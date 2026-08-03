"""The Orchestrator Agent on its own, without a graph around it.

These assertions used to reach the agent through `InvestigationGraph`'s `plan`
node (`test_graph.py`). ADR-0026 deleted the graph and `OrchestratorLoop` does
not run this agent at all — the loop owns sequencing itself — so the agent's
registry gate and its output allowlist are tested here directly.

Note what that means: the fail-closed refusal below no longer guards a live
chat investigation. It is enforced by this agent, and nothing in the live
wiring invokes it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from zentra_domain_agent_execution import (
    AgentInput,
    AgentRole,
    ExecutionUsage,
    ModelMessage,
    ModelResponse,
    RegisteredAgent,
)

from zentra_adapter_langgraph import NoEnabledAgentError, OrchestratorAgent
from zentra_adapter_langgraph.agents.orchestrator import REQUIRED_ROLES

INVESTIGATION_ID = UUID("11000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("22000000-0000-0000-0000-000000000002")
QUESTION = "Why did EU refunds increase from June to July 2026?"


class StubRegistry:
    def __init__(self, roles: Sequence[AgentRole]) -> None:
        self._roles = roles

    async def enabled_agents(self) -> tuple[RegisteredAgent, ...]:
        return tuple(
            RegisteredAgent(agent_id=f"{role.value}_v1", role=role, version="1")
            for role in self._roles
        )


class LedgerModel:
    """Serves one task ledger, so the registry gate is what is under test."""

    def __init__(self, tasks: list[dict[str, str]]) -> None:
        self._tasks = tasks

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[ModelMessage],
        max_tokens: int,
        response_schema: dict[str, Any] | None = None,
    ) -> ModelResponse:
        return ModelResponse(
            text=json.dumps({"tasks": self._tasks}),
            usage=ExecutionUsage(
                input_tokens=100,
                output_tokens=20,
                cost_usd=Decimal("0.001"),
                model="gemini/gemini-3-flash",
            ),
        )


TASKS = [
    {"role": "cube_analyst", "objective": "Quantify the movement."},
    {"role": "evaluator", "objective": "Recheck the movement."},
]


def agent(
    *,
    advertised: Sequence[AgentRole],
    required: Sequence[AgentRole] = (*REQUIRED_ROLES, AgentRole.INSIGHT),
    tasks: list[dict[str, str]] | None = None,
) -> OrchestratorAgent:
    return OrchestratorAgent(
        model=LedgerModel(TASKS if tasks is None else tasks),
        registry=StubRegistry(advertised),
        required_roles=required,
    )


def agent_input() -> AgentInput:
    return AgentInput(
        investigation_id=INVESTIGATION_ID,
        tenant_id=TENANT_ID,
        state={"question": QUESTION, "execution_id": str(INVESTIGATION_ID)},
    )


@pytest.mark.asyncio
async def test_a_missing_required_role_refuses_rather_than_proceeding() -> None:
    planner = agent(advertised=(AgentRole.CUBE_ANALYST,))

    with pytest.raises(NoEnabledAgentError, match="evaluator"):
        await planner.invoke(agent_input())


@pytest.mark.asyncio
async def test_it_refuses_when_insight_is_required_but_not_promoted() -> None:
    """The fail-closed case, and the reason the flag and the registry are two
    switches rather than one. A deployment that requires Insight without a
    promoted one must refuse rather than produce an unattributed narrative."""
    planner = agent(advertised=(AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR))

    with pytest.raises(NoEnabledAgentError, match="insight"):
        await planner.invoke(agent_input())


@pytest.mark.asyncio
async def test_its_output_is_a_task_ledger_and_nothing_else() -> None:
    """Narrative belongs to the Agent evaluated for writing it. Leaving the
    fields declared would let a regression put prose back."""
    planner = agent(
        advertised=(AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR, AgentRole.INSIGHT)
    )

    output = await planner.invoke(agent_input())

    assert set(output.fields) == {"tasks"}
    for field in ("headline", "summary", "claims", "contradictions"):
        assert field not in output.fields


@pytest.mark.asyncio
async def test_a_plan_delegating_to_no_registered_role_does_not_pass() -> None:
    """Dropping the unregistered tasks silently and reporting success would
    delegate the investigation to nobody."""
    planner = agent(
        advertised=(AgentRole.CUBE_ANALYST, AgentRole.EVALUATOR, AgentRole.INSIGHT),
        tasks=[{"role": "forecaster", "objective": "Project next quarter."}],
    )

    output = await planner.invoke(agent_input())

    assert output.fields["tasks"] == []
    assert output.outcome.passed is False
