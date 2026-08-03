"""run_analytics: deterministic SQL build + CH execute, with LLM/MCP fallback."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel

from conversation_agent.clickhouse_client import run_query as run_query_direct
from conversation_agent.models import ExecuteResult, QuerySpec, VizSpec
from conversation_agent.query_builders import (
    AnalyticsPlan,
    build_sql,
    plan_from_viz_spec,
)

if TYPE_CHECKING:
    from agno.tools.mcp import MCPTools


def _parse_viz(content: Any) -> VizSpec:
    if isinstance(content, VizSpec):
        return content
    if isinstance(content, BaseModel):
        return VizSpec.model_validate(content.model_dump())
    if isinstance(content, dict):
        return VizSpec.model_validate(content)
    if isinstance(content, str):
        return VizSpec.model_validate(json.loads(content))
    raise TypeError(f"Cannot parse VizSpec from {type(content)}")


def run_deterministic(plan: AnalyticsPlan) -> ExecuteResult:
    built = build_sql(plan)
    columns, rows = run_query_direct(built.sql)
    return ExecuteResult(
        sql=built.sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        error=None,
        path="deterministic",
        caveats=built.caveats,
    )


async def run_llm_mcp_fallback(
    *,
    viz: VizSpec,
    user_question: str | None = None,
    mcp_tools: MCPTools | None = None,
    reason: str,
) -> ExecuteResult:
    """Existing path: LLM generate_query → execute (direct CH, else MCP)."""
    from conversation_agent.steps.generate_query import build_agent

    agent = build_agent(db=None)
    prompt_parts = [
        "Produce a QuerySpec for this VizSpec.",
        json.dumps(viz.model_dump(), default=str),
    ]
    if user_question:
        prompt_parts.insert(0, f"User question: {user_question}")
    run = await agent.arun("\n\n".join(prompt_parts))
    content = run.content
    if isinstance(content, QuerySpec):
        spec = content
    elif isinstance(content, BaseModel):
        spec = QuerySpec.model_validate(content.model_dump())
    elif isinstance(content, dict):
        spec = QuerySpec.model_validate(content)
    elif isinstance(content, str):
        spec = QuerySpec.model_validate(json.loads(content))
    else:
        raise TypeError(f"LLM returned unexpected type: {type(content)}")

    sql = (spec.sql or "").strip()
    if not sql:
        raise RuntimeError("LLM QuerySpec.sql is empty")

    # Prefer direct ClickHouse client; MCP only if needed / provided
    try:
        from conversation_agent.clickhouse_client import run_query as run_query_direct

        columns, rows = run_query_direct(sql)
    except Exception:
        from conversation_agent.shared import run_query_via_mcp

        columns, rows = await run_query_via_mcp(sql, mcp_tools=mcp_tools)

    return ExecuteResult(
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        error=None,
        path="llm_fallback",
        fallback_reason=reason,
        caveats=spec.caveats,
    )


async def run_analytics(
    *,
    viz: VizSpec | dict[str, Any] | None = None,
    plan: AnalyticsPlan | dict[str, Any] | None = None,
    user_question: str | None = None,
    mcp_tools: MCPTools | None = None,
    force_fallback: bool = False,
) -> ExecuteResult:
    """Build+execute via templates/CH client; on failure use LLM SQL + MCP."""
    viz_obj: VizSpec | None = None
    if viz is not None:
        try:
            viz_obj = _parse_viz(viz)
        except Exception:
            viz_obj = None

    reason = ""
    if not force_fallback:
        try:
            if plan is not None:
                plan_obj = (
                    plan
                    if isinstance(plan, AnalyticsPlan)
                    else AnalyticsPlan.model_validate(plan)
                )
            elif viz_obj is not None:
                plan_obj = plan_from_viz_spec(viz_obj)
            else:
                raise ValueError("Provide viz or plan")
            return run_deterministic(plan_obj)
        except Exception as exc:  # noqa: BLE001
            reason = str(exc)
    else:
        reason = "force_fallback"

    if viz_obj is None and isinstance(viz, dict):
        # Best-effort VizSpec for fallback
        try:
            viz_obj = VizSpec(
                kind=str(viz.get("kind") or "table"),
                event_names=list(viz.get("event_names") or []),
                dimensions=list(viz.get("dimensions") or []),
                metric_names=list(viz.get("metric_names") or []),
                time_window=viz.get("time_window"),
                title=viz.get("title"),
            )
        except Exception:
            viz_obj = None

    if viz_obj is None:
        return ExecuteResult(
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error=(
                f"Deterministic path failed ({reason}) "
                "and no VizSpec for LLM fallback"
            ),
            path="failed",
            fallback_reason=reason,
        )

    try:
        return await run_llm_mcp_fallback(
            viz=viz_obj,
            user_question=user_question,
            mcp_tools=mcp_tools,
            reason=reason or "deterministic_failed",
        )
    except Exception as exc:  # noqa: BLE001
        return ExecuteResult(
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            error=f"Fallback also failed: {exc}",
            path="failed",
            fallback_reason=reason,
        )
