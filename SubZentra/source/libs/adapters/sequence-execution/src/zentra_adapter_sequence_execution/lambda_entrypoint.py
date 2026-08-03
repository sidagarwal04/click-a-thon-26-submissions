"""The actual module AWS Lambda points at (`lambda_entrypoint.handler`).

Everything here is environment/configuration wiring, constructed once at
cold start: `build_handler` (ticket #52) wrapping the real
ChdbSequenceExecutionPort (ticket #51) with a Postgres-backed raw-table
lookup. No business logic lives in this module.
"""

from __future__ import annotations

import os
from pathlib import Path

from zentra_adapter_postgres import Database, PostgresSequenceUnitOfWorkFactory

from .chdb_execution import ChdbSequenceExecutionPort
from .lambda_handler import build_handler
from .postgres_lookup import PostgresRawTableLookup
from .raw_table import ConnectorClickHouseConnection


def _build_port() -> ChdbSequenceExecutionPort:
    database = Database(os.environ["DATABASE_RUNTIME_URL"])
    sequence_lookup = PostgresRawTableLookup(
        PostgresSequenceUnitOfWorkFactory(database)
    )
    connector_clickhouse = ConnectorClickHouseConnection(
        host=os.environ["CONNECTOR_CLICKHOUSE_HOST"],
        port=int(os.environ.get("CONNECTOR_CLICKHOUSE_PORT", "9000")),
        user=os.environ.get("CONNECTOR_CLICKHOUSE_USER", "default"),
        password=os.environ.get("CONNECTOR_CLICKHOUSE_PASSWORD", ""),
    )
    # Lambda's own ephemeral storage — wiped between cold starts, never
    # shared across invocations of a different Tenant's data.
    storage_root = Path(
        os.environ.get("SEQUENCE_STORAGE_ROOT", "/tmp/sequence-execution")
    )
    return ChdbSequenceExecutionPort(
        connector_clickhouse=connector_clickhouse,
        storage_root=storage_root,
        sequence_lookup=sequence_lookup,
    )


handler = build_handler(_build_port())
