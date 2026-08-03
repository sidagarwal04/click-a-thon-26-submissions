from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from zentra_domain_investigation import ExecutionJob, ExecutionJobStatus

from zentra_application_investigation import ExecutionJobWorker

NOW = datetime(2026, 8, 1, tzinfo=UTC)
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("30000000-0000-0000-0000-000000000003")
JOB_ID = UUID("51000000-0000-0000-0000-000000000001")


class Jobs:
    def __init__(self, job: ExecutionJob) -> None:
        self.job = job

    async def claim_next(
        self, *, worker_id: str, now: datetime, lease_for: timedelta
    ) -> ExecutionJob | None:
        if self.job.status is ExecutionJobStatus.QUEUED:
            self.job.claim(worker_id=worker_id, now=now, lease_for=lease_for)
            return self.job
        return None

    async def get_job(
        self, job_id: UUID, *, for_update: bool = False
    ) -> ExecutionJob | None:
        return self.job if self.job.job_id == job_id else None

    async def save_job(self, job: ExecutionJob) -> None:
        self.job = job


class UnitOfWork:
    def __init__(self, jobs: Jobs) -> None:
        self.jobs = jobs
        self.commits = 0

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class Factory:
    def __init__(self, job: ExecutionJob) -> None:
        self.uow = UnitOfWork(Jobs(job))

    async def bound_tenant_ids(self) -> tuple[UUID, ...]:
        return (TENANT_ID,)

    def __call__(
        self, tenant_id: UUID, trace_id: UUID, span_id: UUID
    ) -> AbstractAsyncContextManager[UnitOfWork]:
        assert tenant_id == TENANT_ID
        return self.uow


class Executor:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[UUID] = []
        self.failures: list[str] = []

    async def execute_job(self, *, tenant_id: UUID, investigation_id: UUID) -> None:
        self.calls.append(investigation_id)
        if self.error is not None:
            raise self.error

    async def fail_job(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
        failure_category: str,
    ) -> None:
        self.failures.append(failure_category)


def job() -> ExecutionJob:
    return ExecutionJob.create(
        job_id=JOB_ID,
        tenant_id=TENANT_ID,
        investigation_id=INVESTIGATION_ID,
        now=NOW,
    )


@pytest.mark.asyncio
async def test_worker_claims_executes_and_completes_one_job() -> None:
    factory = Factory(job())
    executor = Executor()
    worker = ExecutionJobWorker(
        unit_of_work_factory=factory,
        executor=executor,
        worker_id="worker-a",
        now=lambda: NOW,
    )

    worked = await worker.run_once()

    assert worked is True
    assert executor.calls == [INVESTIGATION_ID]
    assert factory.uow.jobs.job.status is ExecutionJobStatus.COMPLETED


@pytest.mark.asyncio
async def test_worker_requeues_only_transient_failures_with_bounded_backoff() -> None:
    factory = Factory(job())
    executor = Executor(TimeoutError("private provider detail"))
    worker = ExecutionJobWorker(
        unit_of_work_factory=factory,
        executor=executor,
        worker_id="worker-a",
        now=lambda: NOW,
    )

    await worker.run_once()

    queued = factory.uow.jobs.job
    assert queued.status is ExecutionJobStatus.QUEUED
    assert queued.failure_category == "network_error"
    assert queued.available_at == NOW + timedelta(seconds=2)
    assert executor.failures == []


@pytest.mark.asyncio
async def test_worker_fails_domain_errors_without_retrying_or_leaking_message() -> None:
    factory = Factory(job())
    executor = Executor(ValueError("customer secret in validation message"))
    worker = ExecutionJobWorker(
        unit_of_work_factory=factory,
        executor=executor,
        worker_id="worker-a",
        now=lambda: NOW,
    )

    await worker.run_once()

    failed = factory.uow.jobs.job
    assert failed.status is ExecutionJobStatus.FAILED
    assert failed.failure_category == "domain_failure"
    assert executor.failures == ["domain_failure"]
    assert "customer secret" not in repr(failed)
