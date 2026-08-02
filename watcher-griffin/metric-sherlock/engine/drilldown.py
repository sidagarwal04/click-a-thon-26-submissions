"""Step 4: Recursive drill-down. Takes the top-ranked segment from rank.py
and re-ranks the *other* dimensions restricted to that slice. No single
hourly_by_* rollup covers a 2D slice (e.g. device x region), so this step is
the one documented, deliberate fallback to raw ad_events -- bounded by the
event_time range (the fact table's leading sort key) and the top segment's
own column (bloom-filter-indexed for the four event-level dimensions).
Every fallback query is logged verbatim into the trace, exactly as it runs.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional

from engine.ch_client import Trace, borrowed_client
from engine.config import DIMENSION_REGISTRY, METRIC_DEFS, settings
from engine.rank import DimensionRanking, compute_segment_contributions
from engine.tracing import in_parent_context

# Dimensions whose rollup column is a direct raw ad_events column (no dictGet
# needed) -- these can also be used as the WHERE filter without a dictionary
# lookup, and benefit from the bloom-filter skip indexes in schema.sql.
_RAW_EVENT_COLUMNS = {"app": "app_id", "advertiser": "advertiser_id", "ad_format": "ad_format"}


def _filter_expr(dimension: str, value: str) -> str:
    if dimension in _RAW_EVENT_COLUMNS:
        col = _RAW_EVENT_COLUMNS[dimension]
    else:
        col = DIMENSION_REGISTRY[dimension].raw_expr
    escaped = value.replace("'", "''")
    return f"({col} = '{escaped}')"


def _combined_filter_expr(filters: list) -> str:
    """ANDs every prior level's (dimension, value) pin together -- depth 3
    must stay within depth 1's segment AND depth 2's segment, not just the
    most recent one, or "recursive" drill-down would silently forget earlier
    constraints and drill into the wrong slice."""
    return " AND ".join(_filter_expr(dim, val) for dim, val in filters)


def _rank_one_raw(
    dim_name: str,
    factor: str,
    filters: list,
    window_start: datetime,
    window_end: datetime,
    trailing_weeks: int,
    trace: Trace,
) -> DimensionRanking:
    with borrowed_client() as client:
        return _rank_one_raw_with(client, dim_name, factor, filters, window_start, window_end, trailing_weeks, trace)


def _rank_one_raw_with(
    client,
    dim_name: str,
    factor: str,
    filters: list,
    window_start: datetime,
    window_end: datetime,
    trailing_weeks: int,
    trace: Trace,
) -> DimensionRanking:
    spec = METRIC_DEFS[factor]
    dim = DIMENSION_REGISTRY[dim_name]
    where_filter = _combined_filter_expr(filters)

    def agg(col_alias, expr):
        return f"sum({expr}) AS {col_alias}" if expr != "requests" else "count() AS requests"

    def metric_cols():
        num_expr = "1" if spec.numerator == "requests" else {
            "fills": "is_filled", "impressions": "is_impression", "clicks": "is_click", "revenue": "revenue",
        }[spec.numerator]
        num_agg = "count()" if spec.numerator == "requests" else f"sum({num_expr})"
        den_agg = "NULL"
        if spec.denominator:
            den_expr = {"requests": "1", "fills": "is_filled", "impressions": "is_impression"}[spec.denominator]
            den_agg = "count()" if spec.denominator == "requests" else f"sum({den_expr})"
        return num_agg, den_agg

    num_agg, den_agg = metric_cols()

    current_sql = (
        f"SELECT {dim.raw_expr} AS value, {num_agg} AS numerator, {den_agg} AS denominator "
        f"FROM ad_events WHERE event_time >= '{window_start:%Y-%m-%d %H:%M:%S}' AND event_time < '{window_end:%Y-%m-%d %H:%M:%S}' "
        f"AND {where_filter} GROUP BY value SETTINGS max_execution_time = {settings.clickhouse_query_timeout_s}"
    )
    current_rows = client.query(current_sql, step=f"drilldown_raw_fallback:{dim_name}:current", trace=trace)

    baseline_ranges = []
    for k in range(1, trailing_weeks + 1):
        shift = timedelta(weeks=k)
        s, e = window_start - shift, window_end - shift
        baseline_ranges.append(f"(event_time >= '{s:%Y-%m-%d %H:%M:%S}' AND event_time < '{e:%Y-%m-%d %H:%M:%S}')")
    baseline_sql = (
        f"SELECT {dim.raw_expr} AS value, {num_agg} / {trailing_weeks} AS numerator, "
        f"{den_agg} / {trailing_weeks if spec.denominator else 1} AS denominator "
        f"FROM ad_events WHERE ({' OR '.join(baseline_ranges)}) AND {where_filter} GROUP BY value "
        f"SETTINGS max_execution_time = {settings.clickhouse_query_timeout_s}"
    )
    baseline_rows = client.query(baseline_sql, step=f"drilldown_raw_fallback:{dim_name}:baseline", trace=trace)

    current_by_value = {r["value"]: r for r in current_rows}
    baseline_by_value = {r["value"]: r for r in baseline_rows}
    return compute_segment_contributions(dim_name, spec, current_by_value, baseline_by_value)


def drilldown(
    factor: str,
    filters: list,
    excluded_dimensions: set,
    window_start: datetime,
    window_end: datetime,
    trace: Trace,
    trailing_weeks: Optional[int] = None,
) -> list:
    """Re-ranks every dimension NOT already pinned by `filters`, restricted to
    the conjunction of all of them (raw-ad_events fallback -- no rollup
    covers an N-dimensional slice). `filters` is the accumulated
    (dimension, value) chain from every prior recursion level, so depth 3
    stays within depth 1 AND depth 2's segments, not just the latest one.
    Returns DimensionRankings sorted by concentration, same shape as
    rank.rank_dimensions -- this is what engine/graph.py calls in a loop to
    go one level deeper each time."""
    if not filters:
        return []
    trailing_weeks = trailing_weeks or settings.baseline_trailing_weeks
    other_dims = [d for d in DIMENSION_REGISTRY if d not in excluded_dimensions]
    if not other_dims:
        return []

    # Applied on THIS thread so the pool workers inherit the investigation's
    # OTel context -- see engine/tracing.py::in_parent_context.
    worker = in_parent_context(
        lambda d: _rank_one_raw(d, factor, filters, window_start, window_end, trailing_weeks, trace)
    )
    with ThreadPoolExecutor(max_workers=min(settings.fanout_max_workers, len(other_dims))) as pool:
        results = list(pool.map(worker, other_dims))
    results.sort(key=lambda r: abs(r.top_segment.share_of_total_delta) if r.top_segment else 0.0, reverse=True)
    return results
