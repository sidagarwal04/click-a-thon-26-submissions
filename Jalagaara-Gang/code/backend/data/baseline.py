"""Lane A: like-for-like baseline template (same weekday + hour-of-day, trailing N weeks).

Design: aggregate raw sums per historical hour in ClickHouse (one row per matching hour,
sum/sum'd correctly per metrics_glossary.md), then compute median/MAD across that small
per-hour series in Python — this IS the "pandas only on already-aggregated series" case
the coding standards allow, since it's ~15-25 rows, not raw events.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from data.client import run_query

# metric -> (numerator column, denominator column) on hourly_summary. denominator=None
# means the metric IS the sum (no ratio). Matches EvidenceBundle.metric enum.
METRIC_COLUMNS: dict[str, tuple[str, str | None]] = {
    "requests": ("requests", None),
    "fills": ("fills", None),
    "impressions": ("impressions", None),
    "revenue": ("revenue", None),
    "fill_rate": ("fills", "requests"),
    "render_rate": ("impressions", "fills"),
    "ctr": ("clicks", "impressions"),
    "ecpm": ("revenue", "impressions"),  # x1000 applied after the divide
    "rpr": ("revenue", "requests"),
}


@dataclass
class Baseline:
    median: float
    mad: float
    sample_size: int
    values: list[float]
    sql: str
    resolved_sql: str


def _metric_value(numerator: float, denominator: float | None, metric: str) -> float:
    if denominator is None:
        return numerator
    if denominator == 0:
        return 0.0
    value = numerator / denominator
    return value * 1000 if metric == "ecpm" else value


def historical_hours_sql(segment_where: str = "") -> str:
    """Sums per matching historical hour. segment_where is a raw SQL fragment, e.g.
    "AND country = {country:String}" — caller supplies its own params for it."""
    where_extra = f"{segment_where}\n      " if segment_where else ""
    return f"""
        SELECT
            hour,
            sum(requests)    AS requests,
            sum(fills)       AS fills,
            sum(impressions) AS impressions,
            sum(clicks)      AS clicks,
            sum(revenue)     AS revenue
        FROM hourly_summary
        WHERE toDayOfWeek(hour) = {{weekday:UInt8}}
          AND toHour(hour) = {{hour_of_day:UInt8}}
          AND hour >= {{trailing_start:DateTime}}
          AND hour < {{target_start:DateTime}}
          {where_extra}
        GROUP BY hour
        ORDER BY hour
    """.strip()


def get_baseline(
    metric: str,
    target_start: datetime,
    weeks: int = 3,
    segment_where: str = "",
    segment_params: dict | None = None,
) -> Baseline:
    """Robust like-for-like baseline for `metric` at `target_start`'s weekday+hour,
    over the trailing `weeks` weeks. Never a flat average — same weekday/hour only.

    segment_where / segment_params let a drill-down step scope this to a specific
    segment, e.g. segment_where="AND country = {country:String}",
    segment_params={"country": "IN"}.
    """
    if metric not in METRIC_COLUMNS:
        raise ValueError(f"unknown metric: {metric!r}")
    numerator_col, denominator_col = METRIC_COLUMNS[metric]

    weekday = target_start.isoweekday()  # ClickHouse toDayOfWeek: 1=Monday..7=Sunday
    hour_of_day = target_start.hour
    trailing_start = target_start - timedelta(weeks=weeks)

    sql = historical_hours_sql(segment_where)
    params = {
        "weekday": weekday,
        "hour_of_day": hour_of_day,
        # clickhouse-connect's {x:DateTime} binding does not correctly serialize raw
        # Python datetime objects (silently matches zero rows) — pass ISO strings instead.
        "trailing_start": trailing_start.strftime("%Y-%m-%d %H:%M:%S"),
        "target_start": target_start.strftime("%Y-%m-%d %H:%M:%S"),
        **(segment_params or {}),
    }
    result = run_query(sql, params)

    values = []
    for row in result["rows"]:
        row_dict = dict(zip(result["columns"], row))
        num = row_dict[numerator_col]
        den = row_dict[denominator_col] if denominator_col else None
        values.append(_metric_value(num, den, metric))

    if not values:
        return Baseline(median=0.0, mad=0.0, sample_size=0, values=[], sql=sql, resolved_sql=result["resolved_sql"])

    median = statistics.median(values)
    mad = statistics.median([abs(v - median) for v in values])
    return Baseline(
        median=median,
        mad=mad,
        sample_size=len(values),
        values=values,
        sql=sql,
        resolved_sql=result["resolved_sql"],
    )


def robust_z_score(observed: float, baseline: Baseline) -> float:
    """Modified z-score (Iglewicz & Hoaglin). 0.6745 makes MAD comparable to std-dev
    under normality. mad=0 (flat historical series) -> return 0, not inf/NaN."""
    if baseline.mad == 0:
        return 0.0
    return 0.6745 * (observed - baseline.median) / baseline.mad
