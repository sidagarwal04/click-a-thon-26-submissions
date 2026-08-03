from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    ApprovalDecision,
    CitationState,
    Claim,
    ClaimKind,
    Contradiction,
    DraftFinding,
    DraftFindingError,
    EvidenceCitation,
    EvidenceReference,
    ExecutionJob,
    ExecutionJobKind,
    Finding,
    HumanApproval,
    Investigation,
    MetricComparison,
    RejectionReason,
    RootCauseState,
    WorkFeedEventKind,
)

from zentra_application_investigation import (
    AuditDelivery,
    AuthenticatedActor,
    ConflictError,
    InvestigationDetail,
    InvestigationNotFoundError,
    InvestigationService,
    PermissionDeniedError,
    PipelineResult,
    Role,
)

TENANT_ID = UUID("51000000-0000-0000-0000-000000000001")
USER_ID = UUID("52000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("53000000-0000-0000-0000-000000000003")
APPROVAL_ID = UUID("54000000-0000-0000-0000-000000000004")
JOB_ID = UUID("54000000-0000-0000-0000-000000000005")
CITATION_ID = UUID("cc000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


class Pipeline:
    def __init__(
        self,
        *,
        score: float = 0.42,
        converged: bool = True,
        analyst_model: str = "gemini/gemini-3.6-flash",
        evaluator_model: str = "nvidia/nemotron-3-ultra-550b-a55b",
        analyst_sample_size: int | None = 500,
        evaluator_sample_size: int | None = 500,
        draft_finding: DraftFinding | None = None,
        evidence_citations: tuple = (),
    ) -> None:
        self._draft_finding = draft_finding
        self._citations = evidence_citations
        self._score = score
        self._converged = converged
        self._analyst_model = analyst_model
        self._evaluator_model = evaluator_model
        self._analyst_sample = analyst_sample_size
        self._evaluator_sample = evaluator_sample_size
        self.calls: list[UUID] = []

    async def run(
        self,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        model_tier: str = "free",
        data_connection_id: UUID | None = None,
    ) -> PipelineResult:
        self.calls.append(investigation_id)
        return PipelineResult(
            finding=Finding(
                headline="EU refund rate increased from 25% to 75%",
                summary="Shipping-delay refunds account for the July increase.",
                metrics=(
                    MetricComparison("order_count", "4", "4", "orders"),
                    MetricComparison("refund_amount", "20.00", "260.00", "usd"),
                    MetricComparison("refund_rate", "25", "75", "percent"),
                ),
                evidence_refs=(
                    EvidenceReference("artifact://seed/eu-refund-spike/2026-06-07"),
                ),
            ),
            outcome=ConfidenceOutcome(
                score=self._score,
                calibration_method="evaluator_independent_recheck",
            ),
            converged=self._converged,
            analyst_model=self._analyst_model,
            evaluator_model=self._evaluator_model,
            analyst_sample_size=self._analyst_sample,
            evaluator_sample_size=self._evaluator_sample,
            draft_finding=self._draft_finding,
            evidence_citations=self._citations,
        )


class Investigations:
    def __init__(self) -> None:
        self.rows: dict[UUID, Investigation] = {}

    async def add(self, investigation: Investigation) -> None:
        self.rows[investigation.investigation_id] = investigation

    async def get(
        self, investigation_id: UUID, *, for_update: bool = False
    ) -> Investigation | None:
        return self.rows.get(investigation_id)

    async def save(
        self,
        investigation: Investigation,
        *,
        expected_version: int,
    ) -> None:
        assert investigation.version > expected_version
        self.rows[investigation.investigation_id] = investigation


class Approvals:
    def __init__(self) -> None:
        self.rows: dict[UUID, HumanApproval] = {}

    async def add(self, approval: HumanApproval) -> None:
        self.rows[approval.approval_id] = approval

    async def get_for_investigation(
        self,
        investigation_id: UUID,
        *,
        approval_id: UUID | None = None,
        for_update: bool = False,
    ) -> HumanApproval | None:
        matches = [
            approval
            for approval in self.rows.values()
            if approval.investigation_id == investigation_id
            and (approval_id is None or approval.approval_id == approval_id)
        ]
        return matches[0] if matches else None

    async def save(self, approval: HumanApproval) -> None:
        self.rows[approval.approval_id] = approval


class Outbox:
    def __init__(self) -> None:
        self.events = []

    async def enqueue(self, events) -> None:
        self.events.extend(events)


class AgentExecutions:
    def __init__(self) -> None:
        self.rows: list[object] = []

    async def add(self, execution: object) -> None:
        self.rows.append(execution)


class Jobs:
    def __init__(self) -> None:
        self.rows: dict[UUID, ExecutionJob] = {}

    async def add_job(self, job: ExecutionJob) -> None:
        self.rows[job.job_id] = job


class Citations:
    def __init__(self) -> None:
        self.rows: dict[UUID, tuple[object, ...]] = {}

    async def add(self, citations) -> None:
        for citation in citations:
            existing = self.rows.setdefault(citation.investigation_id, ())
            self.rows[citation.investigation_id] = (*existing, citation)

    async def for_investigation(self, investigation_id: UUID) -> tuple[object, ...]:
        return self.rows.get(investigation_id, ())


class DraftFindings:
    def __init__(self) -> None:
        self.rows: dict[UUID, object] = {}

    async def add(self, draft: object) -> None:
        self.rows[draft.investigation_id] = draft

    async def latest_for_investigation(self, investigation_id: UUID) -> object | None:
        return self.rows.get(investigation_id)


class Policies:
    def __init__(self, threshold: float = 0.7, tier: str = "free") -> None:
        self.threshold = threshold
        self.tier = tier

    async def confidence_threshold(self, tenant_id: UUID) -> float:
        return self.threshold

    async def model_tier(self, tenant_id: UUID) -> str:
        return self.tier


class UnitOfWork:
    def __init__(self) -> None:
        self.investigations = Investigations()
        self.approvals = Approvals()
        self.agent_executions = AgentExecutions()
        self.jobs = Jobs()
        self.draft_findings = DraftFindings()
        self.citations = Citations()
        self.erasures = Erasures()
        self.policies = Policies()
        self.outbox = Outbox()
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class UnitOfWorkFactory:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.unit_of_work = unit_of_work
        self.tenant_ids: list[UUID] = []

    @asynccontextmanager
    async def __call__(
        self,
        tenant_id: UUID,
        trace_id: UUID,
        span_id: UUID,
    ) -> AsyncIterator[UnitOfWork]:
        self.tenant_ids.append(tenant_id)
        yield self.unit_of_work


class Audit:
    async def flush(self, *, tenant_id: UUID, investigation_id: UUID) -> bool:
        return True

    async def list_timeline(self, *, tenant_id: UUID, investigation_id: UUID):
        return ()


def actor(role: Role = Role.OWNER) -> AuthenticatedActor:
    return AuthenticatedActor(
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        role=role,
        trace_id=UUID("55000000-0000-0000-0000-000000000005"),
        span_id=UUID("56000000-0000-0000-0000-000000000006"),
    )


def service(
    unit_of_work: UnitOfWork,
    *,
    pipeline: Pipeline | None = None,
) -> InvestigationService:
    # Investigation, approval, then erasure ids. A fixed sequence keeps the
    # assertions readable; running out of it is what the cycle prevents.
    ids = iter((INVESTIGATION_ID, JOB_ID, APPROVAL_ID, *(uuid4() for _ in range(8))))
    return InvestigationService(
        unit_of_work_factory=UnitOfWorkFactory(unit_of_work),
        pipeline=pipeline or Pipeline(),
        audit_writer=Audit(),
        audit_reader=Audit(),
        now=lambda: NOW,
        new_id=lambda: next(ids),
    )


@pytest.mark.asyncio
async def test_start_returns_running_before_the_agents_have_run() -> None:
    unit_of_work = UnitOfWork()

    detail = await service(unit_of_work).start(
        actor(Role.MEMBER),
        question="Why did EU refunds increase from June to July 2026?",
    )

    assert detail.status == "running"
    assert detail.outcome is None
    assert detail.pending_approval is None
    assert detail.audit_delivery is AuditDelivery.COMPLETE
    assert unit_of_work.commits == 1
    assert list(unit_of_work.jobs.rows) == [JOB_ID]
    assert unit_of_work.jobs.rows[JOB_ID].investigation_id == INVESTIGATION_ID
    assert [event.event_type for event in unit_of_work.outbox.events] == [
        "investigation.created",
        "investigation.started",
    ]


@pytest.mark.asyncio
async def test_low_confidence_gates_on_a_human_rather_than_publishing() -> None:
    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline(score=0.42))

    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    detail = await application.get(actor(), INVESTIGATION_ID)

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval is not None
    assert detail.pending_approval.reason == "low_confidence"
    assert isinstance(detail.outcome, ConfidenceOutcome)
    assert detail.outcome.score == 0.42


@pytest.mark.asyncio
async def test_confident_converged_result_completes_without_a_human() -> None:
    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline(score=0.91))

    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    detail = await application.get(actor(), INVESTIGATION_ID)

    assert detail.status == "completed"
    assert detail.pending_approval is None


