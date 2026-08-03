"""Schema rendering is easy to get wrong: ClickHouse macros look like Python
format placeholders. These tests pin the distinction."""

from __future__ import annotations

from string import Template

from prism_ch.config import Settings
from prism_ch.schema import STATEMENTS


def _rendered(settings: Settings) -> list[str]:
    mapping = {"DB": settings.database, "CLUSTER": settings.cluster}
    return [Template(s.strip()).substitute(mapping) for s in STATEMENTS]


def test_every_statement_targets_the_cluster(make_settings) -> None:  # noqa: ANN001
    for sql in _rendered(make_settings()):
        assert "ON CLUSTER click_agents" in sql or "Distributed('click_agents'" in sql


def test_server_side_macros_are_left_literal(make_settings) -> None:  # noqa: ANN001
    replicated = next(s for s in _rendered(make_settings()) if "ReplicatedMergeTree" in s)
    assert "{shard}" in replicated
    assert "{replica}" in replicated


def test_database_and_cluster_are_substituted(make_settings) -> None:  # noqa: ANN001
    sqls = _rendered(make_settings(database="analytics", cluster="other_cluster"))
    joined = "\n".join(sqls)
    assert "$DB" not in joined
    assert "$CLUSTER" not in joined
    assert "CREATE DATABASE IF NOT EXISTS analytics ON CLUSTER other_cluster" in sqls[0]


def test_statements_are_idempotent(make_settings) -> None:  # noqa: ANN001
    for sql in _rendered(make_settings()):
        assert "IF NOT EXISTS" in sql
