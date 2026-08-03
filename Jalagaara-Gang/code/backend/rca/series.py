"""Hourly actual-vs-expected series for an anomaly's card chart.

The dashboard's "Anomaly detected" graph needs the real curve behind the headline: the
metric in 1-hour chunks over the 24 hours ending at the anomaly, plus the like-for-like
expected line so the drop/spike is legible. This is the ONE place that series is computed.

Two queries:
  * actual   — the metric per hour over the trailing 24h window (from the hourly rollup).
  * baseline — per-hour metric values over the trailing N weeks, medianed by
               (weekday, hour-of-day) in Python to get the expected value for each hour.

Scope is POPULATION-WIDE (global), to match the card's headline % and observed/expected — both
of which are global. Scoping the chart to the localized culprit segment instead makes a diluted
global move (e.g. fill_rate −1.1%) sit over a curve that fell by half in that segment, which
reads as a contradiction. The localized segment is surfaced elsewhere (drill-down, chips).
Every query is logged through run_query so it lands in the investigation's Langfuse trace.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from config import config
from data.client import run_query
from metrics import metric_sql
from models import EvidenceBundle
from rca.robust import med

_CFG = config()
_HOURLY = _CFG["clickhouse"]["hourly_table"]
_BASELINE_WEEKS = _CFG["detection"]["baseline_weeks"]

WINDOW_HOURS = 24


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def hourly_series(bundle: EvidenceBundle) -> dict:
    """24 points of {hour, actual, expected} ending at the anomaly's window, global scope.

    Returns {metric, points[]}; each point's `expected` is None when the baseline has no
    like-for-like history for that hour."""
    expr = metric_sql(bundle.metric, "rollup")

    anchor = bundle.target_window.end                       # exclusive end of the flagged window
    window_start = anchor - timedelta(hours=WINDOW_HOURS)
    baseline_start = window_start - timedelta(weeks=_BASELINE_WEEKS)

    # --- actual: the metric per hour over the trailing 24h ---
    actual_sql = (
        f"SELECT hour, {expr} AS value FROM {_HOURLY} "
        f"WHERE hour >= toDateTime({{start:String}}) AND hour < toDateTime({{end:String}}) "
        f"GROUP BY hour ORDER BY hour"
    )
    actual = run_query(
        actual_sql, {"start": _fmt(window_start), "end": _fmt(anchor)},
        name=f"sql:series-actual:{bundle.metric}",
    )
    actual_by_hour = {r[0]: (float(r[1]) if r[1] is not None else None) for r in actual["rows"]}

    # --- baseline: per-hour values over the trailing N weeks, medianed by (weekday, hour) ---
    base_sql = (
        f"SELECT hour, {expr} AS value FROM {_HOURLY} "
        f"WHERE hour >= toDateTime({{start:String}}) AND hour < toDateTime({{end:String}}) "
        f"GROUP BY hour"
    )
    base = run_query(
        base_sql, {"start": _fmt(baseline_start), "end": _fmt(window_start)},
        name=f"sql:series-baseline:{bundle.metric}",
    )
    by_shape: dict[tuple[int, int], list[float]] = {}
    for hour, value in ((r[0], r[1]) for r in base["rows"]):
        if value is not None:
            by_shape.setdefault((hour.weekday(), hour.hour), []).append(float(value))
    expected_for = {k: med(v) for k, v in by_shape.items() if v}

    # --- assemble a dense 24-point series (holes -> None, so the chart can gap them) ---
    points = []
    for i in range(WINDOW_HOURS):
        h = window_start + timedelta(hours=i)
        points.append({
            "hour": h.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "actual": actual_by_hour.get(h),
            "expected": expected_for.get((h.weekday(), h.hour)),
        })

    return {
        "metric": bundle.metric,
        "scope": "global",
        "points": points,
    }
