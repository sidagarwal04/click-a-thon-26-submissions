from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class FeatureModel(BaseModel):
    """Base model for values shared by the API, MCP, and orchestrator."""

    model_config = ConfigDict(extra="forbid")


class ObservedFieldType(StrEnum):
    """JSON value types observed while profiling a field."""

    NULL = "null"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    OBJECT = "object"
    ARRAY = "array"
    MIXED = "mixed"


JsonScalar = str | int | float | bool | None


class EventFieldStats(FeatureModel):
    """Presence and nullability of a field within one event type."""

    presence_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)
    null_count: int = Field(default=0, ge=0)
    non_null_count: int = Field(default=0, ge=0)
    presence: float = Field(default=0.0, ge=0.0, le=1.0)
    presence_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    null_rate_when_present: float = Field(default=0.0, ge=0.0, le=1.0)


class FieldProfile(FeatureModel):
    """A bounded summary of one event field, including nested object paths."""

    observed_type: ObservedFieldType
    observed_types: list[ObservedFieldType]
    presence_count: int = Field(ge=0)
    missing_count: int = Field(default=0, ge=0)
    null_count: int = Field(default=0, ge=0)
    non_null_count: int = Field(default=0, ge=0)
    presence: float = Field(ge=0.0, le=1.0)
    presence_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    global_presence: float = Field(default=0.0, ge=0.0, le=1.0)
    null_rate_when_present: float = Field(default=0.0, ge=0.0, le=1.0)
    by_event: dict[str, EventFieldStats] = Field(default_factory=dict)
    approx_cardinality: int = Field(ge=0)
    cardinality_is_estimate: bool = False
    examples: list[JsonScalar] = Field(default_factory=list, max_length=5)
    examples_redacted: bool = False
    example_shape: str | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    negative_count: int = Field(default=0, ge=0)
    zero_count: int = Field(default=0, ge=0)
    maximum_decimal_places: int = Field(default=0, ge=0)
    minimum_length: int | None = Field(default=None, ge=0)
    maximum_length: int | None = Field(default=None, ge=0)
    empty_count: int = Field(default=0, ge=0)
    element_types: list[ObservedFieldType] = Field(default_factory=list)
    object_field_names: list[str] = Field(default_factory=list)
    string_values_analysed: int = Field(default=0, ge=0)
    string_type_counts: dict[str, int] = Field(default_factory=dict)
    identifier_like: bool = False
    quality_flags: list[str] = Field(default_factory=list)


class EventProfile(FeatureModel):
    """A streaming-generated profile of an NDJSON event file."""

    event_count: int = Field(ge=0)
    event_names: dict[str, int] = Field(default_factory=dict)
    unnamed_event_count: int = Field(default=0, ge=0)
    fields: dict[str, FieldProfile] = Field(default_factory=dict)
    event_name_field: str | None = None
    event_name_detection_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    common_envelope_fields: list[str] = Field(default_factory=list)
    event_specific_fields: dict[str, list[str]] = Field(default_factory=dict)
    profiler_version: str = "2.0.0"
    source_file_hash: str = ""
    duration_ms: float = Field(default=0.0, ge=0.0)
    fields_discovered: int = Field(default=0, ge=0)
    profile_configuration: dict[str, int | str | bool] = Field(default_factory=dict)


class FeatureFiles(FeatureModel):
    """The small, validated input passed into the processing pipeline."""

    feature: str
    spec: str
    events_path: Path


class ProcessFeatureRequest(FeatureModel):
    """Transport request for the shared process-feature use case."""

    feature_folder: str = Field(min_length=1, max_length=128)


class FeatureUploadResult(FeatureModel):
    """Receipt returned after storing, but not processing, a feature upload."""

    feature_folder: str
    status: Literal["uploaded"] = "uploaded"
    files: list[str] = Field(default_factory=lambda: ["spec.md", "events.ndjson"])


class InsightSummary(FeatureModel):
    """Compact insight representation suitable for list responses."""

    title: str
    confidence: str


class InsightDetail(InsightSummary):
    """Full analytical insight returned by a detail endpoint."""

    observation: str = ""
    evidence: list[JsonValue] = Field(default_factory=list)
    interpretation: str = ""
    context_used: list[str] = Field(default_factory=list)
    recommendation: str = ""
    caveats: list[str] = Field(default_factory=list)


class RunSummary(FeatureModel):
    """Compact status for a feature-processing run."""

    run_id: str
    status: str
    feature: str
    table_created: str | None = None
    rows_loaded: int = Field(default=0, ge=0)
    context_version: int | None = Field(default=None, ge=1)
    insights: list[InsightSummary] = Field(default_factory=list)
    langfuse_trace_id: str | None = None


class ProcessFeatureResult(RunSummary):
    """Immediate, compact result shared by API and MCP process calls."""

    event_profile: EventProfile | None = None
    partition_by: str | None = None
    partition_by_reasoning: str | None = None


class SchemaArtifact(FeatureModel):
    """Generated schema material for a completed or in-progress run."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: str
    table_name: str
    ddl: str
    schema_reasoning: str | None = None
    partition_by: str | None = None
    partition_by_reasoning: str | None = None
    order_by: list[str] = Field(default_factory=list)
    order_by_reasoning: list[dict[str, JsonValue]] = Field(default_factory=list)
    schema_definition: dict[str, JsonValue] = Field(
        default_factory=dict, alias="schema"
    )


class ContextDiff(FeatureModel):
    """Small context delta produced by the context agent."""

    run_id: str
    context_version: int = Field(ge=1)
    entities_added: list[dict[str, JsonValue]] = Field(default_factory=list)
    relationships_added: list[dict[str, JsonValue]] = Field(default_factory=list)
    metrics_added: list[dict[str, JsonValue]] = Field(default_factory=list)
    conventions_added: list[str] = Field(default_factory=list)
    conflicts: list[JsonValue] = Field(default_factory=list)


class ContextDocument(FeatureModel):
    """The full accumulated semantic context at one version."""

    version: int = Field(ge=1)
    run_id: str | None = None
    entities: list[dict[str, JsonValue]] = Field(default_factory=list)
    relationships: list[dict[str, JsonValue]] = Field(default_factory=list)
    metrics: list[dict[str, JsonValue]] = Field(default_factory=list)
    known_issues: list[dict[str, JsonValue]] = Field(default_factory=list)
    naming_conventions: list[str] = Field(default_factory=list)
    conflicts: list[JsonValue] = Field(default_factory=list)
    source: str = "context_agent"


class RunReport(FeatureModel):
    """Complete safe dashboard payload assembled from persisted run artifacts."""

    summary: RunSummary
    artifacts: dict[str, JsonValue] = Field(default_factory=dict)
