from __future__ import annotations

from decimal import Decimal

import pytest
from zentra_domain_agent_execution import AgentRole

from zentra_adapter_model_providers import (
    PROVIDERS,
    ROUTING,
    ModelTier,
    Provider,
    UnknownModelError,
    chain_for,
    model_family,
    token_cost_usd,
)
from zentra_adapter_model_providers.openai_compatible import _cost


def test_no_premium_chain_touches_a_provider_that_trains_on_input() -> None:
    """Privacy is what premium tenants are buying, so this is enforced rather
    than left to review. `routing` also asserts it at import."""
    for role, chain in ROUTING[ModelTier.PREMIUM].items():
        offenders = [str(choice) for choice in chain if choice.trains_on_input]
        assert not offenders, f"{role.value} would leak to {offenders}"


def test_free_evaluator_starts_on_a_different_family_from_the_analyst() -> None:
    analyst = ROUTING[ModelTier.FREE][AgentRole.CUBE_ANALYST][0]
    evaluator = ROUTING[ModelTier.FREE][AgentRole.EVALUATOR][0]

    assert model_family(analyst.model) != model_family(evaluator.model)
    assert analyst.provider is not evaluator.provider


def test_every_free_chain_leads_with_a_schema_verified_provider() -> None:
    """A chain may only lead with a provider whose strict json_schema support
    has been confirmed against its live endpoint. Leading with an unverified one
    puts a retry-and-fall-through on every investigation's critical path."""
    verified = {Provider.GEMINI, Provider.NVIDIA, Provider.GROQ, Provider.ANTHROPIC}
    for role, chain in ROUTING[ModelTier.FREE].items():
        assert chain[0].provider in verified, (
            f"{role.value} leads with a provider of unconfirmed schema support"
        )


def test_premium_important_roles_lead_with_sonnet() -> None:
    """Orchestrator and Cube Analyst produce the plan and the actual
    data-backed figures, so they keep the strongest model."""
    for role in (AgentRole.ORCHESTRATOR, AgentRole.CUBE_ANALYST):
        assert ROUTING[ModelTier.PREMIUM][role][0].model == "claude-sonnet-5"


def test_premium_light_roles_lead_with_a_fast_model() -> None:
    """Intake, Evaluator, and Insight are classification, recheck, and prose
    over already-validated data — lighter workloads than planning or querying.

    Evaluator in particular used to lead with Opus for a different-model-
    family independence guarantee; measured live, that made it the single
    slowest step in the pipeline (an independent recheck, not "reason harder
    than the Analyst"). A deliberate speed tradeoff moved it to Haiku instead.
    """
    for role in (AgentRole.INTAKE, AgentRole.EVALUATOR, AgentRole.INSIGHT):
        assert (
            ROUTING[ModelTier.PREMIUM][role][0].model
            == "claude-haiku-4-5-20251001"
        )


def test_the_canonical_insight_role_routes_on_both_tiers() -> None:
    """A role the registry can hold but the router cannot resolve is a
    KeyError waiting for the first investigation that reaches it."""
    for tier in ModelTier:
        assert chain_for(tier, AgentRole.INSIGHT)


def test_the_legacy_insight_role_has_no_chain() -> None:
    """Routing is a write path. Nothing new may run under the legacy value."""
    for tier in ModelTier:
        with pytest.raises(KeyError):
            chain_for(tier, AgentRole.INSIGHT_ROOT_CAUSE)


def test_every_chain_ends_on_anthropic() -> None:
    """Anthropic is the backstop: no chain may exhaust into nothing."""
    for tier, roles in ROUTING.items():
        for role, chain in roles.items():
            assert chain, f"{tier.value}/{role.value} has no rungs"
            providers = {choice.provider for choice in chain}
            assert Provider.ANTHROPIC in providers, f"{tier.value}/{role.value}"


def test_every_routed_model_has_a_recorded_price() -> None:
    for roles in ROUTING.values():
        for chain in roles.values():
            for choice in chain:
                token_cost_usd(choice.model, input_tokens=1, output_tokens=1)


def test_unpriced_model_fails_loudly_rather_than_recording_zero() -> None:
    with pytest.raises(UnknownModelError):
        token_cost_usd("some-new-model", input_tokens=1, output_tokens=1)


def test_free_tier_models_record_genuinely_zero_cost() -> None:
    cost = token_cost_usd("zai-glm-4.7", input_tokens=100_000, output_tokens=50_000)

    assert cost == 0


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-sonnet-5", "claude"),
        ("groq/openai/gpt-oss-120b", "gpt-oss"),
        ("cerebras/zai-glm-4.7", "glm"),
        ("gemini/gemini-3.6-flash", "gemini"),
        ("nvidia/nemotron-3-ultra", "nemotron"),
        ("nvidia/nemotron-3-ultra-550b-a55b:free", "nemotron"),
        ("gpt-5.5", "gpt-5"),
        (None, None),
    ],
)
def test_model_family_reduces_to_shared_blind_spots(
    model: str | None,
    expected: str | None,
) -> None:
    assert model_family(model) == expected


def test_only_anthropic_uses_a_native_sdk() -> None:
    """Everything else speaks the OpenAI wire format, which is why one client
    covers five providers."""
    for provider, config in PROVIDERS.items():
        if provider is Provider.ANTHROPIC:
            assert config.base_url is None
        else:
            assert config.base_url is not None


def test_a_paid_gemini_key_is_priced_rather_than_recorded_as_free() -> None:
    """The same id costs nothing on a free key and real money on a paid one.
    The code cannot tell which a deployment holds, so it assumes the expensive
    case — the ledger over-reporting is survivable, silently spending is not."""
    cost = token_cost_usd(
        "gemini-3.6-flash", input_tokens=1_000_000, output_tokens=1_000_000
    )

    assert cost == Decimal("9.00")


def test_pricing_follows_the_model_that_answered_not_the_alias_asked_for() -> None:
    """`openrouter/free` is an alias; a live run resolved it to a Nemotron
    variant. Pricing the alias records the alias's cost for another model."""
    served = _cost(
        served="claude-opus-5",
        requested="openrouter/free",
        input_tokens=1_000_000,
        output_tokens=0,
        cache_read_tokens=0,
    )

    assert served == Decimal("5.00")


def test_an_unpriced_served_model_falls_back_to_the_requested_one() -> None:
    """OpenRouter can serve anything. A cost lookup must not fail a call that
    already succeeded, so an unknown served id falls back rather than raising."""
    cost = _cost(
        served="some-model-openrouter-picked-today",
        requested="openrouter/free",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=0,
    )

    assert cost == Decimal("0")


def test_both_ids_unpriced_still_fails_loudly() -> None:
    with pytest.raises(UnknownModelError):
        _cost(
            served="mystery-a",
            requested="mystery-b",
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
        )


def test_a_rung_is_not_held_to_another_providers_token_budget() -> None:
    """The 8000 default is Groq's constraint. NIM does not share it, and a
    reasoning model leading the Evaluator chain needs the room — at 8000 it
    truncated on the 300-order scenario and killed the whole investigation."""
    evaluator = ROUTING[ModelTier.FREE][AgentRole.EVALUATOR]
    nemotron = next(c for c in evaluator if c.provider is Provider.NVIDIA)
    groq = next(c for c in evaluator if c.provider is Provider.GROQ)

    assert nemotron.max_tokens > groq.max_tokens
