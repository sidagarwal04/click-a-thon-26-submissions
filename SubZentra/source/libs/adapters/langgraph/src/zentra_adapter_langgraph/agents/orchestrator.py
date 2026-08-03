from __future__ import annotations

from collections.abc import Sequence

from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentInput,
    AgentOutput,
    AgentRegistryPort,
    AgentRole,
    ExecutionUsage,
    ModelMessage,
    ModelPort,
    ToolAccess,
    ToolScope,
    ValidationOutcome,
    validate_agent_output,
)

from ..constants import MAX_TOKENS, ORCHESTRATOR_MODEL
from ..prompts import ORCHESTRATOR_PLAN
from ..schemas import TASK_LEDGER_SCHEMA, parse_json_object

AGENT_ID = "orchestrator_v1"

# The roles this workflow cannot run without. Resolved against the registry at
# investigation start, never against a hardcoded list of implementations.
#
# Injectable because the Phase 2 route needs Insight to be required too, and a
# route that needs an Agent must refuse when the registry has not promoted one
# rather than quietly running without it.
REQUIRED_ROLES = (AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR)

DESCRIPTOR = AgentDescriptor(
    agent_id=AGENT_ID,
    role=AgentRole.ORCHESTRATOR,
    # Task ledger only: the Orchestrator decomposes and delegates, and can
    # reach neither the semantic layer nor a sandbox.
    tool_permissions=(ToolScope(tool_name="task_ledger", access=ToolAccess.WRITE),),
    context_budget_tokens=MAX_TOKENS,
    input_schema={"type": "object", "properties": {"question": {"type": "string"}}},
    output_schema=TASK_LEDGER_SCHEMA,
    # Tasks only. Narrative belongs to the Agent that is evaluated for
    # writing it, and leaving the fields declared here would let a
    # regression put prose back without tripping the allowlist.
    output_fields=frozenset({"tasks"}),
    eval_suite_ref="evals/orchestrator",
)


class NoEnabledAgentError(RuntimeError):
    """A required role has no enabled, eval-passing agent registered."""


class OrchestratorAgent:
    """Decomposes the question, delegates, and arbitrates. Writes nothing.

    It planned and then wrote the Finding, which meant one Agent Execution
    both chose the work and drew the conclusion, with no independent
    evaluation of the second job. The Insight Agent owns the conclusion now;
    what is left here is planning, delegation, retry arbitration and terminal
    routing.
    """

    def __init__(
        self,
        *,
        model: ModelPort,
        registry: AgentRegistryPort,
        required_roles: Sequence[AgentRole] = REQUIRED_ROLES,
    ) -> None:
        self._model = model
        self._registry = registry
        self._required_roles = tuple(required_roles)

    @property
    def descriptor(self) -> AgentDescriptor:
        return DESCRIPTOR

    async def invoke(self, agent_input: AgentInput) -> AgentOutput:
        question = str(agent_input.state["question"])
        available = await self._available_roles()

        response = await self._model.complete(
            model=ORCHESTRATOR_MODEL,
            system=ORCHESTRATOR_PLAN,
            messages=[
                ModelMessage(
                    role="user",
                    content=(
                        f"Question: {question}\n\n"
                        f"Available roles: {', '.join(sorted(available))}"
                    ),
                )
            ],
            max_tokens=MAX_TOKENS,
            response_schema=TASK_LEDGER_SCHEMA,
        )
        ledger = parse_json_object(response.text)
        tasks = [
            task for task in ledger.get("tasks", []) if task.get("role") in available
        ]

        return validate_agent_output(
            self,
            AgentOutput(
                fields={"tasks": tasks},
                outcome=ValidationOutcome(
                    passed=bool(tasks),
                    checks=("Every delegated role is enabled in the registry.",),
                    issues=()
                    if tasks
                    else ("The plan delegated to no registered role.",),
                ),
                usage=_usage(response.usage),
                fallbacks=response.fallbacks,
            ),
        )

    async def _available_roles(self) -> set[str]:
        enabled = await self._registry.enabled_agents()
        available = {agent.role.value for agent in enabled}
        missing = [
            role.value for role in self._required_roles if role.value not in available
        ]
        if missing:
            raise NoEnabledAgentError(
                "No enabled agent is registered for required roles: "
                + ", ".join(missing)
            )
        return available


def _usage(usage: ExecutionUsage) -> ExecutionUsage:
    """Pass through untouched: the provider reported which model served this."""
    return usage
