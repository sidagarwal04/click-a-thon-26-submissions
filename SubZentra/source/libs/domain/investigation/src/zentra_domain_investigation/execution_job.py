from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class ExecutionJobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionJobKind(StrEnum):
    INVESTIGATION = "investigation"
    VISUALIZATION = "visualization"


TERMINAL_JOB_STATUSES = frozenset(
    {
        ExecutionJobStatus.COMPLETED,
        ExecutionJobStatus.FAILED,
        ExecutionJobStatus.CANCELLED,
    }
)


class ExecutionJobTransitionError(RuntimeError):
    pass


@dataclass(slots=True)
class ExecutionJob:
    """A durable request to execute one Investigation pipeline."""

    job_id: UUID
    tenant_id: UUID
    investigation_id: UUID
    status: ExecutionJobStatus
    attempts: int
    max_attempts: int
    available_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    failure_category: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    job_kind: ExecutionJobKind = ExecutionJobKind.INVESTIGATION
    visualization_id: UUID | None = None
    cancel_requested_at: datetime | None = None
    cancel_requested_by: UUID | None = None

    @classmethod
    def create(
        cls,
        *,
        job_id: UUID,
        tenant_id: UUID,
        investigation_id: UUID,
        now: datetime,
        max_attempts: int = 3,
        job_kind: ExecutionJobKind = ExecutionJobKind.INVESTIGATION,
        visualization_id: UUID | None = None,
    ) -> ExecutionJob:
        if max_attempts < 1:
            raise ValueError("Execution Job max attempts must be positive")
        if (job_kind is ExecutionJobKind.VISUALIZATION) != (
            visualization_id is not None
        ):
            raise ValueError("Execution Job target does not match its kind")
        return cls(
            job_id=job_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            status=ExecutionJobStatus.QUEUED,
            attempts=0,
            max_attempts=max_attempts,
            available_at=now,
            lease_owner=None,
            lease_expires_at=None,
            failure_category=None,
            created_at=now,
            updated_at=now,
            job_kind=job_kind,
            visualization_id=visualization_id,
        )

    def request_cancel(self, *, actor_id: UUID, now: datetime) -> None:
        if self.status in TERMINAL_JOB_STATUSES:
            return
        self.cancel_requested_at = self.cancel_requested_at or now
        self.cancel_requested_by = self.cancel_requested_by or actor_id
        self.updated_at = now
        if self.status is ExecutionJobStatus.QUEUED:
            self.status = ExecutionJobStatus.CANCELLED
            self.completed_at = now

    def cancel(self, *, worker_id: str, now: datetime) -> None:
        self._require_lease_owner(worker_id)
        if self.cancel_requested_at is None:
            raise ExecutionJobTransitionError("Cancellation was not requested")
        self.status = ExecutionJobStatus.CANCELLED
        self.lease_owner = None
        self.lease_expires_at = None
        self.completed_at = now
        self.updated_at = now

    def claim(self, *, worker_id: str, now: datetime, lease_for: timedelta) -> None:
        if not worker_id.strip():
            raise ValueError("Execution Job worker ID is required")
        if lease_for <= timedelta(0):
            raise ValueError("Execution Job lease must be positive")
        if self.status in TERMINAL_JOB_STATUSES:
            raise ExecutionJobTransitionError("A terminal job cannot be claimed")
        if self.status is ExecutionJobStatus.QUEUED and self.available_at > now:
            raise ExecutionJobTransitionError("Execution Job is not available yet")
        if (
            self.status is ExecutionJobStatus.LEASED
            and self.lease_expires_at is not None
            and self.lease_expires_at > now
        ):
            raise ExecutionJobTransitionError("Execution Job has an active lease")
        if (
            self.status is ExecutionJobStatus.QUEUED
            and self.attempts >= self.max_attempts
        ):
            raise ExecutionJobTransitionError("Execution Job attempts are exhausted")
        starting_attempt = self.status is ExecutionJobStatus.QUEUED
        self.status = ExecutionJobStatus.LEASED
        # An expired lease resumes the same persisted LangGraph attempt. Only a
        # queued retry consumes another bounded analytical attempt.
        if starting_attempt:
            self.attempts += 1
        self.lease_owner = worker_id
        self.lease_expires_at = now + lease_for
        self.updated_at = now

    def renew(self, *, worker_id: str, now: datetime, lease_for: timedelta) -> None:
        self._require_lease_owner(worker_id)
        if lease_for <= timedelta(0):
            raise ValueError("Execution Job lease must be positive")
        if self.lease_expires_at is not None and self.lease_expires_at <= now:
            raise ExecutionJobTransitionError("Execution Job lease has expired")
        self.lease_expires_at = now + lease_for
        self.updated_at = now

    def retry(
        self,
        *,
        worker_id: str,
        now: datetime,
        available_at: datetime,
        failure_category: str,
    ) -> None:
        self._require_lease_owner(worker_id)
        if self.attempts >= self.max_attempts:
            raise ExecutionJobTransitionError("Execution Job attempts are exhausted")
        if available_at < now:
            raise ValueError("Execution Job retry cannot be scheduled in the past")
        self.status = ExecutionJobStatus.QUEUED
        self.available_at = available_at
        self.failure_category = _failure_category(failure_category)
        self.lease_owner = None
        self.lease_expires_at = None
        self.updated_at = now

    def complete(self, *, worker_id: str, now: datetime) -> None:
        self._require_lease_owner(worker_id)
        self.status = ExecutionJobStatus.COMPLETED
        self.failure_category = None
        self.lease_owner = None
        self.lease_expires_at = None
        self.completed_at = now
        self.updated_at = now

    def fail(self, *, worker_id: str, now: datetime, failure_category: str) -> None:
        self._require_lease_owner(worker_id)
        self.status = ExecutionJobStatus.FAILED
        self.failure_category = _failure_category(failure_category)
        self.lease_owner = None
        self.lease_expires_at = None
        self.completed_at = now
        self.updated_at = now

    def _require_lease_owner(self, worker_id: str) -> None:
        if (
            self.status is not ExecutionJobStatus.LEASED
            or self.lease_owner != worker_id
        ):
            raise ExecutionJobTransitionError(
                "Only the current lease owner can change a leased job"
            )


def _failure_category(value: str) -> str:
    category = value.strip()
    if not category or len(category) > 64:
        raise ValueError("Execution Job failure category is invalid")
    return category
