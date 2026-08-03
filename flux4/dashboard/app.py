import os
import re
import time
import json
import math
import traceback
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import clickhouse_connect
from openai import OpenAI
from langfuse import Langfuse

load_dotenv()

_lf = Langfuse(
    public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
    secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
)

# ---------------------------------------------------------------------------
# CONFIG  — everything hangs off one schema name
# ---------------------------------------------------------------------------
ORCH = os.environ.get("ORCH_DB", "rca_orch")

NARRATION  = f"{ORCH}.v_narration"                # one row per incident, the contract
INCIDENTS  = f"{ORCH}.incidents"
DIAGNOSES  = f"{ORCH}.diagnoses"
UNIFORMITY = f"{ORCH}.uniformity"
ANOMALIES  = f"{ORCH}.anomalies"                  # per-day detector output
RULEOUT    = f"{ORCH}.v_ruleout"                  # exclusion test, keyed by incident_id
LIFECYCLE  = f"{ORCH}.incident_lifecycle_trace"   # orchestrator stage log
HISTORY    = f"{ORCH}.narration_history"

# Raw events, used for the daily time series and the per-segment split.
# This is the same table the rca_orch views read through v_seg_hourly.
EVENTS = os.environ.get("EVENTS_TABLE", "rca.ad_events")

# Dimension tables, only consulted if EVENTS stores IDs instead of labels.
GEO_DEVICE  = os.environ.get("GEO_DEVICE_TABLE",  "rca.geo_device")
APPS        = os.environ.get("APPS_TABLE",        "rca.apps")
ADVERTISERS = os.environ.get("ADVERTISERS_TABLE", "rca.advertisers")

APP_EVENTS = "rca.app_events"
MODEL      = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b:free")

@asynccontextmanager
async def lifespan(_app):
    yield
    _lf.flush()

