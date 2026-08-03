"""A finding is stored as JSON, so every field it gains has to survive the trip.

No database needed: these are the two pure functions the repository calls on the
way in and out.
"""

from zentra_domain_investigation import EvidenceReference, Finding, MetricComparison

from zentra_adapter_postgres.investigation import _finding_from_json, _finding_to_json


def _finding(*metrics: MetricComparison) -> Finding:
    return Finding(
        headline="EU refunds rose $240 in July",
        summary="Governed evidence requires review.",
        metrics=metrics,
        evidence_refs=(EvidenceReference("artifact://semantic/eu-refunds"),),
    )


def test_the_periods_a_metric_covers_round_trip() -> None:
    stored = _finding_to_json(
        _finding(
            MetricComparison(
                "refund_amount",
                "20.00",
                "260.00",
                "USD",
                previous_label="June 2026",
                current_label="July 2026",
            )
        )
    )

    restored = _finding_from_json(stored)

    assert restored is not None
    assert restored.metrics[0].previous_label == "June 2026"
    assert restored.metrics[0].current_label == "July 2026"


def test_a_metric_naming_no_period_round_trips_as_none() -> None:
    stored = _finding_to_json(
        _finding(MetricComparison("refund_rate", "25", "75", "percent"))
    )

    restored = _finding_from_json(stored)

    assert restored is not None
    assert restored.metrics[0].previous_label is None
    assert restored.metrics[0].current_label is None


def test_a_row_written_before_labels_existed_still_loads() -> None:
    """Investigations persisted before this field cannot be rewritten, so
    reading must not require it."""
    legacy = {
        "headline": "EU refunds rose $240 in July",
        "summary": "Governed evidence requires review.",
        "metrics": [
            {
                "metric": "refund_amount",
                "previous_value": "20.00",
                "current_value": "260.00",
                "unit": "USD",
            }
        ],
        "evidence_refs": ["artifact://semantic/eu-refunds"],
    }

    restored = _finding_from_json(legacy)

    assert restored is not None
    assert restored.metrics[0].previous_value == "20.00"
    assert restored.metrics[0].previous_label is None


def test_a_finding_written_before_the_contraction_still_loads() -> None:
    """The Orchestrator wrote Findings for the whole of Phase 1. Removing the
    node that produced them must not make them unreadable — the row is exactly
    what it was, and nothing about the reader changed."""
    from zentra_adapter_postgres.investigation import _finding_from_json

    orchestrator_written = {
        "headline": "EU refunds rose $240 in July",
        "summary": "Governed EU refund amount rose from $20 to $260.",
        "metrics": [
            {
                "metric": "refund_amount",
                "previous_value": "20.00",
                "current_value": "260.00",
                "unit": "USD",
            }
        ],
        "evidence_refs": ["artifact://execution/60000000-0000-0000-0000-000000000006"],
    }

    finding = _finding_from_json(orchestrator_written)

    assert finding is not None
    assert finding.headline == "EU refunds rose $240 in July"
    assert finding.metrics[0].current_value == "260.00"
    # No claims, no citations: it never had them, and it is not pretended to.
    assert finding.evidence_refs[0].value.startswith("artifact://execution/")
