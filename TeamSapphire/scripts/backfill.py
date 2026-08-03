#!/usr/bin/env python3
"""One-shot historical backfill of the rollup tables, with verification.

WHY THIS HAS A GUARD
--------------------
The materialized views are insert triggers: they only see rows written to
inmobi.ad_events *after* the MV was created. Historical rows therefore need an
explicit INSERT INTO <rollup> SELECT FROM ad_events.

That backfill is NOT idempotent. Running it twice double-counts every row, and
the result looks entirely plausible — totals just come out 2x. This exact
mistake cost a real debugging session during prep, so the script refuses to run
against a non-empty target unless --force is passed.

Note the backfill writes directly to the rollup tables, which does *not* fire
the MVs (they watch ad_events, not the rollups). So there is no double-count
from the MV path, only from re-running this script.

Usage:
    backfill.py            backfill if targets are empty, then verify
    backfill.py --verify   verification only, no writes
    backfill.py --force    backfill even if targets are non-empty (dangerous)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch import query  # noqa: E402

# The dimension fan-out. Kept identical to the MV body in sql/02_rollups.sql —
# if you change one, change both, or history and live data will disagree.
DIM_ARRAY = """[
    ('ad_format',      CAST(ad_format AS String)),
    ('region',         dictGetString('inmobi.dict_geo_device', 'region',         geo_device_id)),
    ('country',        dictGetString('inmobi.dict_geo_device', 'country',        geo_device_id)),
    ('device_model',   dictGetString('inmobi.dict_geo_device', 'device_model',   geo_device_id)),
    ('os_version',     dictGetString('inmobi.dict_geo_device', 'os_version',     geo_device_id)),
    ('category',       dictGetString('inmobi.dict_apps',       'category',       app_id)),
    ('publisher_tier', dictGetString('inmobi.dict_apps',       'publisher_tier', app_id)),
    ('vertical',       if(advertiser_id = '', '(unfilled)', dictGetString('inmobi.dict_advertisers', 'vertical',      advertiser_id))),
    ('campaign_type',  if(advertiser_id = '', '(unfilled)', dictGetString('inmobi.dict_advertisers', 'campaign_type', advertiser_id)))
]"""

BACKFILL_HOURLY = """
INSERT INTO inmobi.events_hourly
SELECT
    toStartOfHour(event_time) AS hour,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM inmobi.ad_events
GROUP BY hour
"""

BACKFILL_BY_DIM = f"""
INSERT INTO inmobi.events_hourly_by_dim
SELECT
    toStartOfHour(event_time) AS hour,
    d.1 AS dim_name,
    d.2 AS dim_value,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM inmobi.ad_events
ARRAY JOIN {DIM_ARRAY} AS d
GROUP BY hour, dim_name, dim_value
"""


def scalar(sql):
    return query(sql).strip()


def count_of(table):
    return int(scalar(f"SELECT count() FROM inmobi.{table}"))


def verify():
    """Raw vs rollup, every column, to the digit.

    Revenue is Float64 and summed in a different order by each path, so it is
    compared rounded to cents. Everything else must match exactly.
    """
    print("\n=== Verification: raw vs rollup ===")

    raw = scalar("""
        SELECT count(), sum(is_filled), sum(is_impression), sum(is_click), round(sum(revenue), 2)
        FROM inmobi.ad_events FORMAT TSV
    """).split("\t")

    hourly = scalar("""
        SELECT sum(requests), sum(fills), sum(impressions), sum(clicks), round(sum(revenue), 2)
        FROM inmobi.events_hourly FORMAT TSV
    """).split("\t")

    cols = ["requests", "fills", "impressions", "clicks", "revenue"]
    ok = True

    print(f"\n  {'column':<12} {'raw':>16} {'events_hourly':>16}  match")
    for c, r, h in zip(cols, raw, hourly):
        match = r == h
        ok &= match
        print(f"  {c:<12} {r:>16} {h:>16}  {'OK' if match else 'MISMATCH'}")

    # Each event contributes exactly once to every dimension, so every
    # dim_name must independently sum to the same grand total. This catches a
    # broken dictGet or a dropped fan-out element that a single total would miss.
    print("\n  Per-dimension totals (each must equal the raw total):")
    per_dim = query("""
        SELECT dim_name, sum(requests), sum(fills), sum(impressions), sum(clicks), round(sum(revenue), 2)
        FROM inmobi.events_hourly_by_dim
        GROUP BY dim_name ORDER BY dim_name FORMAT TSV
    """).strip().splitlines()

    for line in per_dim:
        parts = line.split("\t")
        name, vals = parts[0], parts[1:]
        match = vals == raw
        ok &= match
        print(f"    {name:<16} {'OK' if match else 'MISMATCH -> ' + str(vals)}")

    print(f"\n  Rollup sizes: events_hourly={count_of('events_hourly'):,} rows, "
          f"events_hourly_by_dim={count_of('events_hourly_by_dim'):,} rows, "
          f"raw={int(raw[0]):,} rows")

    print(f"\n  {'ALL COLUMNS MATCH' if ok else 'VERIFICATION FAILED'}")
    return ok


def main():
    force = "--force" in sys.argv

    if "--verify" in sys.argv:
        sys.exit(0 if verify() else 1)

    existing = {t: count_of(t) for t in ("events_hourly", "events_hourly_by_dim")}
    non_empty = {t: n for t, n in existing.items() if n > 0}

    if non_empty and not force:
        print("REFUSING TO BACKFILL — target tables are not empty:")
        for t, n in non_empty.items():
            print(f"  inmobi.{t}: {n:,} rows")
        print("\nRe-running the backfill double-counts. If you truly intend to")
        print("rebuild, TRUNCATE the tables first, or pass --force.")
        sys.exit(1)

    print("Backfilling inmobi.events_hourly ...")
    query(BACKFILL_HOURLY)
    print(f"  -> {count_of('events_hourly'):,} rows")

    print("Backfilling inmobi.events_hourly_by_dim ...")
    query(BACKFILL_BY_DIM)
    print(f"  -> {count_of('events_hourly_by_dim'):,} rows")

    sys.exit(0 if verify() else 1)


if __name__ == "__main__":
    main()
