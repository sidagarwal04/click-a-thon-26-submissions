#!/usr/bin/env python3
"""Reproducible loader: sample data (or a NEW slice) into the team ClickHouse `rca`.

Reads credentials from the repo .env (never printed, never committed). Same DDL as CONTRACTS §1.

Usage:
  python scripts/load_clickhouse.py                 # (re)load the sample data via server-side url()
  python scripts/load_clickhouse.py --verify-only   # just run the integrity asserts on what's loaded
  python scripts/load_clickhouse.py --parquet data/unseen.parquet [--database rca_unseen]
                                                    # Day-2 unseen slice from a LOCAL file (F2:
                                                    # load into a separate DB so it can't corrupt
                                                    # the historical baselines)
"""
import argparse, sys, clickhouse_connect

SAMPLE = "https://raw.githubusercontent.com/sidagarwal04/click-a-thon-2026/main/InMobi/data"
MEDIA  = "https://media.githubusercontent.com/media/sidagarwal04/click-a-thon-2026/main/InMobi/data"
DIMS = {
    "apps":        "app_id String, category String, publisher_tier String",
    "advertisers": "advertiser_id String, vertical String, campaign_type String",
    "geo_device":  "geo_device_id String, region String, country String, device_model String, os_version String",
}

def env(path=".env"):
    cfg = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1); cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg

def connect(cfg):
    return clickhouse_connect.get_client(
        host=cfg["CLICKHOUSE_HOST"], port=int(cfg.get("CLICKHOUSE_PORT", 8443)),
        username=cfg.get("CLICKHOUSE_USER", "default"), password=cfg["CLICKHOUSE_PASSWORD"],
        secure=str(cfg.get("CLICKHOUSE_SECURE", "true")).lower() in ("1", "true", "yes"))

# The denormalized read table the dashboard's Metrics page queries (ui/data.py table()).
# It used to exist only in `rca`, created by hand and recorded nowhere — so loading the unseen
# slice into a fresh database produced ad_events + dims but NO events, and every chart broke.
# Building it here makes a new dataset self-sufficient. MergeTree becomes SharedMergeTree
# automatically on ClickHouse Cloud.
DDL_FLAT = """CREATE TABLE {db}.events
  (event_time DateTime CODEC(Delta(4), ZSTD(1)),
   ad_format LowCardinality(String), app_id LowCardinality(String),
   category LowCardinality(String), publisher_tier LowCardinality(String),
   advertiser_id LowCardinality(String), vertical LowCardinality(String),
   campaign_type LowCardinality(String), geo_device_id LowCardinality(String),
   region LowCardinality(String), country LowCardinality(String),
   device_model LowCardinality(String), os_version LowCardinality(String),
   is_filled UInt8, is_impression UInt8, is_click UInt8, revenue Float64 CODEC(ZSTD(3)))
  ENGINE = MergeTree
  PARTITION BY toYYYYMM(event_time)
  ORDER BY (toStartOfHour(event_time), ad_format, app_id, event_time)"""

FLAT_INSERT = """INSERT INTO {db}.events SELECT
  e.event_time, e.ad_format, e.app_id, a.category, a.publisher_tier,
  e.advertiser_id, ifNull(ad.vertical, ''), ifNull(ad.campaign_type, ''),
  e.geo_device_id, g.region, g.country, g.device_model, g.os_version,
  e.is_filled, e.is_impression, e.is_click, e.revenue
FROM {db}.ad_events e
LEFT JOIN {db}.geo_device  g  ON e.geo_device_id = g.geo_device_id
LEFT JOIN {db}.apps        a  ON e.app_id        = a.app_id
LEFT JOIN {db}.advertisers ad ON e.advertiser_id = ad.advertiser_id"""

DDL_FACT = """CREATE TABLE {db}.ad_events
  (event_time DateTime, app_id String, geo_device_id String, advertiser_id String,
   ad_format String, is_filled UInt8, is_impression UInt8, is_click UInt8, revenue Float64)
  ENGINE = MergeTree ORDER BY (event_time, app_id)"""

