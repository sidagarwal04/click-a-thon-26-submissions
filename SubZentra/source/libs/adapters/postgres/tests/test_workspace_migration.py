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


def test_workspace_migration_is_additive_and_installs_forced_rls() -> None:
    assert OWNER_URL is not None
    os.environ["DATABASE_OWNER_URL"] = OWNER_URL
    config = _config()
    engine = create_engine(OWNER_URL)
    try:
        command.downgrade(config, "0013_outbox_investigation_index")
        assert "workspace_groups" not in inspect(engine).get_table_names()
        assert "projects" not in inspect(engine).get_table_names()

        command.upgrade(config, "head")

        assert {"workspace_groups", "projects"} <= set(
            inspect(engine).get_table_names()
        )
        with engine.begin() as connection:
            rls = connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname IN "
                    "('workspace_groups', 'projects')"
                )
            ).all()
            policies = connection.execute(
                text(
                    "SELECT tablename, policyname FROM pg_policies "
                    "WHERE tablename IN ('workspace_groups', 'projects')"
                )
            ).all()

        assert len(rls) == 2
        assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls)
        assert {(row.tablename, row.policyname) for row in policies} == {
            ("workspace_groups", "workspace_groups_tenant_isolation"),
            ("projects", "projects_tenant_isolation"),
        }
    finally:
        command.upgrade(config, "head")
        engine.dispose()
