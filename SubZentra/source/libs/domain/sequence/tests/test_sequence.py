from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
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
    SequenceTransitionError,
    build_sequence_operation,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
OTHER_TENANT_ID = UUID("20000000-0000-0000-0000-000000000009")
SEQUENCE_ID = UUID("62000000-0000-0000-0000-000000000001")
DATASET_WORKSPACE_ID = UUID("62000000-0000-0000-0000-000000000002")

RAW_TABLE = DatasetTableVersionReference(
    storage_locator="s3://fixtures/messy_orders.csv", file_format="csv"
)


def new_sequence() -> Sequence:
    return Sequence.create(
        sequence_id=SEQUENCE_ID,
        tenant_id=TENANT_ID,
        dataset_workspace_id=DATASET_WORKSPACE_ID,
        raw_table_reference=RAW_TABLE,
        now=NOW,
    )


def prepared_table(
    *, prepared_table_id: UUID, step_id: UUID, parent: SequenceTableReference | None
) -> PreparedTable:
    return PreparedTable(
        prepared_table_id=prepared_table_id,
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=step_id,
        parent_table_reference=parent,
        row_count=10,
        columns=("email", "amount"),
        created_at=NOW,
    )


def step(
    *, step_id: UUID, input_reference: SequenceTableReference | None, produced: UUID
) -> SequenceStep:
    return SequenceStep(
        step_id=step_id,
        sequence_id=SEQUENCE_ID,
        tenant_id=TENANT_ID,
        operation=build_sequence_operation("drop_nulls", {"columns": ["email"]}),
        input_reference=input_reference,
        produced_table_id=produced,
        created_at=NOW,
    )


def test_multi_step_lineage_chains_parent_to_child_correctly() -> None:
    sequence = new_sequence()
    step_1_id, table_1_id = UUID(int=1), UUID(int=2)
    step_2_id, table_2_id = UUID(int=3), UUID(int=4)

    table_1 = prepared_table(
        prepared_table_id=table_1_id, step_id=step_1_id, parent=None
    )
    sequence.append_step(
        step(step_id=step_1_id, input_reference=None, produced=table_1_id), table_1
    )

    table_1_ref = SequenceTableReference(
        tenant_id=TENANT_ID, reference_id=table_1_id, kind="prepared"
    )
    table_2 = prepared_table(
        prepared_table_id=table_2_id, step_id=step_2_id, parent=table_1_ref
    )
    sequence.append_step(
        step(step_id=step_2_id, input_reference=table_1_ref, produced=table_2_id),
        table_2,
    )

    lineage = sequence.lineage_for(table_2_id)
    assert [table.prepared_table_id for table in lineage] == [table_1_id, table_2_id]


def test_prepared_tables_are_append_only() -> None:
    sequence = new_sequence()
    assert isinstance(sequence.prepared_tables, tuple)
    step_id, table_id = UUID(int=1), UUID(int=2)
    table = prepared_table(prepared_table_id=table_id, step_id=step_id, parent=None)
    sequence.append_step(
        step(step_id=step_id, input_reference=None, produced=table_id), table
    )
    assert sequence.prepared_tables == (table,)
    assert isinstance(sequence.prepared_tables, tuple)


def test_final_table_can_be_marked_and_unmarked() -> None:
    sequence = new_sequence()
    step_id, table_id = UUID(int=1), UUID(int=2)
    table = prepared_table(prepared_table_id=table_id, step_id=step_id, parent=None)
    sequence.append_step(
        step(step_id=step_id, input_reference=None, produced=table_id), table
    )

    sequence.mark_final(table_id)
    assert table_id in sequence.final_table_ids

    sequence.unmark_final(table_id)
    assert table_id not in sequence.final_table_ids


def test_marking_an_unrelated_table_final_is_rejected() -> None:
    sequence = new_sequence()
    with pytest.raises(SequenceTransitionError):
        sequence.mark_final(UUID(int=999))


