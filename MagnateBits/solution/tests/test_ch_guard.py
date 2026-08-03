"""The read-only guard, in both directions.

`run_select` is the Analytics Agent's only door into the database, so the guard has to
be exactly as wide as the reads we need and not one keyword wider. Two failure modes
are equally bad: a false reject (`SHOW CREATE TABLE` was dead for a week because the
word `create` is in the forbidden list, which is why `create_statement()` never worked),
and a false accept (anything that mutates or perturbs the server).

The rejection tests never touch a server -- they must hold even with ClickHouse down.
"""

from __future__ import annotations

import pytest

import ch as ch_mod
from ch import CH, ReadOnlyViolation


@pytest.fixture(scope="module")
def offline() -> CH:
    """A CH with no connection: enough to exercise the guard, which runs before I/O."""
    return CH.__new__(CH)


# --- must be rejected -----------------------------------------------------

REJECTED = [
    "SYSTEM DROP CACHE",
    "SYSTEM FLUSH LOGS",
    "SYSTEM RELOAD DICTIONARIES",
    "DROP TABLE atlys.f_events",
    "DROP DATABASE atlys",
    "CREATE TABLE t (a Int64) ENGINE = Memory",
    "TRUNCATE TABLE atlys.f_events",
    "INSERT INTO t VALUES (1)",
    "ALTER TABLE t DELETE WHERE 1",
    "OPTIMIZE TABLE t FINAL",
    "SELECT 1; DROP TABLE t",
    # The SHOW CREATE allowance must not become a hole: it is anchored at both ends,
    # so nothing may ride along after the object name.
    "SHOW CREATE TABLE t FORMAT Null, DROP TABLE t",
    "SHOW CREATE TABLE (SELECT 1) DROP TABLE t",
]


@pytest.mark.parametrize("sql", REJECTED, ids=lambda s: s[:40])
def test_mutating_statements_are_rejected(offline: CH, sql: str) -> None:
    with pytest.raises(ReadOnlyViolation):
        offline.run_select(sql)


def test_show_create_allowance_is_checked_before_the_keyword_scan() -> None:
    """The allowance is a whole-statement match, not a prefix a payload can follow."""
    assert ch_mod._SHOW_CREATE.match("SHOW CREATE TABLE atlys.f_events")
    assert ch_mod._SHOW_CREATE.match("show create table t")
    assert ch_mod._SHOW_CREATE.match("SHOW CREATE VIEW atlys.mv_x")
    assert not ch_mod._SHOW_CREATE.match("SHOW CREATE TABLE t; DROP TABLE t")
    assert not ch_mod._SHOW_CREATE.match("CREATE TABLE t (a Int64) ENGINE = Memory")
    assert not ch_mod._SHOW_CREATE.match("SELECT 'SHOW CREATE TABLE t'")


def test_unsafe_query_id_is_rejected(offline: CH) -> None:
    with pytest.raises(ReadOnlyViolation):
        offline.run_select("SELECT 1", query_id="abc' OR '1'='1")


# --- must be accepted -----------------------------------------------------


@pytest.fixture(scope="module")
def live() -> CH:
    try:
        client = CH()
        client.run_select("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ClickHouse not reachable: {exc}")
    return client


def test_show_create_table_returns_ddl(live: CH) -> None:
    """The T1 regression: `create_statement()` was dead, and silently so."""
    tables = [t for t in live.list_tables() if not t.startswith("__")]
    if not tables:
        pytest.skip("no tables in the database")
    ddl = live.create_statement(tables[0])
    assert "CREATE TABLE" in ddl.upper()
    assert tables[0] in ddl


def test_system_tables_are_readable(live: CH) -> None:
    """`system` is deliberately not a forbidden keyword; introspection depends on it."""
    rows = live.run_select("SELECT count() AS n FROM system.tables", max_rows=1)
    assert rows and int(rows[0]["n"]) > 0


def test_query_stats_returns_measured_cost(live: CH) -> None:
    """A query tagged with a query_id can be costed from system.query_log."""
    import uuid

    qid = f"atlys-test-{uuid.uuid4().hex[:10]}"
    live.run_select(
        "SELECT count() AS n FROM (SELECT number FROM system.numbers LIMIT 50000)",
        query_id=qid,
    )
    stats = live.query_stats(qid)
    if not stats:
        pytest.skip("system.query_log did not materialise the row in time")
    assert set(stats) == {"read_rows", "read_bytes", "query_duration_ms", "memory_usage"}
    assert stats["read_rows"] > 0
    assert stats["read_bytes"] > 0