@pytest.mark.asyncio
async def test_unconverged_recheck_gates_even_when_confidence_is_high() -> None:
    unit_of_work = UnitOfWork()
    application = service(
        unit_of_work,
        pipeline=Pipeline(score=0.95, converged=False),
    )

    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    detail = await application.get(actor(), INVESTIGATION_ID)

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval is not None
    assert detail.pending_approval.reason == "contradiction_unresolved"


@pytest.mark.asyncio
async def test_a_viewer_cannot_start_an_investigation() -> None:
    """Role is checked before the question is even normalised, so a Viewer
    cannot learn anything about what would have been accepted."""
    application = service(UnitOfWork())

    with pytest.raises(PermissionDeniedError):
        await application.start(
            actor(Role.VIEWER),
            question="Why did EU refunds increase from June to July 2026?",
        )


@pytest.mark.asyncio
async def test_owner_decision_is_idempotent_and_member_cannot_decide() -> None:
    unit_of_work = UnitOfWork()
    application = service(unit_of_work)
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    started = await application.get(actor(), INVESTIGATION_ID)
    assert started.pending_approval is not None

    with pytest.raises(PermissionDeniedError):
        await application.decide(
            actor(Role.MEMBER),
            investigation_id=INVESTIGATION_ID,
            approval_id=APPROVAL_ID,
            decision=ApprovalDecision.APPROVE,
            rejection_reason=None,
        )

    first = await application.decide(
        actor(),
        investigation_id=INVESTIGATION_ID,
        approval_id=APPROVAL_ID,
        decision=ApprovalDecision.REJECT,
        rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
    )
    replay = await application.decide(
        actor(),
        investigation_id=INVESTIGATION_ID,
        approval_id=APPROVAL_ID,
        decision=ApprovalDecision.REJECT,
        rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
    )

    assert first.status == "rejected"
    assert replay.status == "rejected"


