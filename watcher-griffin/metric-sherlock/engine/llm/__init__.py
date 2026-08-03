"""Pluggable LLM providers for engine/narrator.py and engine/chat.py -- the ONLY
two places in this codebase allowed to call an LLM. Provider choice is
config-driven (LLM_PROVIDER env var) so switching between Gemini/Anthropic/
OpenAI/Grok never touches the guardrail logic, only which adapter it talks to.

Providers are CACHED per (provider, model, thinking level, output cap). Each one
owns an HTTP client with its own connection pool, and both callers ask for a
provider on every single call -- so without this, every narration and every chat
turn built a fresh client and paid a fresh TLS handshake to the provider. The
Gemini adapter's own docstring already promised "one client, reused across
calls"; this is the layer that was quietly breaking that promise.
"""

import threading

from engine.config import LLMProvider, Settings, settings
from engine.llm.base import LLMProviderBase

_cache: dict = {}
_lock = threading.Lock()


def _cache_key(cfg: Settings) -> tuple:
    """Everything that would change the constructed client. A settings change in a
    test (or a future per-request override) must yield a different provider rather
    than silently reusing one built from the old configuration."""
    return (
        cfg.llm_provider,
        cfg.gemini_model, cfg.anthropic_model, cfg.openai_model, cfg.grok_model,
        cfg.grok_base_url, cfg.gemini_thinking_level, cfg.llm_max_output_tokens,
    )


def _build_provider(cfg: Settings) -> LLMProviderBase:
    if cfg.llm_provider == LLMProvider.gemini:
        from engine.llm.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=cfg.gemini_api_key, model=cfg.gemini_model,
            thinking_level=cfg.gemini_thinking_level,
            max_output_tokens=cfg.llm_max_output_tokens,
        )
    if cfg.llm_provider == LLMProvider.anthropic:
        from engine.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model,
                                 max_output_tokens=cfg.llm_max_output_tokens)
    if cfg.llm_provider == LLMProvider.openai:
        from engine.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=cfg.openai_api_key, model=cfg.openai_model,
                              max_output_tokens=cfg.llm_max_output_tokens)
    if cfg.llm_provider == LLMProvider.grok:
        from engine.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=cfg.grok_api_key, model=cfg.grok_model,
                              base_url=cfg.grok_base_url,
                              max_output_tokens=cfg.llm_max_output_tokens)
    from engine.llm.stub_provider import StubProvider

    return StubProvider()


def get_provider(cfg: Settings = settings) -> LLMProviderBase:
    key = _cache_key(cfg)
    provider = _cache.get(key)
    if provider is not None:
        return provider
    with _lock:
        # Re-check inside the lock: two concurrent API workers asking at once must
        # end up sharing one provider, not racing to replace each other's.
        provider = _cache.get(key)
        if provider is None:
            # Construction can raise (a missing API key does), and that must stay a
            # per-call error the caller degrades on -- so nothing is cached here.
            provider = _build_provider(cfg)
            _cache[key] = provider
    return provider
