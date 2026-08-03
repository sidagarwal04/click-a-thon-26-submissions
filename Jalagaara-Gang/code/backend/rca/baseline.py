"""JAL-26: like-for-like baseline stats engine.

Baseline for a metric at hourly grain = the SAME weekday + hour-of-day over the trailing N weeks
(config.detection). Robust center = median, spread = MAD -> a robust z-score per segment. This is
the feature layer the anomaly detector consumes.

Reads the hourly rollup (config.clickhouse.hourly_table); ratio metrics use the shared metrics
util so formulas match everywhere. Every query is returned for the Evidence Bundle's queries[].
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from config import config
from config import hourly_source as _hourly
from data.calibration import effect_threshold
from data.client import run_query
from metrics import metric_sql
from rca.robust import mad, med, pct_delta, robust_z

_CFG = config()
_DET = _CFG["detection"]
_ALLOWED = set(_CFG["rca"]["drilldown_dimensions"])


@dataclass
class Stat:
    segment: dict
    observed: float
    expected: float  # baseline median
    mad: float
    robust_z: float
    pct_delta: float
    direction: str  # drop | spike
    detected: bool
    n_baseline: int


@dataclass
class Result:
    metric: str
    target_hour: datetime
    stats: list[Stat]
    queries: list[dict] = field(default_factory=list)


def _baseline_start(target_hour: datetime) -> datetime: return target_hour - timedelta(weeks=_DET["baseline_weeks"])

def _fmt(dt: datetime) -> str: return dt.strftime("%Y-%m-%d %H:%M:%S")


def _detected(z: float, mad_value: float, pct: float, min_effect: float) -> bool:
    """Statistical surprise (z-score) AND a real effect size, always both — not just as a
    fallback when mad==0. Measured full-dataset sweep (docs/TEST_CASES.md, Clickathon2026
    session) found z-score alone false-fires on ~15-25% of ordinary hours per metric (e.g.
    130/840 for fill_rate) because a stable ratio's normal sampling wobble routinely trips
    a 3.5 z-score threshold.

    `min_effect` is a plain number, not looked up here — callers pass in a per-metric,
    auto-calibrated value from data.calibration.effect_threshold(). Keeping this function
    pure (no DB access, no config/metric lookups) is deliberate: it's covered by
    tests/test_baseline.py's "without a live DB" unit tests, and calibration itself queries
    ClickHouse (data.calibration.measure_natural_noise) — that lookup belongs at the engine
    layer (score()/scan()/incidents.score_buckets()), computed once per metric, not per stat."""
    if mad_value > 0:
        return abs(z) >= _DET["mad_z_threshold"] and abs(pct) >= min_effect
    return abs(pct) >= min_effect

def _where(segment: dict | None) -> tuple[str, dict]:
    if not segment:
        return "", {}
    clauses, params = [], {}
    for i, (col, val) in enumerate(segment.items()):
        if col not in _ALLOWED:
            raise ValueError(f"segment column not allowed: {col}")
        key = f"seg{i}"
        clauses.append(f"{col} = {{{key}:String}}")
        params[key] = val
    return " AND " + " AND ".join(clauses), params


def _observed_sql(expr: str, where_sql: str, dim: str | None = None) -> str:
    if dim:
        return f"SELECT {dim} AS seg, {expr} AS value FROM {_hourly()} WHERE hour = toDateTime({{target:String}}){where_sql} GROUP BY {dim}"
    return f"SELECT {expr} AS value FROM {_hourly()} WHERE hour = toDateTime({{target:String}}){where_sql}"


def _baseline_sql(expr: str, where_sql: str, dim: str | None = None) -> str:
    head = f"{dim} AS seg, " if dim else ""
    grp = f"{dim}, hour" if dim else "hour"
    return (
        f"SELECT {head}{expr} AS value FROM {_hourly()} "
        f"WHERE toDayOfWeek(hour) = toDayOfWeek(toDateTime({{target:String}})) "
        f"AND toHour(hour) = toHour(toDateTime({{target:String}})) "
        f"AND hour < toDateTime({{target:String}}) AND hour >= toDateTime({{start:String}}){where_sql} "
        f"GROUP BY {grp}"
    )


def _build_stat(segment: dict, observed: float, series: list[float], min_effect: float) -> Stat:
    center = med(series)
    spread = mad(series, center)
    z = robust_z(observed, center, spread, _DET["mad_scale"])
    pct = pct_delta(observed, center)
    return Stat(
        segment=segment, observed=observed, expected=center, mad=spread,
        robust_z=z, pct_delta=pct, direction="drop" if observed < center else "spike",
        detected=_detected(z, spread, pct, min_effect), n_baseline=len(series),
    )


# ---- engine (runs against ClickHouse) ----

def score(metric: str, target_hour: datetime, segment: dict | None = None) -> Result:
    """Robust baseline stats for one metric on one segment (segment=None -> global)."""
    expr = metric_sql(metric, "rollup")
    where_sql, params = _where(segment)
    queries: list[dict] = []
    min_effect = effect_threshold(metric)  # calibrated once, live from ClickHouse

    obs = run_query(_observed_sql(expr, where_sql), {"target": _fmt(target_hour), **params},
                    name=f"sql:observed:{metric}")
    observed = float(obs["rows"][0][0]) if obs["rows"] and obs["rows"][0][0] is not None else 0.0
    queries.append({"id": "q_observed", "sql": obs["resolved_sql"], "result_summary": {"observed": observed}})

    base = run_query(_baseline_sql(expr, where_sql), {"target": _fmt(target_hour), "start": _fmt(_baseline_start(target_hour)), **params},
                     name=f"sql:baseline:{metric}")
    series = [float(r[0]) for r in base["rows"] if r[0] is not None]
    queries.append({"id": "q_baseline", "sql": base["resolved_sql"], "result_summary": {"n": len(series), "values": series}})

    return Result(metric, target_hour, [_build_stat(segment or {}, observed, series, min_effect)], queries)


def scan(metric: str, target_hour: datetime, dimension: str, segment: dict | None = None) -> Result:
    """Baseline stats for EVERY value of `dimension` (the stats table), ranked by |robust_z|.

    Two queries total regardless of cardinality: observed-by-value + baseline-by-value-per-hour.
    """
    if dimension not in _ALLOWED:
        raise ValueError(f"dimension not allowed: {dimension}")
    expr = metric_sql(metric, "rollup")
    where_sql, params = _where(segment)
    queries: list[dict] = []
    min_effect = effect_threshold(metric)  # same metric for every segment -> calibrate once

    obs = run_query(_observed_sql(expr, where_sql, dimension), {"target": _fmt(target_hour), **params},
                    name=f"sql:observed-by:{dimension}")
    observed = {r[0]: float(r[1]) for r in obs["rows"] if r[1] is not None}
    queries.append({"id": "q_observed_by_dim", "sql": obs["resolved_sql"], "result_summary": {"n": len(observed)}})

    base = run_query(_baseline_sql(expr, where_sql, dimension), {"target": _fmt(target_hour), "start": _fmt(_baseline_start(target_hour)), **params},
                     name=f"sql:baseline-by:{dimension}")
    series_by: dict = {}
    for r in base["rows"]:
        if r[1] is not None:
            series_by.setdefault(r[0], []).append(float(r[1]))
    queries.append({"id": "q_baseline_by_dim", "sql": base["resolved_sql"], "result_summary": {"n": len(series_by)}})

    stats = [_build_stat({**(segment or {}), dimension: value}, obs_val, series_by.get(value, []), min_effect) for value, obs_val in observed.items()]
    stats.sort(key=lambda s: abs(s.robust_z), reverse=True)
    return Result(metric, target_hour, stats, queries)
