"""Live data layer for the RootCauseOS console — ClickHouse HTTP, stdlib only.

Every public function returns ``(data, provenance)`` where provenance is
``{"source": "clickhouse"|"fixture", "query_id", "read_rows", "elapsed_ms"}``.
The UI renders those provenance numbers next to every chart, so a judge can
paste the query_id into ``system.query_log`` and find the exact query.

Rules baked in here:
- Ratios (fill_rate, ecpm, ctr, render_rate) are computed as sum/sum IN SQL,
  never as averages of daily ratios.
- Credentials come from the repo-root ``.env`` (gitignored); this module never
  logs or embeds their values. They travel only in request headers.
- No streamlit import — this module stays pure and testable. Caching happens
  in the panel via ``st.cache_data`` on a thin wrapper.
- On any network/auth/HTTP failure the caller falls back to the checked-in
  fixture series and the provenance says so honestly (source="fixture").
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_PATH = _REPO_ROOT / ".env"
_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "scan_series.json"

_QUERY_TIMEOUT_S = 8
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")  # date.weekday(): 0=Mon


def table() -> str:
    """Fully-qualified events table. RCOS_TABLE overrides (e.g. rca_e2e.events
    for the synthetic rehearsal, or whatever DB the unseen slice loads into);
    default follows CLICKHOUSE_DATABASE."""
    t = os.environ.get("RCOS_TABLE", "").strip()
    return t or f"{_cfg('CLICKHOUSE_DATABASE', 'rca')}.events"


class DataUnavailable(Exception):
    """ClickHouse could not be reached / authenticated / queried."""


def _load_env() -> dict[str, str]:
    """Parse KEY=VALUE lines from the repo-root .env. Tolerates a missing file."""
    out: dict[str, str] = {}
    try:
        text = _ENV_PATH.read_text()
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _cfg(key: str, default: str = "") -> str:
    """Process env wins over .env (same precedence the backend uses)."""
    return os.environ.get(key) or _load_env().get(key, default)


def mode() -> str:
    """"live" | "fixture". RCOS_DATA env var overrides; else live iff .env has a host."""
    override = os.environ.get("RCOS_DATA", "").strip().lower()
    if override in ("live", "fixture"):
        return override
    return "live" if _cfg("CLICKHOUSE_HOST") else "fixture"


def query(sql: str, comment: str = "rcos:ui") -> dict:
    """POST one SQL statement to ClickHouse Cloud over HTTPS, JSON format.

    Returns {"rows": [dict per row], "meta": [...], "query_id": str,
    "summary": {"read_rows": int, "read_bytes": int, "elapsed_ms": float}}.
    The summary comes from the X-ClickHouse-Summary response header — these
    are the provenance numbers the UI shows next to every chart.
    Raises DataUnavailable on any network/auth/HTTP/parse error.
    """
    host = _cfg("CLICKHOUSE_HOST")
    if not host:
        raise DataUnavailable("CLICKHOUSE_HOST not configured (expected in .env)")
    port = _cfg("CLICKHOUSE_PORT", "8443")
    query_id = f"rcos-ui-{uuid.uuid4()}"
    params = {
        "query_id": query_id,
        "log_comment": comment,
        "default_format": "JSON",
        "database": _cfg("CLICKHOUSE_DATABASE", "rca"),
        # final (not streaming) numbers in X-ClickHouse-Summary:
        "wait_end_of_query": "1",
        # UInt64 aggregates as JSON numbers, not strings:
        "output_format_json_quote_64bit_integers": "0",
    }
    url = f"https://{host}:{port}/?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        data=sql.encode("utf-8"),
        method="POST",
        headers={
            # values from .env — never printed or logged
            "X-ClickHouse-User": _cfg("CLICKHOUSE_USER", "default"),
            "X-ClickHouse-Key": _cfg("CLICKHOUSE_PASSWORD"),
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_QUERY_TIMEOUT_S) as resp:
            body = resp.read()
            summary_hdr = resp.headers.get("X-ClickHouse-Summary", "") or "{}"
    except urllib.error.HTTPError as e:
        try:  # ClickHouse puts the SQL error text in the body — no secrets there
            detail = e.read(500).decode("utf-8", "replace").strip()
        except OSError:
            detail = ""
        raise DataUnavailable(f"ClickHouse HTTP {e.code}: {e.reason} {detail}".strip()) from e
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise DataUnavailable(f"ClickHouse unreachable: {e}") from e

    try:
        payload = json.loads(body)
        summary_raw = json.loads(summary_hdr)
    except (ValueError, UnicodeDecodeError) as e:
        raise DataUnavailable(f"ClickHouse response unparseable: {e}") from e

    elapsed_ns = summary_raw.get("elapsed_ns")
    if elapsed_ns is not None:
        elapsed_ms = int(elapsed_ns) / 1e6
    else:  # older servers: fall back to the body's statistics block (seconds)
        elapsed_ms = float(payload.get("statistics", {}).get("elapsed", 0.0)) * 1e3
    return {
        "rows": payload.get("data", []),
        "meta": payload.get("meta", []),
        "query_id": query_id,
        "summary": {
            "read_rows": int(summary_raw.get("read_rows", 0)),
            "read_bytes": int(summary_raw.get("read_bytes", 0)),
            "elapsed_ms": elapsed_ms,
        },
    }


# --- per-incident segment series (for the pin-card trend chart) --------------
# The low-card dimension columns that live on {db}.cube. A segment filter's
# dimension name is whitelisted against THIS set before it reaches SQL — the
# values arrive from the incident bundle / engine API, so treat them as input.
_CUBE_DIMS = frozenset({
    "region", "country", "device_model", "os_version", "category",
    "publisher_tier", "vertical", "campaign_type", "ad_format"})
# metric -> (numerator_expr, denominator_expr | None). Ratios are sum/sum IN SQL.
_SEG_METRIC = {
    "fill_rate": ("fills", "requests"),
    "ecpm": ("revenue * 1000", "impressions"),
    "ctr": ("clicks", "impressions"),
    "requests": ("requests", None),
}


def _cube() -> str:
    return f'{_cfg("CLICKHOUSE_DATABASE", "rca")}.cube'


def _sql_str(v: str) -> str:
    """Single-quote a value for inline SQL (segment values come from the API)."""
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def segment_series(metric: str, filters: list[tuple[str, str]]) -> dict:
    """Daily series for ONE incident's culprit segment vs everyone-else, from
    {db}.cube. ``filters`` is ``[(dim_col, value), ...]`` already parsed from the
    culprit; ``[]`` means a global incident (single line, no complement).

    Returns ``{"days": [...], "seg": [...], "rest": [...] | None, "unit"}`` or
    raises DataUnavailable. Ratios are sum/sum IN SQL so the roll-up is correct.
    We hit the cube (not ``table()`` == events) because only the cube carries the
    low-card dimension columns a segment filter needs.
    """
    num, den = _SEG_METRIC.get(metric, _SEG_METRIC["fill_rate"])
    for col, _ in filters:                       # whitelist: reject unknown dims
        if col not in _CUBE_DIMS:
            raise DataUnavailable(f"segment filter uses unknown dimension {col!r}")
    mask = " AND ".join(f"{col}={_sql_str(val)}" for col, val in filters) or "1"

    def expr(cond: str) -> str:
        return (f"sumIf({num}, {cond})/nullIf(sumIf({den}, {cond}), 0)" if den
                else f"sumIf({num}, {cond})")

    if filters:
        sel = f"{expr(mask)} AS seg, {expr(f'NOT ({mask})')} AS rest"
    else:
        sel = f"{expr(mask)} AS seg, NULL AS rest"
    sql = f"SELECT toString(day) AS d, {sel} FROM {_cube()} GROUP BY day ORDER BY day"
    res = query(sql, comment="rcos:ui:incident:segment_series")
    days, seg, rest = [], [], []
    for r in res["rows"]:
        days.append(r["d"])
        seg.append(None if r.get("seg") is None else float(r["seg"]))
        rest.append(None if r.get("rest") is None else float(r["rest"]))
    return {"days": days, "seg": seg,
            "rest": rest if filters else None,
            "unit": "int" if metric == "requests" else "rate"}


# One row per day over the full loaded range. Ratios are sum/sum IN SQL —
# a fill_rate here is total fills / total requests for the day, never an
# average of hourly ratios. The ratio expressions reference the aggregate
# ALIASES (fills / requests, ...): ClickHouse expands aliases textually, so
# writing sum(...) twice would nest into sum(sum(...)) → ILLEGAL_AGGREGATION.
# dow is derived in Python from the ISO date (deterministic, locale-free).
_DAILY_SQL = """
SELECT
    toDate(event_time)          AS d,
    count()                     AS requests,
    sum(is_filled)              AS fills,
    sum(is_impression)          AS impressions,
    sum(is_click)               AS clicks,
    sum(revenue)                AS revenue,
    fills / requests            AS fill_rate,
    revenue / impressions * 1000 AS ecpm,
    clicks / impressions        AS ctr,
    impressions / fills         AS render_rate
