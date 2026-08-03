"""One unit of work an Orchestrator Loop assigns against an Investigation Board.

See ADR-0026: the Investigation Engine replaces a fixed pipeline with a Board
an Orchestrator Loop reads and a queue of Work Items it assigns. A Work Item
carries no analytical content itself — only enough to route it to a
capability-matched Agent and to know what it produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from zentra_domain_agent_execution import AgentRole

from .model import EvidenceReference


class WorkItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    REJECTED = "rejected"


TERMINAL_WORK_ITEM_STATUSES = frozenset(
    {WorkItemStatus.COMPLETED, WorkItemStatus.REJECTED}
)


class WorkItemTransitionError(RuntimeError):
    pass


@dataclass(slots=True)
class WorkItem:
    """One bounded objective assigned to one Agent Role for one Investigation.

    `depends_on` names other Work Items this one cannot start ahead of — an
    Orchestrator Loop checks completion of every dependency, not just their
    existence, before assigning it (`ready`).
    """

    work_item_id: UUID
    investigation_id: UUID
    tenant_id: UUID
    role: AgentRole
    objective: str
    status: WorkItemStatus
    created_at: datetime
    updated_at: datetime
    parent_work_item_id: UUID | None = None
    depends_on: tuple[UUID, ...] = ()
    artifact_refs: tuple[EvidenceReference, ...] = ()
    rejection_reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        work_item_id: UUID,
        investigation_id: UUID,
        tenant_id: UUID,
        role: AgentRole,
        objective: str,
        now: datetime,
        parent_work_item_id: UUID | None = None,
        depends_on: tuple[UUID, ...] = (),
    ) -> WorkItem:
        if not objective.strip():
            raise ValueError("Work Item objective is required")
        return cls(
            work_item_id=work_item_id,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            role=role,
            objective=objective.strip(),
            status=WorkItemStatus.PENDING,
            created_at=now,
            updated_at=now,
            parent_work_item_id=parent_work_item_id,
            depends_on=depends_on,
        )

    def ready(self, completed_ids: frozenset[UUID]) -> bool:
        """Whether every dependency has completed, not merely been created."""
        return self.status is WorkItemStatus.PENDING and set(
            self.depends_on
        ) <= completed_ids

    def start(self, *, now: datetime) -> None:
        if self.status not in {WorkItemStatus.PENDING, WorkItemStatus.WAITING}:
            raise WorkItemTransitionError(
                f"Cannot start a Work Item from {self.status.value}"
            )
        self.status = WorkItemStatus.RUNNING
        self.updated_at = now

    def wait(self, *, now: datetime) -> None:
        if self.status is not WorkItemStatus.RUNNING:
            raise WorkItemTransitionError("Only a running Work Item can wait")
        self.status = WorkItemStatus.WAITING
        self.updated_at = now

    def block(self, *, now: datetime, reason: str) -> None:
        if self.status in TERMINAL_WORK_ITEM_STATUSES:
            raise WorkItemTransitionError("A terminal Work Item cannot be blocked")
        if not reason.strip():
            raise ValueError("A blocked Work Item requires a reason")
        self.status = WorkItemStatus.BLOCKED
        self.rejection_reason = reason.strip()
        self.updated_at = now

    def complete(
        self, *, now: datetime, artifact_refs: tuple[EvidenceReference, ...] = ()
    ) -> None:
        if self.status is not WorkItemStatus.RUNNING:
            raise WorkItemTransitionError("Only a running Work Item can complete")
        self.status = WorkItemStatus.COMPLETED
        self.artifact_refs = artifact_refs
        self.updated_at = now

    def reject(self, *, now: datetime, reason: str) -> None:
        if self.status in TERMINAL_WORK_ITEM_STATUSES:
            raise WorkItemTransitionError("A terminal Work Item cannot be rejected")
        if not reason.strip():
            raise ValueError("A rejected Work Item requires a reason")
        self.status = WorkItemStatus.REJECTED
        self.rejection_reason = reason.strip()
        self.updated_at = now
