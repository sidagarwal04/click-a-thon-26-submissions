import os

import pytest

from ingestion.bootstrap import (
    LoadAbort,
    dimensions_empty,
    ensure_empty,
    ensure_schema,
    reload_dictionaries,
    split_statements,
)


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClient:
    """Answers canned queries; records every command/query it receives."""

    def __init__(self, tables=(), counts=None, mv_targets=()):
        self.tables = list(tables)          # names in system.tables
        self.counts = dict(counts or {})    # table -> row count
        self.mv_targets = list(mv_targets)  # rollup target table names
        self.commands = []

    def command(self, sql):
        self.commands.append(sql)

    def query(self, sql):
        if "system.tables" in sql and "MaterializedView" in sql:
            return FakeResult([[t] for t in self.mv_targets])
        if "system.tables" in sql:
            return FakeResult([[t] for t in self.tables])
        if sql.startswith("SELECT count() FROM "):
            table = sql.rsplit(" ", 1)[1]
            return FakeResult([[self.counts.get(table, 0)]])
        raise AssertionError(f"unexpected query: {sql}")


def test_split_statements_strips_comments_and_empties():
    sql = """-- a comment
CREATE TABLE t (x Int32) ENGINE = MergeTree ORDER BY x;

-- another
SYSTEM RELOAD DICTIONARY foo;
"""
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("CREATE TABLE t")
    assert "comment" not in stmts[0]


def test_ensure_schema_runs_ddl_files_in_order_when_missing(tmp_path):
    for i, name in enumerate(("schema.sql", "dictionaries.sql", "rollups.sql")):
        (tmp_path / name).write_text(f"CREATE TABLE t{i} (x Int32) ENGINE = MergeTree ORDER BY x;")
    client = FakeClient(tables=[])
    assert ensure_schema(client, str(tmp_path)) is True
    assert [c for c in client.commands if c.startswith("CREATE")] == [
        "CREATE TABLE t0 (x Int32) ENGINE = MergeTree ORDER BY x",
        "CREATE TABLE t1 (x Int32) ENGINE = MergeTree ORDER BY x",
        "CREATE TABLE t2 (x Int32) ENGINE = MergeTree ORDER BY x",
    ]


def test_ensure_schema_noop_when_ad_events_exists(tmp_path):
    client = FakeClient(tables=["ad_events", "apps"])
    assert ensure_schema(client, str(tmp_path)) is False
    assert client.commands == []


def test_ensure_empty_passes_on_empty_table():
    ensure_empty(FakeClient(counts={"apps": 0}), "apps", truncate=False)


def test_ensure_empty_refuses_non_empty_without_truncate():
    with pytest.raises(LoadAbort) as exc:
        ensure_empty(FakeClient(counts={"apps": 2000}), "apps", truncate=False)
    assert "--truncate" in str(exc.value)


def test_truncate_dimension_truncates_only_itself():
    client = FakeClient(counts={"apps": 2000})
    ensure_empty(client, "apps", truncate=True)
    assert client.commands == ["TRUNCATE TABLE apps"]


def test_truncate_ad_events_also_truncates_discovered_rollup_targets():
    client = FakeClient(
        counts={"ad_events": 100},
        mv_targets=["hourly_overall", "hourly_by_region"],
    )
    ensure_empty(client, "ad_events", truncate=True)
    assert "TRUNCATE TABLE ad_events" in client.commands
    assert "TRUNCATE TABLE hourly_overall" in client.commands
    assert "TRUNCATE TABLE hourly_by_region" in client.commands


def test_reload_dictionaries_reloads_all_three():
    client = FakeClient()
    reload_dictionaries(client)
    assert client.commands == [
        "SYSTEM RELOAD DICTIONARY apps_dict",
        "SYSTEM RELOAD DICTIONARY advertisers_dict",
        "SYSTEM RELOAD DICTIONARY geo_device_dict",
    ]


def test_dimensions_empty_true_when_all_zero():
    assert dimensions_empty(FakeClient(counts={})) is True
    assert dimensions_empty(FakeClient(counts={"apps": 5})) is False
