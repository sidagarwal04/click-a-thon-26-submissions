from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    SequenceStepExecutionRequest,
    SequenceTableReference,
)
from zentra_domain_sequence import DatasetTableVersionReference

from zentra_adapter_sequence_execution.chdb_execution import ChdbSequenceExecutionPort
from zentra_adapter_sequence_execution.lambda_handler import build_handler
from zentra_adapter_sequence_execution.raw_table import ConnectorClickHouseConnection

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("68000000-0000-0000-0000-000000000001")


class _FixedRawTableLookup:
    def __init__(self, reference) -> None:
        self._reference = reference

    async def resolve(self, *, tenant_id, sequence_id):
        del tenant_id, sequence_id
        return self._reference


@pytest.fixture
def handler(tmp_path: Path):
    fixture = tmp_path / "raw.csv"
    fixture.write_text("email,amount\na@example.com,10\n,20\n")

    port = ChdbSequenceExecutionPort(
        connector_clickhouse=ConnectorClickHouseConnection(
            host="localhost", port=9000, user="default", password=""
        ),
        storage_root=tmp_path,
        sequence_lookup=_FixedRawTableLookup(
            DatasetTableVersionReference(
                storage_locator=str(fixture), file_format="csv"
            )
        ),
    )
    return build_handler(port)


def _event_for(request: SequenceStepExecutionRequest) -> dict:
    return {"request": request.model_dump(mode="json")}


def test_handler_executes_a_successful_operation(handler) -> None:
    request = SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=uuid4(),
        operation_kind="drop_nulls",
        operation_parameters={"columns": ["email"]},
        input_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=uuid4(), kind="raw"
        ),
    )
    response = handler(_event_for(request), context=None)
    assert response["kind"] == "result"
    assert response["row_count"] == 1


def test_handler_executes_a_typed_failure(handler) -> None:
    request = SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=uuid4(),
        operation_kind="drop_table",
        operation_parameters={},
        input_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=uuid4(), kind="raw"
        ),
    )
    response = handler(_event_for(request), context=None)
    assert response["kind"] == "failure"
    assert response["reason"] == "catalog_violation"


def test_handler_never_raises_on_a_malformed_event(handler) -> None:
    response = handler({"request": {"not": "a valid request"}}, context=None)
    assert response["kind"] == "error"
    assert "detail" in response


def test_handler_never_raises_when_the_event_has_no_request_key(handler) -> None:
    response = handler({}, context=None)
    assert response["kind"] == "error"
