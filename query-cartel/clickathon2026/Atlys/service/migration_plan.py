"""Additive schema migration planner (docs/clickhouse-agent-resilience-plan.md §2.6–2.9).

Diffs live `system.columns` vs desired card columns and emits a plan of
CREATE / ADD COLUMN / MODIFY (widen-only) / rebuild. Drops and narrowing never
happen automatically — unused live columns are left in place (deferred removal).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


# Widen-only numeric lattice (P0.1). Edges are allowed MODIFY targets.
_UINT_CHAIN = ["UInt8", "UInt16", "UInt32", "UInt64"]
_INT_CHAIN = ["Int8", "Int16", "Int32", "Int64"]
_FLOAT_CHAIN = ["Float32", "Float64"]


@dataclass
class MigrationStep:
    action: str  # create_table | add_column | widen_type | rebuild | noop
    sql: str = ""
    object: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationPlan:
    table: str
    steps: list[MigrationStep] = field(default_factory=list)
    requires_rebuild: bool = False
    schema_matched: bool = False
    plan_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "steps": [s.to_dict() for s in self.steps],
            "requires_rebuild": self.requires_rebuild,
            "schema_matched": self.schema_matched,
            "plan_hash": self.plan_hash,
        }


def strip_wrappers(ctype: str) -> tuple[str, bool, bool]:
    """Return (base, is_nullable, is_low_cardinality)."""
    t = ctype.strip()
    is_lc = False
    is_null = False
    if t.startswith("LowCardinality(") and t.endswith(")"):
        is_lc = True
        t = t[len("LowCardinality(") : -1].strip()
    if t.startswith("Nullable(") and t.endswith(")"):
        is_null = True
        t = t[len("Nullable(") : -1].strip()
    # CH may also emit LowCardinality(Nullable(...)) — already handled.
    # Rare reverse: Nullable(LowCardinality(...)) — unwrap again.
    if t.startswith("LowCardinality(") and t.endswith(")"):
        is_lc = True
        t = t[len("LowCardinality(") : -1].strip()
    return t, is_null, is_lc


def types_equal(a: str, b: str) -> bool:
    return strip_wrappers(a) == strip_wrappers(b) and a.replace(" ", "") == b.replace(" ", "")


def _chain_index(base: str, chain: list[str]) -> int | None:
    try:
        return chain.index(base)
    except ValueError:
        return None


def can_widen(from_type: str, to_type: str) -> bool:
    """True when MODIFY COLUMN from→to is non-destructive."""
    if from_type.replace(" ", "") == to_type.replace(" ", ""):
        return True

    f_base, f_null, f_lc = strip_wrappers(from_type)
    t_base, t_null, t_lc = strip_wrappers(to_type)

    # May add nullability; may not remove it.
    if f_null and not t_null:
        return False
    # Dropping LowCardinality is fine; adding LC on existing data is also usually fine.
    # Refusing only when bases cannot widen.

    if f_base == t_base:
        # same base: nullability/LC changes that don't narrow
        if (not f_null and t_null) or (f_lc and not t_lc) or (not f_lc and t_lc) or (f_null == t_null and f_lc == t_lc):
            return True
        return f_null == t_null  # identical after wrappers

    for chain in (_UINT_CHAIN, _INT_CHAIN, _FLOAT_CHAIN):
        fi, ti = _chain_index(f_base, chain), _chain_index(t_base, chain)
        if fi is not None and ti is not None and ti >= fi:
            return True

    # DateTime → DateTime64(n) is widen-ish (more precision)
    if f_base == "DateTime" and t_base.startswith("DateTime64"):
        return True
    if f_base.startswith("DateTime64") and t_base.startswith("DateTime64"):
        return True

    return False


def events_content_hash(path_or_bytes: str | bytes) -> str:
    """SHA-256 of the events NDJSON file (or raw bytes) for load idempotency."""
    if isinstance(path_or_bytes, bytes):
        data = path_or_bytes
    else:
        from pathlib import Path
        data = Path(path_or_bytes).read_bytes()
    return hashlib.sha256(data).hexdigest()


def plan_hash(table: str, steps: list[MigrationStep], desired: dict[str, str]) -> str:
    canonical = {
        "table": table,
        "steps": [(s.action, s.object, s.detail) for s in steps],
        "desired": dict(sorted(desired.items())),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def plan_migration(
    table: str,
    desired_columns: dict[str, str],
    live_columns: dict[str, str] | None,
    ddl: str,
) -> MigrationPlan:
    """Build an additive migration plan.

    live_columns=None / empty → CREATE.
    Compatible drift → ADD / widen steps.
    Incompatible drift → single rebuild step (DROP+CREATE); caller must surface
    this on the schema card and only execute after approval.
    """
    live = dict(live_columns or {})
    if not live:
        step = MigrationStep(
            action="create_table",
            sql=ddl,
            object=table,
            detail="table missing — CREATE TABLE IF NOT EXISTS",
        )
        plan = MigrationPlan(table=table, steps=[step], requires_rebuild=False, schema_matched=False)
        plan.plan_hash = plan_hash(table, plan.steps, desired_columns)
        return plan

    # Exact match (order-insensitive on types)
    if live == dict(desired_columns):
        step = MigrationStep(action="noop", object=table, detail="live schema matches card")
        plan = MigrationPlan(table=table, steps=[step], schema_matched=True)
        plan.plan_hash = plan_hash(table, plan.steps, desired_columns)
        return plan

    steps: list[MigrationStep] = []
    incompatible: list[str] = []

    for name, want in desired_columns.items():
        if name not in live:
            steps.append(MigrationStep(
                action="add_column",
                sql=f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {want}",
                object=f"{table}.{name}",
                detail=f"add {name} {want}",
            ))
            continue
        have = live[name]
        if have.replace(" ", "") == want.replace(" ", ""):
            continue
        if can_widen(have, want):
            steps.append(MigrationStep(
                action="widen_type",
                sql=f"ALTER TABLE {table} MODIFY COLUMN {name} {want}",
                object=f"{table}.{name}",
                detail=f"widen {name}: {have} → {want}",
            ))
        else:
            incompatible.append(f"{name}: {have} → {want}")

    # Live-only columns: deferred removal — no DROP COLUMN steps.

    if incompatible:
        detail = "incompatible type changes require rebuild: " + "; ".join(incompatible)
        rebuild = MigrationStep(
            action="rebuild",
            sql=f"DROP TABLE IF EXISTS {table};\n{ddl}",
            object=table,
            detail=detail,
        )
        plan = MigrationPlan(
            table=table,
            steps=[rebuild],
            requires_rebuild=True,
            schema_matched=False,
        )
        plan.plan_hash = plan_hash(table, plan.steps, desired_columns)
        return plan

    if not steps:
        # Only live-extra columns differ — desired ⊆ live with equal types.
        # Treat as matched for load-skip purposes (additive extras are fine).
        desired_ok = all(
            name in live and live[name].replace(" ", "") == want.replace(" ", "")
            for name, want in desired_columns.items()
        )
        if desired_ok:
            step = MigrationStep(
                action="noop",
                object=table,
                detail="desired columns satisfied; extra live columns retained (deferred removal)",
            )
            plan = MigrationPlan(table=table, steps=[step], schema_matched=True)
            plan.plan_hash = plan_hash(table, plan.steps, desired_columns)
            return plan

    plan = MigrationPlan(table=table, steps=steps, schema_matched=False)
    plan.plan_hash = plan_hash(table, plan.steps, desired_columns)
    return plan


def _run_sql(store, sql: str) -> None:
    sql = sql.strip()
    if not sql:
        return
    store.command(sql if sql.endswith(";") else sql + ";")


def apply_migration_plan(store, plan: MigrationPlan) -> list[str]:
    """Execute plan steps against the store. Returns list of applied action labels.

    Rebuild executes DROP then CREATE. ADD/MODIFY run as-is. noop is skipped.
    Idempotent DDL (`IF NOT EXISTS` / widen to same) is fine to re-run.
    """
    applied: list[str] = []
    for step in plan.steps:
        if step.action == "noop":
            applied.append("skipped_idempotent")
            continue
        if step.action == "rebuild":
            # Planner packs "DROP ...;\\nCREATE ..." — run each statement.
            for part in re.split(r";\s*", step.sql):
                part = part.strip()
                if part:
                    _run_sql(store, part)
            applied.append("rebuild")
            continue
        if step.sql:
            _run_sql(store, step.sql)
            applied.append(step.action)
    return applied
