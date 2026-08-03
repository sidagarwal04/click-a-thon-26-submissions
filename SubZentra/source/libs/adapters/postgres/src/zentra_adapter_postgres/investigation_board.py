from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_domain_agent_execution import AgentRole
from zentra_domain_investigation import (
    Conflict,
    EvidenceReference,
    Fact,
    InvestigationBoard,
    KnowledgeGap,
    WorkItem,
    WorkItemStatus,
)

from .schema import (
    board_conflicts,
    board_facts,
    board_gaps,
    investigation_boards,
    work_items,
)


class PostgresInvestigationBoardRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def create(self, board: InvestigationBoard) -> None:
        await self._connection.execute(
            insert(investigation_boards).values(
                board_id=board.board_id,
                tenant_id=board.tenant_id,
                investigation_id=board.investigation_id,
                narrative=board.narrative,
                confidence_score=(
                    board.confidence.score if board.confidence else None
                ),
                confidence_threshold=(
                    board.confidence.threshold if board.confidence else None
                ),
                created_at=board.created_at,
                updated_at=board.updated_at,
            )
        )

    async def save(self, board: InvestigationBoard) -> None:
        await self._connection.execute(
            update(investigation_boards)
            .where(
                investigation_boards.c.board_id == board.board_id,
                investigation_boards.c.tenant_id == board.tenant_id,
            )
            .values(
                narrative=board.narrative,
                confidence_score=(
                    board.confidence.score if board.confidence else None
                ),
                confidence_threshold=(
                    board.confidence.threshold if board.confidence else None
                ),
                updated_at=board.updated_at,
            )
        )

    async def open_gap(
        self, board_id: UUID, tenant_id: UUID, gap: KnowledgeGap
    ) -> None:
        await self._connection.execute(
            insert(board_gaps).values(
                gap_id=gap.gap_id,
                board_id=board_id,
                tenant_id=tenant_id,
                description=gap.description,
                priority=gap.priority.value,
                resolved=gap.resolved,
            )
        )

    async def resolve_gap(self, gap_id: UUID, tenant_id: UUID) -> None:
        await self._connection.execute(
            update(board_gaps)
            .where(board_gaps.c.gap_id == gap_id, board_gaps.c.tenant_id == tenant_id)
            .values(resolved=True)
        )

    async def record_fact(self, board_id: UUID, tenant_id: UUID, fact: Fact) -> None:
        await self._connection.execute(
            insert(board_facts).values(
                fact_id=fact.fact_id,
                board_id=board_id,
                tenant_id=tenant_id,
                metric=fact.metric,
                value=fact.value,
                period=fact.period,
                producing_work_item_id=fact.producing_work_item_id,
                evidence_refs=[ref.value for ref in fact.evidence_refs],
            )
        )

    async def open_conflict(
        self, board_id: UUID, tenant_id: UUID, conflict: Conflict
    ) -> None:
        await self._connection.execute(
            insert(board_conflicts).values(
                conflict_id=conflict.conflict_id,
                board_id=board_id,
                tenant_id=tenant_id,
                description=conflict.description,
                status=conflict.status.value,
                resolution=conflict.resolution,
            )
        )

    async def settle_conflict(self, tenant_id: UUID, conflict: Conflict) -> None:
        await self._connection.execute(
            update(board_conflicts)
            .where(
                board_conflicts.c.conflict_id == conflict.conflict_id,
                board_conflicts.c.tenant_id == tenant_id,
            )
            .values(status=conflict.status.value, resolution=conflict.resolution)
        )


def _work_item_from_row(row: Any) -> WorkItem:
    return WorkItem(
        work_item_id=row.work_item_id,
        investigation_id=row.investigation_id,
        tenant_id=row.tenant_id,
        role=AgentRole(row.role),
        objective=row.objective,
        status=WorkItemStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        parent_work_item_id=row.parent_work_item_id,
        depends_on=tuple(UUID(value) for value in row.depends_on),
        artifact_refs=tuple(
            EvidenceReference(value) for value in row.artifact_refs
        ),
        rejection_reason=row.rejection_reason,
    )


class PostgresWorkItemRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, item: WorkItem) -> None:
        await self._connection.execute(
            insert(work_items).values(
                work_item_id=item.work_item_id,
                tenant_id=item.tenant_id,
                investigation_id=item.investigation_id,
                role=item.role.value,
                objective=item.objective,
                status=item.status.value,
                parent_work_item_id=item.parent_work_item_id,
                depends_on=[str(value) for value in item.depends_on],
                artifact_refs=[ref.value for ref in item.artifact_refs],
                rejection_reason=item.rejection_reason,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    async def save(self, item: WorkItem) -> None:
        await self._connection.execute(
            update(work_items)
            .where(
                work_items.c.work_item_id == item.work_item_id,
                work_items.c.tenant_id == item.tenant_id,
            )
            .values(
                status=item.status.value,
                artifact_refs=[ref.value for ref in item.artifact_refs],
                rejection_reason=item.rejection_reason,
                updated_at=item.updated_at,
            )
        )

    async def list_for_investigation(
        self, investigation_id: UUID, tenant_id: UUID
    ) -> tuple[WorkItem, ...]:
        rows = (
            await self._connection.execute(
                select(work_items)
                .where(
                    work_items.c.investigation_id == investigation_id,
                    work_items.c.tenant_id == tenant_id,
                )
                .order_by(work_items.c.created_at)
            )
        ).all()
        return tuple(_work_item_from_row(row) for row in rows)


__all__ = [
    "PostgresInvestigationBoardRepository",
    "PostgresWorkItemRepository",
]
