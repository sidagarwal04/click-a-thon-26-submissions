"""Pure-logic tests for engine/graph.py's conditional edges -- no ClickHouse
needed. These are what decide whether the graph decomposes at all, and
whether it keeps recursing into deeper drill-down levels or stops -- exactly
the behavior the LangGraph reapproach was meant to get right.
"""

from engine.config import settings
from engine.graph import should_decompose, should_keep_drilling
from engine.rank import DimensionRanking, SegmentContribution


def _ranking(dimension: str, value: str, share: float) -> DimensionRanking:
    seg = SegmentContribution(
        dimension=dimension, value=value,
        numerator_now=100.0, numerator_baseline=90.0,
        denominator_now=0.0, denominator_baseline=0.0,
        metric_now=100.0, metric_baseline=90.0,
        numerator_delta=10.0, share_of_total_delta=share,
    )
    return DimensionRanking(dimension=dimension, segments=[seg], top_segment=seg)


def test_should_decompose_only_for_revenue():
    assert should_decompose({"metric": "revenue"}) == "decompose"
    assert should_decompose({"metric": "fill_rate"}) == "set_primary_factor"
    assert should_decompose({"metric": "requests"}) == "set_primary_factor"


def test_keep_drilling_when_concentrated_and_under_depth_cap():
    concentrated = settings.drilldown_concentration_threshold + 0.1
    state = {"levels": [[_ranking("region", "NAM", concentrated)]], "depth": 0}
    assert should_keep_drilling(state) == "drilldown"


def test_stop_drilling_when_deviation_not_concentrated():
    spread_thin = settings.drilldown_concentration_threshold - 0.05
    state = {"levels": [[_ranking("app", "app_1", spread_thin)]], "depth": 0}
    assert should_keep_drilling(state) == "rule_out"


def test_stop_drilling_at_max_depth_even_if_still_concentrated():
    concentrated = settings.drilldown_concentration_threshold + 0.3
    state = {"levels": [[_ranking("region", "NAM", concentrated)]], "depth": settings.max_drilldown_depth - 1}
    assert should_keep_drilling(state) == "rule_out"


def test_stop_drilling_when_no_segments_found():
    empty_ranking = DimensionRanking(dimension="region", segments=[], top_segment=None)
    state = {"levels": [[empty_ranking]], "depth": 0}
    assert should_keep_drilling(state) == "rule_out"


def test_stop_drilling_when_no_levels_yet():
    assert should_keep_drilling({"levels": [], "depth": 0}) == "rule_out"