def test_appending_a_step_whose_input_is_not_in_this_sequence_is_rejected() -> None:
    sequence = new_sequence()
    dangling_reference = SequenceTableReference(
        tenant_id=TENANT_ID, reference_id=UUID(int=777), kind="prepared"
    )
    step_id, table_id = UUID(int=1), UUID(int=2)
    table = prepared_table(
        prepared_table_id=table_id, step_id=step_id, parent=dangling_reference
    )
    with pytest.raises(SequenceTransitionError):
        sequence.append_step(
            step(
                step_id=step_id, input_reference=dangling_reference, produced=table_id
            ),
            table,
        )
    assert sequence.prepared_tables == ()


def test_a_sequence_may_branch_into_multiple_final_tables() -> None:
    sequence = new_sequence()
    root_step_id, root_table_id = UUID(int=1), UUID(int=2)
    root_table = prepared_table(
        prepared_table_id=root_table_id, step_id=root_step_id, parent=None
    )
    sequence.append_step(
        step(step_id=root_step_id, input_reference=None, produced=root_table_id),
        root_table,
    )
    root_ref = SequenceTableReference(
        tenant_id=TENANT_ID, reference_id=root_table_id, kind="prepared"
    )

    branch_a_step, branch_a_table = UUID(int=10), UUID(int=11)
    branch_a = prepared_table(
        prepared_table_id=branch_a_table, step_id=branch_a_step, parent=root_ref
    )
    sequence.append_step(
        step(step_id=branch_a_step, input_reference=root_ref, produced=branch_a_table),
        branch_a,
    )

    branch_b_step, branch_b_table = UUID(int=20), UUID(int=21)
    branch_b = prepared_table(
        prepared_table_id=branch_b_table, step_id=branch_b_step, parent=root_ref
    )
    sequence.append_step(
        step(step_id=branch_b_step, input_reference=root_ref, produced=branch_b_table),
        branch_b,
    )

    sequence.mark_final(branch_a_table)
    sequence.mark_final(branch_b_table)

    assert sequence.final_table_ids == {branch_a_table, branch_b_table}
    assert [t.prepared_table_id for t in sequence.lineage_for(branch_a_table)] == [
        root_table_id,
        branch_a_table,
    ]
    assert [t.prepared_table_id for t in sequence.lineage_for(branch_b_table)] == [
        root_table_id,
        branch_b_table,
    ]


def test_a_failed_run_is_recorded_without_producing_a_table() -> None:
    sequence = new_sequence()
    run = SequenceRun(
        run_id=UUID(int=1),
        sequence_id=SEQUENCE_ID,
        tenant_id=TENANT_ID,
        step_id=UUID(int=2),
        outcome=SequenceRunFailed(
            reason=SequenceExecutionFailureReason.DATA_INCOMPATIBLE,
            detail="column 'amount' is not numeric",
        ),
        attempted_at=NOW,
    )
    sequence.record_run(run)

    assert sequence.runs == (run,)
    assert sequence.prepared_tables == ()


def test_record_run_rejects_a_run_from_another_tenant_or_sequence() -> None:
    sequence = new_sequence()
    foreign_run = SequenceRun(
        run_id=UUID(int=1),
        sequence_id=SEQUENCE_ID,
        tenant_id=OTHER_TENANT_ID,
        step_id=UUID(int=2),
        outcome=SequenceRunSucceeded(produced_table_id=UUID(int=3)),
        attempted_at=NOW,
    )
    with pytest.raises(SequenceTransitionError):
        sequence.record_run(foreign_run)


def test_sequence_create_sets_created_and_updated_timestamps() -> None:
    sequence = new_sequence()
    assert sequence.created_at == NOW
    assert sequence.updated_at == NOW

    later = NOW + timedelta(minutes=1)
    step_id, table_id = UUID(int=1), UUID(int=2)
    table = prepared_table(prepared_table_id=table_id, step_id=step_id, parent=None)
    table = dataclasses.replace(table, created_at=later)
    sequence.append_step(
        step(step_id=step_id, input_reference=None, produced=table_id), table
    )
    assert sequence.updated_at == later
