#!/usr/bin/env python3
"""Compress the currently-loaded replay so 35 days of history streams past a live
HyperDX alert in minutes instead of real-time weeks.

Rewrites every row's event_time so 1 data-hour occupies BUCKET_SECONDS of wall-clock
time instead of 3600, anchored at "now" — the compressed window starts in the near
future and streams forward, so the alert sees each hour become live at its own pace,
same mechanism as real time, just faster. Updates inmobi.replay_clock so both the
alert query (scripts/metric_query.py) and the RCA agent (RCA/app/registry.get_clock)
bucket the compressed rows identically — see docs/REPLAY_CLOCK.md.

Operates entirely server-side on whatever is already in inmobi.ad_events (run
scripts/replay.sh first) — no local file re-read, no hardcoded dataset dates:
data_start and origin_dow are discovered from min(event_time) at run time, exactly
like the rest of this system reads its own registry rather than restating it.

    ./scripts/compress_replay.py                    # 1 data-hour per wall-clock second
    ./scripts/compress_replay.py --bucket-seconds 3  # slower, e.g. for a longer demo

Depends on nothing outside the standard library, same as metric_query.py.
"""

from __future__ import annotations

import argparse
import base64
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _request(env: dict, sql: str) -> bytes:
    url = f"https://{env['CLICKHOUSE_HOST']}:{env.get('CLICKHOUSE_HTTPS_PORT', '8443')}/?database=inmobi"
    req = urllib.request.Request(url, data=sql.encode())
    auth = f"{env['CLICKHOUSE_USER']}:{env['CLICKHOUSE_PASSWORD']}"
    req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    return urllib.request.urlopen(req, timeout=300).read()


def execute(env: dict, sql: str) -> None:
    _request(env, sql)


def query(env: dict, sql: str) -> list:
    body = _request(env, sql).decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--bucket-seconds",
        type=int,
        default=1,
        help="wall-clock seconds per data-hour (default: 1 -> ~14 min for 840h)",
    )
    args = ap.parse_args()
    bucket_seconds = args.bucket_seconds

    env = load_env()

    anchor = int(
        query(env, "SELECT toUnixTimestamp(now()) AS t FORMAT JSONEachRow")[0]["t"]
    )

    bounds = query(
        env,
        "SELECT toUnixTimestamp(min(event_time)) AS start, "
        "toUnixTimestamp(max(event_time)) AS finish, "
        "toDayOfWeek(min(event_time)) AS iso_dow, "
        "dateDiff('hour', min(event_time), max(event_time)) + 1 AS calendar_hours "
        "FROM inmobi.ad_events FORMAT JSONEachRow",
    )[0]
    data_start = int(bounds["start"])
    span = int(bounds["finish"]) - data_start

    prior = query(
        env,
        "SELECT bucket_seconds, anchor, origin_dow FROM inmobi.replay_clock "
        "FINAL LIMIT 1 FORMAT JSONEachRow",
    )
    prior = prior[0] if prior else {"bucket_seconds": 3600, "anchor": 0, "origin_dow": 0}

    # Is what is already in ad_events real-time or a previous compression?
    #
    # This matters because the script has to be re-runnable: the sealed dataset arrives late,
    # the demo pace gets retuned, and neither can require a full reload first. Deriving the
    # data-hour index as (event_time - min)/3600 is only correct on real-time rows — run it
    # over an already-compressed replay, where a whole data-hour is one second, and intDiv by
    # 3600 collapses all 840 buckets into one.
    #
    # A previous compression is recognisable: its whole span is shorter than the calendar
    # hours it claims to cover. Inverting it is exact, because replay_clock records the anchor
    # and bucket size that produced it.
    compressed_input = span < int(bounds["calendar_hours"]) * 3600 // 2
    if compressed_input:
        prior_size, prior_anchor = int(prior["bucket_seconds"]), int(prior["anchor"])
        hour_index = f"intDiv(toUnixTimestamp(event_time) - {prior_anchor}, {prior_size})"
        total_hours = span // prior_size + 1
        # Cannot be re-read off a compressed calendar, where a data-day may occupy 24
        # seconds — carry forward what the original load recorded.
        origin_dow = int(prior["origin_dow"])
        print(
            f"input is already compressed (bucket_seconds={prior_size}, span={span}s) — "
            f"inverting via replay_clock rather than re-reading the calendar"
        )
    else:
        hour_index = f"intDiv(toUnixTimestamp(event_time) - {data_start}, 3600)"
        total_hours = int(bounds["calendar_hours"])
        origin_dow = int(bounds["iso_dow"]) - 1  # ClickHouse 1=Mon..7=Sun -> 0=Mon..6=Sun

    window_seconds = total_hours * bucket_seconds

    print(
        f"compressing {total_hours} data-hours into {window_seconds}s "
        f"({window_seconds / 60:.1f} min) of wall-clock time, starting now "
        f"({datetime.fromtimestamp(anchor, tz=timezone.utc).isoformat()})"
    )

    print("staging a copy of ad_events ...")
    execute(env, "DROP TABLE IF EXISTS inmobi.ad_events_staging")
    execute(
        env,
        "CREATE TABLE inmobi.ad_events_staging ENGINE = MergeTree ORDER BY event_time "
        "AS SELECT * FROM inmobi.ad_events",
    )

    print("truncating ad_events + ad_events_enriched ...")
    execute(env, "TRUNCATE TABLE inmobi.ad_events")
    execute(env, "TRUNCATE TABLE inmobi.ad_events_enriched")

    print(
        "re-inserting with compressed event_time (MV1 repopulates ad_events_enriched) ..."
    )
    execute(
        env,
        f"""
INSERT INTO inmobi.ad_events
SELECT
    toDateTime64({anchor} + ({hour_index}) * {bucket_seconds}, 3) AS event_time,
    app_id, geo_device_id, advertiser_id, ad_format,
    is_filled, is_impression, is_click, revenue
FROM inmobi.ad_events_staging
""",
    )

    print("dropping staging table ...")
    execute(env, "DROP TABLE inmobi.ad_events_staging")

    print("updating inmobi.replay_clock ...")
    execute(
        env,
        "INSERT INTO inmobi.replay_clock (bucket_seconds, anchor, origin_dow) "
        f"VALUES ({bucket_seconds}, {anchor}, {origin_dow})",
    )

    rows = query(
        env,
        "SELECT count() AS n, toString(min(event_time)) AS lo, "
        "toString(max(event_time)) AS hi FROM inmobi.ad_events_enriched "
        "FORMAT JSONEachRow",
    )[0]
    print(
        f"done. ad_events_enriched: {rows['n']} rows, event_time {rows['lo']} .. {rows['hi']}"
    )
    print(
        f"replay_clock: bucket_seconds={bucket_seconds} anchor={anchor} origin_dow={origin_dow}"
    )
    # The agent re-reads replay_clock per query, so it needs nothing. HyperDX tiles do not:
    # metric_sql bakes the bucket/hour/weekend expressions into the query text at render
    # time, so every saved tile is still scoring on the previous clock until re-rendered.
    print("\nNEXT: ./scripts/provision_alerts.py --apply   (tiles are rendered against the")
    print("      clock and are now stale — they will score the old buckets until re-pushed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