FROM {table}
GROUP BY d
ORDER BY d
"""

_FIXTURE_PROVENANCE = {
    "source": "fixture",
    "query_id": None,
    "read_rows": None,
    "elapsed_ms": None,
}


def _fixture_days() -> tuple[list[dict], dict]:
    """Fallback series from ui/fixtures/scan_series.json, same shape as live.

    The fixture predates the count columns, so fills/impressions/clicks are
    derived from its own measured ratios (fills = requests·fill_rate, etc.).
    """
    try:  # the fixture was deleted in the UI reset; degrade to an empty series
        days = json.loads(_FIXTURE_PATH.read_text())["days"]
    except OSError:
        return [], dict(_FIXTURE_PROVENANCE)
    rows: list[dict] = []
    for day in days:
        r = dict(day)  # copy — never mutate the fixture dicts
        r.setdefault("fills", round(r["requests"] * r["fill_rate"]))
        r.setdefault("impressions", round(r["fills"] * r["render_rate"]))
        r.setdefault("clicks", round(r["impressions"] * r["ctr"]))
        rows.append(r)
    return rows, dict(_FIXTURE_PROVENANCE)


def daily_series() -> tuple[list[dict], dict]:
    """The Scan dataset: one dict per day, live from rca.events.

    Row keys: d, dow, requests, fills, impressions, clicks, revenue,
    fill_rate, ecpm, ctr, render_rate. Falls back to the fixture series
    (provenance marked source="fixture") when ClickHouse is unreachable
    or RCOS_DATA=fixture forces it.
    """
    if mode() == "fixture":
        return _fixture_days()
    try:
        res = query(_DAILY_SQL.format(table=table()), comment="rcos:ui:scan:daily_series")
    except DataUnavailable:
        return _fixture_days()
    rows: list[dict] = []
    for r in res["rows"]:
        d = str(r["d"])
        rows.append({
            "d": d,
            "dow": _DOW[date.fromisoformat(d).weekday()],
            "requests": int(r["requests"]),
            "fills": int(r["fills"]),
            "impressions": int(r["impressions"]),
            "clicks": int(r["clicks"]),
            "revenue": float(r["revenue"]),
            "fill_rate": float(r["fill_rate"]),
            "ecpm": float(r["ecpm"]),
            "ctr": float(r["ctr"]),
            "render_rate": float(r["render_rate"]),
        })
    provenance = {
        "source": "clickhouse",
        "query_id": res["query_id"],
        "read_rows": res["summary"]["read_rows"],
        "elapsed_ms": res["summary"]["elapsed_ms"],
    }
    return rows, provenance


# Timeline grains: bucket expression + how much of ClickHouse's
# "YYYY-MM-DD hh:mm:ss" the grain's label actually needs. The time WINDOW is
# a separate axis, passed by the caller (anchored to max(event_time), not
# wall clock — the dataset is historical).
GRAINS: dict[str, dict] = {
    "month":  {"bucket": "toStartOfMonth(event_time)",  "label_len": 7},
    "day":    {"bucket": "toDate(event_time)",          "label_len": 10},
    "hour":   {"bucket": "toStartOfHour(event_time)",   "label_len": 16},
    "minute": {"bucket": "toStartOfMinute(event_time)", "label_len": 16},
    "second": {"bucket": "event_time",                  "label_len": 19},
}

_GRAIN_SQL = """
SELECT
    {bucket}                    AS d,
    count()                     AS requests,
    sum(is_filled)              AS fills,
    sum(is_impression)          AS impressions,
    sum(is_click)               AS clicks,
    sum(revenue)                AS revenue,
    fills / requests            AS fill_rate,
    revenue / impressions * 1000 AS ecpm,
    clicks / impressions        AS ctr,
    impressions / fills         AS render_rate
