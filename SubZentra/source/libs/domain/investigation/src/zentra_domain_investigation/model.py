from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from zentra_domain_agent_execution import ConfidenceOutcome, OutcomeSignal

from .publication import PublicationCondition


class InvestigationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    EVALUATING = "evaluating"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: The four states an Investigation cannot leave. Named here rather than
#: rediscovered by each caller: "terminal" is a property of the lifecycle, and
#: evidence erasure is one of several things that must not act on a live one.
TERMINAL_STATUSES: frozenset[InvestigationStatus] = frozenset(
    {
        InvestigationStatus.COMPLETED,
        InvestigationStatus.REJECTED,
        InvestigationStatus.FAILED,
        InvestigationStatus.CANCELLED,
    }
)


class EvaluationDirective(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    RETRY = "retry"
    # The evaluation loop ran out of attempts without converging. Distinct from
    # RETRY, which asks for another attempt: this one can only escalate.
    ESCALATE = "escalate"


class ApprovalReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    IRREVERSIBLE_ACTION = "irreversible_action"
    TENANT_POLICY = "tenant_policy"
    CONTRADICTION_UNRESOLVED = "contradiction_unresolved"
    REGULATORY_EXPOSURE = "regulatory_exposure"
    #: A substantive claim cites nothing, or cites evidence that cannot be
    #: followed. Distinct from low confidence: the model may be perfectly sure
    #: and the reviewer still unable to check a word of it.
    EVIDENCE_INCOMPLETE = "evidence_incomplete"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class HumanApprovalStatus(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


class RejectionReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INCORRECT_INTERPRETATION = "incorrect_interpretation"
    POLICY_MISMATCH = "policy_mismatch"
    NEEDS_MORE_ANALYSIS = "needs_more_analysis"


class InvestigationTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    value: str

    def __post_init__(self) -> None:
        if not self.value.startswith("artifact://"):
            raise ValueError("Evidence references must use the artifact:// scheme")


@dataclass(frozen=True, slots=True)
class MetricComparison:
    metric: str
    previous_value: str
    current_value: str
    unit: str
    # What the two values are periods of. Only the agent that chose the
    # granularity can say, so only it fills these in. Optional because an older
    # recording predates them, and because not every comparison is over time —
    # absent means the reader is told nothing rather than told a guess.
    previous_label: str | None = None
    current_label: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    headline: str
    summary: str
    metrics: tuple[MetricComparison, ...]
    evidence_refs: tuple[EvidenceReference, ...]


# A model may be less confident than the evidence supports, never more. These
# are sample-size bounds, not significance tests — real hypothesis testing is
# the Statistician's job. Against the default 0.7 threshold, anything under 30
# observations gates.
#
# Starting values, chosen to be defensible rather than precise; the natural home
# for tenant configuration later.
_SAMPLE_CEILINGS: tuple[tuple[int, float], ...] = (
    (5, 0.50),
    (30, 0.65),
    (100, 0.85),
)
UNKNOWN_SAMPLE_CEILING = 0.50


def confidence_ceiling(sample_size: int | None) -> float:
    """The most confidence a result over this many observations may claim.

    An unknown sample size is treated as the weakest case: a claim whose basis
    cannot be checked does not get to publish itself.
    """
    if sample_size is None or sample_size < 0:
        return UNKNOWN_SAMPLE_CEILING
    for threshold, ceiling in _SAMPLE_CEILINGS:
        if sample_size < threshold:
            return ceiling
    return 1.0


def directive_for_outcome(
    outcome: OutcomeSignal,
    *,
    confidence_threshold: float,
) -> EvaluationDirective:
    """Decide whether an evaluated outcome may complete without a human.

    Retry is not decided here; only the Evaluator knows a recheck disagreed.
    """
    if isinstance(outcome, ConfidenceOutcome):
        passed = outcome.score >= confidence_threshold
    else:
        passed = outcome.passed
    return EvaluationDirective.PASS if passed else EvaluationDirective.REVIEW


@dataclass(frozen=True, slots=True)
class CompletionOutcome:
    finding: Finding
    human_approved: bool


@dataclass(frozen=True, slots=True)
class FailureOutcome:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: UUID
    event_type: str
    investigation_id: UUID
    tenant_id: UUID
    status: InvestigationStatus
    occurred_at: datetime
    artifact_refs: tuple[EvidenceReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HumanApproval:
    approval_id: UUID
    investigation_id: UUID
    tenant_id: UUID
    reason: ApprovalReason
    status: HumanApprovalStatus
    requested_at: datetime
    # Every publication condition that failed, in the policy's own vocabulary.
    # Stored on the approval rather than derived on read: `reason` is the
    # headline, and a reviewer deciding on the headline alone would be deciding
    # on part of the picture.
    failed_conditions: tuple[PublicationCondition, ...] = ()
    decided_at: datetime | None = None
    decided_by: UUID | None = None
    decision_reason: RejectionReason | None = None

    def decide(
        self,
        *,
        decision: ApprovalDecision,
        rejection_reason: RejectionReason | None,
        user_id: UUID,
        now: datetime,
    ) -> bool:
        target = (
            HumanApprovalStatus.GRANTED
            if decision is ApprovalDecision.APPROVE
            else HumanApprovalStatus.REJECTED
        )
        if self.status is target and self.decision_reason is rejection_reason:
            return False
        if self.status is not HumanApprovalStatus.PENDING:
            raise InvestigationTransitionError(
                f"Approval was already decided as {self.status.value}"
            )
        if decision is ApprovalDecision.REJECT and rejection_reason is None:
            raise InvestigationTransitionError("A rejection reason is required")
        if decision is ApprovalDecision.APPROVE and rejection_reason is not None:
            raise InvestigationTransitionError(
                "An approval cannot include a rejection reason"
            )

        self.status = target
        self.decided_at = now
        self.decided_by = user_id
        self.decision_reason = rejection_reason
        return True


@dataclass(slots=True)
class Investigation:
    investigation_id: UUID
    tenant_id: UUID
    question: str
    status: InvestigationStatus
    version: int
    evaluation_attempts: int
    created_at: datetime
    updated_at: datetime
    # Read-compatibility only. Investigations started before ADR-0023 were
    # created from one of two governed scenarios and carry its key; a question
    # is free text now and nothing writes one. Kept because dropping it would
    # make those Investigations unreplayable rather than merely unlabelled —
    # the same reasoning as LEGACY_ROLES in the Agent Execution context.
    scenario_key: str | None = None
    thread_id: UUID | None = None
    thread_sequence: int | None = None
    initiating_message_id: UUID | None = None
    parent_investigation_id: UUID | None = None
    retry_of_investigation_id: UUID | None = None
    finished_at: datetime | None = None
    finding: Finding | None = None
    outcome: OutcomeSignal | None = None
    completion: CompletionOutcome | None = None
    failure: FailureOutcome | None = None
    # Which live Data Connection this Investigation queries through, if any.
    # None means the demo warehouse (today's only reachable source). Set once
    # at creation and never reassigned — ADR-0012: "No source... may switch
    # mid-run."
    data_connection_id: UUID | None = None
    events: list[DomainEvent] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        now: datetime,
        data_connection_id: UUID | None = None,
        thread_id: UUID | None = None,
        thread_sequence: int | None = None,
        initiating_message_id: UUID | None = None,
        parent_investigation_id: UUID | None = None,
        retry_of_investigation_id: UUID | None = None,
    ) -> Investigation:
        thread_link = (thread_id, thread_sequence, initiating_message_id)
        if any(value is not None for value in thread_link) and (
            any(value is None for value in thread_link)
            or (thread_sequence is not None and thread_sequence < 1)
        ):
            raise InvestigationTransitionError(
                "A Thread-linked Investigation requires a Thread, positive sequence, "
                "and initiating message"
            )
        investigation = cls(
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            question=question,
            status=InvestigationStatus.PENDING,
            version=1,
            evaluation_attempts=0,
            created_at=now,
            updated_at=now,
            data_connection_id=data_connection_id,
            thread_id=thread_id,
            thread_sequence=thread_sequence,
            initiating_message_id=initiating_message_id,
            parent_investigation_id=parent_investigation_id,
            retry_of_investigation_id=retry_of_investigation_id,
        )
        investigation._record("investigation.created", now)
        return investigation

    def start(self, now: datetime) -> None:
        self._transition(
            expected={InvestigationStatus.PENDING},
            target=InvestigationStatus.RUNNING,
            event_type="investigation.started",
            now=now,
        )

    def begin_evaluation(self, now: datetime) -> None:
        self._transition(
            expected={InvestigationStatus.RUNNING},
            target=InvestigationStatus.EVALUATING,
            event_type="investigation.evaluation_started",
            now=now,
        )

    def record_evaluation(
        self,
        *,
        directive: EvaluationDirective,
        outcome: OutcomeSignal,
        finding: Finding,
        now: datetime,
        # Which publication conditions failed. Typed rather than strings so
        # renaming a condition cannot silently degrade every gate to the
        # fallback reason.
        failed_conditions: tuple[PublicationCondition, ...] = (),
    ) -> ApprovalReason | None:
        self._require_status({InvestigationStatus.EVALUATING})
        if self.evaluation_attempts >= 3:
            raise InvestigationTransitionError(
                "An investigation cannot exceed three evaluation attempts"
            )

        self.evaluation_attempts += 1
        self.outcome = outcome
        self.finding = finding
        self.updated_at = now
        self.version += 1
        self._record(
            "investigation.validation_completed",
            now,
            artifact_refs=finding.evidence_refs,
            metadata={
                "attempt": self.evaluation_attempts,
                "directive": directive.value,
                "outcome_kind": outcome.kind,
                "confidence": outcome.score
                if isinstance(outcome, ConfidenceOutcome)
                else None,
                "failed_publication_conditions": [
                    condition.value for condition in failed_conditions
                ],
            },
        )

        if directive is EvaluationDirective.PASS:
            self._complete(now, human_approved=False)
            return None

        if directive is EvaluationDirective.RETRY and self.evaluation_attempts < 3:
            self._transition(
                expected={InvestigationStatus.EVALUATING},
                target=InvestigationStatus.RUNNING,
                event_type="investigation.retry_requested",
                now=now,
            )
            return None

        reason = self._approval_reason(directive, outcome, failed_conditions)
        self._transition(
            expected={InvestigationStatus.EVALUATING},
            target=InvestigationStatus.AWAITING_APPROVAL,
            event_type="human_approval.requested",
            now=now,
            metadata={
                "reason": reason.value,
                # Every failure, not the summarising one. A reviewer told only
                # that confidence was low, when the evidence was also
                # unreachable, would approve on a false picture.
                "failed_publication_conditions": [
                    condition.value for condition in failed_conditions
                ],
            },
        )
        return reason

    def decide(
        self,
        *,
        decision: ApprovalDecision,
        rejection_reason: RejectionReason | None,
        now: datetime,
    ) -> None:
        self._require_status({InvestigationStatus.AWAITING_APPROVAL})
        if decision is ApprovalDecision.REJECT and rejection_reason is None:
            raise InvestigationTransitionError("A rejection reason is required")
        if decision is ApprovalDecision.APPROVE and rejection_reason is not None:
            raise InvestigationTransitionError(
                "An approval cannot include a rejection reason"
            )

        if decision is ApprovalDecision.APPROVE:
            self._record("human_approval.granted", now)
            self._complete(now, human_approved=True)
            return

        self._record(
            "human_approval.rejected",
            now,
            metadata={"reason": rejection_reason.value},
        )
        self._transition(
            expected={InvestigationStatus.AWAITING_APPROVAL},
            target=InvestigationStatus.REJECTED,
            event_type="investigation.rejected",
            now=now,
            finished=True,
        )

    def record_denied_decision(
        self,
        now: datetime,
        *,
        role: str,
        user_id: UUID,
    ) -> None:
        """Someone tried to decide a gate they may not decide.

        Recorded rather than only refused. A refusal that leaves no trace means
        the one event worth noticing — repeated attempts by a person who cannot
        approve — is the one event Replay cannot show, and counting attempts
        per *role* would not answer that question.

        The internal user id, never an email or a name, and nothing at all
        about the evidence.
        """
        self._record(
            "human_approval.denied",
            now,
            metadata={"role": role, "user_id": str(user_id)},
        )

    def record_evidence_erased(self, now: datetime, *, category: str) -> None:
        """That evidence was deliberately erased, and when.

        The category and the instant, and nothing about what went. Replay must
        be able to prove work happened and evidence was erased without being
        able to reconstruct the erased conclusion — so this event is the last
        place that content could hide.

        Not a lifecycle transition: the Investigation stays terminal in the
        state it reached. Deleting evidence does not re-decide anything.
        """
        self._record(
            "investigation.evidence_erased",
            now,
            metadata={"category": category},
        )

    def fail(self, failure: FailureOutcome, now: datetime) -> None:
        self._require_status(
            {
                InvestigationStatus.PENDING,
                InvestigationStatus.RUNNING,
                InvestigationStatus.EVALUATING,
            }
        )
        self.failure = failure
        self._transition(
            expected={self.status},
            target=InvestigationStatus.FAILED,
            event_type="investigation.failed",
            now=now,
            metadata={"code": failure.code},
            finished=True,
        )

    def cancel(self, now: datetime) -> None:
        self._require_status(
            {
                InvestigationStatus.PENDING,
                InvestigationStatus.RUNNING,
                InvestigationStatus.EVALUATING,
                InvestigationStatus.AWAITING_APPROVAL,
            }
        )
        self._transition(
            expected={self.status},
            target=InvestigationStatus.CANCELLED,
            event_type="investigation.cancelled",
            now=now,
            finished=True,
        )

    def _complete(self, now: datetime, *, human_approved: bool) -> None:
        if self.finding is None:
            raise InvestigationTransitionError(
                "An investigation cannot complete without a finding"
            )
        self.completion = CompletionOutcome(
            finding=self.finding,
            human_approved=human_approved,
        )
        self._transition(
            expected={
                InvestigationStatus.EVALUATING,
                InvestigationStatus.AWAITING_APPROVAL,
            },
            target=InvestigationStatus.COMPLETED,
            event_type="investigation.completed",
            now=now,
            finished=True,
        )

    @staticmethod
    def _approval_reason(
        directive: EvaluationDirective,
        outcome: OutcomeSignal,
        failed_conditions: tuple[PublicationCondition, ...] = (),
    ) -> ApprovalReason:
        """The headline a reviewer sees first.

        The complete list of failed conditions travels alongside it; this is
        only which one to lead with. Ordered by how much it stops a reviewer
        doing their job: unfollowable evidence means they cannot check
        anything, an open contradiction means the agents disagree, and low
        confidence means the answer is merely weak.
        """
        for condition, reason in (
            (PublicationCondition.EVIDENCED, ApprovalReason.EVIDENCE_INCOMPLETE),
            (
                PublicationCondition.UNCONTRADICTED,
                ApprovalReason.CONTRADICTION_UNRESOLVED,
            ),
            (PublicationCondition.CONVERGED, ApprovalReason.CONTRADICTION_UNRESOLVED),
            (PublicationCondition.CONFIDENT, ApprovalReason.LOW_CONFIDENCE),
        ):
            if condition in failed_conditions:
                return reason

        # No conditions supplied: the pre-policy path, kept so a caller that
        # has not adopted the policy still gets a sensible reason.
        if directive in {
            EvaluationDirective.RETRY,
            EvaluationDirective.ESCALATE,
        }:
            return ApprovalReason.CONTRADICTION_UNRESOLVED
        if isinstance(outcome, ConfidenceOutcome):
            return ApprovalReason.LOW_CONFIDENCE
        return ApprovalReason.TENANT_POLICY

    def _require_status(self, expected: set[InvestigationStatus]) -> None:
        if self.status not in expected:
            allowed = ", ".join(sorted(status.value for status in expected))
            raise InvestigationTransitionError(
                f"Cannot transition investigation from {self.status.value}; "
                f"expected {allowed}"
            )

    def _transition(
        self,
        *,
        expected: set[InvestigationStatus],
        target: InvestigationStatus,
        event_type: str,
        now: datetime,
        metadata: dict[str, Any] | None = None,
        finished: bool = False,
    ) -> None:
        self._require_status(expected)
        self.status = target
        self.updated_at = now
        self.version += 1
        if finished:
            self.finished_at = now
        self._record(event_type, now, metadata=metadata)

    def _record(
        self,
        event_type: str,
        now: datetime,
        *,
        artifact_refs: tuple[EvidenceReference, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        occurred_at = now
        if self.events and occurred_at <= self.events[-1].occurred_at:
            occurred_at = self.events[-1].occurred_at + timedelta(microseconds=1)
        self.events.append(
            DomainEvent(
                event_id=uuid4(),
                event_type=event_type,
                investigation_id=self.investigation_id,
                tenant_id=self.tenant_id,
                status=self.status,
                occurred_at=occurred_at,
                artifact_refs=artifact_refs,
                metadata=metadata or {},
            )
        )
