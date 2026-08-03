from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AliasChoices,
    AnyUrl,
    BeforeValidator,
    EmailStr,
    Field,
    HttpUrl,
    SecretStr,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FEATURE_ROOT = PROJECT_ROOT / "incoming_features"


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Local overrides are intentionally untracked so secrets never need to
        # be added to the template's checked-in .env file.
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.local"),
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None

    # ClickHouse is configured lazily by the repository so the API can still
    # start in environments that do not use the analytics pipeline.
    CLICKHOUSE_HOST: str | None = None
    CLICKHOUSE_PORT: int = Field(default=8443, ge=1, le=65535)
    CLICKHOUSE_USERNAME: str = Field(
        default="default",
        validation_alias=AliasChoices("CLICKHOUSE_USERNAME", "CLICKHOUSE_USER"),
    )
    CLICKHOUSE_PASSWORD: SecretStr | None = None
    CLICKHOUSE_DATABASE: str = Field(default="atlys", min_length=1)
    CLICKHOUSE_SECURE: bool = True
    CLICKHOUSE_CONNECT_TIMEOUT: int = Field(default=10, gt=0)
    CLICKHOUSE_QUERY_TIMEOUT: int = Field(default=30, gt=0)

    FEATURE_ROOT: Path = DEFAULT_FEATURE_ROOT
    FEATURE_MAX_SPEC_BYTES: int = Field(default=256 * 1024, gt=0)
    FEATURE_MAX_EVENT_FILE_BYTES: int = Field(default=512 * 1024 * 1024, gt=0)
    FEATURE_MAX_EVENT_LINE_BYTES: int = Field(default=1024 * 1024, gt=0)
    FEATURE_CARDINALITY_SAMPLE_SIZE: int = Field(default=1024, ge=2)

    LANGFUSE_TRACING_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: SecretStr | None = None
    LANGFUSE_BASE_URL: HttpUrl | None = None

    # Loaded now so the transport-independent agent stages can use Fireworks
    # without reading environment variables directly.
    FIREWORKS_API_KEY: SecretStr | None = None
    FIREWORKS_MODEL: str = "accounts/fireworks/models/gpt-oss-120b"
    FIREWORKS_BASE_URL: HttpUrl = HttpUrl("https://api.fireworks.ai/inference/v1")
    FIREWORKS_TIMEOUT: int = Field(default=120, gt=0)
    ASKLYS_MODEL: str = "accounts/fireworks/models/deepseek-v4-pro"
    ASKLYS_MAX_QUERY_ATTEMPTS: int = Field(default=5, ge=1, le=5)

    MCP_TRANSPORT: Literal["stdio", "streamable-http"] = "stdio"
    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = Field(default=8001, ge=1, le=65535)

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)


settings = Settings()  # type: ignore
