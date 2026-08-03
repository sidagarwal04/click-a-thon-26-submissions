from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkFeedEventKind(StrEnum):
    MESSAGE_ADDED = "thread.message_added"
    ROUTING_CLARIFICATION = "thread.routing_clarification"
    ROUTING_RESOLVED = "thread.routing_resolved"
    INVESTIGATION_QUEUED = "investigation.queued"
    INVESTIGATION_STARTED = "investigation.started"
    INVESTIGATION_STATUS_CHANGED = "investigation.status_changed"
    INVESTIGATION_CANCEL_REQUESTED = "investigation.cancel_requested"
    INVESTIGATION_CANCELLED = "investigation.cancelled"
    INVESTIGATION_COMPLETED = "investigation.completed"
    INVESTIGATION_FAILED = "investigation.failed"
    INVESTIGATION_RETRY_CREATED = "investigation.retry_created"
    AGENT_STARTED = "agent.started"
    AGENT_PUBLIC_UPDATE = "agent.public_update"
    AGENT_CAPABILITY_USED = "agent.capability_used"
    AGENT_HANDOFF = "agent.handoff"
    AGENT_COMPLETED = "agent.completed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    FINDING_PUBLISHED = "finding.published"
    VISUALIZATION_REQUESTED = "visualization.requested"
    VISUALIZATION_STARTED = "visualization.started"
    VISUALIZATION_COMPLETED = "visualization.completed"
    VISUALIZATION_FAILED = "visualization.failed"
    VISUALIZATION_RETRY_REQUESTED = "visualization.retry_requested"
    VISUALIZATION_TOMBSTONED = "visualization.tombstoned"


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MessageEventPayload(_Payload):
    type: Literal["message"] = "message"
    message_id: UUID
    message_kind: str = Field(min_length=1, max_length=32)


class RoutingEventPayload(_Payload):
    type: Literal["routing"] = "routing"
    disposition: str = Field(min_length=1, max_length=32)
    scenario_key: str | None = Field(default=None, max_length=64)
    suggestion_count: int = Field(default=0, ge=0, le=20)


class InvestigationEventPayload(_Payload):
    type: Literal["investigation"] = "investigation"
    investigation_id: UUID
    status: str = Field(min_length=1, max_length=32)
    parent_investigation_id: UUID | None = None
    retry_of_investigation_id: UUID | None = None
    failure_category: str | None = Field(default=None, max_length=64)


class AgentEventPayload(_Payload):
    type: Literal["agent"] = "agent"
    execution_id: UUID
    agent_id: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=64)
    capability_id: str | None = Field(default=None, max_length=128)
    from_agent_id: str | None = Field(default=None, max_length=128)
    to_agent_id: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=280)
    provider: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=160)
    fallback_count: int = Field(default=0, ge=0, le=16)
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)


class ApprovalEventPayload(_Payload):
    type: Literal["approval"] = "approval"
    approval_id: UUID
    status: str = Field(min_length=1, max_length=16)
    failed_conditions: tuple[str, ...] = Field(default=(), max_length=16)


class FindingEventPayload(_Payload):
    type: Literal["finding"] = "finding"
    investigation_id: UUID
    citation_count: int = Field(ge=0, le=1_000)


class VisualizationEventPayload(_Payload):
    type: Literal["visualization"] = "visualization"
    visualization_id: UUID
    investigation_id: UUID
    status: str = Field(min_length=1, max_length=24)
    model: str | None = Field(default=None, max_length=160)
    api_version: str | None = Field(default=None, max_length=32)
    failure_category: str | None = Field(default=None, max_length=64)


WorkFeedPayload = Annotated[
    MessageEventPayload
    | RoutingEventPayload
    | InvestigationEventPayload
    | AgentEventPayload
    | ApprovalEventPayload
    | FindingEventPayload
    | VisualizationEventPayload,
    Field(discriminator="type"),
]


class ThreadEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: UUID
    tenant_id: UUID
    thread_id: UUID
    sequence: int = Field(ge=1)
    kind: WorkFeedEventKind
    occurred_at: datetime
    payload: WorkFeedPayload
