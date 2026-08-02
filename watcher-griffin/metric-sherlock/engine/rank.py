"""Step 3: Rank dimensions by contribution. For the factor that decompose.py
identified as having moved (requests / fill_rate / ecpm), queries every
candidate dimension's hourly_by_* rollup CONCURRENTLY (never serially -- see
CLAUDE.md's "concurrency where independent" principle) and ranks each
dimension's segments by how much of the metric's numerator delta they
individually account for. A segment with an outsized share is the drill-down
candidate; a dimension where the delta is spread evenly across many segments
is *not* localized to it.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from engine.ch_client import Trace, borrowed_client
from engine.config import DIMENSION_REGISTRY, METRIC_DEFS, settings
from engine.tracing import in_parent_context


@dataclass
class SegmentContribution:
    dimension: str
    value: str
    numerator_now: float
    numerator_baseline: float
    denominator_now: float
    denominator_baseline: float
    metric_now: float
    metric_baseline: float
    numerator_delta: float
    share_of_total_delta: float


@dataclass
class DimensionRanking:
    dimension: str
    segments: list  # list[SegmentContribution], sorted by |share_of_total_delta| desc
    top_segment: Optional[SegmentContribution]


def _metric_value(numerator: float, denominator: Optional[float], multiplier: float) -> float:
    if denominator is None:
        return numerator
    return (numerator / denominator * multiplier) if denominator else 0.0


def compute_segment_contributions(dim_name: str, spec, current_by_value: dict, baseline_by_value: dict) -> DimensionRanking:
    """Pure math, no I/O: given {value: {"numerator":.., "denominator":..}}
    dicts for the current window and the (already-averaged) baseline, returns
    a DimensionRanking. Shared by rank.py (rollup-backed) and drilldown.py
    (raw-ad_events-backed) so the contribution formula is defined once."""
    all_values = set(current_by_value) | set(baseline_by_value)
    # '' means "no advertiser" (unfilled request, see CLAUDE.md) -- it's not a
    # real segment to attribute a deviation to, only a fill-rate artifact.
    all_values.discard("")

    total_numerator_delta = sum(
        float(current_by_value.get(v, {}).get("numerator") or 0) - float(baseline_by_value.get(v, {}).get("numerator") or 0)
        for v in all_values
    ) or 1.0

    segments = []
    for v in all_values:
        cur = current_by_value.get(v, {})
        base = baseline_by_value.get(v, {})
        num_now = float(cur.get("numerator") or 0)
        num_base = float(base.get("numerator") or 0)
        den_now = float(cur.get("denominator") or 0) if spec.denominator else None
        den_base = float(base.get("denominator") or 0) if spec.denominator else None
        delta = num_now - num_base
        segments.append(
            SegmentContribution(
                dimension=dim_name,
                value=str(v),
                numerator_now=num_now,
                numerator_baseline=num_base,
                denominator_now=den_now if den_now is not None else 0.0,
                denominator_baseline=den_base if den_base is not None else 0.0,
                metric_now=_metric_value(num_now, den_now, spec.multiplier),
                metric_baseline=_metric_value(num_base, den_base, spec.multiplier),
                numerator_delta=delta,
                share_of_total_delta=delta / total_numerator_delta,
            )
        )

    segments.sort(key=lambda s: abs(s.share_of_total_delta), reverse=True)
    return DimensionRanking(dimension=dim_name, segments=segments, top_segment=segments[0] if segments else None)


def _rank_one_dimension(dim_name: str, factor: str, window_start: datetime, window_end: datetime, trailing_weeks: int, trace: Trace) -> DimensionRanking:
    with borrowed_client() as client:
        return _rank_one_dimension_with(client, dim_name, factor, window_start, window_end, trailing_weeks, trace)


def _rank_one_dimension_with(client, dim_name: str, factor: str, window_start: datetime, window_end: datetime, trailing_weeks: int, trace: Trace) -> DimensionRanking:
    spec = METRIC_DEFS[factor]
    dim = DIMENSION_REGISTRY[dim_name]

    num_col = f"sum({spec.numerator})" if spec.numerator != "requests" else "sum(requests)"
    den_col = f"sum({spec.denominator})" if spec.denominator else "NULL"

    current_sql = (
        f"SELECT {dim.column} AS value, {num_col} AS numerator, {den_col} AS denominator "
        f"FROM {dim.rollup_table} WHERE hour >= '{window_start:%Y-%m-%d %H:%M:%S}' AND hour < '{window_end:%Y-%m-%d %H:%M:%S}' "
        f"GROUP BY {dim.column}"
    )
    current_rows = client.query(current_sql, step=f"rank:{dim.rollup_table}:current", trace=trace)

    baseline_ranges = []
    for k in range(1, trailing_weeks + 1):
        shift = timedelta(weeks=k)
        s, e = window_start - shift, window_end - shift
        baseline_ranges.append(f"(hour >= '{s:%Y-%m-%d %H:%M:%S}' AND hour < '{e:%Y-%m-%d %H:%M:%S}')")
    baseline_sql = (
        f"SELECT {dim.column} AS value, {num_col} / {trailing_weeks} AS numerator, "
        f"{den_col} / {trailing_weeks if spec.denominator else 1} AS denominator "
        f"FROM {dim.rollup_table} WHERE {' OR '.join(baseline_ranges)} GROUP BY {dim.column}"
    )
    baseline_rows = client.query(baseline_sql, step=f"rank:{dim.rollup_table}:baseline", trace=trace)

    current_by_value = {r["value"]: r for r in current_rows}
    baseline_by_value = {r["value"]: r for r in baseline_rows}
    return compute_segment_contributions(dim_name, spec, current_by_value, baseline_by_value)


def rank_dimensions(
    factor: str,
    window_start: datetime,
    window_end: datetime,
    trace: Trace,
    trailing_weeks: Optional[int] = None,
    dimensions: Optional[list] = None,
) -> list:
    """Returns one DimensionRanking per candidate dimension, sorted overall by
    the top segment's |share_of_total_delta| descending -- the first entry is
    the strongest localization candidate for drilldown.py to recurse into."""
    trailing_weeks = trailing_weeks or settings.baseline_trailing_weeks
    dim_names = dimensions or list(DIMENSION_REGISTRY.keys())

    # in_parent_context must be applied on THIS thread so the workers inherit
    # the investigation's OTel context -- otherwise each parallel query's span
    # orphans itself into its own root trace instead of nesting.
    worker = in_parent_context(
        lambda d: _rank_one_dimension(d, factor, window_start, window_end, trailing_weeks, trace)
    )
    # Sized from config so every dimension runs in ONE wave. At the previous
    # hardcoded 8 against 12 registered dimensions, the last 4 waited for the first 8,
    # doubling this stage's wall clock for no reason -- and the right number is
    # "however many dimensions this dataset has", which is not a literal.
    with ThreadPoolExecutor(max_workers=min(settings.fanout_max_workers, len(dim_names))) as pool:
        results = list(pool.map(worker, dim_names))

    results.sort(key=lambda r: abs(r.top_segment.share_of_total_delta) if r.top_segment else 0.0, reverse=True)
    return results
