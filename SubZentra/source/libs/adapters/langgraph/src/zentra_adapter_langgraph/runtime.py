"""The loop every tool-using Agent runs.

An Agent used to be a fixed sequence of model calls written into its own class.
That is enough when the shape of the answer is known in advance — plan a query,
read the result — and it is not enough against a tenant's own catalog, where
the right query is not knowable until you have looked at what is there.

This is the generic form: offer the Agent its permitted tools, run whatever it
asks for, hand back the results, repeat until it answers or the step cap trips.
It is deliberately not a LangGraph node — the graph orchestrates *Agents*, and
what happens inside one Agent Execution is this.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from pydantic.types import JsonValue
from zentra_domain_agent_execution import (
    AgentDescriptor,
    ExecutionUsage,
    ModelMessage,
    ModelPort,
    ModelResponse,
    ToolCall,
    ToolInvocation,
    ToolResult,
    UnauthorizedToolError,
)

from .schemas import MalformedAgentResponseError, parse_json_object
from .skills import SkillRegistry
from .tools import ToolRegistry

#: How many model turns one Agent Execution may take before it is failed.
#:
#: The cap exits hard and visibly, exactly as MAX_EVALUATION_ATTEMPTS does for
#: the Evaluator loop. A model that keeps calling tools without converging is
#: not making progress, and silently returning its last partial answer would
#: publish a conclusion nobody decided to draw.
#:
#: 12 was tuned against the demo warehouse's one small Commerce cube. A real
#: tenant's harvested catalog is two orders of magnitude bigger — hundreds of
#: members across many tables — and genuinely needs more search-then-query
#: turns to converge; that is more exploration, not less progress.
#:
#: 20 still wasn't enough headroom for a real breakdown-by-date question —
#: observed live hitting the cap on a 30-point time series that had converged
#: fine on an earlier run, i.e. model-call variance rather than a fixed need.
MAX_STEPS = 30

#: Asked once the Agent stops calling tools, to convert its prose into the
#: declared object. Deliberately says nothing about content: the Agent has
#: already decided what it found, and this turn is only about shape.
_CLOSING_TURN = (
    "Report your findings now as the required structured object, using only "
    "figures from the query results above."
)


class StepBudgetExhaustedError(RuntimeError):
    """An Agent kept calling tools and never produced its answer."""


@dataclass(slots=True)
class RuntimeResult:
    """What one Agent Execution's conversation established."""

    #: The final structured object, parsed against the declared schema.
    output: dict[str, Any]
    #: Every tool that ran, in order. Names and timings only — never
    #: arguments or results, which carry rows (ADR-0006).
    tool_calls: tuple[ToolInvocation, ...] = ()
    usage: ExecutionUsage = field(default_factory=ExecutionUsage)
    fallbacks: tuple[str, ...] = ()
    #: How many model turns it took. One means it answered without tools.
    steps: int = 1


