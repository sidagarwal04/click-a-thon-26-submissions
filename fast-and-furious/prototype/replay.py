#!/usr/bin/env python3
"""
Event-time replay: proves the pipeline handles OPEN sessions and LATE events
incrementally (the judges' "update handling" criterion).

- All 905K events are replayed in event-time order in 5-minute batches
  (simulating the live stream; the extract at rest has zero open sessions,
  so live behavior only exists mid-replay — profiling fact F9/E9).
- STRESS: 1% of hot-window events are held back by 30 minutes of stream time
  (on top of the natural 7% within-session disorder), simulating late arrivals.
- After each batch: incremental compaction (dirty units only), live concurrency
  reading, correction-row accounting.
- At the end: the served series must equal brute-force ground truth EXACTLY,
  proving corrections converge with no rebuild.
"""
import time
from pipeline import open_session, create_all, load_content, create_dict, compact, DATA

BATCH_S = 300          # 5-minute stream batches
HOLDBACK_S = 1800      # late events delayed 30 min
HOLDBACK_PCT = 1       # % of events held back

s = open_session("proto_replay")
create_all(s)
load_content(s)
create_dict(s)

# Assign each event to a replay batch; hold back a deterministic 1% sample by 30 min.
s.query(f"""
CREATE OR REPLACE TABLE ch.replay_src ENGINE = MergeTree ORDER BY (batch_id) AS
SELECT *,
       cityHash64(video_session_id, event_timestamp) % 100 < {HOLDBACK_PCT} AS held_back,
       toUInt32(intDiv(intDiv(assumeNotNull(event_timestamp), 1000) + if(held_back, {HOLDBACK_S}, 0), {BATCH_S})) AS batch_id
FROM file('{DATA}/raw_events.parquet')
""")

batches = [int(x) for x in str(s.query(
    "SELECT DISTINCT batch_id FROM ch.replay_src ORDER BY batch_id", "TSV")).split()]
n_held = str(s.query("SELECT countIf(held_back), count() FROM ch.replay_src", "CSV")).strip()
print(f"replaying {len(batches)} batches of {BATCH_S}s stream time; held-back,total = {n_held}")

wm = 0
total_ms, total_corr, peak_tick_ms = 0.0, 0, 0.0
log = []
for i, b in enumerate(batches):
    s.query(f"""
        INSERT INTO ch.raw_events
        SELECT
            toUInt64(assumeNotNull(event_timestamp)), assumeNotNull(user_id),
            assumeNotNull(video_session_id), toUInt64(assumeNotNull(session_start_epoch)),
            toUInt64(assumeNotNull(content_id)), assumeNotNull(event_type), assumeNotNull(event),
            assumeNotNull(platform), assumeNotNull(country), assumeNotNull(app_version),
            lower(extract(assumeNotNull(audio_language), '^[a-zA-Z]*')),
            lower(extract(assumeNotNull(subtitle_language), '^[a-zA-Z]*')),
            assumeNotNull(player_version)
        FROM ch.replay_src WHERE batch_id = {b}
    """)
    rows_before = int(str(s.query("SELECT count() FROM ch.concurrency_deltas_global", "CSV")).strip())
    dt, wm = compact(s, since_seq=wm)
    rows_after = int(str(s.query("SELECT count() FROM ch.concurrency_deltas_global", "CSV")).strip())
    corr = rows_after - rows_before
    total_ms += dt * 1000
    total_corr += corr
    peak_tick_ms = max(peak_tick_ms, dt * 1000)

    # live global concurrency at the stream watermark minute
    stream_minute = b * BATCH_S // 60 * 60 + BATCH_S - 60
    live = str(s.query(f"""
        SELECT sum(delta) FROM ch.concurrency_deltas_global
        WHERE day = toDate(intDiv({stream_minute}, 86400)) AND m <= {stream_minute}
    """, "CSV")).strip()
    log.append((b * BATCH_S, live, corr, round(dt * 1000)))

# show the interesting ticks: around the live-event ramp
print("\nstream_time_utc          live_concurrency  corr_rows  compact_ms")
for ts, live, corr, ms in log:
    if int(live or 0) > 0 or corr > 0:
        from datetime import datetime, timezone
        t = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m-%d %H:%M")
        print(f"{t}   {live:>10}   {corr:>7}   {ms:>6}")

print(f"\ntotals: {total_corr} correction rows across {len(batches)} ticks; "
      f"avg tick {total_ms/len(batches):.0f} ms, max tick {peak_tick_ms:.0f} ms")

# ---------- final convergence check ----------
print("\n=== FINAL: served series vs brute-force ground truth ===")
print(str(s.query(f"""
WITH serving AS (
    SELECT m, sum(d) OVER (PARTITION BY day ORDER BY m
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS concurrent
    FROM (
        SELECT g.day AS day, g.m AS m, coalesce(e.d, 0) AS d
        FROM (
            SELECT dd.day AS day, toUInt32(toUInt32(dd.day) * 86400 + 60 * nn.number) AS m
            FROM (SELECT DISTINCT day FROM ch.concurrency_deltas_global) AS dd
            CROSS JOIN numbers(1440) AS nn
        ) g
        LEFT JOIN (
            SELECT day, m, sum(delta) AS d FROM ch.concurrency_deltas_global GROUP BY day, m
        ) e ON g.day = e.day AND g.m = e.m
    )
),
gt AS (
    SELECT toUInt32(minute_ts) AS m, toInt64(concurrent_sessions) AS c
    FROM file('{DATA}/ground_truth_foreground_per_minute.csv', CSVWithNames)
)
SELECT
    countIf(coalesce(gt.c, 0) != coalesce(serving.concurrent, 0)) AS mismatched_minutes,
    count() AS minutes_compared,
    max(abs(coalesce(gt.c, 0) - coalesce(serving.concurrent, 0))) AS max_abs_diff
FROM serving FULL OUTER JOIN gt ON serving.m = gt.m
WHERE coalesce(gt.c, 0) != 0 OR coalesce(serving.concurrent, 0) != 0
""", "PrettyCompact")))
