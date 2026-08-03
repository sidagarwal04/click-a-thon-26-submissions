"""Agno toolkit: run_analytics + LibreChat data-plane tools."""

from __future__ import annotations

import json
from typing import Optional

from agno.tools import Toolkit

from conversation_agent.analytics import run_analytics
from conversation_agent.catalog import list_dimensions, list_metrics
from conversation_agent.data_plane import fetch_dimension_values, fetch_insight_data
from conversation_agent.models import (
    AnalyticsDataPayload,
    AnalyticsDataRequest,
    AnalyticsDimensionFilter,
    AnalyticsDimensionsRequest,
)
from conversation_agent.query_builders import AnalyticsPlan


class AnalyticsTools(Toolkit):
    """Analytics tools shared by agents and HTTP routes."""

    def __init__(self):
        super().__init__(
            name="analytics",
            tools=[
                self.run_analytics,
                self.fetch_dimension_values,
                self.fetch_insight_data,
                self.list_dimensions,
                self.list_metrics,
            ],
        )

    async def run_analytics(
        self,
        kind: str,
        event_names: Optional[str] = None,
        dimensions: Optional[str] = None,
        time_window: Optional[str] = "last_30_days",
        window_seconds: int = 86400,
        filters_json: Optional[str] = None,
        limit: int = 20,
        viz_json: Optional[str] = None,
        user_question: Optional[str] = None,
        force_fallback: bool = False,
    ) -> str:
        """Run ClickHouse analytics: build SQL + execute (or LLM/MCP fallback).

        Prefer structured args. kind: funnel | timeseries | breakdown | metric |
        top_n | comparison.

        Args:
            kind: Analytics pattern key.
            event_names: Comma-separated event names (funnel order for funnels;
                for metric rates: numerator,denominator).
            dimensions: Comma-separated group-by columns
                (device_type, os, geoip_country_code, destination).
            time_window: e.g. last_30_days.
            window_seconds: windowFunnel window (funnel kind).
            filters_json: Optional JSON object of equality filters.
            limit: Max rows for breakdown/top_n.
            viz_json: Optional full VizSpec JSON (used for LLM fallback).
            user_question: Original NL question (helps LLM fallback).
            force_fallback: Skip builders; use LLM + MCP only.
        """
        events = [e.strip() for e in (event_names or "").split(",") if e.strip()]
        dims = [d.strip() for d in (dimensions or "").split(",") if d.strip()]
        filters: dict = {}
        if filters_json:
            parsed = json.loads(filters_json)
            if not isinstance(parsed, dict):
                return json.dumps({"error": "filters_json must be a JSON object"})
            filters = parsed

        viz = None
        if viz_json:
            viz = json.loads(viz_json)
        else:
            viz = {
                "kind": kind,
                "event_names": events,
                "dimensions": dims,
                "time_window": time_window,
                "metric_names": [],
            }

        plan = None
        try:
            plan = AnalyticsPlan(
                kind=kind,  # type: ignore[arg-type]
                event_names=events,
                dimensions=dims,
                time_window=time_window,
                window_seconds=window_seconds,
                filters=filters,
                limit=limit,
            )
        except Exception:
            plan = None

        result = await run_analytics(
            plan=plan,
            viz=viz,
            user_question=user_question,
            force_fallback=force_fallback,
        )
        return result.model_dump_json()

    async def fetch_dimension_values(
        self,
        dimension: str,
        fromtime: Optional[str] = None,
        totime: Optional[str] = None,
        metric_name: Optional[str] = None,
        filters_json: Optional[str] = None,
    ) -> str:
        """Fetch ordered dimension member values from ClickHouse (cached).

        Queries the raw event table for DISTINCT members. If the column is
        missing, falls back to extracting members from a contributor aggregate.

        Args:
            dimension: Catalog key (country, channel, destination, …) or CH column.
            fromtime: Optional YYYY-MM-DD window start.
            totime: Optional YYYY-MM-DD window end.
            metric_name: Optional metric to scope ranking of members.
            filters_json: Optional JSON array of {key, value} filters.
        """
        filters = None
        if filters_json:
            parsed = json.loads(filters_json)
            if isinstance(parsed, list):
                filters = [AnalyticsDimensionFilter.model_validate(x) for x in parsed]
            elif isinstance(parsed, dict):
                filters = [
                    AnalyticsDimensionFilter(key=str(k), value=str(v))
                    for k, v in parsed.items()
                ]
            else:
                return json.dumps({"error": "filters_json must be array or object"})

        try:
            result = fetch_dimension_values(
                AnalyticsDimensionsRequest(
                    dimension=dimension,
                    fromtime=fromtime,
                    totime=totime,
                    metric_name=metric_name,
                    filters=filters,
                )
            )
            return result.model_dump_json()
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "code": "UPSTREAM_ERROR"})

    async def fetch_insight_data(
        self,
        insight_type: str,
        fromtime: str,
        totime: str,
        metric_name: str,
        timegrain: Optional[str] = None,
        dimensions: Optional[str] = None,
        filters_json: Optional[str] = None,
    ) -> str:
        """Fetch chart series / matrix for trend | contributor | pivot.

        Args:
            insight_type: trend | contributor | pivot
            fromtime: YYYY-MM-DD
            totime: YYYY-MM-DD
            metric_name: Catalog metric key
            timegrain: day | week | month (optional)
            dimensions: Comma-separated dimension keys
            filters_json: Optional JSON array of {key, value}
        """
        dims = [d.strip() for d in (dimensions or "").split(",") if d.strip()] or None
        filters = None
        if filters_json:
            parsed = json.loads(filters_json)
            if isinstance(parsed, list):
                filters = [AnalyticsDimensionFilter.model_validate(x) for x in parsed]

        try:
            result = fetch_insight_data(
                AnalyticsDataRequest(
                    insight_type=insight_type,  # type: ignore[arg-type]
                    payload=AnalyticsDataPayload(
                        fromtime=fromtime,
                        totime=totime,
                        metric_name=metric_name,
                        timegrain=timegrain,  # type: ignore[arg-type]
                        dimensions=dims,
                        filters=filters,
                    ),
                )
            )
            return result.model_dump_json()
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc), "code": "UPSTREAM_ERROR"})

    async def list_dimensions(self) -> str:
        """List product dimension keys (no ClickHouse hit)."""
        return json.dumps({"dimensions": list_dimensions()})

    async def list_metrics(self) -> str:
        """List product metric keys (no ClickHouse hit)."""
        return json.dumps({"metrics": list_metrics()})


def get_analytics_tools() -> AnalyticsTools:
    return AnalyticsTools()
