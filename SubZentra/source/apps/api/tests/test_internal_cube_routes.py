"""The internal endpoint Cube's Node process calls — not tenant-facing.

Covers the three failure/success shapes that matter: no internal secret
configured (503), a wrong or missing credential (403), and no ConnectorService
wired (501, not an AttributeError) — plus the one success path, since the
governance content itself (only confirmed Relations ever appear) is already
covered end to end in test_connector_model.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi.testclient import TestClient

from zentra_api.main import create_app
from zentra_api.settings import Settings

TENANT_ID = uuid4()
DATA_CONNECTION_ID = uuid4()
PATH = f"/internal/v1/cube/model/{TENANT_ID}/{DATA_CONNECTION_ID}"


class Probe:
    async def health(self) -> bool:
        return True


@dataclass
class Dependencies:
    database: object
    audit: object
    cube: object
    jwt_verifier: object
    connector: object | None = None
    investigations: object | None = None
    organization: object | None = None

    async def close(self) -> None:
        return None


def _client(*, internal_secret: str | None, connector: object | None) -> TestClient:
    dependencies = Dependencies(
        database=Probe(), audit=Probe(), cube=Probe(), jwt_verifier=Probe(),
        connector=connector,
    )
    settings = Settings(
        clerk_issuer="https://example.clerk.accounts.dev",
        cube_internal_api_secret=internal_secret,
    )
    app = create_app(settings, dependencies=dependencies)  # type: ignore[arg-type]
    return TestClient(app)


def test_missing_internal_secret_configuration_refuses_every_caller() -> None:
    with _client(internal_secret=None, connector=None) as client:
        response = client.get(PATH, headers={"Authorization": "Bearer anything"})

    assert response.status_code == 503


def test_wrong_credential_is_rejected() -> None:
    with _client(internal_secret="right", connector=None) as client:
        response = client.get(PATH, headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 403


def test_missing_credential_is_rejected() -> None:
    with _client(internal_secret="right", connector=None) as client:
        response = client.get(PATH)

    assert response.status_code == 403


def test_unconfigured_connector_fails_with_501_not_an_attribute_error() -> None:
    with _client(internal_secret="right", connector=None) as client:
        response = client.get(PATH, headers={"Authorization": "Bearer right"})

    assert response.status_code == 501


def test_configured_connector_returns_the_confirmed_model() -> None:
    from .test_connector_model import _connector

    with _client(
        internal_secret="right", connector=_connector(pending_relation=True)
    ) as client:
        response = client.get(PATH, headers={"Authorization": "Bearer right"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["joins"]) == 1
    assert body["clickhouse"]["password"] == "secret"
