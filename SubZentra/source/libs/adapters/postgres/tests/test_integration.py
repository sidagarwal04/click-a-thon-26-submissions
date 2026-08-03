from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from zentra_adapter_postgres import resolve_identity_context
from zentra_adapter_postgres.database import set_tenant_context
from zentra_adapter_postgres.schema import (
    agent_executions,
    agent_registry,
    identity_subjects,
    investigations,
    tenant_identity_bindings,
    tenant_memberships,
    tenants,
    users,
)

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_RUNTIME_URL")

pytestmark = pytest.mark.skipif(
    not OWNER_URL or not RUNTIME_URL,
    reason="local Postgres integration URLs are not configured",
)

TENANT_A = UUID("71000000-0000-0000-0000-000000000001")
TENANT_B = UUID("71000000-0000-0000-0000-000000000002")
USER_ID = UUID("72000000-0000-0000-0000-000000000001")
INVALID_USER_ID = UUID("72000000-0000-0000-0000-000000000002")
INVESTIGATION_ID = UUID("73000000-0000-0000-0000-000000000001")


async def seed(owner_url: str) -> None:
    owner = create_async_engine(owner_url)
    async with owner.begin() as connection:
        await connection.execute(
            postgres_insert(tenants)
            .values(
                [
                    {"tenant_id": TENANT_A, "name": "Integration A"},
                    {"tenant_id": TENANT_B, "name": "Integration B"},
                ]
            )
            .on_conflict_do_nothing()
        )
        await connection.execute(
            postgres_insert(users)
            .values(
                [
                    {"user_id": USER_ID, "email": "integration@example.com"},
                    {"user_id": INVALID_USER_ID, "email": "invalid@example.com"},
                ]
            )
            .on_conflict_do_nothing()
        )
        await connection.execute(
            postgres_insert(identity_subjects)
            .values(
                provider="clerk",
                external_subject_id="user_integration",
                user_id=USER_ID,
            )
            .on_conflict_do_nothing()
        )
        await connection.execute(
            postgres_insert(tenant_identity_bindings)
            .values(
                [
                    {
                        "provider": "clerk",
                        "external_tenant_id": "org_integration_a",
                        "tenant_id": TENANT_A,
                    },
                    {
                        "provider": "clerk",
                        "external_tenant_id": "org_integration_b",
                        "tenant_id": TENANT_B,
                    },
                ]
            )
            .on_conflict_do_nothing()
        )
        await connection.execute(
            postgres_insert(tenant_memberships)
            .values(
                [
                    {"tenant_id": TENANT_A, "user_id": USER_ID, "role": "owner"},
                    {"tenant_id": TENANT_B, "user_id": USER_ID, "role": "viewer"},
                ]
            )
            .on_conflict_do_nothing()
        )
        await connection.execute(
            postgres_insert(investigations)
            .values(
                investigation_id=INVESTIGATION_ID,
                tenant_id=TENANT_A,
                question="Integration fixture",
                status="running",
            )
            .on_conflict_do_nothing()
        )
    await owner.dispose()


@pytest.mark.asyncio
async def test_rls_identity_and_constraints() -> None:
    assert OWNER_URL is not None
    assert RUNTIME_URL is not None
    await seed(OWNER_URL)

    runtime = create_async_engine(RUNTIME_URL)
    async with runtime.begin() as connection:
        without_context = await connection.scalar(
            select(func.count()).select_from(tenants)
        )
    assert without_context == 0

    async with runtime.begin() as connection:
        identity = await resolve_identity_context(
            connection,
            provider="clerk",
            external_subject_id="user_integration",
            external_tenant_id="org_integration_a",
        )
        visible_memberships = await connection.scalar(
            select(func.count()).select_from(tenant_memberships)
        )
    assert identity.user_id == USER_ID
    assert identity.tenant_id == TENANT_A
    assert identity.role == "owner"
    assert visible_memberships == 1

    async with runtime.begin() as connection:
        await set_tenant_context(connection, TENANT_B)
        visible_tenants = (
            (await connection.execute(select(tenants.c.tenant_id))).scalars().all()
        )
    assert visible_tenants == [TENANT_B]
    await runtime.dispose()

    owner = create_async_engine(OWNER_URL)
    with pytest.raises(IntegrityError, match="ck_tenant_memberships_role"):
        async with owner.begin() as connection:
            await connection.execute(
                insert(tenant_memberships).values(
                    tenant_id=TENANT_A,
                    user_id=INVALID_USER_ID,
                    role="guest",
                )
            )

    with pytest.raises(IntegrityError, match="ck_agent_executions_typed_outcome"):
        async with owner.begin() as connection:
            await connection.execute(
                insert(agent_executions).values(
                    investigation_id=INVESTIGATION_ID,
                    tenant_id=TENANT_A,
                    agent_id="deterministic-validator",
                    step=0,
                    input={},
                    outcome_kind="validation",
                    confidence=0.9,
                    status="success",
                )
            )
    await owner.dispose()


