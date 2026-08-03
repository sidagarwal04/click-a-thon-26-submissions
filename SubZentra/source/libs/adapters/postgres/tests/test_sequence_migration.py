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

SEQUENCE_TABLES = {
    "sequences",
    "sequence_steps",
    "prepared_tables",
    "sequence_runs",
    "sequence_final_tables",
}


def _config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def test_sequence_migration_is_additive_and_installs_forced_rls() -> None:
    assert OWNER_URL is not None
    os.environ["DATABASE_OWNER_URL"] = OWNER_URL
    config = _config()
    engine = create_engine(OWNER_URL)
    try:
        command.downgrade(config, "0018_merge_heads")
        assert not SEQUENCE_TABLES & set(inspect(engine).get_table_names())

        command.upgrade(config, "head")

        assert set(inspect(engine).get_table_names()) >= SEQUENCE_TABLES
        with engine.begin() as connection:
            rls = connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname = ANY(:names) "
                    "AND relnamespace = 'public'::regnamespace"
                ),
                {"names": list(SEQUENCE_TABLES)},
            ).all()
            policies = connection.execute(
                text(
                    "SELECT tablename, policyname FROM pg_policies "
                    "WHERE tablename = ANY(:names)"
                ),
                {"names": list(SEQUENCE_TABLES)},
            ).all()

        assert len(rls) == len(SEQUENCE_TABLES)
        assert all(row.relrowsecurity and row.relforcerowsecurity for row in rls)
        assert {(row.tablename, row.policyname) for row in policies} == {
            (name, f"{name}_tenant_isolation") for name in SEQUENCE_TABLES
        }
    finally:
        command.upgrade(config, "head")
        engine.dispose()


def test_sequence_migration_downgrade_removes_every_table() -> None:
    assert OWNER_URL is not None
    os.environ["DATABASE_OWNER_URL"] = OWNER_URL
    config = _config()
    engine = create_engine(OWNER_URL)
    try:
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names()) >= SEQUENCE_TABLES

        command.downgrade(config, "0018_merge_heads")
        assert not SEQUENCE_TABLES & set(inspect(engine).get_table_names())
    finally:
        command.upgrade(config, "head")
        engine.dispose()
