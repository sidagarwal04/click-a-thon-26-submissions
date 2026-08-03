from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_adapter_postgres import Database, PostgresSequenceUnitOfWorkFactory
from zentra_adapter_postgres.schema import tenants
from zentra_domain_sequence import DatasetTableVersionReference, Sequence

from zentra_adapter_sequence_execution.postgres_lookup import PostgresRawTableLookup

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_resolves_a_persisted_sequences_raw_table_reference() -> None:
    assert OWNER_URL is not None
    assert RUNTIME_URL is not None
    tenant_id = uuid4()

    owner_engine = create_async_engine(OWNER_URL)
    async with owner_engine.begin() as connection:
        await connection.execute(
            insert(tenants), [{"tenant_id": tenant_id, "name": "Lookup Tenant"}]
        )
    await owner_engine.dispose()

    sequence_id = uuid4()
    raw_table = DatasetTableVersionReference(
        storage_locator="s3://fixtures/messy_orders.csv", file_format="csv"
    )
    sequence = Sequence.create(
        sequence_id=sequence_id,
        tenant_id=tenant_id,
        dataset_workspace_id=uuid4(),
        raw_table_reference=raw_table,
        now=NOW,
    )

    database = Database(RUNTIME_URL)
    factory = PostgresSequenceUnitOfWorkFactory(database)
    async with factory(tenant_id, UUID(int=0), UUID(int=0)) as unit_of_work:
        await unit_of_work.sequences.add_sequence(sequence)
        await unit_of_work.commit()

    lookup = PostgresRawTableLookup(factory)
    resolved = await lookup.resolve(tenant_id=tenant_id, sequence_id=sequence_id)
    assert resolved == raw_table


@pytest.mark.asyncio
async def test_resolves_to_none_for_an_unknown_sequence() -> None:
    assert RUNTIME_URL is not None
    database = Database(RUNTIME_URL)
    factory = PostgresSequenceUnitOfWorkFactory(database)
    lookup = PostgresRawTableLookup(factory)

    resolved = await lookup.resolve(tenant_id=uuid4(), sequence_id=uuid4())
    assert resolved is None
