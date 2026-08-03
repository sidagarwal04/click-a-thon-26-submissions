"""Proves ticket #49's acceptance criteria together: a Sequence built
entirely through the fake adapter, driven step by step, with lineage,
immutability, catalog enforcement, and Final Table marking all coherent
in one flow — not just isolated unit assertions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
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
    SequenceTransitionError,
    build_sequence_operation,
)

from .fakes import FakeSequenceExecutionPort

NOW = datetime(2026, 8, 1, tzinfo=UTC)
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("64000000-0000-0000-0000-000000000001")
DATASET_WORKSPACE_ID = UUID("64000000-0000-0000-0000-000000000002")
RAW_TABLE_ID = UUID("64000000-0000-0000-0000-000000000003")

RAW_ROWS = [
    {"email": "a@example.com", "amount": "10"},
    {"email": None, "amount": "20"},
    {"email": "a@example.com", "amount": "10"},
]


async def run_step(
    sequence: Sequence,
    port: FakeSequenceExecutionPort,
    *,
    input_reference: SequenceTableReference | None,
    operation_kind: str,
    operation_parameters: dict,
) -> UUID | None:
    """Drives one turn: attempt a step through the port, always record the
    Run, and only append a Step + Prepared Table on success. Returns the new
    Prepared Table id on success, None on a recorded failure."""
    run_id = uuid4()
    step_id = uuid4()
    request = SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=step_id,
        operation_kind=operation_kind,
        operation_parameters=operation_parameters,
        input_table=input_reference
        or SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=RAW_TABLE_ID, kind="raw"
        ),
    )
    result = await port.apply_operation(request)

    if isinstance(result, SequenceStepExecutionFailure):
        sequence.record_run(
            SequenceRun(
                run_id=run_id,
                sequence_id=SEQUENCE_ID,
                tenant_id=TENANT_ID,
                step_id=step_id,
                outcome=SequenceRunFailed(reason=result.reason, detail=result.detail),
                attempted_at=NOW,
            )
        )
        return None

    assert isinstance(result, SequenceStepExecutionResult)
    prepared_table_id = result.output_table.reference_id
    sequence.record_run(
        SequenceRun(
            run_id=run_id,
            sequence_id=SEQUENCE_ID,
            tenant_id=TENANT_ID,
            step_id=step_id,
            outcome=SequenceRunSucceeded(produced_table_id=prepared_table_id),
            attempted_at=NOW,
        )
    )
    step = SequenceStep(
        step_id=step_id,
        sequence_id=SEQUENCE_ID,
        tenant_id=TENANT_ID,
        operation=build_sequence_operation(operation_kind, operation_parameters),
        input_reference=input_reference,
        produced_table_id=prepared_table_id,
        created_at=NOW,
    )
    table = PreparedTable(
        prepared_table_id=prepared_table_id,
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=step_id,
        parent_table_reference=input_reference,
        row_count=result.row_count,
        columns=result.columns,
        created_at=NOW,
    )
    sequence.append_step(step, table)
    return prepared_table_id


@pytest.mark.asyncio
async def test_a_full_sequence_can_be_built_incrementally_through_the_fake_port() -> (
    None
):
    port = FakeSequenceExecutionPort()
    port.seed_table(
        tenant_id=TENANT_ID,
        reference_id=RAW_TABLE_ID,
        kind="raw",
        rows=RAW_ROWS,
        columns=("email", "amount"),
    )
    sequence = Sequence.create(
        sequence_id=SEQUENCE_ID,
        tenant_id=TENANT_ID,
        dataset_workspace_id=DATASET_WORKSPACE_ID,
        raw_table_reference=DatasetTableVersionReference(
            storage_locator="s3://fixtures/messy_orders.csv", file_format="csv"
        ),
        now=NOW,
    )

    step_1_table_id = await run_step(
        sequence,
        port,
        input_reference=None,
        operation_kind="drop_nulls",
        operation_parameters={"columns": ["email"]},
    )
    assert step_1_table_id is not None

    step_1_ref = SequenceTableReference(
        tenant_id=TENANT_ID, reference_id=step_1_table_id, kind="prepared"
    )
    step_2_table_id = await run_step(
        sequence,
        port,
        input_reference=step_1_ref,
        operation_kind="dedupe",
        operation_parameters={},
    )
    assert step_2_table_id is not None

    # Lineage: raw -> drop_nulls -> dedupe, both hops recorded in order.
    lineage = sequence.lineage_for(step_2_table_id)
    assert [table.prepared_table_id for table in lineage] == [
        step_1_table_id,
        step_2_table_id,
    ]
    assert len(sequence.runs) == 2
    assert len(sequence.prepared_tables) == 2

    # Mark the final hop as this Sequence's Final Table.
    sequence.mark_final(step_2_table_id)
    assert sequence.final_table_ids == {step_2_table_id}

    # A catalog-violating instruction is rejected before touching the graph.
    catalog_violation_table_id = await run_step(
        sequence,
        port,
        input_reference=step_1_ref,
        operation_kind="drop_table",
        operation_parameters={},
    )
    assert catalog_violation_table_id is None
    assert len(sequence.runs) == 3
    assert len(sequence.prepared_tables) == 2  # unchanged — no table was produced

    failed_run = sequence.runs[-1]
    assert isinstance(failed_run.outcome, SequenceRunFailed)
    assert failed_run.outcome.reason is SequenceExecutionFailureReason.CATALOG_VIOLATION


@pytest.mark.asyncio
async def test_a_sequence_may_branch_into_two_final_tables_via_the_fake_port() -> None:
    port = FakeSequenceExecutionPort()
    port.seed_table(
        tenant_id=TENANT_ID,
        reference_id=RAW_TABLE_ID,
        kind="raw",
        rows=RAW_ROWS,
        columns=("email", "amount"),
    )
    sequence = Sequence.create(
        sequence_id=SEQUENCE_ID,
        tenant_id=TENANT_ID,
        dataset_workspace_id=DATASET_WORKSPACE_ID,
        raw_table_reference=DatasetTableVersionReference(
            storage_locator="s3://fixtures/messy_orders.csv", file_format="csv"
        ),
        now=NOW,
    )

    root_table_id = await run_step(
        sequence,
        port,
        input_reference=None,
        operation_kind="drop_nulls",
        operation_parameters={"columns": ["email"]},
    )
    assert root_table_id is not None
    root_ref = SequenceTableReference(
        tenant_id=TENANT_ID, reference_id=root_table_id, kind="prepared"
    )

    branch_a = await run_step(
        sequence,
        port,
        input_reference=root_ref,
        operation_kind="dedupe",
        operation_parameters={},
    )
    branch_b = await run_step(
        sequence,
        port,
        input_reference=root_ref,
        operation_kind="rename_column",
        operation_parameters={"from_name": "amount", "to_name": "amount_raw"},
    )
    assert branch_a is not None
    assert branch_b is not None
    assert branch_a != branch_b

    sequence.mark_final(branch_a)
    sequence.mark_final(branch_b)
    assert sequence.final_table_ids == {branch_a, branch_b}

    with pytest.raises(SequenceTransitionError):
        sequence.mark_final(UUID(int=0))
