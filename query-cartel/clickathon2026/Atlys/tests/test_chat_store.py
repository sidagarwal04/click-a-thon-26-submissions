"""Tests for Atlys-owned chat transcript store."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.chat_store import ChatStore, is_valid_id, new_conversation_id  # noqa: E402


def test_new_id_is_uuid():
    assert is_valid_id(new_conversation_id())


def test_create_list_save_roundtrip(tmp_path):
    store = ChatStore(tmp_path)
    cid = new_conversation_id()
    created = store.create(cid)
    assert created["id"] == cid
    assert store.list() == []  # empty shells hidden from sidebar

    saved = store.save_messages(cid, [
        {"id": "welcome", "role": "assistant", "content": "hi", "ts": "2026-01-01T00:00:00Z"},
        {"id": "u1", "role": "user", "content": "Run express checkout", "ts": "2026-01-01T00:01:00Z"},
        {"id": "a1", "role": "assistant", "content": "Sure.", "ts": "2026-01-01T00:02:00Z"},
    ])
    assert saved["title"] == "Run express checkout"
    assert saved["messageCount"] == 2

    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["id"] == cid
    assert listed[0]["title"] == "Run express checkout"

    msgs = store.get_messages(cid)
    assert [m["id"] for m in msgs] == ["u1", "a1"]


def test_save_creates_missing_conversation(tmp_path):
    store = ChatStore(tmp_path)
    cid = new_conversation_id()
    store.save_messages(cid, [
        {"role": "user", "content": "Hello there friend this is a somewhat long title that should truncate nicely for the sidebar display"},
    ])
    meta = store.get(cid)
    assert meta is not None
    assert meta["title"].endswith("…")
    assert len(meta["title"]) <= 72


def test_tool_messages_persist_args_and_result(tmp_path):
    store = ChatStore(tmp_path)
    cid = new_conversation_id()
    store.save_messages(cid, [
        {"id": "u1", "role": "user", "content": "tables?", "ts": "2026-01-01T00:00:00Z"},
        {
            "id": "tc1",
            "role": "tool",
            "toolPhase": "call",
            "toolName": "db_schema",
            "args": "{}",
            "content": "",
            "status": "done",
            "ts": "2026-01-01T00:00:01Z",
        },
        {
            "id": "tr1",
            "role": "tool",
            "toolPhase": "result",
            "toolName": "db_schema",
            "content": "",
            "result": '{"count": 2}',
            "status": "done",
            "callId": "tc1",
            "ts": "2026-01-01T00:00:02Z",
        },
        {"id": "a1", "role": "assistant", "content": "Two tables.", "ts": "2026-01-01T00:00:03Z"},
    ])
    msgs = store.get_messages(cid)
    assert [m["role"] for m in msgs] == ["user", "tool", "tool", "assistant"]
    assert msgs[1]["toolName"] == "db_schema"
    assert msgs[1]["toolPhase"] == "call"
    assert msgs[1]["args"] == "{}"
    assert msgs[2]["toolPhase"] == "result"
    assert msgs[2]["result"] == '{"count": 2}'
    assert msgs[2]["callId"] == "tc1"
