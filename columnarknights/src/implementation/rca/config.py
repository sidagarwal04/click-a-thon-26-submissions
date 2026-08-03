import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# Load .env from the project root (implementation/, one level up from this
# package), not from whatever directory the process happens to be launched
# from — dotenv_values() with no path only checks the current working
# directory, which silently finds nothing if `rca` is invoked from elsewhere.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Values from this project's own .env take priority over whatever is already
# in the ambient shell environment (rather than dotenv's usual default of
# "don't override an existing env var"). This matters concretely here: some
# dev environments (e.g. a Claude Code session) already export an
# ANTHROPIC_API_KEY of their own, which would otherwise silently shadow the
# project-specific key a user pastes into .env.
_dotenv = dotenv_values(_ENV_PATH)


def _get(key: str, default: str = "") -> str:
    val = _dotenv.get(key)
    return val if val else os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    clickhouse_host: str = _get("CLICKHOUSE_HOST", "localhost")
    clickhouse_port: int = int(_get("CLICKHOUSE_PORT", "8123"))
    clickhouse_user: str = _get("CLICKHOUSE_USER", "default")
    clickhouse_password: str = _get("CLICKHOUSE_PASSWORD", "")
    clickhouse_database: str = _get("CLICKHOUSE_DATABASE", "inmobi")
    clickhouse_secure: bool = _get("CLICKHOUSE_SECURE", "true").lower() == "true"

    gemini_api_key: str = _get("GEMINI_API_KEY", "")
    gemini_model: str = _get("GEMINI_MODEL", "gemini-flash-lite-latest")
    # Hard ceiling on the one LLM call in the pipeline. Measured free-tier
    # rate-limit retries can otherwise push this stage's tail latency to
    # ~80s (see rca/latency.py); past this many seconds, narrate() gives up
    # and returns a deterministic, template-based summary instead -- every
    # number in it already existed before the LLM was ever called, so the
    # diagnosis is never blocked on the one non-deterministic dependency.
    narrate_timeout_seconds: float = float(_get("NARRATE_TIMEOUT_SECONDS", "8"))

    langfuse_public_key: str = _get("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = _get("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = _get("LANGFUSE_HOST", "https://cloud.langfuse.com")

    librechat_base_url: str = _get("LIBRECHAT_BASE_URL", "http://localhost:3080")
    librechat_followup_agent_id: str = _get("LIBRECHAT_FOLLOWUP_AGENT_ID", "")

    # Live monitor: how often it polls fact_events' row count, and how many
    # continuous seconds of an unchanged count count as "ingestion has gone
    # quiet" -- the only signal that triggers an automatic scan+investigate.
    # There is no explicit "batch done" flag from the loader; this idle
    # window is the entire detection mechanism (see rca/live_monitor.py).
    live_poll_seconds: float = float(_get("LIVE_POLL_SECONDS", "2"))
    live_idle_seconds: float = float(_get("LIVE_IDLE_SECONDS", "10"))


settings = Settings()
