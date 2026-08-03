"""ClickHouse Cloud client helpers."""

from __future__ import annotations

import threading
import time
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from clickathon.config import Settings, get_settings
from clickathon.telemetry import clickhouse_query_span, finish_query_span, flush_telemetry

_local = threading.local()


def get_client(settings: Settings | None = None) -> Client:
    """Return a per-thread client (ClickHouse sessions are not concurrent-safe)."""
    s = settings or get_settings()
    key = (
        s.clickhouse_host,
        s.clickhouse_port,
        s.clickhouse_user,
        s.clickhouse_rca_database,
        s.clickhouse_secure,
    )
    cached = getattr(_local, "client", None)
    cached_key = getattr(_local, "client_key", None)
    if cached is not None and cached_key == key:
        return cached
    client = clickhouse_connect.get_client(
        host=s.clickhouse_host,
        port=s.clickhouse_port,
        username=s.clickhouse_user,
        password=s.clickhouse_password,
        secure=s.clickhouse_secure,
        database=s.clickhouse_rca_database,
    )
    _local.client = client
    _local.client_key = key
    return client


def query_rows(sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    s = get_settings()
    client = get_client(s)
    params = parameters or {}
    t0 = time.perf_counter()
    with clickhouse_query_span(sql, parameters=params, database=s.clickhouse_rca_database) as span:
        try:
            result = client.query(sql, parameters=params)
            cols = result.column_names
            rows = [dict(zip(cols, row, strict=True)) for row in result.result_rows]
            finish_query_span(
                span,
                n_rows=len(rows),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            return rows
        except Exception as exc:
            finish_query_span(
                span,
                n_rows=0,
                duration_ms=(time.perf_counter() - t0) * 1000,
                error=str(exc),
            )
            flush_telemetry()
            raise


def query_one(sql: str, parameters: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = query_rows(sql, parameters)
    return rows[0] if rows else None


def command(sql: str) -> Any:
    """Run a DDL/DML command and log it to Langfuse as clickhouse.query."""
    s = get_settings()
    client = get_client(s)
    t0 = time.perf_counter()
    with clickhouse_query_span(sql, parameters={}, database=s.clickhouse_rca_database) as span:
        try:
            result = client.command(sql)
            finish_query_span(
                span,
                n_rows=None,
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
            return result
        except Exception as exc:
            finish_query_span(
                span,
                duration_ms=(time.perf_counter() - t0) * 1000,
                error=str(exc),
            )
            flush_telemetry()
            raise
