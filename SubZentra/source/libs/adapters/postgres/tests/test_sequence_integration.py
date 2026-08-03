from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceTableReference,
)
from zentra_domain_sequence import (
    DatasetTableVersionReference,
    PreparedTable,
    Sequence,
    SequenceRun,
    SequenceRunFailed,
    SequenceRunSucceeded,
    SequenceStep,
    build_sequence_operation,
)

from zentra_adapter_postgres import Database, PostgresSequenceUnitOfWorkFactory
from zentra_adapter_postgres.schema import tenants
from zentra_adapter_postgres.sequence import PostgresSequenceRepository

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


async def _seed_tenants(*tenant_ids: UUID) -> None:
    assert OWNER_URL is not None
    owner_engine = create_async_engine(OWNER_URL)
    async with owner_engine.begin() as connection:
        await connection.execute(
            insert(tenants),
            [{"tenant_id": tid, "name": f"Tenant {tid}"} for tid in tenant_ids],
        )
    await owner_engine.dispose()


def _build_sequence_with_two_steps(
    *, tenant_id: UUID, sequence_id: UUID, dataset_workspace_id: UUID
) -> Sequence:
    sequence = Sequence.create(
        sequence_id=sequence_id,
        tenant_id=tenant_id,
        dataset_workspace_id=dataset_workspace_id,
        raw_table_reference=DatasetTableVersionReference(
            storage_locator="s3://fixtures/messy_orders.csv", file_format="csv"
        ),
        now=NOW,
    )

    step_1_id, table_1_id = uuid4(), uuid4()
    step_1 = SequenceStep(
        step_id=step_1_id,
        sequence_id=sequence_id,
        tenant_id=tenant_id,
        operation=build_sequence_operation("drop_nulls", {"columns": ["email"]}),
        input_reference=None,
        produced_table_id=table_1_id,
        created_at=NOW,
    )
    table_1 = PreparedTable(
        prepared_table_id=table_1_id,
        tenant_id=tenant_id,
        sequence_id=sequence_id,
        step_id=step_1_id,
        parent_table_reference=None,
        row_count=3,
        columns=("email", "amount"),
        created_at=NOW,
    )
    sequence.record_run(
        SequenceRun(
            run_id=uuid4(),
            sequence_id=sequence_id,
            tenant_id=tenant_id,
            step_id=step_1_id,
            outcome=SequenceRunSucceeded(produced_table_id=table_1_id),
            attempted_at=NOW,
        )
    )
    sequence.append_step(step_1, table_1)

    step_2_id, table_2_id = uuid4(), uuid4()
    table_1_ref = SequenceTableReference(
        tenant_id=tenant_id, reference_id=table_1_id, kind="prepared"
    )
    step_2 = SequenceStep(
        step_id=step_2_id,
        sequence_id=sequence_id,
        tenant_id=tenant_id,
        operation=build_sequence_operation("dedupe", {}),
        input_reference=table_1_ref,
        produced_table_id=table_2_id,
        created_at=NOW,
    )
    table_2 = PreparedTable(
        prepared_table_id=table_2_id,
        tenant_id=tenant_id,
        sequence_id=sequence_id,
        step_id=step_2_id,
        parent_table_reference=table_1_ref,
        row_count=2,
        columns=("email", "amount"),
        created_at=NOW,
    )
    sequence.record_run(
        SequenceRun(
            run_id=uuid4(),
            sequence_id=sequence_id,
            tenant_id=tenant_id,
            step_id=step_2_id,
            outcome=SequenceRunSucceeded(produced_table_id=table_2_id),
            attempted_at=NOW,
        )
    )
    sequence.append_step(step_2, table_2)

    sequence.record_run(
        SequenceRun(
            run_id=uuid4(),
            sequence_id=sequence_id,
            tenant_id=tenant_id,
            step_id=uuid4(),
            outcome=SequenceRunFailed(
                reason=SequenceExecutionFailureReason.CATALOG_VIOLATION,
                detail="unknown operation 'drop_table'",
            ),
            attempted_at=NOW,
        )
    )

    sequence.mark_final(table_2_id)
    return sequence


