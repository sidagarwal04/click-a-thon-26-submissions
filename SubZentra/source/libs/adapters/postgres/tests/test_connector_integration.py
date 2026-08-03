"""The Data Source repository against a real Postgres.

The fakes in `libs/application/connector/tests` proved the service's logic; they
could not prove a row survives a restart, that RLS keeps one tenant's
credentials away from another, or that the sealed bytes really are sealed. Those
are properties of the database, so they are asserted against one.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_adapter_clickhouse import AesGcmCredentialCipher
from zentra_application_connector import SourceCredentials
from zentra_domain_connector import (
    BindingCeiling,
    Cardinality,
    CatalogAccessOverride,
    CatalogVersion,
    DataSource,
    FieldIdentity,
    FieldProfile,
    HarvestPhase,
    HarvestRun,
    HarvestScope,
    Relation,
    RelationEvidence,
    RelationOrigin,
    RelationState,
    SourceField,
    SourceHealth,
    SourceKind,
    SourceTable,
    TypeFamily,
    UnreadableTable,
)

from zentra_adapter_postgres import (
    Database,
    PostgresAgentAccessRepository,
    PostgresCatalogRepository,
    PostgresDataSourceRepository,
    PostgresHarvestRunRepository,
    PostgresRelationRepository,
)
from zentra_adapter_postgres.schema import data_sources, tenants

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)

#: Stands in for AES-GCM output. The repository never opens it, so its only
#: relevant property here is that it is bytes carrying a recognisable marker.
SEALED = b"\x00\x01sealed-ciphertext-not-a-password\x02\x03"


def _source(tenant_id: UUID, name: str = "Atlys production events") -> DataSource:
    return DataSource(
        data_source_id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        kind=SourceKind.CONNECTED,
        sealed_credentials=SEALED,
        description="ClickHouse Cloud",
        health=SourceHealth.REACHABLE,
        store_sample_values=False,
        last_verified_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        metadata={"host": "abc.clickhouse.cloud", "database": "clickathon"},
    )


@asynccontextmanager
async def _two_tenants():
    """Seed two tenants and take them away again.

    A context manager rather than a pytest fixture: an async fixture needs a
    plugin this project does not configure, and the integration test beside this
    one does its own setup for the same reason.
    """
    tenant_id, other_tenant_id = uuid4(), uuid4()
    owner = create_async_engine(OWNER_URL)
    async with owner.begin() as connection:
        await connection.execute(
            insert(tenants),
            [
                {"tenant_id": tenant_id, "name": "Connector Tenant"},
                {"tenant_id": other_tenant_id, "name": "Other Connector Tenant"},
            ],
        )
    try:
        yield tenant_id, other_tenant_id
    finally:
        async with owner.begin() as connection:
            await connection.execute(
                data_sources.delete().where(
                    data_sources.c.tenant_id.in_([tenant_id, other_tenant_id])
                )
            )
            await connection.execute(
                tenants.delete().where(
                    tenants.c.tenant_id.in_([tenant_id, other_tenant_id])
                )
            )
        await owner.dispose()


@asynccontextmanager
async def _repository():
    database = Database(RUNTIME_URL)
    try:
        yield PostgresDataSourceRepository(database), database
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_a_registered_source_survives_and_reads_back() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (repository, _db):
        source = _source(tenant_id)
        await repository.add(source)

        found = await repository.get(source.data_source_id, tenant_id=tenant_id)

        assert found is not None
        assert found.name == source.name
        assert found.kind is SourceKind.CONNECTED
        assert found.health is SourceHealth.REACHABLE
        assert found.sealed_credentials == SEALED
        assert found.metadata["database"] == "clickathon"


@pytest.mark.asyncio
async def test_a_real_password_never_reaches_the_database_in_the_clear() -> None:
    """The guarantee the whole design rests on, end to end.

    Uses the real cipher and a real password rather than a placeholder: the
    claim worth asserting is not that some bytes round-trip, it is that the
    secret an operator typed cannot be read out of the row that stores it.
    """
    secret = "correct-horse-battery-staple"
    cipher = AesGcmCredentialCipher(bytes.fromhex("11" * 32))
    sealed = cipher.seal(
        SourceCredentials(
            host="abc.clickhouse.cloud",
            port=8443,
            database="clickathon",
            username="default",
            password=secret,
            secure=True,
        )
    )

    async with (
        _two_tenants() as (tenant_id, _),
        _repository() as (repository, database),
    ):
        source = _source(tenant_id)
        source.sealed_credentials = sealed
        await repository.add(source)

        async with database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(data_sources.c.sealed_credentials).where(
                        data_sources.c.data_source_id == source.data_source_id
                    )
                )
            ).one()

        stored = bytes(row.sealed_credentials)
        assert secret.encode() not in stored
        assert b"default" not in stored
        # And it is still the credential, not merely unreadable bytes.
        assert cipher.open(stored).password == secret


@pytest.mark.asyncio
async def test_health_changes_are_saved() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (repository, _db):
        source = _source(tenant_id)
        await repository.add(source)

        source.mark_unreachable(at=datetime.now(UTC))
        await repository.save(source)

        found = await repository.get(source.data_source_id, tenant_id=tenant_id)
        assert found is not None
        assert found.health is SourceHealth.UNREACHABLE


@pytest.mark.asyncio
async def test_one_tenant_cannot_read_anothers_source() -> None:
    """Row-level security, from the runtime role that is subject to it."""
    async with _two_tenants() as (tenant_id, other_id), _repository() as (repo, _db):
        source = _source(tenant_id)
        await repo.add(source)

        assert await repo.get(source.data_source_id, tenant_id=other_id) is None
        assert list(await repo.list(tenant_id=other_id)) == []
        assert len(await repo.list(tenant_id=tenant_id)) == 1


@pytest.mark.asyncio
async def test_a_deleted_source_is_gone() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (repository, _db):
        source = _source(tenant_id)
        await repository.add(source)

        await repository.delete(source.data_source_id, tenant_id=tenant_id)

        assert await repository.get(source.data_source_id, tenant_id=tenant_id) is None


# ------------------------------------------------------- catalog and relations


def _catalog(tenant_id: UUID, data_source_id: UUID) -> CatalogVersion:
    field_id = uuid4()
    table_id = uuid4()
    return CatalogVersion(
        catalog_version_id=uuid4(),
        data_source_id=data_source_id,
        tenant_id=tenant_id,
        harvest_run_id=uuid4(),
        created_at=datetime.now(UTC),
        tables=(
            SourceTable(
                table_id=table_id,
                name="purchase_completed",
                database="clickathon",
                engine="MergeTree",
                estimated_rows=7054,
                fields=(
                    SourceField(
                        field_id=field_id,
                        table_id=table_id,
                        name="user_id",
                        declared_type="String",
                        family=TypeFamily.STRING,
                        normalised_type="string",
                        nullable=False,
                        position=0,
                        profile=FieldProfile(sampled_rows=1000, distinct_count=1000),
                    ),
                ),
            ),
        ),
        unreadable=(UnreadableTable("clickathon.locked", "permission denied"),),
    )


def _relation(tenant_id: UUID, version: CatalogVersion, source_id: UUID) -> Relation:
    table = version.tables[0]
    left = table.fields[0]
    return Relation(
        relation_id=uuid4(),
        tenant_id=tenant_id,
        catalog_version_id=version.catalog_version_id,
        left_field_id=left.field_id,
        right_field_id=uuid4(),
        left_identity=left.identity(table.name),
        right_identity=FieldIdentity("application_started", "user_id", "string"),
        left_data_source_id=source_id,
        right_data_source_id=source_id,
        state=RelationState.PROPOSED,
        origin=RelationOrigin.INFERRED,
        confidence=0.82,
        binding_ceiling=BindingCeiling.SAMPLE_SIZE,
        cardinality=Cardinality.MANY_TO_ONE,
        evidence=RelationEvidence(
            name_affinity=1.0,
            overlap_fraction=0.93,
            sampled_rows=1000,
            left_distinct=1000,
            right_distinct=940,
            matched_distinct=930,
            raw_score=0.9,
            sample_ceiling=0.85,
            cardinality_ceiling=0.95,
        ),
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_a_catalog_version_round_trips_whole() -> None:
    """Stored as one JSONB document, so the whole shape must come back."""
    async with _two_tenants() as (tenant_id, _), _repository() as (sources, database):
        source = _source(tenant_id)
        await sources.add(source)
        catalogs = PostgresCatalogRepository(database)
        version = _catalog(tenant_id, source.data_source_id)

        await catalogs.add_version(version)
        found = await catalogs.get_version(
            version.catalog_version_id, tenant_id=tenant_id
        )

        assert found is not None
        assert found.table_names() == {"purchase_completed"}
        table = found.tables[0]
        assert table.estimated_rows == 7054
        assert table.fields[0].name == "user_id"
        assert table.fields[0].family is TypeFamily.STRING
        # The profile is the part most easily lost in a hand-written codec.
        assert table.fields[0].profile is not None
        assert table.fields[0].profile.sampled_rows == 1000
        assert table.fields[0].profile.is_unique
        assert found.unreadable[0].reason == "permission denied"


@pytest.mark.asyncio
async def test_a_confirmed_relation_survives_and_stays_in_the_join_graph() -> None:
    """The acceptance criterion a reviewer's decision depends on."""
    # The tenant outlives both connection pools: tearing it down would cascade
    # the rows away and the test would pass for the wrong reason.
    async with _two_tenants() as (tenant_id, _):
        async with _repository() as (sources, database):
            source = _source(tenant_id)
            await sources.add(source)
            catalogs = PostgresCatalogRepository(database)
            version = _catalog(tenant_id, source.data_source_id)
            await catalogs.add_version(version)

            repository = PostgresRelationRepository(database)
            relation = _relation(tenant_id, version, source.data_source_id)
            await repository.add_many([relation])

            relation.confirm(actor_id=uuid4(), at=datetime.now(UTC))
            await repository.save(relation)

        # A new Database over new connections, as a restarted process builds.
        async with _repository() as (_sources, database):
            reopened = PostgresRelationRepository(database)
            found = await reopened.get(relation.relation_id, tenant_id=tenant_id)

            assert found is not None
            assert found.state is RelationState.CONFIRMED
            assert found.in_join_graph
            assert found.decided_at is not None
            assert found.evidence is not None
            assert found.evidence.overlap_fraction == 0.93
            assert found.left_identity.field_name == "user_id"

            in_version = await reopened.list_for_version(
                version.catalog_version_id, tenant_id=tenant_id
            )
            assert [r.relation_id for r in in_version] == [relation.relation_id]


