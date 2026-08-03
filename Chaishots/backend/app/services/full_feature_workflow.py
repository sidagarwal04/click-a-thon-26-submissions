from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import JsonValue

from app.agents.fireworks import FireworksAgentClient, FireworksAgentError
from app.repositories.clickhouse import ClickHouseRepository
from app.repositories.run_store import ClickHouseRunStore
from app.schemas.agents import (
    AnalysisPlan,
    AnalysisQuery,
    AnalyticsAgentOutput,
    ContextAgentOutput,
    ContextSelection,
    InstrumentationPlan,
    OrderByFieldReason,
)
from app.schemas.features import (
    ContextDiff,
    ContextDocument,
    EventProfile,
    InsightSummary,
    ProcessFeatureResult,
    SchemaArtifact,
)
from app.tools.baseline_analysis import build_baseline_analyses
from app.tools.context_store import (
    ContextValidationError,
    merge_context,
    valid_context_subset,
    validate_context_output,
)
from app.tools.generated_schema import (
    GeneratedSchemaError,
    build_ddl,
    ingest_events,
    schema_fingerprint,
    validate_instrumentation_plan,
)
from app.tools.materialized_view import (
    build_materialization_plan,
    build_materialized_analysis,
    compile_materialization,
)
from app.tools.sql_validator import (
    UnsafeAnalysisQueryError,
    build_deterministic_analysis_plan,
    validate_analysis_sql,
)
from app.tracing import Tracer

_INSTRUMENTATION_PROMPT = """You are the Instrumentation Agent for an analytics
pipeline. First read the product specification and the bounded event profile and
work out what the feature does in analytics terms: its primary entity, the join
keys it exposes, and the analyses and questions a PM would bring to it. Then
infer a general feature contract and ClickHouse schema from those same inputs in
one shot. Produce exactly one column for every observed top-level field. Profile
field names containing a dot are nested paths for context
only; never create separate columns for them because the top-level object is
stored as JSON. Use DateTime64(3) for the timestamp
field, String for strings/objects/arrays, Int64 for integers, Float64 for floats,
and UInt8 for booleans. A field must be nullable when presence is below 1 or null
was observed. The table name must be a safe
snake_case identifier ending in _events. ORDER BY must use 1-4 non-null columns.
Return schema_reasoning explaining the table grain, field/type/nullability design,
and how the schema supports the feature's analyses, grounded in the supplied
specification and event profile.
primary_entity and timestamp_field must exactly match observed field names. Do
not invent event columns. Decide the complete partition design. Return
partition_by as null when partitions are unnecessary, or as a partition expression
using an observed non-null field when data volume, retention operations, or
lifecycle management justify it. Supported expressions are a bare field or one
of toDate(field), toMonday(field), toStartOfMonth(field), toYYYYMM(field), and
toYYYY(field). Choose the field and granularity that fit the expected workload;
do not default to the timestamp or monthly partitions merely because they are
available. Partitioning is not an ORDER BY substitute. Explain the decision in
partition_by_reasoning by citing concrete evidence from the specification or
event profile, including expected scale, retention, and lifecycle requirements.
When those inputs provide no such evidence, say so and return null; never invent
an unstated retention policy or production volume. Existing context describes how
the warehouse already models related data - reuse its naming conventions and
join keys where they apply.

Design ORDER BY for the dominant queries implied by the specification, event
profile, relationships, metrics, and expected analyses. Prefer fields commonly
used in WHERE clauses. For entity timelines, put the primary entity before the
timestamp; for event/funnel filtering, put the event field early. Always include
the timestamp field. Use relationship keys when expected analyses join or
correlate by them. Do not prioritize a field merely because it is a reporting
dimension. Never put near-unique row identifiers such as id, event_id,
request_id, or trace_id in the first two positions. Keep the key as small as
possible, with at most four non-null columns. Return order_by_reasoning with one
entry per ORDER BY field, in the same order, stating its query role and why it
belongs in the physical key. Return one recommendation, not alternatives."""

