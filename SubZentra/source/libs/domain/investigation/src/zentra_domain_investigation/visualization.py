from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VisualizationView(StrEnum):
    AUTO = "auto"
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    GROUPED_BAR = "grouped_bar"
    STACKED_BAR = "stacked_bar"
    PIE = "pie"
    RADAR = "radar"
    RADIAL = "radial"
    TABLE = "table"
    METRIC_CARDS = "metric_cards"
    STRUCTURED_TEXT = "structured_text"


class VisualizationArtifactStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    TOMBSTONED = "tombstoned"


class VisualizationActionKind(StrEnum):
    CONTINUE_CONVERSATION = "continue_conversation"
    OPEN_CITATION = "open_citation"


class BriefMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    exact_value: str = Field(min_length=1, max_length=128)
    display_value: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=48)
    direction: Literal["up", "down", "flat", "not_applicable"]
    citation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=16)


class BriefComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    previous_label: str | None = Field(default=None, max_length=120)
    previous_exact_value: str = Field(min_length=1, max_length=128)
    previous_display_value: str = Field(min_length=1, max_length=128)
    current_label: str | None = Field(default=None, max_length=120)
    current_exact_value: str = Field(min_length=1, max_length=128)
    current_display_value: str = Field(min_length=1, max_length=128)
    unit: str = Field(min_length=1, max_length=48)
    citation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=16)


class BriefTimeRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_label: str = Field(min_length=1, max_length=120)
    end_label: str = Field(min_length=1, max_length=120)


class BriefSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    position: int = Field(ge=0, le=199)
    label: str = Field(min_length=1, max_length=120)
    exact_value: str = Field(min_length=1, max_length=128)
    display_value: str = Field(min_length=1, max_length=128)
    citation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=16)


class BriefSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=120)
    dimensions: tuple[str, ...] = Field(default=(), max_length=8)
    unit: str = Field(min_length=1, max_length=48)
    points: tuple[BriefSeriesPoint, ...] = Field(min_length=1, max_length=200)

    @field_validator("points")
    @classmethod
    def points_are_ordered(
        cls, points: tuple[BriefSeriesPoint, ...]
    ) -> tuple[BriefSeriesPoint, ...]:
        if tuple(point.position for point in points) != tuple(range(len(points))):
            raise ValueError("Series points must have contiguous ordered positions")
        return points


class BriefClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["observed", "interpretation"]
    text: str = Field(min_length=1, max_length=600)
    citation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=16)


class BriefAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: UUID
    kind: VisualizationActionKind
    label: str = Field(min_length=1, max_length=80)


class VisualizationBriefV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    investigation_id: UUID
    question: str = Field(min_length=1, max_length=4_000)
    headline: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=2_000)
    view: VisualizationView = VisualizationView.AUTO
    metrics: tuple[BriefMetric, ...] = Field(default=(), max_length=32)
    comparisons: tuple[BriefComparison, ...] = Field(default=(), max_length=32)
    time_range: BriefTimeRange | None = None
    series: tuple[BriefSeries, ...] = Field(default=(), max_length=12)
    claims: tuple[BriefClaim, ...] = Field(default=(), max_length=64)
    caveats: tuple[str, ...] = Field(default=(), max_length=16)
    outcome_kind: Literal["confidence", "validation"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    actions: tuple[BriefAction, ...] = Field(default=(), max_length=24)

    @field_validator("caveats")
    @classmethod
    def caveats_are_bounded(cls, caveats: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() or len(value) > 500 for value in caveats):
            raise ValueError("Visualization caveats must be 1-500 characters")
        return caveats

    def normalized_json(self) -> str:
        return self.model_dump_json(exclude_none=True, by_alias=True)

    def content_hash(self, *, renderer_configuration: str) -> str:
        material = f"{renderer_configuration}\n{self.normalized_json()}".encode()
        return hashlib.sha256(material).hexdigest()


class VisualizationUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)
    latency_ms: int = Field(default=0, ge=0)


class VisualizationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    visualization_id: UUID
    tenant_id: UUID
    investigation_id: UUID
    brief_id: UUID
    status: VisualizationArtifactStatus
    renderer_kind: Literal["thesys_c1"] = "thesys_c1"
    model: str | None = None
    api_version: str | None = None
    c1_response: str | None = None
    usage: VisualizationUsage = VisualizationUsage()
    failure_category: str | None = None
    retry_of_visualization_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    erased_at: datetime | None = None
    erasure_category: str | None = None

    @model_validator(mode="after")
    def status_content_is_consistent(self) -> VisualizationArtifact:
        if self.status is VisualizationArtifactStatus.READY and (
            not self.c1_response or not self.model or not self.api_version
        ):
            raise ValueError("A ready Visualization requires rendered content metadata")
        if self.status is VisualizationArtifactStatus.FAILED and (
            not self.failure_category or self.c1_response is not None
        ):
            raise ValueError("A failed Visualization requires only a safe failure")
        if self.status is VisualizationArtifactStatus.TOMBSTONED and (
            self.c1_response is not None
            or self.erased_at is None
            or self.erasure_category is None
        ):
            raise ValueError("A tombstoned Visualization retains only erasure metadata")
        return self


class VisualizationActionMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: UUID
    tenant_id: UUID
    visualization_id: UUID
    thread_id: UUID
    investigation_id: UUID
    kind: VisualizationActionKind
    label: str = Field(min_length=1, max_length=80)
    citation_id: UUID | None = None
    follow_up_message: str | None = Field(default=None, max_length=4_000)
    expires_at: datetime
    single_use: bool = False
    consumed_at: datetime | None = None

    @model_validator(mode="after")
    def target_matches_kind(self) -> VisualizationActionMapping:
        citation = self.kind is VisualizationActionKind.OPEN_CITATION
        if citation != (self.citation_id is not None) or citation == (
            self.follow_up_message is not None
        ):
            raise ValueError("Visualization action target does not match its kind")
        return self
