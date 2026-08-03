"""How a tool conversation is put on the wire, per provider.

Both clients used to hand `ModelMessage.model_dump()` straight to the SDK,
which worked precisely because a message was a role and a string. A tool turn
is neither — Anthropic wants content blocks and OpenAI wants a parallel
`tool_calls` array plus separate `role: "tool"` messages — so the shaping is
now explicit, and this is what pins it.

No network: both SDK clients are replaced by a recorder that captures the
request and returns a canned response.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from zentra_domain_agent_execution import (
    ModelMessage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

from zentra_adapter_model_providers.anthropic_client import AnthropicModelClient
from zentra_adapter_model_providers.openai_compatible import (
    OpenAICompatibleModelClient,
)
from zentra_adapter_model_providers.providers import PROVIDERS, Provider

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

#: One full round: the model asked, the tool answered, the model must now see
#: both to continue.
CONVERSATION = [
    ModelMessage(role="user", content="Why did refunds rise?"),
    ModelMessage(
        role="assistant",
        content="",
        tool_calls=(
            ToolCall(
                call_id="call_1",
                name="semantic_catalog_search",
                arguments={"term": "refund"},
            ),
        ),
    ),
    ModelMessage(
        role="user",
        content="",
        tool_results=(
            ToolResult(call_id="call_1", content="Commerce.refundAmount (number)"),
        ),
    ),
]


class RecordingAnthropic:
    def __init__(self, response: Any) -> None:
        self.request: dict[str, Any] = {}
        self._response = response
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        return self._response


def _anthropic_response(*content: Any) -> Any:
    return SimpleNamespace(
        stop_reason="tool_use",
        content=list(content),
        model="claude-sonnet-5",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )


@pytest.mark.asyncio
async def test_anthropic_sends_tool_use_and_tool_result_blocks() -> None:
    client = RecordingAnthropic(
        _anthropic_response(SimpleNamespace(type="text", text="done"))
    )
    model = AnthropicModelClient(client)  # type: ignore[arg-type]

    await model.complete(
        model="claude-sonnet-5",
        system="s",
        messages=CONVERSATION,
        max_tokens=1000,
        tools=[TOOL],
    )

    sent = client.request["messages"]
    # A plain turn stays a plain string: that is the shape every recording made
    # before tools existed used, and changing it would move their cassette key.
    assert sent[0] == {"role": "user", "content": "Why did refunds rise?"}
    assert sent[1]["content"] == [
        {
            "type": "tool_use",
            "id": "call_1",
            "name": "semantic_catalog_search",
            "input": {"term": "refund"},
        }
    ]
    assert sent[2]["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "call_1",
            "content": "Commerce.refundAmount (number)",
            "is_error": False,
        }
    ]
    assert client.request["tools"] == [
        {
            "name": TOOL.name,
            "description": TOOL.description,
            "input_schema": TOOL.input_schema,
        }
    ]


@pytest.mark.asyncio
async def test_anthropic_parses_tool_use_blocks_back_out() -> None:
    client = RecordingAnthropic(
        _anthropic_response(
            SimpleNamespace(type="text", text=""),
            SimpleNamespace(
                type="tool_use",
                id="call_9",
                name="semantic_query",
                input={"measures": ["Commerce.refundAmount"]},
            ),
        )
    )
    model = AnthropicModelClient(client)  # type: ignore[arg-type]

    response = await model.complete(
        model="claude-sonnet-5",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        tools=[TOOL],
    )

    assert response.stop_reason == "tool_use"
    assert response.tool_calls == (
        ToolCall(
            call_id="call_9",
            name="semantic_query",
            arguments={"measures": ["Commerce.refundAmount"]},
        ),
    )


class RecordingOpenAI:
    def __init__(self, response: Any) -> None:
        self.request: dict[str, Any] = {}
        self._response = response
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        return self._response


def _openai_response(*, content: str | None, tool_calls: list[Any]) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls" if tool_calls else "stop",
                message=SimpleNamespace(content=content, tool_calls=tool_calls),
            )
        ],
        model="openai/gpt-oss-120b",
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            prompt_tokens_details=None,
        ),
    )


def _openai_client(
    response: Any,
) -> tuple[OpenAICompatibleModelClient, RecordingOpenAI]:
    inner = RecordingOpenAI(response)
    return (
        OpenAICompatibleModelClient(
            config=PROVIDERS[Provider.GROQ],
            client=inner,  # type: ignore[arg-type]
        ),
        inner,
    )


@pytest.mark.asyncio
async def test_openai_fans_tool_results_out_into_their_own_messages() -> None:
    model, inner = _openai_client(_openai_response(content="done", tool_calls=[]))

    await model.complete(
        model="openai/gpt-oss-120b",
        system="s",
        messages=CONVERSATION,
        max_tokens=1000,
        tools=[TOOL],
    )

    sent = inner.request["messages"]
    assert sent[0] == {"role": "system", "content": "s"}
    assert sent[1] == {"role": "user", "content": "Why did refunds rise?"}
    # An assistant turn with no prose sends a null content: some providers in
    # this chain reject an empty string where they accept null.
    assert sent[2]["content"] is None
    assert sent[2]["tool_calls"][0]["function"]["name"] == "semantic_catalog_search"
    # This format has no way to carry several results in one message, so the
    # turn fans out into one `role: "tool"` message per result.
    assert sent[3] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "Commerce.refundAmount (number)",
    }
    assert inner.request["tools"][0]["function"]["parameters"] == TOOL.input_schema


@pytest.mark.asyncio
async def test_openai_parses_tool_calls_and_their_json_arguments() -> None:
    call = SimpleNamespace(
        id="call_7",
        type="function",
        function=SimpleNamespace(
            name="semantic_query",
            arguments='{"measures": ["Commerce.refundAmount"]}',
        ),
    )
    model, _ = _openai_client(_openai_response(content=None, tool_calls=[call]))

    response = await model.complete(
        model="openai/gpt-oss-120b",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        tools=[TOOL],
    )

    assert response.tool_calls == (
        ToolCall(
            call_id="call_7",
            name="semantic_query",
            arguments={"measures": ["Commerce.refundAmount"]},
        ),
    )


@pytest.mark.asyncio
async def test_openai_treats_malformed_arguments_as_an_empty_call() -> None:
    """A model that emits broken arguments made a bad call; the provider did
    not break. Empty arguments let the tool refuse and say why, which is a turn
    the model can recover from — raising here would end the investigation."""
    call = SimpleNamespace(
        id="call_8",
        type="function",
        function=SimpleNamespace(name="semantic_query", arguments="{not json"),
    )
    model, _ = _openai_client(_openai_response(content=None, tool_calls=[call]))

    response = await model.complete(
        model="openai/gpt-oss-120b",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
        tools=[TOOL],
    )

    assert response.tool_calls[0].arguments == {}


@pytest.mark.asyncio
async def test_neither_client_sends_a_tools_key_when_none_are_offered() -> None:
    """The one-shot path has to stay byte-identical: every existing cassette
    was recorded without a `tools` key in the request."""
    anthropic_inner = RecordingAnthropic(
        _anthropic_response(SimpleNamespace(type="text", text="{}"))
    )
    await AnthropicModelClient(anthropic_inner).complete(  # type: ignore[arg-type]
        model="claude-sonnet-5",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
    )
    assert "tools" not in anthropic_inner.request

    model, openai_inner = _openai_client(_openai_response(content="{}", tool_calls=[]))
    await model.complete(
        model="openai/gpt-oss-120b",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
    )
    assert "tools" not in openai_inner.request


@pytest.mark.asyncio
async def test_the_openai_compatible_client_defaults_to_a_low_fixed_temperature() -> (
    None
):
    """Low and fixed rather than left to provider defaults — a trust-first
    system has nothing to gain from sampling variance, and every caller relies
    on this default rather than passing one explicitly."""
    model, openai_inner = _openai_client(_openai_response(content="{}", tool_calls=[]))
    await model.complete(
        model="openai/gpt-oss-120b",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
    )
    assert openai_inner.request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_the_anthropic_client_never_sends_temperature() -> None:
    """Verified live against claude-sonnet-5: this model generation answers
    400 "temperature is deprecated for this model" the instant it is
    included, which took down every Anthropic call and, through it, the
    entire chain — so it must never be sent, regardless of what is passed."""
    anthropic_inner = RecordingAnthropic(
        _anthropic_response(SimpleNamespace(type="text", text="{}"))
    )
    await AnthropicModelClient(anthropic_inner).complete(  # type: ignore[arg-type]
        model="claude-sonnet-5",
        system="s",
        messages=[ModelMessage(role="user", content="q")],
        max_tokens=1000,
    )
    assert "temperature" not in anthropic_inner.request
