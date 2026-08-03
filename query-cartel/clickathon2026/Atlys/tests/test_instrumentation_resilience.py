"""Path confinement, failed-state, and approve locks."""
from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.agents.context import ContextAgent  # noqa: E402
from service.agents.instrumentation import (  # noqa: E402
    STATE_APPROVED,
    STATE_FAILED,
    STATE_PROPOSED,
    InstrumentationAgent,
)
from service.app import DDL_STATEMENTS  # noqa: E402
from service.bus import EventBus  # noqa: E402
from service.events import new_event  # noqa: E402
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
        # skip analytics for focused tests — optional chain
        "schema.created": [ctx.on_schema_created],
    })
    ctx.seed_if_empty()
    return settings, store, bus, instr


def test_resolve_spec_dir_accepts_relative_and_specs_prefix():
    settings, _, _, instr = _boot()
    p1 = instr._resolve_spec_dir("01_express_checkout")
    p2 = instr._resolve_spec_dir("specs/01_express_checkout")
    assert p1 == p2
    assert p1.is_relative_to(settings.specs_dir.resolve()) or str(p1).startswith(
        str(settings.specs_dir.resolve())
    )


@pytest.mark.parametrize("bad", [
    "../etc/passwd",
    "specs/../../etc/passwd",
    "/etc/passwd",
    "01_express_checkout/../../../etc",
])
def test_resolve_spec_dir_rejects_traversal(bad):
    _, _, _, instr = _boot()
    with pytest.raises(ValueError, match="spec_dir"):
        instr._resolve_spec_dir(bad)


def test_run_requested_rejects_escaping_spec_dir():
    _, _, bus, _ = _boot()
    with pytest.raises(ValueError, match="spec_dir"):
        bus.emit(new_event(
            "spec.run.requested", "spec/evil", "test",
            payload={"spec_dir": "../README.md", "run_id": str(uuid.uuid4())},
            trace_id="t-evil",
        ))


def test_duplicate_approve_is_ignored():
    _, store, bus, _ = _boot()
    run_id = str(uuid.uuid4())
    bus.emit(new_event(
        "spec.run.requested", "spec/01", "test",
        payload={"spec_dir": "01_express_checkout", "run_id": run_id},
        trace_id="t1",
    ))
    bus.emit(new_event(
        "schema.approved", f"run/{run_id}", "test",
        payload={"run_id": run_id}, trace_id="t1",
    ))
    assert store.query_rows(
        "SELECT state FROM meta.pending_runs WHERE run_id = {r:String}",
        {"r": run_id},
    )[0]["state"] == STATE_APPROVED

    # second approve must no-op (still approved, not failed)
    bus.emit(new_event(
        "schema.approved", f"run/{run_id}", "test",
        payload={"run_id": run_id}, trace_id="t1",
    ))
    assert store.query_rows(
        "SELECT state FROM meta.pending_runs WHERE run_id = {r:String}",
        {"r": run_id},
    )[0]["state"] == STATE_APPROVED


def test_approve_marks_failed_when_load_raises():
    _, store, bus, instr = _boot()
    run_id = str(uuid.uuid4())
    bus.emit(new_event(
        "spec.run.requested", "spec/01", "test",
        payload={"spec_dir": "01_express_checkout", "run_id": run_id},
        trace_id="t-fail",
    ))
    assert store.query_rows(
        "SELECT state FROM meta.pending_runs WHERE run_id = {r:String}",
        {"r": run_id},
    )[0]["state"] == STATE_PROPOSED

    with patch("service.agents.instrumentation.apply_migration_plan", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            bus.emit(new_event(
                "schema.approved", f"run/{run_id}", "test",
                payload={"run_id": run_id}, trace_id="t-fail",
            ))

    assert store.query_rows(
        "SELECT state FROM meta.pending_runs WHERE run_id = {r:String}",
        {"r": run_id},
    )[0]["state"] == STATE_FAILED


def test_concurrent_double_approve_single_winner():
    _, store, bus, _ = _boot()
    run_id = str(uuid.uuid4())
    bus.emit(new_event(
        "spec.run.requested", "spec/01", "test",
        payload={"spec_dir": "01_express_checkout", "run_id": run_id},
        trace_id="t-race",
    ))

    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _approve():
        try:
            barrier.wait(timeout=5)
            bus.emit(new_event(
                "schema.approved", f"run/{run_id}", "test",
                payload={"run_id": run_id}, trace_id="t-race",
            ))
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    t1 = threading.Thread(target=_approve)
    t2 = threading.Thread(target=_approve)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not errors, errors

    state = store.query_rows(
        "SELECT state FROM meta.pending_runs WHERE run_id = {r:String}",
        {"r": run_id},
    )[0]["state"]
    assert state == STATE_APPROVED
    cards = store.query_rows(
        "SELECT table_name FROM meta.schema_catalog WHERE table_name = {t:String}",
        {"t": "express_checkout_events"},
    )
    assert len(cards) == 1


def test_cas_only_one_claimer_wins():
    _, store, bus, instr = _boot()
    run_id = str(uuid.uuid4())
    bus.emit(new_event(
        "spec.run.requested", "spec/01", "test",
        payload={"spec_dir": "01_express_checkout", "run_id": run_id},
        trace_id="t-cas",
    ))
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    assert instr._cas_run_state(run_id, STATE_PROPOSED, "running", runner_token=t1) is True
    assert instr._cas_run_state(run_id, STATE_PROPOSED, "running", runner_token=t2) is False
    row = store.query_rows(
        "SELECT state, runner_token FROM meta.pending_runs WHERE run_id = {r:String}",
        {"r": run_id},
    )[0]
    assert row["state"] == "running"
    assert row["runner_token"] == t1


def test_bus_allows_parallel_emits_on_different_aggregates():
    """Regression: bus must not globally single-thread unrelated work."""
    store = DryRunStore()
    bus = EventBus(store=store, persist=False)
    release = threading.Event()
    both_entered = threading.Event()
    entered = {"n": 0}
    entered_lock = threading.Lock()
    order: list[str] = []

    def blocking(e):
        order.append(f"enter:{e.aggregate_id}")
        with entered_lock:
            entered["n"] += 1
            if entered["n"] >= 2:
                both_entered.set()
        assert release.wait(timeout=5)
        order.append(f"leave:{e.aggregate_id}")

    bus.register("slow", blocking)

    def _emit(agg: str):
        bus.emit(new_event("slow", agg, "test"))

    t1 = threading.Thread(target=_emit, args=("a",))
    t2 = threading.Thread(target=_emit, args=("b",))
    t1.start()
    t2.start()
    assert both_entered.wait(timeout=5), "handlers did not overlap — bus is globally serialized"
    release.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert order.count("enter:a") == 1 and order.count("enter:b") == 1
