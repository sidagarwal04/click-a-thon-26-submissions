from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

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


def test_the_two_prior_migration_heads_are_merged_into_one() -> None:
    assert OWNER_URL is not None
    os.environ["DATABASE_OWNER_URL"] = OWNER_URL
    config = _config()

    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    # Exactly one head from here forward — later revisions (e.g. Sequence's
    # own tables) build on this single lineage rather than reintroducing a
    # branch. "0018_merge_heads" itself is an ancestor of every later head.
    assert len(heads) == 1
    ancestor_revisions = {
        revision.revision
        for revision in script.walk_revisions(base="base", head=heads[0])
    }
    assert "0018_merge_heads" in ancestor_revisions

    # A no-op merge: upgrading to head must succeed without error.
    command.upgrade(config, "head")
