from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    NVIDIA = "nvidia"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    OPENROUTER = "openrouter"


class ModelTier(StrEnum):
    FREE = "free"
    PREMIUM = "premium"


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """How to reach a provider, and whether it may see paid-tier traffic."""

    provider: Provider
    env_key: str
    base_url: str | None
    trains_on_input: bool


# Every provider except Anthropic speaks the OpenAI wire format, so one client
# serves five of the six — only the base URL differs.
PROVIDERS: dict[Provider, ProviderConfig] = {
    Provider.ANTHROPIC: ProviderConfig(
        provider=Provider.ANTHROPIC,
        env_key="ANTHROPIC_API_KEY",
        base_url=None,
        trains_on_input=False,
    ),
    Provider.OPENAI: ProviderConfig(
        provider=Provider.OPENAI,
        env_key="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        trains_on_input=False,
    ),
    Provider.GROQ: ProviderConfig(
        provider=Provider.GROQ,
        env_key="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1",
        trains_on_input=False,
    ),
    Provider.CEREBRAS: ProviderConfig(
        provider=Provider.CEREBRAS,
        env_key="CEREBRAS_API_KEY",
        base_url="https://api.cerebras.ai/v1",
        trains_on_input=False,
    ),
    # Gemini, NVIDIA, and OpenRouter train on free-tier traffic. The flag
    # assumes a free-tier key: Google does not train on paid-tier API data, so a
    # paid Gemini key does not in fact train — but the code cannot tell the key
    # classes apart, and privacy takes the pessimistic reading rather than an
    # assumption. Moving Gemini into a premium chain on the strength of a paid
    # key is a deliberate decision that has to revisit this flag first.
    #
    # They are reachable only from the free chain; ROUTING asserts at import
    # that none
    # appears in a premium one.
    Provider.GEMINI: ProviderConfig(
        provider=Provider.GEMINI,
        env_key="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        trains_on_input=True,
    ),
    Provider.NVIDIA: ProviderConfig(
        provider=Provider.NVIDIA,
        env_key="NVIDIA_API_KEY",
        base_url="https://integrate.api.nvidia.com/v1",
        # NVIDIA records inputs and outputs on free endpoints to train their
        # models, and warns against sending personal data. Only self-hosted NIM
        # avoids that, which is infrastructure we do not run.
        trains_on_input=True,
    ),
    Provider.OPENROUTER: ProviderConfig(
        provider=Provider.OPENROUTER,
        env_key="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        trains_on_input=True,
    ),
}


@dataclass(frozen=True, slots=True)
class ModelChoice:
    """One rung of a fallback chain."""

    provider: Provider
    model: str
    # Free tiers meter tokens per minute far more tightly than Anthropic, so
    # the ceiling belongs to the rung rather than being global.
    max_tokens: int
    # Whether this rung can be handed tools. A property of the model, not the
    # provider: `openrouter/free` resolves to whatever is free today, and the
    # NIM catalogue mixes tool-capable and text-only models behind one base
    # URL. Default False so a rung is opted in deliberately, after being
    # checked — the same discipline the strict-json_schema notes in
    # `routing.py` already record.
    supports_tools: bool = False

    @property
    def trains_on_input(self) -> bool:
        return PROVIDERS[self.provider].trains_on_input

    def __str__(self) -> str:
        # Several ids already carry a vendor prefix of their own
        # (`nvidia/nemotron-...`, `openai/gpt-oss-120b`), so do not double it.
        if "/" in self.model:
            return f"{self.provider.value}:{self.model}"
        return f"{self.provider.value}/{self.model}"


# ---------------------------------------------------------------------------
# Cost
#
# Free-tier rungs are recorded as genuinely zero rather than at a notional list
# price, so `cost_so_far_usd` stays truthful. An unpriced model is a loud
# failure, never a silent zero.
# ---------------------------------------------------------------------------

_MILLION = Decimal("1000000")
_ZERO = (Decimal("0"), Decimal("0"))

_PER_MILLION: dict[str, tuple[Decimal, Decimal]] = {
    # Anthropic list price. Sonnet 5 has a lower introductory rate through
    # 2026-08-31; list price is used so recorded cost never understates.
    "claude-sonnet-5": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "claude-haiku-4-5-20251001": (Decimal("1.00"), Decimal("5.00")),
    "gpt-5.5": (Decimal("5.00"), Decimal("30.00")),
    # Google's paid list price. Priced rather than zeroed because the same model
    # id costs nothing on a free key and real money on a paid one, and the code
    # cannot tell which a deployment holds — so it assumes the expensive case,
    # for the same reason Sonnet uses list price above. A free-tier key
    # over-reports, which is the safe direction.
    "gemini-3.6-flash": (Decimal("1.50"), Decimal("7.50")),
    # Free tiers with no paid equivalent in use: no charge is incurred, so none
    # is recorded.
    "zai-glm-4.7": _ZERO,
    "openai/gpt-oss-120b": _ZERO,
    "openai/gpt-oss-20b": _ZERO,
    "nvidia/nemotron-3-ultra-550b-a55b": _ZERO,
    # An alias, not a model: OpenRouter picks what answers. Priced at zero
    # because only its `:free` variants are routed to, and `token_cost_usd`
    # prices whatever actually served when that id is known.
    "openrouter/free": _ZERO,
}

# Cache reads bill at ~0.1x input; writes at ~1.25x for the 5-minute TTL.
CACHE_READ_MULTIPLIER = Decimal("0.1")
CACHE_WRITE_MULTIPLIER = Decimal("1.25")


class UnknownModelError(ValueError):
    """Cost cannot be attributed for a model with no recorded price."""


def token_cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    price = _PER_MILLION.get(model)
    if price is None:
        raise UnknownModelError(f"No recorded price for model: {model}")
    input_price, output_price = price
    billable_input = (
        Decimal(input_tokens)
        + Decimal(cache_read_tokens) * CACHE_READ_MULTIPLIER
        + Decimal(cache_write_tokens) * CACHE_WRITE_MULTIPLIER
    )
    return (
        billable_input * input_price + Decimal(output_tokens) * output_price
    ) / _MILLION
