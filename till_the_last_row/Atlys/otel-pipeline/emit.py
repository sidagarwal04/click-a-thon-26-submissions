#!/usr/bin/env python3
"""
emit.py - Atlys Parquet -> OTEL Collector -> ClickHouse

Reads every Parquet file from Atlys/data/, converts each row to an OTLP
LogRecord (via Python logging + OTELHandler), tags the batch with resource
attribute  atlys.table=<table_name>  so the collector routing connector
forwards it to the correct ClickHouse table.

Usage:
    docker compose up                             # start collector first
    pip install -r requirements.txt
    python emit.py                                # all 8 tables
    python emit.py --table purchase_completed     # single table
    python emit.py --batch 50000 --endpoint localhost:4317
"""

from __future__ import annotations

import argparse
import decimal
import json
import logging
import time
from pathlib import Path

import pyarrow.parquet as pq
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

# ── table map: parquet filename stem -> ClickHouse table name ─────────────────
TABLE_MAP: dict[str, str] = {
    "destination_card_clicked": "destination_card_clicked",
    "application_started":      "application_started",
    "document_uploaded":        "document_uploaded",
    "purchase_completed":       "purchase_completed",
    "search_typed":             "search_typed",
    "landing_page_scrolled":    "landing_page_scrolled",
    "auth_completed":           "auth_completed",
    "pay_now_clicked":          "pay_now_clicked",
}


def _scalar(val: object) -> object:
    """Convert a pyarrow scalar to a JSON-serialisable Python primitive."""
    if val is None:
        return None
    if isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, decimal.Decimal):
        return float(val)
    if hasattr(val, "isoformat"):  # datetime / date
        return val.isoformat()
    return str(val)


def read_parquet(path: Path) -> list[dict]:
    """Return rows as a list of dicts with Python-native values."""
    table = pq.read_table(str(path))
    cols = table.schema.names
    return [
        {col: _scalar(table[col][i].as_py()) for col in cols}
        for i in range(table.num_rows)
    ]


def emit_table(
    table_name: str,
    rows: list[dict],
    endpoint: str,
    batch_size: int,
) -> None:
    """
    Send all rows as OTLP LogRecords to the collector.

    Each SDK Resource is tagged:
        atlys.table  = table_name      <- routing connector key
        service.name = atlys-parquet-emitter

    Row fields are passed as LogRecord extra attributes, which the
    ClickHouse exporter writes directly to the table columns.

    Per insert-batch-size (CRITICAL): batch_size defaults to 10_000.
    """
    resource = Resource(attributes={
        "atlys.table":  table_name,
        "service.name": "atlys-parquet-emitter",
    })

    exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(
        BatchLogRecordProcessor(exporter, max_export_batch_size=batch_size)
    )
    set_logger_provider(provider)

    # Attach the OTEL handler to a stdlib logger for this table
    otel_handler = LoggingHandler(level=logging.INFO, logger_provider=provider)
    logger = logging.getLogger(f"atlys.emitter.{table_name}")
    logger.setLevel(logging.INFO)
    logger.addHandler(otel_handler)
    # Prevent log records propagating to root (avoid duplicate console output)
    logger.propagate = False

    total = len(rows)
    for i, row in enumerate(rows, start=1):
        # Pass row fields as `extra` — OTEL handler adds them as log attributes,
        # which the ClickHouse exporter maps to table columns.
        logger.info(
            json.dumps({"event": table_name}, default=str),
            extra={k: v for k, v in row.items() if v is not None},
        )
        if i % batch_size == 0:
            print(f"  [{table_name}] {i:,}/{total:,} emitted")

    provider.force_flush(timeout_millis=60_000)
    provider.shutdown()
    print(f"  [{table_name}] complete — {total:,} rows sent")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atlys Parquet -> OTEL Collector -> ClickHouse"
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).parent.parent / "data"),
        help="Path to Atlys/data/ directory (default: ../data)",
    )
    parser.add_argument(
        "--endpoint",
        default="localhost:4317",
        help="OTEL Collector gRPC endpoint (default: localhost:4317)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=10_000,
        help="Rows per OTLP batch flush (default: 10000, per insert-batch-size rule)",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Emit only this table name (default: all tables)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: data directory not found: {data_dir}")
        raise SystemExit(1)

    targets = {
        stem: tbl
        for stem, tbl in TABLE_MAP.items()
        if args.table is None or stem == args.table
    }
    if not targets:
        print(f"ERROR: unknown table '{args.table}'. Valid: {list(TABLE_MAP)}")
        raise SystemExit(1)

    print(f"Endpoint  : {args.endpoint}")
    print(f"Data dir  : {data_dir}")
    print(f"Batch size: {args.batch:,} rows  (per insert-batch-size rule: 10K-100K)")
    print(f"Tables    : {', '.join(targets)}")
    print()

    for stem, table_name in targets.items():
        parquet_path = data_dir / f"{stem}.parquet"
        if not parquet_path.exists():
            print(f"  [{stem}] SKIP — file not found: {parquet_path}")
            continue

        print(f"  [{stem}] reading {parquet_path.name} ...")
        rows = read_parquet(parquet_path)
        print(f"  [{stem}] {len(rows):,} rows loaded — emitting ...")
        emit_table(table_name, rows, args.endpoint, args.batch)
        print()

    print("All done.")


if __name__ == "__main__":
    main()
