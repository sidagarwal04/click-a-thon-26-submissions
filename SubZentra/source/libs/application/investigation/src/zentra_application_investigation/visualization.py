from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol
from uuid import UUID, uuid5

from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    AgentEventPayload,
    BriefAction,
    BriefClaim,
    BriefComparison,
    BriefMetric,
    BriefSeries,
    BriefSeriesPoint,
    BriefTimeRange,
    CitationState,
    DraftFinding,
    EvidenceCitation,
    ExecutionJob,
    ExecutionJobKind,
    Investigation,
    VisualizationActionKind,
    VisualizationActionMapping,
    VisualizationArtifact,
    VisualizationArtifactStatus,
    VisualizationBriefV1,
    VisualizationEventPayload,
    VisualizationView,
    WorkFeedEventKind,
)

from .ports import InvestigationUnitOfWork

RENDERER_CONFIGURATION = "thesys_c1:c1/anthropic/claude-sonnet-4/v-20251230"
_IDENTITY_NAMESPACE = UUID("b8df65f1-5649-4d41-8f92-e7e414592d22")
# `VisualizationBriefV1.series` admits 12. Truncating here keeps a
# pathologically wide Finding from failing validation at the very end.
_MAX_SERIES = 12


class IdFactory(Protocol):
    def __call__(self) -> UUID: ...


