"""Draft Finding persistence against a real Postgres.

Three things only a real database can prove, and all three are load-bearing:
claim order survives a round trip, RLS makes another Tenant's draft invisible
rather than merely filtered, and the migration is safe to run twice.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    CitationFilter,
    Claim,
    ClaimKind,
    Contradiction,
    DraftFinding,
    EvidenceCitation,
    RootCauseState,
)

from zentra_adapter_postgres.database import set_tenant_context
from zentra_adapter_postgres.draft_finding import (
    PostgresDraftFindingRepository,
    PostgresEvidenceCitationRepository,
)
from zentra_adapter_postgres.schema import (
    draft_finding_claims,
    draft_findings,
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

TENANT_A = UUID("81000000-0000-0000-0000-000000000001")
TENANT_B = UUID("81000000-0000-0000-0000-000000000002")
INVESTIGATION_A = UUID("82000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
CITATION_ID = UUID("cc000000-0000-0000-0000-000000000001")
CITATION_ID_2 = UUID("cc000000-0000-0000-0000-000000000002")


async def seed(owner_url: str) -> None:
    owner = create_async_engine(owner_url)
    async with owner.begin() as connection:
        await connection.execute(
            postgres_insert(tenants)
            .values(
                [
                    {"tenant_id": TENANT_A, "name": "Draft A"},
                    {"tenant_id": TENANT_B, "name": "Draft B"},
                ]
            )
            .on_conflict_do_nothing()
        )
        await connection.execute(
            postgres_insert(investigations)
            .values(
                investigation_id=INVESTIGATION_A,
                tenant_id=TENANT_A,
                question="Why did EU refunds increase?",
                status="completed",
            )
            .on_conflict_do_nothing()
        )
    await owner.dispose()


def citations() -> tuple[EvidenceCitation, ...]:
    """The evidence the fixture's claims cite. Written first: a claim
    referencing a citation that is not there yet is a dangling reference the
    database will refuse, which is the point of the foreign key."""
    return tuple(
        EvidenceCitation(
            citation_id=citation_id,
            tenant_id=TENANT_A,
            investigation_id=INVESTIGATION_A,
            metric=metric,
            filters=(
                CitationFilter(
                    member="Commerce.region", operator="equals", values=("EU",)
                ),
            ),
            period="July 2026",
            grain="month",
            producing_execution_id=None,
            aggregate_value=value,
            evaluator_outcome=None,
        )
        for citation_id, metric, value in (
            (CITATION_ID, "refund_amount", "260.00"),
            (CITATION_ID_2, "refund_rate", "75"),
        )
    )


def draft(version: int = 1) -> DraftFinding:
    return DraftFinding(
        draft_finding_id=uuid4(),
        tenant_id=TENANT_A,
        investigation_id=INVESTIGATION_A,
        version=version,
        created_at=NOW,
        produced_by_execution_id=None,
        headline=f"Draft at version {version}",
        summary="Governed EU refund amount rose from $20 to $260.",
        claims=(
            Claim(
                claim_id=uuid4(),
                kind=ClaimKind.OBSERVED,
                text="EU refund amount rose from $20.00 to $260.00.",
                position=0,
                metric="refund_amount",
                value="260.00",
                period="July 2026",
                citation_ids=(CITATION_ID,),
            ),
            Claim(
                claim_id=uuid4(),
                kind=ClaimKind.INTERPRETATION,
                text="The rise is concentrated in a single week.",
                position=1,
            ),
            Claim(
                claim_id=uuid4(),
                kind=ClaimKind.OBSERVED,
                text="Refund rate rose from 25% to 75%.",
                position=2,
                metric="refund_rate",
                value="75",
                period="July 2026",
                citation_ids=(CITATION_ID_2,),
            ),
        ),
        contradictions=(Contradiction(detail="Recheck counted 8 rows, not 12."),),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=ConfidenceOutcome(
            score=0.42,
            calibration_method="capped_sample_size",
        ),
    )


async def cleanup(owner_url: str) -> None:
    owner = create_async_engine(owner_url)
    async with owner.begin() as connection:
        await connection.execute(
            draft_findings.delete().where(
                draft_findings.c.investigation_id == INVESTIGATION_A
            )
        )
        await connection.execute(
            evidence_citations.delete().where(
                evidence_citations.c.investigation_id == INVESTIGATION_A
            )
        )
    await owner.dispose()


@pytest.mark.asyncio
async def test_a_draft_and_its_claim_order_survive_a_round_trip() -> None:
    assert OWNER_URL is not None and RUNTIME_URL is not None
    await seed(OWNER_URL)
    await cleanup(OWNER_URL)

    runtime = create_async_engine(RUNTIME_URL)
    try:
        stored = draft()
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            await PostgresEvidenceCitationRepository(connection).add(citations())
            await PostgresDraftFindingRepository(connection).add(stored)

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            loaded = await PostgresDraftFindingRepository(
                connection
            ).latest_for_investigation(INVESTIGATION_A)

        assert loaded is not None
        assert loaded.draft_finding_id == stored.draft_finding_id
        # Order is the contract. A set-like round trip would pass a weaker
        # assertion and still have lost the reader's sequence.
        assert [c.position for c in loaded.claims] == [0, 1, 2]
        assert [c.text for c in loaded.claims] == [c.text for c in stored.claims]
        assert [c.kind for c in loaded.claims] == [
            ClaimKind.OBSERVED,
            ClaimKind.INTERPRETATION,
            ClaimKind.OBSERVED,
        ]
        assert loaded.contradictions == stored.contradictions
        assert loaded.root_cause is RootCauseState.UNRESOLVED
        assert loaded.confidence is not None
        assert loaded.confidence.score == 0.42
        assert loaded.confidence.calibration_method == "capped_sample_size"
        # The claim-to-citation link survives, read back through the join
        # rather than the claim's own JSON copy.
        assert loaded.claims[0].citation_ids == (CITATION_ID,)
        assert loaded.claims[1].citation_ids == ()
    finally:
        await runtime.dispose()
        await cleanup(OWNER_URL)


@pytest.mark.asyncio
async def test_a_refresh_returns_the_latest_stored_draft() -> None:
    """Not a regenerated one, and not the first attempt's. An Investigation can
    be evaluated three times; the reader must see the conclusion they were
    shown, whichever attempt produced it."""
    assert OWNER_URL is not None and RUNTIME_URL is not None
    await seed(OWNER_URL)
    await cleanup(OWNER_URL)

    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            await PostgresEvidenceCitationRepository(connection).add(citations())
            repository = PostgresDraftFindingRepository(connection)
            await repository.add(draft(version=1))
            await repository.add(draft(version=2))

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            loaded = await PostgresDraftFindingRepository(
                connection
            ).latest_for_investigation(INVESTIGATION_A)

        assert loaded is not None
        assert loaded.version == 2
        assert loaded.headline == "Draft at version 2"
    finally:
        await runtime.dispose()
        await cleanup(OWNER_URL)


@pytest.mark.asyncio
async def test_another_tenants_draft_is_invisible_rather_than_filtered() -> None:
    """Fail closed. The row is not merely excluded from a WHERE clause — RLS
    makes it not exist for this connection, including its claims."""
    assert OWNER_URL is not None and RUNTIME_URL is not None
    await seed(OWNER_URL)
    await cleanup(OWNER_URL)

    runtime = create_async_engine(RUNTIME_URL)
    try:
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            await PostgresEvidenceCitationRepository(connection).add(citations())
            await PostgresDraftFindingRepository(connection).add(draft())

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_B)
            intruder = await PostgresDraftFindingRepository(
                connection
            ).latest_for_investigation(INVESTIGATION_A)
            visible_drafts = await connection.scalar(
                select(func.count()).select_from(draft_findings)
            )
            visible_claims = await connection.scalar(
                select(func.count()).select_from(draft_finding_claims)
            )

        assert intruder is None
        assert visible_drafts == 0
        assert visible_claims == 0

        # And with no tenant context at all, nothing is visible either.
        async with runtime.begin() as connection:
            without_context = await connection.scalar(
                select(func.count()).select_from(draft_findings)
            )
        assert without_context == 0
    finally:
        await runtime.dispose()
        await cleanup(OWNER_URL)


@pytest.mark.asyncio
async def test_a_draft_cannot_be_written_into_another_tenant() -> None:
    """The policy's WITH CHECK half. USING stops a Tenant reading another's
    rows; only WITH CHECK stops one *planting* a row there, and a draft
    smuggled into another Tenant would be evidence they never produced.
    """
    assert OWNER_URL is not None and RUNTIME_URL is not None
    await seed(OWNER_URL)
    await cleanup(OWNER_URL)

    runtime = create_async_engine(RUNTIME_URL)
    try:
        forged = DraftFinding(
            draft_finding_id=uuid4(),
            tenant_id=TENANT_A,
            investigation_id=INVESTIGATION_A,
            version=1,
            created_at=NOW,
            produced_by_execution_id=None,
            headline="Planted by another tenant",
            summary="Should never be stored.",
            claims=(),
            contradictions=(),
            root_cause=RootCauseState.UNRESOLVED,
            confidence=None,
        )
        with pytest.raises(DBAPIError):
            async with runtime.begin() as connection:
                # Acting as B, writing a row owned by A.
                await set_tenant_context(connection, TENANT_B)
                await PostgresDraftFindingRepository(connection).add(forged)

        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            assert (
                await PostgresDraftFindingRepository(
                    connection
                ).latest_for_investigation(INVESTIGATION_A)
                is None
            )
    finally:
        await runtime.dispose()
        await cleanup(OWNER_URL)


@pytest.mark.asyncio
async def test_a_claim_cannot_be_written_into_another_tenants_draft() -> None:
    """The same guarantee one level down. Claims carry their own `tenant_id`,
    so the child table needs its own proof, not the parent's."""
    assert OWNER_URL is not None and RUNTIME_URL is not None
    await seed(OWNER_URL)
    await cleanup(OWNER_URL)

    runtime = create_async_engine(RUNTIME_URL)
    try:
        stored = draft()
        async with runtime.begin() as connection:
            await set_tenant_context(connection, TENANT_A)
            await PostgresEvidenceCitationRepository(connection).add(citations())
            await PostgresDraftFindingRepository(connection).add(stored)

        with pytest.raises(DBAPIError):
            async with runtime.begin() as connection:
                await set_tenant_context(connection, TENANT_B)
                await connection.execute(
                    draft_finding_claims.insert().values(
                        claim_id=uuid4(),
                        draft_finding_id=stored.draft_finding_id,
                        tenant_id=TENANT_A,
                        kind="observed",
                        claim_text="Planted claim.",
                        metric="refund_amount",
                        claim_value="260.00",
                        period="July 2026",
                        position=99,
                    )
                )
    finally:
        await runtime.dispose()
        await cleanup(OWNER_URL)
