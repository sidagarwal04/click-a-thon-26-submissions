from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceExecutionPort,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("60000000-0000-0000-0000-000000000001")
STEP_ID = UUID("60000000-0000-0000-0000-000000000002")
TABLE_ID = UUID("60000000-0000-0000-0000-000000000003")


def _request(**overrides: object) -> SequenceStepExecutionRequest:
    fields: dict[str, object] = {
        "tenant_id": TENANT_ID,
        "sequence_id": SEQUENCE_ID,
        "step_id": STEP_ID,
        "operation_kind": "drop_nulls",
        "operation_parameters": {"columns": ["email"], "strategy": "any"},
        "input_table": SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=TABLE_ID, kind="raw"
        ),
    }
    fields.update(overrides)
    return SequenceStepExecutionRequest(**fields)


def test_request_is_frozen_and_forbids_unknown_fields() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        SequenceStepExecutionRequest(**{**request.model_dump(), "unexpected": 1})

    with pytest.raises(Exception):  # noqa: B017 - frozen models raise pydantic's own error
        request.step_id = STEP_ID  # type: ignore[misc]


def test_table_reference_is_scoped_and_tagged() -> None:
    reference = SequenceTableReference(
        tenant_id=TENANT_ID, reference_id=TABLE_ID, kind="prepared"
    )
    assert reference.kind == "prepared"


def test_success_result_carries_the_new_table_and_metadata() -> None:
    result = SequenceStepExecutionResult(
        request=_request(),
        output_table=SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=TABLE_ID, kind="prepared"
        ),
        row_count=41,
        columns=("email", "amount"),
    )
    assert result.row_count == 41
    assert result.columns == ("email", "amount")


def test_failure_carries_a_typed_reason_not_free_text() -> None:
    failure = SequenceStepExecutionFailure(
        request=_request(),
        reason=SequenceExecutionFailureReason.DATA_INCOMPATIBLE,
        detail="column 'amount' is not numeric",
    )
    assert failure.reason is SequenceExecutionFailureReason.DATA_INCOMPATIBLE


def test_port_is_a_protocol_with_one_apply_operation_method() -> None:
    assert hasattr(SequenceExecutionPort, "apply_operation")
