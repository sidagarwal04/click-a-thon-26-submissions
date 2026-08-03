from dataclasses import dataclass
from datetime import UTC, datetime
from typing import get_args
from uuid import UUID

from fastapi.testclient import TestClient
from zentra_adapter_postgres import IdentityContext, IdentityNotBoundError
from zentra_application_investigation import (
    AuditDelivery,
    InvestigationDetail,
    PermissionDeniedError,
)
from zentra_domain_agent_execution import (
    ConfidenceOutcome,
    SemanticCatalog,
    SemanticDimension,
    SemanticMeasure,
)
from zentra_domain_investigation import (
    ApprovalDecision,
    DraftFinding,
    EvidenceCitation,
    EvidenceReference,
    Finding,
    InvestigationStatus,
    MetricComparison,
)

from zentra_api.auth import AuthenticationError, ClerkPrincipal
from zentra_api.main import create_app
from zentra_api.settings import Settings


class Probe:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    async def health(self) -> bool:
        return self.healthy


class Verifier:
    async def verify(self, token: str) -> ClerkPrincipal:
        if token != "valid":
            raise AuthenticationError("Invalid bearer token")
        return ClerkPrincipal(subject_id="user_123", organization_id="org_123")


class Engine:
    class Transaction:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *args: object) -> None:
            return None

    def begin(self) -> Transaction:
        return self.Transaction()


@dataclass
class DatabaseProbe(Probe):
    engine: Engine

    def __init__(self, healthy: bool) -> None:
        super().__init__(healthy)
        self.engine = Engine()


class SemanticLayer:
    async def catalog(self) -> SemanticCatalog:
        return SemanticCatalog(
            measures=(
                SemanticMeasure(
                    name="Commerce.refundAmount",
                    type="number",
                    description="Value refunded to customers",
                ),
            ),
            dimensions=(
                SemanticDimension(
                    name="Commerce.region",
                    type="string",
                    values=("EU", "NA"),
                ),
            ),
        )


class SemanticLayers:
    """Stands in for ScopedCubeSemanticLayers. Records what it was asked for,
    because serving one tenant another's catalog is the bug the real one
    exists to prevent."""

    def __init__(self) -> None:
        self.resolved: list[tuple[object, object]] = []

    async def resolve(
        self, *, tenant_id: object, data_connection_id: object
    ) -> SemanticLayer:
        self.resolved.append((tenant_id, data_connection_id))
        return SemanticLayer()


@dataclass
class Dependencies:
    database: DatabaseProbe
    audit: Probe
    cube: Probe
    jwt_verifier: Verifier
    investigations: object | None = None
    organization: object | None = None
    threads: object | None = None
    semantic_layers: object | None = None
    #: No Connector wired: these tests are about the API surface, and a
    #: tenant with no Data Connection asks against the demo warehouse.
    connector: object | None = None

    async def close(self) -> None:
        return None


@dataclass
class LifecycleDependencies(Dependencies):
    started: bool = False
    stopped: bool = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


def client(
    *,
    postgres: bool = True,
    clickhouse: bool = True,
    cube: bool = True,
    investigations: object | None = None,
    organization: object | None = None,
    threads: object | None = None,
    semantic_layers: object | None = None,
) -> TestClient:
    dependencies = Dependencies(
        database=DatabaseProbe(postgres),
        audit=Probe(clickhouse),
        cube=Probe(cube),
        jwt_verifier=Verifier(),
        investigations=investigations,
        organization=organization,
        threads=threads,
        semantic_layers=semantic_layers or SemanticLayers(),
    )
    app = create_app(
        Settings(
            clerk_issuer="https://example.clerk.accounts.dev",
            # `Settings` reads the repository `.env`, so a developer holding a
            # real renderer key would otherwise change what readiness reports
            # here. The harness states the renderer's absence rather than
            # inheriting whatever the machine happens to be configured for.
            thesys_api_key=None,
        ),
        dependencies=dependencies,  # type: ignore[arg-type]
    )
    return TestClient(app)