@pytest.mark.asyncio
async def test_sequence_lineage_and_immutability_survive_a_full_reload() -> None:
    assert RUNTIME_URL is not None
    tenant_id = uuid4()
    await _seed_tenants(tenant_id)

    sequence_id = uuid4()
    dataset_workspace_id = uuid4()
    original = _build_sequence_with_two_steps(
        tenant_id=tenant_id,
        sequence_id=sequence_id,
        dataset_workspace_id=dataset_workspace_id,
    )

    database = Database(RUNTIME_URL)
    factory = PostgresSequenceUnitOfWorkFactory(database)

    async with factory(tenant_id, UUID(int=0), UUID(int=0)) as unit_of_work:
        await unit_of_work.sequences.add_sequence(original)
        for step, table in zip(original.steps, original.prepared_tables, strict=True):
            await unit_of_work.sequences.add_step(step, table)
        for run in original.runs:
            await unit_of_work.sequences.add_run(run)
        for prepared_table_id in original.final_table_ids:
            await unit_of_work.sequences.mark_final(
                sequence_id=sequence_id,
                prepared_table_id=prepared_table_id,
                tenant_id=tenant_id,
                marked_at=NOW,
            )
        await unit_of_work.commit()

    # Reload from a fresh connection/unit of work — no in-memory state reused.
    async with factory(tenant_id, UUID(int=0), UUID(int=0)) as unit_of_work:
        reloaded = await unit_of_work.sequences.get_sequence(sequence_id)

    assert reloaded is not None
    assert reloaded.sequence_id == original.sequence_id
    assert reloaded.dataset_workspace_id == original.dataset_workspace_id
    assert reloaded.raw_table_reference == original.raw_table_reference
    assert len(reloaded.steps) == 2
    assert len(reloaded.prepared_tables) == 2
    assert len(reloaded.runs) == 3
    assert reloaded.final_table_ids == original.final_table_ids

    final_table_id = next(iter(original.final_table_ids))
    original_lineage = [
        t.prepared_table_id for t in original.lineage_for(final_table_id)
    ]
    reloaded_lineage = [
        t.prepared_table_id for t in reloaded.lineage_for(final_table_id)
    ]
    assert reloaded_lineage == original_lineage

    reloaded_operations = {step.step_id: step.operation for step in reloaded.steps}
    original_operations = {step.step_id: step.operation for step in original.steps}
    assert reloaded_operations == original_operations


@pytest.mark.asyncio
async def test_no_repository_method_can_mutate_a_persisted_prepared_table() -> None:
    public_methods = {
        name for name in dir(PostgresSequenceRepository) if not name.startswith("_")
    }
    assert "update_prepared_table" not in public_methods
    assert not any(name.startswith("update_prepared") for name in public_methods)


@pytest.mark.asyncio
async def test_cross_tenant_isolation_is_enforced_by_rls() -> None:
    assert RUNTIME_URL is not None
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    await _seed_tenants(tenant_id, other_tenant_id)

    sequence_id = uuid4()
    original = _build_sequence_with_two_steps(
        tenant_id=tenant_id,
        sequence_id=sequence_id,
        dataset_workspace_id=uuid4(),
    )

    database = Database(RUNTIME_URL)
    factory = PostgresSequenceUnitOfWorkFactory(database)
    async with factory(tenant_id, UUID(int=0), UUID(int=0)) as unit_of_work:
        await unit_of_work.sequences.add_sequence(original)
        for step, table in zip(original.steps, original.prepared_tables, strict=True):
            await unit_of_work.sequences.add_step(step, table)
        await unit_of_work.commit()

    async with factory(other_tenant_id, UUID(int=0), UUID(int=0)) as unit_of_work:
        invisible = await unit_of_work.sequences.get_sequence(sequence_id)

    assert invisible is None
