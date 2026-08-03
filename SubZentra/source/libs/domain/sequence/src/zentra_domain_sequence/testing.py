"""A SequenceExecutionPort contract suite, shared by every implementation.

Any port implementation — the in-memory fake, the real chDB adapter, a
future one — must behave identically for the same inputs. This module is
the one place that contract is written down; each implementation's own test
suite calls `assert_port_satisfies_contract` rather than re-deriving it.

This is deliberately shipped as a `testing` submodule of the domain package
(not inside `tests/`, which isn't part of the installed package and so isn't
importable across package boundaries) — a common pattern for a package that
wants to hand its consumers a way to verify their own port implementations.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Protocol
from uuid import UUID, uuid4

from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)

Row = dict[str, object]


class SeedRawTable(Protocol):
    def __call__(
        self, *, rows: list[Row], columns: tuple[str, ...]
    ) -> SequenceTableReference: ...


class ApplyOperation(Protocol):
    def __call__(
        self, request: SequenceStepExecutionRequest
    ) -> Awaitable[SequenceStepExecutionResult | SequenceStepExecutionFailure]: ...


def _request(
    *,
    tenant_id: UUID,
    sequence_id: UUID,
    input_table: SequenceTableReference,
    operation_kind: str,
    operation_parameters: dict,
) -> SequenceStepExecutionRequest:
    return SequenceStepExecutionRequest(
        tenant_id=tenant_id,
        sequence_id=sequence_id,
        step_id=uuid4(),
        operation_kind=operation_kind,
        operation_parameters=operation_parameters,
        input_table=input_table,
    )


async def assert_port_satisfies_contract(
    *,
    apply_operation: ApplyOperation,
    seed_raw_table: SeedRawTable,
    tenant_id: UUID,
    sequence_id: UUID,
) -> None:
    """Runs the same assertions against any SequenceExecutionPort
    implementation, driven only through its public `apply_operation` and a
    caller-supplied way to seed a Raw Table for that implementation."""

    # drop_nulls: keeps only rows with no null in the given columns.
    table = seed_raw_table(
        rows=[
            {"email": "a@example.com", "amount": 10},
            {"email": None, "amount": 20},
        ],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="drop_nulls",
            operation_parameters={"columns": ["email"]},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 1

    # dedupe: collapses exact duplicate rows.
    table = seed_raw_table(
        rows=[
            {"email": "a@example.com", "amount": 10},
            {"email": "a@example.com", "amount": 10},
        ],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="dedupe",
            operation_parameters={},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 1

    # filter_rows: keeps only rows matching the predicate.
    table = seed_raw_table(
        rows=[
            {"email": "a@example.com", "amount": 10},
            {"email": "b@example.com", "amount": 20},
        ],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="filter_rows",
            operation_parameters={"column": "amount", "operator": "gt", "value": 15},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 1

    # rename_column: the new name appears, the old one doesn't.
    table = seed_raw_table(
        rows=[{"email": "a@example.com", "amount": 10}],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="rename_column",
            operation_parameters={"from_name": "amount", "to_name": "amount_raw"},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert set(result.columns) == {"email", "amount_raw"}

    # cast_type: succeeds against compatible data.
    table = seed_raw_table(
        rows=[{"email": "a@example.com", "amount": 10}],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="cast_type",
            operation_parameters={"column": "amount", "target_type": "float"},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)

    # cast_type against incompatible data: a typed failure, never a crash.
    table = seed_raw_table(
        rows=[{"email": "a@example.com", "amount": "not-a-number"}],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="cast_type",
            operation_parameters={"column": "amount", "target_type": "int"},
        )
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.DATA_INCOMPATIBLE

    # cast_type to a target_type the catalog's own validation doesn't
    # constrain (target_type is an open string) but no adapter actually
    # supports: still a typed failure, never an unhandled exception.
    table = seed_raw_table(
        rows=[{"email": "a@example.com", "amount": 10}],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="cast_type",
            operation_parameters={"column": "amount", "target_type": "datetime"},
        )
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.DATA_INCOMPATIBLE

    # An operation name outside the closed catalog is a typed failure.
    table = seed_raw_table(
        rows=[{"email": "a@example.com", "amount": 10}],
        columns=("email", "amount"),
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=table,
            operation_kind="drop_table",
            operation_parameters={},
        )
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.CATALOG_VIOLATION

    # An unknown input table reference is a typed failure, not an exception.
    unknown_table = SequenceTableReference(
        tenant_id=tenant_id, reference_id=uuid4(), kind="prepared"
    )
    result = await apply_operation(
        _request(
            tenant_id=tenant_id,
            sequence_id=sequence_id,
            input_table=unknown_table,
            operation_kind="dedupe",
            operation_parameters={},
        )
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.UNKNOWN_TABLE
