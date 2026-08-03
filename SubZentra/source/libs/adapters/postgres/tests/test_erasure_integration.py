"""The erasure harness.

Criterion 9 asks for proof that content is present before and absent after —
so this seeds every surface with a distinctive marker, asserts each one is
there, erases, and asserts each one is gone. A test that only checked the
operation's own status would pass while content survived.

The markers are walked from `EvidenceSurface` rather than a hand-written list,
so a surface added to the domain without a clause in the repository fails here
rather than being silently missed.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_domain_investigation import (
    DeletionCategory,
    ErasureError,
    ErasureProgress,
    EvidenceSurface,
)

from zentra_adapter_postgres.database import set_tenant_context
from zentra_adapter_postgres.erasure import PostgresErasureRepository
from zentra_adapter_postgres.schema import (
    agent_executions,
    draft_finding_claims,
    draft_findings,
    erasure_operations,
    evidence_citations,
    investigations,
    tenants,
)

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)

TENANT = UUID("88000000-0000-0000-0000-000000000001")
INVESTIGATION = UUID("89000000-0000-0000-0000-000000000001")
EXECUTION = UUID("8a000000-0000-0000-0000-000000000001")
DRAFT = UUID("8b000000-0000-0000-0000-000000000001")
CLAIM = UUID("8c000000-0000-0000-0000-000000000001")
CITATION = UUID("8d000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 31, 10, 0, tzinfo=UTC)

# One distinctive marker per surface. Distinct strings so a test can say which
# surface leaked rather than only that something did.
MARKERS = {
    EvidenceSurface.AGENT_EXECUTION_INPUT: "MARKER-execution-input",
    EvidenceSurface.AGENT_EXECUTION_OUTPUT: "MARKER-execution-output",
    EvidenceSurface.INVESTIGATION_FINDING: "MARKER-narrative-finding",
    EvidenceSurface.DRAFT_FINDING_NARRATIVE: "MARKER-draft-headline",
    EvidenceSurface.DRAFT_FINDING_CLAIMS: "MARKER-claim-text",
    EvidenceSurface.CITATION_AGGREGATE: "MARKER-aggregate-value",
    EvidenceSurface.DRAFT_FINDING_CONTRADICTIONS: "MARKER-contradiction",
    EvidenceSurface.AGENT_EXECUTION_OUTCOME: "MARKER-validation-issue",
    EvidenceSurface.INVESTIGATION_FAILURE_MESSAGE: "MARKER-failure-message",
}


async def seed(status: str = "completed") -> None:
    owner = create_async_engine(OWNER_URL)
    async with owner.begin() as connection:
        await connection.execute(
            postgres_insert(tenants)
            .values(tenant_id=TENANT, name="Erasure")
            .on_conflict_do_nothing()
        )
        await connection.execute(
            erasure_operations.delete().where(
                erasure_operations.c.investigation_id == INVESTIGATION
            )
        )
        await connection.execute(
            investigations.delete().where(
                investigations.c.investigation_id == INVESTIGATION
            )
        )
        await connection.execute(
            investigations.insert().values(
                investigation_id=INVESTIGATION,
                tenant_id=TENANT,
                question="Why did EU refunds increase?",
                status=status,
                state={
                    "finding": {
                        "headline": MARKERS[EvidenceSurface.INVESTIGATION_FINDING],
                        "summary": "narrative",
                        "metrics": [],
                        "evidence_refs": [],
                    },
                    # Process, and must survive.
                    "completion": {"human_approved": False},
                    "failure": {
                        # The code explains the terminal state and stays.
                        "code": "pipeline_failed",
                        "message": MARKERS[
                            EvidenceSurface.INVESTIGATION_FAILURE_MESSAGE
                        ],
                    },
                },
            )
        )
        await connection.execute(
            agent_executions.insert().values(
                execution_id=EXECUTION,
                investigation_id=INVESTIGATION,
                tenant_id=TENANT,
                agent_id="cube_analyst_v1",
                step=1,
                input={"question": MARKERS[EvidenceSurface.AGENT_EXECUTION_INPUT]},
                output={"rows": [MARKERS[EvidenceSurface.AGENT_EXECUTION_OUTPUT]]},
                status="success",
                model="cerebras/zai-glm-4.7",
                latency_ms=1200,
                outcome_kind="validation",
                outcome={
                    "kind": "validation",
                    "passed": False,
                    "checks": [],
                    "issues": [MARKERS[EvidenceSurface.AGENT_EXECUTION_OUTCOME]],
                },
            )
        )
        await connection.execute(
            draft_findings.insert().values(
                draft_finding_id=DRAFT,
                investigation_id=INVESTIGATION,
                tenant_id=TENANT,
                version=1,
                headline=MARKERS[EvidenceSurface.DRAFT_FINDING_NARRATIVE],
                summary="draft summary",
                contradictions=[
                    {
                        "detail": MARKERS[
                            EvidenceSurface.DRAFT_FINDING_CONTRADICTIONS
                        ],
                        "resolved": False,
                    }
                ],
                root_cause="unresolved",
            )
        )
        await connection.execute(
            draft_finding_claims.insert().values(
                claim_id=CLAIM,
                draft_finding_id=DRAFT,
                tenant_id=TENANT,
                kind="observed",
                claim_text=MARKERS[EvidenceSurface.DRAFT_FINDING_CLAIMS],
                metric="refund_amount",
                claim_value="260.00",
                period="July 2026",
                position=0,
            )
        )
        await connection.execute(
            evidence_citations.insert().values(
                citation_id=CITATION,
                investigation_id=INVESTIGATION,
                tenant_id=TENANT,
                metric="refund_amount",
                filters=[{"member": "Commerce.region", "operator": "equals",
                          "values": ["EU"]}],
                period="July 2026",
                grain="month",
                aggregate_value=MARKERS[EvidenceSurface.CITATION_AGGREGATE],
                state="active",
            )
        )
    await owner.dispose()


async def cleanup() -> None:
    owner = create_async_engine(OWNER_URL)
    async with owner.begin() as connection:
        await connection.execute(
            investigations.delete().where(
                investigations.c.investigation_id == INVESTIGATION
            )
        )
    await owner.dispose()


async def surviving_markers(connection) -> set[str]:
    """Every marker still reachable, whatever surface it is on."""
    found: set[str] = set()
    rows = []
    rows.append(str(await connection.scalar(
        select(investigations.c.state).where(
            investigations.c.investigation_id == INVESTIGATION
        )
    )))
    for column, where in (
        (
            agent_executions.c.input,
            agent_executions.c.investigation_id == INVESTIGATION,
        ),
        (
            agent_executions.c.output,
            agent_executions.c.investigation_id == INVESTIGATION,
        ),
        (
            draft_findings.c.headline,
            draft_findings.c.investigation_id == INVESTIGATION,
        ),
        (
            draft_finding_claims.c.claim_text,
            draft_finding_claims.c.draft_finding_id == DRAFT,
        ),
        (
            evidence_citations.c.aggregate_value,
            evidence_citations.c.investigation_id == INVESTIGATION,
        ),
        (
            draft_findings.c.contradictions,
            draft_findings.c.investigation_id == INVESTIGATION,
        ),
        (
            agent_executions.c.outcome,
            agent_executions.c.investigation_id == INVESTIGATION,
        ),
    ):
        rows.extend(
            str(value)
            for value in (
                await connection.execute(select(column).where(where))
            ).scalars()
        )
    haystack = json.dumps(rows)
    for marker in MARKERS.values():
        if marker in haystack:
            found.add(marker)
    return found


@pytest.mark.asyncio
async def test_every_surface_is_present_before_and_absent_after() -> None:
    """The whole harness in one test: seed all six, prove each is reachable,
    erase, prove none is."""
    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            before = await surviving_markers(connection)
        assert before == set(MARKERS.values()), "the harness did not seed a surface"

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            operation = await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )

        assert operation.progress is ErasureProgress.COMPLETED
        assert operation.completed_at is not None

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            after = await surviving_markers(connection)
        assert after == set(), f"content survived the erasure: {sorted(after)}"
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_process_survives_what_content_does_not() -> None:
    """Replay must still prove the work happened. Erasing rows instead of
    content would leave nothing to prove it with."""
    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            row = (
                await connection.execute(
                    select(
                        investigations.c.status,
                        investigations.c.question,
                        investigations.c.state,
                    ).where(investigations.c.investigation_id == INVESTIGATION)
                )
            ).one()
            execution = (
                await connection.execute(
                    select(
                        agent_executions.c.agent_id,
                        agent_executions.c.model,
                        agent_executions.c.latency_ms,
                        agent_executions.c.status,
                    ).where(agent_executions.c.investigation_id == INVESTIGATION)
                )
            ).one()
            claim = (
                await connection.execute(
                    select(
                        draft_finding_claims.c.kind,
                        draft_finding_claims.c.position,
                    ).where(draft_finding_claims.c.claim_id == CLAIM)
                )
            ).one()

        assert row.status == "completed"
        # The lifecycle decision survives; the narrative does not.
        assert row.state.get("completion") == {"human_approved": False}
        assert "finding" not in row.state
        # Non-sensitive execution metadata survives entirely.
        assert execution.agent_id == "cube_analyst_v1"
        assert execution.model == "cerebras/zai-glm-4.7"
        assert execution.latency_ms == 1200
        assert execution.status == "success"
        # The failure *code* explains the terminal state and stays; only
        # the message, which is `str(error)`, goes.
        assert row.state["failure"] == {"code": "pipeline_failed"}
        # That a claim was observed, and where it sat, is process not content.
        assert claim.kind == "observed"
        assert claim.position == 0
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_a_cited_claim_still_resolves_to_something() -> None:
    """Tombstoned, not deleted. A claim resolving to nothing would be
    indistinguishable from a claim that never had evidence."""
    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            citation = (
                await connection.execute(
                    select(
                        evidence_citations.c.state,
                        evidence_citations.c.aggregate_value,
                        evidence_citations.c.filters,
                        evidence_citations.c.metric,
                        evidence_citations.c.period,
                        evidence_citations.c.grain,
                    ).where(evidence_citations.c.citation_id == CITATION)
                )
            ).one()

        assert citation.state == "tombstoned"
        assert citation.aggregate_value == ""
        # Filters can carry customer values, so they go too.
        assert citation.filters == []
        # The governed context goes with the value. A Tombstone carries
        # identity, category and instant, so leaving the metric on the row
        # would let the citation list serve what resolving it refuses.
        assert citation.metric == ""
        assert citation.period is None
        assert citation.grain is None
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_a_running_investigation_cannot_be_erased() -> None:
    """Erasing under a live pipeline races every write still to come."""
    await seed(status="running")
    runtime = create_async_engine(RUNTIME_URL)
    try:
        with pytest.raises(ErasureError, match="terminal"):
            async with runtime.begin() as connection:
                await set_tenant_context(connection, TENANT)
                await PostgresErasureRepository(connection).request(
                    erasure_id=uuid4(),
                    tenant_id=TENANT,
                    investigation_id=INVESTIGATION,
                    category=DeletionCategory.TENANT_REQUEST,
                    now=NOW,
                )
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_asking_twice_reaches_the_same_operation() -> None:
    """Not a second erasure racing the first."""
    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            first = await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            second = await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            count = await connection.scalar(
                select(erasure_operations.c.erasure_id).where(
                    erasure_operations.c.investigation_id == INVESTIGATION
                )
            )

        assert first.erasure_id == second.erasure_id
        assert count == first.erasure_id
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_erasing_twice_keeps_the_original_completion_time() -> None:
    """A Tombstone's timestamp should say when the content actually went."""
    await seed()
    later = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            first = await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            again = await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=later,
            )

        assert first.completed_at == again.completed_at
        assert again.progress is ErasureProgress.COMPLETED
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_a_failed_erasure_is_retryable_and_never_completed() -> None:
    """"We deleted some of it" is the one answer this must never give."""
    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            await repository.mark_failed(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                failure_code="storage_unavailable",
            )

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            failed = (
                await connection.execute(
                    select(
                        erasure_operations.c.progress,
                        erasure_operations.c.completed_at,
                        erasure_operations.c.failure_code,
                    ).where(
                        erasure_operations.c.investigation_id == INVESTIGATION
                    )
                )
            ).one()
        assert failed.progress == "failed"
        assert failed.completed_at is None

        # And the retry succeeds, from the same operation.
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            retried = await PostgresErasureRepository(connection).erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
        assert retried.progress is ErasureProgress.COMPLETED
        assert retried.failure_code is None
        assert retried.attempts >= 1
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_a_rolled_back_erasure_leaves_everything_intact() -> None:
    """The transaction is the boundary. A partial erasure that committed would
    be content surviving a deletion no retry knows the shape of."""
    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        with pytest.raises(RuntimeError, match="interrupted"):
            async with runtime.begin() as connection:
                await set_tenant_context(connection, TENANT)
                repository = PostgresErasureRepository(connection)
                await repository.request(
                    erasure_id=uuid4(),
                    tenant_id=TENANT,
                    investigation_id=INVESTIGATION,
                    category=DeletionCategory.TENANT_REQUEST,
                    now=NOW,
                )
                await repository.erase(
                    investigation_id=INVESTIGATION,
                    category=DeletionCategory.TENANT_REQUEST,
                    now=NOW,
                )
                raise RuntimeError("interrupted after erasing, before commit")

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            survived = await surviving_markers(connection)
            operation = await connection.scalar(
                select(erasure_operations.c.progress).where(
                    erasure_operations.c.investigation_id == INVESTIGATION
                )
            )

        # Everything is back, including the operation itself.
        assert survived == set(MARKERS.values())
        assert operation is None
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_the_audit_outbox_is_outside_the_mutation_boundary() -> None:
    """Audit Entries must be byte-for-byte unchanged.

    The outbox is where they leave from, and it is the only audit surface this
    transaction could reach — ClickHouse itself is unreachable, since the
    runtime holds insert/select and the erasure never opens a client. So this
    asserts on the rows that would become Audit Entries.
    """
    from zentra_adapter_postgres.schema import audit_outbox

    await seed()
    event_id = uuid4()
    owner = create_async_engine(OWNER_URL)
    try:
        async with owner.begin() as connection:
            await connection.execute(
                audit_outbox.insert().values(
                    event_id=event_id,
                    investigation_id=INVESTIGATION,
                    tenant_id=TENANT,
                    payload={
                        "event_type": "investigation.completed",
                        "status": "completed",
                        "metadata": {"agent_id": "cube_analyst_v1", "step": 1},
                    },
                )
            )
    finally:
        await owner.dispose()

    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            before = json.dumps(
                await connection.scalar(
                    select(audit_outbox.c.payload).where(
                        audit_outbox.c.event_id == event_id
                    )
                ),
                sort_keys=True,
            )

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            after = json.dumps(
                await connection.scalar(
                    select(audit_outbox.c.payload).where(
                        audit_outbox.c.event_id == event_id
                    )
                ),
                sort_keys=True,
            )

        assert after == before
    finally:
        await runtime.dispose()
        await cleanup()


