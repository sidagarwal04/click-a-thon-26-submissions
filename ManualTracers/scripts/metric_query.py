#!/usr/bin/env python3
"""Render a metric's deviation query from metric_def. Prints SQL, runs nothing.

There is no detection view any more: the same builder that the RCA agent uses
(`RCA/app/metric_sql.py`) is the only place the baseline and z-score are
expressed, and everything else renders it. Four consumers:

  scripts/metric_query.py alert     fill_rate   global tile: does the metric itself move?
  scripts/metric_query.py marginal  fill_rate   sentinel tile: does any depth-1 slice move?
  scripts/metric_query.py freshness             ops tile: is data still arriving?
  scripts/metric_query.py scan      fill_rate   ranked segment scan, for replay.sh

All read the metric's formula, threshold and guard rails live from metric_def, so
a registry change needs no edit here.

**Why `marginal` exists.** The global tile only fires when the metric moves in
aggregate, so an incident confined to a segment too small to shift the global
number is never detected at all — it is found by the agent's depth-1 scan, but
only once something else has woken the agent. The marginal tile scores all
depth-1 slices in the same single ARRAY JOIN pass and lets HyperDX alert on each
independently (non-numeric columns become group columns), which closes that gap
without a second query shape.

**Tile bounds are macro-bound, CLI bounds are now()-relative.** A tile is
evaluated by ClickStack over an explicit window, so it takes that window from
`{startDateMilliseconds}`/`{endDateMilliseconds}` — if the inner query used its
own fixed lookback instead, the two windows would disagree and the tile would
score fewer buckets than the alert asked for.

**Every lookback here is in data-hours, converted through replay_clock.** Writing
one as `INTERVAL 24 HOUR` is correct only at real time; under a compressed replay
it reaches past the whole dataset. See docs/REPLAY_CLOCK.md.

Depends on nothing outside the standard library — replay.sh runs it without a venv.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_metric_sql():
    """Load RCA/app/metric_sql.py by path, NOT as `from app import metric_sql`.

    Importing it as part of the `app` package would execute app/__init__.py, which pulls in
    python-dotenv — and replay.sh calls this with the system python, outside RCA's venv.
    metric_sql itself imports nothing, so loading the file directly keeps this script
    dependency-free while still sharing the one copy of the query builder."""
    path = ROOT / "RCA" / "app" / "metric_sql.py"
    spec = importlib.util.spec_from_file_location("metric_sql", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metric_sql = _load_metric_sql()

LOOKBACK_BUCKETS = 24  # data-hours, not wall-clock hours

# ClickStack hands a tile its evaluation window as epoch-millisecond parameters. Binding the
# inner query to these rather than to a fixed lookback is what keeps the rows the query scores
# identical to the rows the alert evaluates.
TILE_START = "fromUnixTimestamp64Milli({startDateMilliseconds:Int64})"
TILE_END = "fromUnixTimestamp64Milli({endDateMilliseconds:Int64})"


def load_env() -> dict[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def query(env: dict[str, str], sql: str) -> list[dict]:
    url = f"https://{env['CLICKHOUSE_HOST']}:{env.get('CLICKHOUSE_HTTPS_PORT', '8443')}/?database=inmobi"
    req = urllib.request.Request(url, data=sql.encode())
    auth = f"{env['CLICKHOUSE_USER']}:{env['CLICKHOUSE_PASSWORD']}"
    req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    body = urllib.request.urlopen(req, timeout=120).read().decode()
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def get_clock(env: dict[str, str]) -> dict:
    """Not cached: this row is exactly what a compressed replay rewrites, and this script is
    invoked fresh per call, unlike the agent's long-lived process."""
    rows = query(
        env,
        "SELECT bucket_seconds, anchor, origin_dow FROM inmobi.replay_clock "
        "FINAL LIMIT 1 FORMAT JSONEachRow",
    )
    return rows[0] if rows else {"bucket_seconds": 3600, "anchor": 0, "origin_dow": 0}


def eligible_dims(env: dict[str, str], metric_id: str) -> list[str]:
    """The metric's drill order from metric_dim_map, minus its own invalid_dims. Read from the
    registry rather than restated, so adding a dimension is a row and nothing else."""
    return [
        r["dim_id"]
        for r in query(
            env,
            f"SELECT dim_id FROM inmobi.metric_dim_map FINAL "
            f"WHERE metric_id = '{metric_id}' AND dim_id NOT IN "
            f"(SELECT arrayJoin(invalid_dims) FROM inmobi.metric_def FINAL "
            f"WHERE metric_id = '{metric_id}') ORDER BY priority FORMAT JSONEachRow",
        )
    ]