@pytest.mark.asyncio
async def test_invisible_investigation_returns_not_found() -> None:
    with pytest.raises(InvestigationNotFoundError):
        await service(UnitOfWork()).get(actor(Role.VIEWER), INVESTIGATION_ID)


async def outcome_of(pipeline: Pipeline) -> InvestigationDetail:
    application = service(UnitOfWork(), pipeline=pipeline)
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    return await application.get(actor(), INVESTIGATION_ID)


@pytest.mark.asyncio
async def test_same_model_on_both_agents_gates_however_confident() -> None:
    """What fallback actually produced live: the chain collapsed and Gemini
    checked itself. A second pass by one model is not a second opinion."""
    detail = await outcome_of(
        Pipeline(
            score=0.95,
            analyst_model="gemini/gemini-3.6-flash",
            evaluator_model="gemini/gemini-3.6-flash",
        )
    )

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval is not None
    assert detail.pending_approval.reason == "low_confidence"
    assert isinstance(detail.outcome, ConfidenceOutcome)
    assert detail.outcome.score == 0.5
    assert detail.outcome.calibration_method == "capped_independence_none"


@pytest.mark.asyncio
async def test_same_family_may_publish_but_never_at_near_certainty() -> None:
    """Opus checking Sonnet is a real second opinion, so premium is not
    blanket-gated — but they share a training philosophy, so it is bounded."""
    detail = await outcome_of(
        Pipeline(
            score=0.98,
            analyst_model="claude-sonnet-5",
            evaluator_model="claude-opus-5",
        )
    )

    assert detail.status == "completed"
    assert isinstance(detail.outcome, ConfidenceOutcome)
    assert detail.outcome.score == 0.85
    assert detail.outcome.calibration_method == "capped_independence_partial"