class AgentRuntime:
    """Runs one Agent's conversation to a structured answer."""

    def __init__(
        self,
        *,
        model: ModelPort,
        tools: ToolRegistry,
        skills: SkillRegistry,
        max_steps: int = MAX_STEPS,
        now: Callable[[], float] = perf_counter,
    ) -> None:
        self._model = model
        self._tools = tools
        self._skills = skills
        self._max_steps = max_steps
        self._now = now

    async def run(
        self,
        *,
        descriptor: AgentDescriptor,
        system: str,
        messages: Sequence[ModelMessage],
        response_schema: dict[str, JsonValue],
        accept: Callable[[dict[str, Any]], str | None] | None = None,
    ) -> RuntimeResult:
        """Run the conversation until the Agent produces an accepted answer.

        `accept` returns None to take the answer, or the reason to refuse it.
        A refusal goes back into the conversation as a user turn, so the Agent
        gets to fix it — a model that answers before doing the work usually
        does the work when told. Without this the loop takes the first
        schema-valid object it sees, and a schema cannot express "this answer
        rests on a query you never ran".
        """
        # Skills append to the system prompt rather than arriving as a user
        # turn, so they stay inside the cached prefix. They are stable per
        # role, so this costs nothing after the first call.
        prompt = self._skills.apply(descriptor.role, system)
        offered = self._tools.definitions_for(descriptor)

        conversation = list(messages)
        invocations: list[ToolInvocation] = []
        usage = ExecutionUsage()
        fallbacks: dict[str, None] = {}

        for step in range(1, self._max_steps + 1):
            response = await self._model.complete(
                model=descriptor.role.value,
                system=prompt,
                messages=conversation,
                max_tokens=descriptor.context_budget_tokens,
                # Not both. Strict structured output obliges the model to emit
                # an object matching the schema, which it cannot do while also
                # emitting a tool call — observed live, where an Analyst given
                # both returned the same schema-valid placeholder every turn
                # and never once called a tool. So: schema alone when there are
                # no tools, tools alone while the conversation is still open,
                # and the schema again on the closing turn below.
                response_schema=None if offered else response_schema,
                tools=offered,
            )
            usage = _accumulate(usage, response)
            fallbacks.update(dict.fromkeys(response.fallbacks))

            if response.tool_calls:
                conversation.append(
                    ModelMessage(
                        role="assistant",
                        content=response.text,
                        tool_calls=response.tool_calls,
                    )
                )
                results: list[ToolResult] = []
                for call in response.tool_calls:
                    result, invocation = await self._invoke(descriptor, call)
                    results.append(result)
                    invocations.append(invocation)
                conversation.append(
                    ModelMessage(role="user", content="", tool_results=tuple(results))
                )
                continue

            if offered:
                # The Agent has stopped reaching for tools, so its prose is the
                # answer. One more call, schema enforced and tools withdrawn,
                # turns it into the object the caller declared.
                conversation.append(
                    ModelMessage(role="assistant", content=response.text)
                )
                conversation.append(
                    ModelMessage(role="user", content=_CLOSING_TURN)
                )
                closing = await self._model.complete(
                    model=descriptor.role.value,
                    system=prompt,
                    messages=conversation,
                    max_tokens=descriptor.context_budget_tokens,
                    response_schema=response_schema,
                )
                usage = _accumulate(usage, closing)
                fallbacks.update(dict.fromkeys(closing.fallbacks))
                response = closing

            output = parse_json_object(response.text)
            refusal = accept(output) if accept is not None else None
            if refusal is None:
                return RuntimeResult(
                    output=output,
                    tool_calls=tuple(invocations),
                    usage=usage,
                    fallbacks=tuple(fallbacks),
                    steps=step,
                )
            conversation.append(ModelMessage(role="assistant", content=response.text))
            conversation.append(ModelMessage(role="user", content=refusal))

        raise StepBudgetExhaustedError(
            f"{descriptor.agent_id} used {self._max_steps} steps without "
            f"producing an answer"
        )

    async def _invoke(
        self,
        descriptor: AgentDescriptor,
        call: ToolCall,
    ) -> tuple[ToolResult, ToolInvocation]:
        """Run one tool call, turning every failure into a turn the Agent can
        answer.

        Nothing here raises. A tool that refuses, a tool the Agent may not
        hold, a tool that breaks — all three come back as `is_error` results
        the model reads and can correct on the next step. The alternative is
        failing an entire investigation because a model guessed one argument
        wrong on its first try.
        """
        started = self._now()
        try:
            tool = self._tools.resolve(descriptor, call.name)
            result = await tool.invoke(call.arguments)
        except UnauthorizedToolError as error:
            result = ToolResult(call_id=call.call_id, content=str(error), is_error=True)
        except (MalformedAgentResponseError, ValueError) as error:
            result = ToolResult(
                call_id=call.call_id,
                content=f"{type(error).__name__}: {error}",
                is_error=True,
            )
        else:
            # Tools build results without knowing which call they answer; the
            # runtime is what pairs them back up.
            result = result.model_copy(update={"call_id": call.call_id})

        return result, ToolInvocation(
            name=call.name,
            latency_ms=max(0, int((self._now() - started) * 1000)),
            ok=not result.is_error,
        )


def _accumulate(usage: ExecutionUsage, response: ModelResponse) -> ExecutionUsage:
    """Add a turn's cost, keeping the model that served the latest one.

    `ExecutionUsage.__add__` deliberately drops the model, because which call
    decided is the Agent's to say. In a loop that is the final turn: the one
    that stopped calling tools and answered, which is what independence should
    be graded on.
    """
    return (usage + response.usage).model_copy(
        update={"model": response.usage.model or usage.model}
    )


def json_arguments(value: dict[str, JsonValue]) -> str:
    """Stable rendering, for a tool result that wants to echo what it ran."""
    return json.dumps(value, sort_keys=True)