app       = FastAPI(title="RCA Dashboard", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

_CH_KWARGS = dict(
    host=os.environ["CH_HOST"],
    port=int(os.environ.get("CH_PORT", 8443)),
    username=os.environ.get("CH_USER", "default"),
    password=os.environ["CH_PASSWORD"],
    secure=True,
    connect_timeout=30,
    send_receive_timeout=120,
)

def ch():
    return clickhouse_connect.get_client(**_CH_KWARGS)

llm = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

# ---------------------------------------------------------------------------
# EVENTS TABLE SHAPE
# The events table may carry dimension labels directly (region, os_version, ...)
# or only foreign keys (geo_device_id, app_id, advertiser_id). Probe once and
# build the right join either way, so the dashboard does not care which it is.
# ---------------------------------------------------------------------------
DIM_FK = {
    "os_version":     (GEO_DEVICE,  "geo_device_id"),
    "region":         (GEO_DEVICE,  "geo_device_id"),
    "country":        (GEO_DEVICE,  "geo_device_id"),
    "device_model":   (GEO_DEVICE,  "geo_device_id"),
    "category":       (APPS,        "app_id"),
    "publisher_tier": (APPS,        "app_id"),
    "vertical":       (ADVERTISERS, "advertiser_id"),
    "campaign_type":  (ADVERTISERS, "advertiser_id"),
    "ad_format":      (None,        None),
}

_SHAPE: Dict[str, Any] = {"cols": None, "at": 0.0, "err": None}

def events_columns(client, force: bool = False) -> set:
    now = time.time()
    if not force and _SHAPE["cols"] is not None and now - _SHAPE["at"] < 300:
        return _SHAPE["cols"]
    db, _, tbl = EVENTS.partition(".")
    try:
        res = client.query(
            "SELECT name FROM system.columns WHERE database = {d:String} AND table = {t:String}",
            parameters={"d": db, "t": tbl})
        cols = {r[0] for r in res.result_rows}
        _SHAPE.update({"cols": cols, "at": now, "err": None if cols else f"{EVENTS} has no columns"})
    except Exception as e:
        cols = set()
        _SHAPE.update({"cols": cols, "at": now, "err": str(e)})
    return cols


def dim_join(client, dim: str):
    """(join clause, value expression) for `dim` against EVENTS aliased `e`."""
    cols = events_columns(client)
    if dim in cols:                       # label stored directly on the event row
        return "", f"e.{dim}"
    fk = DIM_FK.get(dim)
    if fk and fk[0] and fk[1] in cols:    # resolve through the dimension table
        return f"INNER JOIN {fk[0]} AS dt ON dt.{fk[1]} = e.{fk[1]}", f"dt.{dim}"
    return None, None                     # not resolvable


# Conditional numerator / denominator. {p} = prefix, {c} = window filter.
METRIC_AGG = {
    "requests":    ("countIf({c})",                  None),
    "revenue":     ("sumIf({p}revenue, {c})",        None),
    "fill_rate":   ("sumIf({p}is_filled, {c})",      "countIf({c})"),
    "render_rate": ("sumIf({p}is_impression, {c})",  "sumIf({p}is_filled, {c})"),
    "ctr":         ("sumIf({p}is_click, {c})",       "sumIf({p}is_impression, {c})"),
    "ecpm":        ("sumIf({p}revenue, {c}) * 1000", "sumIf({p}is_impression, {c})"),
    "rpr":         ("sumIf({p}revenue, {c})",        "countIf({c})"),
}

def agg(metric: str, cond: str, prefix: str = "e."):
    n, d = METRIC_AGG.get(metric, METRIC_AGG["requests"])
    fmt = lambda s: None if s is None else s.format(p=prefix, c=cond)
    return fmt(n), fmt(d)


METRIC_PLAIN = {
    "requests":    ("count()",               None),
    "revenue":     ("sum(e.revenue)",        None),
    "fill_rate":   ("sum(e.is_filled)",      "count()"),
    "render_rate": ("sum(e.is_impression)",  "sum(e.is_filled)"),
    "ctr":         ("sum(e.is_click)",       "sum(e.is_impression)"),
    "ecpm":        ("sum(e.revenue) * 1000", "sum(e.is_impression)"),
    "rpr":         ("sum(e.revenue)",        "count()"),
}

def num_den(metric: str):
    return METRIC_PLAIN.get(metric, METRIC_PLAIN["requests"])


def metric_of(row: Dict[str, float], metric: str) -> Optional[float]:
    r, fl, i, cl, rev = (row["requests"], row["fills"], row["impressions"],
                         row["clicks"], row["revenue"])
    if metric == "requests":    return float(r)
    if metric == "revenue":     return float(rev)
    if metric == "fill_rate":   return fl / r if r else None
    if metric == "render_rate": return i / fl if fl else None
    if metric == "ctr":         return cl / i if i else None
    if metric == "ecpm":        return rev * 1000 / i if i else None
    if metric == "rpr":         return rev / r if r else None
    return None


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def rows_to_dicts(result) -> List[Dict[str, Any]]:
    return [dict(zip(result.column_names, r)) for r in result.result_rows]


def jsonable(v):
    if isinstance(v, Decimal):        return float(v)
    if isinstance(v, bool):           return v
    if hasattr(v, "isoformat"):       return v.isoformat()
    if isinstance(v, (list, tuple)):  return [jsonable(x) for x in v]
    return v


def serialize_row(row: Dict) -> Dict:
    return {k: jsonable(v) for k, v in row.items()}


def f(v) -> Optional[float]:
    try:
        if v is None: return None
        x = float(v)
        return None if (math.isnan(x) or math.isinf(x)) else x
    except Exception:
        return None


def pairs(arr) -> List[Dict[str, Any]]:
    """Array(Tuple(String, Float64)) -> [{'key','value'}]"""
    out = []
    for item in (arr or []):
        try:
            out.append({"key": str(item[0]), "value": f(item[1])})
        except Exception:
            continue
    return out


class Timer:
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self._t0 = time.time()

    def mark(self, label: str) -> int:
        now = time.time()
        ms = int(round((now - self._t0) * 1000))
        self._t0 = now
        self.steps.append({"label": label, "ms": ms})
        return ms

    def total(self) -> int:
        return sum(s["ms"] for s in self.steps)


def log_event(endpoint: str, incident_id: str, status: str, stage: str,
              latency_ms: int, error: str = ""):
    try:
        ch().insert(APP_EVENTS,
            [[endpoint, str(incident_id or ""), status, stage,
              int(latency_ms), 0, error[:500], ""]],
            column_names=["endpoint", "run_id", "status", "stage",
                          "latency_ms", "rows_returned", "error", "trace_id"])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GLOBAL DAILY  (one scan powers every global chart; cached in-process)
# ---------------------------------------------------------------------------
_GD: Dict[str, Any] = {"at": 0.0, "rows": None, "err": None}
_GD_TTL = float(os.environ.get("EVENTS_CACHE_TTL", 30))

def global_daily(client, force: bool = False) -> List[Dict[str, Any]]:
    now = time.time()
    if not force and _GD["rows"] is not None and now - _GD["at"] < _GD_TTL:
        return _GD["rows"]
    try:
        res = client.query(f"""
            SELECT toDate(event_time) AS d,
                   count()            AS requests,
                   sum(is_filled)     AS fills,
                   sum(is_impression) AS impressions,
                   sum(is_click)      AS clicks,
                   sum(revenue)       AS revenue
            FROM {EVENTS}
            GROUP BY d ORDER BY d
        """)
        rows = [{"d": str(r[0]), "requests": float(r[1]), "fills": float(r[2]),
                 "impressions": float(r[3]), "clicks": float(r[4]),
                 "revenue": float(r[5])} for r in res.result_rows]
        _GD.update({"at": now, "rows": rows, "err": None})
    except Exception as e:
        _GD.update({"at": now, "rows": [], "err": str(e)})
    return _GD["rows"]


# ---------------------------------------------------------------------------
# NARRATION VIEW  (the single source of truth for incidents)
# ---------------------------------------------------------------------------
NARRATION_COLS = """
    incident_id, metric, window_start, window_end, days,
    metric_change_pct, peak_z, culprit_dim, culprit_val,
    culprit_baseline, culprit_value, culprit_change_pct,
    culprit_share_pct, explains_pct,
    global_without_culprit, global_without_culprit_baseline,
    clears_anomaly, ruled_out_segments, ruled_out_dimensions, verdict
"""

# v_narration and v_ruleout are views that recompute on every call (3-8s each), so
# each is fetched once for all incidents and served from a short-lived cache.
_NARR: Dict[str, Any] = {"at": 0.0, "rows": None}
_RO:   Dict[str, Any] = {"at": 0.0, "by_id": None}

# The orchestrator's refresh views run every 15s, so hold results only briefly.
# Long enough to spare the 3-8s recompute on rapid clicks, short enough that the
# page tracks a pipeline that is still loading. Any endpoint accepts ?fresh=1.
_VIEW_TTL = float(os.environ.get("VIEW_CACHE_TTL", 25))


def narration_rows(client, incident_id: Optional[str] = None,
                   force: bool = False) -> List[Dict]:
    now = time.time()
    if force or _NARR["rows"] is None or now - _NARR["at"] >= _VIEW_TTL:
        sql = f"SELECT {NARRATION_COLS.strip()} FROM {NARRATION} ORDER BY window_start, metric"
        with _lf.start_as_current_observation(
            name="ch:v_narration", as_type="retriever",
            input={"sql": sql},
            metadata={"source_table": NARRATION, "schema": ORCH, "forced": force},
        ):
            res = client.query(sql)
            rows_fetched = rows_to_dicts(res)
            _NARR.update({"at": now, "rows": rows_fetched})
            _lf.update_current_span(output={"rows": len(rows_fetched)})
    rows = _NARR["rows"]
    if incident_id:
        return [r for r in rows if r["incident_id"] == incident_id]
    return rows


def shape_narration(r: Dict) -> Dict:
    row = serialize_row(r)
    row["clears_anomaly"] = 1 if r.get("clears_anomaly") else 0
    row["ruled_out_segments"] = [
        {"key": p["key"], "explains_pct": p["value"],
         "dim": p["key"].split("=")[0], "val": p["key"].split("=", 1)[-1]}
        for p in pairs(r.get("ruled_out_segments"))
    ]
    row["ruled_out_dimensions"] = [
        {"dim": p["key"], "spread": p["value"]}
        for p in pairs(r.get("ruled_out_dimensions"))
    ]
    for k in ("metric_change_pct", "peak_z", "culprit_baseline", "culprit_value",
              "culprit_change_pct", "culprit_share_pct", "explains_pct",
              "global_without_culprit", "global_without_culprit_baseline"):
        row[k] = f(row.get(k))
    return row


_UNIF: Dict[str, Any] = {"at": 0.0, "by_id": None}


def uniformity_rows(client, incident_id: str, force: bool = False) -> List[Dict]:
    """Spread of the culprit's effect across every other dimension.

    v_narration only carries (dimension, spread); the uniformity table also has the
    worst and best segment deltas, which is what makes the range readable.
    """
    now = time.time()
    if force or _UNIF["by_id"] is None or now - _UNIF["at"] >= _VIEW_TTL:
        by_id: Dict[str, List[Dict]] = {}
        try:
            res = client.query(f"""
                SELECT incident_id, other_dim, spread, worst, best
                FROM {UNIFORMITY} ORDER BY incident_id, spread ASC
            """)
            for r in res.result_rows:
                by_id.setdefault(str(r[0]), []).append({
                    "dim": str(r[1]), "spread": f(r[2]),
                    "worst": f(r[3]), "best": f(r[4]),
                })
        except Exception:
            by_id = {}
        _UNIF.update({"at": now, "by_id": by_id})
    return (_UNIF["by_id"] or {}).get(incident_id, [])


def detection_row(client, metric: str, d) -> Optional[Dict]:
    try:
        res = client.query(f"""
            SELECT value, baseline, effect, z, n FROM {ANOMALIES}
            WHERE metric = {{m:String}} AND dim = '__all__' AND d = {{d:Date}} LIMIT 1
        """, parameters={"m": metric, "d": str(d)})
        if not res.result_rows:
            return None
        out = {k: f(v) for k, v in zip(res.column_names, res.result_rows[0])}
        out["n"] = int(out["n"]) if out.get("n") is not None else None
        return out
    except Exception:
        return None


def ruleout_rows(client, incident_id: str, limit: int = 10,
                 force: bool = False) -> List[Dict]:
    """Exclusion test straight out of the orchestrator's own view."""
    now = time.time()
    if force or _RO["by_id"] is None or now - _RO["at"] >= _VIEW_TTL:
        by_id: Dict[str, List[Dict]] = {}
        try:
            res = client.query(f"""
                SELECT incident_id, dim, val, excl_incident, excl_baseline,
                       clears_anomaly, residual_effect
                FROM {RULEOUT} ORDER BY incident_id, residual_effect ASC
            """)
            for r in res.result_rows:
                by_id.setdefault(str(r[0]), []).append({
                    "dim": str(r[1]), "val": str(r[2]),
                    "excl_incident": f(r[3]), "excl_baseline": f(r[4]),
                    "clears_anomaly": 1 if r[5] else 0, "residual": f(r[6]),
                })
        except Exception:
            by_id = {}
        _RO.update({"at": now, "by_id": by_id})
    return (_RO["by_id"] or {}).get(incident_id, [])[:limit]


# Stage labels for the orchestrator lifecycle log.
STAGE_LABEL = {
    "anomaly_detected":            "Detect the anomaly",
    "incident_created_or_updated": "Open the incident window",
    "diagnosis":                   "Attribute across every segment",
    "uniformity":                  "Test uniformity across other dimensions",
    "ruleout":                     "Exclusion test",
    "narration":                   "Publish the narration",
}


def lifecycle_rows(client, incident_id: str) -> List[Dict]:
    """One row per orchestrator stage.

    The refresh views re-record the same event every 15s, so the raw log holds
    ~100 rows per incident. Collapse to the latest entry per stage and report how
    many distinct records that stage covered.
    """
    try:
        # Aliases must not reuse a source column name: `argMax(details, ...) AS details`
        # reads as an aggregate inside an aggregate and ClickHouse rejects it.
        res = client.query(f"""
            SELECT stage,
                   min(stage_order)                AS ord,
                   uniqExact(record_key)           AS n_records,
                   max(observed_at)                AS last_at,
                   argMax(record_key, observed_at) AS last_key,
                   argMax(details,    observed_at) AS last_details
            FROM {LIFECYCLE} WHERE incident_id = {{id:String}}
            GROUP BY stage ORDER BY ord ASC
        """, parameters={"id": incident_id})
        out = []
        for r in res.result_rows:
            stage = str(r[0])
            try:
                details = json.loads(r[5]) if r[5] else {}
            except Exception:
                details = {}
            out.append({
                "stage":       stage,
                "label":       STAGE_LABEL.get(stage, stage.replace("_", " ").capitalize()),
                "order":       int(r[1]),
                "records":     int(r[2]),
                "observed_at": r[3].isoformat() if r[3] else None,
                "record_key":  str(r[4]),
                "details":     details,
            })
        return out
    except Exception as e:
        # Surfaced in the response so a broken trace query is visible, not silent.
        return [{"stage": "error", "label": "Lifecycle trace unavailable", "order": 0,
                 "records": 0, "observed_at": None, "record_key": "",
                 "details": {"error": str(e).split("(for url")[0][:200]}}]


def breakdown_series(client, metric: str, dim: str, b0, i1, pad: int = 10):
    if not dim:
        return []
    join, valexpr = dim_join(client, dim)
    if valexpr is None:
        return []
    n_expr, d_expr = num_den(metric)
    vexpr = n_expr if d_expr is None else f"{n_expr} / nullIf({d_expr}, 0)"
    start = str(date.fromisoformat(str(b0)) - timedelta(days=10))
    end   = str(date.fromisoformat(str(i1)) + timedelta(days=pad))
    try:
        res = client.query(f"""
            SELECT toDate(e.event_time) AS d, {valexpr} AS val, {vexpr} AS v, count() AS n
            FROM {EVENTS} AS e
            {join}
            WHERE toDate(e.event_time) BETWEEN {{s:Date}} AND {{e2:Date}}
            GROUP BY d, val HAVING n >= 50 AND v IS NOT NULL
            ORDER BY val, d
        """, parameters={"s": start, "e2": end})
    except Exception:
        return []
    by_val: Dict[str, list] = {}
    for r in res.result_rows:
        by_val.setdefault(str(r[1]), []).append({"d": str(r[0]), "v": f(r[2])})
    return [{"val": k, "points": v} for k, v in by_val.items()]


def revenue_impact(gd: List[Dict], i0, i1, change_pct: Optional[float]):
    if not gd:
        return None
    s0, s1 = str(i0), str(i1)
    actual = sum(r["revenue"] for r in gd if s0 <= r["d"] <= s1)
    eff = (change_pct or 0) / 100.0
    if eff >= 0 or (1 + eff) == 0:
        return {"actual": actual, "expected": actual, "shortfall": 0.0}
    expected = actual / (1 + eff)
    return {"actual": actual, "expected": expected, "shortfall": expected - actual}


def factor_decomposition(gd: List[Dict], d, lookback: int = 7):
    idx = next((k for k, r in enumerate(gd) if r["d"] == str(d)), None)
    if idx is None or idx < 1:
        return None
    prev = gd[max(0, idx - lookback):idx]
    if not prev:
        return None
    cur = gd[idx]
    b = {k: sum(p[k] for p in prev) / len(prev)
         for k in ("requests", "fills", "impressions", "revenue")}
    try:
        lg = lambda x, y: math.log(x / y) if (x > 0 and y > 0) else 0.0
        return {
            "l_requests":    100 * lg(cur["requests"], b["requests"]),
            "l_fill_rate":   100 * lg(cur["fills"] / cur["requests"], b["fills"] / b["requests"]),
            "l_render_rate": 100 * lg(cur["impressions"] / cur["fills"], b["impressions"] / b["fills"]),
            "l_ecpm":        100 * lg(cur["revenue"] / cur["impressions"], b["revenue"] / b["impressions"]),
            "rev_change":    100 * (cur["revenue"] / b["revenue"] - 1) if b["revenue"] else 0.0,
        }
    except (ZeroDivisionError, ValueError):
        return None


# ---------------------------------------------------------------------------
# VALIDATION QUERIES
# One entry per key computation so the dashboard can show the exact SQL
# behind each number for manual reproduction.
# ---------------------------------------------------------------------------

def build_queries(row: Dict, orch: str, events: str) -> List[Dict[str, str]]:
    inc_id = row.get("incident_id", "")
    metric = row.get("metric", "")
    dim    = row.get("culprit_dim") or ""
    w0     = str(row.get("window_start", ""))
    w1     = str(row.get("window_end",   ""))

    try:
        series_start = str(date.fromisoformat(w0) - timedelta(days=10))
        series_end   = str(date.fromisoformat(w1) + timedelta(days=10))
    except Exception:
        series_start, series_end = w0, w1

    metric_expr = {
        "ecpm":        "sum(revenue) * 1000 / nullIf(sum(is_impression), 0)",
        "fill_rate":   "sum(is_filled)      / nullIf(count(), 0)",
        "render_rate": "sum(is_impression)  / nullIf(sum(is_filled), 0)",
        "ctr":         "sum(is_click)       / nullIf(sum(is_impression), 0)",
        "revenue":     "sum(revenue)",
        "rpr":         "sum(revenue)        / nullIf(count(), 0)",
        "requests":    "count()",
    }.get(metric, "count()")

    qs: List[Dict[str, str]] = [
        {
            "label": "Core result — v_narration",
            "sql": (
                f"SELECT *\n"
                f"FROM {orch}.v_narration\n"
                f"WHERE incident_id = '{inc_id}'"
            ),
        },
        {
            "label": "Detection — anomalies",
            "sql": (
                f"SELECT value, baseline, effect, z, n\n"
                f"FROM {orch}.anomalies\n"
                f"WHERE metric = '{metric}'\n"
                f"  AND dim    = '__all__'\n"
                f"  AND d      = '{w0}'"
            ),
        },
        {
            "label": "Attribution — diagnoses",
            "sql": (
                f"SELECT dim, val, incident_val, baseline_val, contribution, share_pct\n"
                f"FROM {orch}.diagnoses\n"
                f"WHERE incident_id = '{inc_id}'\n"
                f"ORDER BY abs(contribution) DESC\n"
                f"LIMIT 20"
            ),
        },
        {
            "label": "Exclusion test — v_ruleout",
            "sql": (
                f"SELECT dim, val, excl_incident, excl_baseline,\n"
                f"       clears_anomaly, residual_effect\n"
                f"FROM {orch}.v_ruleout\n"
                f"WHERE incident_id = '{inc_id}'\n"
                f"ORDER BY residual_effect ASC"
            ),
        },
        {
            "label": "Orchestrator lifecycle — incident_lifecycle_trace",
            "sql": (
                f"SELECT stage, min(stage_order) AS ord,\n"
                f"       uniqExact(record_key)           AS n_records,\n"
                f"       max(observed_at)                AS last_at,\n"
                f"       argMax(record_key, observed_at) AS last_key\n"
                f"FROM {orch}.incident_lifecycle_trace\n"
                f"WHERE incident_id = '{inc_id}'\n"
                f"GROUP BY stage\n"
                f"ORDER BY ord ASC"
            ),
        },
    ]

    if dim:
        qs.insert(4, {
            "label": f"Segment time series — split by {dim}",
            "sql": (
                f"SELECT toDate(event_time) AS d,\n"
                f"       {dim} AS val,\n"
                f"       {metric_expr} AS v,\n"
                f"       count() AS n\n"
                f"FROM {events}\n"
                f"WHERE toDate(event_time) BETWEEN '{series_start}' AND '{series_end}'\n"
                f"GROUP BY d, val\n"
                f"HAVING n >= 50\n"
                f"   AND v IS NOT NULL\n"
                f"ORDER BY val, d"
            ),
        })

    return qs


# ---------------------------------------------------------------------------
# NARRATION TEXT
# ---------------------------------------------------------------------------
_NARR_CACHE: Dict[str, str] = {}

NARRATE_PROMPT = """You summarise one incident from an automated root-cause system.
Write 3 short sentences of plain English for a non-technical reader.

Sentence 1: which metric moved, by how much, over which dates.
Sentence 2: which segment caused it, its share of traffic, the share of the move it explains.
Sentence 3: the exclusion proof, if present.

Rules:
- Never use em-dashes. Use full stops.
- Never print raw identifiers. Say "OS version" not os_version.
- Every number must come from the data given. Never invent one.
- No markdown, max 90 words."""


def narrate(payload: Dict[str, Any], incident_id: str) -> str:
    if incident_id in _NARR_CACHE:
        return _NARR_CACHE[incident_id]

    with _lf.start_as_current_observation(
        name="llm:narrate", as_type="generation",
        input={"incident_id": incident_id,
               "metric": payload.get("metric"),
               "window_start": str(payload.get("window_start", "")),
               "window_end":   str(payload.get("window_end", ""))},
        model=MODEL,
        metadata={"source_table": NARRATION, "schema": ORCH},
    ):
        try:
            resp = llm.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": NARRATE_PROMPT},
                          {"role": "user", "content": json.dumps(payload, default=str)}],
                max_tokens=260, temperature=0)
            text = re.sub(r"^```[a-z]*\s*|\s*```$", "",
                          (resp.choices[0].message.content or "").strip()).strip()
            if text:
                usage = getattr(resp, "usage", None)
                _lf.update_current_generation(
                    output=text,
                    usage_details={
                        "input":  getattr(usage, "prompt_tokens",     0) if usage else 0,
                        "output": getattr(usage, "completion_tokens", 0) if usage else 0,
                    },
                )
                _NARR_CACHE[incident_id] = text
            return text
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html", context={})


