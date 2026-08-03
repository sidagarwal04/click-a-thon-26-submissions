"""LLM planner: natural-language prompt → metadata-only AnalyticsQueryResponse."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from conversation_agent import config
from conversation_agent.catalog import FUNNEL_STAGE_METRICS, catalog_prompt_blurb
from conversation_agent.models import (
    AnalyticsInsightBlock,
    AnalyticsQueryMeta,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    AnalyticsTextBlock,
)
from conversation_agent.shared import agent_trace_metadata, build_model, setup_langfuse

STEP_NAME = "analytics_query"

INSTRUCTIONS = [
    "You are the Analytics Agent query planner for LibreChat.",
    "Given a user analytics question, return ONLY an AnalyticsQueryResponse JSON.",
    "Blocks are METADATA ONLY — never invent chart points or numeric series.",
    "Typical shape: one text block summarizing the answer plan, then one or more insight blocks.",
    "insight_type must be one of: Trend, Ranking, Pivot, Funnel.",
    "Cardinality rules:",
    "- Trend: metrics ≥ 1, dimensions must be []",
    "- Ranking: metrics ≥ 1, dimensions length === 1",
    "- Pivot: metrics ≥ 1, dimensions length === 2 [rowDim, colDim]",
    "- Funnel: metrics ≥ 2 (ordered stages), dimensions length 0 or 1",
    "Use ONLY catalog metric_name and dimension keys.",
    "Dates: fromTime/toTime as YYYY-MM-DD inclusive. timeGrain: DAILY | WEEKLY | MONTHLY.",
    "If the question is unclear or impossible with the catalog, return a single text block explaining why.",
    "Empty blocks array is invalid.",
    catalog_prompt_blurb(),
]


def build_query_agent(*, db: Any = None) -> Any:
    from agno.agent import Agent

    setup_langfuse()
    return Agent(
        id=f"{config.AGENT_ID}-analytics-query",
        name="Analytics Query Planner",
        model=build_model(),
        tools=[],
        db=db,
        instructions=list(INSTRUCTIONS),
        output_schema=AnalyticsQueryResponse,
        use_json_mode=True,
        markdown=False,
        add_history_to_context=False,
        metadata=agent_trace_metadata(step=STEP_NAME),
    )


def _history_blob(history: Optional[list[dict[str, str]]]) -> str:
    if not history:
        return ""
    lines: list[str] = ["Prior conversation:"]
    for turn in history[-8:]:
        role = str(turn.get("role") or "user")
        content = str(turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _parse_response(content: Any) -> AnalyticsQueryResponse:
    if isinstance(content, AnalyticsQueryResponse):
        return content
    if isinstance(content, BaseModel):
        return AnalyticsQueryResponse.model_validate(content.model_dump())
    if isinstance(content, dict):
        return AnalyticsQueryResponse.model_validate(content)
    if isinstance(content, str):
        return AnalyticsQueryResponse.model_validate(json.loads(content))
    raise TypeError(f"Unexpected planner content type: {type(content)}")


def _normalize_blocks(resp: AnalyticsQueryResponse) -> AnalyticsQueryResponse:
    """Re-validate insight blocks; soften Funnel metrics if planner used event names."""
    blocks: list[Any] = []
    warnings: list[str] = []
    for block in resp.blocks:
        if isinstance(block, AnalyticsTextBlock) or getattr(block, "type", None) == "text":
            blocks.append(
                block
                if isinstance(block, AnalyticsTextBlock)
                else AnalyticsTextBlock.model_validate(
                    block.model_dump() if isinstance(block, BaseModel) else block
                )
            )
            continue
        try:
            insight = (
                block
                if isinstance(block, AnalyticsInsightBlock)
                else AnalyticsInsightBlock.model_validate(
                    block.model_dump() if isinstance(block, BaseModel) else block
                )
            )
            if insight.insight_type == "Funnel" and len(insight.metrics) < 2:
                # Auto-fill ordered funnel stages when planner under-specified
                from conversation_agent.catalog import METRICS

                insight = insight.model_copy(
                    update={
                        "metrics": [
                            {
                                "metric_name": k,
                                "metric_label": METRICS[k].label,
                            }
                            for k in FUNNEL_STAGE_METRICS
                        ]
                    }
                )
                insight = AnalyticsInsightBlock.model_validate(insight.model_dump())
                warnings.append("Filled Funnel metrics with default core funnel stages")
            blocks.append(insight)
        except ValidationError as exc:
            warnings.append(f"Dropped invalid insight block: {exc}")
    if not blocks:
        blocks = [
            AnalyticsTextBlock(
                text="I could not build a valid insight for that question. "
                "Try asking for a trend, ranking, pivot, or funnel using catalog metrics."
            )
        ]
    meta = resp.meta or AnalyticsQueryMeta()
    if warnings:
        meta = meta.model_copy(
            update={"warnings": list(meta.warnings or []) + warnings}
        )
    return AnalyticsQueryResponse(blocks=blocks, meta=meta)


async def run_analytics_query(
    request: AnalyticsQueryRequest,
    *,
    agent: Any = None,
) -> AnalyticsQueryResponse:
    """Plan metadata-only blocks for LibreChat (no ClickHouse data fetch)."""
    t0 = time.perf_counter()
    planner = agent or build_query_agent()
    prompt_parts = [f"User question:\n{request.prompt.strip()}"]
    hist = _history_blob(request.history)
    if hist:
        prompt_parts.insert(0, hist)
    if request.locale:
        prompt_parts.append(f"Locale hint: {request.locale}")

    try:
        run = await planner.arun("\n\n".join(prompt_parts))
        resp = _normalize_blocks(_parse_response(run.content))
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return AnalyticsQueryResponse(
            blocks=[
                AnalyticsTextBlock(
                    text=f"Analytics planner failed: {exc}. Please rephrase your question."
                )
            ],
            meta=AnalyticsQueryMeta(
                model=f"{config.MODEL_PROVIDER}:{config.MODEL_ID}",
                latency_ms=latency_ms,
                warnings=[str(exc)],
            ),
        )

    latency_ms = int((time.perf_counter() - t0) * 1000)
    meta = resp.meta or AnalyticsQueryMeta()
    meta = meta.model_copy(
        update={
            "model": meta.model or f"{config.MODEL_PROVIDER}:{config.MODEL_ID}",
            "latency_ms": latency_ms,
        }
    )
    return AnalyticsQueryResponse(blocks=resp.blocks, meta=meta)
