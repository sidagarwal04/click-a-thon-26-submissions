from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_application_investigation import (
    AuthenticatedActor,
    InvestigationService,
    Role,
)
from zentra_domain_investigation import ExecutionJob, ExecutionJobStatus

from zentra_adapter_postgres import (
    Database,
    PostgresInvestigationUnitOfWorkFactory,
)
from zentra_adapter_postgres.schema import execution_jobs, tenants

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)


class UnusedPipeline:
    async def run(self, **kwargs: object) -> None:
        raise AssertionError("HTTP creation must not execute the pipeline")


class PendingAudit:
    async def flush(self, **kwargs: object) -> bool:
        return False

    async def list_timeline(self, **kwargs: object) -> tuple[()]:
        return ()


async def _claim(
    factory: PostgresInvestigationUnitOfWorkFactory,
    tenant_id: UUID,
    *,
    worker_id: str,
    now: datetime,
) -> ExecutionJob | None:
    async with factory(tenant_id, UUID(int=0), UUID(int=0)) as unit_of_work:
        job = await unit_of_work.jobs.claim_next(
            worker_id=worker_id,
            now=now,
            lease_for=timedelta(seconds=60),
        )
        if job is not None:
            await unit_of_work.commit()
        return job


@pytest.mark.asyncio
async def test_competing_workers_claim_once_and_an_expired_lease_is_recovered() -> None:
    assert OWNER_URL is not None
    assert RUNTIME_URL is not None
    tenant_id = uuid4()
    owner_engine = create_async_engine(OWNER_URL)
    async with owner_engine.begin() as connection:
        await connection.execute(
            insert(tenants).values(tenant_id=tenant_id, name="Job Tenant")
        )

    database = Database(RUNTIME_URL)
    factory = PostgresInvestigationUnitOfWorkFactory(database)
    service = InvestigationService(
        unit_of_work_factory=factory,
        pipeline=UnusedPipeline(),
        audit_writer=PendingAudit(),
        audit_reader=PendingAudit(),
        now=lambda: datetime.now(UTC),
        new_id=uuid4,
    )
    actor = AuthenticatedActor(
        user_id=uuid4(),
        tenant_id=tenant_id,
        role=Role.MEMBER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )
    started = await service.start(
        actor, question="Why did EU refunds increase from June to July 2026?"
    )
    claimed_at = datetime.now(UTC)

    first, second = await asyncio.gather(
        _claim(factory, tenant_id, worker_id="worker-a", now=claimed_at),
        _claim(factory, tenant_id, worker_id="worker-b", now=claimed_at),
    )

    claimed = [job for job in (first, second) if job is not None]
    assert len(claimed) == 1
    assert claimed[0].investigation_id == started.investigation_id
    assert claimed[0].attempts == 1

    async with owner_engine.begin() as connection:
        await connection.execute(
            update(execution_jobs)
            .where(execution_jobs.c.job_id == claimed[0].job_id)
            .values(lease_expires_at=claimed_at - timedelta(seconds=1))
        )

    recovered = await _claim(
        factory,
        tenant_id,
        worker_id="worker-recovery",
        now=claimed_at,
    )

    assert recovered is not None
    assert recovered.status is ExecutionJobStatus.LEASED
    assert recovered.lease_owner == "worker-recovery"
    assert recovered.attempts == 1

    await database.close()
    async with owner_engine.begin() as connection:
        await connection.execute(
            delete(tenants).where(tenants.c.tenant_id == tenant_id)
        )
    await owner_engine.dispose()
