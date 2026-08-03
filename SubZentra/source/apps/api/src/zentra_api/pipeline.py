from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from zentra_adapter_postgres import PostgresInvestigationUnitOfWorkFactory
from zentra_adapter_telemetry import record_insight_execution
from zentra_application_investigation import PipelineResult
from zentra_domain_agent_execution import (
    AgentExecutionRecord,
    AgentExecutionStart,
    AgentRole,
    ConfidenceOutcome,
    ExecutionStatus,
    OutcomeSignal,
    reject_legacy_role,
)
from zentra_domain_investigation import (
    AgentEventPayload,
    CitationFilter,
    Claim,
    ClaimKind,
    Contradiction,
    DomainEvent,
    DraftFinding,
    EvidenceCitation,
    EvidenceReference,
    Finding,
    InvestigationStatus,
    MetricComparison,
    RootCauseState,
    WorkFeedEventKind,
)

from .outcomes import InsightOutcome, PipelineOutcome, ValidatedEvidence


def _provider_of(model: str | None) -> str | None:
    """The vendor, from the model id the router recorded.

    `gemini/gemini-3.6-flash` names both; taking the first segment avoids a
    second source of truth about which provider served a call.

    An unprefixed id yields nothing rather than itself. Returning `"gpt-5"` as a
    provider would invent a vendor that does not exist and, because provider is
    a metric dimension, mint a permanent series named after a model.
    """
    if not model or "/" not in model:
        return None
    return model.split("/", maxsplit=1)[0]


#: Error types an operator is expected to see, and the only ones named in
#: telemetry. An allowlist rather than a split on the first colon: the graph
#: happens to format errors as `Type: message`, but that is its convention, not
#: a guarantee, and one message with a colon in the wrong place would publish
#: whatever preceded it.
_KNOWN_ERROR_CATEGORIES = frozenset(
    {
        "AbsentEvidenceError",
        "MalformedAgentResponseError",
        "NoEnabledAgentError",
        "UncitableClaimError",
        "UngroundedClaimError",
        "UnsupportedCausalClaimError",
    }
)


def _error_category(errors: tuple[str, ...]) -> str | None:
    """The exception type, never its message.

    A refusal message names a claim position and a governed metric; an
    unexpected one could name anything. The type tells a provider outage from a
    contract break, and cannot quote evidence. Anything unrecognized reports as
    `unexpected` — which is itself the useful signal, because it means a class
    of failure nobody has triaged.
    """
    if not errors:
        return None
    candidate = errors[0].split(":", maxsplit=1)[0].strip()
    return candidate if candidate in _KNOWN_ERROR_CATEGORIES else "unexpected"


class UncitableClaimError(RuntimeError):
    """A substantive claim has no validated evidence to cite."""


class CancellationRequested(RuntimeError):
    category = "cancellation_requested"
    transient = False


SYSTEM_TRACE_ID = UUID(int=0)
SYSTEM_SPAN_ID = UUID(int=0)

# The completion event already uses the execution id as its event id, and
# the outbox deduplicates on that. Deriving the start's id keeps both
# stable across an at-least-once retry without colliding with each other.
_STARTED_NAMESPACE = UUID("5f9d1e3a-0000-4000-8000-000000000001")
_CAPABILITY_NAMESPACE = UUID("5f9d1e3a-0000-4000-8000-000000000002")
_HANDOFF_NAMESPACE = UUID("5f9d1e3a-0000-4000-8000-000000000003")
_UPDATE_NAMESPACE = UUID("5f9d1e3a-0000-4000-8000-000000000004")
_TOOL_NAMESPACE = UUID("5f9d1e3a-0000-4000-8000-000000000005")
_CAPABILITY_BY_ROLE = {
    AgentRole.ORCHESTRATOR: "plan_investigation",
    AgentRole.CUBE_ANALYST: "query_semantic_metrics",
    AgentRole.EVALUATOR: "validate_evidence",
    AgentRole.INSIGHT: "draft_finding",
}
_PREDECESSOR_BY_ROLE = {
    AgentRole.CUBE_ANALYST: "orchestrator_v1",
    AgentRole.EVALUATOR: "cube_analyst_v1",
    AgentRole.INSIGHT: "evaluator_v1",
}


