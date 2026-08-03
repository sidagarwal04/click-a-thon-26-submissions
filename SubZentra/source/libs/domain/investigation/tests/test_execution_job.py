from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from zentra_domain_investigation import (
    ExecutionJob,
    ExecutionJobStatus,
    ExecutionJobTransitionError,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
JOB_ID = UUID("51000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("30000000-0000-0000-0000-000000000003")


def queued_job() -> ExecutionJob:
    return ExecutionJob.create(
        job_id=JOB_ID,
        tenant_id=TENANT_ID,
        investigation_id=INVESTIGATION_ID,
        now=NOW,
    )


def test_job_claim_renew_and_complete_preserve_one_lease_owner() -> None:
    job = queued_job()

    job.claim(worker_id="worker-a", now=NOW, lease_for=timedelta(seconds=60))
    job.renew(
        worker_id="worker-a",
        now=NOW + timedelta(seconds=20),
        lease_for=timedelta(seconds=60),
    )
    job.complete(worker_id="worker-a", now=NOW + timedelta(seconds=21))

    assert job.status is ExecutionJobStatus.COMPLETED
    assert job.attempts == 1
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.completed_at == NOW + timedelta(seconds=21)


def test_only_lease_owner_can_change_a_running_job() -> None:
    job = queued_job()
    job.claim(worker_id="worker-a", now=NOW, lease_for=timedelta(seconds=60))

    with pytest.raises(ExecutionJobTransitionError, match="lease owner"):
        job.complete(worker_id="worker-b", now=NOW + timedelta(seconds=1))


def test_transient_failure_is_bounded_and_terminal_failure_is_sanitized() -> None:
    job = queued_job()
    job.claim(worker_id="worker-a", now=NOW, lease_for=timedelta(seconds=60))
    job.retry(
        worker_id="worker-a",
        now=NOW + timedelta(seconds=1),
        available_at=NOW + timedelta(seconds=2),
        failure_category="provider_rate_limited",
    )

    assert job.status is ExecutionJobStatus.QUEUED
    assert job.available_at == NOW + timedelta(seconds=2)
    assert job.failure_category == "provider_rate_limited"

    job.claim(
        worker_id="worker-b",
        now=NOW + timedelta(seconds=2),
        lease_for=timedelta(seconds=60),
    )
    job.fail(
        worker_id="worker-b",
        now=NOW + timedelta(seconds=3),
        failure_category="domain_failure",
    )

    assert job.status is ExecutionJobStatus.FAILED
    assert job.failure_category == "domain_failure"
    assert job.attempts == 2


def test_expired_lease_can_be_reclaimed_but_live_lease_cannot() -> None:
    job = queued_job()
    job.claim(worker_id="worker-a", now=NOW, lease_for=timedelta(seconds=60))

    with pytest.raises(ExecutionJobTransitionError, match="active lease"):
        job.claim(
            worker_id="worker-b",
            now=NOW + timedelta(seconds=59),
            lease_for=timedelta(seconds=60),
        )

    job.claim(
        worker_id="worker-b",
        now=NOW + timedelta(seconds=60),
        lease_for=timedelta(seconds=60),
    )

    assert job.lease_owner == "worker-b"
    assert job.attempts == 1


def test_queued_cancellation_is_immediate_and_idempotent() -> None:
    job = queued_job()
    actor_id = uuid4()

    job.request_cancel(actor_id=actor_id, now=NOW)
    job.request_cancel(actor_id=uuid4(), now=NOW + timedelta(seconds=1))

    assert job.status is ExecutionJobStatus.CANCELLED
    assert job.cancel_requested_by == actor_id
    assert job.completed_at == NOW


def test_running_cancellation_waits_for_worker_checkpoint() -> None:
    job = queued_job()
    job.claim(worker_id="worker-a", now=NOW, lease_for=timedelta(seconds=30))
    job.request_cancel(actor_id=uuid4(), now=NOW + timedelta(seconds=1))

    assert job.status is ExecutionJobStatus.LEASED
    job.cancel(worker_id="worker-a", now=NOW + timedelta(seconds=2))
    assert job.status is ExecutionJobStatus.CANCELLED
