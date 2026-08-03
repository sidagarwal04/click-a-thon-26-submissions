"""What an erasure operation must guarantee before anyone can invoke it."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from zentra_domain_investigation import (
    TERMINAL_STATUSES,
    DeletionCategory,
    ErasureError,
    ErasureOperation,
    ErasureProgress,
    EvidenceSurface,
    InvestigationStatus,
    require_erasable,
)

NOW = datetime(2026, 7, 31, 9, 0, tzinfo=UTC)
TERMINAL = frozenset(status.value for status in TERMINAL_STATUSES)


def operation(**overrides) -> ErasureOperation:
    defaults = {
        "erasure_id": uuid4(),
        "tenant_id": UUID("aa000000-0000-0000-0000-000000000001"),
        "investigation_id": UUID("bb000000-0000-0000-0000-000000000001"),
        "category": DeletionCategory.TENANT_REQUEST,
        "progress": ErasureProgress.REQUESTED,
        "requested_at": NOW,
    }
    return ErasureOperation(**(defaults | overrides))


def test_an_operation_is_scoped_to_one_tenant_and_investigation() -> None:
    subject = operation()

    assert subject.tenant_id == UUID("aa000000-0000-0000-0000-000000000001")
    assert subject.investigation_id == UUID("bb000000-0000-0000-0000-000000000001")
    assert subject.category is DeletionCategory.TENANT_REQUEST


def test_a_completed_erasure_must_say_when() -> None:
    """A Tombstone's timestamp comes from here. Without it the product can say
    evidence was erased but not when, which is half an explanation."""
    with pytest.raises(ErasureError, match="when it completed"):
        operation(progress=ErasureProgress.COMPLETED)

    assert (
        operation(progress=ErasureProgress.COMPLETED, completed_at=NOW).completed_at
        == NOW
    )


def test_only_a_completed_erasure_may_claim_a_completion_time() -> None:
    with pytest.raises(ErasureError, match="Only a completed"):
        operation(progress=ErasureProgress.ERASING, completed_at=NOW)


def test_a_failure_must_record_a_category() -> None:
    with pytest.raises(ErasureError, match="must record why"):
        operation(progress=ErasureProgress.FAILED)

    assert (
        operation(
            progress=ErasureProgress.FAILED, failure_code="storage_unavailable"
        ).failure_code
        == "storage_unavailable"
    )


def test_a_partial_failure_is_never_settled() -> None:
    """ "We deleted some of it" is the one answer this must never give. A failed
    operation is retryable, and treating it as finished is how content survives
    a deletion that reported success."""
    failed = operation(progress=ErasureProgress.FAILED, failure_code="timeout")

    assert failed.is_settled is False
    assert failed.completed_at is None


@pytest.mark.parametrize(
    "progress",
    [ErasureProgress.REQUESTED, ErasureProgress.ERASING, ErasureProgress.FAILED],
)
def test_nothing_but_completion_is_settled(progress: ErasureProgress) -> None:
    subject = operation(
        progress=progress,
        failure_code="timeout" if progress is ErasureProgress.FAILED else None,
    )

    assert subject.is_settled is False


def test_only_a_terminal_investigation_may_be_erased() -> None:
    """Erasing under a live pipeline races every write still to come, and the
    Agent Executions it has not finished would reintroduce what was erased."""
    for status in (
        InvestigationStatus.PENDING,
        InvestigationStatus.RUNNING,
        InvestigationStatus.EVALUATING,
        InvestigationStatus.AWAITING_APPROVAL,
    ):
        with pytest.raises(ErasureError, match="terminal"):
            require_erasable(status.value, TERMINAL)


@pytest.mark.parametrize("status", sorted(TERMINAL))
def test_every_terminal_status_is_erasable(status: str) -> None:
    require_erasable(status, TERMINAL)


def test_the_terminal_set_is_exactly_the_states_that_cannot_transition() -> None:
    """If a fifth terminal state is ever added, this fails rather than
    silently leaving its Investigations un-erasable."""
    assert {"completed", "rejected", "failed", "cancelled"} == TERMINAL


def test_every_evidence_surface_is_named() -> None:
    """A surface in the schema and not in this enum is a surface an erasure
    silently misses. The integration harness walks this list."""
    assert {surface.value for surface in EvidenceSurface} == {
        "agent_execution_input",
        "agent_execution_output",
        "investigation_finding",
        "draft_finding_narrative",
        "draft_finding_claims",
        "citation_aggregate",
        "draft_finding_contradictions",
        "agent_execution_outcome",
        "investigation_failure_message",
    }


def test_a_failure_records_a_category_not_a_message() -> None:
    """An erasure's failure must not become the place the erased value is
    quoted back."""
    failed = operation(
        progress=ErasureProgress.FAILED, failure_code="storage_unavailable"
    )

    assert " " not in (failed.failure_code or "")


def test_the_surface_list_names_every_place_content_can_be() -> None:
    """Nine, not the six this started with. Contradictions are Evaluator prose,
    a validation outcome carries its issues verbatim, and a pipeline failure
    records `str(error)` — all content, all missed until a review said so."""
    assert len(EvidenceSurface) == 9
    assert EvidenceSurface.DRAFT_FINDING_CONTRADICTIONS in EvidenceSurface
    assert EvidenceSurface.AGENT_EXECUTION_OUTCOME in EvidenceSurface
    assert EvidenceSurface.INVESTIGATION_FAILURE_MESSAGE in EvidenceSurface
