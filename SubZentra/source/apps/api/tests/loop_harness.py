"""The Orchestrator Loop wired to the *real* Analyst, Evaluator and Insight.

`test_orchestrator_loop.py` fakes the Agents to test the loop's control flow.
This harness does the opposite: it fakes only the model and the semantic layer,
so the assertions it supports are about what the Agents actually do — the shape
they hand each other, what reaches the ledger, and what must never travel
between them.

It replaces the harness that lived in `libs/adapters/langgraph/tests/
test_graph.py`. Those tests exercised the same four Agents through
`InvestigationGraph`; ADR-0026 deleted the graph, not the Agents, so the
coverage moved here rather than out.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from zentra_adapter_langgraph import (
    CubeAnalystAgent,
    EvaluatorAgent,
    InsightAgent,
    OrchestratorAgent,
)
from zentra_adapter_langgraph.schemas import (
    ANALYSIS_SCHEMA,
    DRAFT_FINDING_SCHEMA,
    RECHECK_SCHEMA,
    TASK_LEDGER_SCHEMA,
)
from zentra_adapter_model_providers import ModelTier
from zentra_domain_agent_execution import (
    AgentExecutionRecord,
    AgentExecutionStart,
    AgentRole,
    ExecutionUsage,
    ModelMessage,
    ModelResponse,
    RegisteredAgent,
    SemanticCatalog,
    SemanticDimension,
    SemanticMeasure,
    SemanticQuery,
    SemanticResult,
    ToolCall,
)

from zentra_api.orchestrator_loop import OrchestratorLoop, StepAgents

INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")
QUESTION = "Why did EU refunds increase from June to July 2026?"

CATALOG = SemanticCatalog(
    measures=(
        SemanticMeasure(name="Commerce.refundAmount", type="sum"),
        SemanticMeasure(name="Commerce.orderCount", type="countDistinct"),
    ),
    dimensions=(
        SemanticDimension(name="Commerce.orderedAt", type="time"),
        SemanticDimension(name="Commerce.region", type="string"),
    ),
)

QUERY_PLAN = {
    "reasoning": "Compare governed EU refund amount month over month.",
    "query": {
        "measures": ["Commerce.refundAmount"],
        "dimensions": [],
        "time_dimensions": [
            {
                "dimension": "Commerce.orderedAt",
                "granularity": "month",
                "date_range": ["2026-06-01", "2026-07-31"],
            }
        ],
        "filters": [],
    },
}

METRICS = [
    {
        "metric": "refund_amount",
        "previous_value": "20.00",
        "current_value": "260.00",
        "unit": "USD",
    }
]

# What the router resolves each role to, mirrored here so these tests keep
# asserting on real model identities rather than on role keys.
ROLE_MODELS = {
    "orchestrator": "gemini/gemini-3-flash",
    "cube_analyst": "cerebras/zai-glm-4.7",
    "evaluator": "groq/openai/gpt-oss-120b",
    # Deliberately distinct from every other role, so a test asserting Insight's
    # attribution cannot pass by picking up another agent's model.
    "insight": "nvidia/nemotron-3-ultra-550b-a55b",
}


class StubSemanticLayer:
    def __init__(self) -> None:
        self.queries: list[SemanticQuery] = []

    async def catalog(self) -> SemanticCatalog:
        return CATALOG

    async def query(self, request: SemanticQuery) -> SemanticResult:
        CATALOG.reject_ungoverned(request)
        self.queries.append(request)
        return SemanticResult(
            query=request,
            rows=({"Commerce.refundAmount": "260.00"},),
        )


class ScriptedModel:
    """Answers by declared schema, so the loop's control flow is what is
    under test rather than any particular model wording."""

    def __init__(
        self,
        *,
        recheck_passed: bool,
        fallbacks: tuple[str, ...] = (),
        tasks: list[dict[str, str]] | None = None,
        measured_values: tuple[str, ...] = ("260.00",),
        failing_analysis: int | None = None,
    ) -> None:
        self._recheck_passed = recheck_passed
        self._fallbacks = fallbacks
        self._tasks = tasks or []
        # One per Analyst interpretation call, in order, the last repeating.
        # A fan-out whose child measures a *different* value for the same
        # metric and period is how a Conflict gets exercised end to end.
        self._measured_values = measured_values
        # Which Analyst interpretation call raises, 0-based. The provider
        # falling over inside one branch is the failure a fan-out must survive.
        self._failing_analysis = failing_analysis
        self._analyses = 0
        self.calls = 0

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[ModelMessage],
        max_tokens: int,
        response_schema: dict[str, Any] | None = None,
        tools: Sequence[Any] = (),
    ) -> ModelResponse:
        self.calls += 1

        # The Cube Analyst and Evaluator reach data through a tool now, not a
        # structured planning call. One round: call `semantic_query`, then
        # answer. Detected from the conversation rather than a counter, since
        # the Evaluator loop invokes the Analyst afresh on every attempt, each
        # with its own tool instance — a retry has to query again exactly as a
        # real model would.
        if tools and not any(message.tool_results for message in messages):
            return ModelResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        call_id=f"call_{self.calls}",
                        name="semantic_query",
                        arguments=QUERY_PLAN["query"],
                    ),
                ),
                stop_reason="tool_use",
                usage=ExecutionUsage(
                    input_tokens=50,
                    output_tokens=10,
                    cost_usd=Decimal("0.0005"),
                    model=ROLE_MODELS[model],
                ),
                fallbacks=self._fallbacks,
            )

        # A tool-loop turn carries no schema: the Agent has finished calling
        # tools and its prose is the answer, which the runtime then asks it to
        # restate as the declared object on a closing schema-bearing call.
        if response_schema is None:
            return ModelResponse(
                text="The governed result is ready to report.",
                stop_reason="stop",
                usage=ExecutionUsage(
                    input_tokens=50,
                    output_tokens=10,
                    cost_usd=Decimal("0.0005"),
                    model=ROLE_MODELS[model],
                ),
                fallbacks=self._fallbacks,
            )

        payload = self._payload(response_schema)
        return ModelResponse(
            text=json.dumps(payload),
            usage=ExecutionUsage(
                input_tokens=100,
                output_tokens=20,
                cost_usd=Decimal("0.001"),
                model=ROLE_MODELS[model],
            ),
            fallbacks=self._fallbacks,
        )

    def _payload(self, schema: dict[str, Any] | None) -> dict[str, Any]:
        if schema == TASK_LEDGER_SCHEMA:
            return {"tasks": self._tasks}
        if schema == ANALYSIS_SCHEMA:
            index = min(self._analyses, len(self._measured_values) - 1)
            failed = self._analyses == self._failing_analysis
            self._analyses += 1
            if failed:
                raise TimeoutError("simulated provider interruption")
            return {
                "result_summary": "EU refunds rose from $20 to $260.",
                "metrics": [
                    {**METRICS[0], "current_value": self._measured_values[index]}
                ],
                "confidence": 0.88,
                # Underlying records, not returned rows: two monthly totals
                # over 240 orders.
                "sample_size": 240,
            }
        if schema == RECHECK_SCHEMA:
            return {
                "recheck_passed": self._recheck_passed,
                "discrepancy_pct": 0.0 if self._recheck_passed else 0.42,
                "confidence": 0.86 if self._recheck_passed else 0.2,
                "sample_size": 240,
                "issues": [] if self._recheck_passed else ["Figures disagree."],
            }
        if schema == DRAFT_FINDING_SCHEMA:
            return {
                "headline": "EU refunds rose $240 in July.",
                "summary": "Governed EU refund amount rose from $20 to $260.",
                "claims": [
                    {
                        "kind": "observed",
                        "text": "EU refund amount rose to $260.00.",
                        "metric": "refund_amount",
                        "value": "260.00",
                    }
                ],
                "contradictions": [],
                "root_cause_resolved": False,
                "confidence": 0.9,
            }
        raise AssertionError(f"Unscripted schema: {schema}")


def keys(value: Any) -> set[str]:
    """Every key at every depth."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(str(key))
            found |= keys(child)
    elif isinstance(value, list):
        for child in value:
            found |= keys(child)
    return found


