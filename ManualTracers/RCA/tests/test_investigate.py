import math
from unittest.mock import patch

import pytest

from app.investigate import (
    compute_factor_contributions,
    compute_holdout_verdict,
    compute_interaction,
    holdout_check,
    _log_growth,
)


def _strata(rows):
    """rows: (child_value, in_parent, value, sample_count) — scan_interaction's row shape."""
    return [
        {"child_value": v, "in_parent": p, "value": val, "sample_count": n}
        for v, p, val, n in rows
    ]


def test_localized_when_residual_near_zero():
    # matches the Android 15 fill_rate incident: candidate delta -0.35, residual ~0
    assert (
        compute_holdout_verdict(candidate_delta=-0.3517, residual_delta=-0.0006)
        == "localized"
    )


def test_inconclusive_when_residual_comparable_to_candidate():
    assert (
        compute_holdout_verdict(candidate_delta=-0.10, residual_delta=-0.08)
        == "inconclusive"
    )


def test_inconclusive_when_candidate_delta_is_zero():
    assert (
        compute_holdout_verdict(candidate_delta=0.0, residual_delta=0.01)
        == "inconclusive"
    )


def test_ratio_threshold_is_a_boundary():
    assert (
        compute_holdout_verdict(
            candidate_delta=-1.0, residual_delta=0.25, ratio_threshold=0.25
        )
        == "localized"
    )
    assert (
        compute_holdout_verdict(
            candidate_delta=-1.0, residual_delta=0.2500001, ratio_threshold=0.25
        )
        == "inconclusive"
    )


@pytest.mark.anyio
async def test_holdout_check_null_complement_is_inconclusive_not_a_crash():
    # the candidate is ~all the traffic in this window (a real, reachable state on a narrow
    # analysis window, not just a test artifact) -> nullIf(count(),0) makes value_sql return
    # NULL for the complement. residual_actual - global_expected_ref used to crash on
    # None - float; with no complement to hold out against, this is inconclusive, not an error.
    with (
        patch(
            "app.investigate.get_metric",
            return_value={"sql": "sum(is_filled)/nullIf(count(),0)"},
        ),
        patch("app.investigate.known_dims", return_value=frozenset({"os_version"})),
        patch(
            "app.investigate.query_rows",
            return_value=[{"value": None, "sample_count": 0}],
        ),
    ):
        result = await holdout_check(
            "fill_rate",
            [{"dim_name": "os_version", "dim_value": "Android 15"}],
            candidate_delta=-0.35,
            global_expected_ref=0.785,
            start="2026-08-01",
            end="2026-08-01",
        )
    assert result["residual_actual"] is None
    assert result["residual_delta"] is None
    assert result["verdict"] == "inconclusive"


def test_log_growth_is_exact_log_ratio():
    assert _log_growth(0.4338, 0.7849) == math.log(0.4338 / 0.7849)


def test_log_growth_guards_nonpositive_inputs():
    assert _log_growth(0.0, 0.5) == 0.0
    assert _log_growth(0.5, 0.0) == 0.0


def test_single_dominant_factor_is_sole_implicated():
    # fill_rate drives the move; requests/render_rate/ecpm barely move — mirrors the
    # Android 15 incident's decomposition (docs/RCA_DECOMPOSITION_MATH.md §3 "corrected" example)
    growth = {"requests": 0.001, "fill_rate": -0.29, "render_rate": 0.0, "ecpm": 0.03}
    min_effect_rel = {
        "requests": 0.05,
        "fill_rate": 0.02,
        "render_rate": 0.02,
        "ecpm": 0.03,
    }
    result = compute_factor_contributions(
        growth, total_delta_rel=-0.046, min_effect_rel=min_effect_rel
    )

    assert result["offsetting"] is False
    verdicts = {f["metric_id"]: f["verdict"] for f in result["factors"]}
    assert verdicts == {
        "requests": "cleared",
        "fill_rate": "implicated",
        "render_rate": "cleared",
        "ecpm": "cleared",
    }
    # contributions must sum to the total revenue delta_rel — the whole point of the log-share split
    assert sum(f["contribution_rel"] for f in result["factors"]) == pytest.approx(
        -0.046
    )


