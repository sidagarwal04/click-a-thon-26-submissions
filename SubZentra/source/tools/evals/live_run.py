"""Drive one real investigation end to end.

Builds the same graph the API composition root builds, but seeds a tenant
directly and calls the service with a hand-made actor, so no Clerk setup is
needed. Everything downstream of that — agents, routing, Cube, the confidence
gate, agent_executions, the ClickHouse ledger — is the real thing.

    uv run python tools/evals/live_run.py --replay free_tier
    uv run python tools/evals/live_run.py --record free_tier
    uv run python tools/evals/live_run.py --record premium_tier --tier premium

`--replay` costs nothing and touches no provider: it serves a cassette under
`evals/cassettes/` recorded by an earlier `--record` run, so a calibration or
gating change can be re-verified against real model output for free. Anything
the cassette does not hold raises rather than silently reaching the network.

The tier defaults to `free` and a bare run calls live models, so spending money
is always something you typed on purpose.

Reads provider keys from the environment or apps/api/.env. Never prints them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine
from zentra_adapter_clickhouse import AuditRepository
from zentra_adapter_langgraph import (
    CubeAnalystAgent,
    EvaluatorAgent,
    InsightAgent,
)
from zentra_adapter_model_providers import (
    ModelTier,
    ProviderCircuitBreaker,
    ProviderClients,
    RecordingModelClient,
    ReplayModelClient,
    RoutedModelClient,
    chain_for,
)
from zentra_adapter_postgres import Database, PostgresInvestigationUnitOfWorkFactory
from zentra_adapter_postgres.schema import (
    agent_registry,
    tenant_memberships,
    tenants,
    users,
)
from zentra_api.audit_delivery import AuditDeliveryCoordinator
from zentra_api.cube_scope import ScopedCubeSemanticLayers
from zentra_api.orchestrator_loop import OrchestratorLoop, StepAgents
from zentra_api.pipeline import PostgresExecutionRecorder
from zentra_api.settings import Settings
from zentra_application_investigation import (
    AuthenticatedActor,
    InvestigationService,
    Role,
)
from zentra_domain_agent_execution import AgentRole, ModelPort

CASSETTE_ROOT = Path(__file__).resolve().parents[2] / "evals" / "cassettes"
EXPECT_FILE = "expect.json"

OWNER_URL = os.environ.get(
    "DATABASE_OWNER_URL",
    "postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control",
)
RUNTIME_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://zentra_app:zentra_app@localhost:5432/zentra_control",
)


async def seed_tenant(tier: str) -> tuple[UUID, UUID]:
    """A tenant, a user, and an owner membership. Idempotent per run."""
    tenant_id, user_id = uuid4(), uuid4()
    engine = create_async_engine(OWNER_URL)
    async with engine.begin() as connection:
        await connection.execute(
            insert(tenants).values(
                tenant_id=tenant_id,
                name=f"Live run ({tier})",
                model_tier=tier,
            )
        )
        await connection.execute(
            insert(users).values(user_id=user_id, email=f"{user_id}@live.test")
        )
        await connection.execute(
            insert(tenant_memberships).values(tenant_id=tenant_id, user_id=user_id, role="owner")
        )
        enabled = (
            (
                await connection.execute(
                    select(agent_registry.c.agent_id).where(agent_registry.c.enabled.is_(True))
                )
            )
            .scalars()
            .all()
        )
    await engine.dispose()
    if len(enabled) < 4:
        raise SystemExit(
            f"Only {len(enabled)} agents enabled; Insight is required "
            f"since the Orchestrator stopped synthesising. Run:\n"
            "  DATABASE_OWNER_URL=... npx nx run evals:promote"
        )
    return tenant_id, user_id


def build(
    settings: Settings,
    tier: ModelTier,
    database: Database,
    *,
    record: str | None,
    replay: str | None,
    without: Sequence[str] = (),
) -> tuple[InvestigationService, ProviderClients, AuditRepository]:
    keys = settings.provider_api_keys()
    for provider in without:
        # Simulates an outage the chain must survive. `from_keys` skips falsy
        # values, so the rung is treated exactly as an unconfigured one.
        keys[f"{provider.upper()}_API_KEY"] = None
    models = ProviderClients.from_keys(keys)

    if replay is not None:
        # Wrapped outside the router on purpose: the cassette records which
        # model actually served, so replay reproduces the served identities the
        # independence check reads — without a single provider call.
        directory = CASSETTE_ROOT / replay
        replayer = ReplayModelClient(directory)
        print(f"tier: {tier.value}  replaying {replayer.recorded} calls\n")
        service, audit = _assemble(settings, tier, database, replayer)
        return service, models, audit

    print(f"providers configured: {sorted(p.value for p in models.available)}")
    if without:
        print(f"deliberately withheld: {sorted(without)}")
    print(f"tier: {tier.value}")
    for role in (
        AgentRole.ORCHESTRATOR,
        AgentRole.CUBE_ANALYST,
        AgentRole.EVALUATOR,
        AgentRole.INSIGHT,
    ):
        chain = " -> ".join(str(c) for c in chain_for(tier, role))
        reachable = [c for c in chain_for(tier, role) if c.provider in models.available]
        print(f"  {role.value:14s} {chain}")
        if not reachable:
            raise SystemExit(f"No provider key for any rung of {role.value}")
    print()

    model: ModelPort = RoutedModelClient(
        tier=tier, clients=models.as_dict(), breaker=ProviderCircuitBreaker()
    )
    if record is not None:
        model = RecordingModelClient(model, CASSETTE_ROOT / record)
        print(f"recording to {CASSETTE_ROOT / record}\n")
    service, audit = _assemble(settings, tier, database, model)
    return service, models, audit


def _assemble(
    settings: Settings,
    tier: ModelTier,
    database: Database,
    model: ModelPort,
) -> tuple[InvestigationService, AuditRepository]:
    """Everything below the model seam, identical whichever client is above it."""
    uow = PostgresInvestigationUnitOfWorkFactory(database)

    async def _unreachable_fingerprint(tenant_id, data_connection_id):
        # live_run.py never targets a Data Connection — every investigation
        # here runs against the demo warehouse — so this resolver is never
        # actually called.
        raise NotImplementedError(
            "live_run.py does not support querying a Data Connection"
        )

    semantic_layers = ScopedCubeSemanticLayers(
        cube_url=settings.cube_url,
        cube_api_secret=settings.cube_api_secret,
        resolve_relation_fingerprint=_unreachable_fingerprint,
    )

    def build_agents(semantic_layer):
        return StepAgents(
            cube_analyst=CubeAnalystAgent(model=model, semantic_layer=semantic_layer),
            evaluator=EvaluatorAgent(model=model, semantic_layer=semantic_layer),
            # Required since the Orchestrator stopped synthesising. A recorded
            # scenario that skipped Insight would be exercising a pipeline the
            # product no longer has.
            insight=InsightAgent(model=model),
        )

    audit = AuditRepository.connect(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_username,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
        secure=settings.clickhouse_secure,
    )
    delivery = AuditDeliveryCoordinator(unit_of_work_factory=uow, audit=audit)
    service = InvestigationService(
        unit_of_work_factory=uow,
        pipeline=OrchestratorLoop(
            {tier: build_agents},
            semantic_layers,
            unit_of_work_factory=uow,
            recorder=PostgresExecutionRecorder(uow),
        ),
        audit_writer=delivery,
        audit_reader=delivery,
        now=lambda: datetime.now(UTC),
        new_id=uuid4,
    )
    return service, audit


def observed(
    detail,
    rows,
    *,
    question: str,
    tier: ModelTier,
    without: Sequence[str],
) -> dict:
    """The facts a replay must reproduce.

    Deliberately narrow: what was decided, why, and by which models. Latency,
    cost and wording are not reproducible and are not asserted.
    """
    models = {row.agent_id: row.model for row in rows}
    samples = {
        row.agent_id: (row.output or {}).get("sample_size")
        for row in rows
        if row.output is not None
    }
    outcome = detail.outcome.model_dump() if detail.outcome is not None else {}
    return {
        "question": question,
        "tier": tier.value,
        "without": sorted(without),
        "status": detail.status.value,
        "approval_reason": (detail.pending_approval.reason if detail.pending_approval else None),
        "score": outcome.get("score"),
        "calibration_method": outcome.get("calibration_method"),
        "analyst_model": models.get("cube_analyst_v1"),
        "evaluator_model": models.get("evaluator_v1"),
        "analyst_sample_size": samples.get("cube_analyst_v1"),
        "evaluator_sample_size": samples.get("evaluator_v1"),
    }


def compare(expected: dict, actual: dict) -> list[str]:
    """Which fields diverged. `note` is prose for humans and is never asserted."""
    return [
        f"{field}: expected {expected[field]!r}, got {actual.get(field)!r}"
        for field in sorted(actual)
        if field in expected and expected[field] != actual.get(field)
    ]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tier",
        choices=["free", "premium"],
        default="free",
        help="Defaults to free so premium spend is always deliberate.",
    )
    parser.add_argument(
        "--question",
        default="Why did EU refunds increase from June to July 2026?",
        help="The question to investigate, verbatim. Recorded into the cassette.",
    )
    parser.add_argument(
        "--without",
        action="append",
        default=[],
        metavar="PROVIDER",
        help="Withhold a provider key to force a degraded chain. Repeatable.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--record", metavar="NAME", help="Save responses as a cassette.")
    group.add_argument("--replay", metavar="NAME", help="Serve a cassette. Costs $0.")
    args = parser.parse_args()

    settings = Settings(_env_file="apps/api/.env")
    expected: dict = {}
    if args.replay is not None:
        # The cassette knows the tier and the withheld providers it was recorded
        # under, so replaying it never needs those repeated on the command line.
        expected = json.loads((CASSETTE_ROOT / args.replay / EXPECT_FILE).read_text())
        args.tier = expected["tier"]
        args.without = expected["without"]
        args.question = expected["question"]

    tier = ModelTier(args.tier)
    tenant_id, user_id = await seed_tenant(args.tier)

    database = Database(RUNTIME_URL)
    service, models, audit = build(
        settings,
        tier,
        database,
        record=args.record,
        replay=args.replay,
        without=args.without,
    )
    actor = AuthenticatedActor(
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.OWNER,
        trace_id=uuid4(),
        span_id=uuid4(),
    )

    started = datetime.now(UTC)
    detail = await service.start(actor, question=args.question)
    print(f"started  {detail.investigation_id}  status={detail.status.value}")
    print("running the agents...\n")

    try:
        await service.execute(actor, detail.investigation_id)
    finally:
        elapsed = (datetime.now(UTC) - started).total_seconds()

    detail = await service.get(actor, detail.investigation_id)

    print(f"=== {detail.status.value}  in {elapsed:.0f}s ===")
    if detail.outcome is not None:
        print(f"outcome: {detail.outcome.model_dump()}")
    if detail.pending_approval is not None:
        print(f"gate:    {detail.pending_approval.reason}")
    if detail.finding is not None:
        print(f"\nheadline: {detail.finding.headline}")
        print(f"summary:  {detail.finding.summary}")
        for metric in detail.finding.metrics:
            # The labels are printed because a recording is eyeballed here
            # before it is trusted, and a wrong period is exactly what reading
            # the numbers alone will not catch.
            previous = f"{metric.previous_label} " if metric.previous_label else ""
            current = f"{metric.current_label} " if metric.current_label else ""
            print(
                f"  {metric.metric}: {previous}{metric.previous_value} -> "
                f"{current}{metric.current_value} {metric.unit}"
            )

    print("\n=== which model served each step ===")
    engine = create_async_engine(OWNER_URL)
    async with engine.begin() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT step, agent_id, model, status, confidence, "
                    "latency_ms, cost_usd, output FROM agent_executions "
                    "WHERE investigation_id = :i ORDER BY step"
                ),
                {"i": detail.investigation_id},
            )
        ).all()
    await engine.dispose()
    for row in rows:
        print(
            f"  {row.step}. {row.agent_id:18s} {str(row.model):34s} "
            f"{row.status:8s} conf={row.confidence} {row.latency_ms}ms "
            f"${row.cost_usd}"
        )

    print("\n=== ledger timeline ===")
    for entry in detail.timeline:
        label = entry.model or entry.event_type
        print(f"  {entry.created_at:%H:%M:%S}  {label}  [{entry.delivery.value}]")
        for rung in entry.fallbacks:
            print(f"      fell through: {rung}")

    actual = observed(detail, rows, question=args.question, tier=tier, without=args.without)
    status = 0

    if args.record is not None:
        path = CASSETTE_ROOT / args.record / EXPECT_FILE
        path.write_text(json.dumps(actual, indent=2) + "\n")
        print(f"\nwrote {path}")
        print("Review it, add a `note`, and commit it with the recording.")
    elif args.replay is not None:
        print("\n=== replay vs expectations ===")
        differences = compare(expected, actual)
        for difference in differences:
            print(f"  MISMATCH  {difference}")
        if differences:
            # Loudly, and with a non-zero exit: a cassette that no longer
            # reproduces its recorded decision is the whole alarm.
            print(f"  {len(differences)} field(s) diverged from {args.replay}")
            status = 1
        else:
            print(f"  OK  {args.replay} reproduced its recorded decision")

    await models.close()
    await audit.close()
    await database.close()
    return status


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
