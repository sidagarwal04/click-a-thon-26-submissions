from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import delete, insert, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_application_investigation import (
    ThreadCursor,
    ThreadSlice,
    ThreadSummary,
)
from zentra_domain_investigation import (
    InvestigationThread,
    ThreadMessage,
    ThreadMessageKind,
    ThreadStatus,
)

from .database import Database, set_tenant_context
from .draft_finding import (
    PostgresDraftFindingRepository,
    PostgresEvidenceCitationRepository,
)
from .execution_job import PostgresExecutionJobRepository
from .investigation import (
    PostgresAgentExecutionRepository,
    PostgresAuditOutboxRepository,
    PostgresHumanApprovalRepository,
    PostgresInvestigationRepository,
)
from .schema import investigation_threads, investigations, thread_messages
from .work_feed import PostgresWorkFeedRepository
from .workspace import PostgresOrganizationRepository


def _thread_from_row(row: Any) -> InvestigationThread:
    value = row._mapping
    return InvestigationThread(
        thread_id=value["thread_id"],
        tenant_id=value["tenant_id"],
        project_id=value["project_id"],
        initiating_message_id=value["initiating_message_id"],
        title=value["title"],
        status=ThreadStatus(value["status"]),
        archived_from_status=(
            ThreadStatus(value["archived_from_status"])
            if value["archived_from_status"]
            else None
        ),
        created_at=value["created_at"],
        updated_at=value["updated_at"],
        latest_activity_at=value["latest_activity_at"],
        archived_at=value["archived_at"],
    )


def _message_from_row(row: Any) -> ThreadMessage:
    value = row._mapping
    return ThreadMessage(
        message_id=value["message_id"],
        thread_id=value["thread_id"],
        tenant_id=value["tenant_id"],
        author_id=value["author_id"],
        kind=ThreadMessageKind(value["kind"]),
        content=value["content"],
        created_at=value["created_at"],
    )


class PostgresThreadRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add_thread(self, thread: InvestigationThread) -> None:
        await self._connection.execute(
            insert(investigation_threads).values(
                thread_id=thread.thread_id,
                tenant_id=thread.tenant_id,
                project_id=thread.project_id,
                initiating_message_id=thread.initiating_message_id,
                title=thread.title,
                status=thread.status.value,
                archived_from_status=None,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
                latest_activity_at=thread.latest_activity_at,
                archived_at=thread.archived_at,
            )
        )

    async def get_thread(
        self, thread_id: UUID, *, for_update: bool = False
    ) -> InvestigationThread | None:
        statement = select(investigation_threads).where(
            investigation_threads.c.thread_id == thread_id
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).first()
        return _thread_from_row(row) if row else None

    async def save_thread(self, thread: InvestigationThread) -> None:
        await self._connection.execute(
            update(investigation_threads)
            .where(investigation_threads.c.thread_id == thread.thread_id)
            .values(
                title=thread.title,
                status=thread.status.value,
                archived_from_status=(
                    thread.archived_from_status.value
                    if thread.archived_from_status
                    else None
                ),
                updated_at=thread.updated_at,
                latest_activity_at=thread.latest_activity_at,
                archived_at=thread.archived_at,
            )
        )

    async def delete_thread(self, thread_id: UUID) -> None:
        await self._connection.execute(
            delete(investigation_threads).where(
                investigation_threads.c.thread_id == thread_id
            )
        )

    async def add_message(self, message: ThreadMessage) -> None:
        await self._connection.execute(
            insert(thread_messages).values(
                message_id=message.message_id,
                thread_id=message.thread_id,
                tenant_id=message.tenant_id,
                author_id=message.author_id,
                kind=message.kind.value,
                content=message.content,
                created_at=message.created_at,
            )
        )

    async def messages_for_thread(self, thread_id: UUID) -> tuple[ThreadMessage, ...]:
        statement = (
            select(thread_messages)
            .where(thread_messages.c.thread_id == thread_id)
            .order_by(
                thread_messages.c.created_at,
                thread_messages.c.message_id,
            )
        )
        rows = (await self._connection.execute(statement)).all()
        return tuple(_message_from_row(row) for row in rows)

    async def list_threads(
        self,
        *,
        project_id: UUID,
        include_archived: bool,
        limit: int,
        after: ThreadCursor | None,
    ) -> ThreadSlice:
        latest_investigation = (
            select(investigations.c.investigation_id)
            .where(investigations.c.thread_id == investigation_threads.c.thread_id)
            .order_by(investigations.c.thread_sequence.desc())
            .limit(1)
            .scalar_subquery()
        )
        statement = select(
            investigation_threads,
            latest_investigation.label("investigation_id"),
        ).where(
            investigation_threads.c.project_id == project_id,
        )
        if not include_archived:
            statement = statement.where(
                investigation_threads.c.status != ThreadStatus.ARCHIVED.value
            )
        if after is not None:
            statement = statement.where(
                tuple_(
                    investigation_threads.c.latest_activity_at,
                    investigation_threads.c.thread_id,
                )
                < tuple_(after.activity_at, after.thread_id)
            )
        statement = statement.order_by(
            investigation_threads.c.latest_activity_at.desc(),
            investigation_threads.c.thread_id.desc(),
        ).limit(limit + 1)
        rows = (await self._connection.execute(statement)).all()
        summaries = tuple(
            ThreadSummary(
                thread_id=row.thread_id,
                project_id=row.project_id,
                title=row.title,
                status=ThreadStatus(row.status),
                latest_activity_at=row.latest_activity_at,
                investigation_id=row.investigation_id,
            )
            for row in rows
        )
        if len(summaries) <= limit:
            return ThreadSlice(summaries, None)
        visible = summaries[:limit]
        last = visible[-1]
        return ThreadSlice(
            visible,
            ThreadCursor(last.latest_activity_at, last.thread_id),
        )

    async def investigation_id_for_thread(self, thread_id: UUID) -> UUID | None:
        statement = (
            select(investigations.c.investigation_id)
            .where(investigations.c.thread_id == thread_id)
            .order_by(investigations.c.thread_sequence.desc())
            .limit(1)
        )
        return (await self._connection.execute(statement)).scalar_one_or_none()


class PostgresThreadUnitOfWork:
    def __init__(
        self, connection: AsyncConnection, *, trace_id: UUID, span_id: UUID
    ) -> None:
        self.threads = PostgresThreadRepository(connection)
        self.organization = PostgresOrganizationRepository(connection)
        self.investigations = PostgresInvestigationRepository(connection)
        self.jobs = PostgresExecutionJobRepository(connection)
        self.outbox = PostgresAuditOutboxRepository(
            connection, trace_id=trace_id, span_id=span_id
        )
        self.work_feed = PostgresWorkFeedRepository(connection)
        self.approvals = PostgresHumanApprovalRepository(connection)
        self.agent_executions = PostgresAgentExecutionRepository(connection)
        self.draft_findings = PostgresDraftFindingRepository(connection)
        self.citations = PostgresEvidenceCitationRepository(connection)
        self.should_commit = False

    async def commit(self) -> None:
        self.should_commit = True


class PostgresThreadUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def __call__(
        self,
        tenant_id: UUID,
        trace_id: UUID,
        span_id: UUID,
    ) -> AsyncIterator[PostgresThreadUnitOfWork]:
        async with self._database.engine.connect() as connection:
            await connection.execution_options(isolation_level="REPEATABLE READ")
            transaction = await connection.begin()
            await set_tenant_context(connection, tenant_id)
            unit_of_work = PostgresThreadUnitOfWork(
                connection, trace_id=trace_id, span_id=span_id
            )
            try:
                yield unit_of_work
            except Exception:
                await transaction.rollback()
                raise
            else:
                if unit_of_work.should_commit:
                    await transaction.commit()
                else:
                    await transaction.rollback()
