"""The two latency decisions in the LLM layer, pinned so a later edit cannot undo them
silently: the thinking level actually reaches the request, and the provider (and so its
connection pool) is built once rather than per call.

No network here. GeminiProvider's constructor builds a client object but issues no
request, and nothing below calls generate().
"""

import pytest

from engine.config import LLMProvider, Settings, settings
from engine.llm import get_provider

genai = pytest.importorskip("google.genai")


def _provider(level: str):
    from engine.llm.gemini_provider import GeminiProvider

    return GeminiProvider(api_key="not-a-real-key", model="gemini-3.5-flash",
                          thinking_level=level, max_output_tokens=512)


def test_thinking_level_reaches_the_request_config():
    """The measured difference between a 21.9s narration and a 1.4s one is exactly this
    field being present."""
    cfg = _provider("low")._config("system", with_thinking=True)

    assert cfg.thinking_config is not None
    # The SDK coerces the string into its own ThinkingLevel enum.
    assert str(cfg.thinking_config.thinking_level.value).lower() == "low"
    assert cfg.max_output_tokens == 512
    assert cfg.temperature == 0


def test_the_output_cap_is_dropped_whenever_thinking_is_not_constrained():
    """Thinking tokens come out of max_output_tokens, so capping output while letting
    thinking run free spends the budget before the answer starts -- observed as a
    narration cut off mid-word ("...falling from 698,274"). A truncated answer is worse
    than a slow one because it still reads like an answer."""
    assert _provider("default")._config("s", with_thinking=True).max_output_tokens is None
    assert _provider("low")._config("s", with_thinking=False).max_output_tokens is None
    assert _provider("low")._config("s", with_thinking=True).max_output_tokens == 512


def test_an_unrecognised_level_degrades_instead_of_breaking_narration():
    """A mistyped GEMINI_THINKING_LEVEL must not surface as "narration unavailable".
    The SDK validates the level, and that validation would otherwise fire inside
    generate() where the failure reads as a broken model rather than a bad setting."""
    p = _provider("fastest-possible")

    assert p._thinking_level == "default"
    assert p._config("system", with_thinking=True).thinking_config is None


def test_default_sentinel_sends_no_thinking_config():
    """GEMINI_THINKING_LEVEL=default must restore the model's own behaviour from the
    environment, without a code change."""
    assert _provider("default")._config("system", with_thinking=True).thinking_config is None


def test_thinking_is_dropped_on_the_fallback_path():
    """A model that rejects `thinking_level` (the 2.5 generation wants
    `thinking_budget`) must degrade to today's behaviour, not to a failed narration."""
    p = _provider("low")
    assert p._config("system", with_thinking=False).thinking_config is None

    assert p._is_thinking_rejection(ValueError("thinking_level is not supported for this model"))
    # Anything that is not about the thinking knob must propagate untouched, or a bad
    # key would be retried as though it were a capability problem.
    assert not p._is_thinking_rejection(ValueError("API key not valid"))
    assert not p._is_thinking_rejection(ValueError("429 quota exceeded"))


def test_provider_is_cached_per_configuration():
    """narrate() and ask() both call get_provider() on EVERY call. Without caching,
    each narration and each chat turn built a fresh client and paid a fresh TLS
    handshake to the provider."""
    assert get_provider(settings) is get_provider(settings)


def test_a_changed_setting_yields_a_different_provider():
    """The cache must key on what would change the constructed client, or a settings
    change would silently keep using a provider built from the old configuration."""
    base = Settings(llm_provider=LLMProvider.stub)
    changed = Settings(llm_provider=LLMProvider.stub, llm_max_output_tokens=settings.llm_max_output_tokens + 1)

    assert get_provider(base) is get_provider(base)
    assert get_provider(base) is not get_provider(changed)


# ---------------------------------------------------------------------------
# An empty response is a FAILED narration, not an available one.
#
# Observed on a real incident: two consecutive calls returned finish_reason=STOP with no
# thinking tokens and either None or a bare '\n', then the identical payload succeeded with
# 234 output tokens. So an empty text part is transient here. Two separate defects fell out
# of it -- the provider gave up on it, and narrator.py reported it as a successful
# narration, persisting narration_available=1 beside a 1-character narration that the
# console renders as an empty explanation claiming to be one.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text, finish="STOP"):
        self.text = text
        self.candidates = [type("C", (), {"finish_reason": type("F", (), {"name": finish})()})()]


class _FakeModels:
    """Returns each queued response in turn and counts the calls."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate_content(self, **_kwargs):
        self.calls += 1
        return self._responses.pop(0) if self._responses else _FakeResponse("fallback")


def _with_fake(provider, responses):
    provider._client = type("C", (), {"models": _FakeModels(responses)})()
    return provider._client.models


def test_an_empty_response_is_retried_once_and_the_retry_is_used():
    p = _provider("low")
    models = _with_fake(p, [_FakeResponse("\n"), _FakeResponse("the real answer")])

    assert p.generate("system", "user") == "the real answer"
    assert models.calls == 2, "an empty text part must be retried exactly once"


def test_a_good_response_is_never_retried():
    """The retry must not double the cost of every ordinary narration."""
    p = _provider("low")
    models = _with_fake(p, [_FakeResponse("first answer"), _FakeResponse("second")])

    assert p.generate("system", "user") == "first answer"
    assert models.calls == 1


def test_max_tokens_truncation_is_not_retried():
    """That is the thinking-budget trap in _config(), not a transient: the model spent the
    whole cap before answering, and an identical request would spend it again. Retrying
    would only hide a configuration problem behind doubled latency."""
    p = _provider("low")
    models = _with_fake(p, [_FakeResponse("", finish="MAX_TOKENS"), _FakeResponse("unused")])

    p.generate("system", "user")
    assert models.calls == 1


def test_a_persistently_empty_provider_yields_empty_rather_than_looping():
    """One retry, not a loop -- narration is on the interactive path, so a provider that
    genuinely returns nothing has to surface quickly as 'narration unavailable'."""
    p = _provider("low")
    models = _with_fake(p, [_FakeResponse(None), _FakeResponse("   ")])

    assert not (p.generate("system", "user") or "").strip()
    assert models.calls == 2


def test_narrate_reports_an_empty_response_as_unavailable():
    """`available=True` used to be unconditional on "no exception raised", so an empty
    answer was persisted as a real narration. The guardrail this module exists to enforce
    is that a failure is explicit -- never an empty box the reader has to interpret."""
    from engine import narrator

    class _Empty:
        def generate(self, _system, _user):
            return "\n"

    original = narrator.get_provider
    narrator.get_provider = lambda _settings: _Empty()
    try:
        class _Evidence:
            def to_llm_json(self):
                return {"metric": "revenue"}

        result = narrator.narrate(_Evidence())
    finally:
        narrator.get_provider = original

    assert result.available is False
    assert result.narration is None
    assert "empty" in (result.error or "").lower()
