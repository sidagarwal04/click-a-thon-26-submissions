"""Unit tests — event bus (Part 9: test_bus.py).

Ordering, depth-first dispatch, at-least-once persistence (in-memory store).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.bus import EventBus  # noqa: E402
from service.events import Event, new_event  # noqa: E402
from service.store import DryRunStore  # noqa: E402


def test_handlers_called_in_registration_order():
    store = DryRunStore()
    bus = EventBus(store=store)
    order = []

    def h1(e):
        order.append("h1")

    def h2(e):
        order.append("h2")

    bus.register("evt", h1)
    bus.register("evt", h2)
    bus.emit(new_event("evt", "agg", "test"))
    assert order == ["h1", "h2"]


def test_depth_first_dispatch():
    store = DryRunStore()
    bus = EventBus(store=store)
    order = []

    def parent(e):
        order.append("parent")
        bus.emit(new_event("child", e.aggregate_id, "test"))

    def child(e):
        order.append("child")

    bus.register("parent", parent)
    bus.register("child", child)
    bus.emit(new_event("parent", "agg", "test"))
    # depth-first: parent handler runs, then the child it emitted, before the
    # parent's event is done
    assert order == ["parent", "child"]


def test_persistence_at_least_once():
    store = DryRunStore()
    bus = EventBus(store=store)
    bus.emit(new_event("evt", "agg", "test"))
    bus.emit(new_event("evt", "agg", "test"))
    assert store.row_count("atlys.event_log") == 2


def test_version_stamping():
    store = DryRunStore()
    bus = EventBus(store=store)
    e = new_event("evt", "agg", "test")
    bus.emit(e)
    assert e.version == 1
    e2 = new_event("evt", "agg", "test")
    bus.emit(e2)
    assert e2.version == 2


def test_event_log_row_shape():
    store = DryRunStore()
    bus = EventBus(store=store)
    e = new_event("spec.run.requested", "spec/01_x", "mcp", {"spec_dir": "01_x"})
    bus.emit(e)
    rows = store.query_rows("SELECT event_type, aggregate_id, actor, trace_id FROM atlys.event_log")
    assert rows[0]["event_type"] == "spec.run.requested"
    assert rows[0]["aggregate_id"] == "spec/01_x"
