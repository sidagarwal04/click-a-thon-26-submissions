#!/usr/bin/env python3
"""Load a dataset slice into ClickHouse.

Used both for the original data and for the unseen incident. The materialized
views are already in place, so anything inserted here rolls up automatically —
there is no backfill step on this path and nothing to remember to re-run.

SAFETY
------
The unseen slice is "a fresh slice of the same universe", which may or may not
overlap what is already loaded. Loading an overlapping range would double-count
those hours and quietly corrupt every baseline downstream. So the loader reports
the incoming range, compares it against what is already present, and refuses to
proceed on an overlap unless explicitly told to.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch import query  # noqa: E402

DIMENSION_FILES = {
    "apps.csv": "apps",
    "advertisers.csv": "advertisers",
    "geo_device.csv": "geo_device",
}
FACT_FILE = "ad_events.parquet"


def _curl_insert(path: Path, table: str, fmt: str) -> None:
    """Stream a file straight into ClickHouse over HTTP.

    Shelling out to curl rather than reading the file into Python keeps a
    100MB+ parquet off the heap and makes the upload restartable by hand.
    """
    import os
    from ch import _load_env
    _load_env()
    host = os.environ["CLICKHOUSE_HOST"]
    port = os.environ.get("CLICKHOUSE_PORT", "8443")
    user = os.environ.get("CLICKHOUSE_ADMIN_USER", "default")
    password = os.environ.get("CLICKHOUSE_ADMIN_PASSWORD", "")
    url = f"https://{host}:{port}/?query=INSERT+INTO+inmobi.{table}+FORMAT+{fmt}"

    result = subprocess.run(
        ["curl", "-sS", "--fail-with-body", "-u", f"{user}:{password}",
         url, "--data-binary", f"@{path}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"load failed for {path.name}: {result.stdout}{result.stderr}")


def existing_range() -> tuple[str | None, str | None, int]:
    row = query(
        "SELECT min(event_time), max(event_time), count() FROM inmobi.ad_events FORMAT TSV"
    ).strip().split("\t")
    if len(row) < 3 or row[2] == "0":
        return None, None, 0
    return row[0], row[1], int(row[2])


def parquet_range(path: Path) -> tuple[str, str, int]:
    # pyarrow.compute.min_max, not Python's builtins: iterating an Arrow column
    # yields TimestampScalar objects, which are not orderable, so min()/max()
    # raise TypeError. Caught on the real unseen dataset, because every
    # rehearsal ran against data already in ClickHouse and never touched this
    # path — the overlap guard it feeds is exactly what must not be skipped.
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    f = pq.ParquetFile(path)
    lo, hi = None, None
    for batch in f.iter_batches(columns=["event_time"], batch_size=500_000):
        mm = pc.min_max(batch.column(0)).as_py()
        b_lo, b_hi = mm["min"], mm["max"]
        lo = b_lo if lo is None else min(lo, b_lo)
        hi = b_hi if hi is None else max(hi, b_hi)
    return str(lo), str(hi), f.metadata.num_rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Load a dataset slice into ClickHouse.")
    ap.add_argument("data_dir", help="directory containing ad_events.parquet and/or the dimension CSVs")
    ap.add_argument("--allow-overlap", action="store_true",
                    help="load even if the incoming range overlaps existing data (double-counts)")
    ap.add_argument("--skip-dimensions", action="store_true",
                    help="fact table only; use when dimension tables are unchanged")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        sys.exit(f"not a directory: {data_dir}")

    before_lo, before_hi, before_n = existing_range()
    print(f"Already loaded: {before_n:,} rows"
          + (f"  ({before_lo} -> {before_hi})" if before_n else ""))

    fact = data_dir / FACT_FILE
    if fact.exists():
        lo, hi, n = parquet_range(fact)
        print(f"Incoming:       {n:,} rows  ({lo} -> {hi})")

        if before_n and not args.allow_overlap and lo <= (before_hi or ""):
            sys.exit(
                f"\nREFUSING TO LOAD — incoming data starts at {lo}, which is not after\n"
                f"the existing maximum of {before_hi}. Loading would double-count the\n"
                f"overlapping hours and corrupt every baseline computed from them.\n"
                f"Pass --allow-overlap only if you are certain this is a distinct slice."
            )

    if not args.skip_dimensions:
        for filename, table in DIMENSION_FILES.items():
            path = data_dir / filename
            if not path.exists():
                continue
            # Dimensions are reference data, not events: replacing is correct and
            # appending would create duplicate keys for the dictionaries to resolve.
            query(f"TRUNCATE TABLE inmobi.{table}")
            _curl_insert(path, table, "CSVWithNames")
            count = query(f"SELECT count() FROM inmobi.{table}").strip()
            print(f"  {table:<14} reloaded -> {int(count):,} rows")

        query("SYSTEM RELOAD DICTIONARIES")
        print("  dictionaries reloaded")

    if fact.exists():
        print(f"  loading {FACT_FILE} ...")
        _curl_insert(fact, "ad_events", "Parquet")

    after_lo, after_hi, after_n = existing_range()
    print(f"\nNow loaded:     {after_n:,} rows  ({after_lo} -> {after_hi})")
    print(f"Added:          {after_n - before_n:,} rows")

    # The MVs fire on insert, so the rollups should already agree with the raw
    # table. Checking here means a broken rollup surfaces at load time rather
    # than as a wrong number in the diagnosis.
    raw = query("SELECT count() FROM inmobi.ad_events").strip()
    rollup = query("SELECT sum(requests) FROM inmobi.events_hourly").strip()
    match = int(raw) == int(rollup)
    print(f"Rollup check:   raw={int(raw):,} rollup={int(rollup):,} "
          f"{'OK' if match else 'MISMATCH — do not trust results'}")
    if not match:
        sys.exit(1)


if __name__ == "__main__":
    main()
