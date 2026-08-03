from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from zentra_domain_agent_execution import ConfidenceOutcome, ValidationOutcome

from zentra_domain_investigation import (
    ApprovalDecision,
    EvaluationDirective,
    EvidenceReference,
    Finding,
    HumanApproval,
    HumanApprovalStatus,
    Investigation,
    InvestigationStatus,
    InvestigationTransitionError,
    MetricComparison,
    RejectionReason,
    directive_for_outcome,
)

CONFIDENCE_THRESHOLD = 0.7

INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")
NOW = datetime(2026, 7, 29, 8, 30, tzinfo=UTC)


def finding() -> Finding:
    return Finding(
        headline="EU refund rate increased from 25% to 75%",
        summary="Shipping-delay refunds account for the July increase.",
        metrics=(
            MetricComparison(
                metric="refund_rate",
                previous_value="25",
                current_value="75",
                unit="percent",
            ),
        ),
        evidence_refs=(EvidenceReference("artifact://seed/eu-refund-spike"),),
    )


def validation(*, passed: bool = False) -> ValidationOutcome:
    return ValidationOutcome(
        passed=passed,
        checks=("governed_metrics", "minimum_sample_size"),
        issues=() if passed else ("Only four orders were observed per month.",),
    )


def confidence(score: float) -> ConfidenceOutcome:
    return ConfidenceOutcome(score=score, calibration_method="evaluator_recheck")


def new_investigation() -> Investigation:
    return Investigation.create(
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        question="Why did EU refunds increase from June to July 2026?",
        now=NOW,
    )


@pytest.mark.parametrize(
    ("thread_id", "thread_sequence", "initiating_message_id"),
    [
        (INVESTIGATION_ID, None, None),
        (INVESTIGATION_ID, 0, TENANT_ID),
        (None, 1, TENANT_ID),
    ],
)
def test_thread_link_must_be_complete_with_a_positive_sequence(
    thread_id: UUID | None,
    thread_sequence: int | None,
    initiating_message_id: UUID | None,
) -> None:
    with pytest.raises(InvestigationTransitionError):
        Investigation.create(
            investigation_id=INVESTIGATION_ID,
            tenant_id=TENANT_ID,
            question="Why did EU refunds increase?",
            now=NOW,
            thread_id=thread_id,
            thread_sequence=thread_sequence,
            initiating_message_id=initiating_message_id,
        )


def test_canonical_investigation_requires_human_approval() -> None:
    investigation = new_investigation()

    investigation.start(NOW + timedelta(seconds=1))
    investigation.begin_evaluation(NOW + timedelta(seconds=2))
    approval_reason = investigation.record_evaluation(
        directive=EvaluationDirective.REVIEW,
        outcome=validation(),
        finding=finding(),
        now=NOW + timedelta(seconds=3),
    )

    assert investigation.status is InvestigationStatus.AWAITING_APPROVAL
    assert investigation.evaluation_attempts == 1
    assert approval_reason == "tenant_policy"
    assert [event.event_type for event in investigation.events] == [
        "investigation.created",
        "investigation.started",
        "investigation.evaluation_started",
        "investigation.validation_completed",
        "human_approval.requested",
    ]
    assert [event.occurred_at for event in investigation.events] == sorted(
        event.occurred_at for event in investigation.events
    )
    assert len({event.occurred_at for event in investigation.events}) == len(
        investigation.events
    )


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (ApprovalDecision.APPROVE, InvestigationStatus.COMPLETED),
        (ApprovalDecision.REJECT, InvestigationStatus.REJECTED),
    ],
)
def test_human_decision_finishes_an_investigation(
    decision: ApprovalDecision,
    expected: InvestigationStatus,
) -> None:
    investigation = new_investigation()
    investigation.start(NOW)
    investigation.begin_evaluation(NOW)
    investigation.record_evaluation(
        directive=EvaluationDirective.REVIEW,
        outcome=validation(),
        finding=finding(),
        now=NOW,
    )

    investigation.decide(
        decision=decision,
        rejection_reason=(
            RejectionReason.INSUFFICIENT_EVIDENCE
            if decision is ApprovalDecision.REJECT
            else None
        ),
        now=NOW + timedelta(seconds=1),
    )

    assert investigation.status is expected
    assert investigation.finished_at == NOW + timedelta(seconds=1)


