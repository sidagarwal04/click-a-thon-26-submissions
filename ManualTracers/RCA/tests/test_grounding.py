from app.grounding import (
    allowed_numbers,
    check_grounding,
    fallback_summary,
    round_floats,
)

# real numbers from the Android 15 / fill_rate incident (2026-07-30 window), same shape
# run_investigation returns: decomposition=None for an L2 metric, one finding.
LEDGER = {
    "metric_id": "fill_rate",
    "window": {"start": "2026-07-30T12:00:00", "end": "2026-07-30T23:00:00"},
    "decomposition": None,
    "findings": [
        {
            "factor": "fill_rate",
            "global": {
                "actual": 0.7499,
                "expected": 0.7813,
                "hours": 12,
                "peak_abs_z": 9.17,
            },
            "candidates": [
                {
                    "dim_name": "os_version",
                    "dim_value": "Android 15",
                    "avg_actual": 0.4287,
                    "avg_expected": 0.7449,
                    "peak_abs_z": 23.79,
                    "contribution": 4208.36,
                },
                {
                    "dim_name": "publisher_tier",
                    "dim_value": "tier_2",
                    "avg_actual": 0.7792,
                    "avg_expected": 0.8089,
                    "peak_abs_z": 6.68,
                    "contribution": 1790.85,
                },
            ],
            "holdout": {
                "candidate": [{"dim_name": "os_version", "dim_value": "Android 15"}],
                "residual_actual": 0.7841,
                "residual_delta": 0.0029,
                "candidate_delta": -0.3162,
                "verdict": "localized",
            },
            "interaction": None,
            "verdict": "localized",
            "ruled_out": ["publisher_tier=tier_2"],
        }
    ],
    "verdict": "localized",
}


def test_allowed_numbers_covers_exact_and_percentage_forms():
    allowed = allowed_numbers(LEDGER)
    assert "0.7499" in allowed  # exact echo of a raw ledger float
    assert "42.87" in allowed  # 0.4287 rendered as a percentage
    assert "23.79" in allowed  # a peak_abs_z, matched directly
    assert "15" in allowed  # digit run from the "Android 15" dim_value string


def test_check_grounding_passes_a_clean_narrative():
    clean = (
        "fill_rate actual 0.7499 vs expected 0.7813, peak z 9.17. "
        "os_version=Android 15 confirmed, contribution 4208.36."
    )
    assert check_grounding(clean, allowed_numbers(LEDGER)) == []


def test_check_grounding_flags_a_fabricated_number():
    fabricated = "fill_rate actually dropped to 0.1234, a figure nowhere in the ledger."
    ungrounded = check_grounding(fabricated, allowed_numbers(LEDGER))
    assert "0.1234" in ungrounded


def test_fallback_summary_needs_no_llm_and_names_the_key_facts():
    summary = fallback_summary(LEDGER)
    assert "fill_rate" in summary
    assert "localized" in summary
    assert "Android 15" in summary


def test_round_floats_makes_raw_clickhouse_precision_groundable():
    # real shape: a ClickHouse float straight off the wire, 16 significant digits. The
    # system prompt tells the model to copy numbers verbatim from what it's shown — before
    # this fix, narrate.py handed it the raw ledger, so a fully-compliant model would write
    # this exact 16-digit string, which no 0-6dp rounding of itself ever matches.
    raw_value = 9.392279762013764
    raw = {
        **LEDGER,
        "findings": [
            {
                **LEDGER["findings"][0],
                "global": {**LEDGER["findings"][0]["global"], "peak_abs_z": raw_value},
            }
        ],
    }
    verbatim_echo = str(raw_value)
    assert verbatim_echo not in allowed_numbers(
        raw
    )  # the bug: a compliant echo was rejected

    # the fix: round before the model ever sees it, so a verbatim copy is always groundable
    rounded = round_floats(raw)
    assert rounded["findings"][0]["global"]["peak_abs_z"] == 9.39228
    compliant_narrative = "peak z-score reached 9.39228 during the window."
    assert check_grounding(compliant_narrative, allowed_numbers(rounded)) == []


def test_fallback_summary_names_both_halves_of_a_crossed_culprit():
    # depth-1 holdout came back inconclusive, the dependency walk crossed os_version with
    # device_model, and the pair's holdout confirmed it
    finding = {
        **LEDGER["findings"][0],
        "holdout": {**LEDGER["findings"][0]["holdout"], "verdict": "inconclusive"},
        "interaction": {
            "child_dim": "device_model",
            "strata_tested": 8,
            "top_share": 0.83,
            "top": {
                "child_value": "Galaxy A54",
                "rate_in": 0.31,
                "rate_out": 0.78,
                "effect": -0.47,
                "contribution": -3910.5,
            },
            "verdict": "interaction",
            "holdout": {
                "candidate": [
                    {"dim_name": "os_version", "dim_value": "Android 15"},
                    {"dim_name": "device_model", "dim_value": "Galaxy A54"},
                ],
                "residual_actual": 0.7802,
                "residual_delta": -0.0011,
                "candidate_delta": -0.47,
                "verdict": "localized",
            },
        },
    }
    summary = fallback_summary({**LEDGER, "findings": [finding]})
    assert "os_version=Android 15 AND device_model=Galaxy A54" in summary
    assert "0.83" in summary
