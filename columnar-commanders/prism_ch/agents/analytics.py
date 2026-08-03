"""Analytics Agent: context + data -> insights a PM would act on.

Follows the workflow the ClickHouse skill prescribes - discover, plan, execute,
recover - with two rules that shape everything else:

**Aggregate in ClickHouse, interpret in the LLM.** The model never sees raw
rows. It writes SQL, ClickHouse does the work, and the model interprets a small
result set. That is the brief's own hint, and it is enforced here rather than
hoped for: every query carries `agent-query-safety` settings, and a result that
comes back too wide is rejected as a query that failed to aggregate.

**A number without a `why` is not an insight.** `Insight.why` is required, the
same contract the tracing layer applies to decisions. Judges are scoring whether
a PM would act on the output; "mobile conversion is 12%" is a chart, "mobile
conversion is 12%, and the drop starts the day the OTP flow shipped" is a
finding.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import time
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..tracing import agent_step
from . import llm
from .context_store import ContextStore, context_dialect
from .rules import ANALYTICS_PREFIXES, load_rules, rules_for, skill_guidance
from .types import (
    AnalysisQuestion,
    ContextEntry,
    ContextSnapshot,
    InsightReport,
    QueryResult,
    parse_insights,
    parse_questions,
)

log = logging.getLogger(__name__)

_PROMPTS = pathlib.Path(__file__).parent / "prompts"
PLAN_PROMPT = "\n\n---\n\n".join(
    p
    for p in (
        (_PROMPTS / "analytics_plan.md").read_text(),
        skill_guidance(),
        load_rules(*rules_for(*ANALYTICS_PREFIXES)),
    )
    if p
)
INTERPRET_PROMPT = (_PROMPTS / "analytics_interpret.md").read_text()

# Per `agent-query-safety`. Applied to every generated query, and mirrored by a
# role-level settings profile in production - defence in depth, because the
# model will eventually forget to emit them.
QUERY_SETTINGS = {
    "max_execution_time": 30,
    "max_rows_to_read": 1_000_000_000,
    "max_bytes_to_read": 100_000_000_000,
    "max_result_rows": 10_000,
    "result_overflow_mode": "break",
    # Default 10 grants a grace period that silently defeats the wall clock.
    "timeout_before_checking_execution_speed": 0,
    # Server-enforced backstop for `_is_destructive()`: even if a DROP/DELETE/
    # ALTER/TRUNCATE somehow got past the client-side check, ClickHouse itself
    # refuses anything but SELECT/SHOW/DESCRIBE under readonly=1. The Analytics
    # Agent only ever reads - it must never touch schema or data.
    "readonly": 1,
}

# A result wider than this is raw data, not an aggregate - the model was
# supposed to push the computation down.
MAX_INTERPRETABLE_ROWS = 200

REQUIRED_CUTS = {"overall", "trend", "device", "geo", "funnel", "segment"}

_RAW_SELECT = re.compile(
    r"^\s*SELECT\s+\*\s+FROM\b", re.IGNORECASE | re.MULTILINE
)
_NO_GROUP_BY = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)
_AGGREGATE_FN = re.compile(
    r"\b(count|countIf|sum|sumIf|avg|avgIf|min|max|uniq|uniqExact|quantile|"
    r"quantiles|median|argMin|argMax|groupArray|groupUniqArray)\s*\(",
    re.IGNORECASE,
)


def _is_raw_select(sql: str) -> str | None:
    """Return a rejection reason if the SQL looks like it fetches raw rows."""
    if _RAW_SELECT.search(sql):
        return "SELECT * fetches raw rows - use aggregation functions"
    if not _NO_GROUP_BY.search(sql) and not _AGGREGATE_FN.search(sql):
        return "query has no GROUP BY and no aggregate functions - must aggregate in ClickHouse"
    return None


# Guard rail: the Analytics Agent only ever reads. A whitelist of the first
# keyword, not a blacklist of DROP/TRUNCATE/DELETE/ALTER/RENAME/UPDATE/INSERT/
# CREATE/... - enumerating every destructive statement ClickHouse's grammar
# allows is a losing game; requiring the query to open with SELECT or WITH
# (a CTE prefix) is not. Backed up by `readonly=1` in QUERY_SETTINGS, which
# enforces the same rule server-side in case this check is ever bypassed.
_SAFE_LEADING_KEYWORDS = {"SELECT", "WITH"}


def _is_destructive(sql: str) -> str | None:
    """Return a rejection reason if the statement isn't a read-only SELECT."""
    stripped = sql.strip()
    first = stripped.split(None, 1)[0].upper() if stripped else ""
    if first not in _SAFE_LEADING_KEYWORDS:
        return (
            f"query starts with {first or '(empty)'!r}, not SELECT/WITH - the "
            "Analytics Agent only ever reads; it must never create, alter, "
            "drop, or delete tables, columns, or rows"
        )
    return None


