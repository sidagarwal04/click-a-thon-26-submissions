"""Pure-function tests for engine/rank.py's compute_segment_contributions --
no ClickHouse needed. Shared by rank.py (rollup-backed) and drilldown.py
(raw-ad_events-backed), so a regression here would silently break both.
"""

from engine.config import METRIC_DEFS
from engine.rank import compute_segment_contributions


def test_single_segment_explains_the_whole_deviation():
    spec = METRIC_DEFS["requests"]  # numerator=requests, no denominator
    current = {"A": {"numerator": 1500}, "B": {"numerator": 1000}}
    baseline = {"A": {"numerator": 1000}, "B": {"numerator": 1000}}  # only A moved (+500)

    ranking = compute_segment_contributions("dim", spec, current, baseline)

    assert ranking.top_segment.value == "A"
    assert ranking.top_segment.share_of_total_delta == 1.0  # A alone accounts for the entire delta


def test_evenly_spread_deviation_has_no_dominant_segment():
    spec = METRIC_DEFS["requests"]
    current = {"A": {"numerator": 1100}, "B": {"numerator": 1100}, "C": {"numerator": 1100}}
    baseline = {"A": {"numerator": 1000}, "B": {"numerator": 1000}, "C": {"numerator": 1000}}

    ranking = compute_segment_contributions("dim", spec, current, baseline)

    # each segment contributes an equal, non-dominant share
    for seg in ranking.segments:
        assert abs(seg.share_of_total_delta - (1 / 3)) < 1e-9


def test_empty_string_bucket_is_excluded():
    """'' means "no advertiser" on unfilled requests -- never a real segment
    to attribute a deviation to (see CLAUDE.md)."""
    spec = METRIC_DEFS["requests"]
    current = {"": {"numerator": 5000}, "real_advertiser": {"numerator": 600}}
    baseline = {"": {"numerator": 4000}, "real_advertiser": {"numerator": 500}}

    ranking = compute_segment_contributions("advertiser", spec, current, baseline)

    values = {seg.value for seg in ranking.segments}
    assert "" not in values
    assert ranking.top_segment.value == "real_advertiser"


def test_ratio_metric_computes_metric_now_and_baseline_correctly():
    spec = METRIC_DEFS["fill_rate"]  # fills / requests
    current = {"A": {"numerator": 80, "denominator": 100}}
    baseline = {"A": {"numerator": 90, "denominator": 100}}

    ranking = compute_segment_contributions("dim", spec, current, baseline)

    seg = ranking.top_segment
    assert seg.metric_now == 0.8
    assert seg.metric_baseline == 0.9