class RecordingRecorder:
    def __init__(self) -> None:
        self.records: list[AgentExecutionRecord] = []
        self.starts: list[AgentExecutionStart] = []

    async def record_started(self, start: AgentExecutionStart) -> None:
        self.starts.append(start)

    async def record(self, execution: AgentExecutionRecord) -> None:
        self.records.append(execution)


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
    def __init__(self, layer: StubSemanticLayer) -> None:
        self._layer = layer

    async def resolve(self, *, tenant_id, data_connection_id):
        return self._layer


class StubRegistry:
    def __init__(self, roles: Sequence[AgentRole]) -> None:
        self._roles = roles

    async def enabled_agents(self) -> tuple[RegisteredAgent, ...]:
        return tuple(
            RegisteredAgent(agent_id=f"{role.value}_v1", role=role, version="1")
            for role in self._roles
        )


PROMOTED = (AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR, AgentRole.INSIGHT)


def build_loop(
    *,
    recheck_passed: bool,
    fallbacks: tuple[str, ...] = (),
    insight: object | None = None,
    cancellation_checkpoint: Callable[[UUID, UUID], Awaitable[None]] | None = None,
    tasks: list[dict[str, str]] | None = None,
    promoted: Sequence[AgentRole] = PROMOTED,
    measured_values: tuple[str, ...] = ("260.00",),
    failing_analysis: int | None = None,
    max_fanout: int | None = None,
) -> tuple[OrchestratorLoop, RecordingRecorder, StubSemanticLayer]:
    """A loop over the real Agents.

    Passing `tasks` wires a planner that proposes them, which is what turns
    fan-out on; leaving it `None` is a Phase 1/2-shaped run with no children.
    """
    model = ScriptedModel(
        recheck_passed=recheck_passed,
        fallbacks=fallbacks,
        tasks=tasks,
        measured_values=measured_values,
        failing_analysis=failing_analysis,
    )
    layer = StubSemanticLayer()
    recorder = RecordingRecorder()
    unit_of_work_factory = FakeUnitOfWorkFactory()
    clock = iter(
        datetime(2026, 7, 29, 8, 0, tzinfo=UTC) + timedelta(seconds=n)
        for n in range(1000)
    )

    def build(_semantic_layer: object) -> StepAgents:
        return StepAgents(
            cube_analyst=CubeAnalystAgent(model=model, semantic_layer=layer),
            evaluator=EvaluatorAgent(model=model, semantic_layer=layer),
            insight=insight if insight is not None else InsightAgent(model=model),
            planner=(
                None
                if tasks is None
                else OrchestratorAgent(
                    model=model,
                    registry=StubRegistry(promoted),
                    required_roles=PROMOTED,
                )
            ),
        )

    loop = OrchestratorLoop(
        {ModelTier.FREE: build},
        FakeSemanticLayers(layer),
        unit_of_work_factory=unit_of_work_factory,
        recorder=recorder,
        now=lambda: next(clock),
        **(
            {"cancellation_checkpoint": cancellation_checkpoint}
            if cancellation_checkpoint is not None
            else {}
        ),
        **({"max_fanout": max_fanout} if max_fanout is not None else {}),
    )
    return loop, recorder, layer


def board_store(loop: OrchestratorLoop) -> dict:
    """What the run actually persisted: boards, gaps, facts and Work Items.

    Reaches through the loop for the fake factory it was built with, so the
    one private access lives here rather than in every test that needs to see
    what a run wrote.
    """
    return loop._unit_of_work_factory.store  # type: ignore[attr-defined]


async def run(loop: OrchestratorLoop):
    return await loop.run(
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        question=QUESTION,
    )
