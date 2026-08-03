"""Proves perf_tool works end-to-end against real ClickHouse Cloud data.

Tests two candidate ordering keys for `destination_card_clicked` against the legacy
baseline (`ORDER BY (id, timestamp, user_id)`) that's actually in production
(Atlys/data/ddl.sql) — using time-filter and segment-groupby queries, the two access
patterns `base_context.md` says the funnel is always analysed by.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from perf_tool import Candidate, run_perf_test

COLUMNS_DDL = """
    id UUID,
    timestamp DateTime,
    user_id String,
    application_id Nullable(String),
    device_type Nullable(String),
    os Nullable(String),
    geoip_country_code Nullable(String),
    destination Nullable(String),
    visa_type Nullable(String),
    card_type Nullable(String),
    funnel_type Nullable(String),
    flow Nullable(String)
"""

CANDIDATES = [
    Candidate(label="time_user", ordering_key="(timestamp, user_id)"),
    Candidate(label="time_dest_device", ordering_key="(timestamp, destination, device_type)"),
]

QUERY_PATTERNS = [
    "SELECT count() FROM {table} WHERE timestamp >= '2026-04-01' AND timestamp < '2026-05-01'",
    "SELECT destination, count() FROM {table} "
    "WHERE timestamp >= '2026-04-01' AND timestamp < '2026-05-01' "
    "GROUP BY destination ORDER BY count() DESC LIMIT 10",
    "SELECT device_type, uniqExact(user_id) FROM {table} "
    "WHERE timestamp >= '2026-04-01' AND timestamp < '2026-05-01' "
    "GROUP BY device_type",
]


def main():
    report = run_perf_test(
        table_name="destination_card_clicked_smoketest",
        columns_ddl=COLUMNS_DDL,
        candidates=CANDIDATES,
        sample_source="atlys.destination_card_clicked",
        query_patterns=QUERY_PATTERNS,
        sample_limit=1_000_000,  # full table — it's only 1M rows
        repeats=3,
    )
    print(report.to_json())
    print()
    print(f"winner: {report.winner}  (speedup vs {report.baseline_label}: {report.speedup_vs_baseline}x)")


if __name__ == "__main__":
    main()
