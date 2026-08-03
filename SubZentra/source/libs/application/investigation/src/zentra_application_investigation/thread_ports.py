from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from zentra_domain_investigation import InvestigationThread, ThreadMessage

from .ports import (
    AgentExecutionRepository,
    AuditOutboxRepository,
    DraftFindingRepository,
    EvidenceCitationRepository,
    ExecutionJobRepository,
    HumanApprovalRepository,
    InvestigationRepository,
    WorkFeedRepository,
)
from .thread_dto import RoutingResult, ThreadCursor, ThreadSlice
from .workspace_ports import OrganizationRepository


class IntakePort(Protocol):
    """Resolves a message against the Tenant's Analytical Scope (ADR-0027).

    Replaces the keyword-matched scenario whitelist that used to sit in
    `thread_routing.py`: same `RoutingResult` shape, but decided by an Agent
    reading a scoped catalog instead of a token-overlap check.
    """

    async def resolve(
        self,
        question: str,
        *,
        tenant_id: UUID,
        data_connection_id: UUID | None = None,
    ) -> RoutingResult: ...


class ThreadRepository(Protocol):
    async def add_thread(self, thread: InvestigationThread) -> None: ...

    async def get_thread(
        self, thread_id: UUID, *, for_update: bool = False
    ) -> InvestigationThread | None: ...

    async def save_thread(self, thread: InvestigationThread) -> None: ...

    async def delete_thread(self, thread_id: UUID) -> None: ...

    async def add_message(self, message: ThreadMessage) -> None: ...

    async def messages_for_thread(
        self, thread_id: UUID
    ) -> tuple[ThreadMessage, ...]: ...

    async def list_threads(
        self,
        *,
        project_id: UUID,
        include_archived: bool,
        limit: int,
        after: ThreadCursor | None,
    ) -> ThreadSlice: ...

    async def investigation_id_for_thread(self, thread_id: UUID) -> UUID | None: ...


class ThreadUnitOfWork(Protocol):
    threads: ThreadRepository
    organization: OrganizationRepository
    investigations: InvestigationRepository
    jobs: ExecutionJobRepository
    outbox: AuditOutboxRepository
    work_feed: WorkFeedRepository
    approvals: HumanApprovalRepository
    agent_executions: AgentExecutionRepository
    draft_findings: DraftFindingRepository
    citations: EvidenceCitationRepository

    async def commit(self) -> None: ...


class ThreadUnitOfWorkFactory(Protocol):
    def __call__(
        self, tenant_id: UUID, trace_id: UUID, span_id: UUID
    ) -> AbstractAsyncContextManager[ThreadUnitOfWork]: ...
