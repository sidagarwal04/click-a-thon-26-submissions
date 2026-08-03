from __future__ import annotations

import pytest

from prism_ch.config import Settings

ENV_KEYS = (
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_PORT",
    "APP_PORT",
    "PORT",
    "CLICKHOUSE_DB",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
    "CLICKHOUSE_CLUSTER",
    "CLICKHOUSE_SECURE",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults(clean_env: None) -> None:
    settings = Settings.from_env()
    assert settings.cluster == "click_agents"
    assert settings.database == "prism"
    assert settings.port == 8123


def test_env_overrides(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLICKHOUSE_HOST", "clickhouse")
    monkeypatch.setenv("CLICKHOUSE_CLUSTER", "click_agents_prod")
    settings = Settings.from_env()
    assert settings.host == "clickhouse"
    assert settings.cluster == "click_agents_prod"


def test_railway_port_is_used_when_app_port_is_unset(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", "4312")
    assert Settings.from_env().http_port == 4312


def test_app_port_overrides_railway_port(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", "4312")
    monkeypatch.setenv("APP_PORT", "8000")
    assert Settings.from_env().http_port == 8000


def test_empty_string_falls_back_to_default(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Compose passes through empty values for unset variables; they must not win.
    monkeypatch.setenv("CLICKHOUSE_HOST", "")
    assert Settings.from_env().host == "localhost"


def test_dsn_redacts_the_password(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "hunter2")
    dsn = Settings.from_env().dsn
    assert "hunter2" not in dsn
    assert "***" in dsn