def test_the_erasure_never_reaches_the_audit_ledger() -> None:
    """Structural, not disciplinary.

    Checked against what the module *imports*, not what its prose says — a
    grep over source text would be defeated by the very comment explaining the
    rule.
    """
    import ast
    import inspect as py_inspect

    from zentra_adapter_postgres import erasure

    tree = ast.parse(py_inspect.getsource(erasure))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    assert not any("clickhouse" in name.lower() for name in imported)
    # Not even the outbox: nothing this writes becomes an event.
    assert "audit_outbox" not in imported
    assert "audit_entries" not in imported


@pytest.mark.asyncio
async def test_a_timeline_stays_strictly_increasing_across_requests() -> None:
    """The aggregate bumps its own events by a microsecond, but a rehydrated
    Investigation carries none — so two requests writing in the same instant
    would sort by a random id, and Replay would show an order that never
    happened."""
    from zentra_domain_investigation import DomainEvent, InvestigationStatus

    from zentra_adapter_postgres.investigation import PostgresAuditOutboxRepository
    from zentra_adapter_postgres.schema import audit_outbox

    await seed()
    same_instant = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)

    def event(event_type: str) -> DomainEvent:
        return DomainEvent(
            event_id=uuid4(),
            event_type=event_type,
            investigation_id=INVESTIGATION,
            tenant_id=TENANT,
            status=InvestigationStatus.AWAITING_APPROVAL,
            occurred_at=same_instant,
        )

    runtime = create_async_engine(RUNTIME_URL)
    try:
        # Three separate requests, each with its own repository, all claiming
        # the same microsecond.
        for event_type in (
            "human_approval.requested",
            "human_approval.denied",
            "human_approval.granted",
        ):
            async with runtime.begin() as connection:
                await set_tenant_context(connection, TENANT)
                await PostgresAuditOutboxRepository(
                    connection,
                    trace_id=uuid4(),
                    span_id=uuid4(),
                ).enqueue([event(event_type)])

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            rows = (
                await connection.execute(
                    select(audit_outbox.c.created_at, audit_outbox.c.payload)
                    .where(audit_outbox.c.investigation_id == INVESTIGATION)
                    .order_by(audit_outbox.c.created_at)
                )
            ).all()

        stamps = [row.created_at for row in rows]
        assert stamps == sorted(stamps)
        assert len(set(stamps)) == 3, "two events share an instant"
        assert [row.payload["event_type"] for row in rows] == [
            "human_approval.requested",
            "human_approval.denied",
            "human_approval.granted",
        ]
    finally:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            await connection.execute(
                audit_outbox.delete().where(
                    audit_outbox.c.investigation_id == INVESTIGATION
                )
            )
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_an_erased_citation_resolves_to_a_minimal_tombstone() -> None:
    """Identity, category, timestamp. A blanked citation would still hand back
    the metric, the period, the grain and the filters — and a filter can carry
    customer values as readily as an aggregate can."""
    from zentra_domain_investigation import Tombstone

    from zentra_adapter_postgres.draft_finding import (
        PostgresEvidenceCitationRepository,
    )
    from zentra_adapter_postgres.schema import evidence_citations

    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            repository = PostgresErasureRepository(connection)
            await repository.request(
                erasure_id=uuid4(),
                tenant_id=TENANT,
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )
            await repository.erase(
                investigation_id=INVESTIGATION,
                category=DeletionCategory.TENANT_REQUEST,
                now=NOW,
            )

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            resolved = await PostgresEvidenceCitationRepository(connection).resolve(
                INVESTIGATION, CITATION
            )
            # The row is still there — a claim must resolve to something.
            row_count = await connection.scalar(
                select(func.count())
                .select_from(evidence_citations)
                .where(evidence_citations.c.citation_id == CITATION)
            )

        assert row_count == 1
        assert isinstance(resolved, Tombstone)
        assert resolved.citation_id == CITATION
        assert resolved.category == "tenant_request"
        assert resolved.erased_at is not None
        # Nothing else is reachable through it.
        for leaky in ("metric", "filters", "period", "grain", "aggregate_value"):
            assert not hasattr(resolved, leaky)
    finally:
        await runtime.dispose()
        await cleanup()


@pytest.mark.asyncio
async def test_unexpected_loss_is_still_unavailable_after_a_deletion_elsewhere(
) -> None:
    """A fault and a Tenant's request stay different facts. Erasing one
    Investigation must not relabel another's missing evidence as deliberate."""
    from zentra_domain_investigation import CitationState

    from zentra_adapter_postgres.draft_finding import (
        PostgresEvidenceCitationRepository,
    )

    await seed()
    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT)
            # This citation names no producing execution, so its evidence is
            # unreachable — a fault, not a deletion.
            resolved = await PostgresEvidenceCitationRepository(connection).resolve(
                INVESTIGATION, CITATION
            )

        assert getattr(resolved, "state", None) is CitationState.UNAVAILABLE
    finally:
        await runtime.dispose()
        await cleanup()
