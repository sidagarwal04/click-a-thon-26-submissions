#!/usr/bin/env python3
"""Backfill atlys.activity_events from per-event tables (Instrumentation SAS shape).

DDL matches instrumentation_agent (payload JSON, DateTime64(3), ch_table).
Prefer Instrumentation MVs for feature events; this script backfills the 8
legacy funnel/engagement tables (and any extra --sources).

Usage:
    uv run python conversation_agent/scripts/build_activity_events.py
    uv run python conversation_agent/scripts/build_activity_events.py --sample 5000
    uv run python conversation_agent/scripts/build_activity_events.py --drop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as script without install path quirks
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from conversation_agent import config

# Envelope columns on activity_events (everything else → payload JSON)
ENVELOPE = frozenset(
    {
        "timestamp",
        "user_id",
        "application_id",
        "device_type",
        "os",
        "geoip_country_code",
        "destination",
    }
)

# Legacy source fact tables (not funnel_events / not activity_events)
SOURCE_TABLES = (
    "destination_card_clicked",
    "application_started",
    "document_uploaded",
    "purchase_completed",
    "search_typed",
    "landing_page_scrolled",
    "auth_completed",
    "pay_now_clicked",
)


def _client():
    import clickhouse_connect

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
        connect_timeout=60,
        send_receive_timeout=600,
    )


def _ddl(fqn: str) -> str:
    """Match instrumentation_agent.utils.clickhouse.build_create_activity_events_sql."""
    return f"""
CREATE TABLE IF NOT EXISTS {fqn}
(
    event_name LowCardinality(String),
    ch_table LowCardinality(String),
    timestamp DateTime64(3),
    user_id String,
    application_id String,
    device_type LowCardinality(String),
    os LowCardinality(String),
    geoip_country_code LowCardinality(String),
    destination LowCardinality(String),
    payload String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (toDate(timestamp), event_name, user_id)
SETTINGS index_granularity = 8192
""".strip()


def _table_columns(client, database: str, table: str) -> list[str]:
    rows = client.query(f"DESCRIBE TABLE `{database}`.`{table}`").result_rows
    return [r[0] for r in rows]


def _payload_sql(columns: list[str]) -> str:
    """JSON of all source columns (same idea as Instrumentation MV payload)."""
    if not columns:
        return "CAST('{}' AS String)"
    keys = ", ".join(f"'{c}'" for c in columns)
    vals = ", ".join(f"ifNull(toString(`{c}`), '')" for c in columns)
    return f"toJSONString(mapFromArrays([{keys}], [{vals}]))"


def _envelope_expr(col: str, columns: list[str]) -> str:
    if col not in columns:
        if col == "timestamp":
            return "toDateTime64(0, 3)"
        return "CAST('' AS String)"
    if col == "timestamp":
        return f"toDateTime64(`{col}`, 3)"
    return f"ifNull(toString(`{col}`), '')"


def _insert_sql(
    *,
    database: str,
    fqn: str,
    table: str,
    columns: list[str],
    sample: int | None,
) -> str:
    if "timestamp" not in columns or "user_id" not in columns:
        raise RuntimeError(f"{table} missing required column timestamp/user_id")

    payload = _payload_sql(columns)
    limit = f"\nLIMIT {int(sample)}" if sample and sample > 0 else ""
    return f"""
INSERT INTO {fqn}
(
    event_name, ch_table, timestamp, user_id, application_id,
    device_type, os, geoip_country_code, destination, payload
)
SELECT
    '{table}' AS event_name,
    '{table}' AS ch_table,
    {_envelope_expr("timestamp", columns)} AS timestamp,
    {_envelope_expr("user_id", columns)} AS user_id,
    {_envelope_expr("application_id", columns)} AS application_id,
    {_envelope_expr("device_type", columns)} AS device_type,
    {_envelope_expr("os", columns)} AS os,
    {_envelope_expr("geoip_country_code", columns)} AS geoip_country_code,
    {_envelope_expr("destination", columns)} AS destination,
    {payload} AS payload
FROM `{database}`.`{table}`
{limit}
""".strip()


def _resolve_sources(client, database: str, extra: list[str]) -> list[str]:
    sources = list(SOURCE_TABLES) + [s for s in extra if s and s not in SOURCE_TABLES]
    existing = []
    for src in sources:
        try:
            _table_columns(client, database, src)
            existing.append(src)
        except Exception as exc:  # noqa: BLE001
            print(f"  skip {src}: {exc}")
    return existing


def build(
    *,
    drop: bool = False,
    sample: int | None = None,
    extra_sources: list[str] | None = None,
) -> dict:
    database = config.CLICKHOUSE_DATABASE
    fqn = config.activity_table_fqn()

    client = _client()
    try:
        if drop:
            client.command(f"DROP TABLE IF EXISTS {fqn}")
            print(f"Dropped {fqn}")

        client.command(_ddl(fqn))
        print(f"Ensured {fqn} (Instrumentation SAS: payload + DateTime64)")

        client.command(f"TRUNCATE TABLE IF EXISTS {fqn}")
        print(f"Truncated {fqn}")

        sources = _resolve_sources(client, database, extra_sources or [])
        totals: dict[str, int] = {}
        for src in sources:
            cols = _table_columns(client, database, src)
            sql = _insert_sql(
                database=database,
                fqn=fqn,
                table=src,
                columns=cols,
                sample=sample,
            )
            print(f"Inserting from {src}…")
            client.command(sql)
            n = client.query(
                f"SELECT count() FROM {fqn} WHERE event_name = {{n:String}}",
                parameters={"n": src},
            ).first_item
            count = int(n["count()"] if isinstance(n, dict) else n)
            totals[src] = count
            print(f"  → {count:,} rows")

        total = client.query(f"SELECT count() FROM {fqn}").first_item
        total_n = int(total["count()"] if isinstance(total, dict) else total)
        return {
            "table": fqn,
            "sample_per_table": sample,
            "by_event": totals,
            "total_rows": total_n,
        }
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill activity_events (Instrumentation SAS shape) from "
            "per-event ClickHouse tables"
        )
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="DROP TABLE before CREATE (needed to migrate off event_info DDL)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Limit rows per source table (for a quick sample load)",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Extra per-event table to include (repeatable), e.g. express_checkout_shown",
    )
    args = parser.parse_args()
    result = build(drop=args.drop, sample=args.sample, extra_sources=args.source)
    print(result)


if __name__ == "__main__":
    main()