def test_two_factors_can_both_be_implicated():
    # two independent real faults in the same window — not one masking the other
    growth = {"requests": 0.001, "fill_rate": -0.20, "render_rate": 0.0, "ecpm": -0.15}
    min_effect_rel = {
        "requests": 0.05,
        "fill_rate": 0.02,
        "render_rate": 0.02,
        "ecpm": 0.03,
    }
    result = compute_factor_contributions(
        growth, total_delta_rel=-0.10, min_effect_rel=min_effect_rel
    )

    verdicts = {f["metric_id"]: f["verdict"] for f in result["factors"]}
    assert verdicts["fill_rate"] == "implicated"
    assert verdicts["ecpm"] == "implicated"


def test_interaction_found_when_one_stratum_carries_the_parent_effect():
    # parent = os_version 'Android 15', crossed with device_model: only Galaxy A54 inside the
    # parent slice is depressed against the same device outside it -> the culprit is the pair
    rows = _strata(
        [
            ("Galaxy A54", 1, 0.300, 1000),
            ("Galaxy A54", 0, 0.780, 1000),
            ("Pixel 8", 1, 0.770, 1000),
            ("Pixel 8", 0, 0.780, 1000),
            ("iPhone 15", 1, 0.775, 1000),
            ("iPhone 15", 0, 0.780, 1000),
        ]
    )
    result = compute_interaction("device_model", rows)

    assert result["verdict"] == "interaction"
    assert result["top"]["child_value"] == "Galaxy A54"
    assert result["strata_tested"] == 3
    assert result["top_share"] > 0.9


def test_uniform_when_the_parent_effect_is_spread_across_strata():
    # every device inside the parent slice is equally depressed -> the fault is at the
    # parent's level, and naming a device would be bleed-through
    rows = _strata(
        [
            ("Galaxy A54", 1, 0.50, 1000),
            ("Galaxy A54", 0, 0.78, 1000),
            ("Pixel 8", 1, 0.50, 1000),
            ("Pixel 8", 0, 0.78, 1000),
            ("iPhone 15", 1, 0.50, 1000),
            ("iPhone 15", 0, 0.78, 1000),
        ]
    )
    assert compute_interaction("device_model", rows)["verdict"] == "uniform"


def test_opposite_signed_strata_do_not_manufacture_a_concentration():
    # one stratum up, one down by the same amount: the NET effect is zero, so a net
    # denominator would divide by ~0 and report a fake dominant child. Gross must be used.
    rows = _strata(
        [
            ("Galaxy A54", 1, 0.90, 1000),
            ("Galaxy A54", 0, 0.78, 1000),
            ("Pixel 8", 1, 0.66, 1000),
            ("Pixel 8", 0, 0.78, 1000),
        ]
    )
    result = compute_interaction("device_model", rows)

    assert result["verdict"] == "uniform"
    assert result["top_share"] == pytest.approx(0.5)


def test_no_interaction_without_a_control_for_the_stratum():
    # child value exists only inside the parent slice — nothing to compare it against
    rows = _strata([("Galaxy A54", 1, 0.30, 1000), ("Pixel 8", 0, 0.78, 1000)])
    assert compute_interaction("device_model", rows) is None


def test_offsetting_factors_skip_the_share_split():
    # fill_rate down, ecpm up, nearly cancel — net revenue move is ~0
    growth = {
        "requests": 0.0,
        "fill_rate": -0.003,
        "render_rate": 0.0005,
        "ecpm": 0.002,
    }
    min_effect_rel = {
        "requests": 0.05,
        "fill_rate": 0.02,
        "render_rate": 0.02,
        "ecpm": 0.03,
    }
    result = compute_factor_contributions(
        growth, total_delta_rel=-0.0005, min_effect_rel=min_effect_rel
    )

    assert result["offsetting"] is True
    # contribution_rel falls back to each factor's own log_growth, not a share of ~0
    fill_rate = next(f for f in result["factors"] if f["metric_id"] == "fill_rate")
    assert fill_rate["contribution_rel"] == growth["fill_rate"]
