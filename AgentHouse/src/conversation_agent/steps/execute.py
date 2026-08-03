"""Step: execute — deterministic single-query runner via ClickHouse MCP."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from agno.workflow import Step
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel

from conversation_agent.models import ExecuteResult, QuerySpec
from conversation_agent.shared import run_query_via_mcp

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools

STEP_NAME = "execute"


def _parse_query_spec(content: Any) -> QuerySpec:
    if isinstance(content, QuerySpec):
        return content
    if isinstance(content, BaseModel):
        return QuerySpec.model_validate(content.model_dump())
    if isinstance(content, dict):
        return QuerySpec.model_validate(content)
    if isinstance(content, str):
        return QuerySpec.model_validate(json.loads(content))
    raise TypeError(f"Cannot parse QuerySpec from {type(content)}")


def build_step(*, mcp_tools: Optional[MCPTools] = None) -> Step:
    """Build the execute step. Reuses `mcp_tools` when provided (CLI/AgentOS)."""

    async def execute_query(step_input: StepInput) -> StepOutput:
        """Run QuerySpec.sql once via ClickHouse MCP `run_query`."""
        prior = step_input.get_step_output("generate_query")
        content = prior.content if prior is not None else step_input.previous_step_content

        try:
            spec = _parse_query_spec(content)
        except Exception as exc:  # noqa: BLE001
            result = ExecuteResult(
                sql="",
                columns=[],
                rows=[],
                row_count=0,
                error=f"Failed to parse QuerySpec: {exc}",
            )
            return StepOutput(content=result, success=False, error=result.error)

        sql = (spec.sql or "").strip()
        if not sql:
            result = ExecuteResult(
                sql="",
                columns=[],
                rows=[],
                row_count=0,
                error="QuerySpec.sql is empty",
            )
            return StepOutput(content=result, success=False, error=result.error)

        try:
            columns, rows = await run_query_via_mcp(sql, mcp_tools=mcp_tools)
            result = ExecuteResult(
                sql=sql,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                error=None,
            )
            return StepOutput(content=result, success=True)
        except Exception as exc:  # noqa: BLE001
            result = ExecuteResult(
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                error=str(exc),
            )
            return StepOutput(content=result, success=False, error=result.error)

    return Step(
        name=STEP_NAME,
        description="Execute the generated SQL once via ClickHouse MCP",
        executor=execute_query,
    )
