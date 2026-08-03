from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from zentra_domain_investigation import VisualizationBriefV1

from zentra_adapter_thesys import (
    DEFAULT_THESYS_MODEL,
    ThesysC1Client,
    ThesysRenderError,
)


class _Completions:
    def __init__(self) -> None:
        self.request: dict[str, object] = {}

    async def create(self, **values: object) -> object:
        self.request = values
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="<c1 />"))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
            model=DEFAULT_THESYS_MODEL,
        )


def _brief() -> VisualizationBriefV1:
    return VisualizationBriefV1(
        investigation_id=UUID("10000000-0000-0000-0000-000000000001"),
        question="How did revenue change?",
        headline="Revenue increased",
        summary="The governed comparison increased.",
        outcome_kind="confidence",
        confidence=0.91,
    )


@pytest.mark.asyncio
async def test_render_uses_pinned_non_streaming_tool_free_request() -> None:
    completions = _Completions()
    transport = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    result = await ThesysC1Client(api_key="secret", client=transport).render(_brief())

    assert completions.request["model"] == DEFAULT_THESYS_MODEL
    assert completions.request["stream"] is False
    assert "tools" not in completions.request
    assert result.api_version == "v-20251230"
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.cost_usd == Decimal("0.000600")


def test_unversioned_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="explicit API version"):
        ThesysC1Client(api_key="secret", model="c1/anthropic/claude-sonnet-4")


@pytest.mark.asyncio
async def test_network_and_malformed_responses_fail_with_safe_categories() -> None:
    class NetworkFailure:
        async def create(self, **_: object) -> object:
            raise ConnectionError("secret-provider-body")

    network = SimpleNamespace(chat=SimpleNamespace(completions=NetworkFailure()))
    with pytest.raises(ThesysRenderError) as network_error:
        await ThesysC1Client(api_key="secret-key", client=network).render(_brief())
    assert network_error.value.category == "network_error"
    assert network_error.value.transient is True
    assert "secret" not in str(network_error.value)

    class EmptyResponse:
        async def create(self, **_: object) -> object:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
                usage=None,
                model=DEFAULT_THESYS_MODEL,
            )

    malformed = SimpleNamespace(chat=SimpleNamespace(completions=EmptyResponse()))
    with pytest.raises(ThesysRenderError) as malformed_error:
        await ThesysC1Client(api_key="secret-key", client=malformed).render(_brief())
    assert malformed_error.value.category == "malformed_response"
    assert malformed_error.value.transient is False
