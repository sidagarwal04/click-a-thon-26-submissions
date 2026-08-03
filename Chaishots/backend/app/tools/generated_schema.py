from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from app.repositories.clickhouse import ClickHouseRepository
from app.schemas.agents import ColumnPlan, InstrumentationPlan
from app.schemas.features import EventProfile, ObservedFieldType

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PARTITION_EXPRESSION = re.compile(
    r"(?:(toDate|toMonday|toStartOfMonth|toYYYYMM|toYYYY)\()?"
    r"([A-Za-z_][A-Za-z0-9_]*)(?(1)\))"
)
_TYPE_COMPATIBILITY = {
    ObservedFieldType.STRING: {"String"},
    ObservedFieldType.INTEGER: {"Int64", "Float64"},
    ObservedFieldType.FLOAT: {"Float64"},
    ObservedFieldType.BOOLEAN: {"UInt8"},
    ObservedFieldType.OBJECT: {"String"},
    ObservedFieldType.ARRAY: {"String"},
    ObservedFieldType.NULL: {"String"},
    ObservedFieldType.MIXED: {"String"},
}


class GeneratedSchemaError(RuntimeError):
    """Raised when an agent-proposed schema fails deterministic validation."""


def _quoted(identifier: str) -> str:
    if _IDENTIFIER.fullmatch(identifier) is None:
        raise GeneratedSchemaError(f"Unsafe ClickHouse identifier: {identifier!r}")
    return f"`{identifier}`"


def _compile_partition_expression(
    expression: str | None, columns: dict[str, ColumnPlan]
) -> str | None:
    if expression is None:
        return None
    match = _PARTITION_EXPRESSION.fullmatch(expression)
    if match is None:
        raise GeneratedSchemaError(f"Unsupported partition expression: {expression!r}")
    function, field = match.groups()
    if field not in columns:
        raise GeneratedSchemaError("PARTITION BY references an unknown column")
    if columns[field].nullable:
        raise GeneratedSchemaError("PARTITION BY cannot use a Nullable column")
    quoted_field = _quoted(field)
    return f"{function}({quoted_field})" if function else quoted_field


def validate_instrumentation_plan(
    plan: InstrumentationPlan,
    profile: EventProfile,
    *,
    existing_tables: Sequence[str],
    allow_existing_table: bool = False,
) -> None:
    _quoted(plan.table_name)
    if plan.table_name in existing_tables and not allow_existing_table:
        raise GeneratedSchemaError(f"Target table already exists: {plan.table_name}")
    if not plan.table_name.endswith("_events"):
        raise GeneratedSchemaError("Generated table name must end with '_events'")

    columns = {column.name: column for column in plan.columns}
    if len(columns) != len(plan.columns):
        raise GeneratedSchemaError("Generated schema contains duplicate columns")
    # Nested paths are retained in the event profile so agents can understand
    # object contents, but nested objects are stored as JSON in their top-level
    # column. Ingestion therefore creates columns only for top-level fields.
    top_level_fields = {
        name: field for name, field in profile.fields.items() if "." not in name
    }
    expected = set(top_level_fields)
    if set(columns) != expected:
        missing = sorted(expected - set(columns))
        extra = sorted(set(columns) - expected)
        raise GeneratedSchemaError(
            f"Generated columns do not match observed fields; missing={missing}, extra={extra}"
        )

    for name, field in top_level_fields.items():
        _quoted(name)
        column = columns[name]
        compatible = _TYPE_COMPATIBILITY[field.observed_type]
        if name == plan.timestamp_field:
            compatible = {"DateTime64(3)"}
        if column.base_type not in compatible:
            raise GeneratedSchemaError(
                f"Column {name!r} type {column.base_type} is incompatible with "
                f"observed type {field.observed_type}"
            )
        needs_nullable = (
            field.presence_count < profile.event_count
            or ObservedFieldType.NULL in field.observed_types
        )
        if needs_nullable and not column.nullable:
            raise GeneratedSchemaError(f"Optional column must be Nullable: {name}")

    if plan.timestamp_field not in top_level_fields:
        raise GeneratedSchemaError(
            "Timestamp field is not present in the event profile"
        )
    if plan.primary_entity not in top_level_fields:
        raise GeneratedSchemaError("Primary entity is not present in the event profile")
    if len(plan.funnel_steps) < 2:
        raise GeneratedSchemaError("At least two observed funnel steps are required")
    unknown_steps = set(plan.funnel_steps) - set(profile.event_names)
    if unknown_steps:
        raise GeneratedSchemaError(
            f"Funnel steps were not observed: {sorted(unknown_steps)}"
        )
    unknown_dimensions = set(plan.dimensions) - set(top_level_fields)
    if unknown_dimensions:
        raise GeneratedSchemaError(
            f"Dimensions were not observed: {sorted(unknown_dimensions)}"
        )
    if any(name not in columns for name in plan.order_by):
        raise GeneratedSchemaError("ORDER BY references an unknown column")
    if any(columns[name].nullable for name in plan.order_by):
        raise GeneratedSchemaError("ORDER BY cannot use Nullable columns")
    _compile_partition_expression(plan.partition_by, columns)
    reasoned_fields = [item.field for item in plan.order_by_reasoning]
    if reasoned_fields != plan.order_by:
        raise GeneratedSchemaError(
            "ORDER BY reasoning must cover each key field once and in key order"
        )
    if plan.timestamp_field not in plan.order_by:
        raise GeneratedSchemaError("ORDER BY must include the timestamp field")
    near_unique_fields = {"id", "event_id", "request_id", "trace_id"}
    early_near_unique = near_unique_fields.intersection(plan.order_by[:2])
    if early_near_unique:
        raise GeneratedSchemaError(
            "Near-unique row identifiers cannot appear in the first two ORDER BY "
            f"positions: {sorted(early_near_unique)}"
        )


