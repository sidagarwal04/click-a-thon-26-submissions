"""What a citation must be able to say."""

from __future__ import annotations

from uuid import UUID

from zentra_domain_agent_execution import ConfidenceOutcome

from zentra_domain_investigation import (
    CitationFilter,
    CitationState,
    EvidenceCitation,
)

TENANT_ID = UUID("aa000000-0000-0000-0000-000000000001")
INVESTIGATION_ID = UUID("bb000000-0000-0000-0000-000000000001")
EXECUTION_ID = UUID("dd000000-0000-0000-0000-000000000001")


def citation(**overrides) -> EvidenceCitation:
    defaults = {
        "citation_id": UUID("cc000000-0000-0000-0000-000000000001"),
        "tenant_id": TENANT_ID,
        "investigation_id": INVESTIGATION_ID,
        "metric": "refund_amount",
        "filters": (
            CitationFilter(member="Commerce.region", operator="equals", values=("EU",)),
        ),
        "period": "July 2026",
        "grain": "month",
        "producing_execution_id": EXECUTION_ID,
        "aggregate_value": "260.00",
        "evaluator_outcome": ConfidenceOutcome(
            score=0.82, calibration_method="evaluator_independent_recheck"
        ),
    }
    return EvidenceCitation(**(defaults | overrides))


def test_a_citation_says_everything_an_artifact_pointer_could_not() -> None:
    """ADR 0011's list, in full. A pointer said only *where*; this says what,
    scoped how, measured by whom, and what the recheck made of it."""
    subject = citation()

    assert subject.metric == "refund_amount"
    assert subject.filters[0].member == "Commerce.region"
    assert subject.filters[0].values == ("EU",)
    assert subject.period == "July 2026"
    assert subject.grain == "month"
    assert subject.producing_execution_id == EXECUTION_ID
    assert subject.aggregate_value == "260.00"
    assert subject.evaluator_outcome is not None


def test_a_citation_is_active_until_something_says_otherwise() -> None:
    assert citation().state is CitationState.ACTIVE


def test_loss_and_deliberate_erasure_are_different_states() -> None:
    """Collapsing them would either alarm a reader about a deletion they asked
    for, or quietly reassure them about data loss."""
    assert CitationState.UNAVAILABLE is not CitationState.TOMBSTONED
    assert {state.value for state in CitationState} == {
        "active",
        "unavailable",
        "tombstoned",
    }


def test_a_citation_belongs_to_one_tenant_and_investigation() -> None:
    subject = citation()

    assert subject.tenant_id == TENANT_ID
    assert subject.investigation_id == INVESTIGATION_ID
