from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)
from zentra_domain_sequence import DatasetTableVersionReference

from zentra_adapter_sequence_execution.chdb_execution import ChdbSequenceExecutionPort
from zentra_adapter_sequence_execution.raw_table import ConnectorClickHouseConnection

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("65000000-0000-0000-0000-000000000001")

CONNECTION = ConnectorClickHouseConnection(
    host="localhost", port=9000, user="default", password=""
)


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def port(storage_root: Path) -> ChdbSequenceExecutionPort:
    return ChdbSequenceExecutionPort(
        connector_clickhouse=CONNECTION,
        storage_root=storage_root,
        sequence_lookup=None,
    )


def _write_fixture(path: Path, content: str) -> None:
    path.write_text(content)


def _raw_request(
    *, operation_kind: str, operation_parameters: dict, raw_table_id: UUID
) -> SequenceStepExecutionRequest:
    return SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=uuid4(),
        operation_kind=operation_kind,
        operation_parameters=operation_parameters,
        input_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=raw_table_id, kind="raw"
        ),
    )


class _StubRawTableLookup:
    """Stands in for the Postgres-backed Sequence lookup: kind="raw" always
    resolves to a fixed local CSV file, since ticket #51's business logic is
    tested in-process, not through a real database."""

    def __init__(self, reference) -> None:
        self._reference = reference

    async def resolve(self, *, tenant_id, sequence_id) -> object:
        del tenant_id, sequence_id
        return self._reference


@pytest.mark.asyncio
async def test_drop_nulls_removes_null_rows_via_chdb(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(fixture, "email,amount\na@example.com,10\n,20\na@example.com,10\n")
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    request = _raw_request(
        operation_kind="drop_nulls",
        operation_parameters={"columns": ["email"]},
        raw_table_id=uuid4(),
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 2


@pytest.mark.asyncio
async def test_dedupe_collapses_duplicate_rows_via_chdb(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(
        fixture, "email,amount\na@example.com,10\na@example.com,10\nb@example.com,5\n"
    )
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    request = _raw_request(
        operation_kind="dedupe", operation_parameters={}, raw_table_id=uuid4()
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 2


@pytest.mark.asyncio
async def test_filter_rows_applies_the_predicate_via_chdb(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(
        fixture,
        "email,amount\na@example.com,10\nb@example.com,20\nc@example.com,30\n",
    )
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    request = _raw_request(
        operation_kind="filter_rows",
        operation_parameters={"column": "amount", "operator": "gt", "value": 15},
        raw_table_id=uuid4(),
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 2


@pytest.mark.asyncio
async def test_rename_column_renames_via_chdb(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(fixture, "email,amount\na@example.com,10\n")
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    request = _raw_request(
        operation_kind="rename_column",
        operation_parameters={"from_name": "amount", "to_name": "amount_raw"},
        raw_table_id=uuid4(),
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionResult)
    assert set(result.columns) == {"email", "amount_raw"}


@pytest.mark.asyncio
async def test_cast_type_changes_column_type_via_chdb(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(fixture, "email,amount\na@example.com,10\n")
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    request = _raw_request(
        operation_kind="cast_type",
        operation_parameters={"column": "amount", "target_type": "float"},
        raw_table_id=uuid4(),
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 1


@pytest.mark.asyncio
async def test_cast_type_on_incompatible_data_is_a_typed_failure(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(fixture, "email,amount\na@example.com,not-a-number\n")
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    request = _raw_request(
        operation_kind="cast_type",
        operation_parameters={"column": "amount", "target_type": "int"},
        raw_table_id=uuid4(),
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.DATA_INCOMPATIBLE


@pytest.mark.asyncio
async def test_chained_steps_read_the_prior_prepared_table_not_the_raw_one(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    _write_fixture(fixture, "email,amount\na@example.com,10\n,20\n")
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    first = await port.apply_operation(
        _raw_request(
            operation_kind="drop_nulls",
            operation_parameters={"columns": ["email"]},
            raw_table_id=uuid4(),
        )
    )
    assert isinstance(first, SequenceStepExecutionResult)

    second_request = SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=uuid4(),
        operation_kind="dedupe",
        operation_parameters={},
        input_table=first.output_table,
    )
    second = await port.apply_operation(second_request)
    assert isinstance(second, SequenceStepExecutionResult)
    assert second.row_count == 1


@pytest.mark.asyncio
async def test_a_raw_table_is_never_mutated(
    port: ChdbSequenceExecutionPort, storage_root: Path
) -> None:
    fixture = storage_root / "raw.csv"
    original_content = "email,amount\na@example.com,10\n,20\n"
    _write_fixture(fixture, original_content)
    port._sequence_lookup = _StubRawTableLookup(
        DatasetTableVersionReference(storage_locator=str(fixture), file_format="csv")
    )

    await port.apply_operation(
        _raw_request(
            operation_kind="drop_nulls",
            operation_parameters={"columns": ["email"]},
            raw_table_id=uuid4(),
        )
    )

    assert fixture.read_text() == original_content


@pytest.mark.asyncio
async def test_unknown_prepared_table_reference_is_a_typed_failure(
    port: ChdbSequenceExecutionPort,
) -> None:
    request = SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=uuid4(),
        operation_kind="dedupe",
        operation_parameters={},
        input_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=uuid4(), kind="prepared"
        ),
    )
    result = await port.apply_operation(request)
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.UNKNOWN_TABLE
