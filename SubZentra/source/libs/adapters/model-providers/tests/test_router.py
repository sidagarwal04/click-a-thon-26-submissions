from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from zentra_domain_agent_execution import (
    AgentRole,
    ExecutionUsage,
    ModelMessage,
    ModelResponse,
    ToolCall,
    ToolDefinition,
)

from zentra_adapter_model_providers import (
    ChainExhaustedError,
    ModelTier,
    Provider,
    ProviderAuthError,
    ProviderCircuitBreaker,
    ProviderTruncatedError,
    ProviderUnavailableError,
    RoutedModelClient,
    chain_for,
)
from zentra_adapter_model_providers.breaker import BreakerState

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
VALID = json.dumps({"answer": "ok"})


class StubClient:
    """Replays a scripted sequence of outcomes for one provider."""

    def __init__(self, *outcomes: Any) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0
        self.max_tokens_seen: list[int] = []
        self.tools_seen: list[tuple[Any, ...]] = []

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[ModelMessage],
        max_tokens: int,
        response_schema: dict[str, Any] | None = None,
        tools: Sequence[Any] = (),
        temperature: float = 0.2,
    ) -> ModelResponse:
        self.calls += 1
        self.max_tokens_seen.append(max_tokens)
        self.tools_seen.append(tuple(tools))
        outcome = self._outcomes[min(self.calls - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        # A whole response, for cases that need to script something other than
        # the text — a turn that asks for a tool, say.
        if isinstance(outcome, ModelResponse):
            return outcome
        return ModelResponse(
            text=outcome,
            usage=ExecutionUsage(
                input_tokens=10,
                output_tokens=5,
                cost_usd=Decimal("0"),
                model=f"{model}-served",
            ),
        )


async def run(
    clients: dict[Provider, Any],
    *,
    tier: ModelTier = ModelTier.FREE,
    role: AgentRole = AgentRole.CUBE_ANALYST,
    breaker: ProviderCircuitBreaker | None = None,
    schema: dict[str, Any] | None = SCHEMA,
) -> ModelResponse:
    router = RoutedModelClient(tier=tier, clients=clients, breaker=breaker)
    return await router.complete(
        model=role.value,
        system="system",
        messages=[ModelMessage(role="user", content="question")],
        max_tokens=99999,
        response_schema=schema,
    )


@pytest.mark.asyncio
async def test_rate_limited_provider_falls_through_to_the_next_rung() -> None:
    first = StubClient(ProviderUnavailableError("429 rate limited"))
    second = StubClient(VALID)

    response = await run({Provider.GEMINI: first, Provider.CEREBRAS: second})

    assert first.calls == 1
    assert second.calls == 1
    assert response.text == VALID


@pytest.mark.asyncio
async def test_bad_credentials_raise_instead_of_spending_elsewhere() -> None:
    first = StubClient(ProviderAuthError("401 invalid key"))
    second = StubClient(VALID)

    with pytest.raises(ProviderAuthError):
        await run({Provider.GEMINI: first, Provider.CEREBRAS: second})

    # The whole point: a misconfigured key must not quietly cost money.
    assert second.calls == 0


@pytest.mark.asyncio
async def test_unenumerated_status_falls_through_rather_than_escaping() -> None:
    """A 402 from a free tier out of credit killed a whole live run: the status
    was not in the mapped set, so it escaped the chain walker entirely. Any
    provider answer that is not an auth failure must fall through."""

    class WeirdStatusClient(StubClient):
        async def complete(self, **kwargs: Any) -> ModelResponse:
            self.calls += 1
            raise ProviderUnavailableError("cerebras returned 402: payment required")

    first = WeirdStatusClient()
    second = StubClient(VALID)

    # OpenRouter, not Groq: Groq now outranks Cerebras in the chain, so it
    # would answer before the 402 rung was ever reached.
    response = await run({Provider.CEREBRAS: first, Provider.OPENROUTER: second})

    assert first.calls == 1
    assert second.calls == 1
    assert response.text == VALID


@pytest.mark.asyncio
async def test_truncated_response_falls_through() -> None:
    first = StubClient(ProviderTruncatedError("hit the ceiling"))
    second = StubClient(VALID)

    await run({Provider.GEMINI: first, Provider.CEREBRAS: second})

    assert second.calls == 1


@pytest.mark.asyncio
async def test_schema_violation_retries_once_then_falls_through() -> None:
    bad = json.dumps({"wrong_field": 1})
    first = StubClient(bad, bad)
    second = StubClient(VALID)

    response = await run({Provider.GEMINI: first, Provider.CEREBRAS: second})

    assert first.calls == 2, "one retry on the same provider before moving on"
    assert response.text == VALID


@pytest.mark.asyncio
async def test_schema_violation_recovering_on_retry_keeps_the_cheaper_rung() -> None:
    first = StubClient(json.dumps({"wrong_field": 1}), VALID)
    second = StubClient(VALID)

    response = await run({Provider.GEMINI: first, Provider.CEREBRAS: second})

    assert first.calls == 2
    assert second.calls == 0
    assert response.text == VALID


@pytest.mark.asyncio
async def test_unparseable_json_is_treated_as_a_schema_violation() -> None:
    first = StubClient("{not json", "{not json")
    second = StubClient(VALID)

    await run({Provider.GEMINI: first, Provider.CEREBRAS: second})

    assert second.calls == 1


@pytest.mark.asyncio
async def test_provider_without_a_key_is_skipped_not_failed() -> None:
    only = StubClient(VALID)

    # Gemini leads the free analyst chain; with no key it is simply absent.
    response = await run({Provider.CEREBRAS: only})

    assert only.calls == 1
    assert response.text == VALID


@pytest.mark.asyncio
async def test_exhausted_chain_reports_every_attempt() -> None:
    failing = StubClient(ProviderUnavailableError("down"))

    with pytest.raises(ChainExhaustedError) as caught:
        await run({Provider.GEMINI: failing, Provider.CEREBRAS: failing})

    assert "cube_analyst" in str(caught.value)
    assert len(caught.value.attempts) == len(
        chain_for(ModelTier.FREE, AgentRole.CUBE_ANALYST)
    )


@pytest.mark.asyncio
async def test_rung_ceiling_overrides_the_agents_request() -> None:
    client = StubClient(VALID)

    await run({Provider.GEMINI: client})

    # The agent asked for 99999; the free rung caps it far lower.
    assert client.max_tokens_seen == [8000]


@pytest.mark.asyncio
async def test_breaker_opens_after_three_failures_and_stops_calling() -> None:
    clock = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    breaker = ProviderCircuitBreaker(now=lambda: clock)
    flaky = StubClient(ProviderUnavailableError("429"))
    healthy = StubClient(VALID)
    clients = {Provider.GEMINI: flaky, Provider.CEREBRAS: healthy}

    for _ in range(3):
        await run(clients, breaker=breaker)

    assert flaky.calls == 3
    assert breaker.state(Provider.GEMINI) is BreakerState.OPEN

    await run(clients, breaker=breaker)
    assert flaky.calls == 3, "open circuit stops paying the 429 round trip"


@pytest.mark.asyncio
async def test_breaker_half_opens_after_the_cooldown() -> None:
    clock = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)
    breaker = ProviderCircuitBreaker(now=lambda: clock)
    flaky = StubClient(ProviderUnavailableError("429"))
    healthy = StubClient(VALID)
    clients = {Provider.GEMINI: flaky, Provider.CEREBRAS: healthy}

    for _ in range(3):
        await run(clients, breaker=breaker)
    assert breaker.state(Provider.GEMINI) is BreakerState.OPEN

    clock += timedelta(seconds=61)
    assert breaker.state(Provider.GEMINI) is BreakerState.HALF_OPEN

    flaky._outcomes = [VALID]
    await run(clients, breaker=breaker)

    assert flaky.calls == 4, "one probe is allowed through"
    assert breaker.state(Provider.GEMINI) is BreakerState.CLOSED


@pytest.mark.asyncio
async def test_a_successful_call_still_records_what_failed_before_it() -> None:
    """The live Evaluator fell through three providers before Gemini answered,
    and nothing recorded it — each rung had to be probed by hand afterwards."""
    dead = StubClient(ProviderUnavailableError("cerebras returned 402: no credit"))
    missing = StubClient(ProviderUnavailableError("nvidia returned 404: unknown model"))
    served = StubClient(VALID)

    response = await run(
        {
            Provider.CEREBRAS: dead,
            Provider.NVIDIA: missing,
            Provider.GEMINI: served,
        },
        role=AgentRole.EVALUATOR,
    )

    assert response.text == VALID
    trail = "\n".join(response.fallbacks)
    assert "nvidia returned 404" in trail
    assert "cerebras returned 402" in trail
    # Rungs skipped for want of a key are part of the story too: without them
    # the trail cannot explain why a chain ran shorter than it looks.
    assert "no API key configured" in trail
    assert "gemini" not in trail


@pytest.mark.asyncio
async def test_a_first_rung_success_carries_an_empty_trail() -> None:
    response = await run({Provider.GEMINI: StubClient(VALID)})

    assert response.fallbacks == ()


# --- tool calling ---------------------------------------------------------

TOOL = ToolDefinition(
    name="semantic_catalog_search",
    description="Find governed members matching a term.",
    input_schema={
        "type": "object",
        "properties": {"term": {"type": "string"}},
        "required": ["term"],
        "additionalProperties": False,
    },
)


@pytest.mark.asyncio
async def test_a_rung_without_tool_support_is_skipped_and_recorded() -> None:
    """Cerebras and OpenRouter still serve one-shot calls; they are passed over
    only when tools are actually asked for, and the pass is visible."""
    cerebras = StubClient(VALID)
    anthropic = StubClient(VALID)

    client = RoutedModelClient(
        tier=ModelTier.FREE,
        clients={Provider.CEREBRAS: cerebras, Provider.ANTHROPIC: anthropic},
    )
    response = await client.complete(
        model=AgentRole.CUBE_ANALYST.value,
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        response_schema=SCHEMA,
        tools=[TOOL],
    )

    assert cerebras.calls == 0
    assert anthropic.calls == 1
    assert any("no tool support" in attempt for attempt in response.fallbacks)


@pytest.mark.asyncio
async def test_the_same_rung_still_serves_when_no_tools_are_requested() -> None:
    cerebras = StubClient(VALID)

    client = RoutedModelClient(
        tier=ModelTier.FREE,
        clients={Provider.CEREBRAS: cerebras},
    )
    await client.complete(
        model=AgentRole.CUBE_ANALYST.value,
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        response_schema=SCHEMA,
    )

    assert cerebras.calls == 1


@pytest.mark.asyncio
async def test_a_tool_request_is_not_validated_against_the_final_schema() -> None:
    """A turn asking for a tool has not answered yet.

    Validating its empty text against the declared schema would fail every
    tool round, retry once, and then burn the rest of the chain — turning a
    working loop into an exhausted one.
    """
    asking = ModelResponse(
        text="",
        tool_calls=(ToolCall(call_id="c1", name="semantic_catalog_search"),),
        stop_reason="tool_use",
        usage=ExecutionUsage(model="anthropic/claude-sonnet-5"),
    )
    anthropic = StubClient(asking)

    client = RoutedModelClient(
        tier=ModelTier.FREE,
        clients={Provider.ANTHROPIC: anthropic},
    )
    response = await client.complete(
        model=AgentRole.CUBE_ANALYST.value,
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        response_schema=SCHEMA,
        tools=[TOOL],
    )

    assert anthropic.calls == 1
    assert response.tool_calls[0].name == "semantic_catalog_search"


@pytest.mark.asyncio
async def test_tools_reach_the_provider_client() -> None:
    anthropic = StubClient(VALID)

    client = RoutedModelClient(
        tier=ModelTier.FREE,
        clients={Provider.ANTHROPIC: anthropic},
    )
    await client.complete(
        model=AgentRole.CUBE_ANALYST.value,
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        tools=[TOOL],
    )

    assert anthropic.tools_seen == [(TOOL,)]
