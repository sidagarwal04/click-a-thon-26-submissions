#!/usr/bin/env python
"""Python mirror of ``load.sh`` — load the 8 funnel tables into ClickHouse.

Use this when the ``clickhouse-client`` binary is not installed (or you want a
pure-Python loader): it reads ``Atlys/.env`` (or the process environment) for
``CH_HOST``/``CH_USER``/``CH_PASSWORD``/``CH_SECURE``/``ATLYS_DB`` and bulk-loads
every ``*.parquet`` in this directory into database ``ATLYS_DB`` (default
``atlys``). Idempotent: ``CREATE TABLE IF NOT EXISTS`` via ``ddl.sql``, then
``INSERT`` — re-running re-inserts rows.

Usage:
    PYTHONPATH=Atlys python data/load_python.py
    # or with explicit env:
    CH_HOST=... CH_PASSWORD=... python data/load_python.py

Requires: clickhouse-connect, pyarrow  (dev tooling only — the service itself
needs neither).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pyarrow.parquet as pq

DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parent

# Let settings.py's dependency-free loader pick up Atlys/.env (no override).
sys.path.insert(0, str(ROOT))
from service.settings import Settings  # noqa: E402

DDL = DATA_DIR / "ddl.sql"
PARQUETS = [
    "destination_card_clicked", "application_started", "document_uploaded",
    "purchase_completed", "search_typed", "landing_page_scrolled",
    "auth_completed", "pay_now_clicked",
]


def _convert_table(tbl):
    """Convert a pyarrow table to column-oriented python lists.

    `id` (UUID-as-string) → uuid.UUID (with a defensive fallback: keep the raw
    string if it isn't UUID-shaped, mirroring ClickHouse's own ingest casting);
    `timestamp` (timestamp[ms]) → datetime. pyarrow's ``to_pylist()`` already
    yields python ``datetime`` objects for timestamp columns, so no extra
    conversion is needed there.
    """
    columns = []
    for name in tbl.column_names:
        col = tbl.column(name)
        if name == "id":
            out = []
            for v in col.to_pylist():
                if v is None:
                    out.append(None)
                else:
                    try:
                        out.append(uuid.UUID(v))
                    except (ValueError, AttributeError):
                        out.append(v)  # not UUID-shaped — let ClickHouse cast
            columns.append(out)
        else:
            columns.append(col.to_pylist())
    return tbl.column_names, columns


def main() -> int:
    settings = Settings()
    if not settings.ch_host:
        print("no CH_HOST configured — set it in Atlys/.env or the environment", file=sys.stderr)
        return 1

    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host=settings.ch_host, username=settings.ch_user, password=settings.ch_password or "",
        secure=settings.ch_secure, connect_timeout=10, send_receive_timeout=300,
    )
    db = settings.atlys_db
    client.command(f"CREATE DATABASE IF NOT EXISTS {db}")
    # Unqualified CREATE TABLE / INSERT below must target `db` — pin the
    # client's database now that it exists (same pattern as store.py).
    client.database = db
    # ddl.sql has one statement per table (no semicolons inside) — strip
    # comment lines first so the first chunk (comments + first CREATE TABLE)
    # doesn't get dropped by the `--` guard. ddl.sql uses plain CREATE TABLE,
    # so make it idempotent (IF NOT EXISTS) — a re-run must not crash on an
    # already-created table.
    clean_ddl = "\n".join(
        l for l in DDL.read_text().splitlines() if not l.strip().startswith("--")
    )
    for stmt in (clean_ddl + "\n").split(";"):
        stmt = stmt.strip()
        if stmt:
            stmt = stmt.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
            client.command(stmt)
    print(f"database {db} ready (ddl applied)")

    for table in PARQUETS:
        path = DATA_DIR / f"{table}.parquet"
        if not path.exists():
            print(f"  SKIP {table} (missing {path.name})")
            continue
        tbl = pq.read_table(path)
        names, columns = _convert_table(tbl)
        # insert in row-batches via column-oriented data (memory-friendly)
        n = tbl.num_rows
        batch = 50_000
        inserted = 0
        for start in range(0, n, batch):
            end = min(start + batch, n)
            chunk = [c[start:end] for c in columns]
            client.insert(table, chunk, column_names=names, column_oriented=True)
            inserted += end - start
        print(f"  {table}: {inserted:,} rows")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
