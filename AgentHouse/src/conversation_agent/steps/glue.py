"""Glue function steps — pack multi-prior outputs for later agents."""

from __future__ import annotations

import json
from typing import Any

from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel


def _content_to_jsonable(content: Any) -> Any:
    if content is None:
        return None
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json")
    if isinstance(content, (dict, list, str, int, float, bool)):
        return content
    return str(content)


def _step_content(step_input: StepInput, step_name: str) -> Any:
    out = step_input.get_step_output(step_name)
    if out is None:
        return None
    return _content_to_jsonable(out.content)


def pack_for_plan_visualization(step_input: StepInput) -> StepOutput:
    """Bundle original NL prompt + SchemaContext for the viz planner."""
    payload = {
        "user_question": step_input.get_input_as_string(),
        "schema_context": _step_content(step_input, "discover_schema")
        or _content_to_jsonable(step_input.previous_step_content),
    }
    return StepOutput(
        content=json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    )
