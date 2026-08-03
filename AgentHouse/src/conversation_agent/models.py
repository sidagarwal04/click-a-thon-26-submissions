"""Pydantic contracts for the Visualization Agent workflow + LibreChat analytics API."""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Step 1 — discover_schema
# ---------------------------------------------------------------------------


class ColumnInfo(BaseModel):
    name: str = Field(..., description="Column name")
    type: Optional[str] = Field(None, description="ClickHouse type if known")


class TableSchema(BaseModel):
    name: str = Field(..., description="Table name")
    columns: list[ColumnInfo] = Field(
        default_factory=list,
        description="Relevant columns for the question",
    )
    event_names: list[str] = Field(
        default_factory=list,
        description="Event names present in / represented by this table",
    )


class SchemaContext(BaseModel):
    """Tables / columns / events selected for the analytics question."""

    database: Optional[str] = Field(None, description="Database name if known")
    tables: list[TableSchema] = Field(
        ...,
        description="Relevant tables with columns and event names",
    )
    notes: Optional[str] = Field(None, description="Join / funnel / caveats")
    rationale: Optional[str] = Field(
        None,
        description="Why these tables were selected for the question",
    )


# ---------------------------------------------------------------------------
# Step 2 — plan_visualization (VizPlan: 1–5 VizSpecs)
# ---------------------------------------------------------------------------


class VizSpec(BaseModel):
    """One visualization / insight plan."""

    kind: str = Field(
        ...,
        description=(
            "Visualization type key. Examples: "
            "timeseries, breakdown, comparison, table, funnel, metric, top_n"
        ),
    )
    title: Optional[str] = Field(None, description="Short chart title")
    metric_names: list[str] = Field(
        default_factory=list,
        description="Metrics the visualization should show",
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Slice / group-by dimensions",
    )
    event_names: list[str] = Field(
        default_factory=list,
        description="Events involved in the viz",
    )
    time_window: Optional[str] = Field(
        None,
        description="Requested time window, e.g. last_30_days",
    )
    rationale: Optional[str] = Field(
        None,
        description="Why this viz type fits the question and schema",
    )


class VizPlan(BaseModel):
    """One or more VizSpecs that together answer the analytics question."""

    insights: list[VizSpec] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Ordered insight plans (1–5)",
    )
    summary: Optional[str] = Field(
        None,
        description="Brief plan of how these insights answer the question",
    )


# ---------------------------------------------------------------------------
# Step 3 — generate_query
# ---------------------------------------------------------------------------


class QuerySpec(BaseModel):
    """Single ClickHouse SELECT to execute (funnel / analytics)."""

    sql: str = Field(..., description="Exactly one aggregate SELECT (or WITH … SELECT)")
    tables_used: list[str] = Field(
        default_factory=list,
        description="Tables referenced in the SQL",
    )
    funnel: Optional[str] = Field(
        None,
        description="Funnel id for viz contract, e.g. express_checkout",
    )
    window_seconds: Optional[int] = Field(
        None,
        description="windowFunnel window in seconds (when event_time is DateTime)",
    )
    step_names: list[str] = Field(
        default_factory=list,
        description="Ordered funnel step event_name values",
    )
    filters: Optional[dict[str, Any]] = Field(
        None,
        description="Filters for viz contract, e.g. start_date, end_date, segment",
    )
    caveats: Optional[str] = Field(
        None,
        description="Limitations, timestamp unit, companion metrics not in this SQL",
    )


# ---------------------------------------------------------------------------
# Step 4 — execute
# ---------------------------------------------------------------------------


class ExecuteResult(BaseModel):
    """Deterministic query execution result."""

    sql: str = Field(..., description="SQL that was run")
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(
        default_factory=list,
        description="Row values aligned with columns",
    )
    row_count: int = Field(0, description="Number of rows returned")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    path: Optional[str] = Field(
        None,
        description="deterministic | llm_mcp_fallback | llm_fallback | failed",
    )
    fallback_reason: Optional[str] = Field(
        None,
        description="Why deterministic path was skipped/failed",
    )
    caveats: Optional[str] = Field(None, description="Builder or LLM caveats")


class InsightResult(BaseModel):
    """One planned insight paired with its execution result."""

    plan: VizSpec
    result: ExecuteResult


class MultiExecuteResult(BaseModel):
    """Workflow output when plan_visualization returns multiple insights."""

    summary: Optional[str] = Field(
        None,
        description="Plan summary from VizPlan (if any)",
    )
    insights: list[InsightResult] = Field(default_factory=list)
    insight_count: int = Field(0, description="Number of insights attempted")
    success_count: int = Field(0, description="Insights with no execution error")
    error: Optional[str] = Field(
        None,
        description="Set when every insight failed",
    )


