from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single config source for RCA/app/ — every env var the app reads lives here, nowhere
    else. Real environment variables still win over the .env file (pydantic-settings'
    default precedence), so RCA/tests/conftest.py forcing keys empty stays hermetic."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )

    clickhouse_host: str
    # Repo .env uses CLICKHOUSE_HTTPS_PORT (ClickHouse Cloud); accept either name.
    clickhouse_http_port: int = Field(
        validation_alias=AliasChoices("CLICKHOUSE_HTTP_PORT", "CLICKHOUSE_HTTPS_PORT"),
    )
    clickhouse_user: str
    clickhouse_password: str

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str | None = None

    # Where persist_report() writes — docs/RCA_UI_TEMPLATE.md Step 2 (Option A). Default
    # matches local dev (RCA/app runs on the host); Docker overrides via RCA_REPORTS_DIR
    # to the shared volume mounted into rca-api (docker-compose.yml).
    rca_reports_dir: Path = Path(__file__).resolve().parents[2] / "data" / "rca_reports"

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
