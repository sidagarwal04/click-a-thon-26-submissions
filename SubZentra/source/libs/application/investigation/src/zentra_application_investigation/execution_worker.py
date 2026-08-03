from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from zentra_domain_investigation import (
    ExecutionJob,
    ExecutionJobKind,
    ExecutionJobStatus,
)

from .ports import InvestigationUnitOfWorkFactory

SYSTEM_TRACE_ID = UUID(int=0)
SYSTEM_SPAN_ID = UUID(int=0)

_log = logging.getLogger(__name__)


class DurableInvestigationExecutor(Protocol):
    async def execute_job(self, *, tenant_id: UUID, investigation_id: UUID) -> None: ...

    async def fail_job(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
        failure_category: str,
    ) -> None: ...

    async def cancel_job(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
    ) -> None: ...


class DurableVisualizationExecutor(Protocol):
    async def execute_visualization_job(
        self, *, tenant_id: UUID, visualization_id: UUID
    ) -> None: ...

    async def fail_visualization_job(
        self,
        *,
        tenant_id: UUID,
        visualization_id: UUID,
        failure_category: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    category: str
    transient: bool


def classify_execution_failure(error: Exception) -> ExecutionFailure:
    safe_category = getattr(error, "category", None)
    transient = getattr(error, "transient", None)
    if isinstance(safe_category, str) and isinstance(transient, bool):
        return ExecutionFailure(safe_category, transient)
    name = type(error).__name__.lower()
    if isinstance(error, (TimeoutError, ConnectionError)):
        return ExecutionFailure("network_error", True)
    if "ratelimit" in name or "rate_limit" in name:
        return ExecutionFailure("provider_rate_limited", True)
    if "unavailable" in name or "connection" in name or "timeout" in name:
        return ExecutionFailure("dependency_unavailable", True)
    if isinstance(error, (ValueError, TypeError, AssertionError)):
        return ExecutionFailure("domain_failure", False)
    return ExecutionFailure("unexpected", False)


class ExecutionJobWorker:
    """Claims one durable job at a time and advances it outside HTTP requests."""

    def __init__(
        self,
        *,
        unit_of_work_factory: InvestigationUnitOfWorkFactory,
        executor: DurableInvestigationExecutor,
        visualization_executor: DurableVisualizationExecutor | None = None,
        worker_id: str,
        now: Callable[[], datetime],
        lease_for: timedelta = timedelta(seconds=60),
        renew_every: timedelta = timedelta(seconds=20),
        poll_every: float = 0.5,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("Execution worker ID is required")
        self._unit_of_work_factory = unit_of_work_factory
        self._executor = executor
        self._visualization_executor = visualization_executor
        self._worker_id = worker_id
        self._now = now
        self._lease_for = lease_for
        self._renew_every = renew_every
        self._poll_every = poll_every
        self._stop = asyncio.Event()

    async def run_once(self) -> bool:
        for tenant_id in await self._unit_of_work_factory.bound_tenant_ids():
            job = await self._claim(tenant_id)
            if job is None:
                continue
            await self._execute(tenant_id, job)
            return True
        return False

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            worked = await self.run_once()
            if not worked:
                await asyncio.sleep(self._poll_every)

    def stop(self) -> None:
        self._stop.set()

    async def _claim(self, tenant_id: UUID) -> ExecutionJob | None:
        async with self._uow(tenant_id) as unit_of_work:
            job = await unit_of_work.jobs.claim_next(
                worker_id=self._worker_id,
                now=self._now(),
                lease_for=self._lease_for,
            )
            if job is not None:
                await unit_of_work.commit()
            return job

    async def _execute(self, tenant_id: UUID, job: ExecutionJob) -> None:
        if await self._cancellation_requested(tenant_id, job.job_id):
            await self._cancel(tenant_id, job.job_id)
            return
        renewal = asyncio.create_task(self._renew(tenant_id, job.job_id))
        try:
            if job.job_kind is ExecutionJobKind.VISUALIZATION:
                if self._visualization_executor is None or job.visualization_id is None:
                    raise RuntimeError("Visualization executor is unavailable")
                await self._visualization_executor.execute_visualization_job(
                    tenant_id=tenant_id,
                    visualization_id=job.visualization_id,
                )
            else:
                await self._executor.execute_job(
                    tenant_id=tenant_id,
                    investigation_id=job.investigation_id,
                )
        except Exception as error:
            if await self._cancellation_requested(tenant_id, job.job_id):
                await self._cancel(tenant_id, job.job_id)
            else:
                failure = classify_execution_failure(error)
                # The stored `failure_category` is a safe, public vocabulary —
                # deliberately so, since it reaches the Work Feed. That leaves
                # nowhere for the operator to read what actually broke, so it
                # goes to the server log, which is not a tenant-facing surface.
                _log.exception(
                    "Execution job %s (%s) failed: %s",
                    job.job_id,
                    job.job_kind.value,
                    failure.category,
                    exc_info=error,
                )
                await self._record_failure(tenant_id, job.job_id, failure)
        else:
            if await self._cancellation_requested(tenant_id, job.job_id):
                await self._cancel(tenant_id, job.job_id)
            else:
                await self._complete(tenant_id, job.job_id)
        finally:
            renewal.cancel()
            with suppress(asyncio.CancelledError):
                await renewal

    async def _cancellation_requested(self, tenant_id: UUID, job_id: UUID) -> bool:
        async with self._uow(tenant_id) as unit_of_work:
            job = await unit_of_work.jobs.get_job(job_id)
            return job is not None and job.cancel_requested_at is not None

    async def _cancel(self, tenant_id: UUID, job_id: UUID) -> None:
        cancelled: ExecutionJob | None = None
        async with self._uow(tenant_id) as unit_of_work:
            job = await unit_of_work.jobs.get_job(job_id, for_update=True)
            if job is None or job.status is not ExecutionJobStatus.LEASED:
                return
            job.cancel(worker_id=self._worker_id, now=self._now())
            await unit_of_work.jobs.save_job(job)
            await unit_of_work.commit()
            cancelled = job
        await self._executor.cancel_job(
            tenant_id=tenant_id,
            investigation_id=cancelled.investigation_id,
        )

    async def _complete(self, tenant_id: UUID, job_id: UUID) -> None:
        async with self._uow(tenant_id) as unit_of_work:
            job = await unit_of_work.jobs.get_job(job_id, for_update=True)
            if job is None:
                return
            job.complete(worker_id=self._worker_id, now=self._now())
            await unit_of_work.jobs.save_job(job)
            await unit_of_work.commit()

    async def _record_failure(
        self, tenant_id: UUID, job_id: UUID, failure: ExecutionFailure
    ) -> None:
        terminal: ExecutionJob | None = None
        async with self._uow(tenant_id) as unit_of_work:
            job = await unit_of_work.jobs.get_job(job_id, for_update=True)
            if job is None:
                return
            now = self._now()
            if failure.transient and job.attempts < job.max_attempts:
                job.retry(
                    worker_id=self._worker_id,
                    now=now,
                    available_at=now + timedelta(seconds=2**job.attempts),
                    failure_category=failure.category,
                )
            else:
                job.fail(
                    worker_id=self._worker_id,
                    now=now,
                    failure_category=failure.category,
                )
                terminal = job
            await unit_of_work.jobs.save_job(job)
            await unit_of_work.commit()
        if terminal is not None:
            if (
                terminal.job_kind is ExecutionJobKind.VISUALIZATION
                and terminal.visualization_id is not None
                and self._visualization_executor is not None
            ):
                await self._visualization_executor.fail_visualization_job(
                    tenant_id=tenant_id,
                    visualization_id=terminal.visualization_id,
                    failure_category=failure.category,
                )
            else:
                await self._executor.fail_job(
                    tenant_id=tenant_id,
                    investigation_id=terminal.investigation_id,
                    failure_category=failure.category,
                )

    async def _renew(self, tenant_id: UUID, job_id: UUID) -> None:
        while True:
            await asyncio.sleep(self._renew_every.total_seconds())
            async with self._uow(tenant_id) as unit_of_work:
                job = await unit_of_work.jobs.get_job(job_id, for_update=True)
                if job is None or job.status is not ExecutionJobStatus.LEASED:
                    return
                job.renew(
                    worker_id=self._worker_id,
                    now=self._now(),
                    lease_for=self._lease_for,
                )
                await unit_of_work.jobs.save_job(job)
                await unit_of_work.commit()

    def _uow(self, tenant_id: UUID):
        return self._unit_of_work_factory(
            tenant_id,
            SYSTEM_TRACE_ID,
            SYSTEM_SPAN_ID,
        )
