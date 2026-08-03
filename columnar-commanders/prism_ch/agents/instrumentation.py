"""Instrumentation Agent: feature spec -> executed ClickHouse schema.

**One table per user action.** `spec.md` declares the raw events a feature
emits; each becomes its own table, matching how the eight existing Atlys source
tables are built. The events file is correlated onto that list, split per
action, and each group is sampled and profiled independently - see
`spec_split.py` for why the spec leads and the data follows.

Six steps, each its own traced span:

1. **profile** - deterministic statistics per action group (no LLM)
2. **design** - LLM turns spec + per-action profiles into a SchemaProposal
3. **validate** - the DDL is created in a throwaway database first
4. **reconcile** - existing tables get `ALTER TABLE ADD COLUMN` for anything new
5. **execute** - only then against the real database
6. **load** - insert each group's full rows into its own table, repairing any
   column ClickHouse reports as unmapped, so a schema that merely *parses* is
   not mistaken for one that actually accepts the data it was designed from

Step 3 is the cheap insurance. A type error or a bad codec surfaces against a
scratch database instead of half-creating tables in the one that counts - which
matters most on the run you cannot repeat.

Nothing here ever drops a table. An existing table is widened, never replaced:
the run that would recover from a bad drop is the one you cannot repeat either.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from dataclasses import dataclass, field, replace
from typing import Any

from ..config import Settings
from ..tracing import agent_step
from . import llm
from .dialect import Dialect, for_settings
from .lint import lint_proposal
from .profiling import (
    default_for,
    profile_events,
    profile_summary,
    suggest_codec,
    suggest_order_by,
    suggest_type,
)
from .rules import (
    INSTRUMENTATION_PREFIXES,
    load_rules,
    rules_for,
    skill_guidance,
)
from .types import (
    ColumnSpec,
    ContextDiff,
    EventGroup,
    InsightReport,
    MaterializedViewSpec,
    SchemaProposal,
    SpecInput,
    TableSpec,
    parse_proposal,
)

log = logging.getLogger(__name__)

# ClickHouse's own wording for an INSERT ... FORMAT JSONEachRow key with no
# matching column, confirmed live: "Unknown field found while parsing
# JSONEachRow format: c: (at row 1)". The field name sits between "format: "
# and the next non-identifier character.
_UNKNOWN_FIELD_RE = re.compile(r"Unknown field found while parsing \w+ format:\s*([A-Za-z0-9_]+)")

_BASE_PROMPT = (pathlib.Path(__file__).parent / "prompts" / "instrumentation.md").read_text()

# The vendored rule text is appended verbatim, so the model reasons from the
# real rules rather than the summary in the prompt above - and its citations
# resolve to files a reviewer can open in this repo.
# SKILL.md first (how to apply and cite), then the rules themselves in the
# official priority order - CRITICAL categories nearest the task.
PROMPT = "\n\n---\n\n".join(
    part
    for part in (
        _BASE_PROMPT,
        skill_guidance(),
        load_rules(*rules_for(*INSTRUMENTATION_PREFIXES)),
    )
    if part
)


class SchemaLintError(RuntimeError):
    """A schema that is valid SQL but a poor design."""


@dataclass
class LoadResult:
    """One table's attempt to accept the sampled events for real."""

    table: str
    attempted: int
    loaded: int
    columns_added: list[str] = field(default_factory=list)
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "attempted": self.attempted,
            "loaded": self.loaded,
            "columns_added": self.columns_added,
            "error": self.error,
        }


@dataclass
class ExecutedStatement:
    """One statement actually sent to ClickHouse, and how it went.

    Surfaced to the caller so the UI can show the exact DDL as it runs rather
    than only the proposal that produced it - an ALTER the agent decided on by
    itself is precisely the thing a reviewer needs to see.
    """

    sql: str
    kind: str  # create_database | create_table | create_view | alter_table
    table: str = ""
    ok: bool = True
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "sql": self.sql,
            "kind": self.kind,
            "table": self.table,
            "ok": self.ok,
            "error": self.error,
        }


@dataclass
class InstrumentationResult:
    spec_name: str
    proposal: SchemaProposal
    statements: list[str]
    executed: bool
    decisions: list[dict[str, Any]]
    load_results: list[LoadResult] = field(default_factory=list)
    executed_statements: list[ExecutedStatement] = field(default_factory=list)
    # Declared in the spec but absent from the data, and vice versa.
    empty_actions: list[str] = field(default_factory=list)
    undeclared_actions: dict[str, int] = field(default_factory=dict)


