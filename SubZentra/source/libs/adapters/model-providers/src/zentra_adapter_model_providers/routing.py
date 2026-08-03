from __future__ import annotations

from zentra_domain_agent_execution import AgentRole

from .providers import ModelChoice, ModelTier, Provider

# Free-tier ceilings are set well under the tightest published TPM budget
# (Groq bottoms out at 6K/min on some models), because one investigation makes
# six or more calls. Anthropic has the headroom for real reasoning depth.
_FREE_MAX_TOKENS = 8000
_PAID_MAX_TOKENS = 16000


def _free(
    provider: Provider,
    model: str,
    max_tokens: int = _FREE_MAX_TOKENS,
    *,
    supports_tools: bool = False,
) -> ModelChoice:
    """A free rung. The default is Groq's constraint, not everyone's.

    Overriding matters: a truncated response is a dead rung, and on a chain with
    one reachable provider it is a dead investigation. That happened live —
    Nemotron ran out of room analysing a 300-order result and the run failed
    with every other rung deliberately withheld.
    """
    return ModelChoice(
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        supports_tools=supports_tools,
    )


def _paid(
    provider: Provider, model: str, *, supports_tools: bool = True
) -> ModelChoice:
    return ModelChoice(
        provider=provider,
        model=model,
        max_tokens=_PAID_MAX_TOKENS,
        supports_tools=supports_tools,
    )


# Ordered by measured Artificial Analysis Intelligence Index v4.1, not vendor
# claim: Gemini 3.6 Flash 50 > Nemotron 3 Ultra 38 > GLM-4.7 34 >
# gpt-oss-120b 24; Opus 5 61 > GPT-5.5 55 > Sonnet 5 53. Sonnet 5 still leads
# the premium workhorse chain because it reaches 96% of GPT-5.5's score at
# roughly a third of the blended price.
# `supports_tools` is False despite Gemini supporting tools natively. Verified
# live on 2026-08-02: through the OpenAI-compatible endpoint it accepts the
# first tool turn and then rejects the transcript on the second with
# "Function call is missing a thought_signature in functionCall parts". Gemini 3
# requires its own opaque signature echoed back on every assistant tool turn,
# which the OpenAI wire format has nowhere to carry.
#
# It stays first on every chain for the one-shot structured calls, where it is
# the highest-Index free rung and works perfectly.
_GEMINI_FLASH = _free(Provider.GEMINI, "gemini-3.6-flash")

# Verified 2026-07-29 against the live NIM endpoint: it honours strict
# json_schema with our real QUERY_PLAN_SCHEMA, despite NVIDIA documenting only
# JSON mode. It therefore leads the Evaluator chain — highest free Index after
# Gemini, a different model family from the Analyst's primary, and 40 requests
# per minute against Cerebras's 5.
# NIM does not share Groq's per-minute token budget, so it is not held to it.
# A reasoning model leading the Evaluator chain needs the room: at 8000 it
# truncated on the larger scenario and took the whole investigation with it.
_NVIDIA_NEMOTRON = _free(
    Provider.NVIDIA,
    "nvidia/nemotron-3-ultra-550b-a55b",
    max_tokens=_PAID_MAX_TOKENS,
    supports_tools=True,
)

# Ranks below Groq everywhere despite the higher Index score. Verified live on
# 2026-07-29: the free tier answers 402 until a card is on file, so every call
# to it is a guaranteed wasted round trip. Cerebras also deprecates this model
# on 2026-08-17. Kept as a late rung so a working key still helps, but nothing
# depends on it — fallback would hide its death rather than surface it.
#
# `supports_tools` stays False for that same reason: the 402 means tool support
# has never been *observed* on this account, which is not the same as having
# been found absent, and claiming it would be a guess.
_CEREBRAS_GLM = _free(Provider.CEREBRAS, "zai-glm-4.7")

_GROQ_OSS = _free(Provider.GROQ, "openai/gpt-oss-120b", supports_tools=True)

# An alias, not a model: it resolves to whatever is free today — a live run
# landed on `nvidia/nemotron-nano-9b-v2:free`. No single answer about its tool
# support stays true, so it does not claim any.
#
# Neither this nor Cerebras is a dead rung. Both still serve the one-shot
# structured calls the Orchestrator and Insight make; they are skipped only
# when tools are actually requested, and the skip is recorded in `fallbacks`
# like every other.
_OPENROUTER_FREE = _free(Provider.OPENROUTER, "openrouter/free")