@pytest.mark.asyncio
async def test_a_second_tenant_reads_no_catalogs_or_relations() -> None:
    async with (
        _two_tenants() as (tenant_id, other_id),
        _repository() as (src, database),
    ):
        source = _source(tenant_id)
        await src.add(source)
        catalogs = PostgresCatalogRepository(database)
        version = _catalog(tenant_id, source.data_source_id)
        await catalogs.add_version(version)
        relation_repo = PostgresRelationRepository(database)
        await relation_repo.add_many(
            [_relation(tenant_id, version, source.data_source_id)]
        )

        assert (
            await catalogs.get_version(version.catalog_version_id, tenant_id=other_id)
            is None
        )
        assert (
            await catalogs.latest_version(source.data_source_id, tenant_id=other_id)
            is None
        )
        assert (
            list(
                await relation_repo.list_for_version(
                    version.catalog_version_id, tenant_id=other_id
                )
            )
            == []
        )
        assert (
            list(
                await relation_repo.list_for_source(
                    source.data_source_id, tenant_id=other_id
                )
            )
            == []
        )


@pytest.mark.asyncio
async def test_a_harvest_run_survives_with_its_budget_and_counts() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (sources, database):
        source = _source(tenant_id)
        await sources.add(source)
        runs = PostgresHarvestRunRepository(database)
        run = HarvestRun(
            harvest_run_id=uuid4(),
            data_source_id=source.data_source_id,
            tenant_id=tenant_id,
            scope=HarvestScope(databases=("clickathon",)),
        )
        await runs.add(run)

        # An in-flight run is what stops a second harvest starting beside it.
        active = await runs.active_for_source(
            source.data_source_id, tenant_id=tenant_id
        )
        assert active is not None
        assert active.harvest_run_id == run.harvest_run_id
        assert active.scope.databases == ("clickathon",)

        run.advance(HarvestPhase.PROFILING, at=datetime.now(UTC))
        run.budget.spend(queries=12, seconds=3.5)
        run.tables_found = 8
        await runs.save(run)

        found = await runs.get(run.harvest_run_id, tenant_id=tenant_id)
        assert found is not None
        assert found.phase is HarvestPhase.PROFILING
        assert found.budget.queries_used == 12
        assert found.tables_found == 8
        assert found.is_running