_CONTEXT_READ_PROMPT = """You are the Context Agent in read-only mode. Given the
accumulated semantic context of the warehouse, the product specification for a new
feature, and a bounded profile of that feature's events, select only the entities,
relationships, metrics, known issues, and naming conventions that are relevant to
modelling and analysing this feature. Copy selected items verbatim from the supplied
context. Select a known issue whenever the feature touches the surface it describes
(a payment step, a device or OS, a destination region, a campaign window), because
the analytics stage uses these to explain anomalies. Do not invent entities,
relationships, metrics, or issues that are not present. Do not propose changes."""

_CONTEXT_WRITE_PROMPT = """You are the Context Agent in write mode. Given a
validated ClickHouse schema, ingestion results, analytical insights, and the
existing semantic context, record only knowledge that is new. Do not repeat items
already present in the existing context. Entities, relationships, and metrics must
name concrete tables and columns that appear in the supplied schemas.

For each new entity, record its row grain, business entity keys, time field,
event field, common filter columns, and common grouping columns when the supplied
specification and analyses support them. Keep common_filters separate from
common_groupings: a useful reporting dimension is not automatically a physical
sorting-key candidate.

The existing context includes a hand-maintained base layer that is known to be
imperfect and may lag the warehouse. Treat it as a claim to be checked, not as
ground truth. Report a conflict when new knowledge contradicts existing context,
when two existing definitions contradict each other (for example one metric
defined two different ways, or with two different denominators), when a definition
references a column or table that does not appear in the supplied schemas, or when
a documented metric is not computable from the available tables. State both sides
of each contradiction and name the items involved."""

_ANALYSIS_PLAN_PROMPT = """You are the Analytics Agent planning product analysis
in ClickHouse. Your queries are executed against the warehouse, so every one must
be valid ClickHouse SQL.

A fixed set of standard analyses (funnel, adoption, trend, segment completion,
and baseline comparison) already runs separately. Generate 3-5 additional bounded
aggregate SELECT queries that those standard analyses would miss: cross-table
joins to existing warehouse tables, correlations between feature usage and
outcomes, comparisons against the metric definitions in the supplied context, or
cuts the supplied context calls out as important.

Use only the supplied tables and columns; every identifier must appear in the
supplied schemas. Queries must start with SELECT and contain no comments,
semicolons, CTEs, DDL, or mutations. Always aggregate - never return raw rows -
and always include a count so the sample size behind each figure is visible. The
new event table stores nested objects as JSON strings, so use
JSONExtractFloat/JSONExtractString when needed.

If validation_feedback is supplied, a previous attempt was rejected: fix exactly
those queries and do not repeat any query_id in already_accepted_query_ids."""

_INSIGHT_PROMPT = """You are the Analytics Agent interpreting executed aggregate
query results for a product manager, not a database audience. Produce
evidence-backed product insights only from the supplied results.

Each insight must include observation, evidence, interpretation, context_used,
recommendation, confidence, and caveats. Write the interpretation as the *why*,
not a restatement of the number: connect the result to the supplied business
context. When a segment result lines up with a documented known issue, name that
issue by key and title in the interpretation and list it in context_used. When a
metric you report is defined in the supplied context, use that definition and its
name. Never assert a known issue caused a result; say the result is consistent
with it and what would confirm it.

Ground every number in evidence: quote the query_id and the figures you used, and
report the sample size behind a segment claim. Lower confidence and say why when a
segment is small, when a denominator is near zero, when the window is short, or
when a documented issue offers a competing explanation. Do not claim causality."""