def _optional_str(value: object) -> str | None:
    """A blank label is no label. A model that emits "" has said nothing, and
    stringifying it would caption a metric with an empty period."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class PostgresExecutionRecorder:
    """Commits each agent execution as it finishes.

    Persisting per step rather than at the end is what makes an interrupted
    investigation replayable up to the point it stopped.
    """

    def __init__(
        self,
        unit_of_work_factory: PostgresInvestigationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def cancellation_checkpoint(
        self, tenant_id: UUID, investigation_id: UUID
    ) -> None:
        async with self._unit_of_work_factory(
            tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            job = await unit_of_work.jobs.get_for_investigation(investigation_id)
        if job is not None and job.cancel_requested_at is not None:
            raise CancellationRequested("Cancellation was requested")

    async def record_started(self, start: AgentExecutionStart) -> None:
        reject_legacy_role(start.role)
        async with self._unit_of_work_factory(
            start.tenant_id,
            SYSTEM_TRACE_ID,
            SYSTEM_SPAN_ID,
        ) as unit_of_work:
            await unit_of_work.outbox.enqueue([_started_event(start)])
            await unit_of_work.work_feed.append_for_investigation(
                tenant_id=start.tenant_id,
                investigation_id=start.investigation_id,
                kind=WorkFeedEventKind.AGENT_STARTED,
                payload=AgentEventPayload(
                    execution_id=start.execution_id,
                    agent_id=start.agent_id,
                    role=start.role.value,
                    summary=f"{start.role.value.replace('_', ' ').title()} started.",
                ),
                occurred_at=start.started_at,
                event_id=start.execution_id,
            )
            capability = _CAPABILITY_BY_ROLE[start.role]
            await unit_of_work.work_feed.append_for_investigation(
                tenant_id=start.tenant_id,
                investigation_id=start.investigation_id,
                kind=WorkFeedEventKind.AGENT_CAPABILITY_USED,
                payload=AgentEventPayload(
                    execution_id=start.execution_id,
                    agent_id=start.agent_id,
                    role=start.role.value,
                    capability_id=capability,
                    summary="A declared capability is in use.",
                ),
                occurred_at=start.started_at,
                event_id=uuid5(_CAPABILITY_NAMESPACE, str(start.execution_id)),
            )
            predecessor = _PREDECESSOR_BY_ROLE.get(start.role)
            if predecessor is not None:
                await unit_of_work.work_feed.append_for_investigation(
                    tenant_id=start.tenant_id,
                    investigation_id=start.investigation_id,
                    kind=WorkFeedEventKind.AGENT_HANDOFF,
                    payload=AgentEventPayload(
                        execution_id=start.execution_id,
                        agent_id=start.agent_id,
                        role=start.role.value,
                        from_agent_id=predecessor,
                        to_agent_id=start.agent_id,
                        summary="Responsibility moved to the next governed role.",
                    ),
                    occurred_at=start.started_at,
                    event_id=uuid5(_HANDOFF_NAMESPACE, str(start.execution_id)),
                )
            await unit_of_work.work_feed.append_for_investigation(
                tenant_id=start.tenant_id,
                investigation_id=start.investigation_id,
                kind=WorkFeedEventKind.AGENT_PUBLIC_UPDATE,
                payload=AgentEventPayload(
                    execution_id=start.execution_id,
                    agent_id=start.agent_id,
                    role=start.role.value,
                    summary="The governed step is running.",
                ),
                occurred_at=start.started_at,
                event_id=uuid5(_UPDATE_NAMESPACE, str(start.execution_id)),
            )
            await unit_of_work.commit()

    async def record(self, execution: AgentExecutionRecord) -> None:
        if execution.role is AgentRole.INSIGHT:
            # Here rather than in the graph: this is where the finished record
            # already exists, so the telemetry cannot disagree with what was
            # persisted about the same step.
            record_insight_execution(
                agent_id=execution.agent_id,
                model=execution.usage.model,
                provider=_provider_of(execution.usage.model),
                fallback_count=len(execution.fallbacks),
                input_tokens=execution.usage.input_tokens,
                output_tokens=execution.usage.output_tokens,
                cost_usd=str(execution.usage.cost_usd),
                duration_ms=execution.latency_ms,
                status=execution.status.value,
                error_category=_error_category(execution.errors),
            )
        # Before the transaction opens. The role travels into the audit
        # ledger's metadata, and Audit Entries are immutable — a legacy value
        # written there could never be corrected.
        reject_legacy_role(execution.role)
        async with self._unit_of_work_factory(
            execution.tenant_id,
            SYSTEM_TRACE_ID,
            SYSTEM_SPAN_ID,
        ) as unit_of_work:
            await unit_of_work.agent_executions.add(execution)
            # Same transaction as the row itself, so the ledger can never
            # disagree with what was actually persisted.
            await unit_of_work.outbox.enqueue([_audit_event(execution)])
            # One event per tool the Agent ran, so the chat surface can say
            # "searched the catalog, queried Cube" rather than showing a
            # silent gap while an Agent iterates. The tool *name* is safe to
            # publish; its arguments and results are not, and
            # `AgentEventPayload` has nowhere to put them.
            for index, invocation in enumerate(execution.tool_calls):
                await unit_of_work.work_feed.append_for_investigation(
                    tenant_id=execution.tenant_id,
                    investigation_id=execution.investigation_id,
                    kind=WorkFeedEventKind.AGENT_CAPABILITY_USED,
                    payload=AgentEventPayload(
                        execution_id=execution.execution_id,
                        agent_id=execution.agent_id,
                        role=execution.role.value,
                        capability_id=invocation.name,
                        summary=(
                            f"Used {invocation.name.replace('_', ' ')}."
                            if invocation.ok
                            else f"{invocation.name.replace('_', ' ')} was refused."
                        ),
                    ),
                    occurred_at=execution.completed_at,
                    # Deterministic per (execution, position), like every other
                    # id here: a redelivered record must not append the same
                    # tool twice.
                    event_id=uuid5(
                        _TOOL_NAMESPACE, f"{execution.execution_id}:{index}"
                    ),
                )
            await unit_of_work.work_feed.append_for_investigation(
                tenant_id=execution.tenant_id,
                investigation_id=execution.investigation_id,
                kind=WorkFeedEventKind.AGENT_COMPLETED,
                payload=AgentEventPayload(
                    execution_id=execution.execution_id,
                    agent_id=execution.agent_id,
                    role=execution.role.value,
                    summary=(
                        f"{execution.role.value.replace('_', ' ').title()} completed."
                    ),
                    provider=_provider_of(execution.usage.model),
                    model=execution.usage.model,
                    fallback_count=len(execution.fallbacks),
                    latency_ms=execution.latency_ms,
                    input_tokens=execution.usage.input_tokens,
                    output_tokens=execution.usage.output_tokens,
                    cost_usd=execution.usage.cost_usd,
                ),
                occurred_at=execution.completed_at,
            )
            await unit_of_work.commit()


def _started_event(start: AgentExecutionStart) -> DomainEvent:
    """Identity and position only.

    There is nothing to say about the work yet — no outcome, no usage, no
    evidence. Saying only that it began is the whole point.
    """
    return DomainEvent(
        event_id=uuid5(_STARTED_NAMESPACE, str(start.execution_id)),
        event_type="agent.execution_started",
        investigation_id=start.investigation_id,
        tenant_id=start.tenant_id,
        status=InvestigationStatus.RUNNING,
        occurred_at=start.started_at,
        metadata={
            "agent_id": start.agent_id,
            "role": start.role.value,
            "step": start.step,
            "execution_id": str(start.execution_id),
        },
    )


def _audit_event(execution: AgentExecutionRecord) -> DomainEvent:
    """Process metadata and artifact pointers only.

    The agent's actual output — including result rows — stays in Postgres and
    is reachable solely through the `artifact://` reference carried here.
    """
    return DomainEvent(
        event_id=execution.execution_id,
        event_type=(
            "agent.execution_completed"
            if execution.status is ExecutionStatus.SUCCESS
            else "agent.execution_failed"
        ),
        investigation_id=execution.investigation_id,
        tenant_id=execution.tenant_id,
        status=InvestigationStatus.RUNNING,
        occurred_at=execution.completed_at,
        artifact_refs=tuple(
            EvidenceReference(reference) for reference in execution.evidence_refs
        ),
        metadata={
            "agent_id": execution.agent_id,
            "role": execution.role.value,
            "step": execution.step,
            "execution_id": str(execution.execution_id),
            "execution_status": execution.status.value,
            "latency_ms": execution.latency_ms,
            "input_tokens": execution.usage.input_tokens,
            "output_tokens": execution.usage.output_tokens,
            "total_cost_usd": str(execution.usage.cost_usd),
            "model": execution.usage.model,
            "outcome_kind": execution.outcome.kind if execution.outcome else None,
            "confidence": execution.confidence,
            "errors": list(execution.errors),
            # Which rungs failed before this one answered. Process metadata, so
            # it belongs in the ledger, and it is how the next provider outage
            # gets diagnosed from Replay instead of by hand.
            "fallbacks": list(execution.fallbacks),
        },
    )


def _pipeline_result(
    outcome: PipelineOutcome,
    *,
    investigation_id: UUID,
    tenant_id: UUID,
) -> PipelineResult:
    """Adapt what the run established to what the application expects.

    The seam a field rename used to slip through: everything else mocks the
    pipeline, so a renamed field on `PipelineOutcome` still type-checked, still
    passed every test, and only a live run found it.
    """
    draft, citations = _draft_with_citations(
        outcome.insight,
        outcome.evidence,
        evaluator_outcome=outcome.outcome,
        investigation_id=investigation_id,
        tenant_id=tenant_id,
    )
    return PipelineResult(
        finding=Finding(
            headline=outcome.headline,
            summary=outcome.summary,
            metrics=tuple(
                MetricComparison(
                    metric=str(metric["metric"]),
                    previous_value=str(metric["previous_value"]),
                    current_value=str(metric["current_value"]),
                    unit=str(metric["unit"]),
                    previous_label=_optional_str(metric.get("previous_label")),
                    current_label=_optional_str(metric.get("current_label")),
                )
                for metric in outcome.metrics
            ),
            evidence_refs=tuple(
                EvidenceReference(reference) for reference in outcome.evidence_refs
            ),
        ),
        outcome=outcome.outcome,
        converged=outcome.converged,
        contradictions=outcome.contradictions,
        # The evidence the application needs to bound the confidence: which
        # models actually served, and how much data each one counted.
        analyst_model=outcome.analyst_model,
        evaluator_model=outcome.evaluator_model,
        analyst_sample_size=outcome.analyst_sample_size,
        evaluator_sample_size=outcome.evaluator_sample_size,
        draft_finding=draft,
        evidence_citations=citations,
    )


def _draft_with_citations(
    insight: InsightOutcome,
    evidence: Sequence[ValidatedEvidence],
    *,
    evaluator_outcome: OutcomeSignal,
    investigation_id: UUID,
    tenant_id: UUID,
) -> tuple[DraftFinding, tuple[EvidenceCitation, ...]]:
    """Assemble the Draft Finding and the Citations its claims rest on.

    Here rather than in the graph adapter, because building Investigation
    domain objects is not the agent runtime's job — and here rather than in the
    agent, because a Citation assembled from Insight's output would be a second
    account of the same claim rather than evidence for it.

    Citations are keyed by metric and period and reused, so two claims about
    July's refunds share one measurement instead of holding copies that can
    drift.
    """
    by_metric: dict[str, ValidatedEvidence] = {}
    for item in evidence:
        if item.metric in by_metric:
            # Last-write-wins here would leave a citation carrying filters the
            # claim does not rest on, which is precisely the corroboration
            # this whole contract exists to prevent.
            raise UncitableClaimError(
                f"Upstream state carries two measurements for {item.metric!r}; "
                f"a citation cannot say which one a claim rests on"
            )
        by_metric[item.metric] = item
    citations: dict[tuple[str, str | None], EvidenceCitation] = {}
    claims: list[Claim] = []

    for position, raw in enumerate(insight.claims):
        kind = ClaimKind(str(raw["kind"]))
        metric = _optional_str(raw.get("metric"))
        value = _optional_str(raw.get("value"))
        period = _optional_str(raw.get("period"))
        citation_ids: tuple[UUID, ...] = ()

        if kind is ClaimKind.OBSERVED:
            measured = by_metric.get(metric or "")
            if measured is None:
                # The agent already refuses a claim citing a metric the
                # aggregate lacks. Reaching here means upstream state and the
                # draft disagree, which is not something to paper over.
                raise UncitableClaimError(
                    f"Claim {position} cannot be cited: no validated evidence "
                    f"for its metric"
                )
            key = (measured.metric, period)
            if key not in citations:
                citations[key] = _citation(
                    measured,
                    value=value or "",
                    period=period,
                    evaluator_outcome=evaluator_outcome,
                    investigation_id=investigation_id,
                    tenant_id=tenant_id,
                )
            citation_ids = (citations[key].citation_id,)

        claims.append(
            Claim(
                claim_id=uuid4(),
                kind=kind,
                text=str(raw["text"]),
                position=position,
                metric=metric,
                value=value,
                period=period,
                citation_ids=citation_ids,
            )
        )

    draft = DraftFinding(
        draft_finding_id=uuid4(),
        tenant_id=tenant_id,
        investigation_id=investigation_id,
        version=1,
        created_at=datetime.now(UTC),
        produced_by_execution_id=insight.execution_id,
        headline=insight.headline,
        summary=insight.summary,
        claims=tuple(claims),
        contradictions=tuple(
            Contradiction(detail=detail) for detail in insight.contradictions
        ),
        root_cause=RootCauseState(insight.root_cause),
        confidence=(
            insight.outcome if isinstance(insight.outcome, ConfidenceOutcome) else None
        ),
    )
    return draft, tuple(citations.values())


def _citation(
    measured: ValidatedEvidence,
    *,
    value: str,
    period: str | None,
    evaluator_outcome: OutcomeSignal,
    investigation_id: UUID,
    tenant_id: UUID,
) -> EvidenceCitation:
    """The citation's figure *is* the claim's figure.

    Taken from the claim rather than re-derived from the period, because the
    two can disagree: where the aggregate names no label for a side, a claim
    may legitimately carry that side's value with no period, and choosing by
    period would then cite the other side. A citation whose figure differs
    from its claim's is worse than no citation — it looks like corroboration.

    The claim's value is already proven to be one of this metric's two sides
    by the Insight Agent, so copying it here cannot launder an invention.
    """
    if value not in {measured.previous_value, measured.current_value}:
        raise UncitableClaimError(
            f"A claim's value for {measured.metric!r} is not one the validated "
            f"aggregate carries"
        )
    return EvidenceCitation(
        citation_id=uuid4(),
        tenant_id=tenant_id,
        investigation_id=investigation_id,
        metric=measured.metric,
        filters=tuple(
            CitationFilter(
                member=str(item.get("member", "")),
                operator=str(item.get("operator", "")),
                values=tuple(str(v) for v in item.get("values", [])),
            )
            for item in measured.filters
        ),
        period=period,
        grain=measured.grain,
        producing_execution_id=measured.producing_execution_id,
        aggregate_value=value,
        evaluator_outcome=evaluator_outcome,
    )
