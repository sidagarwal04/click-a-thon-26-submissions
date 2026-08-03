#!/usr/bin/env python3
"""
!! EXPECTED VALUES BELOW ARE STALE !!

The hardcoded targets (2970 @ 10:56, 2965, 2940, and the platform
breakdowns) come from the OLD definition, which had no playback axis and
counted paused-in-foreground sessions as active. See docs/DECISIONS.md D1
(revised 2026-08-02).

Under the corrected definition the global peaks are:
    10:56 UTC -> 2728   (was 2970, -8.1%)
    10:57     -> 2699   (was 2939)
    10:58     -> 2677   (was 2940)
    10:59     -> 2691   (was 2965)
The platform slice targets have NOT been recomputed and must be
regenerated along with the CSV.

Before this harness means anything:
  1. Regenerate the oracle:
         prototype/reference/ground_truth_generator.sql
     (the .csv it compares against is still the old, playback-axis-free one)
  2. Give prototype/pipeline.py a playback axis — it currently has none,
     so it would fail against a corrected oracle for the right reason.

Note this harness also cannot run here: chdb is not installed.

Meanwhile the definition IS verified in SQL on the live service: the live
path and the analytics path both return 2285 at 2026-07-26 10:56 UTC.
See pipeline/sql/032_live_verify.sql, V6.
---------------------------------------------------------------------

Validation harness: serving-layer answers vs brute-force ground truth.

1. GLOBAL: per-minute foreground concurrency reconstructed from
   ch.concurrency_deltas_global (day-anchored dense cumsum) must match
   ground_truth_foreground_per_minute.csv exactly.
2. SLICES: platform series from ch.concurrency_deltas at I6 reference points.
3. LATENCY: serving queries (dashboard shapes) with timings.
4. IDEMPOTENCE: second compactor run must emit zero correction deltas.
"""
import time
from pipeline import open_session, compact, DATA

s = open_session()

def q(sql, fmt="PrettyCompact"):
    return str(s.query(sql, fmt))

def timed(label, sql, fmt="CSV"):
    t0 = time.time()
    r = s.query(sql, fmt)
    dt = (time.time() - t0) * 1000
    print(f"  {label}: {str(r).strip()[:100]}  [{dt:.0f} ms]")

# Dense per-minute series from the delta table: day-anchored cumsum over a
# generated 1440-minute grid (exactly what a dashboard WITH FILL query does).
def series_sql(table: str, where: str = "1") -> str:
    return f"""
    SELECT m, sum(d) OVER (PARTITION BY day ORDER BY m
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS concurrent
    FROM (
        SELECT g.day AS day, g.m AS m, coalesce(e.d, 0) AS d
        FROM (
            SELECT dd.day AS day, toUInt32(toUInt32(dd.day) * 86400 + 60 * nn.number) AS m
            FROM (SELECT DISTINCT day FROM {table} WHERE {where}) AS dd
            CROSS JOIN numbers(1440) AS nn
        ) g
        LEFT JOIN (
            SELECT day, m, sum(delta) AS d FROM {table} WHERE {where} GROUP BY day, m
        ) e ON g.day = e.day AND g.m = e.m
    )
    """

print("=== 1. GLOBAL diff vs ground truth ===")
t0 = time.time()
print(q(f"""
WITH serving AS ({series_sql('ch.concurrency_deltas_global')}),
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
"""), f"({time.time()-t0:.2f}s)")

print("=== 1b. peak sanity ===")
print(q(f"""
WITH serving AS ({series_sql('ch.concurrency_deltas_global')})
SELECT m AS epoch, concurrent FROM serving ORDER BY concurrent DESC, m LIMIT 3
"""))
print("expected: 2970 @ 1785063360 (10:56 UTC), 2965 @ 1785063540, 2940 @ 1785063480")

print("=== 2. SLICE checks vs I6 reference numbers ===")
for p, expect in [("ANDROID_PHONE", "1818 @ 10:56"), ("IPHONE", "362 @ 10:56"),
                  ("JIO_ANDROID_TV", "230 @ 10:59; 219 @ 10:56")]:
    r = q(f"""
    WITH serving AS ({series_sql('ch.concurrency_deltas', f"platform = '{p}'")})
    SELECT
        maxIf(concurrent, m = 1785063360) AS at_1056,
        maxIf(concurrent, m = 1785063540) AS at_1059,
        max(concurrent) AS peak
    FROM serving
    """, "CSV")
    print(f"  {p}: at_10:56, at_10:59, peak = {r.strip()}   expected {expect}")

print("=== 3. LATENCY: serving queries (dashboard shapes) ===")
timed("global peak+avg, hot day, minute grain", f"""
    WITH serving AS ({series_sql('ch.concurrency_deltas_global', "day = toDate(20660)")})
    SELECT max(concurrent) AS peak, round(avg(concurrent), 1) AS avg FROM serving""")
timed("platform slice peak (JIO), hot day", f"""
    WITH serving AS ({series_sql('ch.concurrency_deltas', "platform = 'JIO_ANDROID_TV' AND day = toDate(20660)")})
    SELECT max(concurrent) FROM serving""")
timed("content top-10 by peak, hot day", f"""
    WITH per_min AS (
        SELECT content_id, m, sum(delta) AS d
        FROM ch.concurrency_deltas WHERE day = toDate(20660)
        GROUP BY content_id, m
    ), series AS (
        SELECT content_id, m,
               sum(d) OVER (PARTITION BY content_id ORDER BY m
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c
        FROM per_min
    )
    SELECT content_id, max(c) AS peak FROM series GROUP BY content_id
    ORDER BY peak DESC LIMIT 10""")
timed("video_type=live slice peak, hot day", f"""
    WITH serving AS ({series_sql('ch.concurrency_deltas', "video_type = 'live' AND day = toDate(20660)")})
    SELECT max(concurrent) FROM serving""")
timed("hourly avg-of-minute + peak, hot day (hour grain)", f"""
    WITH serving AS ({series_sql('ch.concurrency_deltas_global', "day = toDate(20660)")})
    SELECT intDiv(m, 3600) * 3600 AS hour, max(concurrent) AS peak, round(avg(concurrent),1) AS avg
    FROM serving GROUP BY hour ORDER BY hour DESC LIMIT 5""")
print("  -- rows the serving layer reads --")
timed("deltas_global rows, hot day", "SELECT count() FROM ch.concurrency_deltas_global WHERE day = toDate(20660)")
timed("deltas (dim) rows, hot day", "SELECT count() FROM ch.concurrency_deltas WHERE day = toDate(20660)")
timed("BRUTE FORCE equivalent (what we avoid): raw scan for one global peak", """
    WITH cover AS (
        SELECT DISTINCT video_session_id, arrayJoin([m0, m0+60, m0+120]) AS m
        FROM (SELECT video_session_id,
                     toUInt32(intDiv(intDiv(ts_ms,1000),60)*60) AS m0
              FROM ch.raw_events
              WHERE event_type IN ('VideoSessionStart','VideoPlay','VideoHeartbeat','AppForegrounded'))
    )
    SELECT max(c) FROM (SELECT m, count() AS c FROM cover GROUP BY m)""")

print("=== 4. IDEMPOTENCE: second compactor run must emit nothing ===")
before = q("SELECT count() FROM ch.concurrency_deltas_global", "CSV").strip()
dt, _ = compact(s)
after = q("SELECT count() FROM ch.concurrency_deltas_global", "CSV").strip()
print(f"  rows before={before} after={after} (must be equal); compact time {dt:.2f}s")
