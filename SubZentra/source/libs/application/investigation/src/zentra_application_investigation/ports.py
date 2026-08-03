"""The seams the application talks through.

Split from `service.py` alongside `dto.py`. Protocols rather than base classes,
so an adapter satisfies one by shape and the application never imports it.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from zentra_domain_agent_execution import AgentExecutionRecord
from zentra_domain_investigation import (
    Conflict,
    DeletionCategory,
    DomainEvent,
    DraftFinding,
    ErasureOperation,
    EvidenceCitation,
    ExecutionJob,
    Fact,
    HumanApproval,
    Investigation,
    InvestigationBoard,
    KnowledgeGap,
    ThreadEvent,
    Tombstone,
    VisualizationActionMapping,
    VisualizationArtifact,
    VisualizationBriefV1,
    WorkFeedEventKind,
    WorkFeedPayload,
    WorkItem,
)

from .dto import PipelineResult, TimelineEntry, UsageSummary


class InvestigationPipeline(Protocol):
    async def run(
        self,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        model_tier: str,
        data_connection_id: UUID | None = None,
    ) -> PipelineResult: ...


class InvestigationRepository(Protocol):
    async def add(self, investigation: Investigation) -> None: ...

    async def get(
        self,
        investigation_id: UUID,
        *,
        for_update: bool = False,
    ) -> Investigation | None: ...

    async def save(
        self,
        investigation: Investigation,
        *,
        expected_version: int,
    ) -> None: ...

    async def latest_for_thread(
        self,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> Investigation | None: ...

    async def all_for_thread(self, thread_id: UUID) -> tuple[Investigation, ...]: ...


class HumanApprovalRepository(Protocol):
    async def add(self, approval: HumanApproval) -> None: ...

    async def get_for_investigation(
        self,
        investigation_id: UUID,
        *,
        approval_id: UUID | None = None,
        for_update: bool = False,
    ) -> HumanApproval | None: ...

    async def save(self, approval: HumanApproval) -> None: ...


class AgentExecutionRepository(Protocol):
    async def add(self, execution: AgentExecutionRecord) -> None: ...

    async def usage_for_investigation(self, investigation_id: UUID) -> UsageSummary: ...


class ExecutionJobRepository(Protocol):
    async def add_job(self, job: ExecutionJob) -> None: ...

    async def claim_next(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_for: timedelta,
    ) -> ExecutionJob | None: ...

    async def get_job(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExecutionJob | None: ...

    async def get_for_investigation(
        self,
        investigation_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExecutionJob | None: ...

    async def save_job(self, job: ExecutionJob) -> None: ...


class EvidenceCitationRepository(Protocol):
    async def add(
        self,
        citations: Sequence[EvidenceCitation],
    ) -> None: ...

    async def for_investigation(
        self,
        investigation_id: UUID,
    ) -> tuple[EvidenceCitation, ...]: ...

    async def resolve(
        self,
        investigation_id: UUID,
        citation_id: UUID,
    ) -> EvidenceCitation | Tombstone | None: ...


class ErasureRepository(Protocol):
    async def request(
        self,
        *,
        erasure_id: UUID,
        tenant_id: UUID,
        investigation_id: UUID,
        category: DeletionCategory,
        now: datetime,
    ) -> ErasureOperation: ...

    async def erase(
        self,
        *,
        investigation_id: UUID,
        category: DeletionCategory,
        now: datetime,
    ) -> ErasureOperation: ...


class VisualizationRepository(Protocol):
    async def create(
        self,
        *,
        brief_id: UUID,
        brief: VisualizationBriefV1,
        renderer_configuration: str,
        artifact: VisualizationArtifact,
        actions: Sequence[VisualizationActionMapping],
    ) -> None: ...

    async def add_retry(
        self, artifact: VisualizationArtifact, *, retry_ordinal: int
    ) -> None: ...

    async def brief(self, brief_id: UUID) -> VisualizationBriefV1 | None: ...

    async def get(
        self, visualization_id: UUID, *, for_update: bool = False
    ) -> VisualizationArtifact | None: ...

    async def latest_for_investigation(
        self, investigation_id: UUID
    ) -> VisualizationArtifact | None: ...

    async def next_retry_ordinal(self, brief_id: UUID) -> int: ...

    async def save(self, artifact: VisualizationArtifact) -> None: ...

    async def action(
        self, visualization_id: UUID, action_id: UUID, *, for_update: bool = False
    ) -> VisualizationActionMapping | None: ...

    async def save_action(self, action: VisualizationActionMapping) -> None: ...

    async def erase(
        self, investigation_id: UUID, *, category: str, now: datetime
    ) -> None: ...


class DraftFindingRepository(Protocol):
    async def add(self, draft: DraftFinding) -> None: ...

    async def latest_for_investigation(
        self,
        investigation_id: UUID,
    ) -> DraftFinding | None: ...


class TenantPolicyRepository(Protocol):
    async def confidence_threshold(self, tenant_id: UUID) -> float: ...

    async def model_tier(self, tenant_id: UUID) -> str: ...


class AuditOutboxRepository(Protocol):
    async def enqueue(self, events: Sequence[DomainEvent]) -> None: ...


class WorkFeedRepository(Protocol):
    async def append(
        self,
        *,
        tenant_id: UUID,
        thread_id: UUID,
        kind: WorkFeedEventKind,
        payload: WorkFeedPayload,
        occurred_at: datetime,
        event_id: UUID | None = None,
    ) -> ThreadEvent: ...

    async def append_for_investigation(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
        kind: WorkFeedEventKind,
        payload: WorkFeedPayload,
        occurred_at: datetime,
        event_id: UUID | None = None,
    ) -> ThreadEvent | None: ...

    async def events_after(
        self, thread_id: UUID, *, after: int, limit: int = 500
    ) -> tuple[ThreadEvent, ...]: ...

    async def latest_sequence(self, thread_id: UUID) -> int: ...


class InvestigationBoardRepository(Protocol):
    async def create(self, board: InvestigationBoard) -> None: ...

    async def save(self, board: InvestigationBoard) -> None: ...

    async def open_gap(
        self, board_id: UUID, tenant_id: UUID, gap: KnowledgeGap
    ) -> None: ...

    async def resolve_gap(self, gap_id: UUID, tenant_id: UUID) -> None: ...

    async def record_fact(
        self, board_id: UUID, tenant_id: UUID, fact: Fact
    ) -> None: ...

    async def open_conflict(
        self, board_id: UUID, tenant_id: UUID, conflict: Conflict
    ) -> None: ...

    async def settle_conflict(self, tenant_id: UUID, conflict: Conflict) -> None:
        """Persist a Conflict's status and the explanation that settled it.

        Takes the whole Conflict rather than its id and a status: `resolved`
        and `documented` are two different claims about the same row, and the
        resolution text is what tells them apart to a reader.
        """
        ...


class WorkItemRepository(Protocol):
    async def add(self, item: WorkItem) -> None: ...

    async def save(self, item: WorkItem) -> None: ...

    async def list_for_investigation(
        self, investigation_id: UUID, tenant_id: UUID
    ) -> tuple[WorkItem, ...]: ...


class InvestigationUnitOfWork(Protocol):
    investigations: InvestigationRepository
    approvals: HumanApprovalRepository
    agent_executions: AgentExecutionRepository
    jobs: ExecutionJobRepository
    draft_findings: DraftFindingRepository
    citations: EvidenceCitationRepository
    erasures: ErasureRepository
    policies: TenantPolicyRepository
    outbox: AuditOutboxRepository
    work_feed: WorkFeedRepository
    visualizations: VisualizationRepository
    investigation_boards: InvestigationBoardRepository
    work_items: WorkItemRepository

    async def commit(self) -> None: ...


class InvestigationUnitOfWorkFactory(Protocol):
    async def bound_tenant_ids(self) -> tuple[UUID, ...]: ...

    def __call__(
        self,
        tenant_id: UUID,
        trace_id: UUID,
        span_id: UUID,
    ) -> AbstractAsyncContextManager[InvestigationUnitOfWork]: ...


class PublicationObserver(Protocol):
    """Somewhere to report a publication decision that is not the audit log.

    A port rather than a direct call because the application may not import an
    adapter, and because an operator's dashboard and the Tenant's Replay record
    are different obligations: one may be dropped under load, the other may
    not.
    """

    def __call__(
        self,
        *,
        decision: str,
        failed_conditions: tuple[str, ...],
    ) -> None: ...


class ErasureObserver(Protocol):
    """Somewhere to report how an erasure went.

    A port for the same reason as `PublicationObserver`, and reporting from
    here rather than from the route because the route does not have these
    facts. The erasure's own identity is minted inside the transaction, and
    `attempts` is a real retry count on the operation — a caller outside can
    only guess at both, and a guessed identifier is worse than none.
    """

    def __call__(
        self,
        *,
        erasure_id: str,
        progress: str,
        attempts: int,
        duration_ms: int,
        failure_category: str | None,
    ) -> None: ...


class AuditWriter(Protocol):
    async def flush(self, *, tenant_id: UUID, investigation_id: UUID) -> bool: ...


class AuditReader(Protocol):
    async def list_timeline(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
    ) -> Sequence[TimelineEntry]: ...
