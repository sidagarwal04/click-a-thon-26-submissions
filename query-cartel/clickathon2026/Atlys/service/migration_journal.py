"""Migration journal — append-only audit + idempotency (resilience plan §2.9).

`meta.migration_journal` records every plan lifecycle:

  planned → approved → applied | skipped_idempotent | failed

Readers always take the **latest** row per `migration_id` (ORDER BY created_at DESC).
State is never mutated in place — double-delivery of the same plan is a no-op once
`applied` / `skipped_idempotent` is the latest status.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .migration_plan import MigrationPlan

log = logging.getLogger("atlys.migration_journal")

JOURNAL_TABLE = "meta.migration_journal"

JOURNAL_DDL = """
CREATE TABLE IF NOT EXISTS meta.migration_journal (
    migration_id String,
    table_name String,
    action LowCardinality(String),
    plan_hash String,
    status LowCardinality(String),
    run_id String,
    trace_id String,
    error String,
    created_at DateTime DEFAULT now(),
    applied_at Nullable(DateTime)
) ENGINE = MergeTree ORDER BY (table_name, migration_id, created_at)
"""

# Terminal statuses — re-applying the same migration_id is a no-op.
TERMINAL_OK = frozenset({"applied", "skipped_idempotent"})
INFLIGHT = frozenset({"approved"})  # mid-apply lock
# Crash safety: an `approved` row older than this is not treated as a lock.
INFLIGHT_STALE_SECONDS = 15 * 60

COLUMNS = [
    "migration_id", "table_name", "action", "plan_hash", "status",
    "run_id", "trace_id", "error", "created_at", "applied_at",
]


def primary_action(plan: MigrationPlan, applied: list[str] | None = None) -> str:
    """Single action label for a (possibly multi-step) plan."""
    if applied:
        if "rebuild" in applied:
            return "rebuild"
        if "add_column" in applied:
            return "add_column"
        if "widen_type" in applied:
            return "widen_type"
        if "create_table" in applied:
            return "create_table"
        if applied == ["skipped_idempotent"]:
            return "noop"
    if plan.requires_rebuild:
        return "rebuild"
    actions = [s.action for s in plan.steps if s.action != "noop"]
    if not actions:
        return "noop"
    if "rebuild" in actions:
        return "rebuild"
    if "create_table" in actions:
        return "create_table"
    if "add_column" in actions:
        return "add_column"
    if "widen_type" in actions:
        return "widen_type"
    return actions[0]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _insert(store, *, migration_id: str, table_name: str, action: str, plan_hash: str,
            status: str, run_id: str, trace_id: str, error: str = "",
            applied_at: datetime | None = None) -> None:
    now = _now()
    store.insert(
        JOURNAL_TABLE,
        COLUMNS,
        [[migration_id, table_name, action, plan_hash, status,
          run_id or "", trace_id or "", error or "", now, applied_at]],
    )


def record_planned(store, plan: MigrationPlan, *, run_id: str, trace_id: str) -> None:
    """Append a `planned` row when the schema card is proposed."""
    _insert(
        store,
        migration_id=plan.plan_hash,
        table_name=plan.table,
        action=primary_action(plan),
        plan_hash=plan.plan_hash,
        status="planned",
        run_id=run_id,
        trace_id=trace_id,
    )


def latest_for_migration(store, migration_id: str) -> dict | None:
    rows = store.query_rows(
        "SELECT migration_id, table_name, action, plan_hash, status, run_id, "
        "trace_id, error, created_at, applied_at "
        f"FROM {JOURNAL_TABLE} WHERE migration_id = {{mid:String}} "
        "ORDER BY created_at DESC LIMIT 1",
        {"mid": migration_id},
    )
    return rows[0] if rows else None


def latest_for_table(store, table_name: str) -> dict | None:
    rows = store.query_rows(
        "SELECT migration_id, table_name, action, plan_hash, status, run_id, "
        "trace_id, error, created_at, applied_at "
        f"FROM {JOURNAL_TABLE} WHERE table_name = {{t:String}} "
        "ORDER BY created_at DESC LIMIT 1",
        {"t": table_name},
    )
    return rows[0] if rows else None


def already_applied(store, migration_id: str) -> bool:
    """True when the latest status for this plan is terminal success."""
    row = latest_for_migration(store, migration_id)
    return bool(row and row.get("status") in TERMINAL_OK)


def table_inflight(store, table_name: str, *, exclude_run_id: str | None = None) -> dict | None:
    """Return the inflight journal row if another run holds the table lock."""
    row = latest_for_table(store, table_name)
    if not row:
        return None
    if row.get("status") not in INFLIGHT:
        return None
    if exclude_run_id and row.get("run_id") == exclude_run_id:
        return None
    created = row.get("created_at")
    if created is not None:
        try:
            if isinstance(created, str):
                created = datetime.fromisoformat(created.replace("Z", ""))
            age = (_now() - created).total_seconds()
            if age > INFLIGHT_STALE_SECONDS:
                log.warning(
                    "ignoring stale migration lock on %s (age=%.0fs, migration_id=%s)",
                    table_name, age, row.get("migration_id"),
                )
                return None
        except Exception:  # noqa: BLE001
            pass
    return row


def begin_apply(store, plan: MigrationPlan, *, run_id: str, trace_id: str) -> str:
    """Mark migration `approved` (inflight). Returns status to execute: apply|skip.

    Raises RuntimeError if another run holds the table lock.
    """
    mid = plan.plan_hash
    if already_applied(store, mid):
        _insert(
            store,
            migration_id=mid,
            table_name=plan.table,
            action=primary_action(plan),
            plan_hash=mid,
            status="skipped_idempotent",
            run_id=run_id,
            trace_id=trace_id,
            applied_at=_now(),
        )
        log.info("migration %s already applied — skipped_idempotent", mid)
        return "skip"

    locked = table_inflight(store, plan.table, exclude_run_id=run_id)
    if locked:
        raise RuntimeError(
            f"migration in flight for {plan.table}: migration_id={locked.get('migration_id')} "
            f"run_id={locked.get('run_id')} status={locked.get('status')}"
        )

    _insert(
        store,
        migration_id=mid,
        table_name=plan.table,
        action=primary_action(plan),
        plan_hash=mid,
        status="approved",
        run_id=run_id,
        trace_id=trace_id,
    )
    return "apply"


def finish_apply(store, plan: MigrationPlan, *, run_id: str, trace_id: str,
                 applied: list[str], error: str | None = None) -> None:
    """Append terminal `applied` / `skipped_idempotent` / `failed` row."""
    mid = plan.plan_hash
    if error:
        status = "failed"
    elif applied == ["skipped_idempotent"] or (plan.schema_matched and not any(
        a in ("create_table", "add_column", "widen_type", "rebuild") for a in applied
    )):
        status = "skipped_idempotent"
    else:
        status = "applied"
    _insert(
        store,
        migration_id=mid,
        table_name=plan.table,
        action=primary_action(plan, applied),
        plan_hash=mid,
        status=status,
        run_id=run_id,
        trace_id=trace_id,
        error=error or "",
        applied_at=_now(),
    )


def record_load_snapshot(store, *, table_name: str, plan_hash: str, events_hash: str,
                         run_id: str, trace_id: str, skipped: bool) -> None:
    """Journal a data load (or skip) keyed by plan + events content hash."""
    mid = f"{plan_hash}:load:{events_hash[:16]}"
    _insert(
        store,
        migration_id=mid,
        table_name=table_name,
        action="load_snapshot",
        plan_hash=plan_hash,
        status="skipped_idempotent" if skipped else "applied",
        run_id=run_id,
        trace_id=trace_id,
        applied_at=_now(),
    )


def next_schema_changelog_version(store) -> int:
    """max(version)+1 for meta.schema_changelog (real evolution versions)."""
    try:
        rows = store.query_rows("SELECT max(version) AS v FROM meta.schema_changelog")
        if rows and rows[0].get("v") is not None:
            return int(rows[0]["v"]) + 1
    except Exception as e:  # noqa: BLE001
        log.warning("schema changelog version lookup failed: %s", e)
    return 1


def list_recent(store, *, table_name: str | None = None, limit: int = 50) -> list[dict]:
    """Dashboard/MCP helper — recent journal rows."""
    if table_name:
        rows = store.query_rows(
            "SELECT migration_id, table_name, action, plan_hash, status, run_id, "
            "trace_id, error, created_at, applied_at "
            f"FROM {JOURNAL_TABLE} WHERE table_name = {{t:String}} "
            "ORDER BY created_at DESC LIMIT {n:UInt32}",
            {"t": table_name, "n": limit},
        )
    else:
        rows = store.query_rows(
            "SELECT migration_id, table_name, action, plan_hash, status, run_id, "
            "trace_id, error, created_at, applied_at "
            f"FROM {JOURNAL_TABLE} ORDER BY created_at DESC LIMIT {{n:UInt32}}",
            {"n": limit},
        )
    out: list[dict[str, Any]] = []
    for r in rows or []:
        out.append({
            **r,
            "created_at": str(r.get("created_at", "")),
            "applied_at": str(r["applied_at"]) if r.get("applied_at") is not None else None,
        })
    return out
