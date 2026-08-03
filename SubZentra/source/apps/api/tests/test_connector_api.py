"""Request-level tests for the Connector API.

`test_connector_contract.py` asserts the committed OpenAPI document matches the
one the application generates. It never calls a handler, which is how every one
of these routes could raise `AttributeError` while its contract test stayed
green. These go through the router: real request, real authorisation, real
service, in-memory repositories.

Storage itself is covered against Postgres in
`libs/adapters/postgres/tests/test_connector_integration.py`. What is asserted
here is the part only a request can show — status codes, authorisation, and that
no response carries a credential.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from zentra_adapter_postgres import IdentityContext
from zentra_application_connector import ConnectorService, SourceCredentials
from zentra_domain_connector import ConnectionCheck, ConnectionFailure

from zentra_api.auth import AuthenticationError, ClerkPrincipal
from zentra_api.main import create_app
from zentra_api.settings import Settings

OWNER = IdentityContext(
    user_id=UUID("10000000-0000-0000-0000-000000000001"),
    tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
    email="owner@example.com",
    tenant_name="Acme Europe",
    role="owner",
)
OTHER_TENANT = IdentityContext(
    user_id=UUID("10000000-0000-0000-0000-000000000009"),
    tenant_id=UUID("20000000-0000-0000-0000-000000000008"),
    email="stranger@example.com",
    tenant_name="Other Co",
    role="owner",
)
VIEWER = IdentityContext(
    user_id=UUID("10000000-0000-0000-0000-000000000003"),
    tenant_id=OWNER.tenant_id,
    email="viewer@example.com",
    tenant_name="Acme Europe",
    role="viewer",
)

CREDENTIALS = {
    "host": "abc123.ap-south-1.aws.clickhouse.cloud",
    "port": 8443,
    "database": "clickathon",
    "username": "default",
    "password": "s3cr3t-not-a-real-password",
    "secure": True,
}
AUTH = {"Authorization": "Bearer valid", "X-Organization-Id": "org_123"}


class Probe:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    async def health(self) -> bool:
        return self.healthy


class Engine:
    """Just enough of an engine for `request_context` to open a transaction."""

    class Transaction:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *args: object) -> None:
            return None

    def begin(self) -> Transaction:
        return self.Transaction()


class DatabaseProbe(Probe):
    def __init__(self, healthy: bool = True) -> None:
        super().__init__(healthy)
        self.engine = Engine()


class Verifier:
    async def verify(self, token: str) -> ClerkPrincipal:
        if token != "valid":
            raise AuthenticationError("Invalid bearer token")
        return ClerkPrincipal(subject_id="user_123", organization_id="org_123")


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class Cipher:
    """Reversible without being encryption — the real one is tested elsewhere."""

    def seal(self, credentials: SourceCredentials) -> bytes:
        return f"sealed::{credentials.host}".encode()

    def open(self, sealed: bytes) -> SourceCredentials:
        return SourceCredentials(**CREDENTIALS)


class Connector:
    """A source that answers, or refuses in a stated way."""

    def __init__(self, failure: ConnectionFailure | None = None) -> None:
        self.failure = failure

    async def test_connection(self, credentials: SourceCredentials) -> ConnectionCheck:
        if self.failure is not None:
            return ConnectionCheck(reachable=False, failure=self.failure)
        return ConnectionCheck(reachable=True)


class SourceRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, object] = {}

    async def add(self, source) -> None:
        self.rows[source.data_source_id] = source

    async def get(self, data_source_id: UUID, *, tenant_id: UUID):
        found = self.rows.get(data_source_id)
        # Tenant scoping, as RLS gives it in production.
        return found if found is not None and found.tenant_id == tenant_id else None

    async def list(self, *, tenant_id: UUID):
        return [s for s in self.rows.values() if s.tenant_id == tenant_id]

    async def save(self, source) -> None:
        self.rows[source.data_source_id] = source

    async def delete(self, data_source_id: UUID, *, tenant_id: UUID) -> None:
        found = self.rows.get(data_source_id)
        if found is not None and found.tenant_id == tenant_id:
            del self.rows[data_source_id]


class AccessRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str, str | None], object] = {}

    async def upsert(self, override) -> None:
        key = (override.data_source_id, override.table_name, override.field_name)
        self.rows[key] = override

    async def list_for_source(self, data_source_id: UUID, *, tenant_id: UUID):
        return [
            o
            for o in self.rows.values()
            if o.data_source_id == data_source_id and o.tenant_id == tenant_id
        ]


class Unused:
    """The repositories these flows never touch."""

    def __getattr__(self, name: str):
        async def unreachable(*args: object, **kwargs: object):
            raise AssertionError(f"{name} should not be called by these flows")

        return unreachable


@dataclass
class Dependencies:
    database: DatabaseProbe
    audit: Probe
    cube: Probe
    jwt_verifier: Verifier
    connector: ConnectorService | None
    investigations: object | None = None

    async def close(self) -> None:
        return None


def build(
    monkeypatch,
    *,
    identity: IdentityContext = OWNER,
    failure: ConnectionFailure | None = None,
    connector_configured: bool = True,
    sources: SourceRepository | None = None,
    access: AccessRepository | None = None,
) -> tuple[TestClient, SourceRepository]:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return identity

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    monkeypatch.setattr(
        "zentra_api.request_context.correlate_tenant", lambda *_: None
    )

    sources = SourceRepository() if sources is None else sources
    access = AccessRepository() if access is None else access
    service = (
        ConnectorService(
            sources=sources,
            catalogs=Unused(),
            relations=Unused(),
            runs=Unused(),
            access=access,
            connector=Connector(failure),
            cipher=Cipher(),
            landing_zone=Unused(),
            clock=Clock(),
        )
        if connector_configured
        else None
    )
    app = create_app(
        Settings(clerk_issuer="https://example.clerk.accounts.dev"),
        dependencies=Dependencies(
            database=DatabaseProbe(),
            audit=Probe(),
            cube=Probe(),
            jwt_verifier=Verifier(),
            connector=service,
        ),  # type: ignore[arg-type]
    )
    return TestClient(app), sources


def _register(test_client: TestClient, name: str = "Atlys production events"):
    return test_client.post(
        "/v1/connector/sources",
        headers=AUTH,
        json={"name": name, "credentials": CREDENTIALS},
    )


def test_registering_a_source_returns_it_without_any_credential(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        response = _register(test_client)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Atlys production events"
    assert body["health"] == "reachable"
    assert body["kind"] == "connected"
    # The write-only guarantee, asserted over a real response rather than over
    # the schema that describes one.
    assert CREDENTIALS["password"] not in response.text
    assert "password" not in body


def test_a_registered_source_is_then_listed(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        created = _register(test_client).json()
        response = test_client.get("/v1/connector/sources", headers=AUTH)

    assert response.status_code == 200
    listed = response.json()
    assert [s["data_source_id"] for s in listed] == [created["data_source_id"]]
    assert CREDENTIALS["password"] not in response.text


def test_an_unreachable_source_is_refused_and_not_stored(monkeypatch) -> None:
    """Registration verifies first, so a failure must leave nothing behind."""
    test_client, sources = build(
        monkeypatch, failure=ConnectionFailure.AUTHENTICATION_FAILED
    )
    with test_client:
        response = _register(test_client)
        listed = test_client.get("/v1/connector/sources", headers=AUTH).json()

    assert response.status_code == 502
    assert response.json()["detail"] == "authentication_failed"
    assert listed == []
    assert sources.rows == {}


def test_re_testing_a_source_records_what_came_back(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        created = _register(test_client).json()
        response = test_client.post(
            f"/v1/connector/sources/{created['data_source_id']}/test-connection",
            headers=AUTH,
        )

    assert response.status_code == 200
    assert response.json()["health"] == "reachable"
    assert response.json()["last_verified_at"] is not None


def test_a_deleted_source_is_gone(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        created = _register(test_client).json()
        deleted = test_client.delete(
            f"/v1/connector/sources/{created['data_source_id']}", headers=AUTH
        )
        after = test_client.get("/v1/connector/sources", headers=AUTH).json()

    assert deleted.status_code == 204
    assert after == []


def test_a_viewer_may_read_but_not_register(monkeypatch) -> None:
    with build(monkeypatch, identity=VIEWER)[0] as test_client:
        listed = test_client.get("/v1/connector/sources", headers=AUTH)
        created = _register(test_client)

    assert listed.status_code == 200
    assert created.status_code == 403


def test_a_second_tenant_cannot_read_or_delete_the_first_tenants_source(
    monkeypatch,
) -> None:
    """404 rather than 403: "wrong tenant" and "no such thing" must not differ."""
    owner_client, sources = build(monkeypatch)
    with owner_client:
        created = _register(owner_client).json()

    # One store behind both clients, as one database sits behind two tenants.
    stranger_client, _ = build(monkeypatch, identity=OTHER_TENANT, sources=sources)
    with stranger_client:
        read = stranger_client.get(
            f"/v1/connector/sources/{created['data_source_id']}", headers=AUTH
        )
        listed = stranger_client.get("/v1/connector/sources", headers=AUTH)
        removed = stranger_client.delete(
            f"/v1/connector/sources/{created['data_source_id']}", headers=AUTH
        )

    assert read.status_code == 404
    assert listed.json() == []
    assert removed.status_code == 404
    # And the first tenant still has it.
    assert len(sources.rows) == 1


def test_the_connector_says_so_when_it_has_no_credential_key(monkeypatch) -> None:
    """Configuration named, rather than a 500 that reads as a broken service."""
    with build(monkeypatch, connector_configured=False)[0] as test_client:
        response = test_client.get("/v1/connector/sources", headers=AUTH)

    assert response.status_code == 503
    assert "CONNECTOR_CREDENTIAL_KEY" in response.json()["detail"]


def test_connector_routes_require_a_bearer_token(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        response = test_client.get("/v1/connector/sources")

    assert response.status_code == 401


# ------------------------------------------------------------- agent access


def test_an_owner_may_hide_a_table_from_agents(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        created = _register(test_client).json()
        response = test_client.patch(
            f"/v1/connector/sources/{created['data_source_id']}"
            "/tables/customers/agent-access",
            headers=AUTH,
            json={"agent_visible": False},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["table_name"] == "customers"
    assert body["field_name"] is None
    assert body["agent_visible"] is False


def test_an_owner_may_hide_one_field_from_agents(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        created = _register(test_client).json()
        response = test_client.patch(
            f"/v1/connector/sources/{created['data_source_id']}"
            "/tables/customers/fields/email/agent-access",
            headers=AUTH,
            json={"agent_visible": False},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["table_name"] == "customers"
    assert body["field_name"] == "email"
    assert body["agent_visible"] is False


def test_toggling_the_same_table_twice_still_reads_back_as_one_decision(
    monkeypatch,
) -> None:
    test_client, sources = build(monkeypatch)
    with test_client:
        created = _register(test_client).json()
        test_client.patch(
            f"/v1/connector/sources/{created['data_source_id']}"
            "/tables/customers/agent-access",
            headers=AUTH,
            json={"agent_visible": False},
        )
        second = test_client.patch(
            f"/v1/connector/sources/{created['data_source_id']}"
            "/tables/customers/agent-access",
            headers=AUTH,
            json={"agent_visible": True},
        )

    assert second.status_code == 200
    assert second.json()["agent_visible"] is True


def test_a_viewer_cannot_toggle_agent_access(monkeypatch) -> None:
    owner_client, sources = build(monkeypatch)
    with owner_client:
        created = _register(owner_client).json()

    viewer_client, _ = build(monkeypatch, identity=VIEWER, sources=sources)
    with viewer_client:
        response = viewer_client.patch(
            f"/v1/connector/sources/{created['data_source_id']}"
            "/tables/customers/agent-access",
            headers=AUTH,
            json={"agent_visible": False},
        )

    assert response.status_code == 403


def test_toggling_access_on_an_unknown_source_is_a_404(monkeypatch) -> None:
    with build(monkeypatch)[0] as test_client:
        response = test_client.patch(
            f"/v1/connector/sources/{uuid4()}/tables/customers/agent-access",
            headers=AUTH,
            json={"agent_visible": False},
        )

    assert response.status_code == 404
