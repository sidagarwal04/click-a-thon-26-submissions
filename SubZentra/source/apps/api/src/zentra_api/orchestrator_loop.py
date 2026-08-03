"""The Investigation Engine's loop: a Board, a Work Item queue, and Agents.

Split out of `pipeline.py`, which crossed the repository's 600-line limit once
Phase 3 gave the loop a planner and parallel children. `pipeline.py` keeps what
surrounds a run — the execution recorder, the audit events, and the assembly
that turns an outcome into a `Finding` and its Citations; this module is the
run itself.

See ADR-0026. The loop is a deterministic service, not an Agent: it may ask a
model for planning *proposals*, but which proposals become Work Items, and when
the investigation is finished, are decided by rule here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from typing import Any
from uuid import UUID, uuid4

from zentra_adapter_cube import CubeSemanticLayer
from zentra_adapter_langgraph import (
    CubeAnalystAgent,
    EvaluatorAgent,
    InsightAgent,
    OrchestratorAgent,
    SkillRegistry,
)
from zentra_adapter_langgraph.constants import MAX_EVALUATION_ATTEMPTS
from zentra_adapter_model_providers import (
    ModelTier,
    ProviderCircuitBreaker,
    ProviderClients,
    RoutedModelClient,
)
from zentra_adapter_postgres import PostgresInvestigationUnitOfWorkFactory
from zentra_application_investigation import PipelineResult, bounded_outcome
from zentra_domain_agent_execution import (
    OUTCOME_ADAPTER,
    AgentExecutionRecord,
    AgentExecutionRecorder,
    AgentExecutionStart,
    AgentInput,
    AgentOutput,
    AgentPort,
    AgentRegistryPort,
    AgentRole,
    ConfidenceOutcome,
    ExecutionStatus,
    ExecutionUsage,
    OutcomeSignal,
)
from zentra_domain_investigation import (
    BoardConfidence,
    Conflict,
    ConflictStatus,
    EvidenceReference,
    Fact,
    GapPriority,
    InvestigationBoard,
    KnowledgeGap,
    WorkItem,
    assess_completion,
)

from .cube_scope import ScopedCubeSemanticLayers
from .outcomes import InsightOutcome, PipelineOutcome, ValidatedEvidence
from .pipeline import SYSTEM_SPAN_ID, SYSTEM_TRACE_ID, _pipeline_result


async def _no_cancellation(_: UUID, __: UUID) -> None:
    """The default for tests and eval harnesses, which have no job to cancel."""
    return None


# Mirrors `InvestigationGraph`'s `_EXCLUDED_FROM_STATE` (graph.py): result rows
# stay in `agent_executions.output`, reachable only through the artifact://
# pointer, never carried in the state a later Agent or the Board sees.
_EXCLUDED_FROM_STATE = frozenset({"rows"})


def _for_state(output: AgentOutput) -> dict[str, Any]:
    """The subset of an Agent's output the next step (or the Board) may see.

    Identical in shape to `InvestigationGraph._for_state` on purpose: Insight
    and the Evaluator are unmodified and still expect exactly this shape,
    whichever mechanism produced it.
    """
    return {
        "fields": {
            key: value
            for key, value in output.fields.items()
            if key not in _EXCLUDED_FROM_STATE
        },
        "metrics": output.fields.get("metrics", []),
        "result_summary": output.fields.get("result_summary", ""),
        "issues": output.fields.get("issues", []),
        "recheck_passed": output.fields.get("recheck_passed"),
        "discrepancy_pct": output.fields.get("discrepancy_pct"),
        "outcome": output.outcome.model_dump(mode="json"),
        "evidence_refs": list(output.evidence_refs),
        "model": output.usage.model,
        "fallbacks": list(output.fallbacks),
        "sample_size": output.fields.get("sample_size"),
    }


def _outcome_signal(payload: dict[str, Any]) -> OutcomeSignal:
    return OUTCOME_ADAPTER.validate_python(payload)


def _insight_outcome_from_state(state: dict[str, Any]) -> InsightOutcome:
    fields = state["fields"]
    return InsightOutcome(
        execution_id=UUID(state["execution_id"]),
        headline=str(fields["headline"]),
        summary=str(fields["summary"]),
        claims=list(fields.get("claims", [])),
        contradictions=tuple(fields.get("contradictions", [])),
        root_cause=str(fields["root_cause"]),
        outcome=_outcome_signal(state["outcome"]),
        model=state.get("model"),
        fallbacks=tuple(state.get("fallbacks", [])),
    )


def _validated_evidence_from_state(
    analyst_state: dict[str, Any],
) -> tuple[ValidatedEvidence, ...]:
    """Mirrors `InvestigationGraph._validated_evidence` (graph.py)."""
    execution_id = analyst_state.get("execution_id")
    if not execution_id:
        return ()
    query = _mapping(_mapping(analyst_state.get("fields")).get("query"))
    time_dimensions = [_mapping(item) for item in query.get("time_dimensions", [])]
    grain = next(
        (
            str(item["granularity"])
            for item in time_dimensions
            if item.get("granularity")
        ),
        None,
    )
    filters = tuple(_mapping(item) for item in query.get("filters", []))
    return tuple(
        ValidatedEvidence(
            metric=str(metric.get("metric")),
            previous_value=str(metric.get("previous_value")),
            current_value=str(metric.get("current_value")),
            previous_period=metric.get("previous_label"),
            current_period=metric.get("current_label"),
            filters=filters,
            grain=grain,
            producing_execution_id=UUID(str(execution_id)),
        )
        for metric in (_mapping(m) for m in analyst_state.get("metrics", []))
        if metric.get("metric")
    )


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class UnsettledConflictError(RuntimeError):
    """Insight was reached with a contradiction nobody accounted for."""


def _accept(
    proposals: Sequence[dict[str, Any]], *, question: str, limit: int
) -> tuple[str, ...]:
    """Which proposed follow-ups become Work Items.

    Rule-based on purpose (ADR-0026): the planner may propose anything, and
    what it proposes is model output. Three rules decide.

    A proposal is accepted only if the loop can actually execute its role —
    the Analyst is the only role with a runtime that measures, so a proposal
    naming a role nobody implements is a plan for work that would sit pending
    forever. It must carry an objective, and that objective must be new: a
    follow-up restating the question would spend a second measurement
    re-deriving the answer the primary Analyst already has. The cap is last,
    so it truncates a list that is already legitimate rather than admitting
    junk that happened to arrive early.
    """
    seen = {question.strip().casefold()}
    accepted: list[str] = []
    for proposal in proposals:
        if proposal.get("role") != AgentRole.CUBE_ANALYST.value:
            continue
        objective = str(proposal.get("objective", "")).strip()
        if not objective or objective.casefold() in seen:
            continue
        seen.add(objective.casefold())
        accepted.append(objective)
        if len(accepted) == limit:
            break
    return tuple(accepted)


def _documented(board: InvestigationBoard) -> tuple[str, ...]:
    """The contradictions the Board found that Insight never saw.

    Insight drafts from the primary measurement alone, so a follow-up that
    disagreed with it is invisible in the draft. Carrying these onto the
    outcome is what stops fan-out from quietly discovering a problem and
    filing it where nobody reads.
    """
    return tuple(
        conflict.description
        for conflict in board.conflicts
        if conflict.status is not ConflictStatus.OPEN
    )


def _require_settled_conflicts(board: InvestigationBoard) -> None:
    """Fail closed rather than draft over an open contradiction.

    `_document_conflicts` settles every Conflict immediately before this runs,
    so today this cannot fire. It exists for the path that does not yet exist:
    a Phase 4 loop that defers a Conflict to a human, or a future merge that
    opens one later, must not reach Insight without deciding what to do about
    it. A Draft Finding written over a live contradiction is exactly the kind
    of confident wrong answer this product exists to not produce.
    """
    open_conflicts = board.unresolved_conflicts
    if open_conflicts:
        raise UnsettledConflictError(
            f"{len(open_conflicts)} contradiction(s) on the Board were neither "
            f"resolved nor documented before Insight"
        )


#: How many follow-up measurements one Investigation may fan out to, and how
#: many run at once — the same number, because accepting more than can run
#: concurrently would only queue them behind each other.
#:
#: A constructor parameter with this default rather than a per-Tenant column:
#: there is no budget field on `tenants` to extend, and inventing one before
#: anybody has asked what a Tenant's analytical budget *is* would be guessing
#: at a schema. This is the seam that change lands on.
MAX_FANOUT_WORK_ITEMS = 3


@dataclass(slots=True)
class StepAgents:
    """The Agents one run drives.

    `planner` is optional. It proposes follow-up questions and enforces the
    registry's capability match; a harness that wires none simply runs the
    primary question with no fan-out, which is what the eval replay harness
    and every test that predates Phase 3 want.
    """

    cube_analyst: CubeAnalystAgent
    evaluator: EvaluatorAgent
    insight: InsightAgent
    planner: OrchestratorAgent | None = None


AgentsFactory = Callable[[CubeSemanticLayer], "StepAgents"]


@dataclass(frozen=True, slots=True)
class _Measurement:
    """One question measured by the Analyst and rechecked by the Evaluator.

    The unit Phase 3 fans out: the primary question and every follow-up go
    through exactly this, so a child measurement carries the same trust
    guarantee as the answer to the question the user actually asked.
    """

    objective: str
    analyst_state: dict[str, Any]
    evaluator_state: dict[str, Any]
    analyst_item_id: UUID
    attempts: int

    @property
    def converged(self) -> bool:
        return bool(self.evaluator_state.get("recheck_passed"))

    @property
    def evidence(self) -> tuple[ValidatedEvidence, ...]:
        return _validated_evidence_from_state(self.analyst_state)


def build_agents_factory(
    *,
    tier: ModelTier,
    models: ProviderClients,
    breaker: ProviderCircuitBreaker,
    registry: AgentRegistryPort | None = None,
) -> AgentsFactory:
    """A per-tier factory, parameterized by the semantic layer.

    The semantic layer is a runtime argument rather than closed over here
    because it must be scoped per (Tenant, Data Connection), not per tier —
    see `ScopedCubeSemanticLayers`.

    A `registry` produces a planner. Insight is required in its required
    roles, not optional: nothing else writes a Finding, so a deployment whose
    registry has not promoted one must refuse at plan time rather than reach
    the last Work Item with nothing to run.
    """
    model = RoutedModelClient(tier=tier, clients=models.as_dict(), breaker=breaker)
    # Read from disk once per tier rather than per Agent Execution. Skills are
    # stable per role, and they are appended to the cached system prefix — a
    # registry rebuilt per investigation would still be correct but would do
    # the file I/O on the request path for no reason.
    skills = SkillRegistry.from_directory()

    def build(semantic_layer: CubeSemanticLayer) -> StepAgents:
        return StepAgents(
            cube_analyst=CubeAnalystAgent(
                model=model, semantic_layer=semantic_layer, skills=skills
            ),
            evaluator=EvaluatorAgent(
                model=model, semantic_layer=semantic_layer, skills=skills
            ),
            insight=InsightAgent(model=model),
            planner=(
                None
                if registry is None
                else OrchestratorAgent(
                    model=model,
                    registry=registry,
                    required_roles=(
                        AgentRole.CUBE_ANALYST,
                        AgentRole.EVALUATOR,
                        AgentRole.INSIGHT,
                    ),
                )
            ),
        )

    return build


class OrchestratorLoop:
    """Drives the existing specialist Agents through a durable Investigation
    Board and Work Item queue instead of a compiled LangGraph (ADR-0026).

    Phase 3 shape: the primary question is measured and rechecked exactly as
    before, then the planner proposes follow-ups against the Board's open
    gaps, the loop accepts them *by rule*, and the accepted ones run
    concurrently as child Work Items. Their Facts land on the same Board,
    where a measurement disagreeing with one already recorded opens a
    Conflict that must be resolved or documented before Insight may draft.

    What did not change: the ≤`MAX_EVALUATION_ATTEMPTS` Evaluator-Optimizer
    loop, the Agents themselves, and publication authority — which stays
    deterministic Investigation policy (ADR-0011), never this loop.
    """

    def __init__(
        self,
        agent_factories: Mapping[ModelTier, AgentsFactory],
        semantic_layers: ScopedCubeSemanticLayers,
        *,
        unit_of_work_factory: PostgresInvestigationUnitOfWorkFactory,
        recorder: AgentExecutionRecorder,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        new_id: Callable[[], UUID] = uuid4,
        cancellation_checkpoint: Callable[[UUID, UUID], Awaitable[None]] = (
            _no_cancellation
        ),
        max_fanout: int = MAX_FANOUT_WORK_ITEMS,
    ) -> None:
        self._agent_factories = dict(agent_factories)
        self._semantic_layers = semantic_layers
        self._unit_of_work_factory = unit_of_work_factory
        self._recorder = recorder
        self._now = now
        self._new_id = new_id
        self._cancellation_checkpoint = cancellation_checkpoint
        self._max_fanout = max_fanout

    async def run(
        self,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        model_tier: str = ModelTier.FREE.value,
        data_connection_id: UUID | None = None,
    ) -> PipelineResult:
        semantic_layer = await self._semantic_layers.resolve(
            tenant_id=tenant_id, data_connection_id=data_connection_id
        )
        agents = self._agent_factories[ModelTier(model_tier)](semantic_layer)
        # Held in memory for the length of the run and written through on every
        # change. The rows are what a later run (or an operator) reads; this
        # object is what the loop reasons over, so a decision can never be made
        # from state that failed to persist.
        board = InvestigationBoard.create(
            board_id=self._new_id(),
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            now=self._now(),
        )
        seed_gap = KnowledgeGap(
            gap_id=self._new_id(), description=question, priority=GapPriority.HIGH
        )
        await self._open_board(board, seed_gap)

        # Shared by every concurrent branch, so the ledger orders the whole
        # investigation rather than each branch privately. `next` on a counter
        # does not await, so no two Work Items can take the same step.
        steps = count(1)

        # Planning first, before a single measurement is paid for. The planner
        # refuses outright when the registry has not promoted a required role,
        # and a deployment that would refuse must do so before it spends, not
        # after the Analyst and its recheck have already run.
        followups = await self._plan(
            agents.planner,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            question=question,
            steps=steps,
        )

        primary = await self._measure(
            agents,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            question=question,
            objective=f"Measure what the question asks: {question}",
            steps=steps,
        )
        await self._merge(board, primary)

        children = await self._fan_out(
            agents,
            board=board,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            followups=followups,
            parent=primary,
            steps=steps,
        )
        for child in children:
            await self._merge(board, child)

        # Every Conflict the merges opened is settled here — the loop cannot
        # resolve one without evidence it does not have, so it documents them.
        # `_require_settled_conflicts` then fails closed if any path ever
        # reaches Insight with one still open.
        await self._document_conflicts(board)
        _require_settled_conflicts(board)

        insight_state, insight_execution_id, _ = await self._run_step(
            agent=agents.insight,
            role=AgentRole.INSIGHT,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            objective="Draft a Finding from the validated evidence",
            payload={
                "question": question,
                "analyst": primary.analyst_state,
                "evaluator": primary.evaluator_state,
            },
            depends_on=(primary.analyst_item_id,),
            steps=steps,
        )
        insight = _insight_outcome_from_state(
            {**insight_state, "execution_id": str(insight_execution_id)}
        )

        # The question is answered because Insight drafted from a rechecked
        # measurement; a follow-up is answered only if its own branch survived.
        await self._close_board(
            board, [question, *(child.objective for child in children)]
        )

        evidence_refs: list[str] = []
        for measurement in (primary, *children):
            for source in (measurement.analyst_state, measurement.evaluator_state):
                evidence_refs.extend(source.get("evidence_refs", []))

        result = _pipeline_result(
            PipelineOutcome(
                # From the Agent that was evaluated for writing them.
                headline=insight.headline,
                summary=insight.summary,
                metrics=list(primary.analyst_state.get("metrics", [])),
                # Deduplicated, ordered: a fan-out that reached the same
                # execution as the primary must not cite it twice.
                evidence_refs=tuple(dict.fromkeys(evidence_refs)),
                # The Evaluator's recheck is the authoritative confidence: it is
                # already capped at the analyst's own score.
                outcome=_outcome_signal(primary.evaluator_state["outcome"]),
                converged=primary.converged,
                # What Insight found, plus what the Board found by cross-checking
                # itself. A follow-up that disagrees with the primary answer is a
                # contradiction the reader is owed, and Insight never saw it.
                contradictions=insight.contradictions + _documented(board),
                attempts=primary.attempts,
                insight=insight,
                analyst_model=primary.analyst_state.get("model"),
                evaluator_model=primary.evaluator_state.get("model"),
                analyst_sample_size=primary.analyst_state.get("sample_size"),
                evaluator_sample_size=primary.evaluator_state.get("sample_size"),
                evidence=primary.evidence,
            ),
            investigation_id=investigation_id,
            tenant_id=tenant_id,
        )

        await self._finish_board(
            board,
            result,
            evidence_validated=primary.converged,
            budget_exhausted=(
                primary.attempts >= MAX_EVALUATION_ATTEMPTS
                or len(children) >= self._max_fanout
            ),
        )
        return result

    async def _finish_board(
        self,
        board: InvestigationBoard,
        result: PipelineResult,
        *,
        evidence_validated: bool,
        budget_exhausted: bool,
    ) -> None:
        """Record what the Board concluded about itself, and why it stopped.

        The score is `bounded_outcome`'s — the same number the application will
        publish — rather than the Evaluator's raw one. The Evaluator's is
        capped at the Analyst's but not by sample size or by how independent
        the recheck actually was, so recording it here would leave the Board
        more confident than the Finding built from it. A second, higher number
        is exactly what ADR-0010 exists to prevent.

        This is not a publication decision. `evaluate_publication` owns that
        (ADR-0011) and is untouched; this says whether the Investigation is
        finished, which is a different question with a different answer.
        """
        outcome = bounded_outcome(result)
        threshold = await self._confidence_threshold(board.tenant_id)
        board.set_confidence(
            BoardConfidence(
                score=(
                    outcome.score if isinstance(outcome, ConfidenceOutcome) else None
                ),
                threshold=threshold,
            ),
            now=self._now(),
        )
        assessment = assess_completion(
            board,
            evidence_validated=evidence_validated,
            budget_exhausted=budget_exhausted,
        )
        board.set_narrative(assessment.describe(), now=self._now())
        async with self._unit_of_work_factory(
            board.tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            await unit_of_work.investigation_boards.save(board)
            await unit_of_work.commit()

    async def _confidence_threshold(self, tenant_id: UUID) -> float:
        async with self._unit_of_work_factory(
            tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            return await unit_of_work.policies.confidence_threshold(tenant_id)

    # -- the unit that fans out -------------------------------------------

    async def _measure(
        self,
        agents: StepAgents,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        objective: str,
        steps: Iterator[int],
        parent_work_item_id: UUID | None = None,
        depends_on: tuple[UUID, ...] = (),
    ) -> _Measurement:
        """Measure one question and recheck it independently.

        The Evaluator-Optimizer loop, unchanged and now reusable: a follow-up
        question earns the same recheck the primary one does, because evidence
        nobody rechecked is not evidence this product is willing to cite.
        """
        analyst_state, analyst_item_id = await self._run_analyst(
            agents.cube_analyst,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            question=question,
            objective=objective,
            steps=steps,
            parent_work_item_id=parent_work_item_id,
            depends_on=depends_on,
            previous_issues=None,
        )

        attempts = 0
        while True:
            evaluator_state, _, _ = await self._run_step(
                agent=agents.evaluator,
                role=AgentRole.EVALUATOR,
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                objective="Independently verify the Analyst's measurement",
                payload={"question": question, "analyst": analyst_state},
                depends_on=(analyst_item_id,),
                steps=steps,
                parent_work_item_id=analyst_item_id,
            )
            attempts += 1
            if (
                bool(evaluator_state.get("recheck_passed"))
                or attempts >= MAX_EVALUATION_ATTEMPTS
            ):
                break
            analyst_state, analyst_item_id = await self._run_analyst(
                agents.cube_analyst,
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                question=question,
                objective="Re-measure after the Evaluator's recheck disagreed",
                steps=steps,
                parent_work_item_id=parent_work_item_id,
                depends_on=depends_on,
                previous_issues=evaluator_state.get("issues", []),
            )

        return _Measurement(
            objective=objective,
            analyst_state=analyst_state,
            evaluator_state=evaluator_state,
            analyst_item_id=analyst_item_id,
            attempts=attempts,
        )

    async def _plan(
        self,
        planner: OrchestratorAgent | None,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        steps: Iterator[int],
    ) -> tuple[str, ...]:
        """Ask what else is worth measuring, then decide by rule.

        The planner's output is a proposal, never an instruction — see
        ADR-0026. Its own job is the registry's capability match: it raises
        `NoEnabledAgentError` when a required role has no promoted agent, and
        that refusal propagates from here, before anything has been measured.
        What this method adds is `_accept`, the rules deciding which proposals
        become Work Items.
        """
        if planner is None or self._max_fanout < 1:
            return ()

        state, _, _ = await self._run_step(
            agent=planner,
            role=AgentRole.ORCHESTRATOR,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            objective="Propose the follow-up measurements this question needs",
            payload={"question": question},
            depends_on=(),
            steps=steps,
        )
        proposals = tuple(
            task
            for task in state.get("fields", {}).get("tasks", [])
            if isinstance(task, dict)
        )
        return _accept(proposals, question=question, limit=self._max_fanout)

    async def _fan_out(
        self,
        agents: StepAgents,
        *,
        board: InvestigationBoard,
        investigation_id: UUID,
        tenant_id: UUID,
        followups: Sequence[str],
        parent: _Measurement,
        steps: Iterator[int],
    ) -> tuple[_Measurement, ...]:
        """Run the accepted follow-ups concurrently, as children of the answer.

        They run after the primary measurement, not beside it: each one exists
        to interrogate a result that does not exist until the primary Analyst
        has produced it.
        """
        accepted = tuple(followups)
        if not accepted:
            return ()

        gaps = [
            KnowledgeGap(
                gap_id=self._new_id(),
                description=objective,
                # Never HIGH: a follow-up is worth asking, but an investigation
                # that cannot answer one has still answered the question the
                # user asked. Only the seed gap is allowed to be HIGH.
                priority=GapPriority.MEDIUM,
            )
            for objective in accepted
        ]
        await self._open_gaps(board, gaps)

        # `return_exceptions`: a follow-up that fails must not sink the answer
        # the user actually asked for. Its Work Item is already REJECTED and
        # its Agent Execution recorded, so the failure stays visible in Replay
        # rather than being swallowed here.
        results = await asyncio.gather(
            *(
                self._measure(
                    agents,
                    investigation_id=investigation_id,
                    tenant_id=tenant_id,
                    question=objective,
                    objective=objective,
                    steps=steps,
                    parent_work_item_id=parent.analyst_item_id,
                    depends_on=(parent.analyst_item_id,),
                )
                for objective in accepted
            ),
            return_exceptions=True,
        )
        return tuple(r for r in results if isinstance(r, _Measurement))

    # -- the Board --------------------------------------------------------

    async def _merge(
        self, board: InvestigationBoard, measurement: _Measurement
    ) -> None:
        """Record what a measurement established, and notice disagreement.

        The Board is what makes fan-out worth anything: two Work Items that
        measured the same metric over the same period and disagree is a
        contradiction nobody would have seen while each result lived only in
        its own agent's state.
        """
        for measured in measurement.evidence:
            fact = Fact(
                fact_id=self._new_id(),
                metric=measured.metric,
                value=measured.current_value,
                period=measured.current_period,
                producing_work_item_id=measurement.analyst_item_id,
                evidence_refs=(
                    EvidenceReference(
                        f"artifact://execution/{measured.producing_execution_id}"
                    ),
                ),
            )
            incumbent = board.contradicted_by(fact)
            board.record_fact(fact, now=self._now())
            conflict = (
                None
                if incumbent is None
                else Conflict(
                    conflict_id=self._new_id(),
                    description=(
                        f"{fact.metric} over {fact.period or 'the whole period'} "
                        f"was measured as {incumbent.value} and as {fact.value}"
                    ),
                )
            )
            if conflict is not None:
                board.open_conflict(conflict, now=self._now())
            await self._persist_merge(board, fact, conflict)

    async def _document_conflicts(self, board: InvestigationBoard) -> None:
        """Settle every open Conflict as documented, never as resolved.

        Resolving one means establishing which measurement was right, and the
        loop has no evidence to do that with — a third query would be a third
        opinion, not an arbiter. Documenting is the honest outcome: the
        disagreement reaches the reader instead of one side being picked
        silently.
        """
        settled = list(board.unresolved_conflicts)
        if not settled:
            return
        for conflict in settled:
            board.resolve_conflict(
                conflict.conflict_id,
                resolution=(
                    "Recorded as an unreconciled disagreement between two "
                    "independent measurements; neither was discarded."
                ),
                now=self._now(),
                documented_only=True,
            )
        async with self._unit_of_work_factory(
            board.tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            for conflict in settled:
                await unit_of_work.investigation_boards.settle_conflict(
                    board.tenant_id, conflict
                )
            await unit_of_work.commit()

    async def _open_board(self, board: InvestigationBoard, gap: KnowledgeGap) -> None:
        board.open_gap(gap, now=self._now())
        async with self._unit_of_work_factory(
            board.tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            await unit_of_work.investigation_boards.create(board)
            await unit_of_work.investigation_boards.open_gap(
                board.board_id, board.tenant_id, gap
            )
            await unit_of_work.commit()

    async def _open_gaps(
        self, board: InvestigationBoard, gaps: Sequence[KnowledgeGap]
    ) -> None:
        async with self._unit_of_work_factory(
            board.tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            for gap in gaps:
                board.open_gap(gap, now=self._now())
                await unit_of_work.investigation_boards.open_gap(
                    board.board_id, board.tenant_id, gap
                )
            await unit_of_work.commit()

    async def _persist_merge(
        self, board: InvestigationBoard, fact: Fact, conflict: Conflict | None
    ) -> None:
        """One transaction, because they are one event.

        A Fact committed without the Conflict it provoked would leave the
        Board claiming two values for the same measurement with nothing
        recording that anybody noticed.
        """
        async with self._unit_of_work_factory(
            board.tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            await unit_of_work.investigation_boards.record_fact(
                board.board_id, board.tenant_id, fact
            )
            if conflict is not None:
                await unit_of_work.investigation_boards.open_conflict(
                    board.board_id, board.tenant_id, conflict
                )
            await unit_of_work.commit()

    async def _close_board(
        self, board: InvestigationBoard, answered: Sequence[str]
    ) -> None:
        """Resolve the gaps this run actually closed, and only those.

        A follow-up whose measurement failed leaves its Knowledge Gap open —
        that is the honest record, and it is what a later run (or an operator)
        needs in order to know there is something still unanswered here.
        Marking every gap resolved because the run finished would make the
        Board agree with itself by construction.
        """
        closing = {description.strip().casefold() for description in answered}
        settled = [
            gap
            for gap in board.open_gaps
            if gap.description.strip().casefold() in closing
        ]
        if not settled:
            return
        async with self._unit_of_work_factory(
            board.tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            for gap in settled:
                board.resolve_gap(gap.gap_id, now=self._now())
                await unit_of_work.investigation_boards.resolve_gap(
                    gap.gap_id, board.tenant_id
                )
            await unit_of_work.commit()

    async def _run_analyst(
        self,
        agent: CubeAnalystAgent,
        *,
        investigation_id: UUID,
        tenant_id: UUID,
        question: str,
        objective: str,
        steps: Iterator[int],
        previous_issues: list[Any] | None,
        parent_work_item_id: UUID | None = None,
        depends_on: tuple[UUID, ...] = (),
    ) -> tuple[dict[str, Any], UUID]:
        payload: dict[str, Any] = {"question": question}
        if previous_issues is not None:
            payload["previous_issues"] = previous_issues
        state, execution_id, work_item_id = await self._run_step(
            agent=agent,
            role=AgentRole.CUBE_ANALYST,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            objective=objective,
            payload=payload,
            depends_on=depends_on,
            steps=steps,
            parent_work_item_id=parent_work_item_id,
        )
        return {**state, "execution_id": str(execution_id)}, work_item_id

    async def _run_step(
        self,
        *,
        agent: AgentPort,
        role: AgentRole,
        investigation_id: UUID,
        tenant_id: UUID,
        objective: str,
        payload: dict[str, Any],
        depends_on: tuple[UUID, ...],
        steps: Iterator[int],
        parent_work_item_id: UUID | None = None,
    ) -> tuple[dict[str, Any], UUID, UUID]:
        """Runs one Agent as one Work Item, recording a started event, the
        Agent Execution, and the same Work Feed events chat already reads.
        Returns the resulting state, the execution id, and the Work Item id.

        `steps` is shared across concurrent branches so the ledger orders the
        whole investigation, and `parent_work_item_id` is what makes the queue
        a graph the Board grew rather than a DAG somebody drew in advance.
        """
        # Before the Work Item exists, not after: a run cancelled here should
        # leave no pending row behind claiming work nobody will ever do.
        await self._cancellation_checkpoint(tenant_id, investigation_id)

        now = self._now()
        item = WorkItem.create(
            work_item_id=self._new_id(),
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            role=role,
            objective=objective,
            now=now,
            parent_work_item_id=parent_work_item_id,
            depends_on=depends_on,
        )
        async with self._unit_of_work_factory(
            tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            await unit_of_work.work_items.add(item)
            await unit_of_work.commit()

        step = next(steps)
        execution_id = self._new_id()
        started_at = self._now()
        agent_state = {**payload, "execution_id": str(execution_id)}
        await self._recorder.record_started(
            AgentExecutionStart(
                execution_id=execution_id,
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                agent_id=agent.descriptor.agent_id,
                role=role,
                step=step,
                started_at=started_at,
            )
        )
        item.start(now=self._now())
        async with self._unit_of_work_factory(
            tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            await unit_of_work.work_items.save(item)
            await unit_of_work.commit()

        try:
            output = await agent.invoke(
                AgentInput(
                    investigation_id=investigation_id,
                    tenant_id=tenant_id,
                    state=agent_state,
                )
            )
        except Exception as error:
            completed_at = self._now()
            await self._recorder.record(
                _execution_record(
                    execution_id=execution_id,
                    investigation_id=investigation_id,
                    tenant_id=tenant_id,
                    agent_id=agent.descriptor.agent_id,
                    role=role,
                    step=step,
                    input_state=agent_state,
                    output=None,
                    status=ExecutionStatus.FAILURE,
                    started_at=started_at,
                    completed_at=completed_at,
                    errors=(f"{type(error).__name__}: {error}",),
                )
            )
            async with self._unit_of_work_factory(
                tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
            ) as unit_of_work:
                item.reject(now=completed_at, reason=str(error))
                await unit_of_work.work_items.save(item)
                await unit_of_work.commit()
            raise

        completed_at = self._now()
        await self._recorder.record(
            _execution_record(
                execution_id=execution_id,
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                agent_id=agent.descriptor.agent_id,
                role=role,
                step=step,
                input_state=agent_state,
                output=output,
                status=ExecutionStatus.SUCCESS,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
        item.complete(
            now=completed_at,
            artifact_refs=(EvidenceReference(f"artifact://execution/{execution_id}"),),
        )
        async with self._unit_of_work_factory(
            tenant_id, SYSTEM_TRACE_ID, SYSTEM_SPAN_ID
        ) as unit_of_work:
            await unit_of_work.work_items.save(item)
            await unit_of_work.commit()

        # And again once the step is durable, so a cancellation requested
        # mid-call stops the loop before the next Agent is paid for rather
        # than after the whole three-attempt trust loop has run.
        await self._cancellation_checkpoint(tenant_id, investigation_id)
        return _for_state(output), execution_id, item.work_item_id


def _execution_record(
    *,
    execution_id: UUID,
    investigation_id: UUID,
    tenant_id: UUID,
    agent_id: str,
    role: AgentRole,
    step: int,
    input_state: dict[str, Any],
    output: AgentOutput | None,
    status: ExecutionStatus,
    started_at: datetime,
    completed_at: datetime,
    errors: tuple[str, ...] = (),
) -> AgentExecutionRecord:
    return AgentExecutionRecord(
        execution_id=execution_id,
        investigation_id=investigation_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        role=role,
        step=step,
        input=input_state,
        output=dict(output.fields) if output else None,
        outcome=output.outcome if output else None,
        status=status,
        latency_ms=max(0, int((completed_at - started_at).total_seconds() * 1000)),
        usage=output.usage if output is not None else ExecutionUsage(),
        evidence_refs=output.evidence_refs if output else (),
        fallbacks=output.fallbacks if output else (),
        errors=errors,
        started_at=started_at,
        completed_at=completed_at,
    )
