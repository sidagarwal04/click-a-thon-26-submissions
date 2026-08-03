from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import AgentRole

from zentra_domain_investigation import (
    EvidenceReference,
    WorkItem,
    WorkItemStatus,
    WorkItemTransitionError,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
WORK_ITEM_ID = UUID("61000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("30000000-0000-0000-0000-000000000003")


def pending_item(**overrides: object) -> WorkItem:
    defaults: dict[str, object] = dict(
        work_item_id=WORK_ITEM_ID,
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        role=AgentRole.SQL_ANALYST,
        objective="Measure EU refund amount for June and July 2026",
        now=NOW,
    )
    defaults.update(overrides)
    return WorkItem.create(**defaults)  # type: ignore[arg-type]


def test_create_rejects_a_blank_objective() -> None:
    with pytest.raises(ValueError, match="objective"):
        pending_item(objective="   ")


def test_start_run_complete_records_artifacts() -> None:
    item = pending_item()

    item.start(now=NOW + timedelta(seconds=1))
    ref = EvidenceReference("artifact://executions/1/result")
    item.complete(now=NOW + timedelta(seconds=2), artifact_refs=(ref,))

    assert item.status is WorkItemStatus.COMPLETED
    assert item.artifact_refs == (ref,)
    assert item.updated_at == NOW + timedelta(seconds=2)


def test_complete_requires_running_status() -> None:
    item = pending_item()

    with pytest.raises(WorkItemTransitionError, match="running"):
        item.complete(now=NOW)


def test_a_terminal_work_item_cannot_be_rejected_or_blocked() -> None:
    item = pending_item()
    item.start(now=NOW)
    item.complete(now=NOW)

    with pytest.raises(WorkItemTransitionError, match="terminal"):
        item.reject(now=NOW, reason="too late")
    with pytest.raises(WorkItemTransitionError, match="terminal"):
        item.block(now=NOW, reason="too late")


def test_waiting_item_can_resume_to_running() -> None:
    item = pending_item()
    item.start(now=NOW)
    item.wait(now=NOW)

    item.start(now=NOW + timedelta(seconds=1))

    assert item.status is WorkItemStatus.RUNNING


def test_ready_requires_every_dependency_completed() -> None:
    dependency_id = uuid4()
    item = pending_item(depends_on=(dependency_id,))

    assert item.ready(completed_ids=frozenset()) is False
    assert item.ready(completed_ids=frozenset({dependency_id})) is True


def test_reject_requires_a_reason() -> None:
    item = pending_item()

    with pytest.raises(ValueError, match="reason"):
        item.reject(now=NOW, reason="  ")