async def prepare_published_visualization(
    *,
    unit_of_work: InvestigationUnitOfWork,
    investigation: Investigation,
    draft: DraftFinding | None,
    citations: tuple[EvidenceCitation, ...],
    now: datetime,
) -> VisualizationArtifact | None:
    """Persist the governed brief, safe actions, artifact, job, and handoff."""
    if investigation.finding is None:
        return None
    # Older application-level fake UoWs deliberately exercise only analytical
    # behavior. Production UoWs always expose the visualization repository.
    if not hasattr(unit_of_work, "visualizations"):
        return None
    existing = await unit_of_work.visualizations.latest_for_investigation(
        investigation.investigation_id
    )
    if existing is not None:
        return existing

    active = tuple(value for value in citations if value.state is CitationState.ACTIVE)
    actions = _actions(investigation, active, now)
    brief = _brief(investigation, draft, active, actions)
    content_hash = brief.content_hash(renderer_configuration=RENDERER_CONFIGURATION)
    brief_id = uuid5(
        _IDENTITY_NAMESPACE,
        f"brief:{investigation.investigation_id}:{investigation.version}:{content_hash}",
    )
    visualization_id = uuid5(
        _IDENTITY_NAMESPACE,
        f"artifact:{brief_id}:{RENDERER_CONFIGURATION}:0",
    )
    mappings = tuple(
        value.model_copy(update={"visualization_id": visualization_id})
        for value in actions[1]
    )
    artifact = VisualizationArtifact(
        visualization_id=visualization_id,
        tenant_id=investigation.tenant_id,
        investigation_id=investigation.investigation_id,
        brief_id=brief_id,
        status=VisualizationArtifactStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    await unit_of_work.visualizations.create(
        brief_id=brief_id,
        brief=brief,
        renderer_configuration=RENDERER_CONFIGURATION,
        artifact=artifact,
        actions=mappings,
    )
    await unit_of_work.jobs.add_job(
        ExecutionJob.create(
            job_id=uuid5(_IDENTITY_NAMESPACE, f"job:{visualization_id}"),
            tenant_id=investigation.tenant_id,
            investigation_id=investigation.investigation_id,
            visualization_id=visualization_id,
            job_kind=ExecutionJobKind.VISUALIZATION,
            max_attempts=2,
            now=now,
        )
    )
    await unit_of_work.work_feed.append_for_investigation(
        tenant_id=investigation.tenant_id,
        investigation_id=investigation.investigation_id,
        kind=WorkFeedEventKind.AGENT_HANDOFF,
        payload=AgentEventPayload(
            execution_id=uuid5(_IDENTITY_NAMESPACE, f"execution:{visualization_id}"),
            agent_id="data_visualization_v1",
            role="visualization",
            from_agent_id="orchestrator_v1",
            to_agent_id="data_visualization_v1",
            summary="A governed Finding is ready for presentation.",
        ),
        occurred_at=now,
        event_id=uuid5(_IDENTITY_NAMESPACE, f"handoff:{visualization_id}"),
    )
    await unit_of_work.work_feed.append_for_investigation(
        tenant_id=investigation.tenant_id,
        investigation_id=investigation.investigation_id,
        kind=WorkFeedEventKind.VISUALIZATION_REQUESTED,
        payload=VisualizationEventPayload(
            visualization_id=visualization_id,
            investigation_id=investigation.investigation_id,
            status=VisualizationArtifactStatus.PENDING,
        ),
        occurred_at=now,
        event_id=uuid5(_IDENTITY_NAMESPACE, f"requested:{visualization_id}"),
    )
    return artifact


def _actions(
    investigation: Investigation,
    citations: tuple[EvidenceCitation, ...],
    now: datetime,
) -> tuple[tuple[BriefAction, ...], tuple[VisualizationActionMapping, ...]]:
    if investigation.thread_id is None:
        return (), ()
    values: list[VisualizationActionMapping] = []
    if citations:
        values.append(
            VisualizationActionMapping(
                action_id=uuid5(
                    _IDENTITY_NAMESPACE,
                    f"citation:{investigation.investigation_id}:{citations[0].citation_id}",
                ),
                tenant_id=investigation.tenant_id,
                visualization_id=UUID(int=0),
                thread_id=investigation.thread_id,
                investigation_id=investigation.investigation_id,
                kind=VisualizationActionKind.OPEN_CITATION,
                label="Open supporting citation",
                citation_id=citations[0].citation_id,
                expires_at=now + timedelta(days=30),
            )
        )
    values.append(
        VisualizationActionMapping(
            action_id=uuid5(
                _IDENTITY_NAMESPACE,
                f"continue:{investigation.investigation_id}:{investigation.version}",
            ),
            tenant_id=investigation.tenant_id,
            visualization_id=UUID(int=0),
            thread_id=investigation.thread_id,
            investigation_id=investigation.investigation_id,
            kind=VisualizationActionKind.CONTINUE_CONVERSATION,
            label="Continue this investigation",
            follow_up_message="Re-run this governed comparison with the latest data.",
            expires_at=now + timedelta(days=30),
            single_use=True,
        )
    )
    mappings = tuple(values)
    return (
        tuple(
            BriefAction(action_id=value.action_id, kind=value.kind, label=value.label)
            for value in mappings
        ),
        mappings,
    )


def _brief(
    investigation: Investigation,
    draft: DraftFinding | None,
    citations: tuple[EvidenceCitation, ...],
    actions: tuple[tuple[BriefAction, ...], tuple[VisualizationActionMapping, ...]],
) -> VisualizationBriefV1:
    finding = investigation.finding
    assert finding is not None
    by_metric = {value.metric: value for value in citations}
    metrics = tuple(
        BriefMetric(
            label=value.metric,
            exact_value=value.current_value,
            display_value=f"{value.current_value} {value.unit}",
            unit=value.unit,
            direction=_direction(value.previous_value, value.current_value),
            citation_ids=(by_metric[value.metric].citation_id,),
        )
        for value in finding.metrics
        if value.metric in by_metric
    )
    comparisons = tuple(
        BriefComparison(
            label=value.metric,
            previous_label=value.previous_label,
            previous_exact_value=value.previous_value,
            previous_display_value=f"{value.previous_value} {value.unit}",
            current_label=value.current_label,
            current_exact_value=value.current_value,
            current_display_value=f"{value.current_value} {value.unit}",
            unit=value.unit,
            citation_ids=(by_metric[value.metric].citation_id,),
        )
        for value in finding.metrics
        if value.metric in by_metric
    )
    labelled = next(
        (
            value
            for value in finding.metrics
            if value.previous_label and value.current_label
        ),
        None,
    )
    claims = tuple(
        BriefClaim(
            kind=value.kind.value,
            text=value.text,
            citation_ids=value.citation_ids,
        )
        for value in (draft.claims if draft else ())
        if value.citation_ids
        and all(
            citation_id in {c.citation_id for c in citations}
            for citation_id in value.citation_ids
        )
    )
    series = _series(comparisons)
    outcome = investigation.outcome
    return VisualizationBriefV1(
        investigation_id=investigation.investigation_id,
        question=investigation.question,
        headline=finding.headline,
        summary=finding.summary,
        view=_view(metrics, comparisons),
        metrics=metrics,
        comparisons=comparisons,
        series=series,
        time_range=(
            BriefTimeRange(
                start_label=labelled.previous_label,
                end_label=labelled.current_label,
            )
            if labelled is not None
            else None
        ),
        claims=claims,
        caveats=("Root cause remains unresolved.",)
        if draft is not None and draft.root_cause.value == "unresolved"
        else (),
        outcome_kind="confidence"
        if isinstance(outcome, ConfidenceOutcome)
        else "validation",
        confidence=outcome.score if isinstance(outcome, ConfidenceOutcome) else None,
        actions=actions[0],
    )


def _series(comparisons: tuple[BriefComparison, ...]) -> tuple[BriefSeries, ...]:
    """Turn each governed comparison into the two-point series it already is.

    Nothing here is measured. A comparison carries a previous and a current
    value that a single citation already validated, so the series restates that
    same evidence in the shape a renderer can draw — it does not introduce a
    figure the Evaluator never saw. That is why both points carry the
    comparison's own `citation_ids` rather than a fresh reference.
    """
    return tuple(
        BriefSeries(
            label=comparison.label,
            unit=comparison.unit,
            points=(
                BriefSeriesPoint(
                    position=0,
                    label=comparison.previous_label or "Previous",
                    exact_value=comparison.previous_exact_value,
                    display_value=comparison.previous_display_value,
                    citation_ids=comparison.citation_ids,
                ),
                BriefSeriesPoint(
                    position=1,
                    label=comparison.current_label or "Current",
                    exact_value=comparison.current_exact_value,
                    display_value=comparison.current_display_value,
                    citation_ids=comparison.citation_ids,
                ),
            ),
        )
        for comparison in comparisons[:_MAX_SERIES]
    )


def _view(
    metrics: tuple[BriefMetric, ...], comparisons: tuple[BriefComparison, ...]
) -> VisualizationView:
    """Decide the presentation here rather than leaving it to the renderer.

    `auto` hands the choice to a model, which makes the same brief render
    differently on two runs. The shape of the evidence already determines the
    answer, so it is decided deterministically and travels in the content hash.
    """
    if len(comparisons) >= 2:
        return VisualizationView.GROUPED_BAR
    if comparisons:
        return VisualizationView.BAR
    if metrics:
        return VisualizationView.METRIC_CARDS
    return VisualizationView.STRUCTURED_TEXT


def _direction(previous: str, current: str) -> str:
    try:
        before = Decimal(previous)
        after = Decimal(current)
    except InvalidOperation:
        return "not_applicable"
    if after > before:
        return "up"
    if after < before:
        return "down"
    return "flat"