class InstrumentationAgent:
    def __init__(self, settings: Settings, client: Any) -> None:
        self.settings = settings
        self.client = client
        # Accumulated across steps so callers can render the reasoning without
        # reading the trace - the approval gate needs it inline.
        self.decisions: list[dict[str, Any]] = []
        self.repairs = 0
        self.lint_issues = 0
        self.steps: list[dict[str, Any]] = []
        self.dialect: Dialect = for_settings(
            settings.clickhouse_target,
            settings.database,
            settings.cluster,
            settings.table_prefix,
        )
        self.executed_statements: list[ExecutedStatement] = []
        self.preexisting_tables: set[str] = set()
        # Populated by _notify_context() - the chain this run set off:
        # instrument -> context refresh -> analytics. None until execute=True
        # actually runs and _notify_context succeeds.
        self.context_version: int | None = None
        self.context_delta: ContextDiff | None = None
        self.last_insight_report: InsightReport | None = None
        self.last_analytics_run_id: str | None = None
        self.last_analytics_trace_id: str | None = None
        # True when this run seeded the context layer from the bundled
        # base_context.md because the database had no context version yet.
        self.bootstrapped_default_context = False

    # --- 0. split -------------------------------------------------------------

    def groups_for(self, spec: SpecInput) -> list[EventGroup]:
        """One group per table to design.

        Normally the user actions the spec declared. When a spec declares none
        - a bare brief, or a format the parser did not recognise - fall back to
        a single table for the whole feature rather than producing nothing.
        """
        if spec.groups:
            return spec.groups
        return [
            EventGroup(
                action=f"{spec.name}_events",
                events=spec.events,
                load_events=spec.load_events or spec.events,
                total=spec.events_total or len(spec.events),
            )
        ]

    # --- 1. profile -----------------------------------------------------------

    def profile(self, groups: list[EventGroup], spec: SpecInput) -> dict[str, list[dict[str, Any]]]:
        """Profile each action group on its own. Returns {action: summary}."""
        with agent_step(
            "instrumentation",
            "profile_events",
            input={"spec": spec.name, "actions": [g.action for g in groups]},
        ) as step:
            summaries: dict[str, list[dict[str, Any]]] = {}
            enums: list[str] = []
            for group in groups:
                summary = profile_summary(profile_events(group.events))
                summaries[group.action] = summary
                enums += [
                    f"{group.action}.{p['name']}" for p in summary if p["looks_like"] == "enum"
                ]

            empty = [g.action for g in groups if not g.load_events]
            step.decision(
                what=(
                    f"profiled {len(groups)} action group(s): "
                    + ", ".join(
                        f"{g.action} ({len(summaries[g.action])} fields, "
                        f"{len(g.events)}/{g.total} rows)"
                        for g in groups
                    )
                ),
                why=(
                    "each user action becomes its own table, so each is sampled and "
                    "profiled on its own rows - a pooled sample would give the rarer "
                    "actions a thinner profile than the common ones for no reason"
                ),
                evidence={"low_cardinality_candidates": enums[:20], "empty_actions": empty},
            )
            if spec.undeclared_actions:
                step.decision(
                    what=(
                        f"data carries {len(spec.undeclared_actions)} event(s) "
                        "the spec never declared"
                    ),
                    why=(
                        "the spec is the source of truth for which tables exist, so these "
                        "get no table - but undocumented instrumentation is worth reporting"
                    ),
                    evidence={"undeclared": spec.undeclared_actions},
                    confidence=1.0,
                )
            step.metrics_from(
                action_groups=len(groups),
                events_sampled=sum(len(g.events) for g in groups),
                events_total=sum(g.total for g in groups),
                fields_profiled=sum(len(s) for s in summaries.values()),
                empty_actions=len(empty),
                undeclared_actions=len(spec.undeclared_actions),
                brief_chars=len(spec.brief),
            )
            step.output({"actions": {a: len(s) for a, s in summaries.items()}})
            self.steps.append(step.snapshot())
            self.decisions += [d.as_dict() for d in step.decisions]
            return summaries

    # --- 2. design ------------------------------------------------------------

    def design(
        self,
        spec: SpecInput,
        groups: list[EventGroup],
        summaries: dict[str, list[dict[str, Any]]],
    ) -> SchemaProposal:
        with agent_step("instrumentation", "design_schema", input={"spec": spec.name}) as step:
            if not self.settings.llm_enabled:
                log.warning("LLM disabled - falling back to the deterministic baseline schema")
                proposal = self._baseline(groups)
                step.decision(
                    what="used the deterministic baseline schema",
                    why="no LLM configured; a working schema beats no schema",
                    confidence=0.4,
                )
                step.output(proposal.as_dict())
                self.steps.append(step.snapshot())
                self.decisions += [d.as_dict() for d in step.decisions]
                return proposal

            payload = llm.complete(
                self.settings,
                name="design_schema",
                system=PROMPT,
                prompt=self._user_prompt(spec, groups, summaries),
                as_json=True,
            )
            proposal = parse_proposal(payload)  # type: ignore[arg-type]

            for entry in payload.get("decisions", []):  # type: ignore[union-attr]
                if not entry.get("why"):
                    continue  # a decision without reasoning is not one
                step.decision(
                    what=entry.get("what", ""),
                    why=entry["why"],
                    alternatives=entry.get("alternatives", []),
                    confidence=entry.get("confidence"),
                    rules=entry.get("rules", []),
                )

            step.metrics_from(
                tables_proposed=len(proposal.tables),
                columns_proposed=sum(len(t.columns) for t in proposal.tables),
                materialized_views=len(proposal.materialized_views),
                decisions=len(step.decisions),
                rules_cited=len({r for d in step.decisions for r in d.rules}),
            )
            step.output(proposal.as_dict(), notes=proposal.notes)
            self.steps.append(step.snapshot())
            self.decisions += [d.as_dict() for d in step.decisions]
            return proposal

    def _user_prompt(
        self,
        spec: SpecInput,
        groups: list[EventGroup],
        summaries: dict[str, list[dict[str, Any]]],
    ) -> str:
        parts = [f"# Feature spec: {spec.name}\n\n{spec.brief}"]
        parts.append(
            f"# Design {len(groups)} table(s) - one per user action\n\n"
            "Each user action below is its own table, named **exactly** as the action "
            "(no suffix, no prefix). This mirrors the existing source tables, which are "
            "one table per event joined on `user_id` / `application_id`.\n\n"
            "Every profile is computed from a sample of **only that action's rows**, so "
            "cardinality and null rates are specific to that table - use each action's "
            "own numbers when choosing its types and ordering key. The shared envelope "
            "repeats across tables by design; type it consistently everywhere."
        )
        for group in groups:
            summary = summaries.get(group.action, [])
            header = (
                f"## `{group.action}` - {len(summary)} fields, "
                f"{len(group.events)} of {group.total} rows sampled"
            )
            if not group.load_events:
                header += "\n\nThe spec declares this action but the sample contains no rows. "
                header += "Design it from the spec text alone and say so in `notes`."
            parts.append(f"{header}\n\n```json\n{json.dumps(summary, indent=2, default=str)}\n```")

        if spec.undeclared_actions:
            parts.append(
                "# Events present in the data but not declared in the spec\n\n"
                f"```json\n{json.dumps(spec.undeclared_actions, indent=2)}\n```\n"
                "Do not create tables for these - the spec decides. Mention them in `notes`."
            )
        parts.append(
            f"Target: ClickHouse {self.dialect.target}. Database: {self.settings.database}.\n"
            "Design the schema. Return only the JSON object."
        )
        return "\n\n".join(parts)

    @staticmethod
    def _is_numeric_type(ch_type: str) -> bool:
        inner = ch_type[len("Nullable(") : -1] if ch_type.startswith("Nullable(") else ch_type
        return inner.startswith(("UInt", "Int", "Float", "Decimal"))

    def _rollup_for(
        self, table: TableSpec, time_col: str | None
    ) -> tuple[TableSpec, MaterializedViewSpec] | None:
        """A mechanical dimensional rollup for the deterministic baseline path.

        The mandatory-MV lint rule (`mv-coverage-missing`) applies here too -
        "no LLM available" is not a way to skip a hard requirement. GROUP BY
        every LowCardinality column plus an hourly bucket; never a
        high-cardinality identifier - those become `uniqState(...)` instead,
        per the instrumentation prompt's own rule for the LLM path.
        """
        dims = [c for c in table.columns if c.type.startswith("LowCardinality(")]
        numeric = [c for c in table.columns if self._is_numeric_type(c.type)]
        user_col = next((c for c in table.columns if c.name == "user_id"), None)
        if not dims and not numeric and user_col is None and not time_col:
            return None  # nothing on this table is worth pre-aggregating

        group_cols = [c.name for c in dims]
        select_parts = list(group_cols)
        target_columns = [ColumnSpec(c.name, c.type) for c in dims]

        if time_col:
            group_cols.append("hour")
            select_parts.append(f"toStartOfHour({time_col}) AS hour")
            target_columns.append(ColumnSpec("hour", "DateTime"))

        select_parts.append("countState() AS event_count")
        target_columns.append(ColumnSpec("event_count", "AggregateFunction(count)"))

        if user_col:
            select_parts.append(f"uniqState({user_col.name}) AS unique_users")
            target_columns.append(
                ColumnSpec("unique_users", f"AggregateFunction(uniq, {user_col.type})")
            )

        for col in numeric:
            select_parts.append(f"sumState({col.name}) AS {col.name}_sum")
            target_columns.append(
                ColumnSpec(f"{col.name}_sum", f"AggregateFunction(sum, {col.type})")
            )

        target_name = f"{table.name}_rollup"
        view = MaterializedViewSpec(
            name=f"mv_{target_name}",
            target_table=target_name,
            select=(
                f"SELECT {', '.join(select_parts)} FROM {table.name} "
                f"GROUP BY {', '.join(group_cols)}"
            ),
            why=(
                f"pre-aggregates {table.name} by its dimension columns so the "
                "Analytics Agent can answer common cuts without rescanning "
                "raw events (deterministic baseline - no LLM available)"
            ),
        )
        target = TableSpec(
            name=target_name,
            columns=target_columns,
            order_by=group_cols or ["event_count"],
            ttl="hour + INTERVAL 365 DAY" if time_col else None,
            engine="AggregatingMergeTree",
            comment=f"dimensional rollup of {table.name}",
        )
        return target, view

    def _baseline(self, groups: list[EventGroup]) -> SchemaProposal:
        """Deterministic fallback so the pipeline still produces something."""
        tables: list[TableSpec] = []
        views: list[MaterializedViewSpec] = []
        mapping: dict[str, str] = {}

        for group in groups:
            profiles = profile_events(group.events)
            if not profiles:
                continue
            columns = []
            for p in profiles:
                ch_type = suggest_type(p)
                columns.append(
                    ColumnSpec(
                        name=p.name,
                        type=ch_type,
                        codec=suggest_codec(p),
                        source_field=p.name,
                        # A DEFAULT stands in for the Nullable we did not add.
                        default=(
                            default_for(ch_type)
                            if p.null_rate > 0 and not ch_type.startswith("Nullable")
                            else None
                        ),
                    )
                )
            time_col = next((p.name for p in profiles if p.looks_like == "timestamp"), None)
            table = TableSpec(
                name=group.action,
                columns=columns,
                order_by=suggest_order_by(profiles),
                partition_by=f"toYYYYMM({time_col})" if time_col else None,
                # Retention is a decision even here; the lint enforces it.
                ttl=(f"toDateTime({time_col}) + INTERVAL 180 DAY" if time_col else None),
                comment=f"raw {group.action} events",
            )
            tables.append(table)
            mapping.update({c.name: c.name for c in columns})

            rollup = self._rollup_for(table, time_col)
            if rollup is not None:
                target, view = rollup
                tables.append(target)
                views.append(view)

        return SchemaProposal(
            tables=tables,
            materialized_views=views,
            event_mapping=mapping,
            notes="deterministic baseline - no LLM was available",
        )

    # --- 3. validate ----------------------------------------------------------

    def validate(self, proposal: SchemaProposal) -> list[str]:
        """Render DDL and prove it executes, in a database we then throw away."""
        statements = self.render(proposal)  # also rewrites MV selects in place
        scratch = f"{self.settings.database}_validate"
        probe = Dialect(
            target=self.dialect.target,
            database=scratch,
            cluster=self.dialect.cluster,
            table_prefix=self.dialect.table_prefix,
        )

        with agent_step("instrumentation", "validate_ddl") as step:
            self.client.command(probe.create_database())
            try:
                for table in proposal.tables:
                    self.client.command(probe.create_table(table))

                # Materialized views must be validated too. Skipping them is how
                # an UNKNOWN_TABLE reaches the real database *after* the base
                # tables are already created. Their SELECT is repointed at the
                # scratch database so it resolves against what we just built.
                for view in proposal.materialized_views:
                    probe_view = replace(
                        view,
                        select=view.select.replace(f"{self.settings.database}.", f"{scratch}."),
                    )
                    self.client.command(probe.create_materialized_view(probe_view))

                step.decision(
                    what=(
                        f"validated {len(proposal.tables)} table(s) and "
                        f"{len(proposal.materialized_views)} view(s) against {scratch}"
                    ),
                    why=(
                        "executing generated DDL in a scratch database first means a bad "
                        "type or codec cannot half-create tables in the real one"
                    ),
                    confidence=0.95,
                )
            except Exception as exc:
                step.decision(
                    what="DDL validation failed",
                    why=str(exc),
                    confidence=1.0,
                )
                raise
            finally:
                self.client.command(probe.drop_database(scratch))

            step.metrics_from(
                statements=len(statements),
                tables_validated=len(proposal.tables),
            )
            step.output({"statements": len(statements)})
            self.steps.append(step.snapshot())
            self.decisions += [d.as_dict() for d in step.decisions]
            return statements

    def qualify_select(self, select: str, table_names: set[str]) -> str:
        """Rewrite table references in an MV's SELECT to their physical names,
        always fully qualified with this database.

        The model writes `FROM atlys.express_checkout_events` - or just as
        often `FROM default.express_checkout_events` (assuming ClickHouse's
        own `default` database is active), or leaves it bare as
        `FROM express_checkout_events` - but the table is created as
        `prism_express_checkout_events`: the prefix is applied when rendering
        DDL, and a free-text SELECT never sees it. Left unqualified or wrongly
        qualified, `validate()` cannot redirect the reference at the scratch
        database (it works by string-replacing `{database}.`, so it needs
        that qualifier to already be there) - a bare or wrongly-qualified
        reference instead resolves against whatever database is active on
        the connection running the query, which is the real database, not
        the scratch one being validated against. So every reference this
        rewrites - qualified correctly, qualified with something else
        (`default`, a guess), or bare - always ends up as
        `{database}.{physical_name}`, unconditionally.
        """
        db = self.settings.database
        # Longest first, so a name that is a prefix of another is not clipped.
        for name in sorted(table_names, key=len, reverse=True):
            physical = self.dialect.physical_name(name)
            select = re.sub(
                rf"(?<![\w.])(?:\w+\.)?{re.escape(name)}\b",
                f"{db}.{physical}",
                select,
            )
        return select

    def render(self, proposal: SchemaProposal) -> list[str]:
        names = {t.name for t in proposal.tables}
        statements = [self.dialect.create_database()]
        statements += [self.dialect.create_table(t) for t in proposal.tables]
        for view in proposal.materialized_views:
            view.select = self.qualify_select(view.select, names)
            statements.append(self.dialect.create_materialized_view(view))
        return statements

    # --- 4. execute -----------------------------------------------------------

    @staticmethod
    def _kind_of(sql: str) -> str:
        head = sql.lstrip().upper()
        if head.startswith("CREATE DATABASE"):
            return "create_database"
        if head.startswith("CREATE MATERIALIZED VIEW"):
            return "create_view"
        if head.startswith("CREATE TABLE"):
            return "create_table"
        if head.startswith("ALTER TABLE"):
            return "alter_table"
        return "other"

    def _run_sql(self, step: Any, sql: str, *, purpose: str, table: str = "") -> ExecutedStatement:
        """Execute one statement, recording it for display either way.

        Never raises. This runs after `validate()` has already proven the
        proposal executes clean against a scratch database - a failure here is
        an edge case validation could not catch (a race with concurrent DDL, a
        transient network error), not a reason to abandon every other
        statement, table, or event still queued behind it. Callers check
        `record.ok` for anything that needs to react to the failure.
        """
        record = ExecutedStatement(sql=sql, kind=self._kind_of(sql), table=table)
        step.sql(sql, purpose=purpose)
        try:
            self.client.command(sql)
        except Exception as exc:  # noqa: BLE001 - recorded and logged, never fatal
            record.ok, record.error = False, str(exc)[:400]
            log.warning("DDL statement failed, continuing: %s", record.error)
        self.executed_statements.append(record)
        return record

    @staticmethod
    def _table_of(sql: str) -> str:
        """Physical table named by a CREATE/ALTER statement, when present."""
        match = re.search(
            r"(?:CREATE\s+(?:MATERIALIZED\s+VIEW|TABLE)|ALTER\s+TABLE)\s+"
            r"(?:IF\s+NOT\s+EXISTS\s+)?`[^`]+`\.`([^`]+)`",
            sql,
            re.IGNORECASE,
        )
        return match.group(1) if match else ""

    def execute(self, statements: list[str]) -> None:
        with agent_step("instrumentation", "execute_ddl") as step:
            failed = 0
            for sql in statements:
                record = self._run_sql(step, sql, purpose="create schema", table=self._table_of(sql))
                failed += 0 if record.ok else 1
            ok = len(statements) - failed
            step.decision(
                what=(
                    f"executed {ok} of {len(statements)} DDL statement(s)"
                    + (f", {failed} failed and were skipped rather than aborting the run" if failed else "")
                ),
                why="the brief requires the agent to create the tables, not just propose them",
                confidence=1.0 if not failed else 0.5,
            )
            step.metrics_from(statements_executed=ok, statements_failed=failed)
            step.output({"executed": ok, "failed": failed})
            self.steps.append(step.snapshot())
            self.decisions += [d.as_dict() for d in step.decisions]

    # --- reconcile existing tables ----------------------------------------

    def existing_tables(self, proposal: SchemaProposal) -> list[str]:
        """Physical table names in `proposal` that already exist for real.

        `CREATE TABLE IF NOT EXISTS` makes re-running against an existing
        table a silent no-op - the proposal can differ completely from what
        is already there and nothing would say so. This check turns that
        silence into an explicit `ALTER TABLE ADD COLUMN`.
        """
        names = [self.dialect.physical_name(t.name) for t in proposal.tables]
        if not names:
            return []
        result = self.client.query(
            "SELECT name FROM system.tables "
            "WHERE database = {db:String} AND name IN {names:Array(String)}",
            parameters={"db": self.settings.database, "names": names},
        )
        rows = getattr(result, "result_rows", None) or []
        return [r[0] for r in rows]

    def _existing_columns(self, physical_name: str) -> set[str]:
        result = self.client.query(
            "SELECT name FROM system.columns WHERE database = {db:String} AND table = {t:String}",
            parameters={"db": self.settings.database, "t": physical_name},
        )
        rows = getattr(result, "result_rows", None) or []
        return {r[0] for r in rows}

    def reconcile(self, proposal: SchemaProposal, existing: set[str]) -> list[str]:
        """Widen existing tables to match the proposal: add what is missing.

        Never drops, never recreates, never asks. `ORDER BY`, `PARTITION BY`
        and `TTL` are immutable after creation and are deliberately left alone
        - the only safe direction for a table that already holds data is
        wider. A column the proposal drops stays; a column it adds appears.
        """
        added: list[str] = []
        failed: list[str] = []
        with agent_step("instrumentation", "reconcile_existing") as step:
            for table in proposal.tables:
                physical = self.dialect.physical_name(table.name)
                if physical not in existing:
                    continue
                have = self._existing_columns(physical)
                for col in table.columns:
                    if col.name in have:
                        continue
                    record = self._run_sql(
                        step,
                        self.dialect.add_column(table.name, col),
                        purpose=f"widen {physical}: column missing from the existing table",
                        table=physical,
                    )
                    (added if record.ok else failed).append(f"{physical}.{col.name}")
            step.decision(
                what=(
                    f"added {len(added)} column(s) to existing table(s): {added}"
                    + (f"; {len(failed)} failed and were skipped: {failed}" if failed else "")
                    if added or failed
                    else f"{len(existing)} table(s) already existed and already cover this proposal"
                ),
                why=(
                    "an existing table is widened, never replaced - dropping it would "
                    "destroy data the pipeline cannot recreate, and the run that needs "
                    "recovering is the one that cannot be repeated"
                ),
                confidence=1.0 if not failed else 0.5,
            )
            step.metrics_from(
                tables_existing=len(existing), columns_added=len(added), columns_failed=len(failed)
            )
            step.output({"added": added, "failed": failed})
            self.steps.append(step.snapshot())
            self.decisions += [d.as_dict() for d in step.decisions]
        return added

    # --- load -------------------------------------------------------------

    def table_for(self, action: str, proposal: SchemaProposal, used: set[str]) -> TableSpec | None:
        """Find the table the model designed for this action.

        Exact name first - the prompt asks for exactly that. A model that
        suffixes or prefixes anyway (`..._events`) still resolves, as long as
        the match is unambiguous; a guess between two candidates is worse than
        reporting the action unloaded.
        """
        exact = next((t for t in proposal.tables if t.name == action and t.name not in used), None)
        if exact is not None:
            return exact
        near = [
            t
            for t in proposal.tables
            if t.name not in used and (action in t.name or t.name in action)
        ]
        return near[0] if len(near) == 1 else None

    def load_groups(self, groups: list[EventGroup], proposal: SchemaProposal) -> list[LoadResult]:
        """Insert each action's full rows into that action's own table.

        The full group, not its profiling sample: an INSERT is not an LLM call,
        so there is no token-cost reason to leave real events out of the table.

        Materialized-view targets are excluded - ClickHouse populates those
        itself from the base table's INSERT, via the view's own SELECT, and a
        second direct insert would double the rows.
        """
        mv_targets = {v.target_table for v in proposal.materialized_views if v.target_table}
        results: list[LoadResult] = []
        used: set[str] = set()

        for group in groups:
            table = self.table_for(group.action, proposal, used)
            if table is None:
                if group.load_events:
                    results.append(
                        LoadResult(
                            table=group.action,
                            attempted=len(group.load_events),
                            loaded=0,
                            error="no table in the proposal matched this user action",
                        )
                    )
                continue
            used.add(table.name)
            if table.name in mv_targets:
                continue
            results.append(self._load_table(table, group.load_events))

        return results

    def _load_table(self, table: TableSpec, events: list[dict[str, Any]]) -> LoadResult:
        if not events:
            return LoadResult(table=table.name, attempted=0, loaded=0)

        columns_added: list[str] = []
        current = {c.name for c in table.columns}
        max_attempts = self.settings.ddl_repair_attempts + 1

        for attempt in range(1, max_attempts + 1):
            payload = "\n".join(json.dumps(e, default=str) for e in events)
            sql = (
                f"INSERT INTO {self.dialect.qualified(table.name)} "
                "SETTINGS input_format_skip_unknown_fields = 0\n"
                f"FORMAT JSONEachRow\n{payload}"
            )
            with agent_step(
                "instrumentation", "load_events", input={"table": table.name, "attempt": attempt}
            ) as step:
                try:
                    self.client.command(sql)
                except Exception as exc:  # noqa: BLE001 - classified below
                    error = str(exc)
                    unknown = _UNKNOWN_FIELD_RE.search(error)
                    field_name = unknown.group(1) if unknown else None
                    can_repair = field_name and field_name not in current and attempt < max_attempts

                    if not can_repair:
                        step.decision(
                            what=f"load into {table.name} failed",
                            why=error[:300],
                            confidence=1.0,
                        )
                        step.output({"loaded": 0, "columns_added": columns_added})
                        self.steps.append(step.snapshot())
                        self.decisions += [d.as_dict() for d in step.decisions]
                        return LoadResult(
                            table=table.name,
                            attempted=len(events),
                            loaded=0,
                            columns_added=columns_added,
                            error=error[:300],
                        )

                    profile = next(
                        (p for p in profile_events(events) if p.name == field_name), None
                    )
                    col = ColumnSpec(
                        name=field_name,
                        type=suggest_type(profile) if profile else "String",
                        codec=suggest_codec(profile) if profile else None,
                        source_field=field_name,
                        comment=(
                            "added automatically - ClickHouse reported it as "
                            "unmapped during the load"
                        ),
                    )
                    record = self._run_sql(
                        step,
                        self.dialect.add_column(table.name, col),
                        purpose=f"repair: add {field_name!r}, named in the server error",
                        table=self.dialect.physical_name(table.name),
                    )
                    if not record.ok:
                        # The column that would have fixed the insert never
                        # landed - retrying would just fail the same way, and
                        # marking it added when it is not would make later
                        # loads assume it exists. Report and move to the next
                        # group instead of raising.
                        step.decision(
                            what=f"load into {table.name} failed - could not add column {field_name!r}",
                            why=record.error or "unknown error",
                            confidence=1.0,
                        )
                        step.output({"loaded": 0, "columns_added": columns_added})
                        self.steps.append(step.snapshot())
                        self.decisions += [d.as_dict() for d in step.decisions]
                        return LoadResult(
                            table=table.name,
                            attempted=len(events),
                            loaded=0,
                            columns_added=columns_added,
                            error=record.error,
                        )
                    table.columns.append(col)
                    current.add(field_name)
                    columns_added.append(field_name)
                    step.decision(
                        what=(
                            f"added column {field_name!r} ({col.type}) after "
                            "ClickHouse rejected an unmapped field"
                        ),
                        why=f"server error: {error[:200]}",
                        confidence=0.7,
                    )
                    step.output({"loaded": 0, "columns_added": columns_added})
                    self.steps.append(step.snapshot())
                    self.decisions += [d.as_dict() for d in step.decisions]
                    continue  # retry the insert with the repaired schema
                else:
                    step.decision(
                        what=f"loaded {len(events)} row(s) into {table.name}",
                        why="proves the schema accepts the real data, not just DDL-valid syntax",
                        confidence=1.0,
                    )
                    step.metrics_from(rows_loaded=len(events), columns_added=len(columns_added))
                    step.output({"loaded": len(events), "columns_added": columns_added})
                    self.steps.append(step.snapshot())
                    self.decisions += [d.as_dict() for d in step.decisions]
                    return LoadResult(
                        table=table.name,
                        attempted=len(events),
                        loaded=len(events),
                        columns_added=columns_added,
                    )

        return LoadResult(
            table=table.name,
            attempted=len(events),
            loaded=0,
            columns_added=columns_added,
            error="repair attempts exhausted",
        )

    # --- orchestration --------------------------------------------------------

    def repair(
        self,
        spec: SpecInput,
        groups: list[EventGroup],
        summaries: dict[str, list[dict[str, Any]]],
        proposal: SchemaProposal,
        error: str,
    ) -> SchemaProposal:
        """Feed a validation failure back to the model and ask it to fix the DDL.

        The model reliably produces *plausible* ClickHouse that the server
        rejects - a SimpleAggregateFunction column in an ORDER BY, a codec on a
        type that will not take one. Aborting the run on that is the wrong
        trade: on the unseen spec an abort means no output at all, while the
        server's own error message is a precise, actionable correction.
        """
        with agent_step("instrumentation", "repair_ddl", input={"error": error[:500]}) as step:
            payload = llm.complete(
                self.settings,
                name="repair_schema",
                system=PROMPT,
                prompt=(
                    f"{self._user_prompt(spec, groups, summaries)}\n\n"
                    "# Your previous proposal was rejected by ClickHouse\n\n"
                    f"```json\n{json.dumps(proposal.as_dict(), indent=2, default=str)}\n```\n\n"
                    f"# Server error\n\n{error}\n\n"
                    "Fix the specific cause and return the corrected JSON object. "
                    "Keep every decision that was not implicated in the error."
                ),
                as_json=True,
            )
            repaired = parse_proposal(payload)  # type: ignore[arg-type]
            step.decision(
                what="revised the schema after a validation failure",
                why=f"ClickHouse rejected the previous DDL: {error[:200]}",
                confidence=0.6,
            )
            step.output(repaired.as_dict())
            self.steps.append(step.snapshot())
            self.decisions += [d.as_dict() for d in step.decisions]
            return repaired

    def run(self, spec: SpecInput, *, execute: bool = True) -> InstrumentationResult:
        """Spec in, tables created and loaded out.

        There is no overwrite path and nothing to decide: a table that already
        exists is widened with `ALTER TABLE ADD COLUMN` and keeps its data. An
        unattended run - the unseen spec - therefore never blocks on a prompt
        nobody is there to answer, and never destroys anything.
        """
        groups = self.groups_for(spec)
        summaries = self.profile(groups, spec)
        proposal = self.design(spec, groups, summaries)

        # Lint each table against its own action's profiles. A field name
        # reused across two actions with different characteristics would
        # otherwise be judged against whichever profile happened to win a
        # merge.
        per_table = {g.action: {p.name: p for p in profile_events(g.events)} for g in groups}
        merged = {p.name: p for g in groups for p in profile_events(g.events)}

        statements: list[str] = []
        self.repairs = 0
        self.lint_issues = 0
        for attempt in range(self.settings.ddl_repair_attempts + 1):
            try:
                issues = lint_proposal(proposal, list(merged.values()), per_table=per_table)
                self.lint_issues = len(issues)
                if issues:
                    raise SchemaLintError(
                        "schema quality checks failed:\n" + "\n".join(f"  - {i}" for i in issues)
                    )
                statements = self.validate(proposal)
                break
            except Exception as exc:
                if attempt >= self.settings.ddl_repair_attempts or not self.settings.llm_enabled:
                    raise
                log.warning(
                    "DDL rejected (repair %d/%d): %s",
                    attempt + 1,
                    self.settings.ddl_repair_attempts,
                    str(exc)[:200],
                )
                self.repairs += 1
                proposal = self.repair(spec, groups, summaries, proposal, str(exc))

        load_results: list[LoadResult] = []
        if execute:
            existing = set(self.existing_tables(proposal))
            self.preexisting_tables = existing
            self.execute(statements)
            if existing:
                self.reconcile(proposal, existing)

            # Automatic, not a separate step someone has to remember to
            # trigger - this is the only proof the schema accepts the data it
            # was designed from, not just DDL the server parsed.
            load_results = self.load_groups(groups, proposal)
            self._notify_context(proposal)

        return InstrumentationResult(
            spec_name=spec.name,
            proposal=proposal,
            statements=statements,
            executed=execute,
            decisions=self.decisions,
            load_results=load_results,
            executed_statements=self.executed_statements,
            empty_actions=[g.action for g in groups if not g.load_events],
            undeclared_actions=spec.undeclared_actions,
        )

    def _bootstrap_default_context(self, ctx: Any) -> None:
        """Seed the context layer from the bundled base_context.md, once.

        `refresh_after_schema_change()` only ever carries forward entries from
        the *previous* version - on a database with no context version yet,
        that previous version is empty, so the business layer (metrics, known
        issues, entity definitions) that Analytics is supposed to read first
        (ARCHITECTURE.md) would never exist unless something seeds it.
        Delegates to `ContextAgent.bootstrap_if_empty()` - the one place every
        agent that reads the context layer relies on for this, shared with
        `AnalyticsAgent.discover()` - which opens its own `context` step, so
        this method does not open a second one under `instrumentation`.
        """
        version = ctx.bootstrap_if_empty(run_analytics=False)
        if version is not None:
            self.bootstrapped_default_context = True

    def _notify_context(self, proposal: SchemaProposal) -> None:
        """Publish tables, columns, and MV rationale in one context version."""
        from .context import ContextAgent

        try:
            ctx = ContextAgent(self.settings, self.client)
            self._bootstrap_default_context(ctx)
            physical_views = [
                replace(view, target_table=self.dialect.physical_name(view.target_table))
                for view in proposal.materialized_views
            ]
            version, delta = ctx.refresh_after_schema_change(
                [table.name for table in proposal.tables], views=physical_views
            )
            # refresh_after_schema_change() chains straight into Analytics
            # (ContextAgent -> AnalyticsAgent) - surface both halves the same
            # way self.decisions/self.steps already are, so the UI can render
            # "context updated" and the resulting insights without re-querying.
            self.context_version = version
            self.context_delta = delta
            self.last_insight_report = ctx.last_insight_report
            self.last_analytics_run_id = ctx.last_analytics_run_id
            self.last_analytics_trace_id = ctx.last_analytics_trace_id
        except Exception:
            log.warning(
                "context notification failed — context will catch up on next refresh", exc_info=True
            )
