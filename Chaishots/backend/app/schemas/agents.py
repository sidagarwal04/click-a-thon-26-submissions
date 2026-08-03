from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ColumnPlan(AgentModel):
    name: str
    base_type: Literal["String", "Int64", "Float64", "UInt8", "DateTime64(3)"]
    nullable: bool


class OrderByFieldReason(AgentModel):
    field: str
    role: Literal[
        "primary_entity",
        "time_filter",
        "event_filter",
        "relationship_key",
        "segment_filter",
        "other",
    ]
    reason: str = Field(min_length=1, max_length=500)


class InstrumentationPlan(AgentModel):
    feature_name: str
    table_name: str
    schema_reasoning: str = Field(
        default="Legacy schema contract without recorded reasoning",
        min_length=1,
        max_length=1000,
    )
    primary_entity: str
    timestamp_field: str
    partition_by: str | None
    partition_by_reasoning: str = Field(min_length=1, max_length=500)
    columns: list[ColumnPlan] = Field(min_length=2, max_length=256)
    order_by: list[str] = Field(min_length=1, max_length=4)
    order_by_reasoning: list[OrderByFieldReason] = Field(min_length=1, max_length=4)
    funnel_steps: list[str] = Field(min_length=2, max_length=20)
    dimensions: list[str] = Field(default_factory=list, max_length=30)
    relationships: list[dict[str, JsonValue]] = Field(default_factory=list)
    expected_queries: list[str] = Field(default_factory=list, max_length=20)


class MaterializationPlan(AgentModel):
    feature: str
    source_schema_fingerprint: str = Field(min_length=64, max_length=64)
    source_table: str
    target_table: str
    view_name: str
    timestamp_field: str
    event_field: str
    entity_field: str
    dimensions: list[str] = Field(default_factory=list, max_length=2)
    purpose: str


class RelationshipDefinition(AgentModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    reason: str


class MetricDefinition(AgentModel):
    name: str
    description: str
    numerator: str
    denominator: str
    dimensions: list[str] = Field(default_factory=list, max_length=20)


class EntityDefinition(AgentModel):
    name: str
    table_name: str
    primary_key: str
    description: str
    dimensions: list[str] = Field(default_factory=list, max_length=20)
    grain: str = ""
    business_entities: list[str] = Field(default_factory=list, max_length=10)
    time_field: str | None = None
    event_field: str | None = None
    common_filters: list[str] = Field(default_factory=list, max_length=20)
    common_groupings: list[str] = Field(default_factory=list, max_length=20)


class KnownIssue(AgentModel):
    """A documented product or data quirk carried from the base context layer."""

    key: str
    title: str
    description: str = ""


class ContextSelection(AgentModel):
    """Read-only slice of accumulated context relevant to one new feature."""

    relevant_entities: list[EntityDefinition] = Field(
        default_factory=list, max_length=20
    )
    relevant_relationships: list[RelationshipDefinition] = Field(
        default_factory=list, max_length=20
    )
    relevant_metrics: list[MetricDefinition] = Field(
        default_factory=list, max_length=20
    )
    relevant_known_issues: list[KnownIssue] = Field(default_factory=list, max_length=20)
    naming_conventions: list[str] = Field(default_factory=list, max_length=20)
    reuse_notes: list[str] = Field(default_factory=list, max_length=10)


class ContextAgentOutput(AgentModel):
    entities_added: list[EntityDefinition] = Field(default_factory=list, max_length=10)
    relationships_added: list[RelationshipDefinition] = Field(default_factory=list)
    metrics_added: list[MetricDefinition] = Field(default_factory=list)
    conventions_added: list[str] = Field(default_factory=list, max_length=10)
    conflicts: list[str] = Field(default_factory=list)


class AnalysisQuery(AgentModel):
    query_id: str
    analysis_type: Literal[
        "funnel",
        "segment_comparison",
        "baseline_comparison",
        "latency",
        "adoption",
        "trend",
    ]
    purpose: str
    sql: str


class AnalysisPlan(AgentModel):
    analyses: list[AnalysisQuery] = Field(min_length=1, max_length=12)


class AgentInsight(AgentModel):
    title: str
    observation: str
    evidence: list[str] = Field(min_length=1, max_length=20)
    interpretation: str
    context_used: list[str] = Field(default_factory=list, max_length=20)
    recommendation: str
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = Field(default_factory=list, max_length=20)


class AnalyticsAgentOutput(AgentModel):
    insights: list[AgentInsight] = Field(min_length=1, max_length=10)
