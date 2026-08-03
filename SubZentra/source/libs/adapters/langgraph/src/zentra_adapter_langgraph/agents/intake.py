from __future__ import annotations

from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRole,
    ModelMessage,
    ModelPort,
    SemanticLayerPort,
    ToolAccess,
    ToolScope,
    ValidationOutcome,
    validate_agent_output,
)

from ..constants import INTAKE_MODEL, MAX_TOKENS
from ..prompts import INTAKE_ROUTE
from ..schemas import INTAKE_SCHEMA, parse_json_object, render_catalog

AGENT_ID = "intake_v1"

DESCRIPTOR = AgentDescriptor(
    agent_id=AGENT_ID,
    role=AgentRole.INTAKE,
    # Reads the scoped catalog to ground its decision; never queries data.
    tool_permissions=(
        ToolScope(tool_name="semantic_layer_query", access=ToolAccess.READ),
    ),
    context_budget_tokens=MAX_TOKENS,
    input_schema={"type": "object", "properties": {"question": {"type": "string"}}},
    output_schema=INTAKE_SCHEMA,
    output_fields=frozenset(
        {"disposition", "normalized_question", "clarification", "reasoning"}
    ),
    eval_suite_ref="evals/intake",
)


class IntakeAgent:
    """Resolves a Thread's message against the Tenant's Analytical Scope.

    Replaces the two-scenario keyword whitelist (ADR-0027): `semantic_layer`
    is expected to already be narrowed to the Tenant's Analytical Scope, so
    Intake can only ever resolve or refuse using exactly what the Tenant
    configured, never the full governed catalog.
    """

    def __init__(self, *, model: ModelPort, semantic_layer: SemanticLayerPort) -> None:
        self._model = model
        self._semantic_layer = semantic_layer

    @property
    def descriptor(self) -> AgentDescriptor:
        return DESCRIPTOR

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        question = str(agent_input.state["question"])
        catalog = await self._semantic_layer.catalog()

        response = await self._model.complete(
            model=INTAKE_MODEL,
            system=INTAKE_ROUTE,
            messages=[
                ModelMessage(
                    role="user",
                    content=(
                        f"Message: {question}\n\n"
                        f"Governed catalog in scope:\n{render_catalog(catalog)}"
                    ),
                )
            ],
            max_tokens=MAX_TOKENS,
            response_schema=INTAKE_SCHEMA,
        )
        decision = parse_json_object(response.text)
        resolved = decision.get("disposition") == "resolved" and bool(
            decision.get("normalized_question")
        )

        return validate_agent_output(
            self,
            AgentOutput(
                fields={
                    "disposition": decision.get("disposition", "unsupported"),
                    "normalized_question": decision.get("normalized_question"),
                    "clarification": decision.get("clarification"),
                    "reasoning": decision.get("reasoning", ""),
                },
                outcome=ValidationOutcome(
                    passed=resolved,
                    checks=("The question resolves inside the Analytical Scope.",),
                    issues=() if resolved else ("The question needs clarification.",),
                ),
                usage=response.usage,
                fallbacks=response.fallbacks,
            ),
        )
