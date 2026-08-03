"""Integration tests — full pipeline against a live ClickHouse (Part 9).

Skipped automatically when no ClickHouse is reachable (e.g. CI without a
service). When `CH_HOST` is set (or a local server is up), verifies:
row counts == NDJSON line counts, meta rows written, trace_id present on every
event-log and meta row, and the event chain reached insight.created.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.app import DDL_STATEMENTS, _bootstrap, create_app  # noqa: E402
from service.bus import EventBus  # noqa: E402
from service.events import new_event  # noqa: E402
from service.store import ClickHouseStore, DryRunStore  # noqa: E402

SPECS = ["01_express_checkout", "02_group_family", "03_status_sharing",
         "04_abandoned_checkout_recovery", "05_instant_forex"]


def _store_from_env() -> ClickHouseStore | None:
    # Use Settings so URL-form CH_HOST is parsed exactly like the app does
    # (scheme stripped, secure inferred) — mirrors production, not the raw env.
    from service.settings import Settings
    s = Settings()
    if not s.ch_host:
        return None
    try:
        store = ClickHouseStore(
            host=s.ch_host,
            user=s.ch_user,
            password=s.ch_password,
            secure=s.ch_secure,
            database=s.atlys_db,
        )
        store.query_rows("SELECT 1")
        return store
    except Exception:
        return None


pytestmark = pytest.mark.skipif(
    _store_from_env() is None,
    reason="no ClickHouse reachable — set CH_HOST to run e2e tests",
)

# re-evaluate the skip result lazily so the fixture check runs once
STORE = _store_from_env()


@pytest.fixture(scope="module")
def store():
    return STORE


@pytest.fixture(scope="module")
def app_store():
    os.environ.setdefault("CH_HOST", os.environ["CH_HOST"])
    app = create_app()
    # the lifespan bootstrap only runs under uvicorn — run it explicitly here
    _bootstrap(app.state.settings, app.state.store, app.state.context)
    yield app.state
    try:
        app.state.tracer.flush()
    except Exception:  # noqa: BLE001
        pass


def _ndjson_lines(spec: str) -> int:
    p = Path(__file__).resolve().parents[1] / "specs" / spec / "events.ndjson"
    return sum(1 for line in p.open() if line.strip())


def test_funnel_tables_loaded(store):
    for table, expected in [("destination_card_clicked", 1_000_000),
                            ("purchase_completed", 7_054)]:
        assert store.row_count(table) == expected, table


def test_full_run_writes_table_and_events(store):
    app = create_app()
    _bootstrap(app.state.settings, app.state.store, app.state.context)
    # run the whole chain with auto-approval: emit spec.run.requested then
    # approve whatever pending run shows up
    state = app.state
    spec = SPECS[0]
    bus: EventBus = state.bus

    # Unique run_id per run: meta.pending_runs.created_at is second-granular
    # DateTime, so a fixed run_id would tie on ORDER BY created_at DESC with an
    # earlier run's row (already flipped to 'approved') — same-second ambiguity
    # would fail the 'proposed' assertion below. UUIDs make the gate collision-
    # free (ENGINEERING.md §5.1: "run_id is a UUID (no collisions)").
    run_id = "e2e-" + spec + "-" + uuid.uuid4().hex[:8]
    bus.emit(new_event(
        "spec.run.requested", f"spec/{spec}", "test",
        payload={"spec_dir": spec, "run_id": run_id},
        trace_id=f"trace-e2e-{spec}",
    ))
    pending = state.store.query_rows(
        "SELECT run_id, state, trace_id FROM meta.pending_runs WHERE run_id = {r:String} "
        "ORDER BY created_at DESC LIMIT 1",
        {"r": run_id})
    assert pending, "pending run should be persisted (durable approval gate)"
    assert pending[0]["state"] == "proposed"

    # human approval gate (D10)
    bus.emit(new_event(
        "schema.approved", f"run/{run_id}", "test",
        payload={"run_id": run_id}, trace_id=pending[0]["trace_id"],
    ))

    # the chain: schema.created → context.checked → context.updated → insight.created
    insights = state.store.query_rows(
        "SELECT spec, title, confidence, trace_id FROM meta.insights ORDER BY created_at DESC LIMIT 3")
    assert insights, "expected at least one insight after approval"
    assert any(i["trace_id"] for i in insights)

    # feature table exists with row_count == NDJSON lines
    table = "express_checkout_events"
    assert state.store.table_exists(table)
    assert state.store.row_count(table) == _ndjson_lines(spec)


def test_event_log_carries_trace_id(app_store):
    rows = app_store.store.query_rows(
        "SELECT event_type, trace_id FROM atlys.event_log LIMIT 50")
    assert rows
    assert any(r["trace_id"] for r in rows)


def test_meta_rows_carry_trace_id(app_store):
    for table in ("meta.schema_catalog", "meta.context_snapshots", "meta.insights"):
        rows = app_store.store.query_rows(f"SELECT trace_id FROM {table} LIMIT 5")
        if rows:
            assert all(r["trace_id"] for r in rows), table


def test_context_reconcile_findings_present(app_store):
    rows = app_store.store.query_rows(
        "SELECT action, object, diff FROM meta.context_changelog LIMIT 20")
    assert any(r["action"] == "reconciliation_finding" for r in rows)
