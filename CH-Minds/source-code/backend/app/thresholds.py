"""Detection thresholds computed live from whatever data is currently
loaded - each metric's own empirical p95 deviation, not one flat percentage
shared across all of them (scripts/validate_thresholds.sql is the by-hand
version of this same measurement)."""
import threading
import time

from . import config, metrics

# 3 concurrent /api/metric-tree calls took ~143s each without caching -
# ClickHouse became the bottleneck. TTL is a small, explicit staleness
# tradeoff, not silently-stale-forever.
CACHE_TTL_SECONDS = 120
_cache_lock = threading.Lock()
_cache: dict = {}

_DIM_DEVIATION_SUBQUERY = """
    SELECT requests, (actual_value - baseline_avg) / baseline_avg AS pct_dev
    FROM (
        WITH daily AS (
            SELECT
                toDate(hour) AS day,
                {dim_col} AS segment_value,
                countMerge(requests) AS requests,
                sumMerge(fills) AS fills,
                sumMerge(impressions) AS impressions,
                sumMerge(clicks) AS clicks,
                sumMerge(revenue) AS revenue
            FROM inmobi_rca.hourly_segment_metrics
            GROUP BY day, segment_value
        )
        SELECT
            requests,
            {metric_expr} AS actual_value,
            quantileExact(0.5)({metric_expr}) OVER (
                PARTITION BY segment_value, toDayOfWeek(day)
                ORDER BY day
                ROWS BETWEEN {trailing} PRECEDING AND 1 PRECEDING
            ) AS baseline_avg,
            count({metric_expr}) OVER (
                PARTITION BY segment_value, toDayOfWeek(day)
                ORDER BY day
                ROWS BETWEEN {trailing} PRECEDING AND 1 PRECEDING
            ) AS baseline_n
        FROM daily
    )
    WHERE baseline_avg > 0 AND baseline_n >= {min_baseline_samples}
"""

_METRIC_THRESHOLD_QUERY = """
    SELECT
        count() AS n,
        quantile(0.95)(abs(pct_dev)) AS pct_p95,
        quantile(0.10)(requests) AS vol_p10
    FROM ( {unioned_subqueries} )
    WHERE isFinite(pct_dev) AND requests > 0
"""


def compute_metric_thresholds(client, metric_names) -> dict:
    """{metric_name: {pct_threshold, volume_floor, n_samples, dynamic}} -
    falls back to static config constants below MIN_THRESHOLD_SAMPLES."""
    cache_key = frozenset(metric_names)
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached is not None and (time.monotonic() - cached[0]) < CACHE_TTL_SECONDS:
            return cached[1]

    result = {}
    for metric_name in metric_names:
        metric_expr = metrics.METRIC_EXPRESSIONS[metric_name]
        subqueries = [
            _DIM_DEVIATION_SUBQUERY.format(
                dim_col=dim_col,
                metric_expr=metric_expr,
                trailing=config.TRAILING_WEEKS,
                min_baseline_samples=config.MIN_BASELINE_SAMPLES,
            )
            for dim_col in metrics.scannable_dimensions(metric_name)
        ]
        query = _METRIC_THRESHOLD_QUERY.format(unioned_subqueries=" UNION ALL ".join(subqueries))
        row = client.query(query).result_rows[0]
        n, pct_p95, vol_p10 = row

        if not n or n < config.MIN_THRESHOLD_SAMPLES:
            result[metric_name] = {
                "pct_threshold": config.PCT_DEVIATION_THRESHOLD,
                "volume_floor": config.MIN_VOLUME_FLOOR,
                "n_samples": int(n or 0),
                "dynamic": False,
            }
        else:
            result[metric_name] = {
                "pct_threshold": max(float(pct_p95), config.MIN_PCT_DEVIATION_THRESHOLD),
                "volume_floor": max(int(vol_p10), config.MIN_VOLUME_FLOOR_ABSOLUTE),
                "n_samples": int(n),
                "dynamic": True,
            }

    with _cache_lock:
        _cache[cache_key] = (time.monotonic(), result)
    return result
