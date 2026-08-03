from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.agents import AnalysisQuery, InstrumentationPlan, MaterializationPlan

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MaterializationError(RuntimeError):
    """Raised when a bounded materialization cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class MaterializationDDL:
    target_table: str
    view_name: str
    target_ddl: str
    view_ddl: str
    backfill_sql: str


def _quoted(identifier: str) -> str:
    if _IDENTIFIER.fullmatch(identifier) is None:
        raise MaterializationError(f"Unsafe materialization identifier: {identifier!r}")
    return f"`{identifier}`"


def build_materialization_plan(
    *,
    feature: str,
    instrumentation: InstrumentationPlan,
    source_schema_fingerprint: str,
) -> MaterializationPlan:
    columns = {column.name: column for column in instrumentation.columns}
    event_field = "event" if "event" in columns else "event_name"
    if event_field not in columns:
        raise MaterializationError("Feature table has no event field")

    excluded = {
        event_field,
        instrumentation.timestamp_field,
        instrumentation.primary_entity,
    }
    dimensions = [
        name
        for name in instrumentation.dimensions
        if name in columns and not columns[name].nullable and name not in excluded
    ][:2]
    stem = instrumentation.table_name.removesuffix("_events")
    return MaterializationPlan(
        feature=feature,
        source_schema_fingerprint=source_schema_fingerprint,
        source_table=instrumentation.table_name,
        target_table=f"{stem}_daily_aggregate",
        view_name=f"{stem}_daily_aggregate_mv",
        timestamp_field=instrumentation.timestamp_field,
        event_field=event_field,
        entity_field=instrumentation.primary_entity,
        dimensions=dimensions,
        purpose=(
            "Accelerate repeated daily funnel, trend, and segment computations "
            "using the entity and dimensions selected from the feature contract"
        ),
    )


def compile_materialization(
    plan: MaterializationPlan,
    *,
    instrumentation: InstrumentationPlan,
    database: str,
) -> MaterializationDDL:
    columns = {column.name: column for column in instrumentation.columns}
    required = {
        plan.timestamp_field,
        plan.event_field,
        plan.entity_field,
        *plan.dimensions,
    }
    unknown = required - set(columns)
    if unknown:
        raise MaterializationError(
            f"Materialization references unknown fields: {sorted(unknown)}"
        )
    if plan.source_table != instrumentation.table_name:
        raise MaterializationError("Materialization source does not match schema contract")
    if columns[plan.timestamp_field].nullable:
        raise MaterializationError("Materialization timestamp cannot be Nullable")
    if columns[plan.entity_field].nullable:
        raise MaterializationError("Materialization entity cannot be Nullable")
    if any(columns[name].nullable for name in plan.dimensions):
        raise MaterializationError("Materialization dimensions cannot be Nullable")

    database_sql = _quoted(database)
    source_sql = _quoted(plan.source_table)
    target_sql = _quoted(plan.target_table)
    view_sql = _quoted(plan.view_name)
    timestamp_sql = _quoted(plan.timestamp_field)
    event_sql = _quoted(plan.event_field)
    entity_sql = _quoted(plan.entity_field)
    dimension_sql = [_quoted(name) for name in plan.dimensions]

    dimension_definitions = [
        f"    {_quoted(name)} {columns[name].base_type}" for name in plan.dimensions
    ]
    target_columns = [
        "    date Date",
        f"    {event_sql} {columns[plan.event_field].base_type}",
        *dimension_definitions,
        "    event_rows AggregateFunction(count)",
        (
            "    entities AggregateFunction(uniq, "
            f"{columns[plan.entity_field].base_type})"
        ),
    ]
    key_columns = ["date", plan.event_field, *plan.dimensions]
    key_sql = ", ".join(_quoted(name) for name in key_columns)
    select_dimensions = [event_sql, *dimension_sql]
    select_prefix = ",\n    ".join(
        [f"toDate({timestamp_sql}) AS date", *select_dimensions]
    )
    group_sql = ", ".join(["date", *select_dimensions])
    aggregate_select = (
        f"SELECT\n    {select_prefix},\n    countState() AS event_rows,\n"
        f"    uniqState({entity_sql}) AS entities\n"
        f"FROM {database_sql}.{source_sql}\nGROUP BY {group_sql}"
    )
    target_ddl = (
        f"CREATE TABLE {database_sql}.{target_sql}\n(\n"
        + ",\n".join(target_columns)
        + f"\n)\nENGINE = AggregatingMergeTree\nORDER BY ({key_sql})"
    )
    view_ddl = (
        f"CREATE MATERIALIZED VIEW {database_sql}.{view_sql}\n"
        f"TO {database_sql}.{target_sql}\nAS\n{aggregate_select}"
    )
    backfill_sql = f"INSERT INTO {database_sql}.{target_sql}\n{aggregate_select}"
    return MaterializationDDL(
        target_table=plan.target_table,
        view_name=plan.view_name,
        target_ddl=target_ddl,
        view_ddl=view_ddl,
        backfill_sql=backfill_sql,
    )


def build_materialized_analysis(plan: MaterializationPlan) -> AnalysisQuery:
    dimensions = [plan.event_field, *plan.dimensions]
    select_dimensions = ", ".join(_quoted(name) for name in dimensions)
    group_dimensions = ", ".join(["date", *(_quoted(name) for name in dimensions)])
    return AnalysisQuery(
        query_id="materialized_daily_activity",
        analysis_type="trend",
        purpose=plan.purpose,
        sql=(
            f"SELECT date, {select_dimensions}, countMerge(event_rows) AS event_rows, "
            f"uniqMerge(entities) AS entities FROM {_quoted(plan.target_table)} "
            f"GROUP BY {group_dimensions} ORDER BY date"
        ),
    )


__all__ = [
    "MaterializationDDL",
    "MaterializationError",
    "build_materialization_plan",
    "build_materialized_analysis",
    "compile_materialization",
]
