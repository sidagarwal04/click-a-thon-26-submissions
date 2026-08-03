"""Runner: executes the fixed q1–q6 sequence for one incident, branching only on
returned numbers, and assembles the evidence bundle the narrator gets.

The runner is intentionally stupid (sql/agent/README.md): it fills placeholders from
`whitelist.py`, fires queries in a fixed order, compares numbers to fixed thresholds.
Zero SQL is generated at runtime beyond whitelist substitution; zero decisions are made
by the LLM. Every step is logged live to rca.investigation_steps via detector.tracing;
the narrative is guard-railed by detector.guardrail before publication.

Contract (ARCHITECTURE.md):
    investigate(incident_id)                      — from an rca.incidents row
    investigate_window(metric, start, end, scope) — ad-hoc; creates the row on demand
Deterministic incident ids converge re-investigations (ReplacingMergeTree); pass
force=True to re-run. Windows are measured at date grain — the fixed q1–q5 set
compares whole days against same-weekday baselines (sub-daily grain arrives with the
parked detection work).
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from detector import chdb, guardrail
from detector.tracing import Investigation

from . import narrator
from .whitelist import (ADVERTISER_DIMS, CANDIDATE_CONTRIB_SHARE, CANDIDATE_DOMINANCE,
                        DIRECT_LEVER_GATE, ENTITY_FALLBACK, ENTITY_MIN_VOLUME,
                        LEVER_DIMS, LOG_SHARE_FIELD, METRIC_LEVERS, MIN_CLEAN_DAYS,
                        MIN_VOLUME, MIX_IDENTITY_TOL, NOISE, Q1_FIELD, Q4_THRESH, RATIO, str_array,
                        REVENUE_LEVER_GATE, VOLUME, VOLUME_CANDIDATE_SHARE,
                        VOLUME_CANDIDATE_SPREAD, date_array, noise_pp,
                        normalize_metric, parse_scope, seg_filter, sql_quote)

SQL_DIR = chdb.REPO_ROOT / "sql" / "agent"
_TOKEN_RE = re.compile(r"__[A-Z]+(?:_[A-Z]+)*__")

DIAGNOSED = {"CAUSE_CONFIRMED", "INTERACTION", "MIX_SHIFT", "MIX_INTERACTION",
             "DEMAND_PULLOUT", "VOLUME_CANDIDATE", "GLOBAL_MOVEMENT",
             "PEER_OUTLIER"}   # peer-confirmed = terminal; confidence nuance lives
                               # in diagnoses.verdict_code, not in the status enum
DISMISSED = {"NO_MOVEMENT", "NO_DATA"}
# 'investigating' is never a terminal resting state. Only genuinely unresolved
# outcomes stay open for human eyes: DISAGREEMENT, and no-outlier-found on a
# short-history sweep incident (can neither confirm nor dismiss)
# (PEER_OUTLIER is hedged by construction — only CONFIRMED causes may enter q6
# and re-shape later baselines).


# ── small helpers ─────────────────────────────────────────────────────────────

def _f(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _sql(name: str) -> str:
    """Query text with header comments stripped (logged sql stays exact-executable)."""
    lines = (SQL_DIR / name).read_text().splitlines()
    return "\n".join(l for l in lines if not l.strip().startswith("--")).strip()


def _sub(sql: str, **tokens) -> str:
    for k, v in tokens.items():
        sql = sql.replace(f"__{k}__", v)
    leftover = _TOKEN_RE.findall(sql)
    if leftover:
        raise RuntimeError(f"unresolved SQL tokens {leftover}")
    return sql


def _parse_dt(s: str, end: bool = False) -> datetime:
    s = s.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d" and end:
                dt += timedelta(days=1)   # date-only end means "through that day"
            return dt
        except ValueError:
            continue
    raise ValueError(f"cannot parse datetime {s!r} (use YYYY-MM-DD [HH:MM[:SS]])")


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _window_dates(start: datetime, end: datetime) -> list[str]:
    last = (end - timedelta(seconds=1)).date()
    d, out = start.date(), []
    while d <= last:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in s)


def adhoc_incident_id(start: datetime, end: datetime, metric: str, scope: str) -> str:
    return f"inc_{start:%Y%m%dT%H}_{end:%Y%m%dT%H}_{metric}_{_slug(scope or 'global')}"


def _trim(rows: list[dict], key, n: int = 8) -> list[dict]:
    return sorted(rows, key=lambda r: abs(_f(r.get(key)) or 0), reverse=True)[:n]


# ── persistence ───────────────────────────────────────────────────────────────

def _get_incident(incident_id: str) -> dict | None:
    rows = chdb.query(
        "SELECT incident_id, run_id, source, metric, scope, "
        "toString(window_start) AS window_start, toString(window_end) AS window_end, "
        "z_score, pct_change, status FROM rca.incidents FINAL "
        "WHERE incident_id = {inc:String}", {"inc": incident_id})
    return rows[0] if rows else None


def _write_incident(row: dict, status: str) -> None:
    chdb.insert_rows("rca.incidents", [{
        "incident_id": row["incident_id"], "run_id": row.get("run_id", ""),
        "source": row.get("source", "alert"), "metric": row["metric"],
        "scope": row["scope"], "window_start": row["window_start"],
        "window_end": row["window_end"], "z_score": row.get("z_score", 0.0),
        "pct_change": row.get("pct_change", 0.0), "status": status,
    }])


def _stored_diagnosis(incident_id: str) -> dict | None:
    rows = chdb.query(
        "SELECT d.incident_id AS incident_id, d.headline AS headline, "
        "d.narrative AS narrative, d.evidence AS evidence, d.ruled_out AS ruled_out, "
        "d.llm_model AS llm_model, d.numbers_verified AS numbers_verified, "
        "i.status AS status "
        "FROM (SELECT * FROM rca.diagnoses FINAL WHERE incident_id = {inc:String}) AS d "
        "LEFT JOIN (SELECT incident_id, status FROM rca.incidents FINAL) AS i "
        "USING (incident_id)", {"inc": incident_id})
    if not rows:
        return None
    r = rows[0]
    try:
        evidence = json.loads(r["evidence"])
    except (ValueError, TypeError):
        evidence = {"raw": r["evidence"]}
    return {"incident_id": incident_id, "cached": True, "status": r["status"],
            "verdict": (evidence.get("verdict") or {}).get("code", "UNKNOWN"),
            "headline": r["headline"], "narrative": r["narrative"],
            "numbers_verified": bool(r["numbers_verified"]),
            "ruled_out": r["ruled_out"], "llm_model": r["llm_model"],
            "evidence": evidence, "trace": _trace(incident_id)}


def _trace(incident_id: str) -> list[dict]:
    return chdb.query(
        "SELECT step_no, step_type, hypothesis, decision, duration_ms "
        "FROM rca.investigation_steps WHERE incident_id = {inc:String} "
        "ORDER BY step_no", {"inc": incident_id})


def list_incidents(status: str | None = None, limit: int = 50) -> list[dict]:
    where = "WHERE i.status = {st:String}" if status else ""
    params = {"st": status, "lim": limit} if status else {"lim": limit}
    return chdb.query(
        "SELECT i.incident_id AS incident_id, i.metric AS metric, i.scope AS scope, "
        "toString(i.window_start) AS window_start, toString(i.window_end) AS window_end, "
        "i.status AS status, i.source AS source, round(i.z_score, 1) AS z_score, "
        "round(i.pct_change * 100, 2) AS pct_change_pct, "
        "d.headline AS headline, d.numbers_verified AS numbers_verified "
        "FROM (SELECT * FROM rca.incidents FINAL) AS i "
        "LEFT JOIN (SELECT incident_id, headline, numbers_verified "
        "           FROM rca.diagnoses FINAL) AS d USING (incident_id) "
        f"{where} ORDER BY i.window_start LIMIT {{lim:UInt32}}", params)


# ── query context ─────────────────────────────────────────────────────────────

class _Ctx:
    def __init__(self, row: dict):
        self.row = row
        self.metric = normalize_metric(row["metric"])
        self.scope_dim, self.scope_val, self.scope_sql = parse_scope(row["scope"])
        self.start = _parse_dt(row["window_start"])
        self.end = _parse_dt(row["window_end"])
        self.dates = _window_dates(self.start, self.end)
        # comma-separated set: an unseen slice continuing the timeline shares
        # baselines with earlier datasets (RCA_DATASET="main,unseen")
        self.datasets = [d.strip() for d in
                         os.environ.get("RCA_DATASET", "main").split(",") if d.strip()]
        self.dataset = ",".join(self.datasets)
        self.excluded: list[str] = []
        self.base_dates: list[str] = []
        self.sql_ms = 0
        self.q1_row: dict | None = None
        self._lock = threading.Lock()
        self.parallel = bool(os.environ.get("CH_HOST"))  # clickhouse-local can't do
                                                         # concurrent processes (dir lock)

    def q(self, sql: str, params: dict) -> tuple[list[dict], int]:
        t0 = time.monotonic()
        rows = chdb.query(sql, params)
        ms = int((time.monotonic() - t0) * 1000)
        with self._lock:
            self.sql_ms += ms
        return rows, ms

    def run_batch(self, thunks: list) -> list:
        """Execute query thunks, concurrently when a server is on the other end."""
        if not thunks:
            return []   # a candidate with zero co-moving dims is legal (clean event)
        if not self.parallel or len(thunks) == 1:
            return [t() for t in thunks]
        with ThreadPoolExecutor(max_workers=min(6, len(thunks))) as ex:
            return list(ex.map(lambda t: t(), thunks))

    def scoped(self, extra: str | None = None) -> str:
        if extra:
            return f"({self.scope_sql}) AND ({extra})" if self.scope_sql != "1" else extra
        return self.scope_sql


# ── the individual queries (fill placeholders, fire, return rows+sql+ms) ─────

def _q6(ctx: _Ctx):
    sql = _sql("q6_excluded_dates.sql")
    rows, ms = ctx.q(sql, {"before_date": ctx.dates[0]})
    excl = rows[0]["excluded_dates"] if rows else []
    return [str(d) for d in excl], sql, ms


def _q1(ctx: _Ctx):
    sql = _sub(_sql("q1_decompose.sql"), SCOPE_FILTER=ctx.scope_sql)
    params = {"flagged_dates": date_array(ctx.dates),
              "excluded_dates": date_array(ctx.excluded), "datasets": str_array(ctx.datasets)}
    rows, ms = ctx.q(sql, params)
    return (rows[0] if rows else None), sql, ms


def _q2a_rollup(ctx: _Ctx, dim: str, lever: str):
    spec = RATIO[lever]
    sql = _sub(_sql("q2a_sweep_ratio_rollup.sql"),
               NUM_COL=spec["num_col"], DEN_COL=spec["den_col"])
    rows, ms = ctx.q(sql, {"dim": dim, "inc_dates": date_array(ctx.dates),
                           "base_dates": date_array(ctx.base_dates),
                           "min_volume": MIN_VOLUME, "scale": spec["scale"]})
    return rows, sql, ms


def _q2a_enriched(ctx: _Ctx, dim: str, lever: str, extra: str | None = None,
                  min_volume: int = MIN_VOLUME):
    spec = RATIO[lever]
    sql = _sub(_sql("q2a_sweep_ratio.sql"), DIM=dim, METRIC_NUM=spec["num"],
               METRIC_DEN=spec["den"], SEG_FILTER=seg_filter(dim),
               SCOPE_FILTER=ctx.scoped(extra))
    rows, ms = ctx.q(sql, {"inc_dates": date_array(ctx.dates),
                           "base_dates": date_array(ctx.base_dates),
                           "datasets": str_array(ctx.datasets), "min_volume": min_volume,
                           "scale": spec["scale"]})
    return rows, sql, ms


def _q2b(ctx: _Ctx, dim: str, volume_expr: str):
    sql = _sub(_sql("q2b_sweep_volume.sql"), DIM=dim, VOLUME_EXPR=volume_expr,
               SEG_FILTER=seg_filter(dim), SCOPE_FILTER=ctx.scope_sql)
    rows, ms = ctx.q(sql, {"inc_dates": date_array(ctx.dates),
                           "base_dates": date_array(ctx.base_dates),
                           "datasets": str_array(ctx.datasets)})
    return rows, sql, ms


def _q3(ctx: _Ctx, dim: str, lever: str, cand_dim: str, cand_val: str):
    spec = RATIO[lever]
    sql = _sub(_sql("q3_confound.sql"), DIM=dim, METRIC_NUM=spec["num"],
               METRIC_DEN=spec["den"], SEG_FILTER=seg_filter(dim),
               SCOPE_FILTER=ctx.scope_sql, CANDIDATE_COL=cand_dim)
    rows, ms = ctx.q(sql, {"inc_dates": date_array(ctx.dates),
                           "base_dates": date_array(ctx.base_dates),
                           "datasets": str_array(ctx.datasets), "candidate_value": cand_val,
                           "scale": spec["scale"]})
    return rows, sql, ms


def _q5(ctx: _Ctx, dim: str, lever: str):
    spec = RATIO[lever]
    sql = _sub(_sql("q5_mix.sql"), DIM=dim, METRIC_NUM=spec["num"],
               METRIC_DEN=spec["den"], SEG_FILTER=seg_filter(dim),
               SCOPE_FILTER=ctx.scope_sql)
    rows, ms = ctx.q(sql, {"inc_dates": date_array(ctx.dates),
                           "base_dates": date_array(ctx.base_dates),
                           "datasets": str_array(ctx.datasets), "scale": spec["scale"]})
    return (rows[0] if rows else None), sql, ms


def _q4(ctx: _Ctx, dim: str, lever: str, extra: str | None = None,
        min_volume: int = MIN_VOLUME):
    spec = RATIO[lever]
    sql = _sub(_sql("q4_peer.sql"), DIM=dim, METRIC_NUM=spec["num"],
               METRIC_DEN=spec["den"], SEG_FILTER=seg_filter(dim),
               SCOPE_FILTER=ctx.scoped(extra))
    rows, ms = ctx.q(sql, {"inc_start": _fmt_dt(ctx.start), "inc_end": _fmt_dt(ctx.end),
                           "datasets": str_array(ctx.datasets), "thresh": Q4_THRESH[lever],
                           "min_volume": min_volume, "scale": spec["scale"]})
    return rows, sql, ms


# ── lever decision logic ──────────────────────────────────────────────────────

def _decide_levers(ctx: _Ctx, q1: dict) -> tuple[list[str], list[str]]:
    """Which levers of the identity moved, ranked. Returns (levers, gate_miss_notes)."""
    metric = ctx.metric
    gates = REVENUE_LEVER_GATE if metric == "revenue" else DIRECT_LEVER_GATE
    moved, misses = [], []
    for lever in METRIC_LEVERS[metric]:
        if lever == "ctr":            # not a revenue lever: no q1 gate exists
            continue
        val = _f(q1.get(Q1_FIELD[lever]))
        gate = gates[lever]
        unit = "%" if lever == "requests" else ("pp" if lever != "ecpm" else "$")
        if val is not None and abs(val) >= gate:
            moved.append((lever, val))
        else:
            misses.append(f"{lever} {val if val is not None else 'n/a'} {unit} vs gate {gate}")
    if metric == "revenue":
        def rank(lv):
            share = _f(q1.get(LOG_SHARE_FIELD[lv[0]]))
            return abs(share) if share is not None else abs(lv[1]) / gates[lv[0]]
        moved.sort(key=rank, reverse=True)
    if "ctr" in METRIC_LEVERS[metric] and not moved:
        moved.append(("ctr", None))   # ctr swept ungated when nothing upstream moved
    return [lv for lv, _ in moved], misses


def _global_move_pp(ctx: _Ctx, q1: dict, lever: str):
    if lever == "fill_rate":
        return _f(q1.get("fill_rate_delta_pp"))
    if lever == "render_rate":
        return _f(q1.get("render_rate_delta_pp"))
    if lever == "ecpm":
        d = _f(q1.get("ecpm_delta"))
        return d * 100.0 / RATIO["ecpm"]["scale"] if d is not None else None
    return None                        # requests (volume) and ctr (no q1 field)



def _floor_baseline_pool(ctx: _Ctx, excluded: list[str]) -> tuple[list[str], list[str]]:
    """Baseline hygiene must not starve q1 (EDGE_CASES "floor it" option): for each
    weekday of the window, the 4-week same-weekday candidate pool must keep at least
    MIN_CLEAN_DAYS dates after exclusion — else re-admit the most recent excluded
    dates of that weekday. A same-weekday MEDIAN absorbs moderate contamination; the
    hedged peer path it would otherwise force is strictly weaker. Deterministic,
    zero queries; re-admissions are logged in the q6 step."""
    window_dows = {datetime.strptime(d, "%Y-%m-%d").isoweekday() for d in ctx.dates}
    start = ctx.start.date()
    pool_by_dow: dict[int, list[str]] = {}
    for k in range(1, 29):                       # q1's own lookback: 4 weeks, < start
        d = start - timedelta(days=k)
        if d.isoweekday() in window_dows:
            pool_by_dow.setdefault(d.isoweekday(), []).append(d.isoformat())
    excl = set(excluded)
    readmitted: list[str] = []
    for dow, days in pool_by_dow.items():        # days: most recent first
        clean = [d for d in days if d not in excl]
        need = MIN_CLEAN_DAYS - len(clean)
        for d in days:
            if need <= 0:
                break
            if d in excl:
                excl.discard(d)
                readmitted.append(d)
                need -= 1
    return sorted(excl), sorted(readmitted)


# ── the fixed sequence ────────────────────────────────────────────────────────

def investigate(incident_id: str, force: bool = False) -> dict:
    row = _get_incident(incident_id)
    if row is None:
        raise ValueError(f"unknown incident_id {incident_id!r} — see list_incidents() "
                         "or use investigate_window for an ad-hoc window")
    return _run(row, force)


def investigate_window(metric: str, window_start: str, window_end: str,
                       scope: str = "global", force: bool = False) -> dict:
    metric = normalize_metric(metric)
    parse_scope(scope)                                    # validate early
    start = _parse_dt(window_start)
    end = _parse_dt(window_end, end=True)
    if end <= start:
        raise ValueError("window_end must be after window_start")
    if (end - start) > timedelta(days=62):
        raise ValueError("window too large (max 62 days)")
    scope = (scope or "global").strip() or "global"
    existing = chdb.query(
        "SELECT incident_id FROM rca.incidents FINAL "
        "WHERE metric = {m:String} AND scope = {s:String} "
        "AND window_start = {ws:DateTime} AND window_end = {we:DateTime}",
        {"m": metric, "s": scope, "ws": _fmt_dt(start), "we": _fmt_dt(end)})
    if existing:
        return _run(_get_incident(existing[0]["incident_id"]), force)
    row = {"incident_id": adhoc_incident_id(start, end, metric, scope),
           "run_id": "adhoc", "source": "alert", "metric": metric, "scope": scope,
           "window_start": _fmt_dt(start), "window_end": _fmt_dt(end),
           "z_score": 0.0, "pct_change": 0.0, "status": "detected"}
    return _run(row, force)


def _run(row: dict, force: bool = False) -> dict:
    inc_id = row["incident_id"]
    if not force:
        stored = _stored_diagnosis(inc_id)
        if stored:
            return stored

    ctx = _Ctx(row)
    t_start = time.monotonic()
    _write_incident(row, "investigating")
    inv = Investigation(inc_id, metadata={
        "metric": ctx.metric, "scope": row["scope"],
        "window": [row["window_start"], row["window_end"]], "source": row.get("source")})

    detection = None
    if row.get("source") == "sweep" or _f(row.get("z_score")):
        detection = {"z_score": _f(row.get("z_score")),
                     "pct_change_pct": round((_f(row.get("pct_change")) or 0) * 100, 2)}

    bundle: dict = {
        "incident": {"incident_id": inc_id, "metric": ctx.metric, "scope": row["scope"],
                     "window_start": row["window_start"], "window_end": row["window_end"],
                     "dates": ctx.dates, "datasets": str_array(ctx.datasets),
                     "source": row.get("source", "alert"), "detection": detection},
        "baseline": {}, "q1": None, "levers": {}, "peers": None, "verdict": None,
        "thresholds": {"lever_gates": (REVENUE_LEVER_GATE if ctx.metric == "revenue"
                                       else DIRECT_LEVER_GATE),
                       "noise": NOISE, "candidate_contribution_share": CANDIDATE_CONTRIB_SHARE,
                       "candidate_dominance": CANDIDATE_DOMINANCE,
                       "q4_peer_thresh": Q4_THRESH, "min_clean_days": MIN_CLEAN_DAYS},
    }

    # q6 — baseline hygiene ---------------------------------------------------
    excl, sql6, ms6 = _q6(ctx)
    excl, readmitted = _floor_baseline_pool(ctx, excl)
    ctx.excluded = excl
    bundle["baseline"]["excluded_dates"] = excl
    bundle["baseline"]["readmitted_dates"] = readmitted
    decision = (f"{len(excl)} date(s) excluded from baselines: {excl}" if excl
                else "no prior diagnosed windows — all history clean")
    if readmitted:
        decision += (f"; re-admitted {readmitted} to keep every weekday's pool "
                     f">= {MIN_CLEAN_DAYS} (hygiene must not starve baselines)")
    inv.step("rule_out",
             hypothesis="Baseline hygiene: which past dates are already-diagnosed "
                        "incident windows (they must not contaminate baselines)?",
             sql_text=sql6, result={"excluded_dates": excl,
                                    "readmitted_dates": readmitted},
             decision=decision, duration_ms=ms6)

    # q1 — decompose ----------------------------------------------------------
    q1, sql1, ms1 = _q1(ctx)
    q1 = {k: (v if not isinstance(v, list) else v) for k, v in (q1 or {}).items()}
    ctx.q1_row = q1
    bundle["q1"] = q1 or None
    inc_requests = _f(q1.get("inc_requests")) if q1 else None
    min_clean = int(_f(q1.get("min_clean_days_per_dow")) or 0) if q1 else 0
    ctx.base_dates = [str(d) for d in (q1.get("base_days_used") or [])] if q1 else []
    bundle["baseline"]["base_days_used"] = ctx.base_dates
    bundle["baseline"]["min_clean_days"] = min_clean

    if not q1 or not inc_requests:
        inv.step("decompose",
                 hypothesis=f"Which lever of Revenue = Requests × Fill × Render × eCPM "
                            f"moved over {ctx.dates} (scope {row['scope']})?",
                 sql_text=sql1, result=q1 or {},
                 decision="window contains no events — NO_DATA", duration_ms=ms1)
        bundle["verdict"] = {"code": "NO_DATA", "primary_lever": None, "cause": None,
                             "ruled_out": [], "notes": []}
        return _finish(ctx, inv, bundle, t_start)

    levers, gate_misses = _decide_levers(ctx, q1)
    q1_summary = (f"requests {q1.get('requests_pct')}%, fill {q1.get('fill_rate_delta_pp')} pp, "
                  f"render {q1.get('render_rate_delta_pp')} pp, eCPM {q1.get('ecpm_delta')}$; "
                  f"min_clean_days {min_clean}")
    if min_clean < MIN_CLEAN_DAYS:
        decision = (f"{q1_summary} → fewer than {MIN_CLEAN_DAYS} clean baseline days per "
                    f"weekday: q2/q3/q5 impossible, switching to peer comparison (q4)")
    elif levers:
        decision = f"{q1_summary} → lever(s) moved: {levers} → sweep their dimensions"
    else:
        decision = f"{q1_summary} → no lever beyond threshold"
    inv.step("decompose",
             hypothesis=f"Which lever of Revenue = Requests × Fill × Render × eCPM "
                        f"moved over {ctx.dates} (scope {row['scope']})?",
             sql_text=sql1, result=q1, decision=decision, duration_ms=ms1)

    if min_clean < MIN_CLEAN_DAYS:
        _short_history_path(ctx, inv, bundle)
    elif not levers:
        orig_status = row.get("status")
        if orig_status == "ruled_out_seasonal":
            # detector's classifier called this seasonal; a weekday-corrected baseline
            # showing no movement AGREES with that — narrate it, don't reopen it
            code = "SEASONAL_CONFIRMED"
            notes = ["measurement agrees with the detector's seasonal classification: "
                     "vs a same-weekday baseline no lever moved"]
        elif row.get("source") == "sweep" and orig_status in ("detected", "investigating"):
            code = "DISAGREEMENT"
            notes = ["no lever beyond threshold; both sides' numbers logged"]
        else:
            code, notes = "NO_MOVEMENT", []
        bundle["verdict"] = {"code": code, "primary_lever": None, "cause": None,
                             "ruled_out": [], "gate_misses": gate_misses,
                             "notes": notes}
    else:
        _baseline_path(ctx, inv, bundle, levers)

    return _finish(ctx, inv, bundle, t_start)


# ── baseline path: q2 → [q3 | q5 → …] ────────────────────────────────────────

def _baseline_path(ctx: _Ctx, inv: Investigation, bundle: dict, levers: list[str]):
    for lever in levers:
        bundle["levers"][lever] = _investigate_lever(ctx, inv, bundle, lever)

    primary = levers[0]
    lb = bundle["levers"][primary]
    verdict = {"code": lb["verdict"], "primary_lever": primary,
               "cause": lb.get("cause"), "ruled_out": lb.get("ruled_out", []),
               "notes": []}
    if lb.get("global_evidence"):
        verdict["global_evidence"] = lb["global_evidence"]
    if lb.get("mix_check"):
        verdict["mix_check"] = lb["mix_check"]
    for lv in levers[1:]:
        sec = bundle["levers"][lv]
        if sec.get("cause"):
            c = sec["cause"]
            note = f"secondary lever {lv}: {c.get('seg')} ({c.get('dim')}) — {sec['verdict']}"
            pc = (lb.get("cause") or {})
            if pc.get("seg") == c.get("seg") and pc.get("dim") == c.get("dim"):
                note += " — the same segment explains both levers"
            verdict["notes"].append(note)
        else:
            verdict["notes"].append(f"secondary lever {lv}: {sec['verdict']}")
    bundle["verdict"] = verdict


def _investigate_lever(ctx: _Ctx, inv: Investigation, bundle: dict, lever: str) -> dict:
    q1 = bundle["q1"]
    lb: dict = {"sweeps": {}, "confounds": {}, "verdict": None, "cause": None,
                "ruled_out": []}
    is_ratio = lever in RATIO
    dims = [d for d in LEVER_DIMS[lever] if d != ctx.scope_dim]

    # -- q2 sweep (per dim, parallel) ----------------------------------------
    def sweep_thunk(dim):
        if is_ratio and lever == "fill_rate" and dim in ADVERTISER_DIMS:
            rows, sql, ms = _q2b(ctx, dim, VOLUME["fills"])   # fills probe: fill rate
            return dim, "volume", rows, sql, ms               # undefined by advertiser attrs
        if is_ratio:
            if ctx.scope_sql == "1":
                rows, sql, ms = _q2a_rollup(ctx, dim, lever)
            else:
                rows, sql, ms = _q2a_enriched(ctx, dim, lever)
            return dim, "ratio", rows, sql, ms
        rows, sql, ms = _q2b(ctx, dim, VOLUME["requests"])
        return dim, "volume", rows, sql, ms

    results = ctx.run_batch([lambda d=d: sweep_thunk(d) for d in dims])
    global_pp = _global_move_pp(ctx, q1, lever)

    for dim, kind, rows, sql, ms in results:
        sw = _summarize_sweep(dim, kind, rows, lever, global_pp)
        lb["sweeps"][dim] = sw
        inv.step("dim_scan",
                 hypothesis=f"Sweep {lever} by {dim}: which segment moved, weighted by "
                            f"its share of the denominator?",
                 sql_text=sql, result=rows[:50], decision=sw["decision"],
                 duration_ms=ms)

    if is_ratio and global_pp is None:   # ctr has no q1 field: additivity estimate
        sums = [s["contribution_sum_pp"] for s in lb["sweeps"].values()
                if s.get("contribution_sum_pp") is not None]
        global_pp = max(sums, key=abs) if sums else None
        lb["global_move_pp_est"] = global_pp

    candidate = _pick_candidate(lb["sweeps"], lever, global_pp)

    # entity fallback: standard dims found nothing
    if candidate is None:
        for dim in [d for d in ENTITY_FALLBACK.get(lever, []) if d != ctx.scope_dim]:
            if is_ratio and not (lever == "fill_rate" and dim in ADVERTISER_DIMS):
                rows, sql, ms = _q2a_enriched(ctx, dim, lever,
                                              min_volume=ENTITY_MIN_VOLUME)
                kind = "ratio"
            else:
                expr = VOLUME["fills"] if lever == "fill_rate" else VOLUME["requests"]
                rows, sql, ms = _q2b(ctx, dim, expr)
                kind = "volume"
            sw = _summarize_sweep(dim, kind, rows, lever, global_pp)
            lb["sweeps"][dim] = sw
            inv.step("dim_scan",
                     hypothesis=f"Entity fallback: sweep {lever} by {dim} at raised "
                                f"volume floor — standard dimensions were flat",
                     sql_text=sql, result=rows[:50], decision=sw["decision"],
                     duration_ms=ms)
        candidate = _pick_candidate(lb["sweeps"], lever, global_pp)

    if candidate is not None:
        lb["cause"] = candidate
        if candidate["kind"] == "volume" and lever == "fill_rate":
            lb["verdict"] = "DEMAND_PULLOUT"
        elif candidate["kind"] == "volume":
            lb["verdict"] = "VOLUME_CANDIDATE"
        else:
            lb["verdict"] = "CAUSE_CONFIRMED"
        if is_ratio:
            _confound_pass(ctx, inv, lb, lever, candidate)
        _note_flat_dims(lb)
        return lb

    # all flat → mix gate (ratio levers only), then GLOBAL
    if is_ratio:
        _mix_gate(ctx, inv, lb, lever)
        if lb["verdict"]:
            _note_flat_dims(lb)
            return lb

    lb["verdict"] = "GLOBAL_MOVEMENT"
    lb["global_evidence"] = _global_evidence(lb["sweeps"])
    _note_flat_dims(lb)
    return lb


def _summarize_sweep(dim: str, kind: str, rows: list[dict], lever: str,
                     global_pp) -> dict:
    noise = NOISE.get(lever, 0.005)
    if kind == "ratio":
        rows = sorted(rows, key=lambda r: abs(_f(r.get("contribution_pp")) or 0),
                      reverse=True)
        top = rows[0] if rows else None
        max_delta = max((abs(_f(r.get("delta")) or 0) for r in rows), default=0.0)
        contrib_sum = round(sum(_f(r.get("contribution_pp")) or 0 for r in rows), 4)
        flat = max_delta < noise
        if top is None:
            decision = "no segments above the volume floor"
        elif flat:
            decision = (f"flat: max |delta| {round(max_delta, 4)} < noise {noise} — "
                        f"ruled out by the sweep itself")
        else:
            share = (f", {round((_f(top['contribution_pp']) or 0) / global_pp * 100, 1)}% "
                     f"of the global move" if global_pp else "")
            decision = (f"top: {top['seg']} delta {top.get('delta')} "
                        f"(contribution {top.get('contribution_pp')} pp{share})")
        return {"kind": kind, "rows": _trim(rows, "contribution_pp"),
                "max_abs_delta": round(max_delta, 4), "flat": flat,
                "contribution_sum_pp": contrib_sum, "decision": decision}
    # volume sweep
    rows = sorted(rows, key=lambda r: abs(_f(r.get("share_of_total_change")) or 0),
                  reverse=True)
    pcts = [_f(r.get("pct_change")) for r in rows if _f(r.get("pct_change")) is not None]
    med = sorted(abs(p) for p in pcts)[len(pcts) // 2] if pcts else 0.0
    top = rows[0] if rows else None
    if top is None:
        decision = "no segments"
    else:
        decision = (f"top mover: {top['seg']} {top.get('pct_change')}% vs expected "
                    f"({top.get('share_of_total_change')}% of total change)")
        if pcts:
            decision += (f"; per-segment range {round(min(pcts), 2)}%.."
                         f"{round(max(pcts), 2)}%")
    return {"kind": kind, "rows": _trim(rows, "share_of_total_change"),
            "pct_range": [round(min(pcts), 2), round(max(pcts), 2)] if pcts else None,
            "median_abs_pct": round(med, 2), "decision": decision}


def _pick_candidate(sweeps: dict, lever: str, global_pp) -> dict | None:
    """Best candidate across all sweeps. Ratio candidates (rate moved) outrank volume
    candidates (share moved); within a kind, largest |contribution| / |share| wins."""
    noise = NOISE.get(lever, 0.005)
    ratio_cands, volume_cands = [], []
    for dim, sw in sweeps.items():
        rows = sw["rows"]
        if not rows:
            continue
        top = rows[0]
        if sw["kind"] == "ratio":
            delta = abs(_f(top.get("delta")) or 0)
            contrib = _f(top.get("contribution_pp")) or 0
            runner_up = abs(_f(rows[1].get("delta")) or 0) if len(rows) > 1 else 0.0
            share_ok = (global_pp not in (None, 0)
                        and abs(contrib) >= CANDIDATE_CONTRIB_SHARE * abs(global_pp)
                        and contrib * global_pp > 0)
            dominance_ok = delta >= noise and (runner_up == 0 or
                                               delta > CANDIDATE_DOMINANCE * runner_up)
            if share_ok or dominance_ok:
                cand = {"kind": "ratio", "dim": dim, "seg": top["seg"],
                        "val_inc": top.get("val_inc"), "val_base": top.get("val_base"),
                        "delta": top.get("delta"), "den_inc": top.get("den_inc"),
                        "contribution_pp": top.get("contribution_pp"),
                        "basis": "contribution_share" if share_ok else "dominance"}
                if global_pp:
                    cand["share_of_move_pct"] = round(contrib / global_pp * 100, 1)
                ratio_cands.append((abs(contrib), cand))
        else:
            share = abs(_f(top.get("share_of_total_change")) or 0)
            pct = abs(_f(top.get("pct_change")) or 0)
            if (share >= VOLUME_CANDIDATE_SHARE
                    and pct >= VOLUME_CANDIDATE_SPREAD * max(sw.get("median_abs_pct") or 0, 1e-9)
                    and pct >= 10.0):
                volume_cands.append((share, {
                    "kind": "volume", "dim": dim, "seg": top["seg"],
                    "vol_inc": top.get("vol_inc"),
                    "vol_expected": top.get("vol_expected"),
                    "pct_change": top.get("pct_change"),
                    "share_of_total_change": top.get("share_of_total_change"),
                    "basis": "volume_share"}))
    pool = ratio_cands or volume_cands
    return max(pool, key=lambda c: c[0])[1] if pool else None


def _confound_pass(ctx: _Ctx, inv: Investigation, lb: dict, lever: str,
                   candidate: dict):
    # the ruled-out bar scales with the move: a 13 pp event leaves correlated
    # shadows in sibling dims far above the fixed noise floor sized for ~3 pp
    # events (EDGE_CASES.md q3-calibration follow-up) — 10% of the global move,
    # never below the metric's noise floor
    global_pp = lb.get("global_move_pp_est")
    if global_pp is None:
        global_pp = _global_move_pp(ctx, ctx.q1_row or {}, lever)
    noise = max(NOISE.get(lever, 0.005),
                0.10 * abs(global_pp or 0.0) / 100.0 * RATIO[lever]["scale"])
    signal_dims = [d for d, sw in lb["sweeps"].items()
                   if d != candidate["dim"] and sw["kind"] == "ratio" and not sw["flat"]]

    def q3_thunk(dim):
        rows, sql, ms = _q3(ctx, dim, lever, candidate["dim"], candidate["seg"])
        return dim, rows, sql, ms

    persisting = []
    for dim, rows, sql, ms in ctx.run_batch([lambda d=d: q3_thunk(d) for d in signal_dims]):
        max_resid = max((abs(_f(r.get("delta_excl_candidate")) or 0) for r in rows),
                        default=0.0)
        ruled_out = max_resid < noise
        lb["confounds"][dim] = {"rows": rows[:12], "max_abs_residual": round(max_resid, 4),
                                "ruled_out": ruled_out}
        if ruled_out:
            lb["ruled_out"].append(f"{dim}: residual {round(max_resid, 4)} < {noise} "
                                   f"after excluding {candidate['seg']}")
        else:
            persisting.append((dim, max_resid))
        inv.step("rule_out",
                 hypothesis=f"Is {dim}'s apparent movement a shadow of "
                            f"{candidate['seg']} ({candidate['dim']})? Re-sweep {dim} "
                            f"with it excluded.",
                 sql_text=sql, result=rows[:50],
                 decision=(f"max residual {round(max_resid, 4)} < noise {noise} → "
                           f"{dim} ruled out (shadow)" if ruled_out else
                           f"residual {round(max_resid, 4)} persists ≥ {noise} → "
                           f"not a pure shadow"),
                 duration_ms=ms)

    if persisting:
        dim2, resid = max(persisting, key=lambda p: p[1])
        extra = f"{candidate['dim']} = {sql_quote(candidate['seg'])}"
        rows, sql, ms = _q2a_enriched(ctx, dim2, lever, extra=extra)
        rows = sorted(rows, key=lambda r: abs(_f(r.get("delta")) or 0), reverse=True)
        top = rows[0] if rows else None
        inv.step("drill_down",
                 hypothesis=f"Residual persists on {dim2}: drill the cross "
                            f"{candidate['dim']}={candidate['seg']} × {dim2} — "
                            f"interaction segment?",
                 sql_text=sql, result=rows[:50],
                 decision=(f"cross segment {candidate['seg']} × {top['seg']}: delta "
                           f"{top.get('delta')}" if top else "no cross segments above floor"),
                 duration_ms=ms)
        if top is not None:
            lb["verdict"] = "INTERACTION"
            lb["cause"] = {"kind": "interaction", "dim1": candidate["dim"],
                           "seg1": candidate["seg"], "dim2": dim2, "seg2": top["seg"],
                           "dim": candidate["dim"], "seg": f"{candidate['seg']} × {top['seg']}",
                           "residual": round(resid, 4),
                           "cross_val_inc": top.get("val_inc"),
                           "cross_val_base": top.get("val_base"),
                           "cross_delta": top.get("delta"),
                           "cross_contribution_pp": top.get("contribution_pp")}
            lb["interaction_rows"] = rows[:8]


def _mix_gate(ctx: _Ctx, inv: Investigation, lb: dict, lever: str):
    ratio_dims = [d for d, sw in lb["sweeps"].items() if sw["kind"] == "ratio"]
    if not ratio_dims:
        return
    floor = noise_pp(lever)

    def q5_thunk(dim):
        row, sql, ms = _q5(ctx, dim, lever)
        return dim, row, sql, ms

    mixes = {}
    for dim, mrow, sql, ms in ctx.run_batch([lambda d=d: q5_thunk(d) for d in ratio_dims]):
        if not mrow:
            continue
        w, m = _f(mrow.get("within_effect_pp")) or 0, _f(mrow.get("mix_effect_pp")) or 0
        i, t = _f(mrow.get("interaction_pp")) or 0, _f(mrow.get("total_delta_pp")) or 0
        mixes[dim] = mrow
        inv.step("mix_check",
                 hypothesis=f"All {dim} segments flat — did the global move come from "
                            f"traffic reshuffling between {dim} segments (Kitagawa "
                            f"within/mix/interaction split)?",
                 sql_text=sql, result=mrow,
                 decision=f"within {w} pp, mix {m} pp, interaction {i} pp, total {t} pp"
                          + ("" if abs(w + m + i - t) < MIX_IDENTITY_TOL
                             else " (identity residual above tolerance — inspect)"),
                 duration_ms=ms)
    lb["mix"] = mixes
    if not mixes:
        return

    mix_dim = max(mixes, key=lambda d: abs(_f(mixes[d].get("mix_effect_pp")) or 0))
    mr = mixes[mix_dim]
    w = _f(mr.get("within_effect_pp")) or 0
    m = _f(mr.get("mix_effect_pp")) or 0
    i = _f(mr.get("interaction_pp")) or 0

    if abs(m) >= max(abs(w), floor):
        den_expr = RATIO[lever]["den"]
        rows, sql, ms = _q2b(ctx, mix_dim, den_expr)
        rows = sorted(rows, key=lambda r: abs(_f(r.get("share_of_total_change")) or 0),
                      reverse=True)
        top = rows[0] if rows else None
        inv.step("dim_scan",
                 hypothesis=f"Mix term dominates on {mix_dim}: whose share of "
                            f"traffic changed?",
                 sql_text=sql, result=rows[:50],
                 decision=(f"largest share mover: {top['seg']} {top.get('pct_change')}% "
                           f"vs expected" if top else "no movers found"),
                 duration_ms=ms)
        lb["verdict"] = "MIX_SHIFT"
        lb["cause"] = {"kind": "mix", "dim": mix_dim, "seg": top["seg"] if top else None,
                       "within_effect_pp": mr.get("within_effect_pp"),
                       "mix_effect_pp": mr.get("mix_effect_pp"),
                       "interaction_pp": mr.get("interaction_pp"),
                       "total_delta_pp": mr.get("total_delta_pp"),
                       "top_mover": top}
        lb["mix_movers"] = rows[:8]
    elif abs(i) >= max(abs(w), abs(m), floor):
        sw_rows = lb["sweeps"].get(mix_dim, {}).get("rows") or []
        top_sw = sw_rows[0] if sw_rows else None
        lb["verdict"] = "MIX_INTERACTION"
        lb["cause"] = {"kind": "mix_interaction", "dim": mix_dim,
                       "seg": top_sw.get("seg") if top_sw else None,
                       "within_effect_pp": mr.get("within_effect_pp"),
                       "mix_effect_pp": mr.get("mix_effect_pp"),
                       "interaction_pp": mr.get("interaction_pp"),
                       "total_delta_pp": mr.get("total_delta_pp"),
                       "segment_row": top_sw}
    else:
        lb["mix_check"] = {"dim": mix_dim,
                           "within_effect_pp": mr.get("within_effect_pp"),
                           "mix_effect_pp": mr.get("mix_effect_pp")}


def _note_flat_dims(lb: dict):
    for dim, sw in lb["sweeps"].items():
        if sw.get("flat"):
            lb["ruled_out"].append(f"{dim}: flat in sweep (max |delta| "
                                   f"{sw['max_abs_delta']})")


def _global_evidence(sweeps: dict) -> dict:
    max_contrib = 0.0
    pct_lo, pct_hi = None, None
    for sw in sweeps.values():
        if sw["kind"] == "ratio":
            for r in sw["rows"]:
                c = abs(_f(r.get("contribution_pp")) or 0)
                max_contrib = max(max_contrib, c)
        elif sw.get("pct_range"):
            lo, hi = sw["pct_range"]
            pct_lo = lo if pct_lo is None else min(pct_lo, lo)
            pct_hi = hi if pct_hi is None else max(pct_hi, hi)
    out: dict = {"max_contribution_pp": round(max_contrib, 4)}
    if pct_lo is not None:
        out["pct_range"] = [pct_lo, pct_hi]
    return out


# ── short-history path: q4 only ──────────────────────────────────────────────

def _short_history_path(ctx: _Ctx, inv: Investigation, bundle: dict):
    metric = ctx.metric
    levers = [l for l in METRIC_LEVERS[metric] if l in RATIO]
    if metric == "revenue":
        levers = ["fill_rate", "render_rate", "ecpm"]
    if not levers:
        bundle["verdict"] = {"code": "SHORT_HISTORY_VOLUME", "primary_lever": None,
                             "cause": None, "ruled_out": [],
                             "notes": ["volume metric with no baseline: peer comparison "
                                       "applies to ratio metrics only"]}
        return

    # detection's direction, when known: a detected spike should surface HIGH peers,
    # not a structurally-low segment (peer differences are not peer anomalies)
    pct = _f(ctx.row.get("pct_change")) or 0
    want = ("ANOMALOUS_HIGH" if pct > 0 else "ANOMALOUS_LOW") if pct else None

    peers: dict = {}
    found: list[tuple] = []      # (lever, dim, row)
    for lever in levers:
        dims = [d for d in LEVER_DIMS[lever] if d != ctx.scope_dim
                and not (lever == "fill_rate" and d in ADVERTISER_DIMS)]

        def q4_thunk(dim, lv=lever):
            rows, sql, ms = _q4(ctx, dim, lv)
            return dim, rows, sql, ms

        for dim, rows, sql, ms in ctx.run_batch([lambda d=d: q4_thunk(d) for d in dims]):
            rows = sorted(rows, key=lambda r: abs(_f(r.get("vs_peer")) or 0), reverse=True)
            outliers = [r for r in rows if r.get("verdict") in ("ANOMALOUS_LOW",
                                                                "ANOMALOUS_HIGH")]
            peers.setdefault(lever, {})[dim] = {"rows": rows[:8],
                                                "outlier": outliers[0] if outliers else None}
            inv.step("peer_check",
                     hypothesis=f"No baseline exists — does any {dim} segment deviate "
                                f"from its sibling median on {lever} inside the window?",
                     sql_text=sql, result=rows[:50],
                     decision=(f"outlier: {outliers[0]['seg']} vs_peer "
                               f"{outliers[0].get('vs_peer')} ({outliers[0]['verdict']})"
                               if outliers else "all segments within peer threshold"),
                     duration_ms=ms)
            found += [(lever, dim, r) for r in outliers]

    best = max(found, key=lambda o: (o[2].get("verdict") == want,
                                     abs(_f(o[2].get("vs_peer")) or 0))) if found else None

    bundle["peers"] = peers
    if best is None:
        bundle["verdict"] = {"code": "NO_PEER_OUTLIER", "primary_lever": levers[0],
                             "cause": None, "ruled_out": [],
                             "notes": ["global-vs-normal cannot be distinguished without "
                                       "a baseline; detection's models own that verdict"]}
        return

    lever, dim, top = best
    ruled_out = []
    extra = f"{dim} != {sql_quote(top['seg'])}"
    others = [d for d in LEVER_DIMS[lever] if d != dim and d != ctx.scope_dim
              and not (lever == "fill_rate" and d in ADVERTISER_DIMS)]

    def q4x_thunk(d):
        rows, sql, ms = _q4(ctx, d, lever, extra=extra)
        return d, rows, sql, ms

    for d, rows, sql, ms in ctx.run_batch([lambda d=d: q4x_thunk(d) for d in others]):
        rows = sorted(rows, key=lambda r: abs(_f(r.get("vs_peer")) or 0), reverse=True)
        still = [r for r in rows if r.get("verdict") != "NORMAL"]
        if not still:
            worst = round(abs(_f(rows[0].get("vs_peer")) or 0), 4) if rows else 0.0
            ruled_out.append(f"{d}: back to peer-normal with {top['seg']} excluded "
                             f"(worst {worst})")
        inv.step("peer_check",
                 hypothesis=f"Shadow check: rerun {d} peers with {top['seg']} excluded — "
                            f"does it collapse to peer-normal?",
                 sql_text=sql, result=rows[:50],
                 decision=("collapses to peer-normal → ruled out" if not still else
                           f"{still[0]['seg']} still {still[0].get('vs_peer')} vs peers"),
                 duration_ms=ms)

    bundle["verdict"] = {"code": "PEER_OUTLIER", "primary_lever": lever,
                         "cause": {"kind": "peer", "dim": dim, "seg": top["seg"],
                                   "val": top.get("val"),
                                   "peer_median": top.get("peer_median"),
                                   "vs_peer": top.get("vs_peer")},
                         "ruled_out": ruled_out, "notes": []}


# ── narrate → guardrail → persist → close ────────────────────────────────────

def _finish(ctx: _Ctx, inv: Investigation, bundle: dict, t_start: float) -> dict:
    code = bundle["verdict"]["code"]
    bundle["timing_ms"] = {"sql_total": ctx.sql_ms}

    headline, narrative, model, usage, dur = None, None, "template", {}, 0
    check = None
    if narrator.llm_available():
        draft = narrator.call_llm(bundle)
        if draft:
            model, usage, dur = draft["model"], draft["usage"], draft["duration_ms"]
            check = guardrail.verify(draft["text"], bundle)
            if not check["ok"]:
                retry = narrator.call_llm(bundle, prior_draft=draft["text"],
                                          misses=check["misses"])
                if retry:
                    check = guardrail.verify(retry["text"], bundle)
                    if check["ok"]:
                        draft = retry
                        usage = {k: usage.get(k, 0) + retry["usage"].get(k, 0)
                                 for k in ("input", "output")}
                        dur += retry["duration_ms"]
            if check["ok"]:
                headline, narrative = narrator.split_headline(draft["text"])

    if narrative is None:                       # no key, call failed, or guardrail blocked
        headline, narrative = narrator.template(bundle)
        model = "template" if model == "template" else f"{model}+template-fallback"
        check = guardrail.verify(headline + "\n" + narrative, bundle)

    inv.generation(model=model,
                   completion=f"{headline}\n\n{narrative}",
                   usage=usage, duration_ms=dur)
    inv.step("verify",
             hypothesis="Guardrail: every figure in the narrative must exist in the "
                        "evidence bundle (fabricated numbers block publication)",
             sql_text="-- detector/guardrail.verify(narrative, evidence)",
             result={"ok": check["ok"], "n_checked": check["n_checked"],
                     "misses": check["misses"]},
             decision=(f"{check['n_checked']} figure(s) checked, all present in "
                       f"evidence → publishable" if check["ok"] else
                       f"misses {[m['token'] for m in check['misses']]} → narrative "
                       f"blocked, template published instead"))

    version = int(chdb.scalar(
        "SELECT coalesce(max(toNullable(version)), 0) + 1 FROM rca.diagnoses "
        "WHERE incident_id = {inc:String}", {"inc": inv.incident_id}) or 1)
    chdb.insert_rows("rca.diagnoses", [{
        "incident_id": inv.incident_id, "version": version, "headline": headline,
        "narrative": narrative, "evidence": json.dumps(bundle, default=str),
        "ruled_out": bundle["verdict"].get("ruled_out", []),
        "verdict_code": bundle["verdict"].get("code", "UNKNOWN"), "llm_model": model,
        "numbers_verified": bool(check["ok"]), "trace_id": inv.trace_id,
    }])

    status = ("diagnosed" if code in DIAGNOSED
              else "dismissed" if code in DISMISSED
              else "ruled_out_seasonal" if code == "SEASONAL_CONFIRMED"
              else "investigating")
    if code in ("NO_PEER_OUTLIER", "SHORT_HISTORY_VOLUME") \
            and bundle["incident"].get("source") != "sweep":
        status = "dismissed"    # ad-hoc window on short history: nothing to hold open
    inv.close(status=status, headline=headline)

    return {"incident_id": inv.incident_id, "cached": False, "status": status,
            "verdict": code, "headline": headline, "narrative": narrative,
            "numbers_verified": bool(check["ok"]),
            "ruled_out": bundle["verdict"].get("ruled_out", []),
            "llm_model": model, "evidence": bundle, "trace": _trace(inv.incident_id),
            "duration_ms": int((time.monotonic() - t_start) * 1000)}
