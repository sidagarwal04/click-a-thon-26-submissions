"""
Configuration utilities for Atlys agents.
Loads .env files and provides typed access to settings.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ClickHouseConfig:
    """ClickHouse connection configuration."""
    host: str
    port: int = 8443
    user: str = "default"
    password: str = ""
    database: str = "atlys"
    secure: bool = True
    
    @classmethod
    def from_env(cls) -> "ClickHouseConfig":
        """Load config from environment variables."""
        return cls(
            host=os.getenv("CLICKHOUSE_HOST", ""),
            port=int(os.getenv("CLICKHOUSE_PORT", "8443")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "atlys"),
            secure=os.getenv("CLICKHOUSE_SECURE", "true").lower() == "true",
        )
    
    def validate(self) -> list[str]:
        """Validate required fields."""
        errors = []
        if not self.host:
            errors.append("CLICKHOUSE_HOST is required")
        if not self.password:
            errors.append("CLICKHOUSE_PASSWORD is required")
        return errors


@dataclass
class LangfuseConfig:
    """Langfuse tracing configuration."""
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> "LangfuseConfig":
        """Load config from environment variables."""
        host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
        return cls(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            host=host,
            enabled=bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")),
        )


@dataclass
class OpenRouterConfig:
    """OpenRouter LLM configuration."""
    api_key: str = ""
    model: str = "openrouter/free"
    base_url: str = "https://openrouter.ai/api/v1"
    enabled: bool = True
    
    @classmethod
    def from_env(cls) -> "OpenRouterConfig":
        """Load config from environment variables."""
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        return cls(
            api_key=api_key,
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            enabled=bool(api_key),
        )

    def get_client(self):
        """Get an OpenAI-compatible client for OpenRouter."""
        if not self.enabled:
            raise ValueError("OpenRouter not configured (missing API key)")
        try:
            from openai import OpenAI
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
                max_retries=1,
            )
        except ImportError:
            raise ImportError("openai package required: pip install openai")


# ---------------------------------------------------------------------------
# Anthropic -- a direct, non-OpenRouter LLM provider. Every call site in this
# codebase (InstrumentationAgent, AnalyticsAgent, ContextAgent's llm_call_fn)
# was written against an OpenAI-shaped client: `client.chat.completions.create(
# model=..., messages=[...], temperature=..., max_tokens=..., response_format=...)`
# returning `.choices[0].message.content`. Rather than touch every call site,
# AnthropicConfig.get_client() returns an adapter that exposes that exact same
# surface but calls the real Anthropic Messages API underneath -- so it's a
# drop-in replacement for OpenRouterConfig anywhere one is threaded through.
# ---------------------------------------------------------------------------

class _AnthropicMessage:
    def __init__(self, content: str):
        self.content = content


class _AnthropicChoice:
    def __init__(self, content: str):
        self.message = _AnthropicMessage(content)


class _AnthropicResponse:
    def __init__(self, content: str):
        self.choices = [_AnthropicChoice(content)]


class _AnthropicChatCompletions:
    def __init__(self, anthropic_client):
        self._client = anthropic_client

    def create(self, model, messages, temperature: float = 0.1, max_tokens: int = 2000,
               response_format: Optional[dict] = None, **_ignored):
        """Translates one OpenAI-shaped chat.completions.create() call into an
        Anthropic messages.create() call and wraps the reply back into an
        OpenAI-shaped response object."""
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        user_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages if m.get("role") != "system"
        ]
        system = "\n\n".join(system_parts) if system_parts else None

        if response_format and response_format.get("type") == "json_object":
            # Claude has no forced-JSON response mode like OpenAI's
            # response_format param -- every call site's own prompt text
            # already asks for JSON-only output, so just reinforce it.
            json_instruction = "\n\nRespond with ONLY valid JSON. No markdown fences, no prose, no explanation."
            system = (system or "") + json_instruction

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": user_messages,
        }
        if system:
            payload["system"] = system

        # `temperature` and `thinking` are best-effort extras, stripped on a
        # per-param 400 and retried:
        # - `temperature`: current Claude models (e.g. claude-sonnet-5) reject
        #   it outright ("`temperature` is deprecated for this model", HTTP 400)
        #   rather than ignoring it.
        # - `thinking: disabled`: extended thinking defaults ON for some Claude
        #   models and eats into max_tokens as hidden reasoning tokens --
        #   observed live: a 2000-token budget spent 1602 tokens thinking,
        #   leaving too little for the actual JSON this call wants (truncated/
        #   empty output). None of this codebase's call sites want visible
        #   reasoning, so disable it; older models that don't recognize the
        #   param fall back the same way.
        extra = {"temperature": temperature, "thinking": {"type": "disabled"}}
        while True:
            try:
                response = self._client.messages.create(**payload, **extra)
                break
            except Exception as e:
                msg = str(e).lower()
                stripped = [k for k in list(extra) if k.lower() in msg]
                if not stripped:
                    raise
                for k in stripped:
                    del extra[k]
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return _AnthropicResponse(text)


class _AnthropicChat:
    def __init__(self, anthropic_client):
        self.completions = _AnthropicChatCompletions(anthropic_client)


class _AnthropicOpenAICompatClient:
    """Duck-types an OpenAI client -- exposes `.chat.completions.create(...)` --
    backed by the real `anthropic` SDK."""
    def __init__(self, anthropic_client):
        self.chat = _AnthropicChat(anthropic_client)


@dataclass
class AnthropicConfig:
    """Direct Anthropic API configuration. Exposes the same (enabled, model,
    get_client()) shape as OpenRouterConfig, so it can be passed anywhere an
    *_config object is threaded through (InstrumentationAgent, AnalyticsAgent,
    make_llm_call_fn) without changing those call sites."""
    api_key: str = ""
    # Haiku 4.5, not one of the Claude 5 reasoning models -- every call site
    # here is a bounded structured-output task (schema JSON, SQL text, insight
    # JSON), not open-ended reasoning, so the cheaper/faster/lower-token model
    # is the better default. Override with ANTHROPIC_MODEL.
    model: str = "claude-haiku-4-5-20251001"
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "AnthropicConfig":
        """Load config from environment variables."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        return cls(
            api_key=api_key,
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            enabled=bool(api_key),
        )

    def get_client(self):
        """Get an OpenAI-compatible client backed by the Anthropic API."""
        if not self.enabled:
            raise ValueError("Anthropic not configured (missing API key)")
        try:
            import anthropic
            return _AnthropicOpenAICompatClient(anthropic.Anthropic(api_key=self.api_key))
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")


