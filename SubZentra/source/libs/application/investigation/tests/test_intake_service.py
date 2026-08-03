from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRole,
    SemanticCatalog,
    SemanticLayerPort,
    SemanticQuery,
    SemanticResult,
    ToolAccess,
    ToolScope,
    ValidationOutcome,
)

from zentra_application_investigation.intake_service import IntakeService
from zentra_application_investigation.thread_dto import RoutingDisposition

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")

DESCRIPTOR = AgentDescriptor(
    agent_id="fake_intake",
    role=AgentRole.INTAKE,
    tool_permissions=(
        ToolScope(tool_name="semantic_layer_query", access=ToolAccess.READ),
    ),
    context_budget_tokens=100,
    input_schema={"type": "object", "properties": {"question": {"type": "string"}}},
    output_schema={"type": "object", "properties": {}},
    output_fields=frozenset(
        {"disposition", "normalized_question", "clarification", "reasoning"}
    ),
    eval_suite_ref="evals/intake",
)


class FakeSemanticLayer:
    async def catalog(self) -> SemanticCatalog:
        return SemanticCatalog(measures=(), dimensions=())

    async def query(self, request: SemanticQuery) -> SemanticResult:
        raise NotImplementedError


class FakeIntakeAgent:
    def __init__(self, fields: dict[str, object]) -> None:
        self._fields = fields
        self.received: AgentInput | None = None
        self.semantic_layer: SemanticLayerPort | None = None

    @property
    def descriptor(self) -> AgentDescriptor:
        return DESCRIPTOR

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        self.received = agent_input
        resolved = self._fields.get("disposition") == "resolved"
        return AgentOutput(
            fields=self._fields,
            outcome=ValidationOutcome(passed=resolved),
        )


def _service(agent: FakeIntakeAgent) -> IntakeService:
    async def resolve_semantic_layer(
        tenant_id: UUID, data_connection_id: UUID | None
    ) -> SemanticLayerPort:
        del tenant_id, data_connection_id
        return FakeSemanticLayer()

    def agent_factory(semantic_layer: SemanticLayerPort) -> FakeIntakeAgent:
        agent.semantic_layer = semantic_layer
        return agent

    return IntakeService(
        agent_factory=agent_factory,
        resolve_semantic_layer=resolve_semantic_layer,
        new_id=uuid4,
    )


@pytest.mark.asyncio
async def test_resolved_disposition_derives_a_bounded_scenario_key() -> None:
    agent = FakeIntakeAgent(
        {
            "disposition": "resolved",
            "normalized_question": "Why did EU refunds rise in July 2026?",
            "clarification": None,
            "reasoning": "Matches the refunds catalog.",
        }
    )

    result = await _service(agent).resolve("why eu refunds up", tenant_id=TENANT_ID)

    assert result.disposition is RoutingDisposition.RESOLVED
    assert result.canonical_question == "Why did EU refunds rise in July 2026?"
    assert result.scenario_key == "why_did_eu_refunds_rise_in_july_2026"
    assert agent.received is not None
    assert agent.received.tenant_id == TENANT_ID
    assert agent.received.state == {"question": "why eu refunds up"}
    assert agent.semantic_layer is not None


@pytest.mark.asyncio
async def test_resolved_without_a_normalized_question_falls_back_to_unsupported() -> (
    None
):
    agent = FakeIntakeAgent(
        {
            "disposition": "resolved",
            "normalized_question": None,
            "clarification": None,
            "reasoning": "",
        }
    )

    result = await _service(agent).resolve("garbled", tenant_id=TENANT_ID)

    assert result.disposition is RoutingDisposition.UNSUPPORTED


@pytest.mark.asyncio
async def test_ambiguous_and_unsupported_dispositions_carry_a_clarification() -> None:
    ambiguous = _service(
        FakeIntakeAgent(
            {
                "disposition": "ambiguous",
                "normalized_question": None,
                "clarification": "Do you mean EU or North America?",
                "reasoning": "",
            }
        )
    )
    unsupported = _service(
        FakeIntakeAgent(
            {
                "disposition": "unsupported",
                "normalized_question": None,
                "clarification": None,
                "reasoning": "",
            }
        )
    )

    ambiguous_result = await ambiguous.resolve(
        "channel or refunds?", tenant_id=TENANT_ID
    )
    unsupported_result = await unsupported.resolve(
        "what's the weather", tenant_id=TENANT_ID
    )

    assert ambiguous_result.disposition is RoutingDisposition.AMBIGUOUS
    assert ambiguous_result.clarification == "Do you mean EU or North America?"
    assert unsupported_result.disposition is RoutingDisposition.UNSUPPORTED
    assert unsupported_result.clarification is not None
