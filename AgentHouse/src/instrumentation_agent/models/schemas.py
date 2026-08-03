"""Pydantic request / response schemas for API routes."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator


class InstrumentRequest(BaseModel):
    """Instrument a feature: ``feature_id`` and/or path to ``spec.md``."""

    feature_id: str | None = Field(
        default=None,
        description="Feature id (defaults to parent folder of spec.md).",
        examples=["01_express_checkout"],
    )
    spec_path: str | None = Field(
        default=None,
        description=(
            "Path to spec.md. Required when feature_id is not in the metadata registry "
            "and SPECS_ROOT/{feature_id}/spec.md is missing."
        ),
    )

    @model_validator(mode="after")
    def require_feature_or_spec(self) -> Self:
        if not self.feature_id and not self.spec_path:
            raise ValueError("Provide feature_id and/or spec_path")
        return self


class EventSummary(BaseModel):
    event_name: str
    journey_order: int
    ch_table: str
    row_count: int


class EventMetaDraft(BaseModel):
    """Structured event metadata inferred from spec.md (workflow step 1)."""

    event_name: str = Field(description="Canonical event name from the journey bullets.")
    journey_order: int = Field(description="1-based order in the product journey.")
    description: str = Field(default="", description="Short description from the spec.")
    ch_table: str = Field(description="ClickHouse table name (usually == event_name).")
    expected_columns: list[str] = Field(
        default_factory=list,
        description="Known or likely columns mentioned in the spec (may be empty).",
    )
    join_keys: list[str] = Field(
        default_factory=lambda: [
            "user_id",
            "application_id",
            "device_type",
            "os",
            "geoip_country_code",
            "destination",
            "timestamp",
        ],
        description="Shared envelope columns for cross-event joins.",
    )


class FeatureSpecMetadata(BaseModel):
    """JSON summary of spec.md used as event / feature metadata."""

    feature_id: str
    feature_summary: str = Field(description="1-3 sentence product summary from the spec.")
    journey: list[EventMetaDraft] = Field(description="Ordered event metadata from the journey.")
    notes: list[str] = Field(default_factory=list, description="Caveats or open questions.")


class PipelineToolChoice(BaseModel):
    """Record of a (mocked) pipeline tool the planner invoked."""

    tool_name: str
    # Stringified JSON — Gemini Developer API rejects dict/additionalProperties schemas.
    arguments_json: str = Field(
        default="{}",
        description="JSON object string of tool arguments (not a free-form object).",
    )
    result: str = ""


class PipelinePlan(BaseModel):
    """Decision from workflow step 2: build / change / skip pipeline."""

    action: str = Field(
        description="One of: create_pipeline | update_pipeline | skip_pipeline.",
    )
    rationale: str = Field(description="Why this action was chosen.")
    feature_id: str
    events_to_materialize: list[str] = Field(
        default_factory=list,
        description="Event / table names the pipeline should cover.",
    )
    pipeline_changes: list[str] = Field(
        default_factory=list,
        description="Concrete pipeline changes (DDL, ORDER BY, etc.).",
    )
    tool_choices: list[PipelineToolChoice] = Field(
        default_factory=list,
        description="Mocked tool calls made while deciding.",
    )


class InstrumentResponse(BaseModel):
    status: str
    run_id: str
    feature_id: str
    events: list[EventSummary]
    agent_run_id: str | None = None
    spec_metadata: FeatureSpecMetadata | None = None
    pipeline_plan: PipelinePlan | None = None


class HealthResponse(BaseModel):
    status: str
    postgres: str
    clickhouse: str
    specs_root: str


class RegistryResponse(BaseModel):
    feature_id: str
    feature: dict[str, Any] | None
    events: list[dict[str, Any]]
