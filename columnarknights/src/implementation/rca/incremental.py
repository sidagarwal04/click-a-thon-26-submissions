"""Incremental detection: track how much of ad_events_raw has already been
folded into fact_events, and how much of fact_events has already been
scanned for anomalies, so an idle-triggered run only looks at what's
actually new instead of re-syncing or re-scanning the whole table every
time.

The watermark (state/scan_watermark.json) is the only persisted state. There
is no "batch done" signal from any loader -- rca.live_monitor decides when to
call run_incremental_pipeline() purely from ingestion having gone idle (see
that module), and this module decides *what date range* is actually new
since the last time it ran.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from . import pipeline
from .db import get_client

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
STATE_DIR = ROOT / "state"
WATERMARK_PATH = STATE_DIR / "scan_watermark.json"

_FACT_INSERT_SELECT = """
    INSERT INTO fact_events
    SELECT
        e.event_time,
        e.app_id,
        ifNull(a.category, '')          AS category,
        ifNull(a.publisher_tier, '')    AS publisher_tier,
        e.geo_device_id,
        ifNull(g.region, '')            AS region,
        ifNull(g.country, '')           AS country,
        ifNull(g.device_model, '')      AS device_model,
        ifNull(g.os_version, '')        AS os_version,
        e.advertiser_id,
        ifNull(adv.vertical, '')        AS vertical,
        ifNull(adv.campaign_type, '')   AS campaign_type,
        e.ad_format,
        e.is_filled,
        e.is_impression,
        e.is_click,
        e.revenue
    FROM ad_events_raw AS e
    LEFT JOIN apps AS a ON e.app_id = a.app_id
    LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id
    LEFT JOIN advertisers AS adv ON e.advertiser_id = adv.advertiser_id
    {where}