def load(client, db, parquet):
    client.command(f"CREATE DATABASE IF NOT EXISTS {db}")
    client.command(f"DROP TABLE IF EXISTS {db}.ad_events")
    client.command(DDL_FACT.format(db=db))
    cols = ("toDateTime(assumeNotNull(event_time)), assumeNotNull(app_id), assumeNotNull(geo_device_id), "
            "assumeNotNull(advertiser_id), assumeNotNull(ad_format), assumeNotNull(is_filled), "
            "assumeNotNull(is_impression), assumeNotNull(is_click), assumeNotNull(revenue)")
    if parquet.startswith("http"):
        print(f"loading ad_events (server-side url) from {parquet} ...")
        client.command(f"INSERT INTO {db}.ad_events SELECT {cols} FROM url('{parquet}', Parquet)")
    else:  # local file (e.g. the unseen slice the judges hand us) -> push via arrow
        print(f"loading ad_events from local {parquet} ...")
        import pyarrow.parquet as pq
        client.insert_arrow(f"{db}.ad_events", pq.read_table(parquet))
    for name, schema in DIMS.items():
        key = schema.split()[0]
        client.command(f"DROP TABLE IF EXISTS {db}.{name}")
        client.command(f"CREATE TABLE {db}.{name} ({schema}) ENGINE = MergeTree ORDER BY {key}")
        client.command(f"INSERT INTO {db}.{name} SELECT * FROM "
                       f"url('{MEDIA}/{name}.csv', CSVWithNames, '{schema.replace('String','Nullable(String)')}')")
    # AFTER the dims — the flat table joins them, so building it earlier would blank
    # every region/category/vertical.
    print("building denormalized events table ...")
    client.command(f"DROP TABLE IF EXISTS {db}.events")
    client.command(DDL_FLAT.format(db=db))
    client.command(FLAT_INSERT.format(db=db))
    print("load complete.")

def verify(client, db):
    print(f"=== integrity checks on {db} ===")
    n = client.query(f"SELECT count() FROM {db}.ad_events").result_rows[0][0]
    ctr = client.query(f"SELECT round(sum(is_click)/sum(is_impression),4) FROM {db}.ad_events").result_rows[0][0]
    # funnel must be monotone consistent; unfilled rows carry no advertiser
    bad = client.query(f"""SELECT
        countIf(is_impression>is_filled), countIf(is_click>is_impression),
        countIf(is_filled=0 AND advertiser_id!='') FROM {db}.ad_events""").result_rows[0]
    dims = client.query(f"SELECT (SELECT count() FROM {db}.apps),(SELECT count() FROM {db}.advertisers),(SELECT count() FROM {db}.geo_device)").result_rows[0]
    ok = True
    def check(label, cond, got):
        nonlocal ok
        flag = "OK " if cond else "FAIL"; ok = ok and cond
        print(f"  [{flag}] {label}: {got}")
    check("rows", n > 0, f"{n:,}")
    check("CTR = clicks/impressions (~0.0109, not 0.0083)", 0.010 < ctr < 0.012, ctr)
    check("funnel consistent (imp<=fill, click<=imp)", bad[0] == 0 and bad[1] == 0, f"imp>fill={bad[0]}, click>imp={bad[1]}")
    check("advertiser_id empty only on unfilled", bad[2] == 0, f"filled-yet-blank={bad[2]}")
    check("dims present", all(dims), f"apps={dims[0]} adv={dims[1]} geo={dims[2]}")
    # the dashboard reads {db}.events, not ad_events — if it is missing or short, every
    # chart on the Metrics page is wrong or blank
    try:
        flat = client.query(f"SELECT count(), countIf(region='') FROM {db}.events").result_rows[0]
    except Exception:
        flat = (0, 0)
    check("events (flat read table) matches ad_events", flat[0] == n, f"{flat[0]:,} vs {n:,}")
    check("events dims joined (region non-empty)", flat[0] > 0 and flat[1] == 0, f"blank region={flat[1]:,}")
    if not ok:
        print("INTEGRITY FAILED — do not trust analysis on this load.", file=sys.stderr); sys.exit(1)
    print("all integrity checks passed.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", default=None,
                    help="target database (default: CLICKHOUSE_DATABASE from .env)")
    ap.add_argument("--parquet", default=SAMPLE + "/ad_events.parquet",
                    help="parquet URL (server-side) or local path (arrow upload)")
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()
    cfg = env()
    a.database = a.database or cfg.get("CLICKHOUSE_DATABASE", "rca")
    client = connect(cfg)
    print(f"connected: {client.server_version}  ->  database {a.database}")
    if not a.verify_only:
        load(client, a.database, a.parquet)
    verify(client, a.database)