@pytest.mark.asyncio
async def test_small_sample_gates_however_confident_the_models_were() -> None:
    """The live regression: Gemini reported 0.95 over eight orders and
    auto-published, where Claude reported 0.55 on the same data and gated."""
    detail = await outcome_of(
        Pipeline(score=0.95, analyst_sample_size=8, evaluator_sample_size=8)
    )

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval is not None
    assert detail.pending_approval.reason == "low_confidence"
    assert isinstance(detail.outcome, ConfidenceOutcome)
    assert detail.outcome.score == 0.65
    assert detail.outcome.calibration_method == "capped_sample_size"


@pytest.mark.asyncio
async def test_the_lower_of_two_independently_counted_samples_is_used() -> None:
    detail = await outcome_of(
        Pipeline(score=0.95, analyst_sample_size=120, evaluator_sample_size=90)
    )

    # 90 lands in the under-100 band, not 120's unbounded one.
    assert isinstance(detail.outcome, ConfidenceOutcome)
    assert detail.outcome.score == 0.85


@pytest.mark.asyncio
async def test_wildly_divergent_sample_counts_gate_as_a_contradiction() -> None:
    detail = await outcome_of(
        Pipeline(score=0.95, analyst_sample_size=500, evaluator_sample_size=40)
    )

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval is not None
    assert detail.pending_approval.reason == "contradiction_unresolved"


@pytest.mark.asyncio
async def test_a_well_evidenced_independent_result_still_publishes() -> None:
    """The ceilings must not simply block everything."""
    detail = await outcome_of(Pipeline(score=0.92))

    assert detail.status == "completed"
    assert isinstance(detail.outcome, ConfidenceOutcome)
    assert detail.outcome.score == 0.92


@pytest.mark.asyncio
async def test_the_question_asked_is_the_question_recorded() -> None:
    """Free text reaches the agents verbatim (ADR-0023).

    There is no registry to look a question up in, so the one thing that must
    hold is that nothing rewrites it on the way through.
    """
    application = service(UnitOfWork())
    asked = "Which warehouse absorbed the backlog after the October cutover?"

    detail = await application.start(actor(), question=asked)

    assert detail.question == asked
    assert detail.scenario_key is None


@pytest.mark.asyncio
async def test_a_question_is_normalised_before_it_is_recorded() -> None:
    """The same normalisation user-authored Thread Messages get.

    A question carrying control characters is refused rather than stored and
    later rendered, and surrounding whitespace never reaches the agents.
    """
    application = service(UnitOfWork())

    detail = await application.start(actor(), question="  Why did refunds rise?  ")
    assert detail.question == "Why did refunds rise?"

    with pytest.raises(ValueError):
        await application.start(actor(), question="Why did\x07 refunds rise?")


def structured_draft() -> DraftFinding:
    return DraftFinding(
        draft_finding_id=UUID("90000000-0000-0000-0000-000000000001"),
        tenant_id=TENANT_ID,
        investigation_id=INVESTIGATION_ID,
        version=1,
        created_at=NOW,
        produced_by_execution_id=UUID("91000000-0000-0000-0000-000000000001"),
        headline="EU refund rate increased from 25% to 75%",
        summary="Governed EU refund amount rose from $20 to $260.",
        claims=(
            Claim(
                claim_id=UUID("92000000-0000-0000-0000-000000000001"),
                kind=ClaimKind.OBSERVED,
                text="EU refund amount rose to $260.00.",
                position=0,
                metric="refund_amount",
                value="260.00",
                period="July 2026",
                citation_ids=(UUID("cc000000-0000-0000-0000-000000000001"),),
            ),
        ),
        contradictions=(),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=ConfidenceOutcome(
            score=0.42,
            calibration_method="insight_bounded_by_evaluator",
        ),
    )


@pytest.mark.asyncio
async def test_a_drafted_investigation_stores_the_draft_with_its_state_change() -> None:
    """Committed alongside the Investigation's own change. A reader must never
    see a completed evaluation whose draft is missing."""
    unit_of_work = UnitOfWork()
    draft = structured_draft()
    application = service(unit_of_work, pipeline=Pipeline(draft_finding=draft))

    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)

    assert unit_of_work.draft_findings.rows[INVESTIGATION_ID] is draft


