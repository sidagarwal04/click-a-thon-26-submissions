"""ClickHouse access. run_query returns rows AND the resolved SQL for queries[] traceability."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import clickhouse_connect

from config import CLICKHOUSE
from obs import langfuse

log = logging.getLogger(__name__)

_local = threading.local()


def get_client():
    """One memoized, pooled client PER THREAD, reused across queries on that thread.

    A clickhouse-connect Client cannot run two queries at once — the FastAPI sync endpoints run
    in a threadpool AND long jobs (seed_bundles, discover, mega, the stream replay) spin up their
    own background thread, so a single process-wide client (the old @lru_cache(maxsize=1)) throws
    "Attempt to execute concurrent queries within the same session" the moment two of those
    threads query at the same time — e.g. the dashboard's own health poll firing mid-sweep. One
    client per thread keeps the pooling benefit (no fresh TLS handshake per query within a thread)
    while removing the cross-thread collision entirely. Call get_client.cache_clear() to force the
    CURRENT thread to reconnect.

    autogenerate_session_id=False layers on top of that. Per-thread clients already avoid the
    collision, but the driver otherwise binds each client to its own generated session_id, so a
    process with many worker threads accumulates that many server-side sessions for no benefit —
    and any future code that does share a client across threads would resurrect the same error.
    Nothing here needs session state (no temporary tables, no session-scoped settings).
    Measured: 8 threads x 6 queries on ONE shared client gives 7 errors with a session bound and
    0 without.
    """
    client = getattr(_local, "client", None)
    if client is None:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE["host"],
            port=CLICKHOUSE["port"],
            username=CLICKHOUSE["username"],
            password=CLICKHOUSE["password"],
            database=CLICKHOUSE["database"],
            secure=True,
            autogenerate_session_id=False,
        )
        _local.client = client
    return client


def _clear_client_cache() -> None:
    _local.client = None


get_client.cache_clear = _clear_client_cache


def clickhouse_available() -> bool:
    """Cheap probe: does ClickHouse answer a trivial query?

    Lets the API fail soft (serve fixtures / an 'offline' signal) instead of 500-ing when the
    datastore is unreachable — the common case being CLICKHOUSE_HOST unset in a container, which
    otherwise defaults to localhost:8443 and refuses. On failure the memoized client is dropped,
    so a corrected .env reconnects on the next call without a process restart.
    """
    if not CLICKHOUSE["host"]:
        log.warning("CLICKHOUSE_HOST is unset - reporting the datastore offline")
        return False

    # Retried once, because the first failure is usually a COLD connection, not an outage:
    # ClickHouse Cloud suspends idle services, and a wake-up plus TLS handshake can exceed the
    # client's timeout. Declaring "offline" on a single cold miss is what made the dashboard
    # flip to sample data while the database was perfectly healthy.
    for attempt in (1, 2):
        try:
            get_client().command("SELECT 1")
            return True
        except Exception as exc:  # noqa: BLE001 - any connection/auth failure means "offline"
            # Drop the pooled client so the retry (and any later call) reconnects cleanly.
            get_client.cache_clear()
            if attempt == 2:
                # Logged, not swallowed: a silent probe failure is undiagnosable — the reason
                # "why is it offline?" had no answer anywhere in the logs.
                log.warning("ClickHouse probe failed twice, reporting offline: %s", exc)
    return False


def run_query(
    sql: str, params: dict[str, Any] | None = None, name: str = "clickhouse-query"
) -> dict[str, Any]:
    """Run parameterized SQL. Returns {rows, columns, resolved_sql, elapsed_ms}.

    resolved_sql is what belongs in EvidenceBundle.queries[].sql — the traceability record.
    Each call is wrapped in a Langfuse span (input=SQL, output=result summary); when Langfuse
    is enabled the returned dict also carries langfuse_span_id for EvidenceBundle.queries[].
    """
    params = params or {}
    lf = langfuse()
    # Span only inside an active trace: untraced callers (dev console, benchmarker) would
    # otherwise each mint a single-span orphan trace and bury real investigations in the list.
    if lf is None or lf.get_current_trace_id() is None:
        return _execute(sql, params)

    with lf.start_as_current_observation(name=name, as_type="span") as span:
        out = _execute(sql, params)
        span.update(
            input=out["resolved_sql"],
            output={
                "row_count": len(out["rows"]),
                "columns": out["columns"],
                "sample": out["rows"][:5],
            },
            metadata={"elapsed_ms": round(out["elapsed_ms"], 1)},
        )
        out["langfuse_span_id"] = span.id
    return out


def _execute(sql: str, params: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result = get_client().query(sql, parameters=params)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "rows": result.result_rows,
        "columns": result.column_names,
        "resolved_sql": _inline(sql, params),
        "elapsed_ms": elapsed_ms,
    }


def _inline(sql: str, params: dict[str, Any]) -> str:
    # Best-effort render of {name:Type} placeholders for logging only (never for execution).
    out = sql
    for key, value in params.items():
        out = out.replace(f"{{{key}:", f"/* {key}={value!r} */ {{{key}:")
    return out
