from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_application_investigation import (
    AuthenticatedActor,
    InvestigationNotFoundError,
    InvestigationService,
    PipelineResult,
    Role,
)
from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    ApprovalDecision,
    EvidenceReference,
    Finding,
    InvestigationStatus,
    MetricComparison,
)

from zentra_adapter_postgres import (
    Database,
    PostgresInvestigationUnitOfWorkFactory,
)
from zentra_adapter_postgres.database import set_tenant_context
from zentra_adapter_postgres.schema import (
    agent_executions,
    audit_outbox,
    tenant_memberships,
    tenants,
    users,
)

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)


class Pipeline:
    async def run(self, **kwargs: object) -> PipelineResult:
        return PipelineResult(
            finding=Finding(
                headline="EU refunds rose $240 in July",
                summary="Governed evidence requires Human Approval.",
                metrics=(
                    MetricComparison(
                        "refund_amount",
                        "20.00",
                        "260.00",
                        "USD",
                    ),
                ),
                evidence_refs=(EvidenceReference("artifact://integration/eu"),),
            ),
            outcome=ConfidenceOutcome(
                score=0.42,
                calibration_method="evaluator_independent_recheck",
            ),
            converged=True,
        )


class PendingAudit:
    async def flush(self, **kwargs: object) -> bool:
        return False

    async def list_timeline(self, **kwargs: object) -> tuple[()]:
        return ()


@pytest.mark.asyncio
async def test_transactional_lifecycle_outbox_rls_and_idempotent_approval() -> None:
    assert OWNER_URL is not None
    assert RUNTIME_URL is not None
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    user_id = uuid4()
    owner = create_async_engine(OWNER_URL)
    async with owner.begin() as connection:
        await connection.execute(
            insert(tenants),
            [
                {"tenant_id": tenant_id, "name": "Phase 1A Tenant"},
                {"tenant_id": other_tenant_id, "name": "Other Tenant"},
            ],
        )
        await connection.execute(
            insert(users).values(
                user_id=user_id,
                email=f"{user_id}@example.test",
            )
        )
        await connection.execute(
            insert(tenant_memberships).values(
                tenant_id=tenant_id,
                user_id=user_id,
                role="owner",
            )
        )
    await owner.dispose()

    database = Database(RUNTIME_URL)
    service = InvestigationService(
        unit_of_work_factory=PostgresInvestigationUnitOfWorkFactory(database),
        pipeline=Pipeline(),
        audit_writer=PendingAudit(),
        audit_reader=PendingAudit(),
        now=lambda: datetime.now(UTC),
        new_id=uuid4,
    )
    actor = AuthenticatedActor(
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.OWNER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )

    started = await service.start(
        actor, question="Why did EU refunds increase from June to July 2026?"
    )
    assert started.status is InvestigationStatus.RUNNING
    # An undeliverable ledger is surfaced, never silently treated as written.
    assert started.audit_delivery.value == "pending"

    await service.execute(actor, started.investigation_id)
    started = await service.get(actor, started.investigation_id)

    assert started.status is InvestigationStatus.AWAITING_APPROVAL
    assert started.pending_approval is not None
    assert started.pending_approval.reason == "low_confidence"

    runtime = create_async_engine(RUNTIME_URL)
    async with runtime.begin() as connection:
        await set_tenant_context(connection, tenant_id)
        outbox_count = await connection.scalar(
            select(func.count()).select_from(audit_outbox)
        )
        agent_execution_count = await connection.scalar(
            select(func.count()).select_from(agent_executions)
        )
    assert outbox_count == 5
    # This pipeline stub reports a result without running agents, so no
    # execution rows are written. The graph writes one per step.
    assert agent_execution_count == 0

    completed = await service.decide(
        actor,
        investigation_id=started.investigation_id,
        approval_id=started.pending_approval.approval_id,
        decision=ApprovalDecision.APPROVE,
        rejection_reason=None,
    )
    repeated = await service.decide(
        actor,
        investigation_id=started.investigation_id,
        approval_id=started.pending_approval.approval_id,
        decision=ApprovalDecision.APPROVE,
        rejection_reason=None,
    )
    assert completed.status is InvestigationStatus.COMPLETED
    assert repeated.status is InvestigationStatus.COMPLETED
    assert repeated.version == completed.version

    invisible_actor = AuthenticatedActor(
        user_id=user_id,
        tenant_id=other_tenant_id,
        role=Role.OWNER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )
    with pytest.raises(InvestigationNotFoundError):
        await service.get(invisible_actor, started.investigation_id)

    async with runtime.begin() as connection:
        await set_tenant_context(connection, other_tenant_id)
        visible_outbox = await connection.scalar(
            select(func.count()).select_from(audit_outbox)
        )
    assert visible_outbox == 0
    await runtime.dispose()
    await database.close()
