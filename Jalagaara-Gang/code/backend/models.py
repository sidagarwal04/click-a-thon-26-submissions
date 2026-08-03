"""Pydantic mirror of contracts/evidence_bundle.schema.json. Keep the two in lockstep."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Status = Literal["culprit", "contributor", "normal"]


class Window(BaseModel):
    start: datetime
    end: datetime


class BaselineWindow(BaseModel):
    method: str
    description: str
    weeks: int = 3


class Anomaly(BaseModel):
    detected: bool
    observed: float
    expected: float
    abs_delta: float
    pct_delta: float
    score: float
    direction: Literal["drop", "spike"]


class Factor(BaseModel):
    factor: str
    contribution_pct: float
    from_: float
    to: float

    model_config = {"populate_by_name": True, "alias_generator": lambda n: "from" if n == "from_" else n}


class FactorDecomposition(BaseModel):
    method: str = "log_additive"
    factors: list[Factor]
    primary_factor: str


class DrilldownNode(BaseModel):
    depth: int
    split_dimension: str
    segment: dict[str, Any]
    metric_from: float | None = None
    metric_to: float | None = None
    contribution_pct: float
    status: Status
    query_id: str


class RuledOut(BaseModel):
    hypothesis: str
    evidence: str
    query_id: str


class Query(BaseModel):
    id: str
    sql: str
    result_summary: dict[str, Any] = {}
    langfuse_span_id: str | None = None


class NarrativeVerification(BaseModel):
    passed: bool
    unverified_numbers: list[str] = []


class EvidenceBundle(BaseModel):
    investigation_id: str
    created_at: datetime
    metric: str
    grain: str = "hour"
    target_window: Window
    baseline_window: BaselineWindow
    anomaly: Anomaly
    factor_decomposition: FactorDecomposition
    drilldown: list[DrilldownNode]
    localized_segment: dict[str, Any] = {}
    ruled_out: list[RuledOut]
    queries: list[Query]
    narrative: str | None = None
    narrative_verification: NarrativeVerification | None = None
    trace_url: str | None = None
