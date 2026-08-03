"""The wire shapes.

Split from `routes.py`, which crossed the repository's 600-line limit as the
Draft Finding and Evidence Citation surfaces landed. Every model forbids extra
fields, so a response can only carry what is declared here — which is also what
makes "no raw rows, prompts or credentials" a property of the type rather than
of each construction site.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from zentra_application_investigation import InvestigationDetail, VisualizationDetail
from zentra_domain_agent_execution import ConfidenceOutcome, ValidationOutcome
from zentra_domain_investigation import (
    ApprovalDecision,
    EvidenceCitation,
    RejectionReason,
    VisualizationArtifact,
    VisualizationBriefV1,
)


class DependencyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    dependencies: dict[str, DependencyStatus]
    configuration: dict[str, bool]


class ContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    tenant_id: UUID
    email: str
    tenant_name: str
    role: str


class CatalogMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    description: str | None = None
    #: Only for dimensions, and only where the dimension holds few enough values
    #: to enumerate. Empty means unconstrained, not empty.
    values: list[str] = Field(default_factory=list)


class CatalogSummaryResponse(BaseModel):
    """What this tenant can actually be asked about.

    Replaces the fixed list of governed scenarios (ADR-0023). A client that has
    to offer the user a starting question needs the tenant's own vocabulary,
    and this is the same governed catalog the Cube Analyst reasons over — so a
    suggestion the UI makes is one the agent can genuinely answer.
    """

    model_config = ConfigDict(extra="forbid")

    measures: list[CatalogMemberResponse]
    dimensions: list[CatalogMemberResponse]


class InvestigationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Free text (ADR-0023). Bounded here so an oversized body is refused at the
    #: edge; the application normalises and re-validates it, since the Thread
    #: path reaches the same service without passing through this model.
    question: str = Field(min_length=1, max_length=4000)
    #: Which Data Connection to ask it against. Omitted resolves to the
    #: tenant's only connection, or the demo warehouse when it has none; a
    #: tenant with several is asked to choose rather than guessed at.
    data_connection_id: UUID | None = None


class VisualizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visualization_id: UUID
    investigation_id: UUID
    status: str
    renderer_kind: str
    model: str | None
    api_version: str | None
    c1_response: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: str
    latency_ms: int
    failure_category: str | None
    retry_of_visualization_id: UUID | None
    fallback_brief: VisualizationBriefV1 | None
    created_at: datetime
    updated_at: datetime
    erased_at: datetime | None
    erasure_category: str | None

    @classmethod
    def from_detail(cls, detail: VisualizationDetail) -> VisualizationResponse:
        artifact: VisualizationArtifact = detail.artifact
        return cls(
            visualization_id=artifact.visualization_id,
            investigation_id=artifact.investigation_id,
            status=artifact.status.value,
            renderer_kind=artifact.renderer_kind,
            model=artifact.model,
            api_version=artifact.api_version,
            c1_response=artifact.c1_response,
            input_tokens=artifact.usage.input_tokens,
            output_tokens=artifact.usage.output_tokens,
            cost_usd=str(artifact.usage.cost_usd),
            latency_ms=artifact.usage.latency_ms,
            failure_category=artifact.failure_category,
            retry_of_visualization_id=artifact.retry_of_visualization_id,
            fallback_brief=detail.fallback_brief,
            created_at=artifact.created_at,
            updated_at=artifact.updated_at,
            erased_at=artifact.erased_at,
            erasure_category=artifact.erasure_category,
        )


class VisualizationActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: dict[str, object] = Field(default_factory=dict)


class VisualizationActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    citation_id: UUID | None = None
    thread_id: UUID | None = None
    investigation_id: UUID | None = None


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ApprovalDecision
    reason: RejectionReason | None = None

    @model_validator(mode="after")
    def validate_reason(self) -> ApprovalDecisionRequest:
        if self.decision is ApprovalDecision.REJECT and self.reason is None:
            raise ValueError("A rejection reason is required")
        if self.decision is ApprovalDecision.APPROVE and self.reason is not None:
            raise ValueError("Approval must not include a rejection reason")
        return self


class MetricComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    previous_value: str
    previous_label: str | None = None
    current_value: str
    current_label: str | None = None
    unit: str


class FindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str
    summary: str
    metrics: list[MetricComparisonResponse]
    evidence_references: list[str]


class ClaimResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: UUID
    # The distinction the reader most needs, and the one prose cannot be
    # trusted to carry. Spelled out rather than `str` so the API keeps the
    # constraint the domain enum already makes.
    kind: Literal["observed", "interpretation"]
    text: str
    position: int
    # The measurement behind an observed claim: which governed metric, what
    # value, and which period that value covers. Null on an interpretation.
    metric: str | None
    value: str | None
    period: str | None
    # Empty until Evidence Citations exist. Present now so a client written
    # against this shape does not need changing when they arrive.
    citation_ids: list[UUID]


class ContradictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    resolved: bool


class CitationFilterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member: str
    operator: str
    values: list[str]


class EvidenceCitationResponse(BaseModel):
    """One validated measurement, addressable on its own.

    The user-facing contract ADR 0011 asks for, in place of an opaque
    `artifact://` pointer: what was measured, scoped how, by which execution,
    and what the independent recheck made of it.
    """

    model_config = ConfigDict(extra="forbid")

    citation_id: UUID
    metric: str
    filters: list[CitationFilterResponse]
    period: str | None
    grain: str | None
    producing_execution_id: UUID | None
    aggregate_value: str
    # What the independent recheck made of the execution that produced it.
    # ADR 0011 lists it, and a reader judging evidence needs it.
    evaluator_outcome: OutcomeResponse | None
    state: Literal["active", "unavailable", "tombstoned"]

    @classmethod
    def from_domain(cls, citation: EvidenceCitation) -> EvidenceCitationResponse:
        return cls(
            citation_id=citation.citation_id,
            metric=citation.metric,
            filters=[
                CitationFilterResponse(
                    member=f.member,
                    operator=f.operator,
                    values=list(f.values),
                )
                for f in citation.filters
            ],
            period=citation.period,
            grain=citation.grain,
            producing_execution_id=citation.producing_execution_id,
            aggregate_value=citation.aggregate_value,
            evaluator_outcome=_outcome_response(citation.evaluator_outcome),
            state=citation.state.value,
        )


class TombstoneResponse(BaseModel):
    """What a citation resolves to once its evidence was deliberately erased.

    Identity, category, timestamp. `extra="forbid"` and the absence of every
    other field are what stop a later change reintroducing the metric, the
    period or the filters — a filter can carry customer values as readily as
    an aggregate can.
    """

    model_config = ConfigDict(extra="forbid")

    state: Literal["tombstoned"] = "tombstoned"
    citation_id: UUID
    category: str
    erased_at: datetime


class EvidenceDeletionRequest(BaseModel):
    """Deleting evidence is irreversible, so it is not a bare POST.

    The caller states the Investigation it means. A confirmation the client can
    default to would not be a confirmation.
    """

    model_config = ConfigDict(extra="forbid")

    confirm_investigation_id: UUID


class ValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["validation"] = "validation"
    passed: bool
    checks: list[str]
    issues: list[str]


class ConfidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["confidence"] = "confidence"
    score: float
    calibration_method: str


OutcomeResponse = Annotated[
    ConfidenceResponse | ValidationResponse,
    Field(discriminator="kind"),
]


def _outcome_response(outcome: object) -> OutcomeResponse | None:
    """One mapping, shared by the Investigation's outcome and a citation's."""
    if isinstance(outcome, ConfidenceOutcome):
        return ConfidenceResponse(
            score=outcome.score,
            calibration_method=outcome.calibration_method,
        )
    if isinstance(outcome, ValidationOutcome):
        return ValidationResponse(
            passed=outcome.passed,
            checks=list(outcome.checks),
            issues=list(outcome.issues),
        )
    return None


class DraftFindingResponse(BaseModel):
    """The Phase 2 structured draft.

    Sits beside `finding` rather than replacing it. An Investigation that ran
    before Insight existed has `finding` and a null `draft_finding`, which is
    how a client tells a legacy narrative apart from claims that are genuinely
    structured and will become individually citable.
    """

    model_config = ConfigDict(extra="forbid")

    draft_finding_id: UUID
    version: int
    created_at: datetime
    produced_by_execution_id: UUID | None
    headline: str
    summary: str
    claims: list[ClaimResponse]
    contradictions: list[ContradictionResponse]
    # ADR 0011 admits no Root Cause Claim until a causal-evidence standard
    # is accepted, so this is the only value Phase 2 can produce.
    root_cause: Literal["unresolved"]
    confidence: ConfidenceResponse | None
    # Shared across claims, so they arrive once rather than once per
    # citing claim. A claim's `citation_ids` index into these.
    citations: list[EvidenceCitationResponse]


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    # The headline reason, and every condition behind it. Both use the
    # publication policy's vocabulary, so the API, the UI and Replay are
    # describing the same decision in the same words.
    reason: str
    requested_at: datetime
    can_decide: bool
    failed_conditions: list[str]


class TimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: UUID
    event_type: str
    status: str
    created_at: datetime
    artifact_references: list[str]
    delivery: str
    agent_id: str | None = None
    step: int | None = None
    model: str | None = None
    # The rungs that failed before `model` answered, and why a publication
    # decision went the way it did — both in the vocabulary the rest of the
    # product already uses.
    fallbacks: list[str] = []
    failed_conditions: list[str] = []
    # Safe usage only: timing and spend, never the work itself.
    latency_ms: int | None = None
    total_cost_usd: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class UsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int
    output_tokens: int
    total_cost_usd: str
    latency_ms: int


class InvestigationDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    canonical_question: str
    #: Present only on Investigations started before free-text questions.
    scenario_key: str | None
    status: str
    version: int
    evaluation_attempts: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    finding: FindingResponse | None
    draft_finding: DraftFindingResponse | None
    outcome: OutcomeResponse | None
    pending_approval: ApprovalResponse | None
    timeline: list[TimelineResponse]
    audit_delivery: str
    # Whether this caller may erase this Investigation's evidence. Decided
    # by the server for the same reason `can_decide` is.
    can_delete_evidence: bool
    usage: UsageResponse

    @classmethod
    def from_detail(cls, detail: InvestigationDetail) -> InvestigationDetailResponse:
        finding = None
        if detail.finding is not None:
            finding = FindingResponse(
                headline=detail.finding.headline,
                summary=detail.finding.summary,
                metrics=[
                    MetricComparisonResponse(
                        metric=metric.metric,
                        previous_value=metric.previous_value,
                        previous_label=metric.previous_label,
                        current_value=metric.current_value,
                        current_label=metric.current_label,
                        unit=metric.unit,
                    )
                    for metric in detail.finding.metrics
                ],
                evidence_references=[
                    reference.value for reference in detail.finding.evidence_refs
                ],
            )
        draft = None
        if detail.draft_finding is not None:
            source = detail.draft_finding
            draft = DraftFindingResponse(
                draft_finding_id=source.draft_finding_id,
                version=source.version,
                created_at=source.created_at,
                produced_by_execution_id=source.produced_by_execution_id,
                headline=source.headline,
                summary=source.summary,
                claims=[
                    ClaimResponse(
                        claim_id=claim.claim_id,
                        kind=claim.kind.value,
                        text=claim.text,
                        position=claim.position,
                        metric=claim.metric,
                        value=claim.value,
                        period=claim.period,
                        citation_ids=list(claim.citation_ids),
                    )
                    for claim in source.claims
                ],
                contradictions=[
                    ContradictionResponse(
                        detail=contradiction.detail,
                        resolved=contradiction.resolved,
                    )
                    for contradiction in source.contradictions
                ],
                root_cause=source.root_cause.value,
                citations=[
                    EvidenceCitationResponse.from_domain(citation)
                    for citation in detail.evidence_citations
                ],
                confidence=(
                    ConfidenceResponse(
                        score=source.confidence.score,
                        calibration_method=source.confidence.calibration_method,
                    )
                    if source.confidence is not None
                    else None
                ),
            )
        outcome = _outcome_response(detail.outcome)
        approval = None
        if detail.pending_approval is not None:
            approval = ApprovalResponse(
                approval_id=detail.pending_approval.approval_id,
                reason=detail.pending_approval.reason,
                requested_at=detail.pending_approval.requested_at,
                can_decide=detail.pending_approval.can_decide,
                failed_conditions=list(detail.pending_approval.failed_conditions),
            )
        return cls(
            investigation_id=detail.investigation_id,
            canonical_question=detail.question,
            scenario_key=detail.scenario_key,
            status=detail.status.value,
            version=detail.version,
            evaluation_attempts=detail.evaluation_attempts,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
            finished_at=detail.finished_at,
            finding=finding,
            draft_finding=draft,
            outcome=outcome,
            pending_approval=approval,
            timeline=[
                TimelineResponse(
                    entry_id=entry.entry_id,
                    event_type=entry.event_type,
                    status=entry.status,
                    created_at=entry.created_at,
                    artifact_references=list(entry.artifact_refs),
                    delivery=entry.delivery.value,
                    agent_id=entry.agent_id,
                    step=entry.step,
                    model=entry.model,
                    fallbacks=list(entry.fallbacks),
                    failed_conditions=list(entry.failed_conditions),
                    latency_ms=entry.latency_ms,
                    total_cost_usd=entry.total_cost_usd,
                    input_tokens=entry.input_tokens,
                    output_tokens=entry.output_tokens,
                )
                for entry in detail.timeline
            ],
            audit_delivery=detail.audit_delivery.value,
            can_delete_evidence=detail.can_delete_evidence,
            usage=UsageResponse(
                input_tokens=detail.usage.input_tokens,
                output_tokens=detail.usage.output_tokens,
                total_cost_usd=str(detail.usage.cost_usd),
                latency_ms=detail.usage.latency_ms,
            ),
        )
