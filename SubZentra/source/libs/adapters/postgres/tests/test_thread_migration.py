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


def test_thread_migration_is_additive_and_messages_are_not_updatable() -> None:
    assert OWNER_URL is not None
    os.environ["DATABASE_OWNER_URL"] = OWNER_URL
    config = _config()
    engine = create_engine(OWNER_URL)
    try:
        command.downgrade(config, "0014_workspace_groups_projects")
        assert "investigation_threads" not in inspect(engine).get_table_names()
        assert "thread_messages" not in inspect(engine).get_table_names()

        command.upgrade(config, "head")

        inspector = inspect(engine)
        assert {"investigation_threads", "thread_messages"} <= set(
            inspector.get_table_names()
        )
        investigation_columns = {
            column["name"] for column in inspector.get_columns("investigations")
        }
        assert {"thread_id", "thread_sequence", "initiating_message_id"} <= (
            investigation_columns
        )
        with engine.begin() as connection:
            privileges = connection.execute(
                text(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    "WHERE grantee = 'zentra_runtime' "
                    "AND table_name = 'thread_messages'"
                )
            ).scalars()
            message_grants = set(privileges)
        assert "SELECT" in message_grants
        assert "INSERT" in message_grants
        assert "UPDATE" not in message_grants
        assert "DELETE" not in message_grants
    finally:
        command.upgrade(config, "head")
        engine.dispose()