@dataclass
class AnalyticsAgent:
    settings: Settings
    client: Any

    def __post_init__(self) -> None:
        self.dialect = context_dialect(self.settings)
        self.store = ContextStore(self.client, self.dialect)
        self.decisions: list[dict[str, Any]] = []

    def _bootstrap_context_if_empty(self) -> None:
        """Seed context from base_context.md if nothing has been published yet.

        Best-effort: a seeding failure must not block analysis from running
        against whatever context (even none) is actually there.
        """
        from .context import ContextAgent

        try:
            ContextAgent(self.settings, self.client).bootstrap_if_empty()
        except Exception:
            log.warning(
                "context bootstrap skipped — analytics will run against current context",
                exc_info=True,
            )

    # --- 1. discover ----------------------------------------------------------

    def discover(self) -> tuple[ContextSnapshot, list[dict[str, Any]]]:
        """Load the newest context and the live schema.

        Reading `MAX(version)` here is what makes context freshness real: a
        table created a minute ago by the Instrumentation Agent is visible to
        this run without anyone refreshing anything.

        Analytics can be the first agent anyone runs against a brand-new
        database - without seeding first, `context_versions` may not even
        exist yet, and reading it would fail before a single query runs.
        """
        self._bootstrap_context_if_empty()
        snapshot = self.store.load()
        with agent_step(
            "analytics", "discover", context_version=str(snapshot.version)
        ) as step:
            sql = (
                "SELECT table, name, type FROM system.columns "
                f"WHERE database = '{self.settings.database}' ORDER BY table, position"
            )
            step.sql(sql, purpose="schema discovery before planning any query")
            result = self.client.query(sql)
            rows = getattr(result, "result_rows", None) or []

            schema: dict[str, list[dict[str, str]]] = {}
            for table, column, ctype in rows:
                schema.setdefault(str(table), []).append(
                    {"name": str(column), "type": str(ctype)}
                )

            tables = [{"table": t, "columns": c} for t, c in schema.items()]

            # Also grab row counts so the planner knows which tables have data.
            try:
                count_sql = (
                    "SELECT name, total_rows FROM system.tables "
                    f"WHERE database = '{self.settings.database}'"
                )
                count_result = self.client.query(count_sql)
                count_rows = getattr(count_result, "result_rows", None) or []
                row_counts = {str(r[0]): r[1] for r in count_rows}
                for t in tables:
                    t["row_count"] = row_counts.get(t["table"], 0)
            except Exception:  # noqa: BLE001
                pass

            step.decision(
                what=f"discovered {len(tables)} tables at context v{snapshot.version}",
                why=(
                    "schema is read from the database and context from MAX(version), so "
                    "a table created moments ago is already in scope"
                ),
                rules=["agent-discovery-schema"],
                evidence={"tables": sorted(schema), "context_version": snapshot.version},
            )
            step.metrics_from(
                tables_discovered=len(tables),
                columns_discovered=sum(len(t["columns"]) for t in tables),
                context_version=snapshot.version,
                context_entries=len(snapshot.entries),
                context_issues=len(snapshot.issues),
            )
            step.output({"tables": len(tables), "context_version": snapshot.version})
            self.decisions += [d.as_dict() for d in step.decisions]
            return snapshot, tables

    # --- 2. plan --------------------------------------------------------------

    def plan(
        self, snapshot: ContextSnapshot, tables: list[dict[str, Any]], focus: str | None
    ) -> list[AnalysisQuestion]:
        with agent_step(
            "analytics", "plan_queries", context_version=str(snapshot.version)
        ) as step:
            if not self.settings.llm_enabled:
                log.warning("LLM disabled - no query plan can be generated")
                step.decision(
                    what="no queries planned",
                    why=(
                        "no LLM configured; planning is the one step with no "
                        "deterministic fallback"
                    ),
                    confidence=0.0,
                )
                return []

            payload = llm.complete(
                self.settings,
                name="plan_queries",
                system=PLAN_PROMPT,
                prompt=self._plan_prompt(snapshot, tables, focus),
                as_json=True,
            )
            questions = parse_questions(payload)  # type: ignore[arg-type]

            # Validate: reject anything destructive first, then anything that
            # looks like it fetches raw rows instead of aggregating.
            valid: list[AnalysisQuestion] = []
            for q in questions:
                reason = _is_destructive(q.sql) or _is_raw_select(q.sql)
                if reason:
                    log.warning("rejected query %r: %s", q.question[:60], reason)
                    step.decision(
                        what=f"rejected query: {q.question[:80]}",
                        why=reason,
                        confidence=1.0,
                    )
                else:
                    valid.append(q)
            questions = valid

            by_cut: dict[str, int] = {}
            for q in questions:
                by_cut[q.cut] = by_cut.get(q.cut, 0) + 1

            missing_cuts = REQUIRED_CUTS - set(by_cut.keys())
            if missing_cuts:
                log.warning("plan missing cuts: %s", ", ".join(sorted(missing_cuts)))

            step.decision(
                what=f"planned {len(questions)} queries across {len(by_cut)} cuts",
                why=(
                    "the brief names device, geo, funnel stage and user segment; a "
                    "single-dimension read misses the iOS-in-one-region class of finding"
                ),
                evidence={"cuts": by_cut, "missing_cuts": sorted(missing_cuts)},
                rules=["agent-discovery-schema"],
            )
            step.metrics_from(
                questions_planned=len(questions),
                cuts_covered=len(by_cut),
                cuts_missing=len(missing_cuts),
                raw_queries_rejected=(
                    len(valid) - len(questions) if len(valid) != len(questions) else 0
                ),
            )
            step.output({"questions": [q.question for q in questions]})
            self.decisions += [d.as_dict() for d in step.decisions]
            return questions

    def _plan_prompt(
        self, snapshot: ContextSnapshot, tables: list[dict[str, Any]], focus: str | None
    ) -> str:
        relevant = self._relevant_context(
            snapshot,
            focus,
            kinds=("definition", "metric", "entity", "relationship", "known_issue"),
        )
        context = [{"kind": e.kind, "key": e.key, "value": e.value[:500]} for e in relevant]
        rollups = snapshot.of_kind("rollup")
        issues = [i.as_dict() for i in snapshot.issues]

        parts = [
            f"# Database: {self.settings.database} (context v{snapshot.version})",
            f"# Business context\n\n```json\n{json.dumps(context, indent=2)[:12000]}\n```",
        ]
        if rollups:
            parts.append(
                "# Pre-aggregated rollups — check these BEFORE any raw-table query\n\n"
                + "\n".join(
                    f"- `{e.key}` — {e.value}\n  select: `{e.detail[:200]}`" for e in rollups
                )
                + "\n\nEvery table listed above has a rollup here. You MUST check "
                "whether one covers a question's dimensions before writing a query "
                "against the raw table it summarizes - query the target with its "
                "aggregate `-Merge` function instead of rescanning raw events. Only "
                "write a raw-table query when no rollup's GROUP BY covers what the "
                "question needs, and say why in that question's `why`."
            )
        parts.append(f"# Schema\n\n```json\n{json.dumps(tables, indent=2)[:14000]}\n```")
        if issues:
            parts.append(
                "# Known problems with the context layer\n\n"
                f"```json\n{json.dumps(issues, indent=2)[:3000]}\n```\n"
                "Where a metric is ambiguous, compute it both ways and say so."
            )
        if focus:
            parts.append(f"# Focus\n\n{focus}")
        parts.append(
            "Plan the queries. You MUST cover all cuts: overall, trend, device, "
            "geo, funnel, segment, and at least one anomaly query. "
            "Every query MUST use GROUP BY or aggregate functions. "
            "Never use SELECT *. Return only the JSON object."
        )
        return "\n\n".join(parts)

    def _relevant_context(
        self,
        snapshot: ContextSnapshot,
        focus: str | None,
        *,
        kinds: tuple[str, ...],
        limit: int = 15,
    ) -> list[ContextEntry]:
        """Use semantic retrieval for focused analysis; safely retain full context."""
        full = [entry for entry in snapshot.entries if entry.kind in kinds]
        if not focus or not self.store.has_embeddings(snapshot.version):
            return full
        try:
            query_vector = llm.embed(self.settings, [focus])[0]
            hits = self.store.semantic_search(
                query_vector, version=snapshot.version, limit=limit
            )
            index = snapshot.index()
            matched = [
                index[(hit["kind"], hit["key"])]
                for hit in hits
                if hit["kind"] in kinds and (hit["kind"], hit["key"]) in index
            ]
            return matched or full
        except Exception:  # noqa: BLE001
            log.warning(
                "semantic context search failed — using the full context set",
                exc_info=True,
            )
            return full

    # --- 3. execute -----------------------------------------------------------

    def execute(
        self, questions: list[AnalysisQuestion], context_version: int
    ) -> list[QueryResult]:
        results: list[QueryResult] = []

        with agent_step(
            "analytics", "run_queries", context_version=str(context_version)
        ) as step:
            for question in questions:
                # Pre-flight: reject anything destructive or raw-row-fetching
                # before it hits the DB - `plan()` already filters these, but
                # `execute()` must not trust a caller who skipped planning.
                reason = _is_destructive(question.sql) or _is_raw_select(question.sql)
                if reason:
                    results.append(QueryResult(question=question, error=reason))
                    continue

                # Emitted before the query runs, not after - this is what lets
                # the live UI show "the query being executed" while it is
                # actually in flight rather than only once it has returned.
                step.sql(question.sql, purpose=question.question)

                started = time.monotonic()
                try:
                    result = self.client.query(question.sql, settings=QUERY_SETTINGS)
                    columns = list(getattr(result, "column_names", None) or [])
                    rows = [list(r) for r in (getattr(result, "result_rows", None) or [])]

                    if len(rows) > MAX_INTERPRETABLE_ROWS:
                        qr = QueryResult(
                            question=question,
                            columns=columns,
                            rows=rows[:MAX_INTERPRETABLE_ROWS],
                            error=(
                                f"returned {len(rows)} rows; aggregate further - the "
                                "model interprets results, it does not scan them"
                            ),
                        )
                    else:
                        qr = QueryResult(question=question, columns=columns, rows=rows)
                except Exception as exc:  # noqa: BLE001 - reported, not fatal
                    qr = QueryResult(question=question, error=str(exc)[:400])

                qr.elapsed_ms = int((time.monotonic() - started) * 1000)
                step.sql(question.sql, purpose=question.question, rows=len(qr.rows))
                results.append(qr)

            failed = [r for r in results if not r.ok]
            step.decision(
                what=f"ran {len(results)} queries, {len(failed)} failed",
                why=(
                    "every query carries LIMIT-equivalent settings and a wall-clock cap, "
                    "so a bad generated query is bounded rather than cluster-wide"
                ),
                rules=["agent-query-safety"],
                evidence={
                    "settings": QUERY_SETTINGS,
                    "failures": [r.error[:160] for r in failed],
                },
            )
            step.metrics_from(
                queries_run=len(results),
                queries_failed=len(failed),
                queries_succeeded=len(results) - len(failed),
                rows_returned=sum(len(r.rows) for r in results),
                query_ms_total=sum(r.elapsed_ms for r in results),
                query_ms_slowest=max((r.elapsed_ms for r in results), default=0),
            )
            step.output({"queries": len(results), "failed": len(failed)})
            self.decisions += [d.as_dict() for d in step.decisions]
            return results

    # --- 4. interpret ---------------------------------------------------------

    def interpret(
        self, snapshot: ContextSnapshot, results: list[QueryResult], focus: str | None
    ) -> InsightReport:
        usable = [r for r in results if r.ok and r.rows]

        with agent_step(
            "analytics", "interpret", context_version=str(snapshot.version)
        ) as step:
            if not usable or not self.settings.llm_enabled:
                step.decision(
                    what="no insights produced",
                    why=(
                        "no query returned usable aggregates"
                        if not usable
                        else "no LLM configured"
                    ),
                    confidence=0.0,
                )
                return InsightReport(
                    context_version=snapshot.version, queries_run=len(results), queries=results
                )

            payload = llm.complete(
                self.settings,
                name="interpret_results",
                system=INTERPRET_PROMPT,
                prompt=self._interpret_prompt(snapshot, usable, focus),
                as_json=True,
            )
            insights = parse_insights(payload)  # type: ignore[arg-type]

            for insight in insights:
                step.decision(
                    what=insight.headline,
                    why=insight.why,
                    confidence=insight.confidence,
                    evidence=insight.evidence,
                )
                step.score(
                    "insight_confidence", insight.confidence, comment=insight.headline[:120]
                )

            report = InsightReport(
                context_version=snapshot.version,
                insights=insights,
                summary=str(payload.get("summary", "")),  # type: ignore[union-attr]
                queries_run=len(results),
                queries=results,
            )
            confidences = [i.confidence for i in insights]
            cuts_in_insights = {i.cut for i in insights}

            step.metrics_from(
                insights=len(insights),
                confidence_avg=round(sum(confidences) / len(confidences), 3) if confidences else 0,
                confidence_min=min(confidences) if confidences else 0,
                insights_with_context_ref=sum(1 for i in insights if i.context_refs),
                insights_with_recommendation=sum(1 for i in insights if i.recommendation),
                cuts_reported=len(cuts_in_insights),
            )
            step.output(report.as_dict())
            self.decisions += [d.as_dict() for d in step.decisions]
            return report

    def _interpret_prompt(
        self, snapshot: ContextSnapshot, results: list[QueryResult], focus: str | None
    ) -> str:
        relevant = self._relevant_context(
            snapshot, focus, kinds=("definition", "metric", "known_issue")
        )
        known_issues = [
            {"key": e.key, "value": e.value[:400]}
            for e in relevant
            if e.kind == "known_issue"
        ]
        metrics = [
            {"key": e.key, "value": e.value[:300]}
            for e in relevant
            if e.kind == "metric"
        ]
        definitions = [
            {"key": e.key, "value": e.value[:300]}
            for e in relevant
            if e.kind == "definition"
        ]

        parts = [
            f"# Business context first (context v{snapshot.version})\n\n"
            "Read this before the query results; it defines what matters and "
            "which anomalies are already explained."
        ]
        if metrics:
            parts.append(f"# Metric definitions\n\n```json\n{json.dumps(metrics, indent=2)}\n```")
        if definitions:
            definitions_json = json.dumps(definitions, indent=2)[:4000]
            parts.append(f"# Business definitions\n\n```json\n{definitions_json}\n```")
        if known_issues:
            parts.append(
                "# Known issues log\n\n"
                f"```json\n{json.dumps(known_issues, indent=2)}\n```\n"
                "Check every anomaly against this before inventing an explanation."
            )
        if snapshot.issues:
            parts.append(
                "# Context problems found\n\n"
                f"```json\n{json.dumps([i.as_dict() for i in snapshot.issues], indent=2)}\n```"
            )
        results_json = json.dumps([r.as_dict() for r in results], indent=2, default=str)
        parts.append(f"# Query results\n\n```json\n{results_json[:20000]}\n```")
        if focus:
            parts.append(f"# Focus\n\n{focus}")

        # Summarize which cuts succeeded and which failed, so the interpreter
        # knows what data is available.
        parts.append(
            f"# Coverage\n\n"
            f"Successful queries: {len(results)}\n"
            f"Cuts covered: {', '.join(sorted({r.question.cut for r in results}))}\n"
            f"Total rows across all results: {sum(len(r.rows) for r in results)}"
        )

        parts.append(
            "Write the insights. Cover headline metrics, trends, segment gaps, "
            "funnel bottlenecks, and anomalies. Every insight must have a `why`. "
            "Return only the JSON object."
        )
        return "\n\n".join(parts)

    # --- orchestration --------------------------------------------------------

    def run(self, focus: str | None = None) -> InsightReport:
        snapshot, tables = self.discover()
        questions = self.plan(snapshot, tables, focus)
        if not questions:
            return InsightReport(context_version=snapshot.version, queries_run=0)
        results = self.execute(questions, snapshot.version)
        return self.interpret(snapshot, results, focus)
