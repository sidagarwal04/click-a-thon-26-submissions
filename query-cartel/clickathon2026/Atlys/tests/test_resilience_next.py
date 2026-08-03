"""Tests for insight↔run correlation, upload caps, partial-load recovery."""
from __future__ import annotations

import asyncio
import io
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.agents.context import ContextAgent  # noqa: E402
from service.agents.instrumentation import InstrumentationAgent  # noqa: E402
from service.api import MAX_SPEC_BYTES, upload_spec  # noqa: E402
from service.app import DDL_STATEMENTS  # noqa: E402
from service.bus import EventBus  # noqa: E402
from service.mcp_server import AtlysMcpServer  # noqa: E402
from service.settings import Settings  # noqa: E402
from service.store import DryRunStore  # noqa: E402


def _boot():
    settings = Settings()
    store = DryRunStore()
    for ddl in DDL_STATEMENTS:
        store.command(ddl)
    bus = EventBus(store=store, persist=True)
    instr = InstrumentationAgent(store, bus, settings)
    ctx = ContextAgent(store, bus, settings)
    bus.register_many({
        "spec.run.requested": [instr.on_run_requested],
        "schema.approved": [instr.on_approved],
        "schema.rejected": [instr.on_rejected],
        "schema.created": [ctx.on_schema_created],
    })
    ctx.seed_if_empty()
    return settings, store, bus, instr


def test_ingest_events_disabled_and_unlisted():
    settings, store, bus, instr = _boot()
    mcp = AtlysMcpServer(bus, instr, None, None, store, settings=settings)
    server = mcp.build_server()

    result = mcp._dispatch("ingest_events", {"table": "x", "rows": [[1]]})
    assert result.get("code") == "TOOL_DISABLED"

    names = []
    mgr = getattr(server, "_tool_manager", None)
    if mgr is not None and hasattr(mgr, "_tools"):
        names = list(mgr._tools.keys())
    elif mgr is not None and hasattr(mgr, "list_tools"):
        tools = asyncio.run(mgr.list_tools())
        names = [t.name for t in tools]
    if names:
        assert "ingest_events" not in names
        assert "run_spec" in names


def test_latest_insight_for_run_matches_trace_not_newest():
    settings, store, bus, instr = _boot()
    mcp = AtlysMcpServer(bus, instr, None, None, store, settings=settings)

    run_a, run_b = str(uuid.uuid4()), str(uuid.uuid4())
    store.insert(
        "meta.pending_runs",
        ["run_id", "state", "spec_dir", "schema_card", "trace_id", "runner_token"],
        [
            [run_a, "approved", "01_express_checkout", "{}", "trace-aaa", ""],
            [run_b, "approved", "02_group_family", "{}", "trace-bbb", ""],
        ],
    )
    store.insert(
        "meta.insights",
        ["spec", "title", "summary", "confidence", "evidence", "trace_id"],
        [
            ["01_express_checkout", "A", "summary-a", "high", "[]", "trace-aaa"],
            ["02_group_family", "B", "summary-b", "high", "[]", "trace-bbb"],
        ],
    )
    got = mcp._latest_insight_for_run(run_a)
    assert got is not None
    assert got["title"] == "A"
    assert got["trace_id"] == "trace-aaa"
    assert mcp._latest_insight_for_run(run_b)["title"] == "B"


def test_partial_load_wipes_stale_rows_before_reload():
    _, store, _, instr = _boot()
    table = "express_checkout_events"
    ddl = (
        "CREATE TABLE IF NOT EXISTS express_checkout_events ("
        "id String, event String) ENGINE = MergeTree ORDER BY id"
    )
    store.command(ddl)
    store.insert(table, ["id", "event"], [["1", "a"], ["2", "a"]])
    events = [{"id": "1", "event": "a"}, {"id": "2", "event": "a"}, {"id": "3", "event": "b"}]
    n = instr._load_events_idempotent(
        table, ddl, ["id", "event"],
        {"id": "String", "event": "String"},
        events, existing=2, matched=True,
    )
    assert n == 3
    assert store.row_count(table) == 3


def test_partial_load_wipes_on_insert_failure():
    _, store, _, instr = _boot()
    table = "express_checkout_events"
    ddl = (
        "CREATE TABLE IF NOT EXISTS express_checkout_events ("
        "id String, event String) ENGINE = MergeTree ORDER BY id"
    )
    store.command(ddl)
    events = [{"id": "1", "event": "a"}]

    def _boom(*_a, **_k):
        # Use the real insert on a side channel — patch replaces store.insert,
        # so write partial rows via the underlying table map.
        store._tables[table].append({"id": "partial", "event": "x"})
        raise RuntimeError("insert exploded")

    with patch.object(store, "insert", side_effect=_boom):
        with pytest.raises(RuntimeError, match="insert exploded"):
            instr._load_events_idempotent(
                table, ddl, ["id", "event"],
                {"id": "String", "event": "String"},
                events, existing=0, matched=True,
            )
    assert store.row_count(table) == 0


def test_upload_rejects_bad_extension_and_oversize(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLYS_ROOT", str(tmp_path))
    (tmp_path / "specs").mkdir(parents=True, exist_ok=True)

    from service.app import create_app
    create_app(Settings())

    bad_events = UploadFile(filename="events.txt", file=io.BytesIO(b'{"event":"x"}\n'))
    spec = UploadFile(filename="spec.md", file=io.BytesIO(b"# hi\n"))
    with pytest.raises(Exception) as ei:
        asyncio.run(upload_spec(spec=spec, events=bad_events, feature="demo"))
    assert getattr(ei.value, "status_code", None) == 400

    huge = UploadFile(filename="spec.md", file=io.BytesIO(b"x" * (MAX_SPEC_BYTES + 1)))
    events = UploadFile(filename="events.ndjson", file=io.BytesIO(b'{"event":"ok"}\n'))
    with pytest.raises(Exception) as ei2:
        asyncio.run(upload_spec(spec=huge, events=events, feature="demo2"))
    assert getattr(ei2.value, "status_code", None) == 413


def test_upload_accepts_small_spec(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLYS_ROOT", str(tmp_path))
    (tmp_path / "specs").mkdir(parents=True, exist_ok=True)

    from service.app import create_app
    create_app(Settings())

    spec = UploadFile(filename="spec.md", file=io.BytesIO(b"# Feature\n"))
    events = UploadFile(
        filename="events.ndjson",
        file=io.BytesIO(
            b'{"event":"shown","id":"1","timestamp":"2026-01-01T00:00:00","user_id":"u"}\n'
        ),
    )
    out = asyncio.run(upload_spec(spec=spec, events=events, feature="upload_demo"))
    assert out["feature"] == "upload_demo"
    assert out["event_lines"] == 1
    assert (tmp_path / "specs" / "upload_demo" / "events.ndjson").exists()
