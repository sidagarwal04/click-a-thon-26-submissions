from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_domain_investigation import (
    ExecutionJob,
    ExecutionJobKind,
    ExecutionJobStatus,
)

from .schema import execution_jobs


def _job_from_row(row: Any) -> ExecutionJob:
    return ExecutionJob(
        job_id=row.job_id,
        tenant_id=row.tenant_id,
        investigation_id=row.investigation_id,
        status=ExecutionJobStatus(row.status),
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        available_at=row.available_at,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        failure_category=row.failure_category,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        job_kind=ExecutionJobKind(row.job_kind),
        visualization_id=row.visualization_id,
        cancel_requested_at=row.cancel_requested_at,
        cancel_requested_by=row.cancel_requested_by,
    )


def _values(job: ExecutionJob) -> dict[str, object]:
    return {
        "status": job.status.value,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "available_at": job.available_at,
        "lease_owner": job.lease_owner,
        "lease_expires_at": job.lease_expires_at,
        "failure_category": job.failure_category,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
        "job_kind": job.job_kind.value,
        "visualization_id": job.visualization_id,
        "cancel_requested_at": job.cancel_requested_at,
        "cancel_requested_by": job.cancel_requested_by,
    }


class PostgresExecutionJobRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add_job(self, job: ExecutionJob) -> None:
        await self._connection.execute(
            insert(execution_jobs).values(
                job_id=job.job_id,
                tenant_id=job.tenant_id,
                investigation_id=job.investigation_id,
                created_at=job.created_at,
                **_values(job),
            )
        )

    async def claim_next(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_for: timedelta,
    ) -> ExecutionJob | None:
        statement = (
            select(execution_jobs)
            .where(
                or_(
                    and_(
                        execution_jobs.c.status == ExecutionJobStatus.QUEUED.value,
                        execution_jobs.c.attempts < execution_jobs.c.max_attempts,
                        execution_jobs.c.available_at <= now,
                        execution_jobs.c.cancel_requested_at.is_(None),
                    ),
                    and_(
                        execution_jobs.c.status == ExecutionJobStatus.LEASED.value,
                        execution_jobs.c.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(
                execution_jobs.c.available_at,
                execution_jobs.c.created_at,
                execution_jobs.c.job_id,
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = (await self._connection.execute(statement)).one_or_none()
        if row is None:
            return None
        job = _job_from_row(row)
        job.claim(worker_id=worker_id, now=now, lease_for=lease_for)
        await self.save_job(job)
        return job

    async def get_job(
        self, job_id: UUID, *, for_update: bool = False
    ) -> ExecutionJob | None:
        statement = select(execution_jobs).where(execution_jobs.c.job_id == job_id)
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).one_or_none()
        return _job_from_row(row) if row is not None else None

    async def get_for_investigation(
        self,
        investigation_id: UUID,
        *,
        for_update: bool = False,
    ) -> ExecutionJob | None:
        statement = select(execution_jobs).where(
            execution_jobs.c.investigation_id == investigation_id,
            execution_jobs.c.job_kind == ExecutionJobKind.INVESTIGATION.value,
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).one_or_none()
        return _job_from_row(row) if row is not None else None

    async def save_job(self, job: ExecutionJob) -> None:
        await self._connection.execute(
            update(execution_jobs)
            .where(execution_jobs.c.job_id == job.job_id)
            .values(**_values(job))
        )
