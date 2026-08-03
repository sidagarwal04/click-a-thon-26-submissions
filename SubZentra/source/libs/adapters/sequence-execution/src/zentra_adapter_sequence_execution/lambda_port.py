"""The production SequenceExecutionPort: invokes the deployed Lambda.

Never lets a raw botocore exception, or a Lambda-reported unhandled
exception, escape the port boundary — both become a typed
EXECUTION_ERROR failure, distinct from the three data/catalog failure
reasons chdb_execution.py itself produces.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)


class LambdaClient(Protocol):
    def invoke(self, *, FunctionName: str, Payload: bytes) -> dict[str, Any]: ...  # noqa: N803


def _response_to_outcome(
    request: SequenceStepExecutionRequest, body: dict[str, Any]
) -> SequenceStepExecutionResult | SequenceStepExecutionFailure:
    if body.get("kind") == "result":
        return SequenceStepExecutionResult(
            request=request,
            output_table=SequenceTableReference(**body["output_table"]),
            row_count=body["row_count"],
            columns=tuple(body["columns"]),
        )
    if body.get("kind") == "failure":
        return SequenceStepExecutionFailure(
            request=request,
            reason=SequenceExecutionFailureReason(body["reason"]),
            detail=body["detail"],
        )
    # "error" (a malformed event) or an unrecognised shape — both are the
    # handler failing to do its job, not a data or catalog problem.
    return SequenceStepExecutionFailure(
        request=request,
        reason=SequenceExecutionFailureReason.EXECUTION_ERROR,
        detail=body.get("detail", str(body)),
    )


class LambdaSequenceExecutionPort:
    def __init__(self, *, lambda_client: LambdaClient, function_name: str) -> None:
        self._lambda_client = lambda_client
        self._function_name = function_name

    async def apply_operation(
        self, request: SequenceStepExecutionRequest
    ) -> SequenceStepExecutionResult | SequenceStepExecutionFailure:
        payload = json.dumps({"request": request.model_dump(mode="json")}).encode()

        try:
            # boto3's client is synchronous; run it off the event loop so
            # one slow invocation doesn't block every other in-flight one.
            response = await asyncio.to_thread(
                self._lambda_client.invoke,
                FunctionName=self._function_name,
                Payload=payload,
            )
        except Exception as error:
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.EXECUTION_ERROR,
                detail=str(error),
            )

        body = json.loads(response["Payload"].read())

        if response.get("FunctionError"):
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.EXECUTION_ERROR,
                detail=body.get("errorMessage", str(body)),
            )

        return _response_to_outcome(request, body)
