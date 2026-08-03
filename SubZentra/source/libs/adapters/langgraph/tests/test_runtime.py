"""The loop one Agent Execution runs, and what it refuses.

Three properties matter here and nothing else does: the loop converges, a tool
the Agent does not hold is refused rather than run, and a loop that will not
converge exits hard instead of returning a partial answer as if it were one.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest
from zentra_domain_agent_execution import (
    AgentDescriptor,
    AgentRole,
    ExecutionUsage,
    ModelMessage,
    ModelResponse,
    ToolAccess,
    ToolCall,
    ToolDefinition,
    ToolResult,
    ToolScope,
)

from zentra_adapter_langgraph.runtime import (
    AgentRuntime,
    StepBudgetExhaustedError,
)
from zentra_adapter_langgraph.skills import Skill, SkillRegistry
from zentra_adapter_langgraph.tools import ToolRegistry

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


class RecordingTool:
    """A tool that answers, and remembers what it was asked."""

    def __init__(self, name: str, *, fails: bool = False) -> None:
        self._name = name
        self._fails = fails
        self.calls: list[dict[str, Any]] = []

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description=f"The {self._name} tool.",
            input_schema={"type": "object", "properties": {}},
        )

    @property
    def scope(self) -> ToolScope:
        return ToolScope(tool_name=self._name, access=ToolAccess.READ)

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append(dict(arguments))
        if self._fails:
            raise ValueError("the tool broke")
        # Deliberately blank: pairing the result to its call is the runtime's
        # job, and a tool that guessed the id would be guessing.
        return ToolResult(call_id="", content=f"{self._name} says hello")


class ScriptedModel:
    def __init__(self, *responses: ModelResponse) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.systems: list[str] = []
        self.tools_seen: list[tuple[str, ...]] = []
        self.conversations: list[list[ModelMessage]] = []

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[ModelMessage],
        max_tokens: int,
        response_schema: dict[str, Any] | None = None,
        tools: Sequence[ToolDefinition] = (),
    ) -> ModelResponse:
        self.systems.append(system)
        self.tools_seen.append(tuple(tool.name for tool in tools))
        self.conversations.append(list(messages))
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _asking(*names: str) -> ModelResponse:
    return ModelResponse(
        text="",
        tool_calls=tuple(
            ToolCall(call_id=f"call_{index}", name=name)
            for index, name in enumerate(names)
        ),
        stop_reason="tool_use",
        usage=ExecutionUsage(input_tokens=10, output_tokens=2, model="anthropic/x"),
    )


def _answering() -> ModelResponse:
    return ModelResponse(
        text=json.dumps({"answer": "done"}),
        stop_reason="end_turn",
        usage=ExecutionUsage(input_tokens=20, output_tokens=4, model="anthropic/y"),
    )


def _descriptor(*tool_names: str) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="test_agent_v1",
        role=AgentRole.CUBE_ANALYST,
        tool_permissions=tuple(
            ToolScope(tool_name=name, access=ToolAccess.READ) for name in tool_names
        ),
        context_budget_tokens=1000,
        input_schema={"type": "object"},
        output_schema=ANSWER_SCHEMA,
        output_fields=frozenset({"answer"}),
        eval_suite_ref="evals/test",
    )


def _runtime(model: Any, tools: Sequence[Any], **kwargs: Any) -> AgentRuntime:
    return AgentRuntime(
        model=model,
        tools=ToolRegistry(tools),
        skills=kwargs.pop("skills", SkillRegistry()),
        **kwargs,
    )


async def _run(runtime: AgentRuntime, descriptor: AgentDescriptor) -> Any:
    return await runtime.run(
        descriptor=descriptor,
        system="You are a test agent.",
        messages=[ModelMessage(role="user", content="go")],
        response_schema=ANSWER_SCHEMA,
    )


@pytest.mark.asyncio
async def test_the_loop_runs_a_tool_then_answers() -> None:
    tool = RecordingTool("search")
    model = ScriptedModel(_asking("search"), _answering())

    result = await _run(_runtime(model, [tool]), _descriptor("search"))

    assert result.output == {"answer": "done"}
    assert result.steps == 2
    assert tool.calls == [{}]
    assert [invocation.name for invocation in result.tool_calls] == ["search"]
    assert result.tool_calls[0].ok is True
    # Three calls, not two: the tool turn, the turn that stopped calling tools,
    # and the closing turn that restates the answer under the schema. Tools and
    # strict structured output cannot be requested together, so the schema is
    # only applied once the conversation is done.
    assert model.calls == 3
    assert model.tools_seen == [("search",), ("search",), ()]
    assert result.usage.input_tokens == 50
    assert result.usage.model == "anthropic/y"


@pytest.mark.asyncio
async def test_the_result_is_paired_back_to_the_call_that_asked() -> None:
    """A model issuing two calls in one turn has to be able to tell the
    answers apart, and tools do not know their own call ids."""
    model = ScriptedModel(_asking("search", "query"), _answering())

    runtime = _runtime(model, [RecordingTool("search"), RecordingTool("query")])
    await _run(runtime, _descriptor("search", "query"))

    # The turn after the tool round, before the closing turn appends its own
    # two messages.
    replayed = model.conversations[1]
    results = replayed[-1].tool_results
    assert [result.call_id for result in results] == ["call_0", "call_1"]
    assert replayed[-2].tool_calls[0].call_id == "call_0"


@pytest.mark.asyncio
async def test_a_tool_the_agent_does_not_hold_is_refused_not_run() -> None:
    """The descriptor is the gate, checked on call and not only on offer.

    A model can name a tool it was never shown — hallucinated outright, or
    carried over from an earlier turn — so offering the right set is not the
    same as enforcing it.
    """
    forbidden = RecordingTool("erase_everything")
    model = ScriptedModel(_asking("erase_everything"), _answering())

    runtime = _runtime(model, [RecordingTool("search"), forbidden])
    result = await _run(runtime, _descriptor("search"))

    assert forbidden.calls == []
    assert model.tools_seen[0] == ("search",)
    assert result.tool_calls[0].ok is False
    # Refused into the conversation, not raised: the Agent is told it may not
    # do that and gets to choose again.
    assert result.output == {"answer": "done"}
    refusal = model.conversations[1][-1].tool_results[0]
    assert refusal.is_error
    assert "erase_everything" in refusal.content


@pytest.mark.asyncio
async def test_a_broken_tool_becomes_a_turn_rather_than_a_failure() -> None:
    model = ScriptedModel(_asking("search"), _answering())

    runtime = _runtime(model, [RecordingTool("search", fails=True)])
    result = await _run(runtime, _descriptor("search"))

    assert result.tool_calls[0].ok is False
    assert result.output == {"answer": "done"}
    assert "the tool broke" in model.conversations[1][-1].tool_results[0].content


@pytest.mark.asyncio
async def test_a_loop_that_never_converges_exits_hard() -> None:
    """Never returns the last partial answer as though it were the answer.

    The same discipline as MAX_EVALUATION_ATTEMPTS: a cap that quietly
    published whatever it had would publish a conclusion nobody drew.
    """
    model = ScriptedModel(_asking("search"))

    runtime = _runtime(model, [RecordingTool("search")], max_steps=3)
    with pytest.raises(StepBudgetExhaustedError):
        await _run(runtime, _descriptor("search"))

    assert model.calls == 3


@pytest.mark.asyncio
async def test_an_agent_with_no_tools_makes_one_call() -> None:
    """The one-shot path is still the one-shot path, so Agents that must not
    reach data keep behaving exactly as they did."""
    model = ScriptedModel(_answering())

    result = await _run(_runtime(model, [RecordingTool("search")]), _descriptor())

    assert model.calls == 1
    assert model.tools_seen == [()]
    assert result.steps == 1
    assert result.tool_calls == ()


@pytest.mark.asyncio
async def test_skills_are_appended_to_the_cached_system_prompt() -> None:
    """Appended to `system`, not sent as a user turn.

    The system block is what providers cache, and skills are stable per role,
    so this costs nothing after the first call. A skill arriving as a user
    message would be outside the cached prefix on every request.
    """
    skill = Skill(
        name="Sample size",
        applies_to=frozenset({AgentRole.CUBE_ANALYST}),
        instructions="Always report the sample behind a figure.",
    )
    model = ScriptedModel(_answering())

    runtime = _runtime(model, [], skills=SkillRegistry([skill]))
    await _run(runtime, _descriptor())

    assert model.systems[0].startswith("You are a test agent.")
    assert "## Sample size" in model.systems[0]
    assert "Always report the sample behind a figure." in model.systems[0]


@pytest.mark.asyncio
async def test_a_skill_for_another_role_is_not_applied() -> None:
    skill = Skill(
        name="Insight voice",
        applies_to=frozenset({AgentRole.INSIGHT}),
        instructions="Write for a business reader.",
    )
    model = ScriptedModel(_answering())

    runtime = _runtime(model, [], skills=SkillRegistry([skill]))
    await _run(runtime, _descriptor())

    assert model.systems[0] == "You are a test agent."
