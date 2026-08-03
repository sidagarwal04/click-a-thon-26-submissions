"""Revenue detectors for incident shapes detect.py's day-grain threshold
scan structurally can't see: sustained multi-day drift, a segment
collapsing to zero, and a mix-shift in revenue composition. All ClickHouse,
same robust baseline as everywhere else - see EDGE_CASES.md for the full
reasoning and the measured findings each detector surfaced."""
from typing import Optional

from . import baseline as baseline_module
from . import config, coverage as coverage_module, metrics

METRIC = "revenue"

DRIFT_MIN_DAYS = int(getattr(config, "DRIFT_MIN_DAYS", 3))
DRIFT_MIN_AVG_DEVIATION = float(getattr(config, "DRIFT_MIN_AVG_DEVIATION", 0.05))
SHARE_SHIFT_MIN_POINTS = float(getattr(config, "SHARE_SHIFT_MIN_POINTS", 0.02))
COLLAPSE_MIN_BASELINE_SHARE = float(getattr(config, "COLLAPSE_MIN_BASELINE_SHARE", 0.005))


def _dim_union(select_template: str, dimensions) -> str:
    return " UNION ALL ".join(
        select_template.format(dim_col=d, dim_name=f"'{d}'") for d in dimensions
    )


# EXCESS drift, not raw drift: scoring each segment against its OWN baseline
# alone returned 336 hits (a global -44.8% day drags every segment together).
# Scoring the gap between a segment's drift and the business-overall drift on
# the same day cuts that to 24 real findings.
_DRIFT_QUERY = """
    SELECT
        seg.dim, seg.segment_value, seg.day,
        seg.avg_deviation - overall.avg_deviation AS excess_deviation,
        seg.avg_deviation, overall.avg_deviation AS overall_deviation,
        seg.days_in_run, seg.requests
    FROM (
        SELECT
            dim, segment_value, day, requests,
            avg(pct_dev) OVER run AS avg_deviation,
            sum(sign(pct_dev)) OVER run AS direction_sum,
            count() OVER run AS days_in_run
        FROM (
            SELECT dim, segment_value, day, requests,
                   (actual_value - baseline_avg) / baseline_avg AS pct_dev
            FROM (
                SELECT dim, segment_value, day, requests, actual_value, baseline_avg, baseline_n
                FROM ( {unioned} )
            )
            WHERE isFinite(baseline_avg) AND baseline_avg > 0 AND baseline_n >= {min_baseline_samples}
        )
        WINDOW run AS (
            PARTITION BY dim, segment_value ORDER BY day
            ROWS BETWEEN {drift_days_minus_1} PRECEDING AND CURRENT ROW
        )
    ) AS seg
    INNER JOIN (
        SELECT day, avg(pct_dev) OVER run AS avg_deviation
        FROM (
            SELECT day, (revenue - baseline_avg) / baseline_avg AS pct_dev
            FROM (
                SELECT day, revenue, {overall_baseline_cols}
                FROM (
                    SELECT toDate(hour) AS day, sumMerge(revenue) AS revenue
                    FROM inmobi_rca.hourly_segment_metrics {where_clause}
                    GROUP BY day
                )
            )
            WHERE isFinite(baseline_avg) AND baseline_avg > 0 AND baseline_n >= {min_baseline_samples}
        )
        WINDOW run AS (ORDER BY day ROWS BETWEEN {drift_days_minus_1} PRECEDING AND CURRENT ROW)
    ) AS overall ON seg.day = overall.day
    WHERE seg.days_in_run = {drift_days}
      AND abs(seg.direction_sum) = {drift_days}
      AND abs(seg.avg_deviation - overall.avg_deviation) >= {min_avg_deviation}
      AND seg.requests >= {volume_floor}
    ORDER BY abs(seg.avg_deviation - overall.avg_deviation) DESC
"""

_DRIFT_DIM_SELECT = """
    SELECT {dim_name} AS dim, segment_value, day, requests, actual_value, baseline_avg, baseline_n
    FROM (
        WITH daily AS (
            SELECT toDate(hour) AS day, {dim_col} AS segment_value,
                   countMerge(requests) AS requests, sumMerge(revenue) AS revenue
            FROM inmobi_rca.hourly_segment_metrics
            {where_clause}
            GROUP BY day, segment_value
        )
        SELECT day, segment_value, requests, revenue AS actual_value, {baseline_cols}
        FROM daily
    )
    WHERE segment_value != ''
"""