@app.get("/api/diag")
def diag():
    """Which configured table is reachable, and does it hold rows."""
    out = {"schema": ORCH, "events_table": EVENTS, "tables": {}}
    c = ch()
    for label, tbl in [("v_narration", NARRATION), ("incidents", INCIDENTS),
                       ("diagnoses", DIAGNOSES), ("uniformity", UNIFORMITY),
                       ("anomalies", ANOMALIES), ("v_ruleout", RULEOUT),
                       ("lifecycle_trace", LIFECYCLE), ("narration_history", HISTORY),
                       ("events", EVENTS)]:
        try:
            n = c.query(f"SELECT count() FROM {tbl}").result_rows[0][0]
            out["tables"][label] = {"table": tbl, "ok": True, "rows": int(n)}
        except Exception as e:
            out["tables"][label] = {"table": tbl, "ok": False,
                                    "error": str(e).split("(for url")[0][:220]}
    return out


@app.get("/api/pulse")
def pulse(fresh: bool = False):
    t = Timer()
    try:
        c = ch()
        notes: List[str] = []

        try:
            rows = narration_rows(c, force=fresh)
        except Exception as e:
            rows = []
            notes.append(f"{NARRATION}: {str(e).split('(for url')[0][:200]}")
        t.mark("v_narration")

        gd = global_daily(c, force=fresh)
        if _GD.get("err"):
            notes.append(f"{EVENTS}: {str(_GD['err']).split('(for url')[0][:200]}")
        elif not gd:
            notes.append(f"{EVENTS} returned no rows, so the charts will be empty.")
        t.mark("events daily")

        # Volume sanity check. A replay that re-inserts the same day inflates the
        # level metrics while leaving the ratios untouched, which is easy to miss.
        # Flag it rather than quietly charting a spike that is not real.
        if len(gd) >= 5:
            counts = sorted(r["requests"] for r in gd)
            median = counts[len(counts) // 2]
            if median > 0:
                spikes = [(r["d"], r["requests"] / median)
                          for r in gd if r["requests"] > 3 * median]
                if spikes:
                    worst = ", ".join(f"{d} ({m:.1f}x)" for d, m in spikes[:4])
                    notes.append(
                        f"{EVENTS}: {len(spikes)} day(s) hold far more rows than the median "
                        f"of {int(median):,}. Affected: {worst}. Ratio metrics such as fill "
                        f"rate and eCPM are unaffected, but requests and revenue read high "
                        f"on those days.")
        t.mark("volume check")

        missed = 0
        try:
            r3 = c.query(f"""
                SELECT count() FROM (
                    SELECT metric, dim, val FROM {ANOMALIES}
                    WHERE dim != '__all__' AND is_onset AND abs(z) > 20
                    GROUP BY metric, dim, val)""")
            missed = int(r3.result_rows[0][0] or 0)
        except Exception:
            pass
        t.mark("segment-only anomalies")

        at_risk = 0.0
        for r in rows:
            imp = revenue_impact(gd, r["window_start"], r["window_end"],
                                 f(r.get("metric_change_pct")))
            if imp:
                at_risk += imp["shortfall"]

        if rows and not gd:
            notes.append("Incidents loaded, but there is no event data to chart.")
        if not rows:
            notes.append(f"{NARRATION} returned no rows.")

        return {
            "schema":           ORCH,
            "events_table":     EVENTS,
            "total":            len(rows),
            "earliest":         min((str(r["window_start"]) for r in rows), default=None),
            "latest":           max((str(r["window_end"])   for r in rows), default=None),
            "coverage_days":    len(gd),
            "coverage_start":   gd[0]["d"]  if gd else None,
            "coverage_end":     gd[-1]["d"] if gd else None,
            "total_events":     sum(r["requests"] for r in gd) if gd else 0,
            "total_revenue":    sum(r["revenue"]  for r in gd) if gd else 0,
            "missed_by_global": missed,
            "revenue_at_risk":  round(at_risk, 2),
            "notes":            notes,
            "cache_age_s":      round(time.time() - _NARR["at"], 1) if _NARR["at"] else 0,
            "timings":          t.steps,
            "fetch_ms":         t.total(),
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()[-700:]},
                            status_code=500)


