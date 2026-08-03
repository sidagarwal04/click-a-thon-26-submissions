"""Tests for docs/inspect-tab-plan.md — Wave A (API filters), Wave B (event
limits), Wave C (trace_id linkage). Runs entirely on the DryRunStore.

Covers:
  - bootstrap DDL carries TTLs (event_log 90d, pending_runs 180d)
  - bus per-run event cap aborts a run with run.aborted, persist-only after
  - tool.called events are exempt from the cap
  - bus.emitted mirror is bounded
  - mcp_server._tool_called carries the tracer trace_id (W0)
  - explore:* traces for read-only tools outside a run (W2)
  - /api/event-log filters (run_id) + /api/runs registry
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.app import DDL_STATEMENTS  # noqa: E402
from service.bus import EventBus, MIRROR_MAXLEN  # noqa: E402
from service.events import RUN_ABORTED, TOOL_CALLED, new_event  # noqa: E402
from service.store import DryRunStore  # noqa: E402


# ---------------------------------------------------------------------------
# Wave B — event-log TTL
# ---------------------------------------------------------------------------

def test_event_log_ttl_in_bootstrap_ddl():
    ddl = "\n".join(DDL_STATEMENTS)
    assert "atlys.event_log" in ddl
    assert "TTL created_at + INTERVAL 90 DAY" in ddl
    assert "meta.pending_runs" in ddl
    assert "TTL created_at + INTERVAL 180 DAY" in ddl
    # retroactive TTL applied to existing deployments
    assert "ALTER TABLE atlys.event_log MODIFY TTL created_at + INTERVAL 90 DAY" in ddl


# ---------------------------------------------------------------------------
# Wave B — bus per-run event cap
# ---------------------------------------------------------------------------

def _run_events(bus, n, run_id="r1", trace="t1", event_type="boom"):
    """Emit n events that carry a run_id payload."""
    for _ in range(n):
        bus.emit(new_event(
            event_type, f"spec/{run_id}", "test",
            payload={"run_id": run_id}, trace_id=trace,
        ))


def test_bus_aborts_run_over_cap():
    store = DryRunStore()
    bus = EventBus(store=store, max_events_per_run=5)
    _run_events(bus, 20)
    rows = store.query_rows("SELECT event_type FROM atlys.event_log")
    types = [r["event_type"] for r in rows]
    # 20 events + 1 synthetic run.aborted
    assert RUN_ABORTED in types
    assert len(types) == 21


def test_bus_cap_is_per_run_id_not_aggregate():
    """Re-running the same spec must not hit the previous run's cap."""
    store = DryRunStore()
    bus = EventBus(store=store, max_events_per_run=3)
    _run_events(bus, 5, run_id="run-A", trace="tA")   # aborts run-A
    # same aggregate_id (spec/run-B is a different key) — must still dispatch
    dispatched = []
    bus.register("boom", lambda e: dispatched.append(e))
    _run_events(bus, 2, run_id="run-B", trace="tB")
    assert len(dispatched) == 2


def test_bus_tool_called_exempt_from_cap():
    store = DryRunStore()
    bus = EventBus(store=store, max_events_per_run=3)
    _run_events(bus, 5)  # consume the run budget
    called = []
    bus.register(TOOL_CALLED, lambda e: called.append(e))
    for _ in range(10):
        bus.emit(new_event(
            TOOL_CALLED, "mcp/db_schema", "mcp",
            payload={"tool": "db_schema"}, trace_id="t1",
        ))
    assert len(called) == 10  # tools are never capped


def test_bus_aborted_run_persists_but_does_not_dispatch():
    store = DryRunStore()
    bus = EventBus(store=store, max_events_per_run=2)
    dispatched = []
    bus.register("boom", lambda e: dispatched.append(e))
    _run_events(bus, 4)
    assert len(dispatched) == 2  # only events 1–2 dispatched
    rows = store.query_rows("SELECT count() AS c FROM atlys.event_log")
    assert rows[0]["c"] == 4 + 1  # 4 events + run.aborted, all persisted


