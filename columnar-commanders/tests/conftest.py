from __future__ import annotations

from typing import Any

import pytest

from prism_ch.config import Settings

_DEFAULTS: dict[str, Any] = {
    "host": "localhost",
    "port": 8123,
    "database": "prism",
    "user": "prism",
    "password": "prism",
    "cluster": "click_agents",
    "secure": False,
    "connect_timeout": 10,
    "http_host": "0.0.0.0",
    "http_port": 8000,
    "log_level": "INFO",
    "langfuse_host": "http://localhost:3000",
    "langfuse_public_key": "pk-lf-test",
    "langfuse_secret_key": "sk-lf-test",
    "tracing_enabled": True,
}


@pytest.fixture
def make_settings():  # noqa: ANN201 - pytest fixture factory
    """Build a Settings with overrides, independent of the environment."""

    def _make(**overrides: Any) -> Settings:
        return Settings(**{**_DEFAULTS, **overrides})

    return _make