class FullFeatureWorkflow:
    def __init__(
        self,
        *,
        database: str,
        clickhouse: ClickHouseRepository,
        run_store: ClickHouseRunStore,
        agents: FireworksAgentClient,
        tracer: Tracer,
    ) -> None:
        self._database = database
        self._clickhouse = clickhouse
        self._run_store = run_store
        self._agents = agents
        self._tracer = tracer

    def run(
        self,
        *,
        run_id: str,
        trace_id: str | None,
        feature: str,
        spec: str,
        profile: EventProfile,
        events_path: Path,
        available_tables: Sequence[str],
    ) -> ProcessFeatureResult:
        profile_payload = profile.model_dump(mode="json")
        existing_table_schemas = self._table_schemas(available_tables)
        # The hand-written base layer becomes version 1 on the very first run,
        # so every agent below reads one accumulated document.
        latest_context = self._run_store.ensure_base_context()
        context_read_input = {
            "specification": spec,
            "event_profile": profile_payload,
            "context": (
                latest_context.model_dump(mode="json") if latest_context else None
            ),
            "table_schemas": existing_table_schemas,
        }
        with self._tracer.span(
            "context_agent_read", input=context_read_input, as_type="agent"
        ) as read_span:
            context_selection = self._select_context(
                latest_context,
                spec=spec,
                profile=profile,
                table_schemas=existing_table_schemas,
            )
            read_span.update(
                output=context_selection.model_dump(mode="json"),
                metadata={
                    "context_version": (
                        latest_context.version if latest_context else None
                    )
                },
            )

        instrumentation_input: dict[str, object] = {
            "specification": spec,
            "event_profile": profile_payload,
            "schema_top_level_fields": [
                name for name in profile.fields if "." not in name
            ],
            "existing_context": context_selection.model_dump(mode="json"),
        }
        with self._tracer.span(
            "instrumentation_agent",
            input=instrumentation_input,
            as_type="agent",
        ) as instrumentation_span:
            instrumentation = self._run_store.get_schema_contract(feature)
            reused_contract = instrumentation is not None
            if instrumentation is not None:
                validate_instrumentation_plan(
                    instrumentation,
                    profile,
                    existing_tables=available_tables,
                    allow_existing_table=True,
                )
            else:
                validation_error: GeneratedSchemaError | None = None
                for attempt in range(1, 4):
                    if validation_error is not None:
                        instrumentation_input["validation_feedback"] = str(
                            validation_error
                        )
                    candidate = self._agents.complete(
                        InstrumentationPlan,
                        name="instrumentation_plan",
                        system_prompt=_INSTRUMENTATION_PROMPT,
                        input_payload=instrumentation_input,
                    )
                    try:
                        validate_instrumentation_plan(
                            candidate,
                            profile,
                            existing_tables=available_tables,
                            allow_existing_table=True,
                        )
                    except GeneratedSchemaError as exc:
                        validation_error = exc
                        continue
                    instrumentation = candidate
                    instrumentation_span.update(metadata={"attempt": attempt})
                    break
                if instrumentation is None:
                    assert validation_error is not None
                    raise validation_error
            fingerprint = schema_fingerprint(instrumentation)
            instrumentation_span.update(
                output=instrumentation.model_dump(mode="json"),
                metadata={
                    "column_count": len(instrumentation.columns),
                    "schema_fingerprint": fingerprint,
                    "reused_contract": reused_contract,
                },
            )

        with self._tracer.span("validate_schema") as validation_span:
            validate_instrumentation_plan(
                instrumentation,
                profile,
                existing_tables=available_tables,
                allow_existing_table=True,
            )
            ddl = build_ddl(instrumentation, database=self._database)
            schema = SchemaArtifact(
                run_id=run_id,
                table_name=instrumentation.table_name,
                ddl=ddl,
                schema_reasoning=instrumentation.schema_reasoning,
                partition_by=instrumentation.partition_by,
                partition_by_reasoning=instrumentation.partition_by_reasoning,
                order_by=instrumentation.order_by,
                order_by_reasoning=[
                    item.model_dump(mode="json")
                    for item in instrumentation.order_by_reasoning
                ],
                schema={
                    column.name: (
                        f"Nullable({column.base_type})"
                        if column.nullable
                        else column.base_type
                    )
                    for column in instrumentation.columns
                },
            )
            validation_span.update(
                output={"table_name": schema.table_name, "validated": True}
            )

        with self._tracer.span("execute_ddl") as ddl_span:
            table_exists = instrumentation.table_name in available_tables
            if table_exists:
                self._validate_existing_table(instrumentation)
                if not reused_contract:
                    actual_order_by = _sorting_key_columns(
                        self._clickhouse.get_sorting_key(instrumentation.table_name)
                    )
                    instrumentation = instrumentation.model_copy(
                        update={
                            "order_by": actual_order_by,
                            "order_by_reasoning": [
                                OrderByFieldReason(
                                    field=field,
                                    role=(
                                        "time_filter"
                                        if field == instrumentation.timestamp_field
                                        else "other"
                                    ),
                                    reason=(
                                        "Preserved from the existing ClickHouse "
                                        "sorting key during contract bootstrap"
                                    ),
                                )
                                for field in actual_order_by
                            ],
                        }
                    )
                    validate_instrumentation_plan(
                        instrumentation,
                        profile,
                        existing_tables=available_tables,
                        allow_existing_table=True,
                    )
                    fingerprint = schema_fingerprint(instrumentation)
                    ddl = build_ddl(instrumentation, database=self._database)
                    schema = SchemaArtifact(
                        run_id=run_id,
                        table_name=instrumentation.table_name,
                        ddl=ddl,
                        schema_reasoning=instrumentation.schema_reasoning,
                        partition_by=instrumentation.partition_by,
                        partition_by_reasoning=instrumentation.partition_by_reasoning,
                        order_by=instrumentation.order_by,
                        order_by_reasoning=[
                            item.model_dump(mode="json")
                            for item in instrumentation.order_by_reasoning
                        ],
                        schema={
                            column.name: (
                                f"Nullable({column.base_type})"
                                if column.nullable
                                else column.base_type
                            )
                            for column in instrumentation.columns
                        },
                    )
            else:
                self._clickhouse.command(ddl)
            if not reused_contract:
                self._run_store.save_schema_contract(
                    feature,
                    instrumentation,
                    fingerprint=fingerprint,
                    run_id=run_id,
                )
            self._run_store.save_artifact(
                run_id, "schema", schema.model_dump(mode="json", by_alias=True)
            )
            self._run_store.save_artifact(
                run_id,
                "instrumentation_plan",
                instrumentation.model_dump(mode="json"),
            )
            ddl_span.update(
                output={
                    "table": instrumentation.table_name,
                    "reused_existing": table_exists,
                }
            )

        with self._tracer.span("materialize_feature") as materialization_span:
            materialization = self._run_store.get_materialization_contract(feature)
            reused_materialization = materialization is not None
            if materialization is None:
                materialization = build_materialization_plan(
                    feature=feature,
                    instrumentation=instrumentation,
                    source_schema_fingerprint=fingerprint,
                )
            elif materialization.source_schema_fingerprint != fingerprint:
                raise RuntimeError(
                    "Materialization contract does not match the active source schema"
                )
            materialization_ddl = compile_materialization(
                materialization,
                instrumentation=instrumentation,
                database=self._database,
            )
            target_exists = materialization.target_table in available_tables
            view_exists = materialization.view_name in available_tables
            if not target_exists:
                self._clickhouse.command(materialization_ddl.target_ddl)
            if not view_exists:
                self._clickhouse.command(materialization_ddl.view_ddl)
            if table_exists and not target_exists:
                self._clickhouse.command(materialization_ddl.backfill_sql)
            if not reused_materialization:
                self._run_store.save_materialization_contract(
                    feature,
                    materialization,
                    run_id=run_id,
                )
            self._run_store.save_artifact(
                run_id,
                "materialization_plan",
                materialization.model_dump(mode="json"),
            )
            materialization_span.update(
                output={
                    "target_table": materialization.target_table,
                    "view_name": materialization.view_name,
                    "reused_contract": reused_materialization,
                    "backfilled": table_exists and not target_exists,
                }
            )

        with self._tracer.span("ingest_events") as ingestion_span:
            if table_exists:
                count_rows = self._clickhouse.query_rows(
                    f"SELECT count() FROM `{instrumentation.table_name}`"
                )
                rows_loaded = int(str(count_rows[0][0]))
            else:
                rows_loaded = ingest_events(
                    self._clickhouse,
                    instrumentation,
                    events_path,
                    database=self._database,
                )
            if rows_loaded != profile.event_count:
                raise RuntimeError(
                    f"Expected {profile.event_count} rows, inserted {rows_loaded}"
                )
            ingestion_span.update(output={"rows_loaded": rows_loaded})

        analytics_tables = list(
            dict.fromkeys(
                [
                    *available_tables,
                    instrumentation.table_name,
                    materialization.target_table,
                ]
            )
        )
        table_schemas = self._table_schemas(analytics_tables)
        selected_context = context_selection.model_dump(mode="json")

        columns_by_table = {
            table: [column["name"] for column in columns]
            for table, columns in table_schemas.items()
        }
        allowed_tables = analytics_tables
        analytics_plan_input: dict[str, object] = {
            "specification": spec,
            "instrumentation": instrumentation.model_dump(mode="json"),
            "context": selected_context,
            "table_schemas": table_schemas,
        }
        with self._tracer.span(
            "analytics_agent_plan", input=analytics_plan_input, as_type="agent"
        ) as plan_span:
            # Deterministic primitives are the guaranteed floor; the agent's own
            # queries extend them with questions no fixed builder anticipated.
            analysis_plan = build_deterministic_analysis_plan(
                instrumentation, profile=profile
            )
            analysis_plan.analyses.append(
                build_materialized_analysis(materialization)
            )
            analysis_plan.analyses.extend(
                build_baseline_analyses(
                    instrumentation,
                    context=latest_context,
                    available_tables=available_tables,
                    table_columns=columns_by_table,
                )
            )
            proposed_analysis_plan, accepted, rejections = self._plan_agent_queries(
                analytics_plan_input,
                allowed_tables=allowed_tables,
                table_columns=columns_by_table,
                reserved_ids={analysis.query_id for analysis in analysis_plan.analyses},
            )
            analysis_plan.analyses.extend(accepted)
            plan_span.update(
                output={
                    "proposed_plan": (
                        proposed_analysis_plan.model_dump(mode="json")
                        if proposed_analysis_plan is not None
                        else None
                    ),
                    "executed_plan": analysis_plan.model_dump(mode="json"),
                    "rejected_queries": rejections,
                },
                metadata={
                    "agent_proposal_count": (
                        len(proposed_analysis_plan.analyses)
                        if proposed_analysis_plan is not None
                        else 0
                    ),
                    "agent_queries_accepted": len(accepted),
                    "agent_queries_rejected": len(rejections),
                    "total_queries": len(analysis_plan.analyses),
                },
            )

        query_results: list[JsonValue] = []
        total_result_rows = 0
        failed_queries: list[JsonValue] = []
        with self._tracer.span("execute_analytics_sql") as sql_span:
            for analysis in analysis_plan.analyses:
                sql = validate_analysis_sql(
                    analysis.sql,
                    allowed_tables=allowed_tables,
                    table_columns=columns_by_table,
                )
                try:
                    rows = self._clickhouse.query_rows(
                        sql,
                        query_settings={
                            "max_execution_time": 30,
                            "max_result_rows": 200,
                            "max_rows_to_read": 200_000_000,
                        },
                    )
                except Exception as exc:  # noqa: BLE001 - reported, never fatal
                    # A single unexecutable query must not discard the analyses
                    # that did run; the failure is recorded for the trace.
                    failed_queries.append(
                        {
                            "query_id": analysis.query_id,
                            "sql": sql,
                            "error": str(exc)[:500],
                        }
                    )
                    continue
                total_result_rows += len(rows)
                query_results.append(
                    {
                        "query_id": analysis.query_id,
                        "analysis_type": analysis.analysis_type,
                        "purpose": analysis.purpose,
                        "sql": sql,
                        "row_count": len(rows),
                        "columns": list[JsonValue](_result_columns(sql)),
                        "rows": [[_json_value(value) for value in row] for row in rows],
                    }
                )
            if not query_results:
                raise RuntimeError(
                    "No analytics query executed successfully; "
                    f"failures: {failed_queries}"
                )
            sql_span.update(
                output={
                    "queries_executed": len(query_results),
                    "result_rows": total_result_rows,
                    "failed_queries": failed_queries,
                },
                metadata={"queries_failed": len(failed_queries)},
            )

        self._run_store.save_artifact(
            run_id,
            "proposed_analysis_plan",
            {
                "plan": (
                    proposed_analysis_plan.model_dump(mode="json")
                    if proposed_analysis_plan is not None
                    else None
                ),
                "rejected_queries": rejections,
            },
        )
        self._run_store.save_artifact(
            run_id, "analysis_plan", analysis_plan.model_dump(mode="json")
        )
        self._run_store.save_artifact(run_id, "query_results", query_results)

        analytics_insights_input = {
            "specification": spec,
            "context": selected_context,
            "analysis_plan": analysis_plan.model_dump(mode="json"),
            "query_results": query_results,
        }
        with self._tracer.span(
            "analytics_agent_insights",
            input=analytics_insights_input,
            as_type="agent",
        ) as insight_span:
            analytics_output = self._agents.complete(
                AnalyticsAgentOutput,
                name="analytics_insights",
                system_prompt=_INSIGHT_PROMPT,
                input_payload=analytics_insights_input,
            )
            insight_span.update(
                output=analytics_output.model_dump(mode="json"),
                metadata={"insight_count": len(analytics_output.insights)},
            )

        self._run_store.save_artifact(
            run_id, "insights", analytics_output.model_dump(mode="json")
        )

        context_write_input = {
            "specification": spec,
            "instrumentation": instrumentation.model_dump(mode="json"),
            "schema": schema.model_dump(mode="json", by_alias=True),
            "rows_loaded": rows_loaded,
            "insights": analytics_output.model_dump(mode="json"),
            "existing_context": (
                latest_context.model_dump(mode="json") if latest_context else None
            ),
            "table_schemas": table_schemas,
        }
        with self._tracer.span(
            "context_agent_write", input=context_write_input, as_type="agent"
        ) as write_span:
            context_version = self._write_context(
                run_id=run_id,
                spec=spec,
                instrumentation=instrumentation,
                schema=schema,
                rows_loaded=rows_loaded,
                analytics_output=analytics_output,
                previous=latest_context,
                table_schemas=table_schemas,
                columns_by_table=columns_by_table,
            )
            write_span.update(output={"context_version": context_version})

        result = ProcessFeatureResult(
            run_id=run_id,
            status="completed",
            feature=feature,
            table_created=instrumentation.table_name,
            rows_loaded=rows_loaded,
            context_version=context_version,
            partition_by=instrumentation.partition_by,
            partition_by_reasoning=instrumentation.partition_by_reasoning,
            insights=[
                InsightSummary(title=insight.title, confidence=insight.confidence)
                for insight in analytics_output.insights
            ],
            langfuse_trace_id=trace_id,
        )
        self._run_store.save_run_snapshot(result, event_count=profile.event_count)
        return result

    def _plan_agent_queries(
        self,
        plan_input: dict[str, object],
        *,
        allowed_tables: Sequence[str],
        table_columns: Mapping[str, Sequence[str]],
        reserved_ids: set[str],
    ) -> tuple[AnalysisPlan | None, list[AnalysisQuery], list[JsonValue]]:
        """Ask the agent for extra analyses and keep only what validates.

        Validation failures are fed back verbatim so the agent can correct a
        wrong column or table rather than losing the query outright. Anything
        still invalid after the retries is dropped and recorded: the primitives
        already guarantee a usable plan, so neither a bad query nor an
        unavailable planning agent ever fails a run.
        """

        proposed: AnalysisPlan | None = None
        accepted: list[AnalysisQuery] = []
        rejections: list[JsonValue] = []
        taken = set(reserved_ids)
        attempt_input = dict(plan_input)

        for _attempt in range(2):
            try:
                proposed = self._agents.complete(
                    AnalysisPlan,
                    name="analysis_plan",
                    system_prompt=_ANALYSIS_PLAN_PROMPT,
                    input_payload=attempt_input,
                )
            except FireworksAgentError as exc:
                rejections.append({"query_id": None, "reason": str(exc)[:500]})
                break
            failures: list[str] = []
            for analysis in proposed.analyses:
                if analysis.query_id in taken:
                    continue
                try:
                    sql = validate_analysis_sql(
                        analysis.sql,
                        allowed_tables=allowed_tables,
                        table_columns=table_columns,
                    )
                except UnsafeAnalysisQueryError as exc:
                    failures.append(f"{analysis.query_id}: {exc}")
                    rejections.append(
                        {
                            "query_id": analysis.query_id,
                            "sql": analysis.sql,
                            "reason": str(exc),
                        }
                    )
                    continue
                taken.add(analysis.query_id)
                accepted.append(analysis.model_copy(update={"sql": sql}))
            if not failures:
                break
            # Only the still-failing queries are worth another attempt.
            attempt_input["validation_feedback"] = failures
            attempt_input["already_accepted_query_ids"] = sorted(taken)

        return proposed, accepted, rejections

    def _select_context(
        self,
        latest: ContextDocument | None,
        *,
        spec: str,
        profile: EventProfile,
        table_schemas: dict[str, list[dict[str, str]]],
    ) -> ContextSelection:
        """Pick the slice of accumulated context relevant to this feature.

        The stored document grows with every feature ever processed, so it is
        narrowed by an agent rather than passed whole into schema design. The
        selection is then filtered back down to what the document actually
        contains, so a fabricated relationship can never shape a schema.
        """

        if latest is None or not (
            latest.entities
            or latest.relationships
            or latest.metrics
            or latest.known_issues
        ):
            return ContextSelection()

        selection = self._agents.complete(
            ContextSelection,
            name="context_read",
            system_prompt=_CONTEXT_READ_PROMPT,
            input_payload={
                "specification": spec,
                "event_profile": profile.model_dump(mode="json"),
                "context": latest.model_dump(mode="json"),
                "table_schemas": table_schemas,
            },
        )
        known_entities = {entity.get("name") for entity in latest.entities}
        known_relationships = {
            _relationship_identity(relationship)
            for relationship in latest.relationships
        }
        known_metrics = {metric.get("name") for metric in latest.metrics}
        known_conventions = set(latest.naming_conventions)
        known_issue_keys = {issue.get("key") for issue in latest.known_issues}
        return ContextSelection(
            relevant_entities=[
                entity
                for entity in selection.relevant_entities
                if entity.name in known_entities
            ],
            relevant_relationships=[
                relationship
                for relationship in selection.relevant_relationships
                if _relationship_identity(relationship.model_dump(mode="json"))
                in known_relationships
            ],
            relevant_metrics=[
                metric
                for metric in selection.relevant_metrics
                if metric.name in known_metrics
            ],
            relevant_known_issues=[
                issue
                for issue in selection.relevant_known_issues
                if issue.key in known_issue_keys
            ],
            naming_conventions=[
                convention
                for convention in selection.naming_conventions
                if convention in known_conventions
            ],
            reuse_notes=list(selection.reuse_notes),
        )

    def _write_context(
        self,
        *,
        run_id: str,
        spec: str,
        instrumentation: InstrumentationPlan,
        schema: SchemaArtifact,
        rows_loaded: int,
        analytics_output: AnalyticsAgentOutput,
        previous: ContextDocument | None,
        table_schemas: dict[str, list[dict[str, str]]],
        columns_by_table: Mapping[str, Sequence[str]],
    ) -> int:
        """Record newly discovered knowledge as the next context version."""

        write_input: dict[str, object] = {
            "specification": spec,
            "instrumentation": instrumentation.model_dump(mode="json"),
            "schema": schema.model_dump(mode="json", by_alias=True),
            "rows_loaded": rows_loaded,
            "insights": analytics_output.model_dump(mode="json"),
            "existing_context": (
                previous.model_dump(mode="json") if previous is not None else None
            ),
            "table_schemas": table_schemas,
        }
        context_output: ContextAgentOutput | None = None
        for _attempt in range(2):
            candidate = self._agents.complete(
                ContextAgentOutput,
                name="context_write",
                system_prompt=_CONTEXT_WRITE_PROMPT,
                input_payload=write_input,
            )
            try:
                validate_context_output(candidate, table_schemas=columns_by_table)
            except ContextValidationError as exc:
                write_input["validation_feedback"] = str(exc)
                context_output = candidate
                continue
            context_output = candidate
            break
        else:
            # The schema, data, and insights are already durable, so keep the
            # knowledge that validates instead of failing a completed run.
            assert context_output is not None
            context_output = valid_context_subset(
                context_output, table_schemas=columns_by_table
            )

        assert context_output is not None
        context_version = self._run_store.next_context_version()
        document = merge_context(
            previous,
            context_output,
            version=context_version,
            run_id=run_id,
        )
        self._run_store.save_context_version(document, run_id=run_id)
        context_diff = ContextDiff(
            run_id=run_id,
            context_version=context_version,
            entities_added=[
                entity.model_dump(mode="json")
                for entity in context_output.entities_added
            ],
            relationships_added=[
                relationship.model_dump(mode="json")
                for relationship in context_output.relationships_added
            ],
            metrics_added=[
                metric.model_dump(mode="json")
                for metric in context_output.metrics_added
            ],
            conventions_added=list(context_output.conventions_added),
            conflicts=list(context_output.conflicts),
        )
        self._run_store.save_artifact(
            run_id, "context_diff", context_diff.model_dump(mode="json")
        )
        return context_version

    def _validate_existing_table(self, plan: InstrumentationPlan) -> None:
        expected = {
            column.name: (
                f"Nullable({column.base_type})" if column.nullable else column.base_type
            )
            for column in plan.columns
        }
        actual = {
            column.name: column.data_type
            for column in self._clickhouse.list_columns(plan.table_name)
        }
        if actual != expected:
            raise RuntimeError(
                f"Existing table {plan.table_name} does not match generated schema"
            )

    def _table_schemas(self, tables: Sequence[str]) -> dict[str, list[dict[str, str]]]:
        return {
            table: [
                {"name": column.name, "type": column.data_type}
                for column in self._clickhouse.list_columns(table)
            ]
            for table in tables
        }


