"""Step: run_analytics — execute each VizSpec in a VizPlan (or legacy VizSpec)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from agno.workflow import Step
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel

from conversation_agent.analytics import run_analytics
from conversation_agent.models import (
    ExecuteResult,
    InsightResult,
    MultiExecuteResult,
    VizPlan,
    VizSpec,
)

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools

STEP_NAME = "run_analytics"


def _parse_viz_plan(content: Any) -> VizPlan:
    """Accept VizPlan, bare VizSpec, or JSON/dict of either (backward compatible)."""
    if isinstance(content, VizPlan):
        return content
    if isinstance(content, VizSpec):
        return VizPlan(insights=[content])
    if isinstance(content, BaseModel):
        data = content.model_dump()
    elif isinstance(content, dict):
        data = content
    elif isinstance(content, str):
        data = json.loads(content)
    else:
        raise TypeError(f"Cannot parse VizPlan from {type(content)}")

    if isinstance(data, dict) and "insights" in data:
        return VizPlan.model_validate(data)
    return VizPlan(insights=[VizSpec.model_validate(data)])


def build_step(*, mcp_tools: Optional[MCPTools] = None) -> Step:
    async def _run(step_input: StepInput) -> StepOutput:
        prior = step_input.get_step_output("plan_visualization")
        content = prior.content if prior is not None else step_input.previous_step_content
        question = None
        if isinstance(step_input.input, str):
            question = step_input.input
        elif step_input.input is not None:
            question = str(step_input.input)

        try:
            plan = _parse_viz_plan(content)
        except Exception as exc:  # noqa: BLE001
            failed = MultiExecuteResult(
                summary=None,
                insights=[],
                insight_count=0,
                success_count=0,
                error=f"Invalid visualization plan: {exc}",
            )
            return StepOutput(content=failed, success=False, error=failed.error)

        paired: list[InsightResult] = []
        for viz in plan.insights:
            try:
                result = await run_analytics(
                    viz=viz,
                    user_question=question,
                    mcp_tools=mcp_tools,
                )
            except Exception as exc:  # noqa: BLE001
                result = ExecuteResult(
                    sql="",
                    columns=[],
                    rows=[],
                    row_count=0,
                    error=str(exc),
                    path="failed",
                )
            paired.append(InsightResult(plan=viz, result=result))

        success_count = sum(1 for item in paired if item.result.error is None)
        multi = MultiExecuteResult(
            summary=plan.summary,
            insights=paired,
            insight_count=len(paired),
            success_count=success_count,
            error=None if success_count else "All insights failed",
        )
        ok = success_count > 0
        return StepOutput(content=multi, success=ok, error=multi.error)

    return Step(
        name=STEP_NAME,
        description=(
            "For each planned insight: build SQL via templates + clickhouse-connect; "
            "fallback to LLM SQL + ClickHouse MCP"
        ),
        executor=_run,
    )