@app.get("/api/incidents")
def incidents(fresh: bool = False):
    t0 = time.time()
    try:
        rows = [shape_narration(r) for r in narration_rows(ch(), force=fresh)]
        ms = int((time.time() - t0) * 1000)
        log_event("/api/incidents", "", "success", "clickhouse", ms)
        return {"incidents": rows, "schema": ORCH, "fetch_ms": ms}
    except Exception as e:
        log_event("/api/incidents", "", "failure", "clickhouse",
                  int((time.time() - t0) * 1000), error=str(e))
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()[-700:]},
                            status_code=500)


@app.get("/api/timeseries")
def global_timeseries():
    t = Timer()
    try:
        gd = global_daily(ch())
        t.mark("events daily")
        return {
            "rows": [{
                "d": r["d"],
                "requests":  metric_of(r, "requests"),
                "fill_rate": metric_of(r, "fill_rate"),
                "ecpm":      metric_of(r, "ecpm"),
                "revenue":   metric_of(r, "revenue"),
            } for r in gd],
            "error":    _GD.get("err"),
            "timings":  t.steps,
            "fetch_ms": t.total(),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/incident/{incident_id:path}/timeseries")
def incident_timeseries(incident_id: str):
    t = Timer()
    try:
        c = ch()
        rows = narration_rows(c, incident_id)
        if not rows:
            return JSONResponse({"error": "not found"}, status_code=404)
        r = rows[0]
        t.mark("v_narration")

        metric = r["metric"]
        dim    = r.get("culprit_dim") or ""
        val    = r.get("culprit_val") or ""
        i0, i1 = r["window_start"], r["window_end"]
        b0     = date.fromisoformat(str(i0)) - timedelta(days=7)

        gd = global_daily(c)
        blended = [{"d": x["d"], "v": metric_of(x, metric), "n": x["requests"]} for x in gd]
        t.mark("blended series")

        breakdown = breakdown_series(c, metric, dim, b0, i1) if dim else []
        t.mark("breakdown series")

        return {
            "metric": metric, "dim": dim, "culprit": val,
            "window_start": str(i0), "window_end": str(i1),
            "blended": blended, "breakdown": breakdown,
            "timings": t.steps, "fetch_ms": t.total(),
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()[-700:]},
                            status_code=500)


