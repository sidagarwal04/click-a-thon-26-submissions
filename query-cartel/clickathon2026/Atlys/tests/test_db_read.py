"""Unit tests — safe generic DB read helpers for the chat agent."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from service import db_read
from service.db_read import DbReadError
from service.mcp_server import AtlysMcpServer
from service.store import DryRunStore


def _store_with_events() -> DryRunStore:
    store = DryRunStore()
    # Insert alone registers schema (CREATE parser is best-effort only).
    store.insert(
        "events",
        ["event", "user_id", "destination", "amount", "ts"],
        [
            ["view", "u1", "FR", 0.0, "2026-01-01"],
            ["view", "u2", "FR", 0.0, "2026-01-01"],
            ["view", "u3", "DE", 0.0, "2026-01-02"],
            ["pay", "u1", "FR", 10.5, "2026-01-03"],
            ["pay", "u2", "FR", 20.0, "2026-01-03"],
        ],
    )
    # Restore real types for numeric metric checks (insert defaults to String).
    store._schemas["events"]["amount"] = "Float64"
    return store


def test_db_schema_list_and_describe():
    store = _store_with_events()
    listed = db_read.db_schema(store)
    assert listed["count"] >= 1
    names = {t["name"] for t in listed["tables"]}
    assert "events" in names

    desc = db_read.db_schema(store, table="events")
    col_names = {c["name"] for c in desc["columns"]}
    assert {"event", "user_id", "destination", "amount"} <= col_names


def test_db_schema_unknown_table():
    store = DryRunStore()
    with pytest.raises(DbReadError) as ei:
        db_read.db_schema(store, table="missing_table")
    assert ei.value.code == "NOT_FOUND"


def test_db_schema_rejects_injection_and_system():
    store = DryRunStore()
    with pytest.raises(DbReadError):
        db_read.db_schema(store, table="events; DROP TABLE x")
    with pytest.raises(DbReadError) as ei:
        db_read.db_schema(store, table="system.users")
    assert ei.value.code == "DB_NOT_ALLOWED"


def test_table_stats():
    store = _store_with_events()
    out = db_read.table_stats(store, "events", approximate=False)
    assert out["count"] == 1
    assert out["tables"][0]["row_count"] == 5
    assert out["tables"][0]["column_count"] >= 4


def test_table_stats_max_tables():
    store = _store_with_events()
    with pytest.raises(DbReadError):
        db_read.table_stats(store, [f"t{i}" for i in range(25)])


def test_aggregate_count_and_group_by():
    store = _store_with_events()
    out = db_read.aggregate(
        store,
        table="events",
        metrics=[{"fn": "count"}, {"fn": "uniq", "column": "user_id"}],
        group_by=["event"],
        order_by=[{"by": "count", "dir": "desc"}],
    )
    assert out["row_count"] == 2
    by_event = {r["event"]: r for r in out["rows"]}
    assert by_event["view"]["count"] == 3
    assert by_event["view"]["uniq_user_id"] == 3
    assert by_event["pay"]["count"] == 2
    assert "SETTINGS" not in out["sql"]
    assert "readonly" not in out["sql"]


def test_aggregate_filter_eq_and_like():
    store = _store_with_events()
    out = db_read.aggregate(
        store,
        table="events",
        metrics=[{"fn": "count", "alias": "n"}],
        filters=[{"column": "destination", "op": "eq", "value": "FR"}],
    )
    assert out["rows"][0]["n"] == 4

    out2 = db_read.aggregate(
        store,
        table="events",
        metrics=[{"fn": "count", "alias": "n"}],
        filters=[{"column": "event", "op": "like", "value": "pa%"}],
    )
    assert out2["rows"][0]["n"] == 2


def test_aggregate_accepts_sql_operator_aliases():
    store = _store_with_events()
    # >= / < should normalize to gte / lt (common LLM mistake)
    out = db_read.aggregate(
        store,
        table="events",
        metrics=[{"fn": "count", "alias": "n"}],
        filters=[
            {"column": "amount", "op": ">=", "value": 10},
            {"column": "amount", "op": "<", "value": 20},
        ],
    )
    assert out["rows"][0]["n"] == 1  # only 10.5
    assert "amount >= 10" in out["sql"]
    assert "amount < 20" in out["sql"]

    out_eq = db_read.aggregate(
        store,
        table="events",
        metrics=[{"fn": "count", "alias": "n"}],
        filters=[{"column": "destination", "op": "=", "value": "DE"}],
    )
    assert out_eq["rows"][0]["n"] == 1


def test_db_schema_multiple_tables_one_call():
    store = _store_with_events()
    store.insert("orders", ["id", "total"], [["1", 9], ["2", 11]])
    out = db_read.db_schema(store, table=["events", "orders"])
    assert out["count"] == 2
    by_name = {t["table"]: t for t in out["tables"]}
    assert "event" in {c["name"] for c in by_name["events"]["columns"]}
    assert "total" in {c["name"] for c in by_name["orders"]["columns"]}

    # comma-separated + MCP tables alias
    out2 = db_read.db_schema(store, table="events, orders")
    assert out2["count"] == 2
    mcp = AtlysMcpServer(None, None, None, None, store, tracer=None)
    out3 = mcp._dispatch("db_schema", {"tables": ["events", "orders"]})
    assert out3["count"] == 2


def test_aggregate_rejects_unknown_column_and_clamps_limit():
    store = _store_with_events()
    with pytest.raises(DbReadError) as ei:
        db_read.aggregate(
            store, table="events",
            metrics=[{"fn": "count"}],
            group_by=["not_a_column"],
        )
    assert ei.value.code == "BAD_ARGUMENT"

    sql, meta = db_read.build_aggregate_sql(
        store,
        table="events",
        metrics=[{"fn": "count"}],
        limit=10_000,
    )
    assert meta["limit"] == db_read.AGGREGATE_MAX_LIMIT
    assert f"LIMIT {db_read.AGGREGATE_MAX_LIMIT}" in sql
    assert "readonly = 1" in sql


def test_aggregate_numeric_and_p50():
    store = _store_with_events()
    out = db_read.aggregate(
        store,
        table="events",
        metrics=[{"fn": "sum", "column": "amount"}, {"fn": "p50", "column": "amount"}],
        filters=[{"column": "event", "op": "eq", "value": "pay"}],
    )
    assert out["rows"][0]["sum_amount"] == 30.5
    assert out["rows"][0]["p50_amount"] in (10.5, 20.0)


def test_aggregate_rejects_meta_without_flag():
    store = DryRunStore()
    store.command("CREATE TABLE IF NOT EXISTS pending_runs (run_id String) ENGINE = Memory")
    with pytest.raises(DbReadError) as ei:
        db_read.aggregate(
            store,
            table="meta.pending_runs",
            metrics=[{"fn": "count"}],
            include_meta=False,
        )
    # dry-run: meta.pending_runs parses as db=meta — DB_NOT_ALLOWED without flag
    assert ei.value.code == "DB_NOT_ALLOWED"


def test_sample_rows():
    store = _store_with_events()
    out = db_read.sample_rows(
        store,
        table="events",
        columns=["event", "user_id"],
        filters=[{"column": "event", "op": "eq", "value": "pay"}],
        limit=5,
    )
    assert out["row_count"] == 2
    assert set(out["columns"]) == {"event", "user_id"}
    assert all(r["event"] == "pay" for r in out["rows"])


def test_sample_rows_clamps_limit():
    store = _store_with_events()
    out = db_read.sample_rows(store, table="events", limit=999)
    assert out["limit"] == db_read.SAMPLE_MAX_LIMIT


def test_mcp_dispatch_db_tools():
    store = _store_with_events()
    mcp = AtlysMcpServer(None, None, None, None, store, tracer=None)
    schema = mcp._dispatch("db_schema", {})
    assert schema["count"] >= 1
    stats = mcp._dispatch("table_stats", {"table": "events", "approximate": False})
    assert stats["tables"][0]["row_count"] == 5
    agg = mcp._dispatch(
        "aggregate",
        {"table": "events", "metrics": [{"fn": "count"}], "group_by": ["event"]},
    )
    assert agg["row_count"] == 2
    sample = mcp._dispatch("sample_rows", {"table": "events", "limit": 2})
    assert sample["row_count"] == 2
    bad = mcp._dispatch("aggregate", {"table": "nope", "metrics": [{"fn": "count"}]})
    assert bad.get("code") == "NOT_FOUND"
