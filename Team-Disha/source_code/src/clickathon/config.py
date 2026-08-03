"""Application settings loaded from environment / `.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ClickHouse Cloud
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8443
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_secure: bool = True
    clickhouse_database: str = "default"
    # Analytical copies (never mutate default for RCA)
    clickhouse_rca_database: str = "eda"

    # Langfuse Cloud
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    # Azure OpenAI (Foundry) — OpenAI-compatible
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-5.6-sol"
    azure_openai_api_key: str = ""
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.6-sol"

    # ClickStack OTel (collector auth uses HyperDX team API key)
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "clickathon-rca"
    hyperdx_api_key: str = ""

    @property
    def llm_base_url(self) -> str:
        return self.openai_base_url or self.azure_openai_endpoint

    @property
    def llm_api_key(self) -> str:
        return self.openai_api_key or self.azure_openai_api_key

    @property
    def llm_model(self) -> str:
        return self.openai_model or self.azure_openai_deployment


@lru_cache
def get_settings() -> Settings:
    return Settings()
