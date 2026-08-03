from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)

from zentra_domain_sequence.testing import assert_port_satisfies_contract

from .fakes import FakeSequenceExecutionPort

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
OTHER_TENANT_ID = UUID("20000000-0000-0000-0000-000000000009")
SEQUENCE_ID = UUID("63000000-0000-0000-0000-000000000001")
RAW_TABLE_ID = UUID("63000000-0000-0000-0000-000000000002")

RAW_ROWS = [
    {"email": "a@example.com", "amount": "10"},
    {"email": None, "amount": "20"},
    {"email": "a@example.com", "amount": "10"},
    {"email": "b@example.com", "amount": "not-a-number"},
]


def seeded_port() -> FakeSequenceExecutionPort:
    port = FakeSequenceExecutionPort()
    port.seed_table(
        tenant_id=TENANT_ID,
        reference_id=RAW_TABLE_ID,
        kind="raw",
        rows=RAW_ROWS,
        columns=("email", "amount"),
    )
    return port


def request(
    *, operation_kind: str, operation_parameters: dict, table_id: UUID = RAW_TABLE_ID
):
    return SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=UUID(int=1),
        operation_kind=operation_kind,
        operation_parameters=operation_parameters,
        input_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=table_id, kind="raw"
        ),
    )


@pytest.mark.asyncio
async def test_drop_nulls_removes_null_rows() -> None:
    port = seeded_port()
    result = await port.apply_operation(
        request(
            operation_kind="drop_nulls", operation_parameters={"columns": ["email"]}
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 3


@pytest.mark.asyncio
async def test_dedupe_collapses_duplicate_rows() -> None:
    port = seeded_port()
    result = await port.apply_operation(
        request(operation_kind="dedupe", operation_parameters={})
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 3


@pytest.mark.asyncio
async def test_filter_rows_applies_the_predicate() -> None:
    port = seeded_port()
    result = await port.apply_operation(
        request(
            operation_kind="filter_rows",
            operation_parameters={
                "column": "email",
                "operator": "eq",
                "value": "a@example.com",
            },
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 2


@pytest.mark.asyncio
async def test_rename_column_renames() -> None:
    port = seeded_port()
    result = await port.apply_operation(
        request(
            operation_kind="rename_column",
            operation_parameters={"from_name": "amount", "to_name": "amount_raw"},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.columns == ("email", "amount_raw")


@pytest.mark.asyncio
async def test_cast_type_changes_column_type() -> None:
    port = FakeSequenceExecutionPort()
    port.seed_table(
        tenant_id=TENANT_ID,
        reference_id=RAW_TABLE_ID,
        kind="raw",
        rows=[{"email": "a@example.com", "amount": "10"}],
        columns=("email", "amount"),
    )
    result = await port.apply_operation(
        request(
            operation_kind="cast_type",
            operation_parameters={"column": "amount", "target_type": "int"},
        )
    )
    assert isinstance(result, SequenceStepExecutionResult)


@pytest.mark.asyncio
async def test_cast_type_on_incompatible_data_is_a_typed_failure_not_an_exception() -> (
    None
):
    port = seeded_port()
    result = await port.apply_operation(
        request(
            operation_kind="cast_type",
            operation_parameters={"column": "amount", "target_type": "int"},
        )
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.DATA_INCOMPATIBLE


@pytest.mark.asyncio
async def test_unknown_operation_name_is_a_catalog_violation_failure() -> None:
    port = seeded_port()
    result = await port.apply_operation(
        request(operation_kind="drop_table", operation_parameters={})
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.CATALOG_VIOLATION


@pytest.mark.asyncio
async def test_unknown_table_reference_is_a_typed_failure() -> None:
    port = FakeSequenceExecutionPort()
    result = await port.apply_operation(
        request(
            operation_kind="drop_nulls",
            operation_parameters={"columns": ["email"]},
            table_id=UUID(int=999),
        )
    )
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.UNKNOWN_TABLE


@pytest.mark.asyncio
async def test_tenant_scoping_fails_closed_for_the_wrong_tenant() -> None:
    port = seeded_port()
    wrong_tenant_request = SequenceStepExecutionRequest(
        tenant_id=OTHER_TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=UUID(int=1),
        operation_kind="drop_nulls",
        operation_parameters={"columns": ["email"]},
        input_table=SequenceTableReference(
            tenant_id=OTHER_TENANT_ID, reference_id=RAW_TABLE_ID, kind="raw"
        ),
    )
    result = await port.apply_operation(wrong_tenant_request)
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.UNKNOWN_TABLE


@pytest.mark.asyncio
async def test_fake_port_satisfies_the_shared_contract_suite() -> None:
    port = FakeSequenceExecutionPort()

    def seed_raw_table(*, rows: list[dict], columns: tuple[str, ...]):
        reference_id = uuid4()
        port.seed_table(
            tenant_id=TENANT_ID,
            reference_id=reference_id,
            kind="raw",
            rows=rows,
            columns=columns,
        )
        return SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=reference_id, kind="raw"
        )

    await assert_port_satisfies_contract(
        apply_operation=port.apply_operation,
        seed_raw_table=seed_raw_table,
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
    )
