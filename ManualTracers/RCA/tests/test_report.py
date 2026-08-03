from app.report import ledger_to_report, split_narrative
from app.schemas import ClickStackAlertPayload

# same shape as test_grounding.py's LEDGER — one finding, no decomposition
LEDGER = {
    "metric_id": "fill_rate",
    "window": {"start": "2026-07-30T12:00:00", "end": "2026-07-30T23:00:00"},
    "dimension_id": None,
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

ALERT = ClickStackAlertPayload(title="fill_rate anomaly", body="metric_id=fill_rate")


def test_split_narrative_maps_three_paragraphs_when_no_decomposition():
    text = (
        "fill_rate dropped globally, actual 0.7499 vs expected 0.7813, peak z 9.17.\n\n"
        "os_version=Android 15 is the localized culprit, holdout confirmed.\n\n"
        "8 candidates tested; publisher_tier=tier_2 was a near-miss ruled out."
    )
    sections = split_narrative(text, LEDGER)
    assert sections["what_went_wrong"].startswith("fill_rate dropped")
    assert sections["why_it_happened"].startswith("os_version=Android 15")
    assert sections["supporting_data_summary"].startswith("8 candidates tested")


def test_split_narrative_folds_decomposition_paragraph_into_what_went_wrong():
    # revenue-shaped ledger: decomposition present, 2 implicated factors -> 2 findings
    # -> narrator writes 5 paragraphs: §1, §2, §3 x2, §4
    revenue_ledger = {
        **LEDGER,
        "decomposition": {"factors": []},
        "findings": [LEDGER["findings"][0], LEDGER["findings"][0]],
    }
    text = "\n\n".join(
        [
            "revenue fell globally.",
            "fill_rate and ecpm both moved, offsetting partly.",
            "fill_rate: os_version=Android 15 localized.",
            "ecpm: category=finance localized.",
            "checked and ruled out summary.",
        ]
    )
    sections = split_narrative(text, revenue_ledger)
    assert (
        sections["what_went_wrong"]
        == "revenue fell globally.\n\nfill_rate and ecpm both moved, offsetting partly."
    )
    assert (
        sections["why_it_happened"]
        == "fill_rate: os_version=Android 15 localized.\n\necpm: category=finance localized."
    )
    assert sections["supporting_data_summary"] == "checked and ruled out summary."


def test_split_narrative_single_sentence_is_not_reproducible_shape():
    sections = split_narrative(
        "The alert did not reproduce against current data.", LEDGER
    )
    assert (
        sections["what_went_wrong"]
        == "The alert did not reproduce against current data."
    )
    assert sections["why_it_happened"] == ""
    assert sections["supporting_data_summary"] == ""


def test_ledger_to_report_matches_ui_template_schema():
    narrative = {
        "narrative": "para one.\n\npara two.\n\npara three.",
        "grounded": True,
        "source": "llm",
    }
    report = ledger_to_report(LEDGER, ALERT, narrative)

    assert report["status"] == "localized"
    assert report["title"] == "fill_rate — localized"
    assert report["trigger"]["metric_id"] == "fill_rate"
    assert report["trigger"]["alert_title"] == "fill_rate anomaly"
    assert report["trigger"]["peak_abs_z"] == 9.17
    assert report["candidates"] == LEDGER["findings"][0]["candidates"]
    assert report["holdout"] == LEDGER["findings"][0]["holdout"]
    assert report["ledger"] == LEDGER


def test_ledger_to_report_ruled_out_reason_mirrors_the_js_sample():
    narrative = {"narrative": "para one.\n\npara two.\n\npara three.", "grounded": True}
    report = ledger_to_report(LEDGER, ALERT, narrative)

    assert report["ruled_out"] == [
        {
            "segment": "publisher_tier=tier_2",
            "reason": "Holdout residual (0.0029) did not move with this slice; contribution "
            "1791 is a correlated follower of os_version=Android 15.",
        }
    ]


def test_ledger_to_report_handles_no_findings_without_crashing():
    empty_ledger = {
        "metric_id": "fill_rate",
        "verdict": "not_reproducible",
        "window": {"start": "a", "end": "b"},
        "dimension_id": None,
        "decomposition": None,
        "findings": [],
    }
    narrative = {
        "narrative": "The alert did not reproduce against current data.",
        "grounded": True,
        "source": "template",
    }
    report = ledger_to_report(empty_ledger, ALERT, narrative)

    assert report["status"] == "not_reproducible"
    assert report["candidates"] == []
    assert report["holdout"] is None
    assert report["ruled_out"] == []
