"""End-to-end proof against a deliberately messy fixture: a real multi-step
chain, through the real chDB adapter, for both Raw Table origins — an
uploaded file (Data Source) and a live ClickHouse table (Connector)."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4

import clickhouse_connect
import pytest
from zentra_domain_agent_execution import (
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)
from zentra_domain_sequence import (
    ConnectorSourceTableReference,
    DatasetTableVersionReference,
)

from zentra_adapter_sequence_execution.chdb_execution import ChdbSequenceExecutionPort
from zentra_adapter_sequence_execution.raw_table import ConnectorClickHouseConnection

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "messy_orders.csv"

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("67000000-0000-0000-0000-000000000001")

CLICKHOUSE_HOST = os.getenv("TEST_CLICKHOUSE_HOST")
CLICKHOUSE_NATIVE_PORT = int(os.getenv("TEST_CLICKHOUSE_NATIVE_PORT", "9000"))
CLICKHOUSE_HTTP_PORT = int(os.getenv("TEST_CLICKHOUSE_PORT", "8123"))


class _FixedRawTableLookup:
    def __init__(self, reference) -> None:
        self._reference = reference

    async def resolve(self, *, tenant_id, sequence_id):
        del tenant_id, sequence_id
        return self._reference


async def _run_chain(
    port: ChdbSequenceExecutionPort, *, first_input: SequenceTableReference
) -> SequenceStepExecutionResult:
    step_1 = await port.apply_operation(
        SequenceStepExecutionRequest(
            tenant_id=TENANT_ID,
            sequence_id=SEQUENCE_ID,
            step_id=uuid4(),
            operation_kind="drop_nulls",
            operation_parameters={"columns": ["email"]},
            input_table=first_input,
        )
    )
    assert isinstance(step_1, SequenceStepExecutionResult)

    step_2 = await port.apply_operation(
        SequenceStepExecutionRequest(
            tenant_id=TENANT_ID,
            sequence_id=SEQUENCE_ID,
            step_id=uuid4(),
            operation_kind="dedupe",
            operation_parameters={},
            input_table=step_1.output_table,
        )
    )
    assert isinstance(step_2, SequenceStepExecutionResult)

    step_3 = await port.apply_operation(
        SequenceStepExecutionRequest(
            tenant_id=TENANT_ID,
            sequence_id=SEQUENCE_ID,
            step_id=uuid4(),
            operation_kind="filter_rows",
            operation_parameters={
                "column": "amount",
                "operator": "ne",
                "value": "not-a-number",
            },
            input_table=step_2.output_table,
        )
    )
    assert isinstance(step_3, SequenceStepExecutionResult)
    return step_3


@pytest.mark.asyncio
async def test_chain_via_an_uploaded_dataset_table_version(tmp_path: Path) -> None:
    original_content = FIXTURE_PATH.read_text()
    port = ChdbSequenceExecutionPort(
        connector_clickhouse=ConnectorClickHouseConnection(
            host="localhost", port=9000, user="default", password=""
        ),
        storage_root=tmp_path,
        sequence_lookup=_FixedRawTableLookup(
            DatasetTableVersionReference(
                storage_locator=str(FIXTURE_PATH), file_format="csv"
            )
        ),
    )

    result = await _run_chain(
        port,
        first_input=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=uuid4(), kind="raw"
        ),
    )

    assert result.row_count == 3
    # The fixture on disk is exactly what it was before the chain ran.
    assert FIXTURE_PATH.read_text() == original_content


@pytest.mark.asyncio
async def test_chain_via_a_live_connector_source_table(tmp_path: Path) -> None:
    if not CLICKHOUSE_HOST:
        pytest.skip("local ClickHouse is not configured")

    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_HTTP_PORT,
        username="zentra_audit_owner",
        password="zentra_audit_owner",
        database="zentra_audit",
    )
    table_name = f"sequence_fixture_{uuid4().hex}"
    client.command(
        f"CREATE TABLE {table_name} "
        "(email Nullable(String), amount String, region Nullable(String)) "
        "ENGINE = MergeTree ORDER BY tuple()"
    )
    try:
        rows = []
        with FIXTURE_PATH.open() as handle:
            header = handle.readline()
            assert header.strip() == "email,amount,region"
            for line in handle:
                email, amount, region = line.rstrip("\n").split(",")
                rows.append((email or None, amount, region or None))
        client.insert(table_name, rows, column_names=["email", "amount", "region"])
        original_count = client.command(f"SELECT count() FROM {table_name}")

        connection = ConnectorClickHouseConnection(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_NATIVE_PORT,
            user="zentra_audit_owner",
            password="zentra_audit_owner",
        )
        port = ChdbSequenceExecutionPort(
            connector_clickhouse=connection,
            storage_root=tmp_path,
            sequence_lookup=_FixedRawTableLookup(
                ConnectorSourceTableReference(
                    catalog_version_id="cv-test",
                    source_table_name=f"zentra_audit.{table_name}",
                )
            ),
        )

        result = await _run_chain(
            port,
            first_input=SequenceTableReference(
                tenant_id=TENANT_ID, reference_id=uuid4(), kind="raw"
            ),
        )

        assert result.row_count == 3
        # Querying the live table again shows it was never mutated.
        assert client.command(f"SELECT count() FROM {table_name}") == original_count
    finally:
        client.command(f"DROP TABLE IF EXISTS {table_name}")