"""  # same join as sql/build_fact.sql; {where} adds the incremental cutoff


@dataclass
class Watermark:
    last_scanned_end: date | None = None  # last event_date already covered by a completed scan
    last_raw_row_count: int = 0  # ad_events_raw row count as of the last run, for reset detection
    last_table_min_date: date | None = None  # fact_events' min event_date as of the last run, for reset detection


def load_watermark() -> Watermark:
    if not WATERMARK_PATH.exists():
        return Watermark()
    try:
        data = json.loads(WATERMARK_PATH.read_text())
        return Watermark(
            last_scanned_end=pipeline.parse_date(data["last_scanned_end"]) if data.get("last_scanned_end") else None,
            last_raw_row_count=int(data.get("last_raw_row_count") or 0),
            last_table_min_date=pipeline.parse_date(data["last_table_min_date"]) if data.get("last_table_min_date") else None,
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return Watermark()


def save_watermark(wm: Watermark) -> None:
    STATE_DIR.mkdir(exist_ok=True, parents=True)
    WATERMARK_PATH.write_text(json.dumps({
        "last_scanned_end": str(wm.last_scanned_end) if wm.last_scanned_end else None,
        "last_raw_row_count": wm.last_raw_row_count,
        "last_table_min_date": str(wm.last_table_min_date) if wm.last_table_min_date else None,
    }, indent=2))


def sync_fact_incremental(client, full_rebuild: bool = False) -> int:
    """Folds ad_events_raw rows newer than what's already in fact_events into
    fact_events -- an append (INSERT ... SELECT ... WHERE event_time >
    watermark), not a truncate+rebuild. Only truncates+rebuilds when
    full_rebuild is set (a detected dataset reset), or fact_events is empty
    to begin with (nothing to be incremental about yet). Returns the number
    of rows inserted (0 if already caught up)."""
    if full_rebuild:
        client.command("TRUNCATE TABLE fact_events")

    # count() first, not max(event_time) IS NULL -- ClickHouse's max() over
    # zero rows of a non-nullable DateTime column returns that type's zero
    # value (1970-01-01), not NULL, which would otherwise be misread as "a
    # real watermark from 1970" instead of "empty table".
    before = client.query("SELECT count() FROM fact_events").result_rows[0][0]
    max_fact = None
    if before > 0:
        max_fact_row = client.query("SELECT max(event_time) FROM fact_events").result_rows
        max_fact = max_fact_row[0][0] if max_fact_row else None

    max_raw_row = client.query("SELECT max(event_time) FROM ad_events_raw").result_rows
    max_raw = max_raw_row[0][0] if max_raw_row else None
    if max_raw is None or (max_fact is not None and max_raw <= max_fact):
        return 0  # nothing in ad_events_raw fact_events doesn't already have

    if max_fact is not None:
        where = "WHERE e.event_time > {watermark:DateTime}"
        params = {"watermark": max_fact}
    else:
        where = ""
        params = {}
    client.command(_FACT_INSERT_SELECT.format(where=where), parameters=params)
    after = client.query("SELECT count() FROM fact_events").result_rows[0][0]
    return int(after - before)


def scan_and_investigate_new(client, wm: Watermark) -> list[dict]:
    """Scans only the date range after wm.last_scanned_end (the lookback
    window baseline.evaluate_series queries for history is not "rescanning" --
    it's context for judging whether the *new* days are anomalous). Investigates
    any incident found whose output isn't already in out/ (guards against the
    same incident being found twice across overlapping idle-triggered runs),
    and mutates wm.last_scanned_end to the end of the range actually scanned.
    """
    count_row = client.query("SELECT count() FROM fact_events").result_rows
    if not count_row or count_row[0][0] == 0:
        return []  # count() first -- see the same note in sync_fact_incremental
    row = client.query("SELECT min(event_date), max(event_date) FROM fact_events").result_rows
    table_min, table_max = row[0] if row else (None, None)
    if table_min is None:
        return []

    start = wm.last_scanned_end + timedelta(days=1) if wm.last_scanned_end else table_min
    if start > table_max:
        return []  # nothing new since the last run

    scan_results = pipeline.scan(start, table_max)
    new_results = []
    for entry in scan_results:
        metric = entry["metric"]
        for inc in entry["incidents"]:
            inc_id = pipeline.investigation_id(metric, inc.start, inc.end)
            if (OUT_DIR / f"{inc_id}.json").exists():
                continue
            result = pipeline.investigate(metric, inc.start, inc.end)
            json_path = pipeline.save_investigation_files(result, OUT_DIR)
            result["id"] = json_path.name  # with .json extension, matching /api/incidents' id shape
            new_results.append(result)

    wm.last_scanned_end = table_max
    return new_results


def run_incremental_pipeline() -> dict:
    """The single entry point rca.live_monitor calls on every idle trigger:
    detect a dataset reset, sync fact_events incrementally (or fully, on
    reset), then scan+investigate whatever's new. Returns a small summary
    for the caller to turn into SSE events."""
    client = get_client()
    wm = load_watermark()

    raw_count_row = client.query("SELECT count() FROM ad_events_raw").result_rows
    raw_count = int(raw_count_row[0][0]) if raw_count_row else 0
    fact_count_row = client.query("SELECT count() FROM fact_events").result_rows
    fact_count = int(fact_count_row[0][0]) if fact_count_row else 0
    table_min = None
    if fact_count > 0:
        min_date_row = client.query("SELECT min(event_date) FROM fact_events").result_rows
        table_min = min_date_row[0][0] if min_date_row else None

    # Two independent reset signals: ad_events_raw shrank (a drop+reload with
    # less data), or fact_events' earliest date moved (a drop+reload with a
    # *different* dataset, even one that happens to be the same size or
    # bigger -- row count alone wouldn't catch that).
    reset = (wm.last_raw_row_count > 0 and raw_count < wm.last_raw_row_count) or (
        wm.last_table_min_date is not None and table_min is not None and table_min != wm.last_table_min_date
    )
    if reset:
        wm = Watermark()

    synced_rows = sync_fact_incremental(client, full_rebuild=reset)
    new_results = scan_and_investigate_new(client, wm)

    wm.last_raw_row_count = raw_count
    wm.last_table_min_date = table_min
    save_watermark(wm)

    return {
        "reset": reset,
        "synced_rows": synced_rows,
        "investigation_ids": [r["id"] for r in new_results],
    }
