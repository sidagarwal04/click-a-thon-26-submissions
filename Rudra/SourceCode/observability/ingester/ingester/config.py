"""
Central configuration for the ingester toolkit.

All settings come from environment variables (loaded from a local `.env`).
Nothing is hard-coded so the same code runs against a local ClickHouse or
ClickHouse Cloud just by changing `.env`.
"""

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

# Load the .env from the running app's directory (cwd upward), NOT the package's
# own directory — so each service picks up its own .env.
load_dotenv(find_dotenv(usecwd=True))


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str
    port: int
    username: str
    password: str
    database: str
    secure: bool


@dataclass(frozen=True)
class TelemetryConfig:
    enabled: bool
    service_name: str
    service_version: str
    environment: str
    endpoint: str
    protocol: str
    headers: str
    metric_interval_ms: int


@dataclass(frozen=True)
class Settings:
    clickhouse: ClickHouseConfig
    telemetry: TelemetryConfig


def _load() -> Settings:
    return Settings(
        clickhouse=ClickHouseConfig(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            # clickhouse-connect speaks HTTP: use 8123 (plain) or 8443 (secure),
            # NOT the native 9000 port.
            port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DATABASE", "sonyliv"),
            secure=_bool(os.getenv("CLICKHOUSE_SECURE"), False),
        ),
        telemetry=TelemetryConfig(
            enabled=_bool(os.getenv("TELEMETRY_ENABLED"), True),
            service_name=os.getenv("OTEL_SERVICE_NAME", "frontrow-pipeline"),
            service_version=os.getenv("SERVICE_VERSION", "0.1.0"),
            environment=os.getenv("ENVIRONMENT", "dev"),
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
            protocol=os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
            headers=os.getenv("OTEL_EXPORTER_OTLP_HEADERS", ""),
            metric_interval_ms=int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "10000")),
        ),
    )


_settings = None


def get_settings(reload=False) -> Settings:
    """Return the process-wide Settings (cached; pass reload=True to re-read env)."""
    global _settings
    if _settings is None or reload:
        _settings = _load()
    return _settings
