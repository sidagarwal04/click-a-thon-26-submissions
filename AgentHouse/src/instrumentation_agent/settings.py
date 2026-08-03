"""Settings loaded from repo-root ``.env`` / environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    # Feature packs: {SPECS_ROOT}/{feature_id}/spec.md + events.ndjson
    specs_root: Path = _REPO_ROOT / "specs"

    clickhouse_host: str = ""
    clickhouse_port: int = 8443
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    # Contest / shared warehouse DB (not ClickHouse's built-in `default`).
    clickhouse_database: str = "atlys"
    clickhouse_secure: bool = True

    # Agno reads GOOGLE_API_KEY from the environment; model id is configurable.
    google_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()
