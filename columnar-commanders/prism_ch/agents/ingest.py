"""Load the sampled events into the table the agent just created.

Designing a schema and never putting data in it leaves the next step guessing:
the Analytics Agent has a table with a good ordering key and zero rows. This
closes that loop.

Three things make it more than a bulk insert:

- **Field paths.** The schema flattens nested objects, so `payment_amount` may
  come from `payment.amount`. Mapping is by dotted path, not by name.
- **Coercion.** ClickHouse will not take the string `"2026-07-01T10:00:00Z"`
  for a `DateTime64`, nor `None` for a non-nullable column. Values are coerced
  to what the declared type accepts, and absent ones fall back to the type's
  zero - which is exactly what the `DEFAULT` on that column means.
- **MATERIALIZED columns are excluded.** The server computes them; naming one
  in an INSERT is an error.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from .types import ColumnSpec, TableSpec

log = logging.getLogger(__name__)

INNER = re.compile(r"^(?:Nullable|LowCardinality)\((.*)\)$")


def unwrap(ch_type: str) -> tuple[str, bool]:
    """Strip Nullable/LowCardinality wrappers. Returns (inner type, nullable)."""
    nullable = False
    current = ch_type.strip()
    while True:
        match = INNER.match(current)
        if not match:
            return current, nullable
        nullable = nullable or current.startswith("Nullable(")
        current = match.group(1).strip()


def resolve(event: dict[str, Any], path: str | None) -> Any:
    """Look up a possibly dotted path, e.g. `payment.amount`."""
    if not path:
        return None
    node: Any = event
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def coerce(value: Any, ch_type: str) -> Any:
    """Convert a raw JSON value to something the column will accept."""
    inner, nullable = unwrap(ch_type)

    if value is None:
        if nullable:
            return None
        # Mirror the column's DEFAULT rather than failing the row: an absent
        # optional field is the common case, not an error.
        return _zero(inner)

    if inner.startswith(("DateTime64", "DateTime")):
        return _parse_datetime(value) or (None if nullable else _zero(inner))
    if inner == "Date":
        parsed = _parse_datetime(value)
        return parsed.date() if parsed else (None if nullable else _zero(inner))
    if inner.startswith(("UInt", "Int")):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None if nullable else 0
    if inner.startswith(("Float", "Decimal")):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None if nullable else 0.0
    if inner == "UUID":
        return str(value)
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, default=str)
    if isinstance(value, bool):
        return int(value)
    return str(value)


def _zero(inner: str) -> Any:
    if inner.startswith(("DateTime64", "DateTime")):
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if inner == "Date":
        return date(1970, 1, 1)
    if inner.startswith(("UInt", "Int")):
        return 0
    if inner.startswith(("Float", "Decimal")):
        return 0.0
    if inner == "UUID":
        return "00000000-0000-0000-0000-000000000000"
    return ""


def insertable_columns(table: TableSpec) -> list[ColumnSpec]:
    """Columns an INSERT may name. MATERIALIZED ones are server-computed."""
    return [c for c in table.columns if not c.materialized]


def build_rows(
    events: list[dict[str, Any]], table: TableSpec, mapping: dict[str, str] | None = None
) -> tuple[list[str], list[list[Any]]]:
    """Map raw events onto the table's columns.

    `mapping` is the proposal's `event_mapping` (raw field -> column). A
    column's own `source_field` wins where both are present, since it is the
    more specific statement.
    """
    columns = insertable_columns(table)
    by_column = {column: raw for raw, column in (mapping or {}).items()}

    names = [c.name for c in columns]
    rows: list[list[Any]] = []
    for event in events:
        row = []
        for column in columns:
            path = column.source_field or by_column.get(column.name) or column.name
            row.append(coerce(resolve(event, path), column.type))
        rows.append(row)
    return names, rows


def ingest(
    client: Any,
    *,
    database: str,
    physical_table: str,
    table: TableSpec,
    events: list[dict[str, Any]],
    mapping: dict[str, str] | None = None,
) -> int:
    """Insert the events. Returns the row count written."""
    if not events:
        return 0
    names, rows = build_rows(events, table, mapping)
    if not names or not rows:
        return 0
    client.insert(
        table=physical_table, database=database, column_names=names, data=rows
    )
    log.info("loaded %d rows into %s.%s", len(rows), database, physical_table)
    return len(rows)


BATCH_SIZE = 10_000


def ingest_file(
    client: Any,
    *,
    database: str,
    physical_table: str,
    table: TableSpec,
    data_path: str,
    mapping: dict[str, str] | None = None,
) -> int:
    """Read a local NDJSON/JSON file and INSERT in batches. Returns total rows."""
    import json as _json
    import pathlib

    path = pathlib.Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"data file not found: {data_path}")

    columns = insertable_columns(table)
    col_names = [c.name for c in columns]
    by_column = {column: raw for raw, column in (mapping or {}).items()}
    total = 0
    batch: list[list[Any]] = []

    def flush() -> int:
        if not batch:
            return 0
        client.insert(
            table=physical_table, database=database,
            column_names=col_names, data=list(batch),
        )
        n = len(batch)
        batch.clear()
        return n

    text = path.read_text()
    try:
        parsed = _json.loads(text)
        if isinstance(parsed, list):
            lines = parsed
        else:
            lines = [parsed]
    except _json.JSONDecodeError:
        lines = None

    if lines is not None:
        for event in lines:
            if not isinstance(event, dict):
                continue
            row = []
            for column in columns:
                p = column.source_field or by_column.get(column.name) or column.name
                row.append(coerce(resolve(event, p), column.type))
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                total += flush()
    else:
        for raw_line in text.splitlines():
            raw_line = raw_line.strip().rstrip(",")
            if not raw_line:
                continue
            try:
                event = _json.loads(raw_line)
            except _json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            row = []
            for column in columns:
                p = column.source_field or by_column.get(column.name) or column.name
                row.append(coerce(resolve(event, p), column.type))
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                total += flush()

    total += flush()
    log.info("bulk-loaded %d rows from %s into %s.%s", total, data_path, database, physical_table)
    return total
