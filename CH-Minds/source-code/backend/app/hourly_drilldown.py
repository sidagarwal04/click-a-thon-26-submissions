"""Hour-grain segment ranking: which segment was responsible during one
specific hour, not diluted across the whole day. Same robust baseline
pattern as everywhere else, partitioned by hour-of-day + day-of-week
instead of just day-of-week. No independent hour-grain background scan -
see EDGE_CASES.md for why that adds no signal on the known data."""
from datetime import date, datetime
from typing import Optional

from . import baseline as baseline_module
from . import config, metrics

_HOUR_SEGMENT_QUERY = """
    WITH hourly AS (
        SELECT
            hour,
            toDate(hour) AS day,
            toHour(hour) AS hod,
            toDayOfWeek(toDate(hour)) AS dow,
            {dim_col} AS segment_value,
            countMerge(requests) AS requests,
            sumMerge(fills) AS fills,
            sumMerge(impressions) AS impressions,
            sumMerge(clicks) AS clicks,
            sumMerge(revenue) AS revenue
        FROM inmobi_rca.hourly_segment_metrics
        GROUP BY hour, segment_value
    )
    SELECT
        hour,
        segment_value,
        requests,
        {metric_expr} AS actual_value,
        {baseline_cols}
    FROM hourly
    ORDER BY segment_value, hour
"""


def hour_segment_ranking(
    client, target_hour: datetime, metric_name: str, dim_col: str, volume_floor: Optional[int] = None
) -> list:
    if volume_floor is None:
        volume_floor = config.MIN_VOLUME_FLOOR
    query = _HOUR_SEGMENT_QUERY.format(
        dim_col=dim_col,
        metric_expr=metrics.METRIC_EXPRESSIONS[metric_name],
        baseline_cols=baseline_module.baseline_select(
            metrics.METRIC_EXPRESSIONS[metric_name], "segment_value, hod, dow", config.TRAILING_WEEKS
        ),
    )
    rows = client.query(query).result_rows

    ranked = []
    for row_hour, segment_value, requests, actual, baseline, _mean, _stddev, baseline_n in rows:
        if row_hour != target_hour or requests < volume_floor:
            continue
        if str(segment_value) == metrics.BLANK_SEGMENT_VALUE:
            continue
        if metrics.is_invalid_number(actual) or metrics.is_invalid_number(baseline) or baseline == 0:
            continue
        if (baseline_n or 0) < config.MIN_BASELINE_SAMPLES:
            continue
        pct_dev = (actual - baseline) / baseline
        ranked.append(
            {
                "dimension": dim_col,
                "value": segment_value,
                "requests": requests,
                "actual": float(actual),
                "baseline": float(baseline),
                "pct_deviation": float(pct_dev),
                "baseline_n": int(baseline_n or 0),
            }
        )
    ranked.sort(key=lambda r: abs(r["pct_deviation"]), reverse=True)
    return ranked


def investigate_hour(client, target_hour: datetime, metric_name: str, computed_thresholds: dict) -> dict:
    metric_thresholds = computed_thresholds.get(metric_name, {"pct_threshold": config.PCT_DEVIATION_THRESHOLD})
    pct_threshold = metric_thresholds["pct_threshold"]
    # Not the day-grain volume_floor (thousands) - one hour carries ~1/24th a
    # day's volume. Measured p10 hourly per-segment volume is ~726 requests.
    volume_floor = config.MIN_VOLUME_FLOOR_ABSOLUTE

    ruled_out = list(metrics.degenerate_notes(metric_name))
    best = None
    per_dim = {}
    for dim_col in metrics.scannable_dimensions(metric_name):
        ranked = hour_segment_ranking(client, target_hour, metric_name, dim_col, volume_floor=volume_floor)
        per_dim[dim_col] = ranked
        if not ranked:
            ruled_out.append(f"{dim_col}: no segment met the minimum volume floor at this hour")
            continue
        top = ranked[0]
        if best is None or abs(top["pct_deviation"]) > abs(best["pct_deviation"]):
            best = top

    for dim_col, ranked in per_dim.items():
        if not ranked:
            continue
        top = ranked[0]
        if best is not None and top is best:
            continue
        if abs(top["pct_deviation"]) < pct_threshold:
            ruled_out.append(f"{dim_col}: no segment stands out (closest: {top['value']} at {top['pct_deviation']:+.1%})")

    responsible = None
    if best is not None and abs(best["pct_deviation"]) >= pct_threshold:
        responsible = best

    return {
        "hour": target_hour.isoformat(),
        "metric": metric_name,
        "pct_threshold": pct_threshold,
        "responsible_segment": responsible,
        "checked_and_ruled_out": ruled_out,
    }


_DAY_HOURS_QUERY = "SELECT DISTINCT hour FROM inmobi_rca.hourly_segment_metrics WHERE toDate(hour) = {day:Date} ORDER BY hour"


def day_hour_scan(client, day: date, metric_name: str, computed_thresholds: dict) -> list:
    """Every hour of `day` with its responsible segment, if any. One query
    per dimension for the whole day (not per hour x dimension)."""
    metric_thresholds = computed_thresholds.get(metric_name, {"pct_threshold": config.PCT_DEVIATION_THRESHOLD})
    pct_threshold = metric_thresholds["pct_threshold"]
    volume_floor = config.MIN_VOLUME_FLOOR_ABSOLUTE

    best_by_hour = {}
    for dim_col in metrics.scannable_dimensions(metric_name):
        query = _HOUR_SEGMENT_QUERY.format(
            dim_col=dim_col,
            metric_expr=metrics.METRIC_EXPRESSIONS[metric_name],
            baseline_cols=baseline_module.baseline_select(
                metrics.METRIC_EXPRESSIONS[metric_name], "segment_value, hod, dow", config.TRAILING_WEEKS
            ),
        )
        for row_hour, segment_value, requests, actual, baseline, _mean, _stddev, baseline_n in client.query(query).result_rows:
            if row_hour.date() != day or requests < volume_floor:
                continue
            if str(segment_value) == metrics.BLANK_SEGMENT_VALUE:
                continue
            if metrics.is_invalid_number(actual) or metrics.is_invalid_number(baseline) or baseline == 0:
                continue
            if (baseline_n or 0) < config.MIN_BASELINE_SAMPLES:
                continue
            pct_dev = (actual - baseline) / baseline
            current_best = best_by_hour.get(row_hour)
            if current_best is None or abs(pct_dev) > abs(current_best["pct_deviation"]):
                best_by_hour[row_hour] = {
                    "dimension": dim_col,
                    "value": segment_value,
                    "requests": requests,
                    "actual": float(actual),
                    "baseline": float(baseline),
                    "pct_deviation": float(pct_dev),
                    "baseline_n": int(baseline_n or 0),
                }

    hour_rows = client.query(_DAY_HOURS_QUERY, parameters={"day": day}).result_rows
    result = []
    for (hour,) in hour_rows:
        best = best_by_hour.get(hour)
        responsible = best if (best and abs(best["pct_deviation"]) >= pct_threshold) else None
        result.append({"hour": hour.isoformat(), "hod": hour.hour, "responsible_segment": responsible})
    return result
