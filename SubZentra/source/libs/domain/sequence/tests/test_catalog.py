from __future__ import annotations

import pytest
from pydantic import ValidationError

from zentra_domain_sequence import (
    CastTypeParameters,
    DedupeParameters,
    DropNullsParameters,
    FilterRowsParameters,
    RenameColumnParameters,
    SequenceOperationKind,
    SequenceOperationValidationError,
    UnknownSequenceOperationError,
    build_sequence_operation,
)


def test_catalog_is_exactly_the_five_v1_operations() -> None:
    assert {kind.value for kind in SequenceOperationKind} == {
        "drop_nulls",
        "cast_type",
        "dedupe",
        "filter_rows",
        "rename_column",
    }


def test_drop_nulls_requires_at_least_one_column() -> None:
    operation = build_sequence_operation(
        "drop_nulls", {"columns": ["email"], "strategy": "any"}
    )
    assert isinstance(operation, DropNullsParameters)
    assert operation.columns == ("email",)

    with pytest.raises(ValidationError):
        DropNullsParameters(columns=(), strategy="any")


def test_cast_type_requires_column_and_target_type() -> None:
    operation = build_sequence_operation(
        "cast_type", {"column": "amount", "target_type": "int"}
    )
    assert isinstance(operation, CastTypeParameters)
    assert operation.column == "amount"
    assert operation.target_type == "int"

    with pytest.raises(SequenceOperationValidationError):
        build_sequence_operation("cast_type", {"column": "amount"})


def test_dedupe_defaults_to_all_columns() -> None:
    operation = build_sequence_operation("dedupe", {})
    assert isinstance(operation, DedupeParameters)
    assert operation.columns == ()


def test_filter_rows_requires_column_operator_and_value() -> None:
    operation = build_sequence_operation(
        "filter_rows",
        {"column": "region", "operator": "eq", "value": "NA"},
    )
    assert isinstance(operation, FilterRowsParameters)
    assert operation.operator == "eq"


def test_rename_column_requires_from_and_to_names() -> None:
    operation = build_sequence_operation(
        "rename_column", {"from_name": "amt", "to_name": "amount"}
    )
    assert isinstance(operation, RenameColumnParameters)
    assert operation.to_name == "amount"


def test_unknown_operation_name_is_rejected() -> None:
    with pytest.raises(UnknownSequenceOperationError, match="drop_table"):
        build_sequence_operation("drop_table", {})


def test_malformed_parameters_are_rejected_with_a_typed_error() -> None:
    with pytest.raises(SequenceOperationValidationError):
        build_sequence_operation("rename_column", {"from_name": "amt"})
