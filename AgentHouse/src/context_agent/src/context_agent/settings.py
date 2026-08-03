"""Settings for the Context Agent (loaded from repo-root .env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """Locate repo-root `.env` even when the package is installed into site-packages."""
    starts = [Path.cwd(), Path(__file__).resolve().parent]
    seen: set[Path] = set()
    for start in starts:
        for base in [start, *start.parents]:
            if base in seen:
                continue
            seen.add(base)
            env = base / ".env"
            if env.is_file():
                return env
            # Prefer the project root even if `.env` is not created yet (clearer errors).
            if (base / "pyproject.toml").is_file() and (base / "context_agent").is_dir():
                return env if env.is_file() else None
    return None


_ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="Postgres URL for meta_* + context_* catalog.",
    )
    session_database_url: str | None = Field(
        default=None,
        alias="SESSION_DATABASE_URL",
        description="Optional. For other Agno agents' session DB; unused by this library.",
    )
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        hint = (
            "Set DATABASE_URL in the environment or create a repo-root `.env` "
            "(copy from `.env.example`)."
        )
        raise RuntimeError(hint) from exc