@pytest.mark.asyncio
async def test_a_refresh_returns_the_stored_draft_without_rerunning_insight() -> None:
    """Insight is a paid model call, and regenerating narrative per read would
    let two readers of the same Investigation see different conclusions."""
    unit_of_work = UnitOfWork()
    draft = structured_draft()
    pipeline = Pipeline(draft_finding=draft)
    application = service(unit_of_work, pipeline=pipeline)

    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    runs_after_execute = len(pipeline.calls)

    first = await application.get(actor(), INVESTIGATION_ID)
    second = await application.get(actor(), INVESTIGATION_ID)

    assert first.draft_finding is draft
    assert second.draft_finding is draft
    assert first.draft_finding.claims[0].position == 0
    assert len(pipeline.calls) == runs_after_execute


@pytest.mark.asyncio
async def test_the_phase_1_path_stores_no_draft_and_stays_readable() -> None:
    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline())

    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    detail = await application.get(actor(), INVESTIGATION_ID)

    assert unit_of_work.draft_findings.rows == {}
    assert detail.draft_finding is None
    assert detail.finding is not None


def cited_draft(*, contradiction: bool = False, cited: bool = True) -> DraftFinding:
    return DraftFinding(
        draft_finding_id=UUID("90000000-0000-0000-0000-000000000002"),
        tenant_id=TENANT_ID,
        investigation_id=INVESTIGATION_ID,
        version=1,
        created_at=NOW,
        produced_by_execution_id=UUID("91000000-0000-0000-0000-000000000001"),
        headline="EU refunds rose $240 in July.",
        summary="Governed EU refund amount rose from $20 to $260.",
        claims=(
            Claim(
                claim_id=UUID("92000000-0000-0000-0000-000000000002"),
                kind=ClaimKind.OBSERVED,
                text="EU refund amount rose to $260.00.",
                position=0,
                metric="refund_amount",
                value="260.00",
                period="July 2026",
                citation_ids=(CITATION_ID,) if cited else (),
            ),
        ),
        contradictions=(
            (Contradiction(detail="Recheck counted 8 rows, not 12."),)
            if contradiction
            else ()
        ),
        root_cause=RootCauseState.UNRESOLVED,
        confidence=None,
    )


def active_citation() -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=CITATION_ID,
        tenant_id=TENANT_ID,
        investigation_id=INVESTIGATION_ID,
        metric="refund_amount",
        filters=(),
        period="July 2026",
        grain="month",
        producing_execution_id=UUID("91000000-0000-0000-0000-000000000001"),
        aggregate_value="260.00",
        evaluator_outcome=None,
        state=CitationState.ACTIVE,
    )


async def run_policy(unit_of_work: UnitOfWork, **pipeline: object):
    application = service(unit_of_work, pipeline=Pipeline(**pipeline))
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    return await application.get(actor(), INVESTIGATION_ID)


@pytest.mark.asyncio
async def test_all_four_conditions_passing_publishes_without_a_human() -> None:
    detail = await run_policy(
        UnitOfWork(),
        score=0.91,
        draft_finding=cited_draft(),
        evidence_citations=(active_citation(),),
    )

    assert detail.status == "completed"
    assert detail.pending_approval is None


class WorkFeed:
    """Records what would have gone to the Work Feed, without a real store."""

    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def append_for_investigation(
        self,
        *,
        tenant_id: UUID,
        investigation_id: UUID,
        kind: WorkFeedEventKind,
        payload: object,
        occurred_at: datetime,
        event_id: UUID | None = None,
    ) -> None:
        self.events.append(
            {"investigation_id": investigation_id, "kind": kind, "payload": payload}
        )


class Visualizations:
    """The visualization repository seam `prepare_published_visualization`
    needs to exist before it will do anything at all."""

    def __init__(self) -> None:
        self.rows: dict[UUID, object] = {}

    async def create(
        self, *, brief_id, brief, renderer_configuration, artifact, actions
    ) -> None:
        self.rows[artifact.investigation_id] = artifact

    async def latest_for_investigation(self, investigation_id: UUID) -> object | None:
        return self.rows.get(investigation_id)


class PublishingUnitOfWork(UnitOfWork):
    """A `UnitOfWork` that also exposes the Work Feed and Visualization
    repository, so a published Finding's handoff to the Visualization Agent
    is actually observable rather than silently skipped."""

    def __init__(self) -> None:
        super().__init__()
        self.work_feed = WorkFeed()
        self.visualizations = Visualizations()


