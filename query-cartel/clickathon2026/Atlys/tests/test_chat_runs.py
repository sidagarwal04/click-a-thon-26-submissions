"""Tests for background chat runs + transcript builder."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.chat_runs import _TranscriptBuilder  # noqa: E402
from service.chat_store import ChatStore, new_conversation_id  # noqa: E402


def test_transcript_builder_tools_and_text():
    b = _TranscriptBuilder([
        {"id": "u1", "role": "user", "content": "How many uploads?", "ts": "t0"},
    ])
    b.tool_call("c1", "aggregate_mcp_abc", {"table": "events"})
    b.tool_done("c1", "aggregate", ok=True)
    b.append_text("There were ")
    b.append_text("42.")
    b.finalize()
    roles = [m["role"] for m in b.messages]
    # Text that arrives after tools is relocated before the tool block.
    assert roles == ["user", "assistant", "tool"]
    assert b.messages[1]["content"] == "There were 42."
    assert b.messages[2]["toolName"] == "aggregate"
    assert b.messages[2]["status"] == "done"


def test_transcript_builder_dedupes_tool_fingerprint():
    b = _TranscriptBuilder([])
    b.tool_call("a", "db_schema", "{}")
    b.tool_call("b", "db_schema", "{}")
    assert sum(1 for m in b.messages if m.get("role") == "tool") == 1


def test_transcript_builder_skips_incomplete_stub_after_real_call():
    b = _TranscriptBuilder([])
    b.tool_call("a", "aggregate", '{"table":"document_uploaded"}')
    b.tool_done("a", "aggregate")
    b.append_text("Here's the answer.")
    b.tool_call("b", "aggregate", "{}")  # LibreChat empty stub
    b.finalize()
    tools = [m for m in b.messages if m.get("role") == "tool"]
    assert len(tools) == 1
    assert "document_uploaded" in (tools[0].get("args") or "")
    # Narration relocated before tools when it arrived after the tool block.
    roles = [m["role"] for m in b.messages]
    assert roles == ["assistant", "tool"]


def test_transcript_builder_relocate_text_before_tools():
    b = _TranscriptBuilder([
        {"id": "u1", "role": "user", "content": "q", "ts": "t0"},
    ])
    b.tool_call("t1", "db_schema", "{}")
    b.tool_done("t1", "db_schema")
    b.append_text("Let me look that up.")
    b.finalize()
    roles = [m["role"] for m in b.messages]
    assert roles == ["user", "assistant", "tool"]


def test_transcript_builder_splits_mashed_preamble_and_answer():
    """Buffered dump with no newline before 'Here are the numbers'."""
    b = _TranscriptBuilder([
        {"id": "u1", "role": "user", "content": "How many?", "ts": "t0"},
    ])
    b.tool_call("t1", "list_insights", "{}")
    b.tool_done("t1", "list_insights")
    b.tool_call("t2", "aggregate", '{"table":"document_uploaded"}')
    b.tool_done("t2", "aggregate")
    b.append_text(
        "Let me check the tables.I found document_uploaded."
        "Here are the numbers from the table:\n\n"
        "| Metric | Value |\n|---|---|\n| Uploads | **2,299** |\n"
    )
    b.finalize()
    roles = [m["role"] for m in b.messages]
    assert roles == ["user", "assistant", "tool", "tool", "assistant"]
    assert "Let me check" in b.messages[1]["content"]
    assert "Here are the numbers" in b.messages[4]["content"]
    assert "2,299" in b.messages[4]["content"]


def test_store_status_roundtrip(tmp_path):
    store = ChatStore(tmp_path)
    cid = new_conversation_id()
    store.create(cid)
    assert store.get_status(cid) == "idle"
    store.set_status(cid, "running")
    assert store.get_status(cid) == "running"
    store.save_messages(cid, [
        {"id": "u1", "role": "user", "content": "hi", "ts": "t0"},
    ], status="running")
    assert store.get_status(cid) == "running"
    meta = store.get(cid)
    assert meta["status"] == "running"
    store.save_messages(cid, [
        {"id": "u1", "role": "user", "content": "hi", "ts": "t0"},
        {"id": "a1", "role": "assistant", "content": "hello", "ts": "t1"},
    ], status="idle")
    assert store.get_status(cid) == "idle"


def test_save_preserves_status_when_omitted(tmp_path):
    store = ChatStore(tmp_path)
    cid = new_conversation_id()
    store.create(cid)
    store.set_status(cid, "running")
    store.save_messages(cid, [
        {"id": "u1", "role": "user", "content": "hi", "ts": "t0"},
    ])
    assert store.get_status(cid) == "running"