_SONNET = _paid(Provider.ANTHROPIC, "claude-sonnet-5")
_OPUS = _paid(Provider.ANTHROPIC, "claude-opus-5")
_GPT = _paid(Provider.OPENAI, "gpt-5.5")
# Premium-tier light roles (Intake, Evaluator, Insight) lead on this instead of
# Sonnet/Opus — a deliberate speed tradeoff. Measured live: Cube Analyst and
# Evaluator each ran 50-70s per call on a 20-step tool loop, and Evaluator's
# retry (up to 3 attempts) multiplied that further, with Evaluator alone on
# Opus — the single slowest model in this table — despite existing only to
# re-derive a number the Analyst already found, not to reason harder than it.
# Accepted knowingly: this costs the "different model family" independence
# the Evaluator's premium chain used to hold, in exchange for the biggest
# available latency win.
_HAIKU = _paid(Provider.ANTHROPIC, "claude-haiku-4-5-20251001")

# On the free tier, the Evaluator's chain still deliberately starts on a
# different vendor and model family from the Cube Analyst, so the independent
# recheck stays independent without costing anything — free tenants have no
# Haiku rung to trade into. OpenAI is absent from the free chains: at $4.35
# blended it is worse value than falling straight through to Sonnet 5.
ROUTING: dict[ModelTier, dict[AgentRole, tuple[ModelChoice, ...]]] = {
    ModelTier.FREE: {
        # Intake classifies a question against a scoped catalog before any
        # Investigation exists — the same light workload shape as planning,
        # so it inherits the Orchestrator's chain rather than getting its own.
        AgentRole.INTAKE: (
            _GEMINI_FLASH,
            _NVIDIA_NEMOTRON,
            _GROQ_OSS,
            _CEREBRAS_GLM,
            _OPENROUTER_FREE,
            _SONNET,
        ),
        AgentRole.ORCHESTRATOR: (
            _GEMINI_FLASH,
            _NVIDIA_NEMOTRON,
            _GROQ_OSS,
            _CEREBRAS_GLM,
            _OPENROUTER_FREE,
            _SONNET,
        ),
        AgentRole.CUBE_ANALYST: (
            _GEMINI_FLASH,
            _NVIDIA_NEMOTRON,
            _GROQ_OSS,
            _CEREBRAS_GLM,
            _OPENROUTER_FREE,
            _SONNET,
        ),
        AgentRole.EVALUATOR: (
            _NVIDIA_NEMOTRON,
            _GROQ_OSS,
            _CEREBRAS_GLM,
            _GEMINI_FLASH,
            _OPENROUTER_FREE,
            _OPUS,
        ),
        # Insight writes prose over aggregates the Analyst and Evaluator have
        # already validated, so it carries the same workload shape the
        # Orchestrator's synthesis did and inherits its chain. It is not an
        # independence check, so it is under no obligation to lead on a
        # different family from either upstream Agent.
        AgentRole.INSIGHT: (
            _GEMINI_FLASH,
            _NVIDIA_NEMOTRON,
            _GROQ_OSS,
            _CEREBRAS_GLM,
            _OPENROUTER_FREE,
            _SONNET,
        ),
    },
    ModelTier.PREMIUM: {
        # Light roles: classification, recheck, and prose-over-already-
        # validated-data. Fast on purpose — see the `_HAIKU` comment above.
        AgentRole.INTAKE: (_HAIKU, _GPT, _GROQ_OSS, _CEREBRAS_GLM),
        # Important roles: these produce the plan and the actual data-backed
        # figures, so they keep the strongest model.
        AgentRole.ORCHESTRATOR: (_SONNET, _GPT, _GROQ_OSS, _CEREBRAS_GLM),
        AgentRole.CUBE_ANALYST: (_SONNET, _GPT, _GROQ_OSS, _CEREBRAS_GLM),
        AgentRole.EVALUATOR: (_HAIKU, _GPT, _GROQ_OSS, _CEREBRAS_GLM),
        AgentRole.INSIGHT: (_HAIKU, _GPT, _GROQ_OSS, _CEREBRAS_GLM),
    },
}


class TrainingProviderInPaidChainError(RuntimeError):
    """A provider that trains on input reached a premium chain.

    Privacy is what premium tenants are paying for, so this is enforced at
    import rather than left to review.
    """


def _assert_premium_never_trains() -> None:
    for role, chain in ROUTING[ModelTier.PREMIUM].items():
        offenders = [str(choice) for choice in chain if choice.trains_on_input]
        if offenders:
            raise TrainingProviderInPaidChainError(
                f"Premium chain for {role.value} includes providers that train "
                f"on input: {', '.join(offenders)}"
            )


_assert_premium_never_trains()


def chain_for(tier: ModelTier, role: AgentRole) -> tuple[ModelChoice, ...]:
    try:
        return ROUTING[tier][role]
    except KeyError as error:
        raise KeyError(f"No routing chain for {tier.value}/{role.value}") from error