# ---------------------------------------------------------------------------
# LibreChat analytics contract — Part 1 (prompt → metadata-only blocks)
# ---------------------------------------------------------------------------

AgentInsightType = Literal["Trend", "Ranking", "Pivot", "Funnel"]
DataInsightType = Literal["trend", "contributor", "pivot"]
AgentTimeGrain = Literal["DAILY", "WEEKLY", "MONTHLY"]
DataTimeGrain = Literal["day", "week", "month"]

AGENT_TO_DATA_INSIGHT: dict[str, DataInsightType | list[DataInsightType]] = {
    "Trend": "trend",
    "Ranking": "contributor",
    "Pivot": "pivot",
    "Funnel": ["contributor", "trend"],
}

AGENT_TO_DATA_GRAIN: dict[str, DataTimeGrain] = {
    "DAILY": "day",
    "WEEKLY": "week",
    "MONTHLY": "month",
}


class AnalyticsMetric(BaseModel):
    metric_name: str = Field(..., description="Stable machine key, e.g. revenue")
    metric_label: str = Field(..., description="Human label, e.g. Revenue")


class AnalyticsDimensionFilter(BaseModel):
    key: str
    value: str


class AnalyticsQueryRequest(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None
    history: Optional[list[dict[str, str]]] = Field(
        None,
        description="Prior turns: {role, content} oldest → newest",
    )
    tenant_id: Optional[str] = None
    locale: Optional[str] = None


class AnalyticsTextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class AnalyticsInsightBlock(BaseModel):
    """Metadata-only insight block — never embeds chart points."""

    type: Literal["insight"] = "insight"
    title: Optional[str] = None
    caption: Optional[str] = None
    insight_type: AgentInsightType
    metrics: list[AnalyticsMetric] = Field(..., min_length=1)
    dimensions: list[str] = Field(default_factory=list)
    fromTime: str = Field(..., description="Inclusive YYYY-MM-DD")
    toTime: str = Field(..., description="Inclusive YYYY-MM-DD")
    timeGrain: AgentTimeGrain

    @model_validator(mode="after")
    def _validate_cardinality(self) -> AnalyticsInsightBlock:
        dims = self.dimensions or []
        n_metrics = len(self.metrics)
        kind = self.insight_type
        if kind == "Trend" and dims:
            raise ValueError("Trend requires empty dimensions")
        if kind == "Ranking" and len(dims) != 1:
            raise ValueError("Ranking requires exactly 1 dimension")
        if kind == "Pivot" and len(dims) != 2:
            raise ValueError("Pivot requires exactly 2 dimensions [row, col]")
        if kind == "Funnel":
            if n_metrics < 2:
                raise ValueError("Funnel requires at least 2 metrics (ordered stages)")
            if len(dims) > 1:
                raise ValueError("Funnel allows 0 or 1 dimension")
        return self


AnalyticsBlock = Union[AnalyticsTextBlock, AnalyticsInsightBlock]


class AnalyticsQueryMeta(BaseModel):
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    warnings: Optional[list[str]] = None


class AnalyticsQueryResponse(BaseModel):
    blocks: list[AnalyticsBlock] = Field(..., min_length=1)
    meta: Optional[AnalyticsQueryMeta] = None


# ---------------------------------------------------------------------------
# LibreChat analytics contract — Part 2a (insight config → data)
# ---------------------------------------------------------------------------


class AnalyticsDataPayload(BaseModel):
    fromtime: str
    totime: str
    metric_name: str
    timegrain: Optional[DataTimeGrain] = None
    dimensions: Optional[list[str]] = None
    filters: Optional[list[AnalyticsDimensionFilter]] = None


class AnalyticsDataRequest(BaseModel):
    payload: AnalyticsDataPayload
    insight_type: DataInsightType


class AnalyticsDataResponse(BaseModel):
    data: list[dict[str, Any]] = Field(default_factory=list)
    interpretation: Optional[str] = None
    query: Optional[str] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# LibreChat analytics contract — Part 2b (dimension values)
# ---------------------------------------------------------------------------


class AnalyticsDimensionsRequest(BaseModel):
    dimension: str
    fromtime: Optional[str] = None
    totime: Optional[str] = None
    metric_name: Optional[str] = None
    filters: Optional[list[AnalyticsDimensionFilter]] = None
    tenant_id: Optional[str] = None


class AnalyticsDimensionsResponse(BaseModel):
    dimension: str
    values: list[str]
    latency_ms: Optional[int] = None


class AnalyticsApiError(BaseModel):
    error: str
    code: Optional[
        Literal[
            "INVALID_REQUEST",
            "UNAUTHORIZED",
            "FORBIDDEN",
            "NOT_FOUND",
            "UPSTREAM_ERROR",
            "TIMEOUT",
        ]
    ] = None
    details: Optional[Any] = None