def test_bus_emitted_mirror_bounded():
    store = DryRunStore()
    bus = EventBus(store=store)
    for i in range(MIRROR_MAXLEN + 500):
        bus.emit(new_event("evt", f"agg{i}", "test"))
    assert len(bus.emitted) == MIRROR_MAXLEN


# ---------------------------------------------------------------------------
# Wave C — tool.called trace_id + explore traces (via mcp_server)
# ---------------------------------------------------------------------------

class _FakeTracer:
    def __init__(self):
        self.trace_id = "trace-fixed"

    def start(self, name, session_id=None):
        self.trace_id = f"trace-{name}"
        return self.trace_id

    def span(self, name, **meta):
        import contextlib
        return contextlib.nullcontext()


def _server():
    from service.mcp_server import AtlysMcpServer  # noqa: PLC0415
    store = DryRunStore()
    bus = EventBus(store=store)
    tracer = _FakeTracer()
    server = AtlysMcpServer(bus, None, None, None, store, tracer=tracer)
    return server, bus, store, tracer


def test_tool_called_carries_trace_id():
    server, bus, store, tracer = _server()
    server._tool_called("db_schema", {"table": "x"})
    rows = store.query_rows(
        "SELECT trace_id, payload FROM atlys.event_log WHERE event_type = 'tool.called'"
    )
    assert rows, "tool.called event should be persisted"
    assert rows[0]["trace_id"] == tracer.trace_id


def test_tool_called_with_explicit_trace_id_wins():
    server, bus, store, tracer = _server()
    server._tool_called("aggregate", {"table": "x"}, trace_id="explicit")
    rows = store.query_rows(
        "SELECT trace_id FROM atlys.event_log WHERE event_type = 'tool.called'"
    )
    assert rows[0]["trace_id"] == "explicit"


def test_tool_called_synthesizes_trace_id_without_tracer():
    """Guard: tool.called must never persist an empty trace_id."""
    from service.mcp_server import AtlysMcpServer  # noqa: PLC0415
    store = DryRunStore()
    bus = EventBus(store=store)
    server = AtlysMcpServer(bus, None, None, None, store, tracer=None)
    server._tool_called("aggregate", {"table": "x"})
    rows = store.query_rows(
        "SELECT trace_id FROM atlys.event_log WHERE event_type = 'tool.called'"
    )
    assert rows, "tool.called event should be persisted"
    assert rows[0]["trace_id"].startswith("synthetic-"), rows[0]["trace_id"]
    assert len(rows[0]["trace_id"]) > len("synthetic-")


def test_tool_called_synthesizes_when_tracer_trace_id_empty():
    """Guard also fires when a tracer exists but has no active trace yet."""
    from service.mcp_server import AtlysMcpServer  # noqa: PLC0415
    store = DryRunStore()
    bus = EventBus(store=store)
    tracer = _FakeTracer()
    tracer.trace_id = ""
    server = AtlysMcpServer(bus, None, None, None, store, tracer=tracer)
    server._tool_called("db_schema", {"table": "x"})
    rows = store.query_rows(
        "SELECT trace_id FROM atlys.event_log WHERE event_type = 'tool.called'"
    )
    assert rows[0]["trace_id"].startswith("synthetic-")


def test_healthz_not_shadowed_by_static_mount():
    """Register /healthz BEFORE the SPA catch-all static mount (404 fix)."""
    from service.app import create_app  # noqa: PLC0415
    from service.settings import Settings  # noqa: PLC0415
    app = create_app(Settings(dry_run=True))
    routes = list(app.routes)
    paths = [getattr(r, "path", None) for r in routes]
    healthz_idx = paths.index("/healthz")
    # the catch-all Mount at "/" (Starlette stores its path as "") must come
    # after /healthz in match order — otherwise it shadows /healthz → 404
    mount_idx = next(
        i for i, r in enumerate(routes) if r.__class__.__name__ == "Mount"
    )
    assert healthz_idx < mount_idx
    # and the explicit / route (spa_root) must also not precede /healthz
    spa_idx = paths.index("/")
    assert healthz_idx < spa_idx


