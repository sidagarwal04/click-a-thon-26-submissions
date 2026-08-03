"""
Instrumented ClickHouse client.

Wraps clickhouse-connect so every insert / query / command is automatically
traced and timed into ClickStack. New analysis code just does:

    from ingester import get_clickhouse
    ch = get_clickhouse()
    rows = ch.query_rows("SELECT count() FROM raw_events FINAL")

and the call shows up in HyperDX with latency and row counts.
"""

import logging
import time

import clickhouse_connect

from . import telemetry as t
from .config import get_settings

log = logging.getLogger(__name__)


class ClickHouseClient:
    """A thin, observable wrapper around a clickhouse-connect client."""

    def __init__(self, client=None, settings=None):
        t.init_telemetry()
        self._settings = settings or get_settings()
        self._client = client if client is not None else self._connect()

    def _connect(self):
        cfg = self._settings.clickhouse
        client = clickhouse_connect.get_client(
            host=cfg.host,
            port=cfg.port,
            username=cfg.username,
            password=cfg.password,
            database=cfg.database,
            secure=cfg.secure,
        )
        client.ping()
        log.info(
            "Connected to ClickHouse %s:%s db=%s secure=%s",
            cfg.host,
            cfg.port,
            cfg.database,
            cfg.secure,
        )
        return client

    @property
    def raw(self):
        """The underlying clickhouse-connect client, for anything not wrapped here."""
        return self._client

    def __getattr__(self, name):
        # Delegate anything not wrapped here to the real client, so this is a
        # drop-in replacement (ch.query_df, ch.query_np, ch.ping, ...).
        client = self.__dict__.get("_client")
        if client is None:
            raise AttributeError(name)
        return getattr(client, name)

    def insert(self, table, rows, column_names):
        """Batch-insert rows. Returns the number of rows inserted."""
        n = len(rows)
        start = time.perf_counter()
        ok = True
        with t.span(
            "clickhouse.insert",
            {"db.system": "clickhouse", "db.operation": "insert",
             "db.sql.table": table, "db.rows": n},
        ) as sp:
            try:
                self._client.insert(table, rows, column_names=column_names)
            except Exception as exc:
                ok = False
                if sp is not None:
                    sp.record_exception(exc)
                t.errors.add(1, {"op": "insert", "table": table})
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000.0
                t.insert_duration.record(duration_ms, {"table": table, "ok": ok})
                if ok:
                    t.insert_rows.add(n, {"table": table})
                    t.insert_batches.add(1, {"table": table})
        log.debug("Inserted %d rows into %s in %.1fms", n, table, duration_ms)
        return n

    def query(self, sql, parameters=None, *, table=""):
        """Run a SELECT and return the clickhouse-connect QueryResult."""
        start = time.perf_counter()
        ok = True
        result = None
        with t.span(
            "clickhouse.query",
            {"db.system": "clickhouse", "db.operation": "select",
             "db.statement": sql[:512], "db.sql.table": table},
        ) as sp:
            try:
                result = self._client.query(sql, parameters=parameters)
            except Exception as exc:
                ok = False
                if sp is not None:
                    sp.record_exception(exc)
                t.errors.add(1, {"op": "query", "table": table})
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000.0
                t.query_duration.record(duration_ms, {"table": table, "ok": ok})
                if ok and result is not None:
                    n = len(result.result_rows)
                    t.query_rows.add(n, {"table": table})
                    if sp is not None:
                        sp.set_attribute("db.rows", n)
        return result

    def query_rows(self, sql, parameters=None, *, table=""):
        """Convenience: run a SELECT and return just the list of result rows."""
        return self.query(sql, parameters=parameters, table=table).result_rows

    def command(self, statement):
        """Run a DDL/DML command (CREATE, ALTER, OPTIMIZE, ...)."""
        start = time.perf_counter()
        with t.span(
            "clickhouse.command",
            {"db.system": "clickhouse", "db.operation": "command",
             "db.statement": statement[:512]},
        ) as sp:
            try:
                return self._client.command(statement)
            except Exception as exc:
                if sp is not None:
                    sp.record_exception(exc)
                t.errors.add(1, {"op": "command"})
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000.0
                t.query_duration.record(duration_ms, {"op": "command"})


def get_clickhouse(settings=None) -> ClickHouseClient:
    """Return a ready, instrumented ClickHouse client (initialises telemetry)."""
    t.init_telemetry()
    return ClickHouseClient(settings=settings)
