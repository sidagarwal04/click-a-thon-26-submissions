"""Drill-down scoring core: metric-from-sums + counterfactual contribution/lift (pure, no DB)."""
from rca import drilldown as d


def test_metric_from_sums_count_and_ratio():
    sums = {"requests": 1000, "fills": 750, "impressions": 600, "clicks": 12, "revenue": 1.5}
    assert d._metric_from_sums("requests", sums) == 1000
    assert d._metric_from_sums("fill_rate", sums) == 0.75
    assert abs(d._metric_from_sums("ecpm", sums) - 1.5 / 600 * 1000) < 1e-9


def test_score_concentrated_segment_has_high_lift():
    # whole population fill_rate 0.785 -> 0.732; the entire drop comes from one small segment
    pop_exp = {"requests": 1000, "fills": 785}
    pop_obs = {"requests": 1000, "fills": 732}
    seg_exp = {"requests": 150, "fills": 118}
    seg_obs = {"requests": 150, "fills": 65}     # this segment lost the 53 fills
    contribution, lift = d._score("fill_rate", pop_obs, pop_exp, seg_obs, seg_exp)
    assert contribution > 0.9      # explains ~all of the gap
    assert lift > 3.0              # and is wildly disproportionate to its ~15% volume


def test_score_proportional_segment_has_lift_near_one():
    # requests drop uniformly: a 20%-of-traffic segment drops 20% like everyone else
    pop_exp = {"requests": 1000}
    pop_obs = {"requests": 550}
    seg_exp = {"requests": 200}
    seg_obs = {"requests": 110}
    _, lift = d._score("requests", pop_obs, pop_exp, seg_obs, seg_exp)
    assert abs(lift - 1.0) < 0.15  # no disproportionality -> not a culprit