def make_llm_call_fn(openrouter_config: "OpenRouterConfig"):
    """
    Build a (prompt, span_name) -> str callable backed by OpenRouter, matching the
    contract ContextAgent (and audit_base_context.run_audit) expect. Traces every
    call through the shared TracingAgent so context-audit/update/resolve calls show
    up in Langfuse alongside the Instrumentation/Analytics LLM calls.
    """
    if not openrouter_config or not openrouter_config.enabled:
        raise ValueError("OpenRouter not configured (missing OPENROUTER_API_KEY)")

    client = openrouter_config.get_client()

    def llm_call_fn(prompt: str, span_name: str = "context_llm_call") -> str:
        from agents.tracing.agent import get_tracer

        tracer = get_tracer()
        with tracer.trace_span(span_name, input_data={"prompt": prompt[:2000]}):
            response = client.chat.completions.create(
                model=openrouter_config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
            )
            completion = (response.choices[0].message.content or "").strip()
            tracer.log_generation(
                name=span_name,
                model=openrouter_config.model,
                prompt=prompt,
                completion=completion,
            )
            return completion

    return llm_call_fn


def load_dotenv(env_path: Optional[Path] = None) -> bool:
    """
    Load environment variables from .env file.
    Returns True if loaded, False if file not found.
    """
    if env_path is None:
        # Search from cwd and from this package so running from repo root still works.
        search_roots = [Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent]
        seen = set()
        for root in search_roots:
            for parent in [root] + list(root.parents):
                if parent in seen:
                    continue
                seen.add(parent)
                env_file = parent / ".env"
                if env_file.exists():
                    env_path = env_file
                    break
            if env_path is not None:
                break
    
    if env_path is None or not env_path.exists():
        return False
    
    try:
        # Try python-dotenv first
        from dotenv import load_dotenv as _load_dotenv
        _load_dotenv(env_path, override=False)
        return True
    except ImportError:
        # Fallback: simple parser
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
        return True


def get_config() -> tuple[ClickHouseConfig, LangfuseConfig, "OpenRouterConfig | AnthropicConfig"]:
    """Load all configs from environment.

    The third element used to always be OpenRouterConfig -- now it's whichever
    LLM provider is actually configured, preferring Anthropic (ANTHROPIC_API_KEY)
    over OpenRouter (OPENROUTER_API_KEY) when both are set, since OpenRouter's
    shared free-tier model rate-limits/returns empty responses under load (seen
    live: schema-generation and context-audit calls failing with "Expecting
    value: line 1 column 1"). Every caller (InstrumentationAgent, AnalyticsAgent,
    make_llm_call_fn) only relies on the duck-typed (.enabled, .model,
    .get_client()) shape both classes share, so nothing downstream needs to
    change based on which provider this resolves to.
    """
    # Try to load .env
    load_dotenv()

    ch_config = ClickHouseConfig.from_env()
    lf_config = LangfuseConfig.from_env()

    # --- Original behavior: OpenRouter only. Kept, not deleted. ---
    # or_config = OpenRouterConfig.from_env()
    # return ch_config, lf_config, or_config

    # --- Current behavior: prefer Anthropic when configured. ---
    anthropic_config = AnthropicConfig.from_env()
    or_config = OpenRouterConfig.from_env()
    llm_config = anthropic_config if anthropic_config.enabled else or_config

    return ch_config, lf_config, llm_config