def test_explore_trace_starts_for_read_tool():
    server, bus, store, tracer = _server()
    server._maybe_start_explore("aggregate")
    assert tracer.trace_id == "trace-explore:aggregate"


def test_no_explore_trace_for_pipeline_tool():
    server, bus, store, tracer = _server()
    server._maybe_start_explore("run_spec")
    assert tracer.trace_id == "trace-fixed"  # untouched


def test_no_explore_trace_while_run_in_flight():
    server, bus, store, tracer = _server()
    server._run_in_flight = True
    server._maybe_start_explore("aggregate")
    assert tracer.trace_id == "trace-fixed"


# ---------------------------------------------------------------------------
# Wave A — API filters (event-log run_id + runs registry)
# ---------------------------------------------------------------------------

def _seed_store():
    """Seed a DryRunStore with a fake run's events + pending_runs row."""
    from service.app import AppState  # noqa: PLC0415
    from service.settings import Settings  # noqa: PLC0415
    store = DryRunStore()
    store.insert(
        "atlys.event_log",
        ["event_id", "event_type", "aggregate_id", "version", "actor",
         "payload", "trace_id", "created_at"],
        [
            ["e1", "spec.run.requested", "spec/x", 1, "mcp",
             '{"spec_dir": "x", "run_id": "run-1"}', "t-run1", "2026-01-01 00:00:00"],
            ["e2", "insight.created", "spec/x", 2, "analytics",
             '{"feature": "x"}', "t-run1", "2026-01-01 00:00:05"],
            ["e3", "tool.called", "mcp/aggregate", 1, "mcp",
             '{"tool": "aggregate", "arguments": {"table": "x"}}', "", "2026-01-01 00:00:03"],
        ],
    )
    store.insert(
        "meta.pending_runs",
        ["run_id", "state", "spec_dir", "schema_card", "trace_id", "runner_token"],
        [["run-1", "approved", "01_x", "{}", "t-run1", ""]],
    )
    return store


def test_event_log_filter_by_run_id():
    import service.app as app_mod  # noqa: PLC0415
    from service import api  # noqa: PLC0415
    store = _seed_store()
    state = app_mod.AppState(
        settings=app_mod.Settings(), store=store, tracer=None, bus=None,
        instrumentation=None, context=None, analytics=None,
    )
    old = app_mod.app_state
    app_mod.app_state = state
    try:
        out = api.event_log(limit=100, run_id="run-1")
    finally:
        app_mod.app_state = old
    # run-1 → trace t-run1 → events e1, e2 (tool.called has no trace_id)
    assert len(out["events"]) == 2
    assert {e["event_id"] for e in out["events"]} == {"e1", "e2"}
    assert out["next_cursor"] is not None


def test_event_log_bare_array_backward_compat():
    import service.app as app_mod  # noqa: PLC0415
    from service import api  # noqa: PLC0415
    store = _seed_store()
    state = app_mod.AppState(
        settings=app_mod.Settings(), store=store, tracer=None, bus=None,
        instrumentation=None, context=None, analytics=None,
    )
    old = app_mod.app_state
    app_mod.app_state = state
    try:
        out = api.event_log(limit=100)
    finally:
        app_mod.app_state = old
    assert isinstance(out, list)
    assert len(out) == 3


def test_runs_registry():
    import service.app as app_mod  # noqa: PLC0415
    from service import api  # noqa: PLC0415
    store = _seed_store()
    state = app_mod.AppState(
        settings=app_mod.Settings(), store=store, tracer=None, bus=None,
        instrumentation=None, context=None, analytics=None,
    )
    old = app_mod.app_state
    app_mod.app_state = state
    try:
        out = api.runs(limit=10)
    finally:
        app_mod.app_state = old
    assert len(out) == 1
    r = out[0]
    assert r["run_id"] == "run-1"
    assert r["state"] == "approved"
    assert r["event_count"] == 2
    assert "insight.created" in r["event_types"]
    assert r["trace_id"] == "t-run1"
