"""Request-level tests for the row-browse endpoint.

Follows `test_connector_api.py`'s fakes: real request, real authorisation,
real service, in-memory repositories — plus two fakes this endpoint alone
needs, since nothing else in the suite reaches Cube through a route.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
from zentra_adapter_cube import CubeSemanticLayer
from zentra_adapter_postgres import IdentityContext
from zentra_application_connector import ConnectorService
from zentra_domain_connector import CatalogVersion, SourceField, SourceTable

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

AUTH = {"Authorization": "Bearer valid", "X-Organization-Id": "org_123"}

DATA_SOURCE_ID = uuid4()


class Probe:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    async def health(self) -> bool:
        return self.healthy


class Engine:
    class Transaction:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *args: object) -> None:
            return None

    def begin(self) -> Engine.Transaction:
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


def _field(name: str, *, position: int) -> SourceField:
    return SourceField(
        field_id=uuid4(),
        table_id=uuid4(),
        name=name,
        declared_type="string",
        family="string",
        normalised_type="string",
        nullable=True,
        position=position,
    )


ORDERS_TABLE = SourceTable(
    table_id=uuid4(),
    name="orders",
    database="db",
    fields=(
        _field("id", position=0),
        _field("status", position=1),
        _field("total", position=2),
    ),
)


class SourceRepository:
    """Just enough of a data-source store for `_load_source` to find one."""

    def __init__(self, *, tenant_id: UUID = OWNER.tenant_id) -> None:
        self.tenant_id = tenant_id

    async def get(self, data_source_id: UUID, *, tenant_id: UUID):
        if data_source_id != DATA_SOURCE_ID or tenant_id != self.tenant_id:
            return None

        @dataclass
        class Source:
            data_source_id: UUID
            tenant_id: UUID

        return Source(data_source_id=data_source_id, tenant_id=tenant_id)


class CatalogRepository:
    """Holds at most one Catalog Version, for the one data source above."""

    def __init__(
        self, version: CatalogVersion | None, *, tenant_id: UUID = OWNER.tenant_id
    ) -> None:
        self.version = version
        self.tenant_id = tenant_id

    async def latest_version(self, data_source_id: UUID, *, tenant_id: UUID):
        if tenant_id != self.tenant_id or self.version is None:
            return None
        if self.version.data_source_id != data_source_id:
            return None
        return self.version

    async def get_version(self, catalog_version_id: UUID, *, tenant_id: UUID):
        raise AssertionError("not used by the rows route")


class Unused:
    def __getattr__(self, name: str):
        async def unreachable(*args: object, **kwargs: object):
            raise AssertionError(f"{name} should not be called by these flows")

        return unreachable


def _catalog_version(tenant_id: UUID = OWNER.tenant_id) -> CatalogVersion:
    return CatalogVersion(
        catalog_version_id=uuid4(),
        data_source_id=DATA_SOURCE_ID,
        tenant_id=tenant_id,
        harvest_run_id=uuid4(),
        created_at=datetime.now(UTC),
        tables=(ORDERS_TABLE,),
    )


class FakeCubeClient:
    """The network boundary only — records every query it is asked to run."""

    def __init__(
        self, payload: dict | None = None, error: Exception | None = None
    ) -> None:
        self.payload = payload
        self.error = error
        self.queries: list[dict] = []

    async def load(self, query: dict) -> dict:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.payload

    async def meta(self) -> dict:
        return {"cubes": []}


class FakeScopedCubeSemanticLayers:
    """Fakes at the `ScopedCubeSemanticLayers` boundary — `resolve()` is the
    only method the route touches."""

    def __init__(self, semantic_layer: CubeSemanticLayer) -> None:
        self._semantic_layer = semantic_layer

    async def resolve(self, *, tenant_id: UUID, data_connection_id: UUID | None):
        return self._semantic_layer


@dataclass
class Dependencies:
    database: DatabaseProbe
    audit: Probe
    cube: Probe
    jwt_verifier: Verifier
    connector: ConnectorService | None
    cube_semantic_layers: FakeScopedCubeSemanticLayers | None = None
    investigations: object | None = None

    async def close(self) -> None:
        return None


_DEFAULT_VERSION = object()


def build(
    monkeypatch,
    *,
    identity: IdentityContext = OWNER,
    catalog_version: CatalogVersion | None = _DEFAULT_VERSION,  # type: ignore[assignment]
    cube_client: FakeCubeClient | None = None,
) -> tuple[TestClient, FakeCubeClient]:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return identity

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    monkeypatch.setattr(
        "zentra_api.request_context.correlate_tenant", lambda *_: None
    )

    version = (
        _catalog_version() if catalog_version is _DEFAULT_VERSION else catalog_version
    )
    service = ConnectorService(
        sources=SourceRepository(),
        catalogs=CatalogRepository(version),
        relations=Unused(),
        runs=Unused(),
        access=Unused(),
        connector=Unused(),
        cipher=Unused(),
        landing_zone=Unused(),
        clock=Clock(),
    )
    fake_cube_client = cube_client or FakeCubeClient(
        payload={"data": [], "total": 0}
    )
    semantic_layers = FakeScopedCubeSemanticLayers(
        CubeSemanticLayer(fake_cube_client)
    )
    app = create_app(
        Settings(clerk_issuer="https://example.clerk.accounts.dev"),
        dependencies=Dependencies(
            database=DatabaseProbe(),
            audit=Probe(),
            cube=Probe(),
            jwt_verifier=Verifier(),
            connector=service,
            cube_semantic_layers=semantic_layers,
        ),  # type: ignore[arg-type]
    )
    return TestClient(app), fake_cube_client


def _rows_url(page: int | None = None) -> str:
    url = f"/v1/connector/sources/{DATA_SOURCE_ID}/tables/orders/rows"
    return f"{url}?page={page}" if page is not None else url


def test_page_one_returns_rows_in_catalog_field_order(monkeypatch) -> None:
    payload = {
        "data": [
            {"orders.id": "1", "orders.status": "paid", "orders.total": "42.00"},
            {"orders.id": "2", "orders.status": "pending", "orders.total": "10.50"},
        ],
        "total": 120,
    }
    test_client, cube_client = build(monkeypatch, cube_client=FakeCubeClient(payload))

    with test_client:
        response = test_client.get(_rows_url(), headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ["id", "status", "total"]
    assert body["rows"] == [["1", "paid", "42.00"], ["2", "pending", "10.50"]]
    assert body["total"] == 120
    assert body["page"] == 1
    assert body["page_size"] == 50


def test_pagination_sends_the_right_offset_to_cube(monkeypatch) -> None:
    test_client, cube_client = build(monkeypatch)

    with test_client:
        response = test_client.get(_rows_url(page=2), headers=AUTH)

    assert response.status_code == 200
    assert cube_client.queries[0]["offset"] == 50
    assert cube_client.queries[0]["limit"] == 50
    assert "measures" not in cube_client.queries[0]


def test_a_source_that_was_never_harvested_is_not_ready(monkeypatch) -> None:
    test_client, cube_client = build(monkeypatch, catalog_version=None)

    with test_client:
        response = test_client.get(_rows_url(), headers=AUTH)

    assert response.status_code == 404
    assert cube_client.queries == []


def test_an_unknown_table_name_is_not_ready_and_cube_is_never_queried(
    monkeypatch,
) -> None:
    test_client, cube_client = build(monkeypatch)

    with test_client:
        response = test_client.get(
            f"/v1/connector/sources/{DATA_SOURCE_ID}/tables/does-not-exist/rows",
            headers=AUTH,
        )

    assert response.status_code == 404
    assert cube_client.queries == []


def test_cube_unreachable_is_a_503_with_a_generic_message(monkeypatch) -> None:
    test_client, cube_client = build(
        monkeypatch,
        cube_client=FakeCubeClient(error=httpx.ConnectError("refused")),
    )

    with test_client:
        response = test_client.get(_rows_url(), headers=AUTH)

    assert response.status_code == 503
    assert "refused" not in response.text
    assert "syncing" in response.json()["detail"]


def test_a_second_tenant_gets_a_404_not_the_first_tenants_rows(monkeypatch) -> None:
    test_client, cube_client = build(monkeypatch, identity=OTHER_TENANT)

    with test_client:
        response = test_client.get(_rows_url(), headers=AUTH)

    assert response.status_code == 404
    assert cube_client.queries == []


def test_a_viewer_can_browse_rows_same_as_an_owner(monkeypatch) -> None:
    """A read, unlike the agent-access toggles — no role gate."""
    test_client, cube_client = build(monkeypatch, identity=VIEWER)

    with test_client:
        response = test_client.get(_rows_url(), headers=AUTH)

    assert response.status_code == 200
