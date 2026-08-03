"""Per-model token prices, so cost is right whichever model a run used.

A single global price breaks the moment `LLM_FALLBACK_MODEL` takes over: the
retry runs on a different model and the cost is silently computed at the primary
model's rate. Prices are keyed by model instead, with an env override for
anything not listed.

Figures are the **standard** paid tier from ai.google.dev/gemini-api/docs/pricing,
USD per million tokens. They change; `make check-pricing` prints what is
configured so it can be reconciled against the page.
"""

from __future__ import annotations

from dataclasses import dataclass

# Batch and Flex are half of standard; Priority is 1.8x.
TIER_MULTIPLIERS = {
    "standard": 1.0,
    "batch": 0.5,
    "flex": 0.5,
    "priority": 1.8,
}

# Pro models price long prompts higher. Above this many input tokens the
# `long_*` rates apply.
LONG_PROMPT_THRESHOLD = 200_000


@dataclass(frozen=True)
class ModelPrice:
    """USD per million tokens."""

    input: float
    output: float
    long_input: float | None = None
    long_output: float | None = None

    def rates(self, input_tokens: int) -> tuple[float, float]:
        if input_tokens > LONG_PROMPT_THRESHOLD and self.long_input is not None:
            return self.long_input, self.long_output or self.output
        return self.input, self.output


# Longest key wins, so `gemini-3.5-flash-lite` is not matched by
# `gemini-3.5-flash`.
MODEL_PRICES: dict[str, ModelPrice] = {
    # Flash
    "gemini-3.6-flash": ModelPrice(1.50, 7.50),
    "gemini-3.5-flash": ModelPrice(1.50, 9.00),
    "gemini-3.5-flash-lite": ModelPrice(0.30, 2.50),
    "gemini-3.1-flash-lite": ModelPrice(0.25, 1.50),
    "gemini-2.5-flash": ModelPrice(0.30, 2.50),
    "gemini-2.5-flash-lite": ModelPrice(0.10, 0.40),
    # Pro - tiered on prompt length
    "gemini-3.1-pro": ModelPrice(2.00, 12.00, long_input=4.00, long_output=18.00),
    "gemini-2.5-pro": ModelPrice(1.25, 10.00, long_input=2.50, long_output=15.00),
}


def lookup(model: str) -> ModelPrice | None:
    """Price for a model id, by longest matching prefix."""
    name = (model or "").strip().lower()
    for key in sorted(MODEL_PRICES, key=len, reverse=True):
        if name.startswith(key):
            return MODEL_PRICES[key]
    return None


def cost(
    model: str,
    usage: dict[str, int],
    *,
    tier: str = "standard",
    fallback: ModelPrice | None = None,
) -> dict[str, float]:
    """USD cost for one completion. Empty when the model has no known price."""
    price = lookup(model) or fallback
    if price is None:
        return {}

    input_tokens = usage.get("input", 0)
    output_tokens = usage.get("output", 0)
    in_rate, out_rate = price.rates(input_tokens)
    multiplier = TIER_MULTIPLIERS.get(tier.strip().lower(), 1.0)

    inp = (input_tokens / 1_000_000) * in_rate * multiplier
    out = (output_tokens / 1_000_000) * out_rate * multiplier
    # Langfuse cost_details keys must mirror usage_details keys. Names such as
    # input_cost are accepted as arbitrary custom buckets but are not included
    # in the dashboard's input/output/total USD aggregates.
    return {"input": round(inp, 8), "output": round(out, 8), "total": round(inp + out, 8)}
