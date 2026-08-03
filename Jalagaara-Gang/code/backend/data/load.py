"""Lane A: load the four InMobi files into ClickHouse, then build enriched + rollup tables.

Usage:  python -m data.load
Expects schema.sql tables to be creatable from scratch. See prompts/01-data-clickhouse.md.
"""
from __future__ import annotations

import re

from pathlib import Path

from data.client import get_client

DATA_DIR = Path(__file__).resolve().parents[2] / "InMobi" / "data"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"

CSV_TABLES = {
    "apps_dim": "apps.csv",
    "advertisers_dim": "advertisers.csv",
    "geo_device_dim": "geo_device.csv",
}


BASE_TABLES = ("ad_events", "apps_dim", "advertisers_dim", "geo_device_dim")
DERIVED_TABLES = ("events_full", "hourly_summary")


def _statements(names: tuple[str, ...]) -> list[str]:
    # Strip full-line comments BEFORE splitting on ';' — comment lines here contain
    # semicolons of their own (e.g. "is_* as UInt8; revenue Float64; ..."), which would
    # otherwise be split into bogus fragments.
    # encoding pinned: the default is locale-dependent, so a schema.sql written on Windows
    # (cp1252) read fine on the host and blew up inside the Linux container.
    text = SCHEMA.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.strip().startswith("--")]
    cleaned = "\n".join(lines)
    raw = [s.strip() for s in cleaned.split(";") if s.strip()]
    # Word-boundary match: a plain substring test makes "EXISTS events_full" also select
    # events_full_unseen, so loading the dev tables would quietly create the unseen ones too.
    pattern = re.compile(r"EXISTS (?:%s)\b" % "|".join(re.escape(n) for n in names))
    return [s for s in raw if pattern.search(s)]


def run_base_schema(client) -> None:
    """Create the 4 raw tables only. Must run BEFORE loading data."""
    for statement in _statements(BASE_TABLES):
        client.command(statement)


def run_derived_schema(client) -> None:
    """Create events_full + hourly_summary. These are CREATE TABLE ... AS SELECT —
    a one-time snapshot, not a live view — so this MUST run AFTER the base tables are loaded."""
    for statement in _statements(DERIVED_TABLES):
        client.command(statement)


def load_ad_events(client) -> None:
    # ClickHouse Cloud's file() table function only reads the SERVER's local disk, which
    # can't see our machine at all. Stream the parquet bytes to the client library instead,
    # which uploads them over HTTP as a native ClickHouse INSERT.
    parquet_path = DATA_DIR / "ad_events.parquet"
    with open(parquet_path, "rb") as f:
        client.raw_insert("ad_events", insert_block=f, fmt="Parquet")


def load_csv(client, table: str, filename: str, data_dir: Path | None = None) -> None:
    """`data_dir` overrides the default slice — the unseen dims ship in their own folder."""
    csv_path = (data_dir or DATA_DIR) / filename
    with open(csv_path, "rb") as f:
        client.raw_insert(table, insert_block=f, fmt="CSVWithNames")


def sanity_check(client) -> None:
    row_count, min_time, max_time = client.query(
        "SELECT count(), min(event_time), max(event_time) FROM ad_events"
    ).result_rows[0]
    print(f"ad_events: {row_count:,} rows, {min_time} -> {max_time}")
    assert row_count == 9_000_000, f"expected 9,000,000 rows, got {row_count:,}"

    regions = [r[0] for r in client.query("SELECT DISTINCT region FROM events_full").result_rows]
    print(f"regions: {regions}")
    assert "NAM" in regions, "expected 'NAM' region, not found"
    assert "NA" not in regions, "'NA' present — should be 'NAM'"

    unfilled_advertiser = client.query(
        "SELECT count() FROM ad_events WHERE is_filled = 0 AND advertiser_id != ''"
    ).result_rows[0][0]
    print(f"unfilled rows with non-empty advertiser_id: {unfilled_advertiser} (expect 0)")
    assert unfilled_advertiser == 0

    print("All sanity checks passed.")


def main() -> None:
    client = get_client()

    print("Creating base tables (ad_events, apps_dim, advertisers_dim, geo_device_dim) ...")
    run_base_schema(client)

    print("Loading ad_events.parquet (9M rows) ...")
    load_ad_events(client)

    for table, filename in CSV_TABLES.items():
        print(f"Loading {filename} -> {table} ...")
        load_csv(client, table, filename)

    print("Creating events_full + hourly_summary (post-load snapshot) ...")
    run_derived_schema(client)

    print("Running sanity checks ...")
    sanity_check(client)


if __name__ == "__main__":
    main()