_COLLAPSE_QUERY = """
    SELECT scored.dim, scored.segment_value, scored.day, scored.revenue, scored.baseline_revenue
    FROM (
        SELECT
            dim, segment_value, day, revenue,
            quantileExact(0.5)(revenue) OVER w AS baseline_revenue,
            count() OVER w AS baseline_n
        FROM ( {unioned} )
        WINDOW w AS (
            PARTITION BY dim, segment_value, toDayOfWeek(day) ORDER BY day
            ROWS BETWEEN {trailing} PRECEDING AND 1 PRECEDING
        )
    ) AS scored
    INNER JOIN (
        SELECT toDate(hour) AS day, sumMerge(revenue) AS total_revenue
        FROM inmobi_rca.hourly_segment_metrics {where_clause} GROUP BY day
    ) AS totals ON scored.day = totals.day
    WHERE scored.baseline_n >= {min_baseline_samples}
      AND scored.baseline_revenue > 0
      AND scored.revenue <= scored.baseline_revenue * {collapse_ratio}
      AND scored.baseline_revenue / totals.total_revenue >= {min_baseline_share}
    ORDER BY scored.baseline_revenue - scored.revenue DESC
"""

# Day x segment grid via CROSS JOIN + LEFT JOIN so a segment that stops
# producing rows entirely still appears, with revenue 0.
_COLLAPSE_DIM_SELECT = """
    SELECT {dim_name} AS dim, grid.segment_value AS segment_value, grid.day AS day,
           coalesce(actuals.revenue, 0) AS revenue
    FROM (
        SELECT days.day AS day, vals.segment_value AS segment_value
        FROM (SELECT DISTINCT toDate(hour) AS day FROM inmobi_rca.hourly_segment_metrics {where_clause}) AS days
        CROSS JOIN (
            SELECT DISTINCT {dim_col} AS segment_value
            FROM inmobi_rca.hourly_segment_metrics WHERE {dim_col} != ''
        ) AS vals
    ) AS grid
    LEFT JOIN (
        SELECT toDate(hour) AS day, {dim_col} AS segment_value, sumMerge(revenue) AS revenue
        FROM inmobi_rca.hourly_segment_metrics {where_clause}
        GROUP BY day, segment_value
    ) AS actuals ON grid.day = actuals.day AND grid.segment_value = actuals.segment_value
"""


_SHARE_QUERY = """
    SELECT dim, segment_value, day, share, baseline_share, share - baseline_share AS share_delta
    FROM (
        SELECT dim, segment_value, day, share,
               quantileExact(0.5)(share) OVER w AS baseline_share,
               count() OVER w AS baseline_n
        FROM (
            SELECT dim, segment_value, day,
                   revenue / nullIf(sum(revenue) OVER (PARTITION BY dim, day), 0) AS share
            FROM ( {unioned} )
        )
        WINDOW w AS (
            PARTITION BY dim, segment_value, toDayOfWeek(day) ORDER BY day
            ROWS BETWEEN {trailing} PRECEDING AND 1 PRECEDING
        )
    )
    WHERE baseline_n >= {min_baseline_samples}
      AND isFinite(share) AND isFinite(baseline_share)
      AND abs(share - baseline_share) >= {min_points}
    ORDER BY abs(share - baseline_share) DESC
"""

_SHARE_DIM_SELECT = """
    SELECT {dim_name} AS dim, {dim_col} AS segment_value, toDate(hour) AS day,
           sumMerge(revenue) AS revenue
    FROM inmobi_rca.hourly_segment_metrics
    {where_clause}
    GROUP BY day, segment_value
    HAVING segment_value != ''
"""


def _where(hour_cutoff: Optional[int]) -> str:
    f = coverage_module.hour_filter_sql(hour_cutoff)
    return f"WHERE {f}" if f else ""


