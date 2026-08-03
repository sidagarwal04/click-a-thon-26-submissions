"""The Orchestrator Loop replaces `InvestigationGraph` as the mechanism that
drives the existing Analyst/Evaluator/Insight Agents (ADR-0026). These tests
guard the two things that would silently regress chat if this seam broke:
the same trust-loop behavior (retry up to `MAX_EVALUATION_ATTEMPTS`, then
settle) and the same `PipelineResult` shape `LangGraphInvestigationPipeline`
produced — plus the new part, that a Board and Work Items are real rows by
the time `run()` returns.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from zentra_adapter_langgraph.constants import MAX_EVALUATION_ATTEMPTS
from zentra_adapter_model_providers import ModelTier
from zentra_domain_agent_execution import (
    AgentExecutionRecord,
    AgentExecutionStart,
    AgentInput,
    AgentOutput,
    AgentRole,
    ConfidenceOutcome,
    ExecutionUsage,
)
from zentra_domain_investigation import WorkItemStatus

from zentra_api.orchestrator_loop import OrchestratorLoop

INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")

ANALYST_QUERY = {
    "measures": ["Commerce.refundAmount"],
    "dimensions": [],
    "time_dimensions": [
        {
            "dimension": "Commerce.orderedAt",
            "granularity": "month",
            "date_range": ["2026-06-01", "2026-07-31"],
        }
    ],
    "filters": [
        {"member": "Commerce.region", "operator": "equals", "values": ["EU"]}
    ],
}
ANALYST_METRIC = {
    "metric": "refund_amount",
    "previous_value": "20.00",
    "current_value": "260.00",
    "unit": "usd",
    "previous_label": "June 2026",
    "current_label": "July 2026",
}


def analyst_output() -> AgentOutput:
    return AgentOutput(
        fields={
            "query": ANALYST_QUERY,
            "reasoning": "Compare EU refunds month over month.",
            "result_summary": "EU refunds rose from $20 to $260.",
            "metrics": [ANALYST_METRIC],
            "sample_size": 40,
            "rows": [{"refundAmount": "260.00"}],
        },
        evidence_refs=(),
        outcome=ConfidenceOutcome(score=0.9, calibration_method="test"),
        usage=ExecutionUsage(model="analyst-model"),
    )


def evaluator_output(*, passed: bool) -> AgentOutput:
    return AgentOutput(
        fields={
            "query": ANALYST_QUERY,
            "recheck_passed": passed,
            "discrepancy_pct": 0.0 if passed else 0.5,
            "issues": [] if passed else ["Independent recheck disagreed."],
            "sample_size": 40,
            "rows": [],
        },
        evidence_refs=(),
        outcome=ConfidenceOutcome(
            score=0.85 if passed else 0.3, calibration_method="test"
        ),
        usage=ExecutionUsage(model="evaluator-model"),
    )


def insight_output() -> AgentOutput:
    return AgentOutput(
        fields={
            "headline": "EU refunds rose $240 in July.",
            "summary": "Governed EU refund amount rose from $20 to $260.",
            "claims": [
                {
                    "kind": "observed",
                    "text": "EU refund amount rose to $260.00.",
                    "metric": "refund_amount",
                    "value": "260.00",
                    "period": "July 2026",
                }
            ],
            "contradictions": [],
            "root_cause": "unresolved",
        },
        evidence_refs=(),
        outcome=ConfidenceOutcome(score=0.8, calibration_method="test"),
        usage=ExecutionUsage(model="insight-model"),
    )


class FakeAgent:
    def __init__(self, *, agent_id: str, outputs: list[AgentOutput]) -> None:
        self.descriptor = SimpleNamespace(agent_id=agent_id)
        self._outputs = outputs
        self.received: list[AgentInput] = []

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        self.received.append(agent_input)
        index = min(len(self.received) - 1, len(self._outputs) - 1)
        return self._outputs[index]


class FakeRecorder:
    def __init__(self) -> None:
        self.started: list[AgentExecutionStart] = []
        self.completed: list[AgentExecutionRecord] = []

    async def record_started(self, start: AgentExecutionStart) -> None:
        self.started.append(start)

    async def record(self, execution: AgentExecutionRecord) -> None:
        self.completed.append(execution)


class FakeBoardRepository:
    def __init__(self, store: dict) -> None:
        self._store = store

    async def create(self, board) -> None:
        self._store["boards"][board.board_id] = board

    async def save(self, board) -> None:
        self._store["boards"][board.board_id] = board

    async def open_gap(self, board_id, tenant_id, gap) -> None:
        self._store["gaps"][gap.gap_id] = gap

    async def resolve_gap(self, gap_id, tenant_id) -> None:
        self._store["gaps"][gap_id].resolved = True

    async def record_fact(self, board_id, tenant_id, fact) -> None:
        self._store["facts"].append(fact)

    async def open_conflict(self, board_id, tenant_id, conflict) -> None:
        self._store["conflicts"][conflict.conflict_id] = conflict

    async def settle_conflict(self, tenant_id, conflict) -> None:
        self._store["conflicts"][conflict.conflict_id] = conflict


class FakeWorkItemRepository:
    def __init__(self, store: dict) -> None:
        self._store = store

    async def add(self, item) -> None:
        self._store["items"][item.work_item_id] = item

    async def save(self, item) -> None:
        self._store["items"][item.work_item_id] = item

    async def list_for_investigation(self, investigation_id, tenant_id):
        return tuple(
            item
            for item in self._store["items"].values()
            if item.investigation_id == investigation_id
        )


class FakePolicies:
    async def confidence_threshold(self, tenant_id) -> float:
        return 0.7


class FakeUnitOfWork:
    def __init__(self, store: dict) -> None:
        self.investigation_boards = FakeBoardRepository(store)
        self.work_items = FakeWorkItemRepository(store)
        self.policies = FakePolicies()

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def commit(self) -> None:
        return None


class FakeUnitOfWorkFactory:
    def __init__(self) -> None:
        self.store: dict = {
            "boards": {},
            "gaps": {},
            "facts": [],
            "items": {},
            "conflicts": {},
        }

    def __call__(self, tenant_id, trace_id, span_id) -> FakeUnitOfWork:
        return FakeUnitOfWork(self.store)


class FakeSemanticLayers:
    async def resolve(self, *, tenant_id, data_connection_id):
        return object()


def build_loop(
    *,
    evaluator_outputs: list[AgentOutput],
    unit_of_work_factory: FakeUnitOfWorkFactory,
    recorder: FakeRecorder,
    analyst_outputs: list[AgentOutput] | None = None,
) -> tuple[OrchestratorLoop, SimpleNamespace]:
    agents = SimpleNamespace(
        cube_analyst=FakeAgent(
            agent_id="cube_analyst_v1", outputs=analyst_outputs or [analyst_output()]
        ),
        evaluator=FakeAgent(agent_id="evaluator_v1", outputs=evaluator_outputs),
        insight=FakeAgent(agent_id="insight_v1", outputs=[insight_output()]),
        # No planner: these tests are about the trust loop's control flow, and
        # a run with nothing to fan out to is the shape they assert on.
        planner=None,
    )
    loop = OrchestratorLoop(
        {ModelTier.FREE: lambda _semantic_layer: agents},
        FakeSemanticLayers(),
        unit_of_work_factory=unit_of_work_factory,
        recorder=recorder,
        new_id=_sequential_ids(),
    )
    return loop, agents


def _sequential_ids():
    counter = iter(range(1, 10_000))

    def make() -> UUID:
        return UUID(int=next(counter))

    return make


@pytest.mark.asyncio
async def test_a_converged_run_persists_work_items_and_resolves_the_gap() -> None:
    unit_of_work_factory = FakeUnitOfWorkFactory()
    recorder = FakeRecorder()
    loop, _agents = build_loop(
        evaluator_outputs=[evaluator_output(passed=True)],
        unit_of_work_factory=unit_of_work_factory,
        recorder=recorder,
    )

    result = await loop.run(
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        question="Why did EU refunds increase from June to July 2026?",
    )

    assert result.converged is True
    assert result.finding.headline == "EU refunds rose $240 in July."
    assert result.draft_finding is not None

    store = unit_of_work_factory.store
    assert len(store["boards"]) == 1
    roles = sorted(item.role for item in store["items"].values())
    assert roles == sorted(
        [AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR, AgentRole.INSIGHT]
    )
    assert all(
        item.status is WorkItemStatus.COMPLETED for item in store["items"].values()
    )
    assert all(gap.resolved for gap in store["gaps"].values())
    assert len(store["facts"]) == 1
    assert recorder.started and recorder.completed


@pytest.mark.asyncio
async def test_a_failed_recheck_retries_the_analyst_before_settling() -> None:
    unit_of_work_factory = FakeUnitOfWorkFactory()
    recorder = FakeRecorder()
    loop, agents = build_loop(
        evaluator_outputs=[
            evaluator_output(passed=False),
            evaluator_output(passed=True),
        ],
        analyst_outputs=[analyst_output(), analyst_output()],
        unit_of_work_factory=unit_of_work_factory,
        recorder=recorder,
    )

    result = await loop.run(
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        question="Why did EU refunds increase from June to July 2026?",
    )

    assert result.converged is True
    analyst_items = [
        item
        for item in unit_of_work_factory.store["items"].values()
        if item.role is AgentRole.CUBE_ANALYST
    ]
    evaluator_items = [
        item
        for item in unit_of_work_factory.store["items"].values()
        if item.role is AgentRole.EVALUATOR
    ]
    assert len(analyst_items) == 2
    assert len(evaluator_items) == 2
    assert len(agents.evaluator.received) == 2
    # The retried Analyst call was told what the recheck disagreed with.
    assert agents.evaluator.received[0].state["analyst"] is not None


@pytest.mark.asyncio
async def test_a_persistently_failing_recheck_settles_at_the_attempt_cap() -> None:
    unit_of_work_factory = FakeUnitOfWorkFactory()
    recorder = FakeRecorder()
    loop, _agents = build_loop(
        evaluator_outputs=[evaluator_output(passed=False)] * MAX_EVALUATION_ATTEMPTS,
        analyst_outputs=[analyst_output()] * MAX_EVALUATION_ATTEMPTS,
        unit_of_work_factory=unit_of_work_factory,
        recorder=recorder,
    )

    result = await loop.run(
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        question="Why did EU refunds increase from June to July 2026?",
    )

    assert result.converged is False
    evaluator_items = [
        item
        for item in unit_of_work_factory.store["items"].values()
        if item.role is AgentRole.EVALUATOR
    ]
    assert len(evaluator_items) == MAX_EVALUATION_ATTEMPTS
    # Insight still drafts a Finding from the last, unconverged evidence —
    # publication policy, not the loop, decides whether it can auto-publish.
    assert result.draft_finding is not None