@pytest.mark.asyncio
async def test_auto_publish_hands_the_finding_to_the_visualization_agent_once() -> None:
    unit_of_work = PublishingUnitOfWork()

    detail = await run_policy(
        unit_of_work,
        score=0.91,
        draft_finding=cited_draft(),
        evidence_citations=(active_citation(),),
    )

    assert detail.status == "completed"
    published = [
        event
        for event in unit_of_work.work_feed.events
        if event["kind"] == WorkFeedEventKind.FINDING_PUBLISHED
    ]
    assert len(published) == 1
    visualization_jobs = [
        job
        for job in unit_of_work.jobs.rows.values()
        if job.job_kind == ExecutionJobKind.VISUALIZATION
    ]
    assert len(visualization_jobs) == 1


@pytest.mark.asyncio
async def test_human_approved_publish_hands_finding_to_visualization_agent() -> None:
    unit_of_work = PublishingUnitOfWork()
    application = service(
        unit_of_work,
        pipeline=Pipeline(
            score=0.42,
            draft_finding=cited_draft(),
            evidence_citations=(active_citation(),),
        ),
    )
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)

    await application.decide(
        actor(),
        investigation_id=INVESTIGATION_ID,
        approval_id=APPROVAL_ID,
        decision=ApprovalDecision.APPROVE,
        rejection_reason=None,
    )

    published = [
        event
        for event in unit_of_work.work_feed.events
        if event["kind"] == WorkFeedEventKind.FINDING_PUBLISHED
    ]
    assert len(published) == 1
    visualization_jobs = [
        job
        for job in unit_of_work.jobs.rows.values()
        if job.job_kind == ExecutionJobKind.VISUALIZATION
    ]
    assert len(visualization_jobs) == 1


def test_an_uncited_draft_fails_closed_rather_than_opening_a_gate() -> None:
    """Gating is for a conclusion a reviewer can judge. A substantive claim
    citing nothing is not weak evidence, it is a structurally invalid draft —
    and it never becomes one to gate on."""
    with pytest.raises(DraftFindingError, match="cites no evidence"):
        cited_draft(cited=False)


@pytest.mark.asyncio
async def test_unresolvable_evidence_gates_even_when_the_claim_cites_it() -> None:
    """A citation that cannot be followed backs a claim no better than none."""
    lost = replace(active_citation(), state=CitationState.UNAVAILABLE)

    detail = await run_policy(
        UnitOfWork(),
        score=0.99,
        draft_finding=cited_draft(),
        evidence_citations=(lost,),
    )

    assert detail.status == "awaiting_approval"
    assert "evidenced" in detail.pending_approval.failed_conditions


@pytest.mark.asyncio
async def test_an_open_contradiction_gates() -> None:
    detail = await run_policy(
        UnitOfWork(),
        score=0.99,
        draft_finding=cited_draft(contradiction=True),
        evidence_citations=(active_citation(),),
    )

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval.reason == "contradiction_unresolved"
    assert "uncontradicted" in detail.pending_approval.failed_conditions


@pytest.mark.asyncio
async def test_every_failed_condition_is_reported_not_just_the_headline() -> None:
    """A reviewer told only the headline would decide on part of the picture."""
    detail = await run_policy(
        UnitOfWork(),
        score=0.42,
        converged=False,
        draft_finding=cited_draft(contradiction=True),
        # The citation the claim names is not among them, so its evidence
        # cannot be followed.
        evidence_citations=(),
    )

    failed = set(detail.pending_approval.failed_conditions)
    assert failed == {"converged", "confident", "evidenced", "uncontradicted"}
    # The headline leads with the one that most stops a reviewer working.
    assert detail.pending_approval.reason == "evidence_incomplete"


@pytest.mark.asyncio
async def test_a_gated_draft_stays_reviewable() -> None:
    """Gating is asking a human to look, so there has to be something to look
    at. A gate that hid the draft would be a refusal wearing a gate's name."""
    detail = await run_policy(
        UnitOfWork(),
        score=0.42,
        draft_finding=cited_draft(),
        evidence_citations=(active_citation(),),
    )

    assert detail.status == "awaiting_approval"
    assert detail.draft_finding is not None
    assert detail.draft_finding.claims[0].citation_ids == (CITATION_ID,)


