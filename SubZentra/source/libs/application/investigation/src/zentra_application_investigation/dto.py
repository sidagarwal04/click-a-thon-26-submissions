"""What the application hands to and takes from its callers.

Split from `service.py`, which crossed the repository's 600-line limit as
Phase 2 added Draft Findings and Evidence Citations. Nothing here decides
anything; these are shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from zentra_domain_agent_execution import OutcomeSignal
from zentra_domain_investigation import (
    DomainEvent,
    DraftFinding,
    EvidenceCitation,
    Finding,
    InvestigationStatus,
)


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class AuditDelivery(StrEnum):
    COMPLETE = "complete"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class UsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0


class PermissionDeniedError(PermissionError):
    pass


class InvestigationNotFoundError(LookupError):
    pass


class ConflictError(RuntimeError):
    pass


class ScenarioUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    user_id: UUID
    tenant_id: UUID
    role: Role
    trace_id: UUID
    span_id: UUID


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """What the agent pipeline established for one investigation."""

    finding: Finding
    outcome: OutcomeSignal
    converged: bool
    contradictions: tuple[str, ...] = ()
    # What actually served each agent, and how many underlying records each
    # counted. The application grades independence and bounds confidence from
    # these rather than trusting the score the models reported.
    analyst_model: str | None = None
    evaluator_model: str | None = None
    analyst_sample_size: int | None = None
    evaluator_sample_size: int | None = None
    # Present only on the Phase 2 path. Absent means the Orchestrator wrote the
    # narrative and no Insight Agent ran — not that Insight failed, which fails
    # the run closed instead.
    draft_finding: DraftFinding | None = None
    # The evidence its claims rest on. Shared across claims, so this is a
    # set of measurements rather than one per claim.
    evidence_citations: tuple[EvidenceCitation, ...] = ()


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    entry_id: UUID
    event_type: str
    status: str
    created_at: datetime
    artifact_refs: tuple[str, ...] = ()
    delivery: AuditDelivery = AuditDelivery.COMPLETE
    agent_id: str | None = None
    step: int | None = None
    model: str | None = None
    # Which rungs failed before `model` answered. Replay shows the degradation
    # instead of only the provider that happened to succeed.
    fallbacks: tuple[str, ...] = ()
    # Which publication conditions failed, in the policy's own vocabulary, so
    # Replay can explain a decision rather than restate it.
    failed_conditions: tuple[str, ...] = ()
    # Safe usage: what the step cost and how long it took. Written to the
    # ledger from the first Phase 1 execution and never read back, so
    # Replay could not answer "why was this slow?" at all.
    latency_ms: int | None = None
    total_cost_usd: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    @classmethod
    def from_domain_event(
        cls,
        event: DomainEvent,
        *,
        delivery: AuditDelivery,
    ) -> TimelineEntry:
        return cls(
            entry_id=event.event_id,
            event_type=event.event_type,
            status=event.status.value,
            created_at=event.occurred_at,
            artifact_refs=tuple(ref.value for ref in event.artifact_refs),
            delivery=delivery,
            agent_id=event.metadata.get("agent_id"),
            step=event.metadata.get("step"),
            model=event.metadata.get("model"),
            fallbacks=tuple(event.metadata.get("fallbacks") or ()),
            failed_conditions=tuple(
                event.metadata.get("failed_publication_conditions") or ()
            ),
        )


@dataclass(frozen=True, slots=True)
class AuditReplay:
    timeline: tuple[TimelineEntry, ...]
    delivery: AuditDelivery


@dataclass(frozen=True, slots=True)
class PendingApproval:
    approval_id: UUID
    reason: str
    requested_at: datetime
    can_decide: bool
    # Every condition the deterministic policy found failing, in its own
    # vocabulary. `reason` is the headline; this is the whole picture, and
    # a reviewer deciding on the headline alone would be deciding on part
    # of it.
    failed_conditions: tuple[str, ...] = ()
    # Safe usage: what the step cost and how long it took. Written to the
    # ledger from the first Phase 1 execution and never read back, so
    # Replay could not answer "why was this slow?" at all.
    latency_ms: int | None = None
    total_cost_usd: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class InvestigationDetail:
    investigation_id: UUID
    question: str
    # Read-compatibility only. Investigations created before free-text
    # questions carry the governed scenario they were started from; nothing
    # writes one now. See ADR-0023.
    scenario_key: str | None
    status: InvestigationStatus
    version: int
    evaluation_attempts: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    finding: Finding | None
    # The Phase 2 structured draft, when the Investigation has one. An
    # Investigation that ran before Insight existed has `finding` without
    # `draft_finding`, and the API says so rather than dressing the
    # narrative up as resolvable evidence.
    draft_finding: DraftFinding | None
    evidence_citations: tuple[EvidenceCitation, ...]
    outcome: OutcomeSignal | None
    pending_approval: PendingApproval | None
    timeline: tuple[TimelineEntry, ...]
    audit_delivery: AuditDelivery
    # Server-decided, like `can_decide` on an approval. The client asking
    # its own role would be a second authorisation rule that can disagree
    # with the one that actually applies.
    can_delete_evidence: bool = False
    usage: UsageSummary = UsageSummary()
