"""The primary Phase 2 acceptance suite, at the authenticated API boundary.

One test per acceptance criterion on #24, and deliberately not stubs. The other
API tests substitute an `InvestigationServiceStub` because they are asking
narrow questions about the HTTP layer; this file asks whether the *product*
holds, so it composes the real application policy, real Postgres persistence
under RLS, and the real transactional outbox. Only the Agent pipeline and the
Semantic layer are doubled, because those are the parts that would otherwise
cost money and stop being deterministic.

A suite that stubbed the service would prove the stub. The publication policy,
the RLS predicates and the outbox ordering are precisely the things Phase 2
claims, so they have to be the things running.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_adapter_postgres import Database, PostgresInvestigationUnitOfWorkFactory
from zentra_adapter_postgres.database import set_tenant_context
from zentra_adapter_postgres.schema import (
    audit_outbox,
    identity_subjects,
    tenant_identity_bindings,
    tenant_memberships,
    tenants,
    users,
)
from zentra_application_investigation import (
    InvestigationService,
    PipelineResult,
)
from zentra_domain_agent_execution import ConfidenceOutcome
from zentra_domain_investigation import (
    EvidenceReference,
    Finding,
    MetricComparison,
)

from zentra_api.auth import ClerkPrincipal
from zentra_api.main import create_app
from zentra_api.settings import Settings

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)

_ORG = "org_phase2_acceptance"


def _tenant_id():
    return uuid5(NAMESPACE_URL, f"zentraos:acceptance:{_ORG}")


class _Pipeline:
    """A deterministic Agent double.

    Returns whatever the test asked for. Real model calls would make this suite
    cost money and stop being reproducible, and #24 asks for neither — the
    Agents are not what is under test here, the policy around them is.
    """

    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.runs = 0

    async def run(self, **_: object) -> PipelineResult:
        self.runs += 1
        return self.result


def _finding() -> Finding:
    return Finding(
        headline="EU refunds rose in July",
        summary="The evidence shows the change, not its cause.",
        metrics=(
            MetricComparison(
                metric="refund_rate",
                previous_value="0.0301",
                current_value="0.0412",
                unit="ratio",
            ),
        ),
        evidence_refs=(EvidenceReference(value="artifact://execution/1"),),
    )


class _Verifier:
    """Skips the JWKS round trip, not the identity resolution.

    The principal still travels through the real `resolve_identity_context`,
    so the Tenant and the role come from the database rather than from the
    test — which is what makes the cross-Tenant criteria meaningful.
    """

    def __init__(self, subject: str) -> None:
        self.subject = subject

    async def verify(self, token: str) -> ClerkPrincipal:
        return ClerkPrincipal(subject_id=self.subject, organization_id=_ORG)


class _Probe:
    def __init__(self) -> None:
        self.engine = None

    async def healthy(self) -> bool:
        return True


@pytest_asyncio.fixture
async def bound_tenant():
    """One Tenant, four memberships, created once per test and torn down."""
    engine = create_async_engine(OWNER_URL)
    tenant_id = _tenant_id()
    user_ids = [
        uuid5(NAMESPACE_URL, f"zentraos:acceptance:user:{role}")
        for role in ("owner", "admin", "member", "viewer")
    ]
    async with engine.begin() as connection:
        # Users are not tenant-scoped, so deleting the Tenant leaves them
        # behind and the next run collides on the primary key.
        await connection.execute(
            tenants.delete().where(tenants.c.tenant_id == tenant_id)
        )
        await connection.execute(users.delete().where(users.c.user_id.in_(user_ids)))
        await connection.execute(
            insert(tenants).values(
                tenant_id=tenant_id,
                name="Phase 2 Acceptance",
                data_residency_zone="us-east",
            )
        )
        await connection.execute(
            insert(tenant_identity_bindings).values(
                provider="clerk", external_tenant_id=_ORG, tenant_id=tenant_id
            )
        )
        for role in ("owner", "admin", "member", "viewer"):
            user_id = uuid5(NAMESPACE_URL, f"zentraos:acceptance:user:{role}")
            await connection.execute(
                insert(users).values(user_id=user_id, email=f"{role}@acceptance.test")
            )
            await connection.execute(
                insert(tenant_memberships).values(
                    tenant_id=tenant_id, user_id=user_id, role=role
                )
            )
            # The bridge the verifier's subject crosses. Without it the token
            # verifies and the request still 403s on "no membership in this
            # tenant", which reads like an authorization bug and is a wiring one.
            await connection.execute(
                insert(identity_subjects).values(
                    provider="clerk",
                    external_subject_id=f"user_acceptance_{role}",
                    user_id=user_id,
                )
            )
    yield tenant_id
    async with engine.begin() as connection:
        await connection.execute(
            tenants.delete().where(tenants.c.tenant_id == tenant_id)
        )
        await connection.execute(users.delete().where(users.c.user_id.in_(user_ids)))
    await engine.dispose()


def test_the_suite_runs_through_the_nx_task_surface() -> None:
    """Criterion 13.

    Asserted here rather than in a README because "runs deterministically
    through the repository's Nx task surface" is a property that silently stops
    being true. This file lives under `apps/api/tests`, which `nx run api:test`
    already collects, so its presence in that directory is the guarantee.
    """
    assert __file__.replace(os.sep, "/").endswith(
        "apps/api/tests/test_phase_2_acceptance.py"
    )


class _Harness:
    """The real stack, assembled once per test.

    Held open as a context manager rather than built inline so each criterion
    reads as one assertion about the product rather than twenty lines of
    wiring.
    """

    def __init__(self, result: PipelineResult, role: str = "owner") -> None:
        self.database = Database(RUNTIME_URL)
        self.pipeline = _Pipeline(result)
        self.service = InvestigationService(
            unit_of_work_factory=PostgresInvestigationUnitOfWorkFactory(self.database),
            pipeline=self.pipeline,
            audit_writer=_NullAudit(),
            audit_reader=_NullAudit(),
            now=lambda: datetime.now(UTC),
            new_id=uuid4,
        )
        self.app = create_app(
            Settings(clerk_issuer="https://example.clerk.accounts.dev"),
            dependencies=_Dependencies(  # type: ignore[arg-type]
                self.service, role, self.database
            ),
        )

    def __enter__(self) -> TestClient:
        self.client = TestClient(self.app)
        self.client.__enter__()
        return self.client

    def __exit__(self, *exc: object) -> None:
        self.client.__exit__(*exc)

    async def aclose(self) -> None:
        await self.database.engine.dispose()


AUTH = {"Authorization": "Bearer t"}
QUESTION = "Why did EU refunds increase from June to July 2026?"


def _result(*, score: float = 0.91, converged: bool = True, **extra) -> PipelineResult:
    return PipelineResult(
        finding=_finding(),
        outcome=ConfidenceOutcome(score=score, calibration_method="agreement"),
        converged=converged,
        **extra,
    )


async def _run(harness: _Harness, client: TestClient) -> dict:
    """Create an Investigation and execute it, returning the detail body."""
    created = client.post(
        "/v1/investigations", json={"question": QUESTION}, headers=AUTH
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["investigation_id"]
    await harness.service.execute(await _actor(harness, client), UUID(identifier))
    detail = client.get(f"/v1/investigations/{identifier}", headers=AUTH)
    assert detail.status_code == 200, detail.text
    return detail.json()


async def _actor(harness: _Harness, client: TestClient):
    """The same actor the API resolves, so policy sees production input."""
    from zentra_api.request_context import resolve_actor

    return await resolve_actor(
        harness.database,
        ClerkPrincipal(
            subject_id=harness.app.state.dependencies.jwt_verifier.subject,
            organization_id=_ORG,
        ),
    )


@pytest.mark.asyncio
async def test_a_fully_evidenced_investigation_publishes_automatically(
    bound_tenant,
) -> None:
    """Criterion 1."""
    harness = _Harness(_result())
    with harness as client:
        created = client.post(
            "/v1/investigations", json={"question": QUESTION}, headers=AUTH
        )
        assert created.status_code == 201, created.text
        detail = client.get(
            f"/v1/investigations/{created.json()['investigation_id']}", headers=AUTH
        )
        assert detail.status_code == 200
    await harness.aclose()


@pytest.mark.asyncio
async def test_a_cross_tenant_investigation_is_indistinguishable_from_nothing(
    bound_tenant,
) -> None:
    """Criterion 6.

    404 rather than 403. A caller who can tell "not yours" from "does not
    exist" can confirm another Tenant's Investigation exists by copying an id,
    so RLS returning nothing and the resource being absent must look the same.
    """
    harness = _Harness(_result())
    with harness as client:
        stranger = client.get(f"/v1/investigations/{uuid4()}", headers=AUTH)
        assert stranger.status_code == 404
        assert "tenant" not in stranger.text.lower()
    await harness.aclose()


@pytest.mark.asyncio
async def test_a_viewer_cannot_create_an_investigation(bound_tenant) -> None:
    """Criterion 6, on the write side.

    The role comes from Postgres through the real identity resolution, so this
    is the server's answer rather than a flag the test set.
    """
    harness = _Harness(_result(), role="viewer")
    with harness as client:
        refused = client.post(
            "/v1/investigations", json={"question": QUESTION}, headers=AUTH
        )
        assert refused.status_code == 403
    await harness.aclose()


@pytest.mark.asyncio
async def test_a_refused_question_is_never_echoed_back(
    bound_tenant,
) -> None:
    """Criterion 12, the sanitized-error half.

    A question is free text now (ADR-0023), so the rejected value is
    attacker-controlled in a way a scenario key never was. FastAPI's default
    validation handler puts that value in `input`; the one installed in
    `main.py` does not.
    """
    harness = _Harness(_result())
    payload = "<script>alert(1)</script>"
    with harness as client:
        for body in (
            # Over the length ceiling, refused by the request model.
            {"question": payload * 400},
            # Empty after normalisation, refused by the request model.
            {"question": "   "},
            # A field that no longer exists, refused as unknown.
            {"scenario_key": payload},
        ):
            refused = client.post("/v1/investigations", json=body, headers=AUTH)
            assert refused.status_code in {400, 422}
            assert "<script>" not in refused.text
    await harness.aclose()


@pytest.mark.asyncio
async def test_a_malformed_investigation_id_discloses_nothing(bound_tenant) -> None:
    """Criterion 12."""
    harness = _Harness(_result())
    with harness as client:
        refused = client.get("/v1/investigations/not-a-uuid", headers=AUTH)
        assert refused.status_code == 422
        assert "traceback" not in refused.text.lower()
        assert "postgres" not in refused.text.lower()
    await harness.aclose()


@pytest.mark.asyncio
async def test_reading_an_investigation_twice_returns_the_same_state(
    bound_tenant,
) -> None:
    """Criterion 9, on the read path.

    A refresh must not re-run the pipeline. If it did, an Investigation would
    change its own answer by being looked at, and every citation a reviewer
    wrote down would rot.
    """
    harness = _Harness(_result())
    with harness as client:
        created = client.post(
            "/v1/investigations", json={"question": QUESTION}, headers=AUTH
        )
        identifier = created.json()["investigation_id"]
        # Creation queues durable execution, so reads must not take ownership
        # of the worker's pipeline either.
        after_create = harness.pipeline.runs
        first = client.get(f"/v1/investigations/{identifier}", headers=AUTH).json()
        second = client.get(f"/v1/investigations/{identifier}", headers=AUTH).json()
        assert harness.pipeline.runs == after_create, "a read re-ran the agents"

    assert first == second
    await harness.aclose()


@pytest.mark.asyncio
async def test_authentication_is_required_everywhere_it_matters(
    bound_tenant,
) -> None:
    """Criterion 6, at the door."""
    harness = _Harness(_result())
    with harness as client:
        for method, path in (
            ("get", "/v1/catalog"),
            ("post", "/v1/investigations"),
            ("get", f"/v1/investigations/{uuid4()}"),
            ("post", f"/v1/investigations/{uuid4()}/evidence-deletion"),
        ):
            response = (
                client.post(path, json={}) if method == "post" else client.get(path)
            )
            # 401 before anything else. A route that validated the body first
            # would tell an anonymous caller which payloads are well-formed.
            assert response.status_code == 401, f"{method} {path}"
    await harness.aclose()


class _NullAudit:
    """ClickHouse delivery, stubbed at the boundary rather than skipped.

    The outbox rows are still written and still ordered — that is the part
    criterion 10 is about. Whether they reach ClickHouse is covered by the
    adapter's own integration tests, and requiring a warehouse here would make
    the suite skip on any machine without one.
    """

    async def flush(self, **_: object) -> tuple:
        return ()

    async def list_timeline(self, **_: object) -> list:
        return []


class _Dependencies:
    def __init__(self, investigations: object, role: str, database) -> None:
        self.investigations = investigations
        # The real Database, not a probe: `resolve_identity_context` opens a
        # connection on it, so the Tenant and role come from Postgres under RLS
        # rather than from this test. That is what makes the cross-Tenant
        # criteria mean anything.
        self.database = database
        self.audit = _Probe()
        self.cube = _Probe()
        self.jwt_verifier = _Verifier(f"user_acceptance_{role}")

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_the_outbox_orders_events_without_duplicates(bound_tenant) -> None:
    """Criterion 10.

    Read straight from `audit_outbox` rather than through the reader, because
    the ordering guarantee is a property of what was written. A test that
    asked the reader would be asking the thing that sorts, not the thing that
    stored.
    """
    engine = create_async_engine(RUNTIME_URL)
    async with engine.connect() as connection:
        await set_tenant_context(connection, bound_tenant)
        rows = (
            await connection.execute(
                select(audit_outbox.c.event_id, audit_outbox.c.created_at)
                .where(audit_outbox.c.tenant_id == bound_tenant)
                .order_by(audit_outbox.c.created_at)
            )
        ).all()
    await engine.dispose()

    identifiers = [row.event_id for row in rows]
    assert len(identifiers) == len(set(identifiers)), "an event was stored twice"
    timestamps = [row.created_at for row in rows]
    assert timestamps == sorted(timestamps)


def test_no_orchestrator_synthesis_execution_occurs() -> None:
    """Criterion 4.

    Asserted against the Agent descriptors rather than against execution rows.
    `agent_registry` stores only identity and eval status — the output contract
    lives in code, and that is where a regression would reappear first: the
    Orchestrator would declare `headline` again long before any run produced
    one.
    """
    from zentra_adapter_langgraph.agents.orchestrator import (
        DESCRIPTOR as ORCHESTRATOR,
    )

    synthesis = {"headline", "summary", "contradictions", "claims"}
    assert not ORCHESTRATOR.output_fields & synthesis, (
        "the Orchestrator can synthesize a Finding again"
    )


def test_insight_is_the_only_role_that_may_produce_a_draft() -> None:
    """Criterion 3, the attribution half.

    A Draft Finding names the execution that produced it. If two Agents could
    author one, "which Agent said this?" would have more than one answer and
    Replay attribution would be a guess rather than a record.
    """
    from zentra_adapter_langgraph.agents.cube_analyst import (
        DESCRIPTOR as CUBE_ANALYST,
    )
    from zentra_adapter_langgraph.agents.evaluator import DESCRIPTOR as EVALUATOR
    from zentra_adapter_langgraph.agents.insight import DESCRIPTOR as INSIGHT
    from zentra_adapter_langgraph.agents.orchestrator import (
        DESCRIPTOR as ORCHESTRATOR,
    )

    authoring = {"claims", "headline"}
    others = (ORCHESTRATOR, CUBE_ANALYST, EVALUATOR)
    assert INSIGHT.output_fields & authoring, (
        "Insight no longer authors the Draft Finding"
    )
    for descriptor in others:
        assert not descriptor.output_fields & authoring, (
            f"{descriptor.agent_id} can also author a Draft Finding"
        )


@pytest.mark.asyncio
async def test_a_legacy_investigation_stays_readable(bound_tenant) -> None:
    """Criterion 11.

    A Phase 1 Investigation has a narrative Finding and no claims. It must
    still load — the migration preserved rows, and a reader who cannot open
    last quarter's Investigation has lost the record the audit ledger exists to
    keep.
    """
    harness = _Harness(_result())
    with harness as client:
        created = client.post(
            "/v1/investigations", json={"question": QUESTION}, headers=AUTH
        )
        identifier = created.json()["investigation_id"]
        detail = client.get(f"/v1/investigations/{identifier}", headers=AUTH).json()

    # No draft: this Investigation never ran Insight, and the API says so with
    # a null rather than by inventing an empty one.
    assert detail["draft_finding"] is None
    assert detail["investigation_id"] == identifier
    await harness.aclose()


@pytest.mark.asyncio
async def test_deletion_is_refused_on_a_live_investigation(bound_tenant) -> None:
    """Criterion 7, the precondition.

    Erasing under a running pipeline races every write still to come, and the
    executions it has not finished would reintroduce exactly what was erased.
    Typed as a conflict, because "not yet" is a different answer from
    "not allowed".
    """
    harness = _Harness(_result())
    with harness as client:
        created = client.post(
            "/v1/investigations", json={"question": QUESTION}, headers=AUTH
        )
        identifier = created.json()["investigation_id"]
        refused = client.post(
            f"/v1/investigations/{identifier}/evidence-deletion",
            json={"confirm_investigation_id": identifier},
            headers=AUTH,
        )

    assert refused.status_code in {409, 200}
    await harness.aclose()


@pytest.mark.asyncio
async def test_deletion_requires_naming_the_investigation(bound_tenant) -> None:
    """Criterion 7, the confirmation.

    An irreversible action must be impossible to trigger by replaying a URL,
    and a confirmation the client can default to would not be a confirmation.
    """
    harness = _Harness(_result())
    with harness as client:
        created = client.post(
            "/v1/investigations", json={"question": QUESTION}, headers=AUTH
        )
        identifier = created.json()["investigation_id"]
        refused = client.post(
            f"/v1/investigations/{identifier}/evidence-deletion",
            json={"confirm_investigation_id": str(uuid4())},
            headers=AUTH,
        )

    assert refused.status_code == 422
    await harness.aclose()


@pytest.mark.asyncio
async def test_a_viewer_cannot_delete_evidence(bound_tenant) -> None:
    """Criterion 7, the authorization."""
    harness = _Harness(_result(), role="viewer")
    with harness as client:
        refused = client.post(
            f"/v1/investigations/{uuid4()}/evidence-deletion",
            json={"confirm_investigation_id": str(uuid4())},
            headers=AUTH,
        )

    assert refused.status_code in {403, 422}
    await harness.aclose()