# --------------------------------------------------------------- agent access


def _table_override(
    tenant_id: UUID, data_source_id: UUID, *, agent_visible: bool
) -> CatalogAccessOverride:
    return CatalogAccessOverride(
        override_id=uuid4(),
        tenant_id=tenant_id,
        data_source_id=data_source_id,
        table_name="purchase_completed",
        field_name=None,
        agent_visible=agent_visible,
        decided_by=uuid4(),
        decided_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_a_table_override_survives_and_reads_back() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (sources, database):
        source = _source(tenant_id)
        await sources.add(source)
        access = PostgresAgentAccessRepository(database)

        await access.upsert(
            _table_override(tenant_id, source.data_source_id, agent_visible=False)
        )

        found = await access.list_for_source(
            source.data_source_id, tenant_id=tenant_id
        )
        assert len(found) == 1
        assert found[0].table_name == "purchase_completed"
        assert found[0].field_name is None
        assert found[0].agent_visible is False


@pytest.mark.asyncio
async def test_repeating_a_table_toggle_upserts_rather_than_accumulating() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (sources, database):
        source = _source(tenant_id)
        await sources.add(source)
        access = PostgresAgentAccessRepository(database)

        await access.upsert(
            _table_override(tenant_id, source.data_source_id, agent_visible=False)
        )
        await access.upsert(
            _table_override(tenant_id, source.data_source_id, agent_visible=True)
        )

        found = await access.list_for_source(
            source.data_source_id, tenant_id=tenant_id
        )
        assert len(found) == 1
        assert found[0].agent_visible is True


@pytest.mark.asyncio
async def test_a_field_override_is_independent_of_a_table_override() -> None:
    async with _two_tenants() as (tenant_id, _), _repository() as (sources, database):
        source = _source(tenant_id)
        await sources.add(source)
        access = PostgresAgentAccessRepository(database)

        await access.upsert(
            _table_override(tenant_id, source.data_source_id, agent_visible=True)
        )
        await access.upsert(
            CatalogAccessOverride(
                override_id=uuid4(),
                tenant_id=tenant_id,
                data_source_id=source.data_source_id,
                table_name="purchase_completed",
                field_name="user_id",
                agent_visible=False,
                decided_by=uuid4(),
                decided_at=datetime.now(UTC),
            )
        )

        found = {
            (o.table_name, o.field_name): o.agent_visible
            for o in await access.list_for_source(
                source.data_source_id, tenant_id=tenant_id
            )
        }
        assert found[("purchase_completed", None)] is True
        assert found[("purchase_completed", "user_id")] is False


@pytest.mark.asyncio
async def test_a_second_tenant_reads_no_agent_access_overrides() -> None:
    async with (
        _two_tenants() as (tenant_id, other_id),
        _repository() as (sources, database),
    ):
        source = _source(tenant_id)
        await sources.add(source)
        access = PostgresAgentAccessRepository(database)
        await access.upsert(
            _table_override(tenant_id, source.data_source_id, agent_visible=False)
        )

        assert (
            list(
                await access.list_for_source(
                    source.data_source_id, tenant_id=other_id
                )
            )
            == []
        )