@pytest.mark.asyncio
async def test_the_phase_1_path_still_publishes_on_confidence_alone() -> None:
    """A narrative Finding was never citable, and gating every legacy
    Investigation on a contract that did not exist when it ran would be a
    change of behaviour rather than a policy."""
    detail = await run_policy(UnitOfWork(), score=0.91)

    assert detail.status == "completed"


@pytest.mark.asyncio
async def test_re_evaluating_cannot_produce_a_conflicting_decision() -> None:
    """The lifecycle refuses a second evaluation on a terminal Investigation,
    so a duplicate policy run cannot flip a published Finding into a gate."""
    unit_of_work = UnitOfWork()
    application = service(
        unit_of_work,
        pipeline=Pipeline(
            score=0.91,
            draft_finding=cited_draft(),
            evidence_citations=(active_citation(),),
        ),
    )
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)

    # The lifecycle refuses it; which error it raises is the aggregate's
    # business, and the property under test is that the decision stands.
    with pytest.raises(Exception):  # noqa: B017, PT011
        await application.execute(actor(), INVESTIGATION_ID)

    detail = await application.get(actor(), INVESTIGATION_ID)
    assert detail.status == "completed"
    assert detail.pending_approval is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.MEMBER, Role.VIEWER])
async def test_a_membership_that_cannot_decide_leaves_a_trace(role: Role) -> None:
    """A refusal that leaves no trace means the one event worth noticing —
    repeated attempts by a membership that cannot approve — is the one event
    Replay cannot show."""
    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline(score=0.42))
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    before = len(unit_of_work.outbox.events)

    with pytest.raises(PermissionDeniedError):
        await application.decide(
            actor(role),
            investigation_id=INVESTIGATION_ID,
            approval_id=APPROVAL_ID,
            decision=ApprovalDecision.APPROVE,
            rejection_reason=None,
        )

    denied = [
        event
        for event in unit_of_work.outbox.events[before:]
        if event.event_type == "human_approval.denied"
    ]
    assert len(denied) == 1
    # The role and the internal user id — enough to count repeated attempts
    # by one person, which counting per role could never answer. Nothing about
    # the evidence, and no email or name.
    assert denied[0].metadata == {"role": role.value, "user_id": str(USER_ID)}


@pytest.mark.asyncio
async def test_a_denied_attempt_changes_nothing() -> None:
    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline(score=0.42))
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)

    with pytest.raises(PermissionDeniedError):
        await application.decide(
            actor(Role.VIEWER),
            investigation_id=INVESTIGATION_ID,
            approval_id=APPROVAL_ID,
            decision=ApprovalDecision.APPROVE,
            rejection_reason=None,
        )
    detail = await application.get(actor(), INVESTIGATION_ID)

    assert detail.status == "awaiting_approval"
    assert detail.pending_approval is not None


@pytest.mark.asyncio
async def test_decisions_appear_in_causal_order() -> None:
    """Requested before denied before granted. A timeline that reordered them
    would tell a different story about what happened."""
    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline(score=0.42))
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)

    with pytest.raises(PermissionDeniedError):
        await application.decide(
            actor(Role.VIEWER),
            investigation_id=INVESTIGATION_ID,
            approval_id=APPROVAL_ID,
            decision=ApprovalDecision.APPROVE,
            rejection_reason=None,
        )
    await application.decide(
        actor(),
        investigation_id=INVESTIGATION_ID,
        approval_id=APPROVAL_ID,
        decision=ApprovalDecision.APPROVE,
        rejection_reason=None,
    )

    approval_events = [
        event.event_type
        for event in unit_of_work.outbox.events
        if event.event_type.startswith("human_approval.")
    ]
    assert approval_events == [
        "human_approval.requested",
        "human_approval.denied",
        "human_approval.granted",
    ]


@pytest.mark.asyncio
async def test_no_decision_event_carries_customer_narrative() -> None:
    """A decision is who, what and why-in-a-typed-reason. The Finding's prose
    is not part of it, and ClickHouse is where it would become permanent."""
    import json as json_module

    unit_of_work = UnitOfWork()
    application = service(unit_of_work, pipeline=Pipeline(score=0.42))
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    await application.decide(
        actor(),
        investigation_id=INVESTIGATION_ID,
        approval_id=APPROVAL_ID,
        decision=ApprovalDecision.REJECT,
        rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
    )

    for event in unit_of_work.outbox.events:
        if not event.event_type.startswith("human_approval."):
            continue
        payload = json_module.dumps(event.metadata).lower()
        assert "refund rate increased" not in payload
        assert "shipping-delay" not in payload
        assert "260.00" not in payload


