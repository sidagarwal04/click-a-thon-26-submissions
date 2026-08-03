"""Step 6: Generate evidence. Assembles everything steps 1-5 computed into one
pydantic EvidenceBundle -- the single artifact that reaches the LLM narrator
(engine/narrator.py) and that every number in the final narration must trace
back to. `queries` is the full, verbatim query log (what ran, in what order,
row counts, latency) -- this is what a judge opens to verify traceability.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from engine.baseline import BaselineResult
from engine.ch_client import Trace
from engine.config import DIMENSION_REGISTRY
from engine.decompose import DecomposeResult
from engine.rank import DimensionRanking
from engine.rule_out import RuledOutCheck


class QueryRecord(BaseModel):
    step: str
    sql: str
    row_count: int          # rows returned
    latency_ms: float
    error: Optional[str] = None
    read_rows: int = 0      # rows ClickHouse actually scanned, per its own summary
    read_bytes: int = 0


class SegmentEvidence(BaseModel):
    dimension: str
    value: str
    metric_now: float
    metric_baseline: float
    share_of_deviation: float
    source_step: str  # the exact Trace step name this segment's numbers came from -- narrator.py cites this


class RuledOutEvidence(BaseModel):
    check: str
    reason: str
    numbers: dict


class EvidenceBundle(BaseModel):
    metric: str
    window_start: datetime
    window_end: datetime
    baseline_trailing_weeks: int

    current_value: float
    baseline_mean: float
    baseline_sample_count: int
    zscore: float
    pct_change: Optional[float] = None
    is_anomalous: bool
    insufficient_baseline: bool = False

    primary_factor: Optional[str] = None
    factor_breakdown: list = []  # list[dict]: factor, now, baseline, share

    drilldown_levels: list = []  # list[list[SegmentEvidence]] -- level 0 = initial ranking, level 1+ = each recursive drill

    ruled_out: list = []  # list[RuledOutEvidence]
    queries: list = []  # list[QueryRecord] -- the full verbatim trace

    def to_llm_json(self) -> dict:
        """What the narrator LLM actually sees -- every computed number, no
        raw SQL text (keeps the prompt small; the SQL trace is still
        returned to the caller/Langfuse for traceability, just not narrated)."""
        return self.model_dump(mode="json", exclude={"queries"})


def _source_step(dimension: str, is_level_0: bool) -> str:
    """Reconstructs the exact Trace step name this segment's numbers came
    from (see rank.py/drilldown.py's own step-naming) so the narrator can
    cite the real query, not a vague reference."""
    if is_level_0:
        return f"rank:{DIMENSION_REGISTRY[dimension].rollup_table}:current"
    return f"drilldown_raw_fallback:{dimension}:current"


def _top_n_segments(rankings: list, is_level_0: bool, n: int = 3) -> list:
    out = []
    for ranking in rankings[:n]:
        seg = ranking.top_segment
        if seg is None:
            continue
        out.append(
            SegmentEvidence(
                dimension=seg.dimension, value=seg.value,
                metric_now=seg.metric_now, metric_baseline=seg.metric_baseline,
                share_of_deviation=seg.share_of_total_delta,
                source_step=_source_step(seg.dimension, is_level_0),
            )
        )
    return out


def build_evidence(
    metric: str,
    window_start: datetime,
    window_end: datetime,
    baseline_trailing_weeks: int,
    metric_baseline_result: BaselineResult,
    decompose_result: Optional[DecomposeResult],
    levels: list,
    ruled_out_checks: list,
    trace: Trace,
) -> EvidenceBundle:
    """`levels` is list[list[DimensionRanking]] -- levels[0] is the initial
    rank across all dimensions, levels[1:] are each recursive drill-down
    (engine/graph.py's should_keep_drilling loop)."""
    factor_breakdown = []
    primary_factor = None
    if decompose_result is not None:
        primary_factor = decompose_result.primary_factor
        factor_breakdown = [
            {"factor": f.factor, "now": f.now, "baseline": f.baseline, "share": f.share} for f in decompose_result.factors
        ]

    drilldown_levels = [_top_n_segments(level_rankings, is_level_0=(i == 0)) for i, level_rankings in enumerate(levels)]

    return EvidenceBundle(
        metric=metric,
        window_start=window_start,
        window_end=window_end,
        baseline_trailing_weeks=baseline_trailing_weeks,
        current_value=metric_baseline_result.current_value,
        baseline_mean=metric_baseline_result.baseline_mean,
        baseline_sample_count=metric_baseline_result.baseline_sample_count,
        zscore=metric_baseline_result.zscore,
        pct_change=metric_baseline_result.pct_change,
        is_anomalous=metric_baseline_result.is_anomalous,
        insufficient_baseline=metric_baseline_result.insufficient_baseline,
        primary_factor=primary_factor,
        factor_breakdown=factor_breakdown,
        drilldown_levels=drilldown_levels,
        ruled_out=[RuledOutEvidence(check=c.check, reason=c.reason, numbers=c.numbers) for c in ruled_out_checks],
        queries=[
            QueryRecord(step=e.step, sql=e.sql, row_count=e.row_count, latency_ms=e.latency_ms,
                        error=e.error, read_rows=e.read_rows, read_bytes=e.read_bytes)
            for e in trace.entries
        ],
    )
