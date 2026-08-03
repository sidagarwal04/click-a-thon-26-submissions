from __future__ import annotations

from collections.abc import Sequence

import anthropic
from anthropic import AsyncAnthropic
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
from .providers import token_cost_usd


def _wire_message(message: ModelMessage) -> dict[str, object]:
    """One ModelMessage as Anthropic content blocks.

    Plain turns stay a plain string rather than a one-element block list: that
    is the shape every existing recorded interaction used, and changing it
    would alter the request for calls that have nothing to do with tools.
    """
    if not message.tool_calls and not message.tool_results:
        return {"role": message.role, "content": message.content}

    blocks: list[dict[str, object]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    blocks.extend(
        {
            "type": "tool_use",
            "id": call.call_id,
            "name": call.name,
            "input": call.arguments,
        }
        for call in message.tool_calls
    )
    blocks.extend(
        {
            "type": "tool_result",
            "tool_use_id": result.call_id,
            "content": result.content,
            "is_error": result.is_error,
        }
        for result in message.tool_results
    )
    return {"role": message.role, "content": blocks}


class AnthropicModelClient:
    """ModelPort over the Anthropic Messages API.

    System prompts are sent as a cacheable block: they are stable across every
    investigation, so the governed catalog and role instructions are written
    once and read at ~0.1x on every subsequent agent call. No other provider in
    the chain offers an equivalent, which is why this client is separate.
    """

    def __init__(self, client: AsyncAnthropic) -> None:
        self._client = client

    @classmethod
    def from_api_key(cls, api_key: str) -> AnthropicModelClient:
        return cls(AsyncAnthropic(api_key=api_key))

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
        # Accepted for ModelPort conformance, but deliberately never sent:
        # verified live against claude-sonnet-5, this whole model generation
        # answers 400 "temperature is deprecated for this model" the instant
        # it is included, which took down every Anthropic call and, through
        # it, the entire chain. Anthropic no longer takes this knob.
        temperature: float = 0.2,
    ) -> ModelResponse:
        del temperature
        request: dict[str, object] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [_wire_message(message) for message in messages],
        }
        if tools:
            request["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]
        if response_schema is not None:
            request["output_config"] = {
                "format": {"type": "json_schema", "schema": response_schema}
            }

        try:
            response = await self._client.messages.create(**request)  # type: ignore[arg-type]
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise ProviderAuthError(f"anthropic rejected credentials: {e}") from e
        except (
            anthropic.RateLimitError,
            anthropic.InternalServerError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
        ) as e:
            raise ProviderUnavailableError(f"anthropic unavailable: {e}") from e
        except anthropic.APIStatusError as e:
            # Any other status the API can answer with. Falling through is the
            # default: letting an unenumerated status escape would bypass the
            # chain entirely rather than trying the next rung.
            raise ProviderUnavailableError(
                f"anthropic returned {e.status_code}: {e}"
            ) from e
        except anthropic.APIError as e:
            raise ProviderUnavailableError(f"anthropic failed: {e}") from e

        if response.stop_reason == "max_tokens":
            raise ProviderTruncatedError(
                f"anthropic/{model} hit the {max_tokens} token ceiling"
            )

        text = next(
            (block.text for block in response.content if block.type == "text"),
            "",
        )
        tool_calls = tuple(
            ToolCall(
                call_id=block.id,
                name=block.name,
                arguments=dict(block.input) if isinstance(block.input, dict) else {},
            )
            for block in response.content
            if block.type == "tool_use"
        )
        usage = response.usage
        cache_read = usage.cache_read_input_tokens or 0
        cache_write = usage.cache_creation_input_tokens or 0
        return ModelResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            usage=ExecutionUsage(
                input_tokens=usage.input_tokens + cache_read + cache_write,
                output_tokens=usage.output_tokens,
                cost_usd=token_cost_usd(
                    model,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                ),
                model=response.model,
            ),
        )