def _relationship_identity(relationship: Mapping[str, JsonValue]) -> tuple[str, ...]:
    return tuple(
        str(relationship.get(field, ""))
        for field in ("source_table", "source_column", "target_table", "target_column")
    )


def _sorting_key_columns(expression: str | None) -> list[str]:
    if expression is None:
        raise RuntimeError("Existing ClickHouse table has no readable sorting key")
    normalized = expression.strip()
    if normalized.startswith("tuple(") and normalized.endswith(")"):
        normalized = normalized[6:-1]
    elif normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]
    fields = [field.strip().strip("`") for field in normalized.split(",")]
    if not fields or any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field) is None for field in fields):
        raise RuntimeError(
            f"Existing ClickHouse sorting key is not a simple column key: {expression}"
        )
    return fields


_SELECT_LIST = re.compile(r"^SELECT\s+(.*?)\s+FROM\s", re.IGNORECASE | re.DOTALL)
_TRAILING_ALIAS = re.compile(
    r".*\bAS\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\s*$", re.IGNORECASE
)


def _result_columns(sql: str) -> list[str]:
    """Name the projected columns so the insight agent can read positional rows.

    Rows come back as bare lists, which an interpreting model cannot label on
    its own. Splitting is depth-aware so commas inside function calls do not
    split an expression. Falls back to positional names when a projection is
    too complex to label.
    """

    match = _SELECT_LIST.match(sql.strip())
    if match is None:
        return []
    projection = match.group(1)
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for character in projection:
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))

    columns: list[str] = []
    for index, part in enumerate(parts):
        expression = part.strip()
        alias = _TRAILING_ALIAS.match(expression)
        if alias is not None:
            columns.append(alias.group(1))
        elif re.fullmatch(r"`?[A-Za-z_][A-Za-z0-9_]*`?", expression):
            columns.append(expression.strip("`"))
        else:
            columns.append(f"column_{index + 1}")
    return columns


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
