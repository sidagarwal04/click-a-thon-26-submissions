from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from threading import Lock
from uuid import UUID

from pydantic import JsonValue

from app.agents.fireworks import FireworksAgentClient, FireworksAgentError
from app.core.config import Settings, settings
from app.repositories.clickhouse import ClickHouseColumn, ClickHouseRepository
from app.schemas.asklys import (
    AsklysContextItem,
    AsklysContextRef,
    AsklysContextResponse,
    AsklysFunnelStep,
    AsklysIntent,
    AsklysNarrative,
    AsklysPathLink,
    AsklysPlan,
    AsklysQueryRequest,
    AsklysQueryResponse,
    AsklysReview,
    AsklysTrendPoint,
    AsklysTrendSeries,
    AsklysVisualization,
)
from app.tools.sql_validator import UnsafeAnalysisQueryError, validate_analysis_sql
from app.tracing import Tracer, create_tracer

MAX_SCHEMA_TABLES = 80
MAX_SCHEMA_COLUMNS_PER_TABLE = 60
MAX_RESULT_ROWS = 200
_SAMPLE_COLUMN_NAMES = {"event", "event_name", "status", "type"}
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AsklysProgress = Callable[[dict[str, JsonValue]], None]


class AsklysError(RuntimeError):
    """Base error for Asklys request failures."""


class AsklysNotConfiguredError(AsklysError):
    """Raised when the LLM or ClickHouse connection is unavailable."""


class AsklysQueryError(AsklysError):
    """Raised when a generated query cannot be validated or executed."""


@dataclass(frozen=True, slots=True)
class _AsklysTableSchema:
    columns: list[ClickHouseColumn]
    engine: str | None = None
    sorting_key: str | None = None


class AsklysIntentRouter:
    """Small deterministic router that keeps the rendering contract predictable."""

    _ROUTES: tuple[tuple[AsklysIntent, tuple[str, ...]], ...] = (
        (
            "funnel",
            ("funnel", "conversion", "dropoff", "drop-off", "step conversion"),
        ),
        (
            "user_path",
            ("user path", "journey", "flow", "before", "after", "sequence"),
        ),
        (
            "trend",
            ("trend", "over time", "daily", "weekly", "monthly", "growth"),
        ),
    )

    def route(self, question: str) -> AsklysIntent:
        folded = question.casefold()
        for intent, phrases in self._ROUTES:
            if any(phrase in folded for phrase in phrases):
                return intent
        return "text"


