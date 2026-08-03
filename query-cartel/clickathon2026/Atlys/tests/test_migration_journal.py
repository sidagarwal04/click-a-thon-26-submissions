"""Unit tests — meta.migration_journal (P1.1)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.app import DDL_STATEMENTS  # noqa: E402
from service.migration_journal import (  # noqa: E402
    already_applied,
    begin_apply,
    finish_apply,
    latest_for_migration,
    list_recent,
    next_schema_changelog_version,
    record_load_snapshot,
    record_planned,
    table_inflight,
)
from service.migration_plan import apply_migration_plan, plan_migration  # noqa: E402
from service.store import DryRunStore  # noqa: E402


def _boot() -> DryRunStore:
    store = DryRunStore()
    for ddl in DDL_STATEMENTS:
        store.command(ddl)
    return store


def test_journal_ddl_in_bootstrap():
    assert any("meta.migration_journal" in d for d in DDL_STATEMENTS)


def test_planned_apply_skip_idempotent():
    store = _boot()
    ddl = (
        "CREATE TABLE IF NOT EXISTS t_events (\n"
        "    id String,\n    n UInt8\n"
        ") ENGINE = MergeTree ORDER BY id;"
    )
    plan = plan_migration("t_events", {"id": "String", "n": "UInt8"}, None, ddl)
    record_planned(store, plan, run_id="r1", trace_id="t1")
    assert latest_for_migration(store, plan.plan_hash)["status"] == "planned"

    assert begin_apply(store, plan, run_id="r1", trace_id="t1") == "apply"
    assert latest_for_migration(store, plan.plan_hash)["status"] == "approved"
    assert table_inflight(store, "t_events", exclude_run_id="other") is not None

    applied = apply_migration_plan(store, plan)
    finish_apply(store, plan, run_id="r1", trace_id="t1", applied=applied)
    assert latest_for_migration(store, plan.plan_hash)["status"] == "applied"
    assert already_applied(store, plan.plan_hash)

    # Same plan again → skip without holding a new lock
    assert begin_apply(store, plan, run_id="r2", trace_id="t2") == "skip"
    assert latest_for_migration(store, plan.plan_hash)["status"] == "skipped_idempotent"
    assert table_inflight(store, "t_events") is None


def test_inflight_blocks_other_run():
    store = _boot()
    plan = plan_migration(
        "t_events", {"id": "String"}, None,
        "CREATE TABLE IF NOT EXISTS t_events (id String) ENGINE = MergeTree ORDER BY id;",
    )
    begin_apply(store, plan, run_id="r1", trace_id="t1")
    locked = table_inflight(store, "t_events", exclude_run_id="r2")
    assert locked is not None
    assert locked["run_id"] == "r1"

    import pytest
    with pytest.raises(RuntimeError, match="migration in flight"):
        begin_apply(store, plan, run_id="r2", trace_id="t2")


def test_finish_failed_releases_for_retry_with_new_hash_path():
    store = _boot()
    plan = plan_migration(
        "t_events", {"id": "String"}, None,
        "CREATE TABLE IF NOT EXISTS t_events (id String) ENGINE = MergeTree ORDER BY id;",
    )
    begin_apply(store, plan, run_id="r1", trace_id="t1")
    finish_apply(store, plan, run_id="r1", trace_id="t1", applied=[], error="boom")
    assert latest_for_migration(store, plan.plan_hash)["status"] == "failed"
    assert table_inflight(store, "t_events") is None
    # Failed is not terminal-ok — can begin again
    assert not already_applied(store, plan.plan_hash)
    assert begin_apply(store, plan, run_id="r1b", trace_id="t1b") == "apply"


def test_load_snapshot_and_list_recent():
    store = _boot()
    record_load_snapshot(
        store, table_name="t_events", plan_hash="abc", events_hash="deadbeef" * 4,
        run_id="r1", trace_id="t1", skipped=False,
    )
    rows = list_recent(store, table_name="t_events", limit=10)
    assert rows
    assert rows[0]["action"] == "load_snapshot"
    assert rows[0]["status"] == "applied"


def test_schema_changelog_versions_increment():
    store = _boot()
    assert next_schema_changelog_version(store) == 1
    store.insert(
        "meta.schema_changelog",
        ["version", "agent", "action", "object", "diff", "rationale", "trace_id"],
        [[1, "instrumentation", "create_table", "t", "{}", "{}", "tr"]],
    )
    assert next_schema_changelog_version(store) == 2
    store.insert(
        "meta.schema_changelog",
        ["version", "agent", "action", "object", "diff", "rationale", "trace_id"],
        [[2, "instrumentation", "add_column", "t", "{}", "{}", "tr"]],
    )
    assert next_schema_changelog_version(store) == 3
