from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any, Protocol

from openai import AsyncOpenAI, OpenAIError
from zentra_domain_investigation import VisualizationBriefV1

THESYS_VISUALIZE_URL = "https://api.thesys.dev/v1/visualize/chat/completions"
THESYS_BASE_URL = "https://api.thesys.dev/v1/visualize"
DEFAULT_THESYS_MODEL = "c1/anthropic/claude-sonnet-4/v-20251230"
MAX_C1_RESPONSE_BYTES = 2_000_000
_VERSIONED_MODEL = re.compile(r"^c1(?:/[a-z0-9][a-z0-9._-]*)+/v-(\d{8})$")


class _Completions(Protocol):
    async def create(self, **values: Any) -> Any: ...


class _Chat(Protocol):
    completions: _Completions


class _Client(Protocol):
    chat: _Chat


@dataclass(frozen=True, slots=True)
class ThesysRenderResult:
    c1_response: str
    model: str
    api_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int


class ThesysRenderError(RuntimeError):
    def __init__(self, category: str, *, transient: bool) -> None:
        super().__init__("Visualization rendering failed safely")
        self.category = category
        self.transient = transient


class ThesysC1Client:
    """Presentation-only adapter for Thesys' OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_THESYS_MODEL,
        input_price_per_million: Decimal = Decimal("3"),
        output_price_per_million: Decimal = Decimal("15"),
        client: _Client | None = None,
    ) -> None:
        match = _VERSIONED_MODEL.fullmatch(model)
        if match is None:
            raise ValueError("Thesys model must include an explicit API version")
        self._model = model
        self._api_version = f"v-{match.group(1)}"
        self._input_price = input_price_per_million
        self._output_price = output_price_per_million
        self._client = client or AsyncOpenAI(api_key=api_key, base_url=THESYS_BASE_URL)

    async def render(self, brief: VisualizationBriefV1) -> ThesysRenderResult:
        started = perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                stream=False,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Render only the governed VisualizationBriefV1. "
                            "Do not infer new facts or actions."
                        ),
                    },
                    {"role": "user", "content": brief.normalized_json()},
                ],
            )
        except OpenAIError as error:
            raise _safe_error(error) from None
        except (ConnectionError, TimeoutError):
            raise ThesysRenderError("network_error", transient=True) from None

        latency_ms = int((perf_counter() - started) * 1000)
        try:
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError
            if len(content.encode("utf-8")) > MAX_C1_RESPONSE_BYTES:
                raise ThesysRenderError("response_oversized", transient=False)
            usage = response.usage
            input_tokens = int(usage.prompt_tokens if usage is not None else 0)
            output_tokens = int(usage.completion_tokens if usage is not None else 0)
            served_model = str(response.model)
        except ThesysRenderError:
            raise
        except (AttributeError, IndexError, TypeError, ValueError):
            raise ThesysRenderError("malformed_response", transient=False) from None

        cost = (
            Decimal(input_tokens) * self._input_price
            + Decimal(output_tokens) * self._output_price
        ) / Decimal(1_000_000)
        return ThesysRenderResult(
            c1_response=content,
            model=served_model,
            api_version=self._api_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )


def _safe_error(error: OpenAIError) -> ThesysRenderError:
    status_code = getattr(error, "status_code", None)
    if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
        return ThesysRenderError("provider_unavailable", transient=True)
    if status_code in {400, 403, 413}:
        return ThesysRenderError("provider_rejected", transient=False)
    return ThesysRenderError("provider_error", transient=False)