class AsklysService:
    def __init__(
        self,
        *,
        config: Settings,
        clickhouse: ClickHouseRepository,
        agent: FireworksAgentClient,
        router: AsklysIntentRouter | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self._config = config
        self._clickhouse = clickhouse
        self._agent = agent
        self._router = router or AsklysIntentRouter()
        self._tracer = tracer or create_tracer()
        self._clickhouse_lock = Lock()

    def context(self, query: str = "", limit: int = 30) -> AsklysContextResponse:
        schema = self._schema()
        needle = query.strip().casefold().lstrip("@")
        items: list[AsklysContextItem] = []
        for table, table_schema in schema.items():
            columns = table_schema.columns
            if not needle or needle in table.casefold():
                items.append(
                    AsklysContextItem(
                        kind="table",
                        label=f"@{table}",
                        table=table,
                        description=(
                            f"{_table_type(table_schema)} · {len(columns)} columns"
                        ),
                    )
                )
            for column in columns:
                qualified = f"{table}.{column.name}"
                if needle and needle not in qualified.casefold():
                    continue
                items.append(
                    AsklysContextItem(
                        kind="column",
                        label=f"@{qualified}",
                        table=table,
                        column=column.name,
                        data_type=column.data_type,
                        description=f"Column · {column.data_type}",
                    )
                )
        return AsklysContextResponse(
            database=self._config.CLICKHOUSE_DATABASE,
            items=items[:limit],
        )

    def ask(
        self,
        request: AsklysQueryRequest,
        *,
        progress: AsklysProgress | None = None,
    ) -> AsklysQueryResponse:
        trace_input = {
            "question": request.question,
            "attached_context": [_context_label(item) for item in request.context],
            "conversation_turns": len(request.conversation),
            "database": self._config.CLICKHOUSE_DATABASE,
        }
        try:
            with self._tracer.span(
                "asklys_query",
                input=trace_input,
                as_type="agent",
            ) as root_span:
                try:
                    response = self._answer(
                        request,
                        progress=progress,
                        trace_id=root_span.trace_id,
                    )
                except Exception as exc:
                    root_span.update(
                        level="ERROR",
                        status=str(exc)[:1200],
                    )
                    raise
                root_span.update(
                    output={
                        "intent": response.intent,
                        "title": response.title,
                        "answer": response.answer,
                        "sql": response.sql,
                        "columns": response.columns,
                        "row_count": len(response.rows),
                        "query_attempts": response.query_attempts,
                    },
                    metadata={
                        "model": response.model,
                        "database": response.database,
                    },
                )
                return response
        finally:
            # Trace delivery must never turn a successful analytics response into
            # an API failure.
            try:
                self._tracer.flush()
            except Exception:
                pass

    def _answer(
        self,
        request: AsklysQueryRequest,
        *,
        progress: AsklysProgress | None,
        trace_id: str | None,
    ) -> AsklysQueryResponse:
        self._emit(progress, "schema", "Inspecting the connected ClickHouse schema")
        with self._tracer.span(
            "asklys_schema_context",
            input={
                "database": self._config.CLICKHOUSE_DATABASE,
                "attached_context": [
                    _context_label(item) for item in request.context
                ],
            },
            as_type="retriever",
        ) as schema_span:
            schema = self._schema()
            route_hint = self._router.route(request.question)
            selected_schema = self._select_schema(schema, request.context)
            schema_span.update(
                output={
                    "available_tables": len(schema),
                    "selected_tables": sorted(selected_schema),
                    "route_hint": route_hint,
                }
            )
        self._emit(
            progress,
            "planning",
            "Understanding the question and choosing an analysis",
        )
        planner_input = {
            "question": request.question,
            "intent_route_hint": route_hint,
            "database": self._config.CLICKHOUSE_DATABASE,
            "schema": selected_schema,
            "attached_context": [item.model_dump() for item in request.context],
            "conversation": [item.model_dump() for item in request.conversation],
        }
        with self._tracer.span(
            "asklys_query_plan",
            input=planner_input,
            as_type="generation",
        ) as plan_span:
            try:
                plan = self._agent.complete(
                    AsklysPlan,
                    name="asklys_query_plan",
                    system_prompt=self._planner_prompt(),
                    input_payload=planner_input,
                    max_tokens=4200,
                )
            except FireworksAgentError as exc:
                raise AsklysQueryError(
                    f"Asklys could not plan this query: {exc}"
                ) from exc
            plan_span.update(
                output={
                    "intent": plan.intent,
                    "title": plan.title,
                    "sql": plan.sql,
                    "metric_definition": plan.metric_definition,
                    "assumptions": plan.assumptions,
                },
                metadata={"model": self._config.ASKLYS_MODEL},
            )
        route = plan.intent
        self._emit(
            progress,
            "intent",
            f"Building a {route.replace('_', ' ')} analysis",
            detail=plan.metric_definition,
        )
        if route != "text" and not plan.sql:
            raise AsklysQueryError(f"The {route} route requires an analytics query")

        columns: list[str] = []
        rows: list[dict[str, JsonValue]] = []
        safe_sql: str | None = None
        query_attempts = 0
        analysis_steps = [
            f"Understood this as a {route.replace('_', ' ')} analysis.",
            plan.metric_definition,
        ]
        if plan.sql:
            candidate_sql = plan.sql
            accepted = False
            last_error: str | None = None
            for attempt in range(1, self._config.ASKLYS_MAX_QUERY_ATTEMPTS + 1):
                query_attempts = attempt
                cleaned_candidate = _clean_planned_sql(candidate_sql)
                self._emit(
                    progress,
                    "query",
                    f"Running ClickHouse query attempt {attempt}",
                    sql=cleaned_candidate,
                )
                with self._tracer.span(
                    "asklys_execute_clickhouse_sql",
                    input={"attempt": attempt, "sql": cleaned_candidate},
                    as_type="tool",
                ) as query_span:
                    safe_sql, columns, rows, last_error = self._execute_candidate(
                        candidate_sql, schema
                    )
                    query_span.update(
                        output={
                            "columns": columns,
                            "row_count": len(rows),
                            "error": last_error,
                        },
                        level="ERROR" if last_error else "DEFAULT",
                        status=last_error,
                    )
                self._emit(
                    progress,
                    "review",
                    (
                        f"Reviewing {len(rows)} result rows"
                        if last_error is None
                        else "Reviewing the ClickHouse error"
                    ),
                    detail=last_error,
                )
                with self._tracer.span(
                    "asklys_query_review",
                    input={
                        "attempt": attempt,
                        "sql": safe_sql or cleaned_candidate,
                        "columns": columns,
                        "row_count": len(rows),
                        "error": last_error,
                    },
                    as_type="generation",
                ) as review_span:
                    review = self._review_candidate(
                        request=request,
                        plan=plan,
                        schema=selected_schema,
                        sql=safe_sql or cleaned_candidate,
                        columns=columns,
                        rows=rows,
                        error=last_error,
                    )
                    review_span.update(
                        output={
                            "decision": review.decision,
                            "reason": review.reason,
                            "revised_sql": review.revised_sql,
                        },
                        metadata={"model": self._config.ASKLYS_MODEL},
                    )
                if review.decision == "accept" and last_error is None:
                    self._emit(
                        progress,
                        "accepted",
                        f"Validated the result after {attempt} query attempt"
                        f"{'s' if attempt != 1 else ''}",
                        detail=review.reason,
                    )
                    analysis_steps.append(
                        f"Validated the result after {attempt} query attempt"
                        f"{'s' if attempt != 1 else ''}."
                    )
                    accepted = True
                    break
                analysis_steps.append(
                    f"Query attempt {attempt} needed repair: {review.reason}"
                )
                self._emit(
                    progress,
                    "repair",
                    f"Repairing query attempt {attempt}",
                    detail=review.reason,
                    sql=review.revised_sql,
                )
                if not review.revised_sql:
                    # Re-running identical SQL cannot produce a different result,
                    # so stop instead of spending the remaining attempts.
                    break
                candidate_sql = review.revised_sql
            if not accepted:
                detail = last_error or "the result critic did not accept the query"
                raise AsklysQueryError(
                    f"Asklys could not produce a trustworthy result after "
                    f"{query_attempts} attempts: {detail}"
                )

        visualization = _visualization(route, rows, sql=safe_sql)
        self._emit(progress, "summary", "Writing the answer and visualization")
        if not plan.sql and plan.direct_answer:
            narrative = plan.direct_answer
        else:
            with self._tracer.span(
                "asklys_result_narrative",
                input={
                    "question": request.question,
                    "intent": route,
                    "columns": columns,
                    "row_count": len(rows),
                },
                as_type="generation",
            ) as narrative_span:
                narrative = self._narrative(
                    request.question, plan, columns, rows, route
                )
                narrative_span.update(
                    output={"answer": narrative},
                    metadata={"model": self._config.ASKLYS_MODEL},
                )
        return AsklysQueryResponse(
            intent=route,
            title=plan.title,
            answer=narrative,
            visualization=visualization,
            sql=safe_sql,
            columns=columns,
            rows=rows[:50],
            database=self._config.CLICKHOUSE_DATABASE,
            context_used=[_context_label(item) for item in request.context],
            analysis_steps=analysis_steps,
            query_attempts=query_attempts,
            model=self._config.ASKLYS_MODEL,
            langfuse_trace_id=trace_id,
        )

    @staticmethod
    def _emit(
        progress: AsklysProgress | None,
        stage: str,
        message: str,
        *,
        detail: str | None = None,
        sql: str | None = None,
    ) -> None:
        if progress is None:
            return
        event: dict[str, JsonValue] = {
            "type": "status",
            "stage": stage,
            "message": message,
        }
        if detail:
            event["detail"] = detail
        if sql:
            event["sql"] = sql
        progress(event)

    def _execute_candidate(
        self,
        candidate_sql: str,
        schema: Mapping[str, _AsklysTableSchema],
    ) -> tuple[
        str | None,
        list[str],
        list[dict[str, JsonValue]],
        str | None,
    ]:
        safe_sql: str | None = None
        try:
            safe_sql = validate_analysis_sql(
                _clean_planned_sql(candidate_sql),
                allowed_tables=list(schema),
                table_columns={
                    table: [column.name for column in table_schema.columns]
                    for table, table_schema in schema.items()
                },
            )
            with self._clickhouse_lock:
                result = self._clickhouse.query(
                    safe_sql,
                    query_settings={
                        "readonly": 2,
                        "max_result_rows": MAX_RESULT_ROWS,
                        "result_overflow_mode": "break",
                        "max_execution_time": 25,
                    },
                )
            columns = [str(name) for name in result.column_names]
            rows = [
                {
                    column: _json_value(value)
                    for column, value in zip(columns, result_row, strict=True)
                }
                for result_row in result.result_rows
            ]
            return safe_sql, columns, rows, None
        except (UnsafeAnalysisQueryError, ValueError, TypeError) as exc:
            return safe_sql, [], [], str(exc)[:1200]
        except Exception as exc:
            return (
                safe_sql,
                [],
                [],
                f"ClickHouse execution failed: {exc}"[:1200],
            )

    def _review_candidate(
        self,
        *,
        request: AsklysQueryRequest,
        plan: AsklysPlan,
        schema: Mapping[str, object],
        sql: str,
        columns: Sequence[str],
        rows: Sequence[Mapping[str, JsonValue]],
        error: str | None,
    ) -> AsklysReview:
        try:
            return self._agent.complete(
                AsklysReview,
                name="asklys_query_review",
                system_prompt=self._review_prompt(plan.intent),
                input_payload={
                    "question": request.question,
                    "intent": plan.intent,
                    "metric_definition": plan.metric_definition,
                    "schema": schema,
                    "sql": sql,
                    "error": error,
                    "columns": list(columns),
                    "rows": list(rows)[:50],
                },
                max_tokens=3000,
            )
        except FireworksAgentError as exc:
            if error is None and rows:
                return AsklysReview(
                    decision="accept",
                    reason="The query executed and returned renderable data.",
                )
            raise AsklysQueryError(
                f"Asklys could not review the query result: {exc}"
            ) from exc

    def _schema(self) -> dict[str, _AsklysTableSchema]:
        try:
            with self._clickhouse_lock:
                table_engines = self._table_engines()
                tables = list(table_engines)[:MAX_SCHEMA_TABLES]
                database = self._config.CLICKHOUSE_DATABASE
                sort_keys = self._sort_keys()
                return {
                    table: _AsklysTableSchema(
                        columns=self._clickhouse.list_columns(table, database)[
                            :MAX_SCHEMA_COLUMNS_PER_TABLE
                        ],
                        engine=table_engines.get(table),
                        sorting_key=sort_keys.get(table),
                    )
                    for table in tables
                }
        except Exception as exc:
            raise AsklysQueryError(
                f"Asklys could not inspect the connected ClickHouse schema: {exc}"
            ) from exc

    def _sort_keys(self) -> dict[str, str]:
        """Sorting keys tell the planner which columns filter cheaply."""

        try:
            rows = self._clickhouse.query_rows(
                """
                SELECT name, sorting_key
                FROM system.tables
                WHERE database = {database:String} AND sorting_key != ''
                """,
                parameters={"database": self._config.CLICKHOUSE_DATABASE},
            )
        except Exception:
            return {}
        return {str(row[0]): str(row[1]) for row in rows}

    def _table_engines(self) -> dict[str, str | None]:
        try:
            return {
                table.name: table.engine
                for table in self._clickhouse.list_table_metadata(
                    self._config.CLICKHOUSE_DATABASE
                )
            }
        except AttributeError:
            return dict.fromkeys(
                self._clickhouse.list_tables(self._config.CLICKHOUSE_DATABASE)
            )

    def _select_schema(
        self,
        schema: Mapping[str, _AsklysTableSchema],
        context: Sequence[AsklysContextRef],
    ) -> dict[str, dict[str, object]]:
        attached_tables = {item.table for item in context if item.table in schema}
        tables = attached_tables or set(schema)
        selected: dict[str, dict[str, object]] = {}
        for table in sorted(tables):
            described: list[dict[str, str]] = []
            table_schema = schema[table]
            for column in table_schema.columns:
                detail = {"name": column.name, "type": column.data_type}
                if _is_dimension_column(column):
                    samples = self._dimension_samples(table, column.name)
                    if samples:
                        detail["sample_values"] = " | ".join(samples)
                described.append(detail)
            selected[table] = {
                "engine": table_schema.engine,
                "table_type": _table_type(table_schema),
                "read_hints": _read_hints(table_schema),
                "sorting_key": table_schema.sorting_key,
                "columns": described,
            }
        return selected

    def _dimension_samples(self, table: str, column: str) -> list[str]:
        if not _SAFE_IDENTIFIER.fullmatch(table) or not _SAFE_IDENTIFIER.fullmatch(
            column
        ):
            return []
        try:
            with self._clickhouse_lock:
                rows = self._clickhouse.query_rows(
                    f"SELECT DISTINCT `{column}` FROM `{table}` "
                    f"WHERE `{column}` IS NOT NULL LIMIT 20",
                    query_settings={"readonly": 2, "max_execution_time": 5},
                )
        except Exception:
            return []
        return [str(row[0])[:100] for row in rows if row]

    @staticmethod
    def _planner_prompt() -> str:
        return """
You are Asklys, a high-reasoning ClickHouse product analytics agent. Work from
evidence, not guesses. First understand the user's actual analytical question,
then choose exactly one rendering intent: funnel, trend, user_path, or text. The
provided keyword route is only a weak hint and must not override the meaning of
the full question or conversation.

Before writing SQL, identify the event grain, actor/entity key, timestamp, time
range, filters, aggregation, and the attached context. Use only the supplied live
schema, table engine metadata, read hints, and sample values. State the metric
definition and any unavoidable assumptions concisely.

Rendering contracts:
- funnel: SQL returns exactly step and value in journey order. This must be an
  ordered actor funnel: an actor reaches step N only after reaching every prior
  step in order inside a conversion window. Default to a 14-day window when the
  user gives none. Prefer ClickHouse windowFunnel over independent event counts.
  Independent uniq/countIf totals by event are not a funnel. Values must be
  monotonically non-increasing. When events live in separate tables, UNION them
  into an actor/timestamp/event stream before evaluating order.
- trend: SQL returns x, series, value ordered by x. Use 'All' as series for one
  line. Respect explicit granularity and time range; choose a sensible bounded
  range otherwise.
- user_path: SQL returns source, target, value. Transitions must come from actual
  adjacent events for each actor ordered by timestamp, not global co-occurrence.
- text: SQL is optional only for schema/help questions. Any claim about counts,
  rates, behavior, or performance requires SQL. Aggregate results and never
  return raw actor identifiers.

SQL rules: start with SELECT or WITH; read only; one statement; no comments; no
SELECT *; no raw payloads; no direct personal or identifier lists; use only the
supplied tables, columns, and observed values; return at most 200 rows. The SQL
must be executable ClickHouse SQL. Every table, column, and literal you reference
must appear verbatim in the supplied schema: never invent a column name, and never
invent a filter value for a column whose sample_values are listed. Column types are
given exactly as ClickHouse reports them; Nullable(...) and LowCardinality(...) are
wrappers around the underlying type, so compare against the inner type and guard
Nullable columns with IS NOT NULL rather than casting. When a table lists a
sorting_key, prefer filtering on its leading columns. AggregateFunction columns
store aggregate
states; read them with the matching Merge aggregate, for example countMerge for
AggregateFunction(count) and uniqMerge for AggregateFunction(uniq, ...). When a
materialized view has a separate AggregatingMergeTree target table, prefer the
target table for analysis. Do not claim result values during planning.
""".strip()

    @staticmethod
    def _review_prompt(intent: AsklysIntent) -> str:
        contract = {
            "funnel": (
                "Reject independent per-event totals. Confirm the SQL applies ordered "
                "actor progression within a conversion window, rows are in requested "
                "step order, aliases are step/value, and values do not increase."
            ),
            "trend": (
                "Confirm x/series/value aliases, chronological ordering, numeric values, "
                "and that the metric and time grain answer the question."
            ),
            "user_path": (
                "Confirm source/target/value aliases and that links are adjacent events "
                "for the same actor in timestamp order."
            ),
            "text": (
                "Confirm the aggregate columns answer the question without exposing raw "
                "identifiers or unsupported claims."
            ),
        }[intent]
        return f"""
You are the result critic in an iterative ClickHouse analytics agent. Inspect the
question, metric definition, live schema, SQL, execution error, columns, and rows.
Accept only when the query is executable, semantically answers the question, and
the returned data satisfies the rendering contract. Empty results are acceptable
only when the SQL used real observed values and the result is plausibly empty.

{contract}

If anything is wrong, return retry with complete corrected ClickHouse SQL. Repair
syntax errors, invented values, wrong tables, missing ordering, incorrect grain,
or misleading metric definitions. The revision must remain read-only, bounded,
and use only supplied schema and sample values. Never weaken ordered funnel or
adjacent-path semantics merely to make a query return rows.
""".strip()

    def _narrative(
        self,
        question: str,
        plan: AsklysPlan,
        columns: Sequence[str],
        rows: Sequence[Mapping[str, JsonValue]],
        route: AsklysIntent,
    ) -> str:
        try:
            result = self._agent.complete(
                AsklysNarrative,
                name="asklys_result_narrative",
                system_prompt=(
                    "You are Asklys, a concise product analyst. Answer from the supplied "
                    "ClickHouse result only. State the key result in 1-3 sentences. Do not "
                    "invent causes, values, or significance. Mention empty results plainly."
                ),
                input_payload={
                    "question": question,
                    "intent": route,
                    "metric_reasoning": plan.reasoning,
                    "metric_definition": plan.metric_definition,
                    "assumptions": plan.assumptions,
                    "columns": list(columns),
                    "rows": list(rows)[:50],
                },
                max_tokens=500,
            )
            return result.answer
        except FireworksAgentError:
            if not rows:
                return "No matching data was returned for this question."
            return plan.reasoning


def _visualization(
    intent: AsklysIntent,
    rows: Sequence[Mapping[str, JsonValue]],
    *,
    sql: str | None = None,
) -> AsklysVisualization | None:
    if intent == "text":
        return None
    if intent == "funnel":
        values = [max(0.0, _number(row.get("value"))) for row in rows]
        ordered_names = _funnel_step_names(sql)
        basis = values[0] if values else 0.0
        steps = []
        for index, (row, value) in enumerate(zip(rows, values, strict=True)):
            previous = values[index - 1] if index else value
            steps.append(
                AsklysFunnelStep(
                    name=_funnel_step_name(row.get("step"), index, ordered_names),
                    value=value,
                    conversion_rate=value / basis if basis else 0.0,
                    previous_conversion_rate=value / previous if previous else 0.0,
                    dropoff=max(0.0, previous - value) if index else 0.0,
                    dropoff_rate=(
                        max(0.0, previous - value) / previous
                        if index and previous
                        else 0.0
                    ),
                )
            )
        return AsklysVisualization(kind=intent, funnel=steps)
    if intent == "trend":
        grouped: dict[str, list[AsklysTrendPoint]] = {}
        for row in rows:
            name = str(row.get("series", "All"))
            grouped.setdefault(name, []).append(
                AsklysTrendPoint(x=str(row.get("x", "")), y=_number(row.get("value")))
            )
        return AsklysVisualization(
            kind=intent,
            series=[
                AsklysTrendSeries(name=name, points=points)
                for name, points in grouped.items()
            ],
        )
    return AsklysVisualization(
        kind=intent,
        paths=[
            AsklysPathLink(
                source=str(row.get("source", "Unknown")),
                target=str(row.get("target", "Unknown")),
                value=max(0.0, _number(row.get("value"))),
            )
            for row in rows
        ],
    )


def _funnel_step_names(sql: str | None) -> list[str]:
    if not sql:
        return []
    names: list[str] = []
    for match in re.finditer(
        r"\b(?:event|event_name|status|type)\s*=\s*'((?:''|[^'])+)'",
        sql,
        re.IGNORECASE,
    ):
        name = match.group(1).replace("''", "'")
        if name not in names:
            names.append(name)
    return names


def _funnel_step_name(
    raw_step: JsonValue | None,
    index: int,
    ordered_names: Sequence[str],
) -> str:
    numeric_step = isinstance(raw_step, int | float) or (
        isinstance(raw_step, str) and raw_step.strip().isdigit()
    )
    if numeric_step and index < len(ordered_names):
        return ordered_names[index]
    return str(raw_step if raw_step is not None else f"Step {index + 1}")


def _number(value: JsonValue | None) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clean_planned_sql(sql: str) -> str:
    normalized = sql.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
    return normalized.removesuffix(";").strip()


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date | UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _is_dimension_column(column: ClickHouseColumn) -> bool:
    """Sample any string-like column an analyst would filter or group on.

    Observed values keep the planner from inventing literals, which is the most
    common reason a candidate query is rejected and retried.
    """

    if column.name.casefold() in _SAMPLE_COLUMN_NAMES:
        return True
    if column.name.casefold().endswith("_payload"):
        return False
    inner = column.data_type
    for wrapper in ("Nullable(", "LowCardinality("):
        while inner.startswith(wrapper):
            inner = inner[len(wrapper) : -1]
    if inner != "String":
        return False
    return "LowCardinality(" in column.data_type or column.name.casefold().endswith(
        ("_step", "_type", "_status", "_name", "_channel", "_kind")
    )


def _table_type(table_schema: _AsklysTableSchema) -> str:
    if table_schema.engine == "MaterializedView":
        return "Materialized view"
    if table_schema.engine == "AggregatingMergeTree" or any(
        column.data_type.startswith("AggregateFunction(")
        for column in table_schema.columns
    ):
        return "Aggregate-state table"
    return "Table"


def _read_hints(table_schema: _AsklysTableSchema) -> list[str]:
    hints: list[str] = []
    if table_schema.engine == "MaterializedView":
        hints.append("This relation is a ClickHouse materialized view.")
    aggregate_columns = [
        column
        for column in table_schema.columns
        if column.data_type.startswith("AggregateFunction(")
    ]
    if aggregate_columns:
        hints.append(
            "AggregateFunction columns store aggregate states and must be read "
            "with matching Merge aggregate functions."
        )
    for column in aggregate_columns:
        if column.data_type.startswith("AggregateFunction(count"):
            hints.append(f"Use countMerge({column.name}) for {column.name}.")
        elif column.data_type.startswith("AggregateFunction(uniq"):
            hints.append(f"Use uniqMerge({column.name}) for {column.name}.")
    return hints


def _context_label(item: AsklysContextRef) -> str:
    return f"{item.table}.{item.column}" if item.column else item.table


def build_asklys_service(
    config: Settings,
    *,
    clickhouse: ClickHouseRepository | None = None,
    agent: FireworksAgentClient | None = None,
    tracer: Tracer | None = None,
) -> AsklysService:
    if config.CLICKHOUSE_HOST is None and clickhouse is None:
        raise AsklysNotConfiguredError("ClickHouse is not configured")
    api_key = config.FIREWORKS_API_KEY
    if api_key is None and agent is None:
        raise AsklysNotConfiguredError("FIREWORKS_API_KEY is required for Asklys")
    if agent is None:
        assert api_key is not None
        agent = FireworksAgentClient(
            api_key=api_key.get_secret_value(),
            model=config.ASKLYS_MODEL,
            base_url=str(config.FIREWORKS_BASE_URL),
            timeout=config.FIREWORKS_TIMEOUT,
        )
    secret_key = (
        config.LANGFUSE_SECRET_KEY.get_secret_value()
        if config.LANGFUSE_SECRET_KEY is not None
        else None
    )
    asklys_tracer = tracer or create_tracer(
        enabled=config.LANGFUSE_TRACING_ENABLED,
        public_key=config.LANGFUSE_PUBLIC_KEY,
        secret_key=secret_key,
        base_url=(
            str(config.LANGFUSE_BASE_URL).rstrip("/")
            if config.LANGFUSE_BASE_URL is not None
            else None
        ),
    )
    return AsklysService(
        config=config,
        clickhouse=clickhouse or ClickHouseRepository(config),
        agent=agent,
        tracer=asklys_tracer,
    )


@lru_cache
def get_asklys_service() -> AsklysService:
    return build_asklys_service(settings)
