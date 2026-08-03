"""Analytics REST routes — LibreChat contract + internal run_analytics."""

from __future__ import annotations

import json
from typing import Any, Optional, Union

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from conversation_agent.data_plane import fetch_dimension_values, fetch_insight_data
from conversation_agent.models import (
    AnalyticsApiError,
    AnalyticsDataRequest,
    AnalyticsDataResponse,
    AnalyticsDimensionsRequest,
    AnalyticsDimensionsResponse,
    AnalyticsQueryRequest,
    AnalyticsQueryResponse,
    ExecuteResult,
    VizSpec,
)
from conversation_agent.query_planner import run_analytics_query
from conversation_agent.tools import get_analytics_tools

router = APIRouter(tags=["analytics"])


class RunAnalyticsRequest(BaseModel):
    """HTTP-friendly mirror of AnalyticsTools.run_analytics args."""

    kind: str = Field(
        ...,
        description="funnel | timeseries | breakdown | metric | top_n | comparison",
    )
    event_names: Optional[list[str]] = Field(
        None,
        description="Event names (funnel order; for metric rates: numerator, denominator)",
    )
    dimensions: Optional[list[str]] = Field(
        None,
        description="Group-by columns (device_type, os, geoip_country_code, destination)",
    )
    time_window: str = Field("last_30_days", description="e.g. last_30_days")
    window_seconds: int = Field(86400, description="windowFunnel window (funnel kind)")
    filters: Optional[dict[str, Any]] = Field(
        None,
        description="Equality filters (serialized to filters_json for the tool)",
    )
    limit: int = Field(20, description="Max rows for breakdown/top_n")
    viz: Optional[Union[VizSpec, dict[str, Any]]] = Field(
        None,
        description="Optional full VizSpec (serialized to viz_json for LLM fallback)",
    )
    user_question: Optional[str] = Field(
        None,
        description="Original NL question (helps LLM fallback)",
    )
    force_fallback: bool = Field(
        False,
        description="Skip builders; use LLM + MCP only",
    )


def _join_csv(values: Optional[list[str]]) -> Optional[str]:
    if not values:
        return None
    return ",".join(v.strip() for v in values if v and v.strip()) or None


def _error(
    status: int,
    message: str,
    *,
    code: str = "UPSTREAM_ERROR",
    details: Any = None,
) -> JSONResponse:
    body = AnalyticsApiError(error=message, code=code, details=details)  # type: ignore[arg-type]
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# LibreChat contract
# ---------------------------------------------------------------------------


@router.post("/api/analytics/query", response_model=AnalyticsQueryResponse)
async def analytics_query(body: AnalyticsQueryRequest) -> AnalyticsQueryResponse:
    """Prompt → metadata-only lego blocks (no chart points)."""
    if not (body.prompt or "").strip():
        raise HTTPException(
            status_code=400,
            detail=AnalyticsApiError(
                error="prompt is required",
                code="INVALID_REQUEST",
            ).model_dump(exclude_none=True),
        )
    try:
        return await run_analytics_query(body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=AnalyticsApiError(
                error=str(exc),
                code="UPSTREAM_ERROR",
            ).model_dump(exclude_none=True),
        ) from exc


@router.post("/api/analytics/data", response_model=AnalyticsDataResponse)
async def analytics_data(body: AnalyticsDataRequest) -> Any:
    """Insight config → chart series / matrix."""
    try:
        return fetch_insight_data(body)
    except ValueError as exc:
        return _error(400, str(exc), code="INVALID_REQUEST")
    except Exception as exc:  # noqa: BLE001
        return _error(502, str(exc), code="UPSTREAM_ERROR")


@router.post("/api/analytics/dimensions", response_model=AnalyticsDimensionsResponse)
async def analytics_dimensions(body: AnalyticsDimensionsRequest) -> Any:
    """Dimension key → ordered member values (cached; raw table + fallback)."""
    if not (body.dimension or "").strip():
        return _error(400, "dimension is required", code="INVALID_REQUEST")
    try:
        return fetch_dimension_values(body)
    except ValueError as exc:
        return _error(400, str(exc), code="INVALID_REQUEST")
    except Exception as exc:  # noqa: BLE001
        return _error(502, str(exc), code="UPSTREAM_ERROR")


# ---------------------------------------------------------------------------
# Internal / tools path
# ---------------------------------------------------------------------------


@router.post("/v1/analytics/run", response_model=ExecuteResult)
async def run_analytics_endpoint(body: RunAnalyticsRequest) -> ExecuteResult:
    """Delegate to AnalyticsTools.run_analytics (same path LLM agents use)."""
    tools = get_analytics_tools()

    filters_json = json.dumps(body.filters) if body.filters is not None else None
    viz_json = None
    if body.viz is not None:
        if isinstance(body.viz, VizSpec):
            viz_json = body.viz.model_dump_json()
        else:
            viz_json = json.dumps(body.viz)

    try:
        raw = await tools.run_analytics(
            kind=body.kind,
            event_names=_join_csv(body.event_names),
            dimensions=_join_csv(body.dimensions),
            time_window=body.time_window,
            window_seconds=body.window_seconds,
            filters_json=filters_json,
            limit=body.limit,
            viz_json=viz_json,
            user_question=body.user_question,
            force_fallback=body.force_fallback,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"analytics failed: {exc}",
        ) from exc

    try:
        return ExecuteResult.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"invalid tool response: {exc}",
        ) from exc
