from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)

from zentra_adapter_sequence_execution.lambda_port import LambdaSequenceExecutionPort

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("69000000-0000-0000-0000-000000000001")


class _Payload:
    """Stands in for botocore's StreamingBody: invoke()'s response Payload
    exposes a .read() returning bytes, nothing else this port uses."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body


class _FakeLambdaClient:
    """An in-memory stand-in for boto3's Lambda client, matching the port's
    single call shape exactly, as the real chDB/Postgres adapters' own fakes
    already do for their respective ports."""

    def __init__(self) -> None:
        self.invocations: list[tuple[str, dict]] = []
        self.response_body: dict | None = None
        self.function_error: str | None = None
        self.raise_error: Exception | None = None

    def invoke(self, *, FunctionName: str, Payload: bytes):  # noqa: N803
        if self.raise_error is not None:
            raise self.raise_error
        self.invocations.append((FunctionName, json.loads(Payload)))
        response: dict = {"Payload": _Payload(json.dumps(self.response_body).encode())}
        if self.function_error is not None:
            response["FunctionError"] = self.function_error
        return response


def _request() -> SequenceStepExecutionRequest:
    return SequenceStepExecutionRequest(
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
        step_id=uuid4(),
        operation_kind="drop_nulls",
        operation_parameters={"columns": ["email"]},
        input_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=uuid4(), kind="raw"
        ),
    )


@pytest.mark.asyncio
async def test_invokes_the_correct_function_with_the_request_as_payload() -> None:
    client = _FakeLambdaClient()
    client.response_body = {
        "kind": "result",
        "output_table": {
            "tenant_id": str(TENANT_ID),
            "reference_id": str(uuid4()),
            "kind": "prepared",
        },
        "row_count": 3,
        "columns": ["email", "amount"],
    }
    port = LambdaSequenceExecutionPort(
        lambda_client=client, function_name="sequence-execution"
    )

    request = _request()
    result = await port.apply_operation(request)

    assert isinstance(result, SequenceStepExecutionResult)
    assert result.row_count == 3
    assert result.columns == ("email", "amount")
    function_name, payload = client.invocations[0]
    assert function_name == "sequence-execution"
    assert payload["request"]["tenant_id"] == str(TENANT_ID)


@pytest.mark.asyncio
async def test_a_typed_failure_response_round_trips() -> None:
    client = _FakeLambdaClient()
    client.response_body = {
        "kind": "failure",
        "reason": "data_incompatible",
        "detail": "cannot cast 'x' to Int64",
    }
    port = LambdaSequenceExecutionPort(
        lambda_client=client, function_name="sequence-execution"
    )

    result = await port.apply_operation(_request())
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.DATA_INCOMPATIBLE


@pytest.mark.asyncio
async def test_a_lambda_function_error_becomes_a_typed_execution_error() -> None:
    client = _FakeLambdaClient()
    client.response_body = {"errorMessage": "boom", "errorType": "RuntimeError"}
    client.function_error = "Unhandled"
    port = LambdaSequenceExecutionPort(
        lambda_client=client, function_name="sequence-execution"
    )

    result = await port.apply_operation(_request())
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.EXECUTION_ERROR


@pytest.mark.asyncio
async def test_a_boto_invocation_error_never_escapes_the_port_boundary() -> None:
    client = _FakeLambdaClient()
    client.raise_error = TimeoutError("connection timed out")
    port = LambdaSequenceExecutionPort(
        lambda_client=client, function_name="sequence-execution"
    )

    result = await port.apply_operation(_request())
    assert isinstance(result, SequenceStepExecutionFailure)
    assert result.reason is SequenceExecutionFailureReason.EXECUTION_ERROR
    assert "connection timed out" in result.detail
