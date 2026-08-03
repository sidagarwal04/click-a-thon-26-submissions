"""Instrumentation Agent (ENGINEERING.md §5.1) — Agent 1.

Spec → schema card → DDL → (⏸ approval) → CREATE + LOAD → schema.created.
Every mutation passes the human approval gate (D10); nothing touches ClickHouse
before `approve_schema`. Idempotent: CREATE TABLE IF NOT EXISTS, additive
ALTER, schema card upserts on table_name, content-hash gated reload.
Approve path is serialized per run_id + feature table (in-process locks) and
marks `running` → `approved` | `failed` so partial failures are visible.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from .. import events as ev
from ..bus import EventBus
from ..events import Event
from ..locks import pipeline_locks
from ..migration_journal import (
    begin_apply,
    finish_apply,
    next_schema_changelog_version,
    record_load_snapshot,
    record_planned,
)
from ..migration_plan import apply_migration_plan, events_content_hash, plan_migration
from ..schema import ENVELOPE, build_ddl, infer_types, load_events, schema_card_dict, schema_rationale, _slug
from ..sqlsafe import require_safe_token, sanitize_identifier, sql_string_literal

log = logging.getLogger("atlys.agents.instrumentation")

# meta.pending_runs states (§3.3 + resilience plan)
STATE_PROPOSED = "proposed"
STATE_RUNNING = "running"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_FAILED = "failed"
STATE_ABORTED = "aborted"


class InstrumentationAgent:
    def __init__(self, store, bus: EventBus, settings, tracer=None, generated_dir: Path | None = None):
        self.store = store
        self.bus = bus
        self.settings = settings
        self.tracer = tracer
        self.generated_dir = generated_dir or settings.generated_dir
        self._locks = pipeline_locks

    # -- handlers -----------------------------------------------------------
    def on_run_requested(self, event: Event) -> None:
        """spec.run.requested → ingest → propose schema (⏸ pause for approval)."""
        spec_dir = event.payload.get("spec_dir")
        if not spec_dir:
            raise ValueError("spec.run.requested missing spec_dir")
        trace_id = event.trace_id
        feature = Path(spec_dir).name
        spec_path = self._resolve_spec_dir(spec_dir)
        events_path = spec_path / "events.ndjson"

        with self._span("instrumentation", spec_dir=spec_dir):
            # 1. read + infer (content-driven)
            events = load_events(events_path)
            inferred = infer_types(events)
            if not inferred.has_user_id:
                log.warning("spec %s has no user_id — analytics will bucket under ''", spec_dir)

            # 2. build DDL + rationale + migration plan vs live schema
            feature_slug = _slug(feature)
            ddl = build_ddl(feature_slug, inferred.columns, inferred.event_order)
            rationale = schema_rationale(
                feature_slug, inferred.columns, inferred.event_order,
                inferred.row_count, inferred.has_user_id,
            )
            ch_version = getattr(self.store, "server_version", None) or "unknown"
            rationale["clickhouse_version"] = f"Planned against ClickHouse {ch_version}."

            live = self._live_columns(f"{feature_slug}_events")
            mig = plan_migration(f"{feature_slug}_events", dict(inferred.columns), live, ddl)
            events_hash = events_content_hash(events_path)

            self.bus.emit(ev.new_event(
                ev.SPEC_INGESTED, spec_dir, ev.ACTOR_INSTRUMENTATION,
                payload={
                    "spec_dir": spec_dir,
                    "feature": feature_slug,
                    "event_order": inferred.event_order,
                    "columns": dict(inferred.columns),
                    "row_count": inferred.row_count,
                    "has_user_id": inferred.has_user_id,
                    "events_hash": events_hash,
                    "clickhouse_version": ch_version,
                },
                trace_id=trace_id,
            ))

            card = schema_card_dict(
                feature_slug, str(spec_dir), inferred.columns, inferred.event_order,
                inferred.row_count, ddl, rationale, trace_id, inferred.has_user_id,
            )
            card["events_hash"] = events_hash
            card["migration_plan"] = mig.to_dict()
            card["clickhouse_version"] = ch_version

            # 3. persist the pending run BEFORE returning (durability, §2.4)
            run_id = event.payload.get("run_id") or str(uuid.uuid4())
            self._save_pending_run(run_id, spec_dir, card, trace_id)
            try:
                record_planned(self.store, mig, run_id=run_id, trace_id=trace_id)
            except Exception as e:  # noqa: BLE001 — journal must not block propose
                log.warning("migration journal planned row failed: %s", e)

            self.bus.emit(ev.new_event(
                ev.SCHEMA_PROPOSED, spec_dir, ev.ACTOR_INSTRUMENTATION,
                payload={
                    "run_id": run_id,
                    "spec_dir": spec_dir,
                    "feature": feature_slug,
                    "schema_card": card,
                    "ddl": ddl,
                    "rationale": rationale,
                    "migration_plan": mig.to_dict(),
                    "migration_id": mig.plan_hash,
                },
                trace_id=trace_id,
            ))
            # ⏸ pipeline pauses here — approval required (D10)

    def on_approved(self, event: Event) -> None:
        """schema.approved → execute CREATE/ALTER + LOAD → schema.created.

        Cross-request concurrency: compare-and-swap on `meta.pending_runs`
        (`proposed` → `running` with a unique runner_token). Only the CAS winner
        executes DDL/load. In-process table locks still serialize DROP/CREATE on
        the same feature table within one process.
        """
        run_id = event.payload.get("run_id")
        if not run_id:
            raise ValueError("schema.approved missing run_id")

        pending = self._load_pending_run(run_id)
        if not pending:
            raise ValueError(f"approve_schema: no pending run found for {run_id}")
        if pending["state"] != STATE_PROPOSED:
            log.warning(
                "run %s already in state %s — ignoring duplicate approval",
                run_id, pending["state"],
            )
            return

        token = str(uuid.uuid4())
        if not self._cas_run_state(run_id, STATE_PROPOSED, STATE_RUNNING, runner_token=token):
            log.warning("run %s approve CAS lost — another worker/thread claimed it", run_id)
            return

        card = json.loads(pending["schema_card"])
        spec_dir = pending["spec_dir"]
        trace_id = pending["trace_id"] or event.trace_id
        feature = card["feature"]
        table = card["table"]
        events_path = self._resolve_spec_dir(spec_dir) / "events.ndjson"

        # Serialize DDL against the same table in this process; CAS already
        # handles cross-process double-approve on the same run_id.
        with self._locks.acquire(f"table:{table}"):
            try:
                with self._span("load", run_id=run_id, table=table,
                                ch_version=getattr(self.store, "server_version", None)):
                    # 4. Re-plan against live schema (card plan may be stale) and apply.
                    #    Additive ADD/widen by default; rebuild only when plan requires it
                    #    (incompatible types) — never silent DROP on mild drift (P0.1).
                    #    Journal gates double-apply + single-flight per table (P1.1).
                    live = self._live_columns(table)
                    plan = plan_migration(table, dict(card["columns"]), live, card["ddl"])
                    card["migration_plan"] = plan.to_dict()
                    card["migration_id"] = plan.plan_hash

                    with self._span("migration:begin", table=table, plan_hash=plan.plan_hash):
                        try:
                            mode = begin_apply(self.store, plan, run_id=run_id, trace_id=trace_id)
                        except RuntimeError as e:
                            log.error("migration lock: %s", e)
                            raise

                    applied: list[str]
                    if mode == "skip":
                        applied = ["skipped_idempotent"]
                        log.info("migration %s skipped via journal (already applied)", plan.plan_hash)
                    else:
                        with self._span("migration:apply", table=table, plan_hash=plan.plan_hash):
                            try:
                                applied = apply_migration_plan(self.store, plan)
                                finish_apply(self.store, plan, run_id=run_id, trace_id=trace_id,
                                             applied=applied)
                            except Exception as e:  # noqa: BLE001
                                finish_apply(self.store, plan, run_id=run_id, trace_id=trace_id,
                                             applied=[], error=str(e))
                                raise

                    log.info("migration for %s applied=%s rebuild=%s matched=%s",
                             table, applied, plan.requires_rebuild, plan.schema_matched)

                    # 5. load the raw events (flattened rows, aligned to the card's columns)
                    #    Idempotent (P0.2): skip when schema matched + events hash + row_count.
                    events = load_events(events_path)
                    current_hash = events_content_hash(events_path)
                    card_hash = card.get("events_hash") or current_hash
                    col_names = list(card["columns"].keys())
                    existing = self.store.row_count(table)
                    mutating = any(a in ("add_column", "widen_type", "create_table", "rebuild") for a in applied)
                    skip_load = (
                        (plan.schema_matched or mode == "skip")
                        and not plan.requires_rebuild
                        and card_hash == current_hash
                        and existing >= len(events)
                        and not mutating
                    )
                    # After additive ALTER or create/rebuild, always (re)load from NDJSON.
                    # Feature tables are fully derived from the spec — TRUNCATE avoids dupes.
                    if skip_load:
                        log.info("table %s already has %d rows (hash=%s) — skipping re-insert",
                                 table, existing, current_hash[:12])
                        row_count = existing
                    else:
                        row_count = self._load_events_idempotent(
                            table, card["ddl"], col_names, card["columns"], events,
                            existing=existing, matched=plan.schema_matched,
                        )
                        card["events_hash"] = current_hash

                    try:
                        record_load_snapshot(
                            self.store,
                            table_name=table,
                            plan_hash=plan.plan_hash,
                            events_hash=current_hash,
                            run_id=run_id,
                            trace_id=trace_id,
                            skipped=skip_load,
                        )
                    except Exception as e:  # noqa: BLE001
                        log.warning("migration journal load_snapshot failed: %s", e)

                    # 6. persist artifacts: generated/ + meta.schema_catalog + changelog
                    self._write_generated(feature, card, row_count)
                    self._upsert_schema_catalog(card, row_count, spec_dir, trace_id, applied, plan)
                    self._mark_run_state(run_id, STATE_APPROVED)

                self.bus.emit(ev.new_event(
                    ev.SCHEMA_CREATED, spec_dir, ev.ACTOR_INSTRUMENTATION,
                    payload={
                        "run_id": run_id,
                        "spec_dir": spec_dir,
                        "feature": feature,
                        "table": table,
                        "row_count": row_count,
                        "schema_card": card,
                        "trace_id": trace_id,
                        "migration_applied": applied,
                        "migration_id": plan.plan_hash,
                    },
                    trace_id=trace_id,
                ))
            except Exception:
                log.exception("approve chain failed for run %s", run_id)
                try:
                    if not self._cas_run_state(
                        run_id, STATE_RUNNING, STATE_FAILED, runner_token=token,
                    ):
                        self._mark_run_state(run_id, STATE_FAILED, runner_token=token)
                except Exception:  # noqa: BLE001
                    log.exception("could not mark run %s as failed", run_id)
                raise

    def on_rejected(self, event: Event) -> None:
        """schema.rejected → abort the run (no ClickHouse mutation)."""
        run_id = event.payload.get("run_id")
        if not run_id:
            raise ValueError("schema.rejected missing run_id")
        pending = self._load_pending_run(run_id)
        if not pending:
            raise ValueError(f"reject_schema: no pending run found for {run_id}")
        if pending["state"] != STATE_PROPOSED:
            log.warning(
                "run %s already in state %s — ignoring reject",
                run_id, pending["state"],
            )
            return
        token = str(uuid.uuid4())
        if not self._cas_run_state(run_id, STATE_PROPOSED, STATE_REJECTED, runner_token=token):
            log.warning("run %s reject CAS lost — already claimed", run_id)

    # -- pending runs (meta.pending_runs, §3.3) -----------------------------
    def _save_pending_run(self, run_id: str, spec_dir: str, card: dict, trace_id: str) -> None:
        self.store.insert(
            "meta.pending_runs",
            ["run_id", "state", "spec_dir", "schema_card", "trace_id", "runner_token"],
            [[run_id, STATE_PROPOSED, spec_dir, json.dumps(card), trace_id, ""]],
        )

    def _load_pending_run(self, run_id: str) -> dict | None:
        rows = self.store.query_rows(
            "SELECT run_id, state, spec_dir, schema_card, trace_id, runner_token "
            "FROM meta.pending_runs "
            "WHERE run_id = {rid:String} ORDER BY created_at DESC LIMIT 1",
            {"rid": run_id},
        )
        return rows[0] if rows else None

    def _live_columns(self, table: str) -> dict[str, str] | None:
        table = sanitize_identifier(table)
        if not self.store.table_exists(table):
            return None
        return {c["name"]: c["type"] for c in self.store.columns(table)}

    def _load_events_idempotent(
        self,
        table: str,
        ddl: str,
        col_names: list[str],
        col_types: dict,
        events: list[dict],
        *,
        existing: int,
        matched: bool,
    ) -> int:
        """Full reload with cleanup so partial inserts cannot duplicate rows.

        If the table already has some (but not enough) rows, or insert fails
        mid-batch, we TRUNCATE/rebuild before writing so a retry is clean.
        """
        table = sanitize_identifier(table)
        if existing > 0:
            log.info(
                "table %s has %d rows (expected %d, matched=%s) — wiping before reload",
                table, existing, len(events), matched,
            )
            self._wipe_table(table, ddl)

        rows = [[_coerce(r.get(c), col_types[c]) for c in col_names] for r in events]
        try:
            inserted = self.store.insert(table, col_names, rows)
            return inserted or len(rows)
        except Exception:
            log.exception("insert into %s failed — wiping partial rows", table)
            try:
                self._wipe_table(table, ddl)
            except Exception:  # noqa: BLE001
                log.exception("wipe after failed insert also failed for %s", table)
            raise

    def _wipe_table(self, table: str, ddl: str) -> None:
        """Empty a feature table; recreate from ddl if truncate is unavailable."""
        table = sanitize_identifier(table)
        try:
            self.store.command(f"TRUNCATE TABLE IF EXISTS {table}")
            if self.store.row_count(table) == 0:
                return
        except Exception:  # noqa: BLE001 — DryRun / restricted CH may lack TRUNCATE
            log.warning("TRUNCATE %s failed — falling back to DROP+CREATE", table)
        self.store.command(f"DROP TABLE IF EXISTS {table}")
        self.store.command(ddl)

    def _cas_run_state(
        self,
        run_id: str,
        from_state: str,
        to_state: str,
        *,
        runner_token: str,
    ) -> bool:
        """Compare-and-swap pending_runs.state (+ runner_token).

        ClickHouse applies table mutations sequentially, so
        `UPDATE … WHERE state = from_state` is a real CAS across workers.
        Returns True only if this caller's token owns the row afterwards.
        """
        allowed = {
            STATE_PROPOSED, STATE_RUNNING, STATE_APPROVED,
            STATE_REJECTED, STATE_FAILED, STATE_ABORTED,
        }
        if from_state not in allowed or to_state not in allowed:
            raise ValueError(f"invalid CAS states: {from_state!r} → {to_state!r}")
        rid = require_safe_token(run_id, what="run_id")
        tok = require_safe_token(runner_token, what="runner_token")
        self.store.command(
            f"ALTER TABLE meta.pending_runs UPDATE "
            f"state = {sql_string_literal(to_state)}, "
            f"runner_token = {sql_string_literal(tok)} "
            f"WHERE run_id = {sql_string_literal(rid)} "
            f"AND state = {sql_string_literal(from_state)} "
            f"SETTINGS mutations_sync = 1"
        )
        pending = self._load_pending_run(run_id)
        return bool(
            pending
            and pending["state"] == to_state
            and pending.get("runner_token") == tok
        )

    def _mark_run_state(
        self, run_id: str, state: str, *, runner_token: str | None = None,
    ) -> None:
        # Unconditional state write (failure path / fallback). Prefer _cas_run_state.
        allowed = {
            STATE_PROPOSED, STATE_RUNNING, STATE_APPROVED,
            STATE_REJECTED, STATE_FAILED, STATE_ABORTED,
        }
        if state not in allowed:
            raise ValueError(f"invalid pending_runs state: {state!r}")
        rid = require_safe_token(run_id, what="run_id")
        if runner_token is not None:
            tok = require_safe_token(runner_token, what="runner_token")
            self.store.command(
                f"ALTER TABLE meta.pending_runs UPDATE "
                f"state = {sql_string_literal(state)}, "
                f"runner_token = {sql_string_literal(tok)} "
                f"WHERE run_id = {sql_string_literal(rid)} SETTINGS mutations_sync = 1"
            )
        else:
            self.store.command(
                f"ALTER TABLE meta.pending_runs UPDATE state = {sql_string_literal(state)} "
                f"WHERE run_id = {sql_string_literal(rid)} SETTINGS mutations_sync = 1"
            )

    # -- meta catalog + changelog ------------------------------------------
    def _upsert_schema_catalog(self, card: dict, row_count: int, spec_dir: str,
                               trace_id: str, applied: list[str], plan) -> None:
        rationale = card.get("rationale") or {}
        if isinstance(rationale, str):
            try:
                rationale = json.loads(rationale)
            except json.JSONDecodeError:
                rationale = {"raw": rationale}
        else:
            rationale = dict(rationale)
        rationale["events_hash"] = card.get("events_hash", "")
        rationale["migration_plan_hash"] = plan.plan_hash
        rationale["migration_applied"] = applied

        self.store.insert(
            "meta.schema_catalog",
            ["table_name", "ddl", "rationale", "source_spec", "event_order", "columns",
             "row_count", "trace_id"],
            [[card["table"], card["ddl"], json.dumps(rationale), spec_dir,
              json.dumps(card["event_order"]), json.dumps(card["columns"]), row_count, trace_id]],
        )
        # Prefer the most specific applied action for the changelog row.
        action = "create_table"
        if plan.requires_rebuild or "rebuild" in applied:
            action = "rebuild"
        elif "add_column" in applied:
            action = "add_column"
        elif "widen_type" in applied:
            action = "alter_type"
        elif applied == ["skipped_idempotent"] or plan.schema_matched:
            action = "noop"
        version = next_schema_changelog_version(self.store)
        self.store.insert(
            "meta.schema_changelog",
            ["version", "agent", "action", "object", "diff", "rationale", "trace_id"],
            [[version, ev.ACTOR_INSTRUMENTATION, action, card["table"],
              json.dumps(plan.to_dict()), json.dumps(rationale), trace_id]],
        )

    # -- generated/ artifacts ----------------------------------------------
    def _write_generated(self, feature: str, card: dict, row_count: int) -> None:
        out = self.generated_dir / feature
        out.mkdir(parents=True, exist_ok=True)
        (out / "ddl.sql").write_text(card["ddl"] + "\n")
        card_json = {**card, "row_count": row_count}
        (out / "schema_card.json").write_text(json.dumps(card_json, indent=2) + "\n")

    # -- helpers ------------------------------------------------------------
    def _resolve_spec_dir(self, spec_dir: str) -> Path:
        """Resolve a spec_dir reference under `settings.specs_dir` only.

        Accepts `01_express_checkout` or `specs/01_express_checkout`. Rejects
        absolute paths, `..` segments, and anything that resolves outside
        the specs directory (path traversal).
        """
        if not spec_dir or not isinstance(spec_dir, str):
            raise ValueError("spec_dir required")
        raw = Path(spec_dir)
        if raw.is_absolute():
            raise ValueError(f"spec_dir must be relative to specs/: {spec_dir!r}")
        if ".." in raw.parts:
            raise ValueError(f"spec_dir must not contain '..': {spec_dir!r}")

        specs_root = self.settings.specs_dir.resolve()
        if raw.parts and raw.parts[0] == "specs":
            candidate = (self.settings.atlys_root / raw).resolve()
        else:
            candidate = (specs_root / raw).resolve()

        try:
            candidate.relative_to(specs_root)
        except ValueError as exc:
            raise ValueError(
                f"spec_dir escapes specs directory: {spec_dir!r}"
            ) from exc

        return candidate

    def _span(self, name: str, **meta):
        if self.tracer is None:
            import contextlib
            return contextlib.nullcontext()
        return self.tracer.span(name, **meta)

    def interrogate(self, spec_dir: str) -> dict:
        """Deterministic gap/questions list for a spec (US2) — no LLM, no writes."""
        events = load_events(self._resolve_spec_dir(spec_dir) / "events.ndjson")
        inferred = infer_types(events)
        gaps: list[dict] = []
        feature_slug = _slug(Path(spec_dir).name)
        envelope_names = {n for n, _ in ENVELOPE}

        flat_cols = [c for c in inferred.columns if "_" in c]
        if flat_cols:
            gaps.append({
                "severity": "info",
                "question": "Nested objects will be flattened with `_`",
                "detail": "columns: " + ", ".join(sorted(flat_cols)),
            })
        if not inferred.has_user_id:
            gaps.append({
                "severity": "warning",
                "question": "No user_id in the events",
                "detail": "analytics will bucket under '' — verify this spec's grain",
            })
        if len(inferred.event_order) == 1:
            gaps.append({
                "severity": "info",
                "question": "Single-event spec",
                "detail": "funnel playbook steps degrade gracefully (P2/P4 still run)",
            })
        bool_cols = [c for c, t in inferred.columns.items() if t in {"UInt8", "Nullable(UInt8)"}]
        if bool_cols:
            gaps.append({
                "severity": "info",
                "question": "Boolean-looking columns typed UInt8",
                "detail": ", ".join(sorted(bool_cols)),
            })
        json_string_cols = [
            c for c, t in inferred.columns.items()
            if c not in envelope_names and "String" in t and c.endswith(("s", "tags", "items", "ids"))
        ]
        if json_string_cols:
            gaps.append({
                "severity": "info",
                "question": "Array/object-like fields stored as JSON String",
                "detail": ", ".join(sorted(json_string_cols)),
            })
        return {
            "spec_dir": spec_dir,
            "feature": feature_slug,
            "event_order": inferred.event_order,
            "columns": dict(inferred.columns),
            "row_count": inferred.row_count,
            "gaps": gaps,
            "clickhouse_version": getattr(self.store, "server_version", None),
        }


def _coerce(value: Any, ctype: str) -> Any:
    """Coerce a raw JSON value to the inferred ClickHouse column type.

    clickhouse-connect requires real `datetime` objects for DateTime columns
    (ISO strings raise AttributeError on insert), so timestamps are parsed here.
    """
    if value is None:
        return None
    if "DateTime" in ctype:
        return _parse_timestamp(value)
    if "UInt8" in ctype or "Int8" in ctype:
        return int(bool(value)) if isinstance(value, bool) else int(value)
    if "UInt16" in ctype or "Int16" in ctype or "UInt32" in ctype or "Int32" in ctype or "Int64" in ctype or "UInt64" in ctype:
        return int(value)
    if "Float64" in ctype or "Float32" in ctype:
        return float(value)
    return value


def _parse_timestamp(value: Any) -> Any:
    """ISO-8601 string → naive UTC datetime (ClickHouse DateTime / DateTime64)."""
    if isinstance(value, str):
        import datetime as _dt
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = _dt.datetime.fromisoformat(v)
        if dt.tzinfo is not None:
            dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        return dt
    return value
