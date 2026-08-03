"""Environment configuration → immutable Settings dataclass.

The pipeline is deterministic-first (D6): it must run with *no* external keys.
Langfuse keys are optional — their absence selects the NullTracer.
There is deliberately **no LLM config in the pipeline**: FastAPI agents make zero LLM
calls. The `zai_api_key` / `librechat_*` fields are only used by the chat proxy layer
(`api.py POST /api/proxy/chat`) and the agent-provisioning bootstrap script.

`.env` support: if `Atlys/.env` exists it is loaded at import time (KEY=VALUE
lines; never overrides variables already set in the real environment). This is
dependency-free — no python-dotenv required. `CH_HOST` may be a bare hostname
(`myhost.clickhouse.cloud`) *or* a full URL (`https://myhost…:8443/`); the
scheme then sets `ch_secure` unless `CH_SECURE` is set explicitly.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _load_dotenv(path: Path) -> None:
    """Dependency-free .env loader: KEY=VALUE lines into os.environ (no override)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):  # tolerate `export KEY=value` lines
            key = key[len("export "):].strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_root() -> Path:
    raw = _env("ATLYS_ROOT")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


def _resolve_ch() -> tuple[str | None, bool]:
    """CH_HOST may be 'host', 'host:port', or 'https://host:port/' → (host, secure).

    The scheme (https) implies secure; an explicit CH_SECURE wins over it.
    """
    raw = _env("CH_HOST")
    if not raw:
        return None, _env_bool("CH_SECURE", False)
    raw = raw.strip().rstrip("/")
    secure = _env_bool("CH_SECURE", False)
    m = re.match(r"^([a-z]+)://", raw, re.I)
    if m:
        scheme = m.group(1).lower()
        if _env("CH_SECURE") is None:  # only infer from scheme when not explicit
            secure = scheme == "https"
        raw = raw[m.end():]
    return raw, secure


# Load Atlys/.env once, before any Settings() is constructed.
_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Parsed once: URL-form CH_HOST (scheme/port/trailing-slash) → bare host.
_CH_HOST, _CH_SECURE = _resolve_ch()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, all sourced from environment variables."""

    # ClickHouse (D3 — the only datastore)
    ch_host: str | None = _CH_HOST
    ch_user: str = field(default_factory=lambda: _env("CH_USER", "default") or "default")
    ch_password: str | None = field(default_factory=lambda: _env("CH_PASSWORD"))
    ch_secure: bool = _CH_SECURE
    atlys_db: str = field(default_factory=lambda: _env("ATLYS_DB", "atlys") or "atlys")

    # Langfuse (D2/D14) — optional; absent → NullTracer
    langfuse_pk: str | None = field(default_factory=lambda: _env("LANGFUSE_PUBLIC_KEY"))
    langfuse_sk: str | None = field(default_factory=lambda: _env("LANGFUSE_SECRET_KEY"))
    langfuse_base_url: str | None = field(
        default_factory=lambda: _env("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
    )
    langfuse_project_id: str | None = field(
        default_factory=lambda: _env("LANGFUSE_PROJECT_ID")
    )


    # LibreChat proxy + agent provisioning (D1 / D12)
    # ZAI_API_KEY is also consumed by LibreChat's librechat.yaml; mirrored here so
    # the provision script and proxy can use it without a separate env var.
    librechat_url: str = field(
        default_factory=lambda: _env("LIBRECHAT_URL", "http://localhost:3080") or "http://localhost:3080"
    )
    librechat_admin_email: str | None = field(
        default_factory=lambda: _env("LIBRECHAT_ADMIN_EMAIL")
    )
    librechat_admin_password: str | None = field(
        default_factory=lambda: _env("LIBRECHAT_ADMIN_PASSWORD")
    )
    # Agents API key for POST /api/agents/v1/chat/completions (not a login JWT).
    # Written by provision_agent.py; can also be forced via LIBRECHAT_API_KEY.
    librechat_api_key: str | None = field(
        default_factory=lambda: _env("LIBRECHAT_API_KEY")
    )
    # agent_id is written to .atlys_agent_id by provision_agent.py and read back here.
    # Can also be forced via env var ATLYS_AGENT_ID (useful in Docker).
    atlys_agent_id: str | None = field(
        default_factory=lambda: _env("ATLYS_AGENT_ID")
    )

    # Behaviour
    dry_run: bool = field(default_factory=lambda: _env_bool("ATLYS_DRY_RUN", False))
    approve_automatically: bool = field(
        default_factory=lambda: _env_bool("ATLYS_AUTO_APPROVE", False)
    )
    # Max MCP tool calls per user-initiated chat series (auto-continues share it).
    # User can say "continue" to start a fresh allowance.
    max_tool_calls_per_series: int = field(
        default_factory=lambda: max(1, _env_int("ATLYS_MAX_TOOL_CALLS_PER_SERIES", 50))
    )
    # Max events persisted per spec run before the bus aborts the run (flood guard).
    # Keyed on payload.run_id / trace_id — see bus.py. tool.called events are exempt.
    max_events_per_run: int = field(
        default_factory=lambda: max(1, _env_int("ATLYS_MAX_EVENTS_PER_RUN", 200))
    )

    # Paths (defaults assume the repo layout Atlys/service → Atlys)
    atlys_root: Path = field(default_factory=_resolve_root)

    @property
    def specs_dir(self) -> Path:
        return self.atlys_root / "specs"

    @property
    def generated_dir(self) -> Path:
        return self.atlys_root / "generated"

    @property
    def base_context_path(self) -> Path:
        return self.atlys_root / "base_context.md"

    @property
    def has_langfuse(self) -> bool:
        return bool(self.langfuse_pk and self.langfuse_sk)

    @property
    def agent_id_path(self) -> Path:
        """Path to the persisted agent_id file written by provision_agent.py."""
        return self.generated_dir / ".atlys_agent_id"

    @property
    def librechat_api_key_path(self) -> Path:
        """Path to the persisted Agents API key written by provision_agent.py."""
        return self.generated_dir / ".atlys_librechat_api_key"

    def load_agent_id(self) -> str | None:
        """Return agent_id: env var wins, else read from .atlys_agent_id file."""
        if self.atlys_agent_id:
            return self.atlys_agent_id
        if self.agent_id_path.exists():
            return self.agent_id_path.read_text().strip() or None
        return None

    def load_librechat_api_key(self) -> str | None:
        """Return Agents API key: env var wins, else read persisted file."""
        if self.librechat_api_key:
            return self.librechat_api_key
        if self.librechat_api_key_path.exists():
            return self.librechat_api_key_path.read_text().strip() or None
        return None

    def summary(self) -> dict:
        return {
            "ch_host": self.ch_host,
            "ch_secure": self.ch_secure,
            "atlys_db": self.atlys_db,
            "dry_run": self.dry_run,
            "langfuse": "configured" if self.has_langfuse else "null-tracer",
            "specs_dir": str(self.specs_dir),
            "agent_provisioned": self.load_agent_id() is not None,
            "librechat_api_key": self.load_librechat_api_key() is not None,
        }
