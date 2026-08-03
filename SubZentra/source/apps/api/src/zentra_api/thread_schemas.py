from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from zentra_application_investigation import (
    InvestigationDetail,
    RoutingResult,
    ThreadDetail,
    ThreadInvestigationSummary,
    ThreadMessageDetail,
    ThreadPage,
    ThreadSummary,
)

from .schemas import (
    DraftFindingResponse,
    EvidenceCitationResponse,
    FindingResponse,
    InvestigationDetailResponse,
    MetricComparisonResponse,
    OutcomeResponse,
    UsageResponse,
    _outcome_response,
)


class ThreadMessageRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"message": ("Why did EU refunds increase from June to July 2026?")}
            ]
        },
    )

    message: str = Field(min_length=1, max_length=4_000)


class RoutingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: str
    scenario_key: str | None = None
    canonical_question: str | None = None
    clarification: str | None = None
    suggestions: list[str]

    @classmethod
    def from_detail(cls, detail: RoutingResult) -> RoutingResponse:
        return cls(
            disposition=detail.disposition.value,
            scenario_key=detail.scenario_key,
            canonical_question=detail.canonical_question,
            clarification=detail.clarification,
            suggestions=list(detail.suggestions),
        )


class ThreadMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID
    kind: str
    content: str
    created_at: datetime
    authored_by_user: bool

    @classmethod
    def from_detail(cls, detail: ThreadMessageDetail) -> ThreadMessageResponse:
        return cls(
            message_id=detail.message_id,
            kind=detail.kind.value,
            content=detail.content,
            created_at=detail.created_at,
            authored_by_user=detail.authored_by_user,
        )


class ThreadActionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_append_message: bool
    can_archive: bool
    can_restore: bool
    can_delete: bool
    can_cancel: bool
    can_retry: bool


class ThreadApprovalStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    reason: str
    status: str
    failed_conditions: list[str]
    requested_at: datetime
    decided_at: datetime | None
    decision_reason: str | None
    can_decide: bool

    @classmethod
    def from_detail(
        cls, detail: ThreadInvestigationSummary
    ) -> ThreadApprovalStateResponse:
        assert detail.approval is not None
        approval = detail.approval
        return cls(
            approval_id=approval.approval_id,
            reason=approval.reason.value,
            status=approval.status.value,
            failed_conditions=[value.value for value in approval.failed_conditions],
            requested_at=approval.requested_at,
            decided_at=approval.decided_at,
            decision_reason=(
                approval.decision_reason.value if approval.decision_reason else None
            ),
            can_decide=detail.can_decide_approval,
        )


class ThreadInvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: UUID
    sequence: int
    status: str
    parent_investigation_id: UUID | None
    retry_of_investigation_id: UUID | None
    created_at: datetime
    updated_at: datetime
    canonical_question: str
    finding: FindingResponse | None
    draft_finding: DraftFindingResponse | None
    outcome: OutcomeResponse | None
    approval: ThreadApprovalStateResponse | None
    citations: list[EvidenceCitationResponse]
    audit_delivery: str
    usage: UsageResponse

    @classmethod
    def from_detail(
        cls, detail: ThreadInvestigationSummary
    ) -> ThreadInvestigationResponse:
        finding = None
        if detail.finding is not None:
            finding = FindingResponse(
                headline=detail.finding.headline,
                summary=detail.finding.summary,
                metrics=[
                    MetricComparisonResponse(
                        metric=value.metric,
                        previous_value=value.previous_value,
                        previous_label=value.previous_label,
                        current_value=value.current_value,
                        current_label=value.current_label,
                        unit=value.unit,
                    )
                    for value in detail.finding.metrics
                ],
                evidence_references=[
                    value.value for value in detail.finding.evidence_refs
                ],
            )
        draft = None
        if detail.draft_finding is not None:
            converted = InvestigationDetailResponse.from_detail(
                InvestigationDetail(
                    investigation_id=detail.investigation_id,
                    question=detail.question,
                    scenario_key=detail.scenario_key,
                    status=detail.status,
                    version=detail.version,
                    evaluation_attempts=detail.evaluation_attempts,
                    created_at=detail.created_at,
                    updated_at=detail.updated_at,
                    finished_at=detail.finished_at,
                    finding=detail.finding,
                    draft_finding=detail.draft_finding,
                    evidence_citations=detail.citations,
                    outcome=detail.outcome,
                    pending_approval=None,
                    timeline=(),
                    audit_delivery=detail.audit_delivery,
                    usage=detail.usage,
                )
            )
            draft = converted.draft_finding
        return cls(
            investigation_id=detail.investigation_id,
            sequence=detail.sequence,
            status=detail.status.value,
            parent_investigation_id=detail.parent_investigation_id,
            retry_of_investigation_id=detail.retry_of_investigation_id,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
            canonical_question=detail.question,
            finding=finding,
            draft_finding=draft,
            outcome=_outcome_response(detail.outcome),
            approval=(
                ThreadApprovalStateResponse.from_detail(detail)
                if detail.approval is not None
                else None
            ),
            citations=[
                EvidenceCitationResponse.from_domain(value)
                for value in detail.citations
            ],
            audit_delivery=detail.audit_delivery.value,
            usage=UsageResponse(
                input_tokens=detail.usage.input_tokens,
                output_tokens=detail.usage.output_tokens,
                total_cost_usd=str(detail.usage.cost_usd),
                latency_ms=detail.usage.latency_ms,
            ),
        )


class ThreadResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "thread_id": "43000000-0000-0000-0000-000000000001",
                    "project_id": "42000000-0000-0000-0000-000000000001",
                    "title": "How is the business doing?",
                    "status": "draft",
                    "created_at": "2026-08-01T09:00:00Z",
                    "updated_at": "2026-08-01T09:00:00Z",
                    "latest_activity_at": "2026-08-01T09:00:00Z",
                    "messages": [
                        {
                            "message_id": "44000000-0000-0000-0000-000000000001",
                            "kind": "user_question",
                            "content": "How is the business doing?",
                            "created_at": "2026-08-01T09:00:00Z",
                            "authored_by_user": True,
                        },
                        {
                            "message_id": "44000000-0000-0000-0000-000000000002",
                            "kind": "router_clarification",
                            "content": (
                                "I could not map that message to a governed "
                                "question. Please choose or rephrase one supported "
                                "question.\n- Why did EU refunds increase from "
                                "June to July 2026?\n- Which sales channel accounted "
                                "for the "
                                "increase in North America revenue from October to "
                                "November 2026?"
                            ),
                            "created_at": "2026-08-01T09:00:00Z",
                            "authored_by_user": False,
                        },
                    ],
                    "investigation_id": None,
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_cost_usd": "0",
                        "latency_ms": 0,
                    },
                    "routing": {
                        "disposition": "unsupported",
                        "scenario_key": None,
                        "canonical_question": None,
                        "clarification": (
                            "I could not map that message to a governed question. "
                            "Please choose or rephrase one supported question."
                        ),
                        "suggestions": [
                            "Why did EU refunds increase from June to July 2026?",
                            (
                                "Which sales channel accounted for the increase in "
                                "North America revenue from October to November 2026?"
                            ),
                        ],
                    },
                    "actions": {
                        "can_append_message": True,
                        "can_archive": True,
                        "can_restore": False,
                        "can_delete": True,
                        "can_cancel": False,
                        "can_retry": False,
                    },
                }
            ]
        },
    )

    thread_id: UUID
    project_id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_activity_at: datetime
    messages: list[ThreadMessageResponse]
    investigation_id: UUID | None = None
    investigations: list[ThreadInvestigationResponse] = Field(default_factory=list)
    event_cursor: int = 0
    usage: UsageResponse
    routing: RoutingResponse | None = None
    actions: ThreadActionsResponse

    @classmethod
    def from_detail(cls, detail: ThreadDetail) -> ThreadResponse:
        return cls(
            thread_id=detail.thread_id,
            project_id=detail.project_id,
            title=detail.title,
            status=detail.status.value,
            created_at=detail.created_at,
            updated_at=detail.updated_at,
            latest_activity_at=detail.latest_activity_at,
            messages=[
                ThreadMessageResponse.from_detail(message)
                for message in detail.messages
            ],
            investigation_id=detail.investigation_id,
            investigations=[
                ThreadInvestigationResponse.from_detail(value)
                for value in detail.investigations
            ],
            event_cursor=detail.event_cursor,
            usage=UsageResponse(
                input_tokens=detail.usage.input_tokens,
                output_tokens=detail.usage.output_tokens,
                total_cost_usd=str(detail.usage.cost_usd),
                latency_ms=detail.usage.latency_ms,
            ),
            routing=(
                RoutingResponse.from_detail(detail.routing) if detail.routing else None
            ),
            actions=ThreadActionsResponse(
                can_append_message=detail.can_append_message,
                can_archive=detail.can_archive,
                can_restore=detail.can_restore,
                can_delete=detail.can_delete,
                can_cancel=detail.can_cancel,
                can_retry=detail.can_retry,
            ),
        )


class ThreadSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: UUID
    project_id: UUID
    title: str
    status: str
    latest_activity_at: datetime
    investigation_id: UUID | None = None

    @classmethod
    def from_detail(cls, detail: ThreadSummary) -> ThreadSummaryResponse:
        return cls(
            thread_id=detail.thread_id,
            project_id=detail.project_id,
            title=detail.title,
            status=detail.status.value,
            latest_activity_at=detail.latest_activity_at,
            investigation_id=detail.investigation_id,
        )


class ThreadPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ThreadSummaryResponse]
    next_cursor: str | None

    @classmethod
    def from_detail(cls, detail: ThreadPage) -> ThreadPageResponse:
        return cls(
            items=[ThreadSummaryResponse.from_detail(item) for item in detail.items],
            next_cursor=detail.next_cursor,
        )
