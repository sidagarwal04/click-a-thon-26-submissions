"""Replay the sealed unseen slice as a live stream instead of one bulk load.

Why this exists: the pipeline was only ever exercised by loading five weeks at once and
investigating after the fact. A stream proves the harder claim — that detection works on data
arriving in order, where the system has never seen what comes next.

The parquet is bulk-loaded ONCE into a staging table, then released hour by hour. Slicing in
ClickHouse rather than pandas keeps the tick cheap (an INSERT ... SELECT over an indexed
range), and avoids a parquet reader dependency the image does not otherwise need.

Per tick:

    1. release the tick's rows from staging into ad_events_unseen
    2. append that window (and only that window) to events_full_unseen, joined to the UNSEEN dims
    3. roll the same window up into hourly_summary_unseen

Steps 2-3 are mandatory, not incidental: events_full / hourly_summary are
`CREATE TABLE ... AS SELECT` SNAPSHOTS, not materialized views, so raw inserts alone would
never reach the tables detection actually queries.

Windows advance in event_time order, so a batch never contains data from the future relative to
the batches before it — the property that makes streamed detection honest.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from config import config, env
from data.client import get_client
from data.load import _statements, load_csv

log = logging.getLogger(__name__)

_REPO = Path(__file__).resolve().parents[2]        # <repo> on a host checkout
_BACKEND_ROOT = Path(__file__).resolve().parents[1]  # /app in the container image

# Dimension CSVs ship WITH the unseen slice and must be loaded from there: same ids, regenerated
# attributes. Joining unseen events to the dev dims misattributes every segment.
_DIM_CSVS = {"apps": "apps.csv", "advertisers": "advertisers.csv", "geo_device": "geo_device.csv"}

_UNSEEN = "unseen"


def stream_config() -> dict:
    return config()["stream"]


def source_dir() -> Path:
    """Where the unseen slice lives.

    Resolved rather than hardcoded because the layout differs by environment: on the host the
    code is <repo>/backend/data/stream.py, but the image copies backend/ to /app, so the same
    parents[2] that means "repo root" locally means "/" in the container — which is how this
    resolved to /InMobi/unseen_data and failed. RCA_STREAM_DIR overrides both.
    """
    override = env("RCA_STREAM_DIR")
    if override:
        return Path(override)
    rel = stream_config()["source_dir"]
    for base in (_REPO, _BACKEND_ROOT):
        if (base / rel).exists():
            return base / rel
    return _REPO / rel  # nothing found: return the canonical path so the error names it


def _t() -> dict:
    return config()["datasets"][_UNSEEN]


def _staging() -> str:
    """Holds the full slice; the stream drains it. Named off the events table so the pair is
    obvious in SHOW TABLES."""
    return _t()["events"] + "_src"


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def prepare(client=None, reload_source: bool = True) -> dict:
    """Create the unseen table set, load its dims, and stage the parquet. Idempotent.

    Always truncates the streamed tables: a replay must start empty, or a second run
    double-counts every hour it re-ingests.
    """
    client = client or get_client()
    unseen = _t()

    for table in unseen.values():
        client.command(_statements((table,))[0])
    client.command(f"CREATE TABLE IF NOT EXISTS {_staging()} AS {unseen['events']}")

    for role in ("events", "enriched", "hourly"):
        client.command(f"TRUNCATE TABLE {unseen[role]}")

    out = {}
    for role, filename in _DIM_CSVS.items():
        client.command(f"TRUNCATE TABLE {unseen[role]}")
        load_csv(client, unseen[role], filename, data_dir=source_dir())
        out[unseen[role]] = client.query(f"SELECT count() FROM {unseen[role]}").result_rows[0][0]

    if reload_source:
        client.command(f"TRUNCATE TABLE {_staging()}")
        with open(source_dir() / "ad_events.parquet", "rb") as f:
            client.raw_insert(_staging(), insert_block=f, fmt="Parquet")
    out[_staging()] = client.query(f"SELECT count() FROM {_staging()}").result_rows[0][0]
    return out


def source_bounds(client=None) -> tuple[datetime | None, datetime | None]:
    """(first, last) event_time staged, or (None, None) when nothing is staged."""
    client = client or get_client()
    count, lo, hi = client.query(
        f"SELECT count(), min(event_time), max(event_time) FROM {_staging()}"
    ).result_rows[0]
    # count() first: min()/max() on an empty ClickHouse table return the epoch, not NULL, so
    # trusting them would report 1970 as a real stream boundary.
    return (lo, hi) if count else (None, None)


def stream_bounds(client=None) -> tuple[datetime | None, datetime | None]:
    """(min, max) hour released so far — what detection can currently see.

    Always the UNSEEN rollup, never tables('target'): the stream fills that table whichever
    dataset is active for investigation, and reading the active one would report the dev range
    (Jun 1-Jul 5) as if it were streamed progress.
    """
    client = client or get_client()
    count, lo, hi = client.query(
        f"SELECT count(), min(hour), max(hour) FROM {_t()['hourly']}"
    ).result_rows[0]
    return (lo, hi) if count else (None, None)


def windows(batch_hours: int | None = None, client=None) -> Iterator[tuple[datetime, datetime]]:
    """Yield [start, end) windows covering the staged slice, in order."""
    hours = batch_hours or stream_config()["batch_hours"]
    lo, hi = source_bounds(client)
    if lo is None:
        return
    step = timedelta(hours=hours)
    start = lo.replace(minute=0, second=0, microsecond=0)
    while start <= hi:
        yield start, start + step
        start += step


def release(start: datetime, end: datetime, client=None) -> int:
    """Land one batch: staging -> raw -> enriched -> hourly, scoped to [start, end).

    Returns rows released. An empty window is not an error — the stream carries on through
    quiet hours.
    """
    client = client or get_client()
    unseen, span = _t(), {"s": _fmt(start), "e": _fmt(end)}
    scope = "event_time >= toDateTime({s:String}) AND event_time < toDateTime({e:String})"

    # Idempotence guard. A resumed stream walks windows from the beginning, so without this it
    # re-ingests hours it already landed: measured 4x on hour 0 (34,060 requests vs a true
    # 8,515), which reads downstream as a +331% "request spike" that never happened.
    already = client.query(
        f"SELECT count() FROM {unseen['hourly']} "
        f"WHERE hour >= toDateTime({{s:String}}) AND hour < toDateTime({{e:String}})",
        parameters=span,
    ).result_rows[0][0]
    if already:
        return 0

    moved = client.query(
        f"SELECT count() FROM {_staging()} WHERE {scope}", parameters=span
    ).result_rows[0][0]
    if not moved:
        return 0

    # EVERY step reads the immutable staging table, never a table this function also writes to.
    # Deriving enriched from ad_events_unseen made duplication compound (1.23x raw -> 1.45x
    # enriched), because a re-run re-read rows a previous run had already inserted.
    join = (
        f"FROM {_staging()} e "
        f"LEFT JOIN {unseen['apps']} a USING (app_id) "
        f"LEFT JOIN {unseen['advertisers']} adv USING (advertiser_id) "
        f"LEFT JOIN {unseen['geo_device']} g USING (geo_device_id) "
        f"WHERE e.{scope}"
    )
    client.command(
        f"INSERT INTO {unseen['events']} SELECT * FROM {_staging()} WHERE {scope}", parameters=span
    )
    # Join to the UNSEEN dims — the whole reason this slice has its own table set.
    client.command(
        f"INSERT INTO {unseen['enriched']} "
        f"SELECT e.event_time, e.app_id, e.geo_device_id, e.advertiser_id, e.ad_format, "
        f"       e.is_filled, e.is_impression, e.is_click, e.revenue, "
        f"       a.category, a.publisher_tier, adv.vertical, adv.campaign_type, "
        f"       g.region, g.country, g.device_model, g.os_version " + join,
        parameters=span,
    )
    client.command(
        f"INSERT INTO {unseen['hourly']} "
        f"SELECT toStartOfHour(e.event_time) AS hour, g.region, g.country, g.os_version, "
        f"       g.device_model, e.ad_format, a.category, a.publisher_tier, adv.vertical, "
        f"       adv.campaign_type, e.app_id, e.advertiser_id, "
        f"       count(), sum(e.is_filled), sum(e.is_impression), sum(e.is_click), sum(e.revenue) "
        + join + " GROUP BY ALL",
        parameters=span,
    )
    return moved


# ---- analysis ledger -------------------------------------------------------
#
# What has already been scored. Lives in ClickHouse rather than job memory so it survives a
# restart: a resumed stream can skip hours it has already inferred on, and "did we ever analyse
# this hour?" stays answerable in SQL after the process is gone.

ANALYSIS = "stream_analysis"


def ensure_analysis_table(client=None) -> None:
    (client or get_client()).command(_statements((ANALYSIS,))[0])


def record_analysis(rows: list[dict], client=None) -> int:
    """Append one row per (hour, metric) scored. ReplacingMergeTree keyed on (hour, metric),
    so re-analysing an hour supersedes the old verdict instead of duplicating it."""
    if not rows:
        return 0
    client = client or get_client()
    ensure_analysis_table(client)
    columns = ["hour", "metric", "method", "analyzed_at", "detected", "score",
               "pct_delta", "observed", "expected", "investigation_id"]
    # UTC-aware on the way in. clickhouse-connect treats a NAIVE datetime as LOCAL time and
    # converts it for the UTC column, which silently shifted every logged hour by the machine's
    # offset (-5:30 here) — mislabelling the ledger and breaking the skip-on-resume match.
    now = datetime.now(UTC)
    client.insert(
        ANALYSIS,
        [[r["hour"].replace(tzinfo=UTC), r["metric"], r["method"], now, 1 if r["detected"] else 0,
          float(r["score"]), float(r["pct_delta"]), float(r["observed"]), float(r["expected"]),
          r.get("investigation_id") or ""] for r in rows],
        column_names=columns,
    )
    return len(rows)


def analyzed_hours(metric: str | None = None, client=None) -> set:
    """(hour, metric) pairs already scored — what a resumed stream should skip."""
    client = client or get_client()
    ensure_analysis_table(client)
    where = "WHERE metric = {m:String}" if metric else ""
    rows = client.query(
        f"SELECT hour, metric FROM {ANALYSIS} FINAL {where}",
        parameters={"m": metric} if metric else {},
    ).result_rows
    return {(h, m) for h, m in rows}


def analysis_summary(client=None) -> dict:
    """Coverage of the streamed slice: how much has been looked at, and what fired."""
    client = client or get_client()
    ensure_analysis_table(client)
    scored, hours, hits = client.query(
        f"SELECT count(), uniqExact(hour), countIf(detected = 1) FROM {ANALYSIS} FINAL"
    ).result_rows[0]
    return {"metric_hours_scored": scored, "hours_covered": hours, "detections": hits}
