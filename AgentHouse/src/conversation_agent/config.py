"""Load conversation_agent settings from repo-root `.env`."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


# ClickHouse
CLICKHOUSE_HOST = _env("CLICKHOUSE_HOST")
CLICKHOUSE_PORT = _env_int("CLICKHOUSE_PORT", 8443)
CLICKHOUSE_USER = _env("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = _env("CLICKHOUSE_PASSWORD")
CLICKHOUSE_SECURE = _env_bool("CLICKHOUSE_SECURE", True)
CLICKHOUSE_VERIFY = _env_bool("CLICKHOUSE_VERIFY", True)
CLICKHOUSE_DATABASE = _env("CLICKHOUSE_DATABASE", "atlys")
# Single Activity Schema table (envelope + payload JSON)
CLICKHOUSE_ACTIVITY_TABLE = _env("CLICKHOUSE_ACTIVITY_TABLE", "activity_events")
CLICKHOUSE_CONNECT_TIMEOUT = _env_int("CLICKHOUSE_CONNECT_TIMEOUT", 30)
CLICKHOUSE_SEND_RECEIVE_TIMEOUT = _env_int("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", 60)


def activity_table_fqn() -> str:
    """Fully-qualified activity table, e.g. atlys.activity_events."""
    name = CLICKHOUSE_ACTIVITY_TABLE or "activity_events"
    if "." in name:
        return name
    return f"{CLICKHOUSE_DATABASE}.{name}"

# MCP
CLICKHOUSE_MCP_COMMAND = _env(
    "CLICKHOUSE_MCP_COMMAND", "python -m mcp_clickhouse.main"
)
CLICKHOUSE_MCP_TIMEOUT_SECONDS = _env_int("CLICKHOUSE_MCP_TIMEOUT_SECONDS", 90)

# Model — provider: claude | gemini | openai
MODEL_PROVIDER = _env("MODEL_PROVIDER", "claude")
MODEL_ID = _env("MODEL_ID", "claude-sonnet-4-6")
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = _env("GOOGLE_API_KEY")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
# Gemini auth keys (AQ.*) need Vertex Express client: api_key + vertexai=True
GOOGLE_GENAI_USE_VERTEXAI = _env_bool("GOOGLE_GENAI_USE_VERTEXAI", False)
GOOGLE_CLOUD_PROJECT = _env("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = _env("GOOGLE_CLOUD_LOCATION", "us-central1")

# Langfuse (same project as LibreChat; filter UI by environment)
LANGFUSE_ENABLED = _env_bool("LANGFUSE_ENABLED", True)
LANGFUSE_SECRET_KEY = _env("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = _env("LANGFUSE_PUBLIC_KEY")
LANGFUSE_BASE_URL = _env("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
LANGFUSE_TRACING_ENVIRONMENT = _env("LANGFUSE_TRACING_ENVIRONMENT", "agno-dev")

# Optional Postgres
DATABASE_URL = _env("DATABASE_URL")
SESSION_DATABASE_URL = _env("SESSION_DATABASE_URL")

# AgentOS
AGENTOS_ID = _env("AGENTOS_ID", "clickathon-visualization")
AGENTOS_DESCRIPTION = _env(
    "AGENTOS_DESCRIPTION",
    "NL → schema → viz plan → template SQL + ClickHouse (LLM/MCP fallback)",
)
AGENTOS_HOST = _env("AGENTOS_HOST", "0.0.0.0")
AGENTOS_PORT = _env_int("AGENTOS_PORT", 7777)
AGENTOS_DB_PATH = _env("AGENTOS_DB_PATH", "tmp/visualization_agent_os.db")
AGENTOS_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:7777",
    "https://os.agno.com",
]
AGENT_ID = _env("AGENT_ID", "visualization-agent")
AGENT_NAME = _env("AGENT_NAME", "Visualization Agent")
AGENT_HISTORY_RUNS = _env_int("AGENT_HISTORY_RUNS", 3)
WORKFLOW_ID = _env("WORKFLOW_ID", "visualization-agent")

# Workflow artifact paths (relative to conversation_agent/ unless absolute)
_CA_DIR = Path(__file__).resolve().parent
GENERATE_QUERY_SKILL_PATH = _env(
    "GENERATE_QUERY_SKILL_PATH",
    str(_CA_DIR / "skills" / "generate_query.md"),
)

DEFAULT_PROMPT = (
    "Show purchase conversion by device_type for the last 30 days "
    "(uniq users who purchased / uniq users who started an application)."
)

# LibreChat analytics dimensions cache (seconds)
ANALYTICS_CACHE_TTL_SECONDS = _env_int("ANALYTICS_CACHE_TTL_SECONDS", 300)