def schema_fingerprint(plan: InstrumentationPlan) -> str:
    """Hash only the physical schema, excluding semantic explanations."""

    physical = {
        "table_name": plan.table_name,
        "timestamp_field": plan.timestamp_field,
        "partition_by": plan.partition_by,
        "columns": [column.model_dump(mode="json") for column in plan.columns],
        "order_by": plan.order_by,
    }
    canonical = json.dumps(physical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_ddl(plan: InstrumentationPlan, *, database: str) -> str:
    column_lines = []
    for column in plan.columns:
        data_type: str = column.base_type
        if column.nullable:
            data_type = f"Nullable({data_type})"
        column_lines.append(f"    {_quoted(column.name)} {data_type}")
    columns = ",\n".join(column_lines)
    order_by = ", ".join(_quoted(name) for name in plan.order_by)
    partition_expression = _compile_partition_expression(
        plan.partition_by, {column.name: column for column in plan.columns}
    )
    partition_clause = (
        f"PARTITION BY {partition_expression}\n" if partition_expression else ""
    )
    return (
        f"CREATE TABLE {_quoted(database)}.{_quoted(plan.table_name)}\n"
        f"(\n{columns}\n)\n"
        "ENGINE = MergeTree\n"
        f"{partition_clause}"
        f"ORDER BY ({order_by})"
    )


def _convert(value: JsonValue, column: ColumnPlan) -> object:
    if value is None:
        if column.nullable:
            return None
        raise GeneratedSchemaError(f"Non-null column {column.name!r} received null")
    if column.base_type == "String":
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return str(value)
    if isinstance(value, (dict, list)):
        raise GeneratedSchemaError(
            f"Column {column.name!r} expected a scalar numeric value"
        )
    if column.base_type == "UInt8":
        return int(value)
    if column.base_type == "Int64":
        return int(value)
    if column.base_type == "Float64":
        return float(value)
    if column.base_type == "DateTime64(3)":
        if not isinstance(value, str):
            raise GeneratedSchemaError("Timestamp value must be a string")
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise GeneratedSchemaError(f"Unsupported generated type: {column.base_type}")


def _rows(events_path: Path, columns: Sequence[ColumnPlan]) -> Iterator[list[object]]:
    with events_path.open("r", encoding="utf-8") as event_file:
        for line_number, line in enumerate(event_file, start=1):
            if not line.strip():
                continue
            decoded = json.loads(line)
            if not isinstance(decoded, dict):
                raise GeneratedSchemaError(f"Event line {line_number} is not an object")
            event = cast(dict[str, JsonValue], decoded)
            row = []
            for column in columns:
                value: JsonValue = event.get(column.name)
                row.append(_convert(value, column))
            yield row


def ingest_events(
    repository: ClickHouseRepository,
    plan: InstrumentationPlan,
    events_path: Path,
    *,
    database: str,
    batch_size: int = 1000,
) -> int:
    batch: list[list[object]] = []
    inserted = 0
    names = [column.name for column in plan.columns]
    for row in _rows(events_path, plan.columns):
        batch.append(row)
        if len(batch) >= batch_size:
            repository.insert(plan.table_name, batch, names, database=database)
            inserted += len(batch)
            batch = []
    if batch:
        repository.insert(plan.table_name, batch, names, database=database)
        inserted += len(batch)
    return inserted
