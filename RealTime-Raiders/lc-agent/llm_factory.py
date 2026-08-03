"""
llm_factory.py
--------------
Build a LangChain chat model for an AgentConfig. Provider imports stay lazy
so you only need the SDK for providers you actually use.
"""

import os

from config import AgentConfig, PROVIDER_KEYS


def build_llm(cfg):
    """cfg is an AgentConfig or SupervisorConfig — both expose the same fields."""
    key_env = PROVIDER_KEYS.get(cfg.provider)
    api_key = os.getenv(key_env, "") if key_env else ""

    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=cfg.model or "claude-sonnet-4-6",
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=api_key,
        )

    if cfg.provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.model or "openrouter/free",
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    if cfg.provider == "xai":
        # Grok speaks the OpenAI chat-completions schema, so ChatOpenAI with a
        # swapped base_url is the whole integration. Tool calling works, which
        # is what the supervisor needs to reach its specialists.
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.model or "grok-4.5",
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )

    if cfg.provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=cfg.model or "gemini-1.5-flash",
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_tokens,
            google_api_key=api_key,
        )

    raise ValueError(f"Unknown provider: {cfg.provider!r}")
