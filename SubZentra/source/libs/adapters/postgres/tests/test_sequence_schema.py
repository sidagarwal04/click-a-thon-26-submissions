from sqlalchemy import CheckConstraint, UniqueConstraint

from zentra_adapter_postgres.schema import (
    prepared_tables,
    sequence_final_tables,
    sequence_runs,
    sequence_steps,
    sequences,
)


def _unique_names(table) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _fk_targets(table) -> set[tuple[str, ...]]:
    return {
        tuple(element.target_fullname for element in constraint.elements)
        for constraint in table.foreign_key_constraints
    }


def test_every_table_is_tenant_scoped() -> None:
    for table in (
        sequences,
        sequence_steps,
        prepared_tables,
        sequence_runs,
        sequence_final_tables,
    ):
        assert "tenant_id" in table.c, f"{table.name} has no tenant_id column"


def test_sequences_carries_its_own_tenant_identity_for_children_to_target() -> None:
    assert "uq_sequences_tenant_identity" in _unique_names(sequences)


def test_sequence_steps_are_tenant_scoped_to_their_sequence() -> None:
    assert ("sequences.sequence_id", "sequences.tenant_id") in _fk_targets(
        sequence_steps
    )
    assert "uq_sequence_steps_tenant_identity" in _unique_names(sequence_steps)


def test_prepared_tables_are_tenant_scoped_to_their_sequence_and_step() -> None:
    fk_targets = _fk_targets(prepared_tables)
    assert ("sequences.sequence_id", "sequences.tenant_id") in fk_targets
    assert ("sequence_steps.step_id", "sequence_steps.tenant_id") in fk_targets
    assert "uq_prepared_tables_tenant_identity" in _unique_names(prepared_tables)


def test_prepared_tables_self_reference_their_parent_for_lineage() -> None:
    fk_targets = _fk_targets(prepared_tables)
    assert ("prepared_tables.prepared_table_id", "prepared_tables.tenant_id") in (
        fk_targets
    )


def test_sequence_runs_are_tenant_scoped_to_their_sequence() -> None:
    assert ("sequences.sequence_id", "sequences.tenant_id") in _fk_targets(
        sequence_runs
    )


def test_sequence_runs_encode_a_typed_succeeded_or_failed_outcome() -> None:
    check_names = {
        constraint.name
        for constraint in sequence_runs.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_sequence_runs_typed_outcome" in check_names
    assert "ck_sequence_runs_outcome_kind" in check_names


def test_sequence_final_tables_is_a_join_table_scoped_to_both_parents() -> None:
    fk_targets = _fk_targets(sequence_final_tables)
    assert ("sequences.sequence_id", "sequences.tenant_id") in fk_targets
    assert (
        "prepared_tables.prepared_table_id",
        "prepared_tables.tenant_id",
    ) in fk_targets


def test_sequence_steps_operation_kind_is_constrained_to_the_typed_catalog() -> None:
    check = next(
        constraint
        for constraint in sequence_steps.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_sequence_steps_operation_kind"
    )
    body = str(check.sqltext)
    for operation in (
        "drop_nulls",
        "cast_type",
        "dedupe",
        "filter_rows",
        "rename_column",
    ):
        assert operation in body


def test_prepared_tables_row_count_cannot_be_negative() -> None:
    assert isinstance(prepared_tables, object)  # sanity: table constructed at all
    check_names = {
        constraint.name
        for constraint in prepared_tables.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_prepared_tables_row_count" in check_names