@app.get("/api/incident/{incident_id:path}")
def incident_detail(incident_id: str, llm_narrate: bool = False, fresh: bool = False):
    t = Timer()
    with _lf.start_as_current_observation(
        name=f"incident:{incident_id}", as_type="span",
        input={"incident_id": incident_id, "llm_narrate": llm_narrate},
        metadata={"source_table": NARRATION, "schema": ORCH},
    ):
        try:
            c = ch()
            rows = narration_rows(c, incident_id, force=fresh)
            if not rows:
                return JSONResponse({"error": f"Not found: {incident_id}"}, status_code=404)
            row = shape_narration(rows[0])
            t.mark("v_narration")

            det = detection_row(c, row["metric"], row["window_start"])
            t.mark("detector")

            # Merge worst/best onto the dimensions v_narration listed as uniform.
            unif = {u["dim"]: u for u in uniformity_rows(c, incident_id, force=fresh)}
            for d0 in row["ruled_out_dimensions"]:
                extra = unif.get(d0["dim"])
                if extra:
                    d0["worst"] = extra["worst"]
                    d0["best"]  = extra["best"]
                    if d0.get("spread") is None:
                        d0["spread"] = extra["spread"]
            for dim, u in unif.items():
                if not any(d0["dim"] == dim for d0 in row["ruled_out_dimensions"]):
                    row["ruled_out_dimensions"].append(u)
            t.mark("uniformity")

            gd  = global_daily(c)
            fac = factor_decomposition(gd, row["window_start"])
            rev = revenue_impact(gd, row["window_start"], row["window_end"],
                                 row.get("metric_change_pct"))
            t.mark("decomposition")

            excl = ruleout_rows(c, incident_id, force=fresh)
            t.mark("exclusion test")

            life = lifecycle_rows(c, incident_id)
            t.mark("lifecycle trace")

            row.update({
                "detection": det, "factor": fac, "revenue": rev,
                "exclusion": excl, "lifecycle": life,
                "baseline_start": str(date.fromisoformat(str(row["window_start"])) - timedelta(days=7)),
                "queries": build_queries(row, ORCH, EVENTS),
                "schema": ORCH,
            })

            row["narration"] = narrate(
                {k: v for k, v in row.items() if k not in ("exclusion", "factor", "lifecycle")},
                incident_id) if llm_narrate else ""
            t.mark("narration")

            result = {**row, "timings": t.steps, "fetch_ms": t.total()}
            _lf.update_current_span(output={"incident_id": incident_id,
                                            "fetch_ms": t.total()})
            log_event("/api/incident", incident_id, "success", "clickhouse", t.total())
            return result
        except Exception as e:
            log_event("/api/incident", incident_id, "failure", "clickhouse", t.total(), error=str(e))
            return JSONResponse({"error": str(e), "trace": traceback.format_exc()[-700:]},
                                status_code=500)


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        return JSONResponse({"error": "no messages"}, status_code=400)
    try:
        resp = llm.chat.completions.create(
            model=MODEL, messages=messages, max_tokens=600, temperature=0.7)
        return {"reply": (resp.choices[0].message.content or "").strip()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/health")
def health():
    try:
        res = ch().query(f"""
            SELECT count() AS calls, countIf(status='success') AS ok,
                   countIf(status='failure') AS failed,
                   round(100*countIf(status='success')/greatest(count(),1), 1) AS success_rate
            FROM {APP_EVENTS} WHERE ts > now() - INTERVAL 24 HOUR""")
        return {"kpi": dict(zip(res.column_names, res.result_rows[0]))}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/context")
def ai_context():
    """Serve the AI analyst instruction file (ai-context.md)."""
    path = Path(__file__).parent / "ai-context.md"
    if not path.exists():
        return PlainTextResponse("")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


class QueryBody(BaseModel):
    sql: str


@app.post("/api/run-query")
def run_query(body: QueryBody):
    """Execute a read-only SELECT query on behalf of the AI assistant."""
    sql = body.sql.strip()
    if not sql.upper().startswith("SELECT"):
        return JSONResponse({"error": "Only SELECT queries are allowed"}, status_code=400)
    try:
        res = ch().query(sql)
        return {
            "columns": list(res.column_names),
            "rows": [list(r) for r in res.result_rows[:100]],
        }
    except Exception as e:
        return JSONResponse({"error": str(e).split("(for url")[0][:400]}, status_code=500)