FROM {table}
{where}
GROUP BY d
ORDER BY d
"""


def max_event_time() -> str:
    """The dataset's clock: max(event_time) as "YYYY-MM-DD hh:mm:ss".
    Empty string when ClickHouse is unreachable."""
    try:
        res = query("SELECT max(event_time) AS m FROM " + table(),
                    comment="rcos:ui:max_event_time")
        return str(res["rows"][0]["m"]) if res["rows"] else ""
    except DataUnavailable:
        return ""


def series(grain: str = "day", window: str | None = None) -> tuple[list[dict], dict]:
    """One row per time bucket at the requested grain, live from rca.events.

    window is a ClickHouse INTERVAL string ("7 DAY", "30 MINUTE", ...)
    trailing from max(event_time); None means the full loaded range.
    Same ratio rules as daily_series (sum/sum in SQL). Sparse fine-grain
    buckets can have zero impressions/fills — ClickHouse emits null for the
    ratio then, which we ground to 0. Fixture fallback is day-grained only
    (the fixture has no sub-day data) and says so via source="fixture".
    """
    g = GRAINS.get(grain) or GRAINS["day"]
    if mode() == "fixture":
        return _fixture_days()
    where = ""
    if window:
        where = (f"WHERE event_time > (SELECT max(event_time) FROM {table()}) "
                 f"- INTERVAL {window}")
    try:
        res = query(_GRAIN_SQL.format(bucket=g["bucket"], where=where, table=table()),
                    comment=f"rcos:ui:scan:series:{grain}")
    except DataUnavailable:
        return _fixture_days()
    rows: list[dict] = []
    for r in res["rows"]:
        rows.append({
            "d": str(r["d"])[:g["label_len"]],
            "requests": int(r["requests"]),
            "fills": int(r["fills"]),
            "impressions": int(r["impressions"]),
            "clicks": int(r["clicks"]),
            "revenue": float(r["revenue"] or 0),
            "fill_rate": float(r["fill_rate"] or 0),
            "ecpm": float(r["ecpm"] or 0),
            "ctr": float(r["ctr"] or 0),
            "render_rate": float(r["render_rate"] or 0),
        })
    provenance = {
        "source": "clickhouse",
        "query_id": res["query_id"],
        "read_rows": res["summary"]["read_rows"],
        "elapsed_ms": res["summary"]["elapsed_ms"],
    }
    return rows, provenance


def incident_series(metric: str) -> tuple[list[dict], dict]:
    """Per-metric series helper: the same daily rows serve every metric —
    callers pick ``row[metric]`` out of the day dicts. Reuses daily_series().
    """
    return daily_series()
