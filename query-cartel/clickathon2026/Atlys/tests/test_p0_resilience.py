"""Unit tests — migration planner, error taxonomy, P0 schema/analytics hardening."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.ch_errors import (  # noqa: E402
    TIMEOUT_QUERY,
    TRANSIENT_NETWORK,
    TYPE_MISMATCH,
    UNKNOWN_TABLE,
    classify_exception,
    evidence_error,
)
from service.migration_plan import (  # noqa: E402
    apply_migration_plan,
    can_widen,
    events_content_hash,
    plan_migration,
)
from service.schema import flatten, infer_types, load_events  # noqa: E402
from service.store import DryRunStore  # noqa: E402
from service.agents.analytics import AnalyticsAgent, P6_USER_LIMIT  # noqa: E402


# ---------------------------------------------------------------------------
# P0.1 — additive migration plan
# ---------------------------------------------------------------------------

def test_plan_create_when_missing():
    plan = plan_migration("t_events", {"id": "String", "n": "UInt8"}, None, "CREATE TABLE t_events (id String) ENGINE = MergeTree ORDER BY id;")
    assert not plan.schema_matched
    assert plan.steps[0].action == "create_table"
    assert not plan.requires_rebuild


def test_plan_noop_when_matched():
    cols = {"id": "String", "n": "UInt8"}
    plan = plan_migration("t_events", cols, cols, "CREATE …")
    assert plan.schema_matched
    assert plan.steps[0].action == "noop"


def test_plan_add_column_no_drop():
    live = {"id": "String", "n": "UInt8"}
    want = {"id": "String", "n": "UInt8", "extra": "Nullable(String)"}
    plan = plan_migration("t_events", want, live, "CREATE …")
    assert not plan.requires_rebuild
    assert [s.action for s in plan.steps] == ["add_column"]
    assert "ADD COLUMN IF NOT EXISTS extra" in plan.steps[0].sql
    assert not any("DROP" in (s.sql or "").upper() for s in plan.steps)


def test_plan_widen_uint():
    live = {"n": "UInt8"}
    want = {"n": "UInt16"}
    plan = plan_migration("t_events", want, live, "CREATE …")
    assert plan.steps[0].action == "widen_type"
    assert "MODIFY COLUMN n UInt16" in plan.steps[0].sql


def test_plan_rebuild_on_incompatible():
    live = {"n": "String"}
    want = {"n": "UInt8"}
    plan = plan_migration("t_events", want, live, "CREATE TABLE t_events (n UInt8) ENGINE = MergeTree ORDER BY tuple();")
    assert plan.requires_rebuild
    assert plan.steps[0].action == "rebuild"
    assert "DROP TABLE IF EXISTS t_events" in plan.steps[0].sql


def test_plan_retains_extra_live_columns():
    live = {"id": "String", "legacy": "String"}
    want = {"id": "String"}
    plan = plan_migration("t_events", want, live, "CREATE …")
    assert plan.schema_matched
    assert "deferred" in plan.steps[0].detail


def test_can_widen_lattice():
    assert can_widen("UInt8", "UInt32")
    assert can_widen("UInt8", "Nullable(UInt8)")
    assert not can_widen("UInt32", "UInt8")
    assert not can_widen("String", "UInt8")
    assert can_widen("DateTime", "DateTime64(3)")


def test_apply_add_column_on_dry_run():
    store = DryRunStore()
    store.command(
        "CREATE TABLE IF NOT EXISTS t_events ("
        "\n    id String,\n    n UInt8\n) ENGINE = MergeTree ORDER BY id;"
    )
    store.insert("t_events", ["id", "n"], [["a", 1]])
    plan = plan_migration(
        "t_events",
        {"id": "String", "n": "UInt8", "x": "Nullable(String)"},
        {c["name"]: c["type"] for c in store.columns("t_events")},
        "CREATE …",
    )
    applied = apply_migration_plan(store, plan)
    assert applied == ["add_column"]
    live = {c["name"]: c["type"] for c in store.columns("t_events")}
    assert live["x"] == "Nullable(String)"
    assert store.row_count("t_events") == 1  # no DROP
    assert not any(c.upper().startswith("DROP") for c in store.commands if "DROP" in c.upper())


# ---------------------------------------------------------------------------
# P0.2 — content hash
# ---------------------------------------------------------------------------

def test_events_content_hash_stable(tmp_path):
    f = tmp_path / "e.ndjson"
    f.write_text('{"event":"a"}\n')
    assert events_content_hash(f) == events_content_hash(f)
    assert events_content_hash(f) == events_content_hash(f.read_bytes())
    f.write_text('{"event":"b"}\n')
    assert events_content_hash(f) != events_content_hash(b'{"event":"a"}\n')


# ---------------------------------------------------------------------------
# P0.3 — error taxonomy
# ---------------------------------------------------------------------------

def test_classify_unknown_table():
    err = classify_exception(Exception("Code: 60. DB::Exception: Unknown table expression identifier 'x'"))
    assert err.error_class == UNKNOWN_TABLE
    assert err.retryable is False


def test_classify_timeout():
    err = classify_exception(Exception("Timeout exceeded. Code: 159"))
    assert err.error_class == TIMEOUT_QUERY


def test_classify_transient_connection():
    err = classify_exception(ConnectionError("Connection reset by peer"))
    assert err.error_class == TRANSIENT_NETWORK
    assert err.retryable is True


def test_classify_type_mismatch():
    err = classify_exception(Exception("Code: 53. Type mismatch"))
    assert err.error_class == TYPE_MISMATCH


def test_evidence_error_shape():
    payload = evidence_error(Exception("Code: 60. Unknown table 'foo'"), "SELECT 1 FROM foo")
    assert payload["error_class"] == UNKNOWN_TABLE
    assert "error" in payload
    assert payload["sql_digest"]


# ---------------------------------------------------------------------------
# P0.4 — type inference fixtures
# ---------------------------------------------------------------------------

def test_infer_array_becomes_json_string():
    flat = flatten({"event": "x", "tags": ["a", "b"], "nested": {"k": 1}})
    assert flat["tags"] == '["a", "b"]'
    assert flat["nested_k"] == 1
    cols = infer_types([flat, {"event": "x", "tags": '["c"]', "nested_k": 2}]).columns
    assert cols["tags"] == "String"
    assert cols["nested_k"] == "UInt8"


def test_infer_mixed_and_missing_user_id():
    inferred = infer_types([
        {"event": "a", "timestamp": "2026-06-08T06:00:00.000", "id": "x" * 32, "v": 1},
        {"event": "b", "timestamp": "2026-06-08T06:00:00.000", "id": "y" * 32, "v": "two"},
    ])
    assert inferred.has_user_id is False
    assert inferred.columns["v"] == "String"


def test_infer_fractional_timestamp_feature_col():
    cols = infer_types([
        {"event": "x", "timestamp": "2026-06-08T06:00:00.000", "id": "z" * 32,
         "user_id": "u1", "completed_at": "2026-06-08T06:00:00.123Z"},
        {"event": "x", "timestamp": "2026-06-08T06:00:01.000", "id": "w" * 32,
         "user_id": "u2", "completed_at": "2026-06-08T06:00:01.456Z"},
    ]).columns
    assert cols["completed_at"] == "DateTime64(3)"
    # envelope timestamp stays DateTime per template
    assert cols["timestamp"] == "DateTime"


def test_load_events_nested_array_fixture(tmp_path):
    f = tmp_path / "e.ndjson"
    f.write_text(
        '{"event":"shown","timestamp":"2026-06-08T06:00:00.123","id":"' + "a" * 32 +
        '","payload":{"items":[1,2],"meta":{"ok":true}}}\n'
        '{"event":"done","timestamp":"2026-06-08T06:00:01.456","id":"' + "b" * 32 +
        '","user_id":"u1","payload":{"items":[3],"meta":{"ok":false}}}\n'
    )
    events = load_events(f)
    inferred = infer_types(events)
    assert "payload_items" in inferred.columns
    assert inferred.columns["payload_items"] == "String"
    assert inferred.columns["payload_meta_ok"] in {"UInt8", "Nullable(UInt8)"}
    assert inferred.has_user_id is True  # present on at least one row
    # sparse user_id → Nullable
    assert "Nullable" in inferred.columns["user_id"]


# ---------------------------------------------------------------------------
# P0.5 — analytics caps + structured errors
# ---------------------------------------------------------------------------

def test_p6_has_limit():
    agent = AnalyticsAgent(DryRunStore(), None, None)
    qs = agent.playbook("f", "f_events", ["a", "b"])
    p6 = next(q for q in qs if q["kind"] == "funnel_timing")
    assert f"LIMIT {P6_USER_LIMIT}" in p6["sql"]


def test_run_playbook_records_error_class():
    store = DryRunStore()
    store.insert("t_events", ["event", "user_id"], [["a", "u1"]])
    agent = AnalyticsAgent(store, None, None)

    class BoomStore:
        def table_exists(self, name):
            return False

        def query(self, sql):
            raise Exception("Code: 60. Unknown table expression identifier")

    agent.store = BoomStore()
    evidence = agent.run_playbook("t", "missing_events", ["a", "b"])
    assert evidence
    assert all("error" in e for e in evidence)
    assert all(e.get("error_class") == UNKNOWN_TABLE for e in evidence)


def test_mv_step_included_when_present():
    store = DryRunStore()
    store.command("CREATE TABLE IF NOT EXISTS mv_funnel_daily (day Date) ENGINE = MergeTree ORDER BY day;")
    agent = AnalyticsAgent(store, None, None)
    qs = agent.playbook("f", "f_events", ["a", "b"])
    assert any(q["kind"] == "mv_funnel" for q in qs)


# ---------------------------------------------------------------------------
# P0.6 — version detection
# ---------------------------------------------------------------------------

def test_dry_run_idempotent_reload_skips_duplicate_rows(tmp_path):
    """P0.1+P0.2: second approve with matching schema+hash must not double rows."""
    from dataclasses import dataclass
    from service.agents.instrumentation import InstrumentationAgent
    from service.bus import EventBus
    from service.events import new_event

    spec = tmp_path / "widget"
    spec.mkdir()
    (spec / "events.ndjson").write_text(
        '{"event":"shown","timestamp":"2026-06-08T06:00:00.000","id":"' + "a" * 32 +
        '","user_id":"u1","n":1}\n'
        '{"event":"done","timestamp":"2026-06-08T06:00:01.000","id":"' + "b" * 32 +
        '","user_id":"u1","n":2}\n'
    )

    @dataclass
    class _S:
        atlys_root: Path = tmp_path
        specs_dir: Path = tmp_path
        generated_dir: Path = tmp_path / "generated"

    store = DryRunStore()
    # bootstrap pending_runs / catalog tables so inserts work
    from service.app import DDL_STATEMENTS
    for ddl in DDL_STATEMENTS:
        store.command(ddl)

    settings = _S()
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    bus = EventBus(store=store, tracer=None)
    agent = InstrumentationAgent(store, bus, settings, tracer=None)
    bus.register("spec.run.requested", agent.on_run_requested)
    bus.register("schema.approved", agent.on_approved)

    run1 = "run-widget-1"
    bus.emit(new_event("spec.run.requested", "spec/widget", "test",
                       payload={"spec_dir": "widget", "run_id": run1}, trace_id="t1"))
    bus.emit(new_event("schema.approved", f"run/{run1}", "test",
                       payload={"run_id": run1}, trace_id="t1"))
    assert store.row_count("widget_events") == 2
    # No DROP on first create path beyond possible none
    drops_after_create = [c for c in store.commands if c.upper().lstrip().startswith("DROP TABLE")]
    assert drops_after_create == []

    # Additive: new column in a fresh propose would ADD — simulate live widen path:
    live = {c["name"]: c["type"] for c in store.columns("widget_events")}
    want = {**live, "bonus": "Nullable(UInt8)"}
    plan = plan_migration("widget_events", want, live, "CREATE …")
    assert [s.action for s in plan.steps] == ["add_column"]
    apply_migration_plan(store, plan)
    assert "bonus" in {c["name"] for c in store.columns("widget_events")}
    assert store.row_count("widget_events") == 2  # data preserved

    # Identical re-approve (new run) — should skip reload
    run2 = "run-widget-2"
    bus.emit(new_event("spec.run.requested", "spec/widget", "test",
                       payload={"spec_dir": "widget", "run_id": run2}, trace_id="t2"))
    bus.emit(new_event("schema.approved", f"run/{run2}", "test",
                       payload={"run_id": run2}, trace_id="t2"))
    assert store.row_count("widget_events") == 2
