from __future__ import annotations

import json
from collections.abc import Sequence

import jsonschema
from pydantic.types import JsonValue
from zentra_domain_agent_execution import (
    AgentRole,
    ModelMessage,
    ModelPort,
    ModelResponse,
    ToolDefinition,
)

from .breaker import ProviderCircuitBreaker
from .errors import (
    ChainExhaustedError,
    ProviderAuthError,
    ProviderError,
    ProviderUnavailableError,
)
from .providers import ModelChoice, ModelTier, Provider
from .routing import chain_for


class SchemaViolationError(ProviderError):
    """The provider returned JSON that does not satisfy the declared schema."""


class RoutedModelClient:
    """ModelPort that resolves an agent role to a provider chain.

    Agents ask for a role — `"cube_analyst"` — not a model. The chain for that
    role in this client's tier decides what actually runs, so swapping
    providers never touches agent code.
    """

    def __init__(
        self,
        *,
        tier: ModelTier,
        clients: dict[Provider, ModelPort],
        breaker: ProviderCircuitBreaker | None = None,
    ) -> None:
        self._tier = tier
        self._clients = clients
        self._breaker = breaker or ProviderCircuitBreaker()

    @property
    def tier(self) -> ModelTier:
        return self._tier

    async def complete(
        self,
        *,
        model: str,
        system: str,
        messages: Sequence[ModelMessage],
        max_tokens: int,
        response_schema: dict[str, JsonValue] | None = None,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.2,
    ) -> ModelResponse:
        role = AgentRole(model)
        attempts: list[str] = []

        for choice in chain_for(self._tier, role):
            client = self._clients.get(choice.provider)
            if client is None:
                # No key configured. Skipping rather than failing is what lets
                # the system run on ANTHROPIC_API_KEY alone.
                attempts.append(f"{choice}: no API key configured")
                continue
            if tools and not choice.supports_tools:
                # Recorded rather than silently skipped, for the same reason
                # every other skip is: a rung that cannot serve tools would
                # otherwise answer in prose, and the caller would read a
                # refusal to use tools as the model choosing not to.
                attempts.append(f"{choice}: no tool support")
                continue
            if not self._breaker.allow(choice.provider):
                attempts.append(f"{choice}: circuit open")
                continue

            try:
                response = await self._attempt(
                    client=client,
                    choice=choice,
                    system=system,
                    messages=messages,
                    response_schema=response_schema,
                    tools=tools,
                    temperature=temperature,
                )
            except ProviderAuthError:
                # Never falls through: a bad key is a configuration mistake, and
                # quietly spending money on the next provider would hide it.
                raise
            except ProviderError as error:
                self._breaker.record_failure(choice.provider)
                attempts.append(f"{choice}: {error}")
                continue

            self._breaker.record_success(choice.provider)
            # Carried even though this call succeeded: a chain that quietly
            # degrades is a chain nobody notices is degrading.
            return response.model_copy(update={"fallbacks": tuple(attempts)})

        raise ChainExhaustedError(role.value, attempts)

    async def _attempt(
        self,
        *,
        client: ModelPort,
        choice: ModelChoice,
        system: str,
        messages: Sequence[ModelMessage],
        response_schema: dict[str, JsonValue] | None,
        tools: Sequence[ToolDefinition] = (),
        temperature: float = 0.2,
    ) -> ModelResponse:
        """One rung, with a single same-provider retry on a schema violation.

        A free model that returns plausible-but-wrong JSON gets one more go
        before the chain moves on — models of this class often succeed on a
        second attempt, and falling straight through would waste the cheaper rung.
        """
        last: SchemaViolationError | None = None
        for _ in range(2):
            response = await client.complete(
                model=choice.model,
                system=system,
                messages=messages,
                # The rung's ceiling wins over the agent's request: free-tier
                # token budgets are far tighter than Anthropic's.
                max_tokens=choice.max_tokens,
                response_schema=response_schema,
                tools=tools,
                temperature=temperature,
            )
            if response_schema is None:
                return response
            # A turn that asked for tools has not answered yet, so there is no
            # final object to validate. Validating the empty text here would
            # fail every tool round and burn the whole chain.
            if response.tool_calls:
                return response
            try:
                _validate(response.text, response_schema)
            except SchemaViolationError as error:
                last = error
                continue
            return response
        assert last is not None
        raise last


def _validate(text: str, schema: dict[str, JsonValue]) -> None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise SchemaViolationError(f"response was not valid JSON: {error}") from error
    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as error:
        raise SchemaViolationError(
            f"response did not satisfy the declared schema: {error.message}"
        ) from error


__all__ = [
    "ProviderUnavailableError",
    "RoutedModelClient",
    "SchemaViolationError",
]