def detect_sustained_drift(client, hour_cutoff=None, volume_floor=None) -> list:
    where_clause = _where(hour_cutoff)
    baseline_cols = baseline_module.baseline_select(
        "revenue", "segment_value, toDayOfWeek(day)", config.TRAILING_WEEKS
    )
    unioned = " UNION ALL ".join(
        _DRIFT_DIM_SELECT.format(
            dim_col=d, dim_name=f"'{d}'", where_clause=where_clause, baseline_cols=baseline_cols
        )
        for d in metrics.scannable_dimensions(METRIC)
    )
    query = _DRIFT_QUERY.format(
        unioned=unioned,
        where_clause=where_clause,
        overall_baseline_cols=baseline_module.baseline_select(
            "revenue", "toDayOfWeek(day)", config.TRAILING_WEEKS
        ),
        min_baseline_samples=config.MIN_BASELINE_SAMPLES,
        drift_days=DRIFT_MIN_DAYS,
        drift_days_minus_1=DRIFT_MIN_DAYS - 1,
        min_avg_deviation=DRIFT_MIN_AVG_DEVIATION,
        volume_floor=int(volume_floor or config.MIN_VOLUME_FLOOR_ABSOLUTE),
    )
    out = []
    for row in client.query(query).result_rows:
        dim, value, day, excess_dev, avg_dev, overall_dev, days_in_run, requests = row
        out.append(
            {
                "detector": "sustained_drift",
                "metric": METRIC,
                "dimension": dim,
                "value": value,
                "day": day,
                "excess_deviation": float(excess_dev),
                "avg_deviation": float(avg_dev),
                "overall_deviation": float(overall_dev),
                "days_in_run": int(days_in_run),
                "requests": int(requests),
                "description": (
                    f"revenue for {dim}={value} moved {avg_dev:+.1%} on average for "
                    f"{int(days_in_run)} consecutive days, every day in the same direction, "
                    f"against {overall_dev:+.1%} for the business overall - {excess_dev:+.1%} of "
                    "segment-specific drift that no single day's deviation would have flagged"
                ),
            }
        )
    return out


def detect_collapsed_segments(client, hour_cutoff=None, collapse_ratio: float = 0.1) -> list:
    where_clause = _where(hour_cutoff)
    unioned = " UNION ALL ".join(
        _COLLAPSE_DIM_SELECT.format(dim_col=d, dim_name=f"'{d}'", where_clause=where_clause)
        for d in metrics.scannable_dimensions(METRIC)
    )
    query = _COLLAPSE_QUERY.format(
        unioned=unioned,
        where_clause=where_clause,
        trailing=config.TRAILING_WEEKS,
        min_baseline_samples=config.MIN_BASELINE_SAMPLES,
        collapse_ratio=collapse_ratio,
        min_baseline_share=COLLAPSE_MIN_BASELINE_SHARE,
    )
    out = []
    for dim, value, day, revenue, baseline_revenue in client.query(query).result_rows:
        lost = float(baseline_revenue) - float(revenue)
        out.append(
            {
                "detector": "collapsed_segment",
                "metric": METRIC,
                "dimension": dim,
                "value": value,
                "day": day,
                "actual": float(revenue),
                "baseline": float(baseline_revenue),
                "revenue_lost": lost,
                "description": (
                    f"revenue for {dim}={value} fell to {revenue:.2f} against a typical "
                    f"{baseline_revenue:.2f} ({lost:.2f} lost) - a near-total stop, which a "
                    "percentage-deviation test cannot report once the baseline itself reaches zero"
                ),
            }
        )
    return out


def detect_share_shifts(client, hour_cutoff=None) -> list:
    where_clause = _where(hour_cutoff)
    unioned = " UNION ALL ".join(
        _SHARE_DIM_SELECT.format(dim_col=d, dim_name=f"'{d}'", where_clause=where_clause)
        for d in metrics.scannable_dimensions(METRIC)
    )
    query = _SHARE_QUERY.format(
        unioned=unioned,
        trailing=config.TRAILING_WEEKS,
        min_baseline_samples=config.MIN_BASELINE_SAMPLES,
        min_points=SHARE_SHIFT_MIN_POINTS,
    )
    out = []
    for dim, value, day, share, baseline_share, delta in client.query(query).result_rows:
        out.append(
            {
                "detector": "share_shift",
                "metric": METRIC,
                "dimension": dim,
                "value": value,
                "day": day,
                "share": float(share),
                "baseline_share": float(baseline_share),
                "share_delta_points": float(delta) * 100,
                "description": (
                    f"{dim}={value} moved from {baseline_share:.1%} to {share:.1%} of total revenue "
                    f"({delta * 100:+.1f} percentage points) - a change in revenue composition that "
                    "an absolute per-segment deviation test can miss entirely"
                ),
            }
        )
    return out


def all_signals(client, hour_cutoff=None, volume_floor=None) -> dict:
    drift = detect_sustained_drift(client, hour_cutoff, volume_floor)
    collapsed = detect_collapsed_segments(client, hour_cutoff)
    shifts = detect_share_shifts(client, hour_cutoff)
    return {
        "sustained_drift": drift,
        "collapsed_segment": collapsed,
        "share_shift": shifts,
        "total": len(drift) + len(collapsed) + len(shifts),
    }
