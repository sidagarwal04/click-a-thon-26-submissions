from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL")
pytestmark = pytest.mark.skipif(
    not OWNER_URL,
    reason="local Postgres integration URL is not configured",
)


def _config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def test_durable_job_migration_adds_leases_rls_and_checkpoint_tables() -> None:
    assert OWNER_URL is not None
    os.environ["DATABASE_OWNER_URL"] = OWNER_URL
    config = _config()
    engine = create_engine(OWNER_URL)
    try:
        command.downgrade(config, "0015_draft_investigation_threads")
        assert "execution_jobs" not in inspect(engine).get_table_names()

        command.upgrade(config, "head")

        tables = set(inspect(engine).get_table_names())
        assert {
            "execution_jobs",
            "checkpoint_migrations",
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
        } <= tables
        with engine.begin() as connection:
            rls = connection.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                    "WHERE relname = 'execution_jobs'"
                )
            ).one()
            policy = connection.execute(
                text(
                    "SELECT policyname FROM pg_policies "
                    "WHERE tablename = 'execution_jobs'"
                )
            ).scalar_one()
            checkpoint_versions = connection.execute(
                text("SELECT count(*) FROM checkpoint_migrations")
            ).scalar_one()
            checkpoint_rls = connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname IN "
                    "('checkpoints', 'checkpoint_blobs', 'checkpoint_writes')"
                )
            ).all()

        assert rls.relrowsecurity and rls.relforcerowsecurity
        assert policy == "execution_jobs_tenant_isolation"
        assert checkpoint_versions == 10
        assert len(checkpoint_rls) == 3
        assert all(
            row.relrowsecurity and row.relforcerowsecurity
            for row in checkpoint_rls
        )
    finally:
        command.upgrade(config, "head")
        engine.dispose()