def test_terminal_investigation_cannot_transition() -> None:
    investigation = new_investigation()
    investigation.cancel(NOW)

    with pytest.raises(InvestigationTransitionError, match="cancelled"):
        investigation.start(NOW)


def test_fourth_evaluation_is_rejected() -> None:
    investigation = new_investigation()
    investigation.start(NOW)

    for attempt in range(3):
        investigation.begin_evaluation(NOW + timedelta(seconds=attempt))
        investigation.record_evaluation(
            directive=EvaluationDirective.RETRY,
            outcome=validation(),
            finding=finding(),
            now=NOW + timedelta(seconds=attempt),
        )

    assert investigation.status is InvestigationStatus.AWAITING_APPROVAL
    assert investigation.evaluation_attempts == 3

    with pytest.raises(InvestigationTransitionError, match="awaiting_approval"):
        investigation.begin_evaluation(NOW)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.9, EvaluationDirective.PASS),
        (0.7, EvaluationDirective.PASS),
        (0.5, EvaluationDirective.REVIEW),
    ],
)
def test_confidence_is_compared_against_the_tenant_threshold(
    score: float,
    expected: EvaluationDirective,
) -> None:
    directive = directive_for_outcome(
        confidence(score),
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )

    assert directive is expected


def test_confident_evaluation_completes_without_a_human() -> None:
    investigation = new_investigation()
    investigation.start(NOW)
    investigation.begin_evaluation(NOW)

    approval_reason = investigation.record_evaluation(
        directive=directive_for_outcome(
            confidence(0.91),
            confidence_threshold=CONFIDENCE_THRESHOLD,
        ),
        outcome=confidence(0.91),
        finding=finding(),
        now=NOW,
    )

    assert approval_reason is None
    assert investigation.status is InvestigationStatus.COMPLETED
    assert investigation.completion is not None
    assert investigation.completion.human_approved is False


def test_low_confidence_gates_on_low_confidence_not_tenant_policy() -> None:
    investigation = new_investigation()
    investigation.start(NOW)
    investigation.begin_evaluation(NOW)

    approval_reason = investigation.record_evaluation(
        directive=directive_for_outcome(
            confidence(0.42),
            confidence_threshold=CONFIDENCE_THRESHOLD,
        ),
        outcome=confidence(0.42),
        finding=finding(),
        now=NOW,
    )

    assert investigation.status is InvestigationStatus.AWAITING_APPROVAL
    assert approval_reason == "low_confidence"


def test_unconverged_retry_gates_on_contradiction_regardless_of_confidence() -> None:
    investigation = new_investigation()
    investigation.start(NOW)

    for attempt in range(3):
        investigation.begin_evaluation(NOW + timedelta(seconds=attempt))
        approval_reason = investigation.record_evaluation(
            directive=EvaluationDirective.RETRY,
            outcome=confidence(0.95),
            finding=finding(),
            now=NOW + timedelta(seconds=attempt),
        )

    assert investigation.evaluation_attempts == 3
    assert investigation.status is InvestigationStatus.AWAITING_APPROVAL
    assert approval_reason == "contradiction_unresolved"


def test_evidence_references_must_be_artifacts() -> None:
    with pytest.raises(ValueError, match="artifact://"):
        EvidenceReference("https://example.test/raw-result")


def test_same_decision_is_idempotent_but_conflicting_decision_is_rejected() -> None:
    approval = HumanApproval(
        approval_id=UUID("33000000-0000-0000-0000-000000000003"),
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        reason="tenant_policy",
        status=HumanApprovalStatus.PENDING,
        requested_at=NOW,
    )

    changed = approval.decide(
        decision=ApprovalDecision.REJECT,
        rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
        user_id=UUID("44000000-0000-0000-0000-000000000004"),
        now=NOW,
    )
    replayed = approval.decide(
        decision=ApprovalDecision.REJECT,
        rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
        user_id=UUID("44000000-0000-0000-0000-000000000004"),
        now=NOW,
    )

    assert changed is True
    assert replayed is False
    with pytest.raises(InvestigationTransitionError, match="already decided"):
        approval.decide(
            decision=ApprovalDecision.APPROVE,
            rejection_reason=None,
            user_id=UUID("44000000-0000-0000-0000-000000000004"),
            now=NOW,
        )
