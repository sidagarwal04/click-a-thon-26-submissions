"""Direct ClickHouse access via clickhouse-connect + SQLGlot validation."""

from __future__ import annotations

from typing import Any

import clickhouse_connect
import sqlglot
from clickhouse_connect.driver.client import Client
from sqlglot import exp

from conversation_agent import config

_DIALECT = "clickhouse"


def get_client() -> Client:
    if not config.CLICKHOUSE_HOST or not config.CLICKHOUSE_USER:
        raise RuntimeError("Set CLICKHOUSE_HOST and CLICKHOUSE_USER in .env")
    return clickhouse_connect.get_client(
        host=config.CLICKHOUSE_HOST,
        port=config.CLICKHOUSE_PORT,
        username=config.CLICKHOUSE_USER,
        password=config.CLICKHOUSE_PASSWORD,
        database=config.CLICKHOUSE_DATABASE,
        secure=config.CLICKHOUSE_SECURE,
        verify=config.CLICKHOUSE_VERIFY,
        connect_timeout=config.CLICKHOUSE_CONNECT_TIMEOUT,
        send_receive_timeout=config.CLICKHOUSE_SEND_RECEIVE_TIMEOUT,
    )


def validate_select_sql(sql: str) -> exp.Expression:
    """Parse as ClickHouse and require a single SELECT / WITH…SELECT."""
    tree = sqlglot.parse_one(sql, read=_DIALECT)
    if not isinstance(tree, (exp.Select, exp.With)):
        raise ValueError("Only a single SELECT (or WITH … SELECT) is allowed")
    # Reject obvious mutations if nested
    sql_upper = sql.strip().upper()
    for banned in ("INSERT ", "ALTER ", "DROP ", "TRUNCATE ", "DELETE ", "CREATE ", "RENAME "):
        if banned in sql_upper:
            raise ValueError(f"Disallowed statement keyword: {banned.strip()}")
    return tree


def run_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Validate then execute; return (columns, rows)."""
    validate_select_sql(sql)
    client = get_client()
    try:
        result = client.query(sql)
        columns = list(result.column_names)
        rows = [list(row) for row in result.result_rows]
        return columns, rows
    finally:
        client.close()
