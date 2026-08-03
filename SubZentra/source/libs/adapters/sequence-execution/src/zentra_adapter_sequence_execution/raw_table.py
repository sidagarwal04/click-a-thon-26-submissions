"""Resolves a Sequence's Raw Table into a chDB table-function SQL fragment.

Neither branch ever copies data: a Connector Source Table is read live over
the wire via ClickHouse's `remote()` table function; a Data Source Dataset
Table Version is read directly from its file, local or S3, via `file()`/
`s3()`. Both are FROM-clause expressions, not standalone queries.
"""

from __future__ import annotations

from dataclasses import dataclass

from zentra_domain_sequence import (
    ConnectorSourceTableReference,
    DatasetTableVersionReference,
    RawTableReference,
)

_CHDB_FORMAT_NAMES = {
    "csv": "CSVWithNames",
    "parquet": "Parquet",
}


@dataclass(frozen=True, slots=True)
class ConnectorClickHouseConnection:
    """How to reach the shared ClickHouse instance Connector-sourced Raw
    Tables live in. Sequence's own domain model deliberately keeps a
    ConnectorSourceTableReference to identifying fields only (catalog
    version, table name) — this carries the connection details a real
    deployment injects as configuration, not something the Sequence
    graph itself stores."""

    host: str
    port: int
    user: str
    password: str


def _quote_literal(value: str) -> str:
    """Escapes a value for embedding in a single-quoted chDB/ClickHouse SQL
    literal. Single quotes and backslashes are the two characters that can
    break out of the literal; both are escaped."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def resolve_raw_table_sql(
    reference: RawTableReference,
    *,
    connector_clickhouse: ConnectorClickHouseConnection,
) -> str:
    """The FROM-clause SQL fragment a chDB query can select from to read
    this Raw Table, without ever mutating or copying it."""
    if isinstance(reference, ConnectorSourceTableReference):
        address = f"{connector_clickhouse.host}:{connector_clickhouse.port}"
        return (
            "remote("
            f"'{_quote_literal(address)}', "
            f"'{_quote_literal(reference.source_table_name)}', "
            f"'{_quote_literal(connector_clickhouse.user)}', "
            f"'{_quote_literal(connector_clickhouse.password)}')"
        )

    if isinstance(reference, DatasetTableVersionReference):
        chdb_format = _CHDB_FORMAT_NAMES[reference.file_format]
        table_function = (
            "s3" if reference.storage_locator.startswith("s3://") else "file"
        )
        return (
            f"{table_function}("
            f"'{_quote_literal(reference.storage_locator)}', '{chdb_format}')"
        )

    msg = f"Unsupported Raw Table reference: {reference!r}"
    raise TypeError(msg)
