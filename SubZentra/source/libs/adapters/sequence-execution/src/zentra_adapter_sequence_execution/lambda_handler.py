"""The Lambda entrypoint wrapping ChdbSequenceExecutionPort.

`handler` is the only thing AWS Lambda calls. It never re-implements
transform logic (that's chdb_execution.py, ticket #51's own business logic,
unchanged here) and never lets a raw exception or traceback escape to the
caller — a malformed event or an unexpected internal error both come back
as a typed `{"kind": "error", ...}` response, the same way a Lambda cold
start with no prior invocations would.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from zentra_domain_agent_execution import (
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
)

from .chdb_execution import ChdbSequenceExecutionPort

Handler = Callable[[dict[str, Any], Any], dict[str, Any]]


def _result_to_response(result: SequenceStepExecutionResult) -> dict[str, Any]:
    return {
        "kind": "result",
        "output_table": result.output_table.model_dump(mode="json"),
        "row_count": result.row_count,
        "columns": list(result.columns),
    }


def _failure_to_response(failure: SequenceStepExecutionFailure) -> dict[str, Any]:
    return {
        "kind": "failure",
        "reason": failure.reason.value,
        "detail": failure.detail,
    }


def build_handler(port: ChdbSequenceExecutionPort) -> Handler:
    """Builds a Lambda handler bound to one ChdbSequenceExecutionPort
    instance, constructed once per cold start and reused across warm
    invocations within the same microVM. The port itself holds no
    cross-invocation Tenant-scoped cache, so no Tenant data persists between
    invocations — only the immutable connection/storage configuration does.
    """

    def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
        del context
        try:
            raw_request = event["request"]
        except (KeyError, TypeError) as error:
            return {
                "kind": "error",
                "detail": f"Event has no 'request' payload: {error}",
            }

        try:
            request = SequenceStepExecutionRequest.model_validate(raw_request)
        except ValidationError as error:
            return {"kind": "error", "detail": str(error)}

        try:
            result = asyncio.run(port.apply_operation(request))
        except Exception as error:  # a handler must never propagate a raw traceback
            return {"kind": "error", "detail": str(error)}

        if isinstance(result, SequenceStepExecutionResult):
            return _result_to_response(result)
        return _failure_to_response(result)

    return handler
