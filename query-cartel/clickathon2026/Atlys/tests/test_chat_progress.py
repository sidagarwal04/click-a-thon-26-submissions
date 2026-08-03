"""Unit tests for chat progress hub + tool budget."""
from __future__ import annotations

from service.chat_progress import ChatProgressHub


def test_tool_budget_resets_on_new_series():
    hub = ChatProgressHub()
    hub.begin_series("c1", limit=2, extend=False)
    hub.activate("c1")

    ok1, info1 = hub.try_consume_tool("c1")
    ok2, info2 = hub.try_consume_tool("c1")
    ok3, info3 = hub.try_consume_tool("c1")

    assert ok1 and info1["used"] == 1
    assert ok2 and info2["used"] == 2
    assert not ok3
    assert info3["used"] == 2
    assert info3["limit"] == 2

    hub.begin_series("c1", limit=2, extend=False)
    ok4, info4 = hub.try_consume_tool("c1")
    assert ok4 and info4["used"] == 1


def test_tool_budget_extend_keeps_count():
    hub = ChatProgressHub()
    hub.begin_series("c1", limit=3, extend=False)
    hub.activate("c1")
    hub.try_consume_tool("c1")
    hub.try_consume_tool("c1")

    hub.begin_series("c1", limit=3, extend=True)
    ok, info = hub.try_consume_tool("c1")
    assert ok and info["used"] == 3
    blocked, _ = hub.try_consume_tool("c1")
    assert not blocked


def test_unscoped_tools_allowed_when_no_active_stream():
    hub = ChatProgressHub()
    ok, info = hub.try_consume_tool()
    assert ok
    assert info.get("unscoped") is True


def test_single_active_fallback_without_explicit_id():
    hub = ChatProgressHub()
    hub.begin_series("c1", limit=5, extend=False)
    hub.activate("c1")
    ok, info = hub.try_consume_tool()
    assert ok and info["conversation_id"] == "c1" and info["used"] == 1
    hub.publish({"type": "tool_call", "id": "t1", "name": "db_schema"})
    events, _ = hub.poll_since("c1", 0)
    assert len(events) == 1
    assert events[0]["targets"] == ["c1"]


def test_two_active_chats_no_crosstalk():
    """Two tabs / two different cids: budgets and events stay isolated."""
    hub = ChatProgressHub()
    hub.begin_series("c1", limit=3, extend=False)
    hub.begin_series("c2", limit=3, extend=False)
    hub.activate("c1")
    hub.activate("c2")

    ok1, info1 = hub.try_consume_tool("c1")
    ok2, info2 = hub.try_consume_tool("c2")
    assert ok1 and info1["conversation_id"] == "c1" and info1["used"] == 1
    assert ok2 and info2["conversation_id"] == "c2" and info2["used"] == 1

    hub.publish({"type": "tool_call", "id": "a", "name": "db_schema"}, conversation_id="c1")
    hub.publish({"type": "tool_call", "id": "b", "name": "aggregate"}, conversation_id="c2")

    e1, _ = hub.poll_since("c1", 0)
    e2, _ = hub.poll_since("c2", 0)
    assert [e["id"] for e in e1] == ["a"]
    assert [e["id"] for e in e2] == ["b"]
    assert e1[0]["targets"] == ["c1"]
    assert e2[0]["targets"] == ["c2"]

    # Exhaust c1 only — c2 still has budget.
    hub.try_consume_tool("c1")
    hub.try_consume_tool("c1")
    blocked, binfo = hub.try_consume_tool("c1")
    assert not blocked and binfo["conversation_id"] == "c1"
    ok3, info3 = hub.try_consume_tool("c2")
    assert ok3 and info3["used"] == 2


def test_ambiguous_unscoped_does_not_broadcast_or_couple_budgets():
    hub = ChatProgressHub()
    hub.begin_series("c1", limit=2, extend=False)
    hub.begin_series("c2", limit=2, extend=False)
    hub.activate("c1")
    hub.activate("c2")

    ok, info = hub.try_consume_tool()  # no owner
    assert ok and info.get("ambiguous") is True
    hub.publish({"type": "tool_call", "id": "x", "name": "db_schema"})  # dropped
    assert hub.poll_since("c1", 0)[0] == []
    assert hub.poll_since("c2", 0)[0] == []
    # Budgets untouched
    ok1, i1 = hub.try_consume_tool("c1")
    ok2, i2 = hub.try_consume_tool("c2")
    assert ok1 and i1["used"] == 1
    assert ok2 and i2["used"] == 1


def test_activate_refcount():
    hub = ChatProgressHub()
    hub.activate("c1")
    hub.activate("c1")
    hub.deactivate("c1")
    assert hub.active_ids() == ["c1"]
    hub.deactivate("c1")
    assert hub.active_ids() == []