def freshness_sql(clock: dict) -> str:
    """Staleness in wall-clock seconds. The one alert that fires when ingest stops — every
    deviation alert goes *silent* in that case, because no rows means no anomalies, and
    silence is indistinguishable from health.

    Measured against the evaluation window's end rather than now(): ClickStack rejects an
    alert query with no time macro at all, and anchoring to the window is the honest version
    of satisfying that — re-running this by hand for a past window reproduces what the alert
    saw, which `now()` cannot.

    The upper bound is deliberately the only bound. Restricting to rows *inside* the window
    would make max() empty exactly when ingest has stopped, which is the case this alert
    exists to catch; reaching back to the newest row ever is what turns silence into a number.

    least(window_end, max) for the same reason investigate.get_max_ts() clamps: the replay
    writes event_time into the near future and streams forward, so a raw max() sits ahead of
    the window and the difference would be permanently negative — an alert that cannot fire.

    Reported in *evaluation windows*, not seconds, and the window length is derived from the
    macros rather than from {intervalSeconds}. Two ClickStack constraints meet here: an alert
    query is rejected outright unless it references the window macros, but a `number` tile is
    only substituted with the start/end pair — asking it for {intervalSeconds} passes
    validation and then fails at run time with "Substitution `intervalSeconds` is not set".
    end - start is the same quantity and is always available.

    Dividing by it is what earns its place: the threshold ("more than one window with no new
    data") keeps its meaning when the interval changes, which it does on every clock change.
    A fixed second count would silently become a different alert.

    An empty result is not a hole: max() over no rows yields the DateTime epoch, so the
    quotient goes large and the alert fires, which is the intended reading of "no data".
    """
    return (
        f"SELECT dateDiff('second',\n"
        f"                least({TILE_END}, toDateTime(max(event_time))),\n"
        f"                {TILE_END})\n"
        f"       / greatest(dateDiff('second', {TILE_START}, {TILE_END}), 1)\n"
        f"       AS windows_stale\n"
        f"FROM inmobi.ad_events_enriched\n"
        f"WHERE event_time <= {TILE_END}"
    )


def main() -> int:
    argv = sys.argv[1:]
    mode = argv[0] if argv else None
    if mode not in ("alert", "marginal", "freshness", "scan") or (
        mode != "freshness" and len(argv) < 2
    ):
        print(__doc__, file=sys.stderr)
        return 2

    env = load_env()
    clock = get_clock(env)

    if mode == "freshness":
        print(freshness_sql(clock))
        return 0

    metric_id = argv[1]
    rows = query(
        env,
        f"SELECT * FROM inmobi.metric_def FINAL "
        f"WHERE metric_id = '{metric_id}' FORMAT JSONEachRow",
    )
    if not rows:
        print(f"no such metric_id: {metric_id}", file=sys.stderr)
        return 1
    meta = rows[0]

    history_s = metric_sql.window_seconds(metric_sql.HISTORY_BUCKETS, clock)

    if mode in ("alert", "marginal"):
        # A tile inherits its window from ClickStack instead of choosing its own, so the rows
        # scored here are exactly the rows the alert evaluates.
        hist = f"({TILE_START} - INTERVAL {history_s} SECOND)"
        start, end = TILE_START, TILE_END
    else:
        lookback_s = metric_sql.window_seconds(LOOKBACK_BUCKETS, clock)
        hist = f"now() - INTERVAL {history_s} SECOND"
        start, end = f"now() - INTERVAL {lookback_s} SECOND", "now()"

    if mode == "alert":
        # dim_name = 'ALL' only: this tile answers "did the metric itself move?". Shape is a
        # single number, which is the contract a ClickStack `number` tile alert evaluates:
        # pair it with thresholdType above_exclusive at 0 — NOT above, which fires
        # unconditionally at zero.
        inner = metric_sql.deviation_sql(meta, ["ALL"], hist, start, end, clock=clock)
        print(f"SELECT toUInt64(sum(is_anomaly)) AS anomaly_count\nFROM (\n{inner}\n)")

    elif mode == "marginal":
        # No 'ALL' here — the global tile already owns that series, and including it would
        # fire both tiles for the same incident.
        #
        # Column roles are positional in ClickStack: the Date/DateTime column is the time
        # bucket, every non-numeric column is a grouping dimension alerted on independently,
        # and the LAST numeric column is the value compared to the threshold. So dim_name and
        # dim_value must stay strings and peak_abs_z must stay last.
        #
        # Rolled up to $__timeInterval rather than left at one row per data-hour. A
        # time-series alert is *required* to carry an interval macro — ClickStack rejects the
        # query otherwise, because it evaluates each interval bucket independently and has to
        # know where the boundaries are. Aggregating to the same grid the alert scores on is
        # the honest way to satisfy that: one row per group per evaluation, holding the worst
        # z that occurred inside it.
        #
        # LIMIT 1 BY keeps the single highest-contribution slice per bucket. A correlated
        # fault lights up several slices at once (Android 15 drags device_model and region
        # with it) and every surviving group is its own webhook and its own RCA run. Ranking
        # by contribution — sum |delta_abs| x sample_count, never percentage change — is the
        # same rule scan_dims uses, and the agent re-enumerates all 62 slices anyway, so the
        # top one is a trigger, not the conclusion.
        inner = metric_sql.deviation_sql(
            meta, eligible_dims(env, metric_id), hist, start, end, clock=clock
        )
        print(
            "SELECT $__timeInterval(ts) AS bucket, dim_name, dim_value,\n"
            "       round(max(abs(z_score)), 2) AS peak_abs_z\n"
            f"FROM (\n{inner}\n)\nWHERE is_anomaly = 1\n"
            "GROUP BY bucket, dim_name, dim_value\n"
            "ORDER BY bucket, sum(abs(delta_abs) * sample_count) DESC\n"
            "LIMIT 1 BY bucket"
        )

    else:
        inner = metric_sql.deviation_sql(
            meta, ["ALL"] + eligible_dims(env, metric_id), hist, start, end, clock=clock
        )
        print(
            "SELECT dim_name, dim_value, count() AS anomalous_hours,\n"
            "       round(max(abs(z_score)), 2) AS peak_abs_z,\n"
            "       round(avg(actual), 4) AS actual, round(avg(expected), 4) AS expected,\n"
            "       round(sum(abs(delta_abs) * sample_count)) AS contribution\n"
            f"FROM (\n{inner}\n)\nWHERE is_anomaly = 1\n"
            "GROUP BY dim_name, dim_value ORDER BY contribution DESC LIMIT 25"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