class Erasures:
    """An in-memory erasure, honouring the two rules the service depends on:
    a request for an already-completed erasure comes back completed, and only a
    terminal Investigation may be erased."""

    def __init__(self, terminal: bool = True) -> None:
        self.completed: dict[UUID, object] = {}
        self.erase_calls = 0
        self._terminal = terminal

    async def request(self, *, erasure_id, tenant_id, investigation_id, category, now):
        from zentra_domain_investigation import (
            ErasureError,
            ErasureOperation,
            ErasureProgress,
        )

        if not self._terminal:
            raise ErasureError(
                "Evidence can only be erased from a terminal Investigation; "
                "this one is running"
            )
        existing = self.completed.get(investigation_id)
        if existing is not None:
            return existing
        return ErasureOperation(
            erasure_id=erasure_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            category=category,
            progress=ErasureProgress.REQUESTED,
            requested_at=now,
        )

    async def erase(self, *, investigation_id, category, now):
        from zentra_domain_investigation import ErasureOperation, ErasureProgress

        self.erase_calls += 1
        done = ErasureOperation(
            erasure_id=UUID("93000000-0000-0000-0000-000000000001"),
            tenant_id=TENANT_ID,
            investigation_id=investigation_id,
            category=category,
            progress=ErasureProgress.COMPLETED,
            requested_at=now,
            completed_at=now,
            attempts=1,
        )
        self.completed[investigation_id] = done
        return done


async def completed_investigation(unit_of_work: UnitOfWork):
    application = service(unit_of_work, pipeline=Pipeline(score=0.91))
    await application.start(
        actor(), question="Why did EU refunds increase from June to July 2026?"
    )
    await application.execute(actor(), INVESTIGATION_ID)
    return application


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.MEMBER, Role.VIEWER])
async def test_only_owners_and_admins_may_delete_evidence(role: Role) -> None:
    """The real rule, not a stubbed service raising on command."""
    unit_of_work = UnitOfWork()
    unit_of_work.erasures = Erasures()
    application = await completed_investigation(unit_of_work)

    with pytest.raises(PermissionDeniedError):
        await application.delete_evidence(
            actor(role), investigation_id=INVESTIGATION_ID
        )

    assert unit_of_work.erasures.erase_calls == 0


@pytest.mark.asyncio
async def test_an_owner_deletes_and_it_is_recorded_once() -> None:
    unit_of_work = UnitOfWork()
    unit_of_work.erasures = Erasures()
    application = await completed_investigation(unit_of_work)

    await application.delete_evidence(actor(), investigation_id=INVESTIGATION_ID)

    erased = [
        event
        for event in unit_of_work.outbox.events
        if event.event_type == "investigation.evidence_erased"
    ]
    assert len(erased) == 1
    assert erased[0].metadata == {"category": "tenant_request"}


@pytest.mark.asyncio
async def test_asking_twice_erases_once_and_records_once() -> None:
    """Re-recording would put a second event at a new instant on a timeline
    where the content went once."""
    unit_of_work = UnitOfWork()
    unit_of_work.erasures = Erasures()
    application = await completed_investigation(unit_of_work)

    await application.delete_evidence(actor(), investigation_id=INVESTIGATION_ID)
    await application.delete_evidence(actor(), investigation_id=INVESTIGATION_ID)

    erased = [
        event
        for event in unit_of_work.outbox.events
        if event.event_type == "investigation.evidence_erased"
    ]
    assert len(erased) == 1
    assert unit_of_work.erasures.erase_calls == 1


@pytest.mark.asyncio
async def test_a_live_investigation_is_a_conflict() -> None:
    unit_of_work = UnitOfWork()
    unit_of_work.erasures = Erasures(terminal=False)
    application = await completed_investigation(unit_of_work)

    with pytest.raises(ConflictError, match="terminal"):
        await application.delete_evidence(actor(), investigation_id=INVESTIGATION_ID)

    assert unit_of_work.erasures.erase_calls == 0
