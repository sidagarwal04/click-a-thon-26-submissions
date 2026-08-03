from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

import openai
from openai import AsyncOpenAI
from pydantic.types import JsonValue
from zentra_domain_agent_execution import (
    ExecutionUsage,
    ModelMessage,
    ModelResponse,
    ToolCall,
    ToolDefinition,
)

from .errors import (
    ProviderAuthError,
    ProviderTruncatedError,
    ProviderUnavailableError,
)
from .providers import (
    Provider,
    ProviderConfig,
    UnknownModelError,
    token_cost_usd,
)

SCHEMA_NAME = "agent_output"


def _arguments(raw: str | None) -> dict[str, JsonValue]:
    """Tool arguments arrive as a JSON *string* here, unlike Anthropic's dict.

    A model that emits malformed arguments is a model that made a bad call, not
    a provider that broke: returning empty lets the tool refuse on its own
    terms and tell the model why, which is a turn it can recover from.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _wire_messages(message: ModelMessage) -> list[dict[str, object]]:
    """One ModelMessage as OpenAI chat messages.

    Fans out rather than mapping one-to-one: a turn carrying tool results
    becomes one `role: "tool"` message per result, because this wire format
    has no way to put several results in a single message the way Anthropic's
    content blocks do.
    """
    if message.tool_results:
        return [
            {
                "role": "tool",
                "tool_call_id": result.call_id,
                "content": result.content,
            }
            for result in message.tool_results
        ]

    wire: dict[str, object] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]
        # An assistant turn that only asked for tools has no prose, and some
        # providers reject an empty string where they accept a null.
        if not message.content:
            wire["content"] = None
    return [wire]


class OpenAICompatibleModelClient:
    """One ModelPort for Groq, Cerebras, OpenAI, Gemini, and OpenRouter.

    All five expose the OpenAI wire format, so they differ only by base URL and
    key. Structured output goes through `response_format` with `strict: true`,
    which every one of them supports for the models in the routing table.
    """

    def __init__(self, *, config: ProviderConfig, client: AsyncOpenAI) -> None:
        self._config = config
        self._client = client

    @classmethod
    def from_api_key(
        cls,
        config: ProviderConfig,
        api_key: str,
    ) -> OpenAICompatibleModelClient:
        return cls(
            config=config,
            client=AsyncOpenAI(api_key=api_key, base_url=config.base_url),
        )

    @property
    def provider(self) -> Provider:
        return self._config.provider

    async def close(self) -> None:
        await self._client.close()

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
        name = self._config.provider.value
        wire: list[dict[str, object]] = [{"role": "system", "content": system}]
        for message in messages:
            wire.extend(_wire_messages(message))
        request: dict[str, object] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": wire,
        }
        if tools:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in tools
            ]
        if response_schema is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": SCHEMA_NAME,
                    "schema": response_schema,
                    "strict": True,
                },
            }

        try:
            response = await self._client.chat.completions.create(**request)  # type: ignore[arg-type]
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise ProviderAuthError(f"{name} rejected credentials: {e}") from e
        except (
            openai.RateLimitError,
            openai.InternalServerError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ) as e:
            raise ProviderUnavailableError(f"{name} unavailable: {e}") from e
        except openai.BadRequestError as e:
            # A provider that advertises strict schema but rejects ours is a
            # capability gap, not a bug in the request — try the next rung.
            raise ProviderUnavailableError(f"{name} rejected the request: {e}") from e
        except openai.APIStatusError as e:
            # Everything else the provider can answer with. A free tier out of
            # credit returns 402, and other statuses (404, 409, 413, 422) are
            # equally provider-specific. None of them mean the next rung cannot
            # serve, and letting an unenumerated status escape would defeat the
            # whole chain — so the default is to fall through, not to propagate.
            raise ProviderUnavailableError(
                f"{name} returned {e.status_code}: {e}"
            ) from e
        except openai.APIError as e:
            raise ProviderUnavailableError(f"{name} failed: {e}") from e

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise ProviderTruncatedError(
                f"{_qualified(name, model)} hit the {max_tokens} token ceiling"
            )

        tool_calls = tuple(
            ToolCall(
                call_id=call.id,
                name=call.function.name,
                arguments=_arguments(call.function.arguments),
            )
            for call in (choice.message.tool_calls or ())
            # Only function calls carry a `.function`. Providers are starting
            # to return other call types (custom, built-in), and reaching for
            # `.function` on one of those would fail the whole response.
            if getattr(call, "type", "function") == "function"
        )

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cache_read = 0
        if usage is not None and usage.prompt_tokens_details is not None:
            cache_read = usage.prompt_tokens_details.cached_tokens or 0

        return ModelResponse(
            text=choice.message.content or "",
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason,
            usage=ExecutionUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=_cost(
                    served=response.model,
                    requested=model,
                    input_tokens=max(0, input_tokens - cache_read),
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read,
                ),
                # Several ids already carry their own vendor prefix
                # (openai/gpt-oss-120b), so do not double it up.
                model=(
                    response.model
                    if "/" in response.model
                    else f"{name}/{response.model}"
                ),
            ),
        )


def _qualified(provider: str, model: str) -> str:
    """Provider-qualified id, without doubling a prefix the model already has."""
    return model if "/" in model else f"{provider}/{model}"


def _cost(
    *,
    served: str,
    requested: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
) -> Decimal:
    """Price what answered, not what was asked for.

    Some routing entries are aliases rather than models — `openrouter/free`
    resolved to `nvidia/nemotron-nano-9b-v2:free` on a live run — so pricing the
    requested id records the alias's cost for a model that may have its own.
    Falls back to the requested id when the served one is unpriced, because a
    cost lookup must never fail a call that already succeeded.
    """
    for candidate in (served, requested):
        try:
            return token_cost_usd(
                candidate,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
            )
        except UnknownModelError:
            continue
    raise UnknownModelError(
        f"No recorded price for {served!r} (served) or {requested!r} (requested)"
    )
