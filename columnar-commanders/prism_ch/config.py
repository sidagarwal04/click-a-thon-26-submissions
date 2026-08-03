"""Runtime configuration, read from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=False)


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    user: str
    password: str
    cluster: str
    secure: bool
    connect_timeout: int
    http_host: str
    http_port: int
    log_level: str
    # Defaulted so callers that predate tracing still construct cleanly.
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = "pk-lf-prism-dev"
    langfuse_secret_key: str = "sk-lf-prism-dev"
    tracing_enabled: bool = True
    # 'cloud' (SharedMergeTree, no ON CLUSTER) or 'cluster' (local compose).
    clickhouse_target: str = "cluster"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-5"
    llm_fallback_model: str = ""
    llm_max_retries: int = 4
    llm_max_tokens: int = 16000
    ddl_repair_attempts: int = 2
    table_prefix: str = "prism_"
    # Overrides for a model not in prism_ch.pricing, USD per million tokens.
    # Known models are priced from that table, so a fallback model is costed at
    # its own rate rather than the primary's.
    llm_price_input: float = 0.0
    llm_price_output: float = 0.0
    # standard | batch | flex | priority
    llm_price_tier: str = "standard"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8002
    mcp_transport: str = "streamable-http"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=_env("CLICKHOUSE_HOST", "localhost"),
            port=int(_env("CLICKHOUSE_PORT", "8123")),
            database=_env("CLICKHOUSE_DB", "prism"),
            user=_env("CLICKHOUSE_USER", "prism"),
            password=_env("CLICKHOUSE_PASSWORD", "prism"),
            cluster=_env("CLICKHOUSE_CLUSTER", "click_agents"),
            secure=_env("CLICKHOUSE_SECURE", "false").lower() in {"1", "true", "yes"},
            connect_timeout=int(_env("CLICKHOUSE_CONNECT_TIMEOUT", "10")),
            http_host=_env("APP_HOST", "0.0.0.0"),
            # Railway injects PORT. APP_PORT remains the explicit override used
            # by Docker Compose and local development.
            http_port=int(_env("APP_PORT", _env("PORT", "8000"))),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            langfuse_host=_env("LANGFUSE_HOST", "http://localhost:3000"),
            langfuse_public_key=_env("LANGFUSE_PUBLIC_KEY", "pk-lf-prism-dev"),
            langfuse_secret_key=_env("LANGFUSE_SECRET_KEY", "sk-lf-prism-dev"),
            tracing_enabled=_env("LANGFUSE_TRACING_ENABLED", "true").lower()
            in {"1", "true", "yes"},
            clickhouse_target=_env("CLICKHOUSE_TARGET", "cluster").lower(),
            llm_provider=_env("LLM_PROVIDER", "anthropic").lower(),
            llm_model=_env("LLM_MODEL", "claude-opus-5"),
            llm_fallback_model=_env("LLM_FALLBACK_MODEL", ""),
            llm_max_retries=int(_env("LLM_MAX_RETRIES", "4")),
            llm_max_tokens=int(_env("LLM_MAX_TOKENS", "16000")),
            ddl_repair_attempts=int(_env("DDL_REPAIR_ATTEMPTS", "2")),
            table_prefix=_env("TABLE_PREFIX", "prism_"),
            llm_price_input=float(_env("LLM_PRICE_INPUT_PER_M", "0") or 0),
            llm_price_output=float(_env("LLM_PRICE_OUTPUT_PER_M", "0") or 0),
            llm_price_tier=_env("LLM_PRICE_TIER", "standard").lower(),
            anthropic_api_key=_env("ANTHROPIC_API_KEY", ""),
            openai_api_key=_env("OPENAI_API_KEY", ""),
            google_api_key=_env("GOOGLE_API_KEY", "") or _env("GEMINI_API_KEY", ""),
            mcp_host=_env("PRISM_MCP_HOST", "0.0.0.0"),
            mcp_port=int(_env("PRISM_MCP_PORT", "8002")),
            mcp_transport=_env("PRISM_MCP_TRANSPORT", "streamable-http"),
        )

    def cost_details(self, usage: dict[str, int], model: str | None = None) -> dict[str, float]:
        """USD cost for a completion, priced for the model that actually ran."""
        from .pricing import ModelPrice, cost

        override = (
            ModelPrice(self.llm_price_input, self.llm_price_output)
            if (self.llm_price_input or self.llm_price_output)
            else None
        )
        return cost(
            model or self.llm_model,
            usage,
            tier=self.llm_price_tier,
            fallback=override,
        )

    @property
    def llm_enabled(self) -> bool:
        """True when the configured provider has a usable key."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider in ("gemini", "google"):
            return bool(self.google_api_key)
        return False

    @property
    def dsn(self) -> str:
        """Connection string with the password redacted - safe to log."""
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.user}:***@{self.host}:{self.port}/{self.database}"
