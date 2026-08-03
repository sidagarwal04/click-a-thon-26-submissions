#!/usr/bin/env python3
"""
parquet_reader.py — reads a single Parquet file and emits NDJSON to stdout.

Each line written is:
    {"payload": {"event": "<EVENT_NAME>", <all other columns...>}}

Environment variables:
    PARQUET_FILE  — absolute path to the .parquet file (required)
    EVENT_NAME    — value for the "event" field (defaults to stem of PARQUET_FILE)
"""

import json
import math
import os
import sys

import pyarrow.parquet as pq


def _safe(val):
    """Convert a pyarrow scalar value to a JSON-serialisable Python type."""
    if val is None:
        return None
    # Handle pyarrow scalars by converting to Python native first
    if hasattr(val, "as_py"):
        val = val.as_py()
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, (int, str, bool)):
        return val
    # Fallback: stringify anything else (dates, decimals, etc.)
    return str(val)


def main():
    parquet_file = os.environ.get("PARQUET_FILE")
    if not parquet_file:
        print("ERROR: PARQUET_FILE env var not set", file=sys.stderr)
        sys.exit(1)

    event_name = os.environ.get("EVENT_NAME") or os.path.splitext(os.path.basename(parquet_file))[0]

    try:
        table = pq.read_table(parquet_file)
    except Exception as exc:
        print(f"ERROR reading {parquet_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    columns = table.column_names
    rows_written = 0

    for batch in table.to_batches():
        col_arrays = {col: batch.column(col) for col in columns}
        for i in range(batch.num_rows):
            row = {"event": event_name}
            for col in columns:
                row[col] = _safe(col_arrays[col][i])
            line = json.dumps({"payload": row}, ensure_ascii=False)
            print(line, flush=True)
            rows_written += 1

    print(f"INFO: wrote {rows_written} rows from {parquet_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