LEGACY_AGENT_ID = "insight_legacy_fixture"
CANONICAL_AGENT_ID = "insight_canonical_fixture"


def _load_migration_0005():
    """Loaded by path rather than imported: revision filenames start with a
    digit, so they are not importable module names. Reusing the migration's own
    role list is the point — a test that restated it would keep passing after
    the migration and `schema.py` had drifted apart.
    """
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0005_canonical_insight_role.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0005", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_a_legacy_role_row_survives_the_rename_but_cannot_be_written() -> None:
    """ADR 0011's expand step, proved against the database rather than the
    enum. A Phase 1 row must stay readable — Replay renders it — while the same
    value must be unwritable from here on. `NOT VALID` is the only thing that
    gives both, so the migration is re-applied over a seeded legacy row rather
    than merely asserted against an empty table.
    """
    assert OWNER_URL is not None
    migration = _load_migration_0005()
    role_check = migration._role_check(migration.CANONICAL_ROLES)
    owner = create_async_engine(OWNER_URL)

    # Reconstruct a database that predates the rename, and seed the row a
    # Phase 1 deployment would be holding.
    async with owner.begin() as connection:
        await connection.exec_driver_sql(
            "ALTER TABLE agent_registry "
            "DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
        )
        await connection.execute(
            postgres_insert(agent_registry)
            .values(
                agent_id=LEGACY_AGENT_ID,
                role="insight_root_cause",
                version="1",
                eval_suite_ref="evals/insight",
            )
            .on_conflict_do_nothing()
        )

    # Re-apply the tightening exactly as 0005 does.
    async with owner.begin() as connection:
        await connection.exec_driver_sql(
            "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
            f"CHECK ({role_check}) NOT VALID"
        )

    try:
        async with owner.begin() as connection:
            survived = await connection.scalar(
                select(agent_registry.c.role).where(
                    agent_registry.c.agent_id == LEGACY_AGENT_ID
                )
            )
        assert survived == "insight_root_cause"

        with pytest.raises(IntegrityError, match="ck_agent_registry_role"):
            async with owner.begin() as connection:
                await connection.execute(
                    insert(agent_registry).values(
                        agent_id="insight_legacy_probe",
                        role="insight_root_cause",
                        version="1",
                        eval_suite_ref="evals/insight",
                    )
                )

        async with owner.begin() as connection:
            await connection.execute(
                insert(agent_registry).values(
                    agent_id=CANONICAL_AGENT_ID,
                    role="insight",
                    version="1",
                    eval_suite_ref="evals/insight",
                )
            )
        async with owner.begin() as connection:
            canonical = await connection.scalar(
                select(agent_registry.c.role).where(
                    agent_registry.c.agent_id == CANONICAL_AGENT_ID
                )
            )
        assert canonical == "insight"
    finally:
        # Restore the constraint as well as the rows. This test drops a real
        # constraint on a shared database; leaving it dropped after a failure
        # would silently unguard every test that runs afterwards.
        async with owner.begin() as connection:
            await connection.execute(
                agent_registry.delete().where(
                    agent_registry.c.agent_id.in_(
                        (LEGACY_AGENT_ID, CANONICAL_AGENT_ID)
                    )
                )
            )
            await connection.exec_driver_sql(
                "ALTER TABLE agent_registry "
                "DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
            )
            await connection.exec_driver_sql(
                "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
                f"CHECK ({role_check}) NOT VALID"
            )
        await owner.dispose()


@pytest.mark.asyncio
async def test_an_unpromoted_agent_is_invisible_to_the_enabled_filter() -> None:
    """What makes the Phase 2 route fail closed on a *disabled* Insight.

    "Disabled" and "missing" have to reach the Orchestrator as the same answer,
    and this is the predicate that makes them so. Asserted against a real
    database because the guarantee is the `enabled` column, not any Python.
    """
    assert OWNER_URL is not None
    owner = create_async_engine(OWNER_URL)
    try:
        async with owner.begin() as connection:
            await connection.execute(
                postgres_insert(agent_registry)
                .values(
                    agent_id="insight_disabled_probe",
                    role="insight",
                    version="1",
                    enabled=False,
                    eval_status="pending",
                    eval_suite_ref="evals/insight",
                )
                .on_conflict_do_nothing()
            )

        async with owner.begin() as connection:
            advertised = (
                (
                    await connection.execute(
                        select(agent_registry.c.agent_id).where(
                            agent_registry.c.enabled.is_(True)
                        )
                    )
                )
                .scalars()
                .all()
            )
            exists = await connection.scalar(
                select(func.count()).select_from(agent_registry).where(
                    agent_registry.c.agent_id == "insight_disabled_probe"
                )
            )

        # The row is there — it just is not offered to anyone.
        assert exists == 1
        assert "insight_disabled_probe" not in advertised
    finally:
        async with owner.begin() as connection:
            await connection.execute(
                agent_registry.delete().where(
                    agent_registry.c.agent_id == "insight_disabled_probe"
                )
            )
        await owner.dispose()
