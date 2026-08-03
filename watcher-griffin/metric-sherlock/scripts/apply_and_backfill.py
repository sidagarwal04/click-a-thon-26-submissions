"""Applies dictionaries.sql + rollups.sql to the live ClickHouse Cloud instance,
then backfills the 12 hourly_* rollup tables from ad_events (idempotent — skips
any table that already has rows).

Why this exists instead of `clickhouse-client --queries-file`: this repo's
ClickHouse MCP connection is configured read-only (CLICKHOUSE_ALLOW_WRITE_ACCESS
unset), so DDL/DML must go through a direct client instead. Reuses the exact
SELECT bodies from rollups.sql's materialized views for the backfill, since
those views only fire on rows inserted after their own creation.

Usage: .venv/Scripts/python.exe scripts/apply_and_backfill.py [dictionaries|rollups|backfill|reconcile|all]
"""

import os
import re
import sys
import time

import clickhouse_connect
from dotenv import load_dotenv

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO, "utils", ".env"))


def get_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database=os.environ["CLICKHOUSE_DATABASE"],
        secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
    )


def split_statements(sql_text):
    lines = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(re.sub(r"--.*$", "", line))
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def run_file(client, path):
    with open(path, "r", encoding="utf-8") as f:
        statements = split_statements(f.read())
    for i, stmt in enumerate(statements, 1):
        label = stmt.splitlines()[0][:80]
        try:
            client.command(stmt)
            print(f"  [{i}/{len(statements)}] OK   {label}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  [{i}/{len(statements)}] SKIP (exists) {label}")
            else:
                raise


# Same SELECT bodies as the MVs in rollups.sql -- reused verbatim.
BACKFILLS = {
    "hourly_overall": """
        SELECT toStartOfHour(event_time) AS hour,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour""",
    "hourly_by_app": """
        SELECT toStartOfHour(event_time) AS hour, app_id,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, app_id""",
    "hourly_by_advertiser": """
        SELECT toStartOfHour(event_time) AS hour, advertiser_id,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, advertiser_id""",
    "hourly_by_format": """
        SELECT toStartOfHour(event_time) AS hour, ad_format,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, ad_format""",
    "hourly_by_region": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGet('geo_device_dict', 'region', geo_device_id) AS region,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, region""",
    "hourly_by_country": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGet('geo_device_dict', 'country', geo_device_id) AS country,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, country""",
    "hourly_by_device_model": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGet('geo_device_dict', 'device_model', geo_device_id) AS device_model,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, device_model""",
    "hourly_by_os_version": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGet('geo_device_dict', 'os_version', geo_device_id) AS os_version,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, os_version""",
    "hourly_by_category": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGet('apps_dict', 'category', app_id) AS category,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, category""",
    "hourly_by_publisher_tier": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGet('apps_dict', 'publisher_tier', app_id) AS publisher_tier,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, publisher_tier""",
    "hourly_by_vertical": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGetOrDefault('advertisers_dict', 'vertical', advertiser_id, '') AS vertical,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, vertical""",
    "hourly_by_campaign_type": """
        SELECT toStartOfHour(event_time) AS hour,
               dictGetOrDefault('advertisers_dict', 'campaign_type', advertiser_id, '') AS campaign_type,
               count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
               sum(is_click) AS clicks, sum(revenue) AS revenue
        FROM ad_events GROUP BY hour, campaign_type""",
}


def backfill(client):
    for table, select_body in BACKFILLS.items():
        existing = int(client.command(f"SELECT count() FROM {table}"))
        if existing > 0:
            print(f"{table}: SKIP (already has {existing} rows)")
            continue
        t0 = time.time()
        client.command(f"INSERT INTO {table} {select_body.strip()}")
        after = client.command(f"SELECT count() FROM {table}")
        print(f"{table}: backfilled {after} rows in {time.time()-t0:.1f}s")


def reconcile(client):
    overall = client.query(
        "SELECT count() AS hours, sum(requests) AS requests, sum(fills) AS fills, sum(revenue) AS revenue "
        "FROM hourly_overall"
    ).first_row
    raw = client.query(
        "SELECT count() AS requests, sum(is_filled) AS fills, sum(revenue) AS revenue FROM ad_events"
    ).first_row
    print(f"hourly_overall: {overall[0]} hours, requests={overall[1]}, fills={overall[2]}, revenue={overall[3]}")
    print(f"ad_events:                requests={raw[0]}, fills={raw[1]}, revenue={raw[2]}")
    ok = (overall[1], overall[2], str(overall[3])) == (raw[0], raw[1], str(raw[2]))
    print("RECONCILED OK" if ok else "MISMATCH — investigate before trusting rollups")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    client = get_client()
    print("Connected. Server:", client.server_version)

    if step in ("dictionaries", "all"):
        print("\n=== dictionaries.sql ===")
        run_file(client, os.path.join(REPO, "clickhouse", "dictionaries.sql"))

    if step in ("rollups", "all"):
        print("\n=== rollups.sql ===")
        run_file(client, os.path.join(REPO, "clickhouse", "rollups.sql"))

    if step in ("backfill", "all"):
        print("\n=== backfill ===")
        backfill(client)

    if step in ("reconcile", "all"):
        print("\n=== reconcile ===")
        reconcile(client)

    print("\nDone.")