def test_liveness_never_contacts_dependencies() -> None:
    with client(postgres=False, clickhouse=False, cube=False) as test_client:
        response = test_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_app_lifespan_starts_and_stops_durable_services() -> None:
    dependencies = LifecycleDependencies(
        database=DatabaseProbe(True),
        audit=Probe(True),
        cube=Probe(True),
        jwt_verifier=Verifier(),
    )
    app = create_app(
        Settings(clerk_issuer="https://example.clerk.accounts.dev"),
        dependencies=dependencies,  # type: ignore[arg-type]
    )

    with TestClient(app):
        assert dependencies.started is True
        assert dependencies.stopped is False

    assert dependencies.stopped is True


def test_readiness_reports_sanitized_dependency_state() -> None:
    with client(clickhouse=False) as test_client:
        response = test_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["dependencies"] == {
        "postgres": {"status": "ready"},
        "clickhouse": {"status": "unavailable"},
        "cube": {"status": "ready"},
        "thesys": {"status": "unavailable"},
    }
    assert "password" not in response.text


def test_context_requires_bearer_token() -> None:
    with client() as test_client:
        response = test_client.get("/v1/context")

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token is required"


def test_context_rejects_invalid_bearer_token() -> None:
    with client() as test_client:
        response = test_client.get(
            "/v1/context",
            headers={"Authorization": "Bearer invalid"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"


def test_context_returns_internal_identity(monkeypatch) -> None:
    expected = IdentityContext(
        user_id=UUID("10000000-0000-0000-0000-000000000001"),
        tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
        email="owner@example.com",
        tenant_name="Acme Europe",
        role="owner",
    )

    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return expected

    correlated_tenants = []
    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    monkeypatch.setattr(
        "zentra_api.request_context.correlate_tenant",
        correlated_tenants.append,
    )

    with client() as test_client:
        response = test_client.get(
            "/v1/context",
            headers={
                "Authorization": "Bearer valid",
                "Traceparent": (
                    "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
                ),
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(expected.user_id),
        "tenant_id": str(expected.tenant_id),
        "email": expected.email,
        "tenant_name": expected.tenant_name,
        "role": expected.role,
    }
    assert correlated_tenants == [expected.tenant_id]


def test_context_denies_unbound_organization(monkeypatch) -> None:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        raise IdentityNotBoundError("Identity organization is not bound to a tenant")

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)

    with client() as test_client:
        response = test_client.get(
            "/v1/context",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Identity organization is not bound to a tenant"


def investigation_detail(
    draft_finding: DraftFinding | None = None,
    evidence_citations: tuple[EvidenceCitation, ...] = (),
) -> InvestigationDetail:
    """Defaults to the legacy shape — a narrative Finding and no draft —
    because that is what every Investigation that ran before Insight has."""
    now = datetime(2026, 7, 29, tzinfo=UTC)
    return InvestigationDetail(
        investigation_id=UUID("30000000-0000-0000-0000-000000000003"),
        question="Why did EU refunds increase from June to July 2026?",
        scenario_key=None,
        status=InvestigationStatus.AWAITING_APPROVAL,
        version=5,
        evaluation_attempts=1,
        created_at=now,
        updated_at=now,
        finished_at=None,
        finding=Finding(
            headline="EU refunds rose $240 in July",
            summary="Governed evidence requires review.",
            metrics=(
                MetricComparison(
                    "refund_amount",
                    "20.00",
                    "260.00",
                    "USD",
                    previous_label="June 2026",
                    current_label="July 2026",
                ),
                MetricComparison("refund_rate", "25", "75", "percent"),
            ),
            evidence_refs=(EvidenceReference("artifact://semantic/eu-refunds"),),
        ),
        draft_finding=draft_finding,
        evidence_citations=evidence_citations,
        outcome=ConfidenceOutcome(
            score=0.42,
            calibration_method="evaluator_independent_recheck",
        ),
        pending_approval=None,
        timeline=(),
        audit_delivery=AuditDelivery.COMPLETE,
    )


class InvestigationServiceStub:
    def __init__(self) -> None:
        self.detail = investigation_detail()
        self.last_decision: ApprovalDecision | None = None
        self.execute_calls = 0

    async def start(self, *args: object, **kwargs: object) -> InvestigationDetail:
        return self.detail

    async def get(self, *args: object, **kwargs: object) -> InvestigationDetail:
        return self.detail

    async def execute(self, *args: object, **kwargs: object) -> None:
        self.execute_calls += 1

    async def decide(
        self,
        *args: object,
        decision: ApprovalDecision,
        **kwargs: object,
    ) -> InvestigationDetail:
        self.last_decision = decision
        return self.detail


def test_investigation_create_returns_typed_confidence(monkeypatch) -> None:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="owner@example.com",
            tenant_name="Acme Europe",
            role="owner",
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    service = InvestigationServiceStub()
    with client(investigations=service) as test_client:
        response = test_client.post(
            "/v1/investigations",
            headers={"Authorization": "Bearer valid"},
            json={"question": "Why did EU refunds increase from June to July 2026?"},
        )

    assert response.status_code == 201
    assert service.execute_calls == 0
    assert response.json()["status"] == "awaiting_approval"
    assert response.json()["outcome"] == {
        "kind": "confidence",
        "score": 0.42,
        "calibration_method": "evaluator_independent_recheck",
    }


def test_a_metric_carries_the_periods_it_compares(monkeypatch) -> None:
    """The client cannot derive them and must never guess them, so the response
    is the only place they can come from."""

    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="owner@example.com",
            tenant_name="Acme Europe",
            role="owner",
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    with client(investigations=InvestigationServiceStub()) as test_client:
        response = test_client.post(
            "/v1/investigations",
            headers={"Authorization": "Bearer valid"},
            json={"question": "Why did EU refunds increase from June to July 2026?"},
        )

    dated, undated = response.json()["finding"]["metrics"]
    assert dated["previous_label"] == "June 2026"
    assert dated["current_label"] == "July 2026"
    # A metric with no period to name says so, rather than borrowing one.
    assert undated["previous_label"] is None
    assert undated["current_label"] is None


def test_approval_request_validates_reason_before_service(monkeypatch) -> None:
    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="owner@example.com",
            tenant_name="Acme Europe",
            role="owner",
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    service = InvestigationServiceStub()
    with client(investigations=service) as test_client:
        response = test_client.post(
            (
                "/v1/investigations/30000000-0000-0000-0000-000000000003/"
                "approvals/40000000-0000-0000-0000-000000000004/decision"
            ),
            headers={"Authorization": "Bearer valid"},
            json={"decision": "reject"},
        )

    assert response.status_code == 422
    assert service.last_decision is None


def test_catalog_requires_authentication() -> None:
    with client() as test_client:
        response = test_client.get("/v1/catalog")

    assert response.status_code == 401


def test_the_catalog_served_is_the_asking_tenants_own(
    monkeypatch,
) -> None:
    """The launcher offers whatever this returns.

    It served two hardcoded scenarios before. It now serves the tenant's own
    governed vocabulary, resolved per tenant — the same catalog the Cube
    Analyst reasons over, so a suggestion the UI makes is one the agent can
    actually answer.
    """

    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="owner@example.com",
            tenant_name="Acme Europe",
            role="owner",
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)

    layers = SemanticLayers()
    with client(semantic_layers=layers) as test_client:
        response = test_client.get(
            "/v1/catalog",
            headers={"Authorization": "Bearer valid"},
        )

    assert response.status_code == 200
    body = response.json()
    assert [measure["name"] for measure in body["measures"]] == [
        "Commerce.refundAmount"
    ]
    assert body["measures"][0]["description"] == "Value refunded to customers"
    dimension = body["dimensions"][0]
    assert dimension["name"] == "Commerce.region"
    # Discovered values travel too: an agent, and a suggestion built for one,
    # needs to know the region is spelled "EU" rather than "Europe".
    assert dimension["values"] == ["EU", "NA"]
    assert layers.resolved == [(UUID("20000000-0000-0000-0000-000000000002"), None)]


def test_every_blank_setting_means_unconfigured_not_configured_as_empty() -> None:
    """`CLERK_AUDIENCE=` was the key that bit, but nothing made it special: a
    .env file can leave any of these blank, and each consumer would otherwise
    have to remember `or None` on its own. Asserted over every nullable field so
    a new setting cannot quietly reintroduce the bug."""
    from zentra_api.auth import ClerkJwtVerifier

    nullable = [
        name
        for name, field in Settings.model_fields.items()
        if type(None) in get_args(field.annotation)
    ]
    assert "clerk_audience" in nullable

    settings = Settings(**{name: "" for name in nullable})

    assert [name for name in nullable if getattr(settings, name) is not None] == []
    # The derived objects, not just the fields: this is what actually broke.
    verifier = ClerkJwtVerifier(settings.clerk_issuer, settings.clerk_audience)
    assert verifier._audience is None
    assert all(value is None for value in settings.provider_api_keys().values())


def test_a_blank_required_setting_is_left_alone() -> None:
    """Normalising blanks must not reach fields that have no None to fall back
    to. A blank DATABASE_URL is a misconfiguration, and silently rewriting it
    would hide that."""
    assert Settings(database_url="").database_url == ""


def test_a_blank_audience_means_unconfigured_not_configured_as_empty() -> None:
    """`CLERK_AUDIENCE=` in a .env file parses as "", not None. Treating that as
    a configured audience switches verification on and rejects every valid token
    for missing a claim Clerk was never asked to mint."""
    from zentra_api.auth import ClerkJwtVerifier

    blank = ClerkJwtVerifier("https://example.clerk.accounts.dev", "")
    unset = ClerkJwtVerifier("https://example.clerk.accounts.dev", None)
    configured = ClerkJwtVerifier("https://example.clerk.accounts.dev", "zentra-api")

    assert blank._audience is None
    assert unset._audience is None
    assert configured._audience == "zentra-api"


def test_a_trailing_slash_on_the_issuer_does_not_change_it() -> None:
    from zentra_api.auth import ClerkJwtVerifier

    verifier = ClerkJwtVerifier("https://example.clerk.accounts.dev/", None)

    assert verifier._issuer == "https://example.clerk.accounts.dev"


def test_a_member_cannot_decide_and_is_told_so(monkeypatch) -> None:
    """403, and the body says which membership rule applied without naming the
    Investigation's contents."""

    async def resolve(*args: object, **kwargs: object) -> IdentityContext:
        return IdentityContext(
            user_id=UUID("10000000-0000-0000-0000-000000000001"),
            tenant_id=UUID("20000000-0000-0000-0000-000000000002"),
            email="member@example.com",
            tenant_name="Acme Europe",
            role="member",
        )

    monkeypatch.setattr("zentra_api.request_context.resolve_identity_context", resolve)
    service = InvestigationServiceStub()

    async def deny(*args: object, **kwargs: object):
        raise PermissionDeniedError("This membership cannot decide Human Approvals")

    service.decide = deny  # type: ignore[method-assign]
    with client(investigations=service) as test_client:
        response = test_client.post(
            "/v1/investigations/30000000-0000-0000-0000-000000000003"
            "/approvals/40000000-0000-0000-0000-000000000004/decision",
            headers={"Authorization": "Bearer valid"},
            json={"decision": "approve"},
        )

    assert response.status_code == 403
    body = response.text.lower()
    assert "membership" in body
    # Not the Finding's contents, and not another Tenant's anything.
    assert "refund" not in body
    assert "260.00" not in body
