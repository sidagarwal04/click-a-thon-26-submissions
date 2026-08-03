#!/usr/bin/env python3
"""
!! SEMANTICALLY STALE — DO NOT USE AS A CORRECTNESS REFERENCE !!

This file has NO PLAYBACK AXIS: no pause, resume, or error handling
anywhere. It therefore counts paused-in-foreground sessions as active,
which contradicts:
    solution/policy.yaml                          (the source of truth)
    pipeline/sql/011_build_active_intervals.sql   (gates playing_state = 1)
    docs/DECISIONS.md D1                          (revised 2026-08-02)

Its "validated against brute-force ground truth" claim below is true but
circular: prototype/reference/ground_truth_generator.py had no playback
axis either, so the two agreed with each other while both diverged from
the shipped SQL. Agreement proved the encoding faithful; it proved
nothing about the semantics.

It also cannot run — chdb is not installed in this environment.

The canonical definition now lives in SQL and is verified on the live
service:
    prototype/reference/ground_truth_generator.sql   (the oracle)
    pipeline/sql/011_build_active_intervals.sql      (analytics)
    pipeline/sql/030_session_live_now.sql            (live)
All three agree: at 2026-07-26 10:56 UTC the live path and the analytics
path both return 2285 (pipeline/sql/032_live_verify.sql, V6).

To revive this file, add a playing-state carry mirroring `playing_setter`
in 011 (stop = pause|error|session_end, start = play|resume) and
re-validate against the regenerated CSV.
---------------------------------------------------------------------

Foreground-only concurrency pipeline — ClickHouse prototype (chdb).

Implements the two-tier design from docs/DESIGN.md:
  raw_events  --insert-time MV-->  session_state (AggregatingMergeTree, commutative states)
  session_state --compactor-->     concurrency_deltas / concurrency_deltas_global (SummingMergeTree)
  serving queries: day-anchored cumulative sum over deltas.

Semantics (the correctness contract, validated against brute-force ground truth):
  - activity events: VideoSessionStart, VideoPlay, VideoHeartbeat, AppForegrounded
  - an activity event at t covers minutes {m0, m0+60, m0+120} (T = 120s liveness),
    clamped to the unit's [first-event-minute, last-event-minute] span
  - a minute M is excluded if some AppBackgrounded at b <= M has its next
    AppForegrounded f >= M+60 (unclosed bg => excluded to span end)
  - dimension slices are event-attributed: the unit of presence for the dimension
    table is (video_session_id, platform, content_id); the global table uses
    (video_session_id) with bg/fg pairing across all of the session's events
All minute arithmetic in epoch seconds (timezone-proof).
"""
import time
import chdb.session as chs

DATA = "/private/tmp/claude-501/-Users-dahiya-Work-sonyliv/fb664459-f44c-49cf-b6a2-4edcd8a9c7a7/scratchpad"
ACTIVITY = "('VideoSessionStart','VideoPlay','VideoHeartbeat','AppForegrounded')"
T_LIVENESS = 120  # seconds; evidence: legit-gap p99=40.01s, cut-rate 0.201% at 120s

DDL = f"""
CREATE DATABASE IF NOT EXISTS ch ENGINE = Atomic;

-- ============ landing table ============
CREATE TABLE IF NOT EXISTS ch.raw_events (
    event_date        Date MATERIALIZED toDate(
        fromUnixTimestamp64Milli(toInt64(ts_ms), 'UTC'), 'UTC'
    ),
    ts_ms             UInt64,
    user_id           String,
    video_session_id  String,
    session_start_ms  UInt64,
    content_id        UInt64,
    event_type        LowCardinality(String),
    event             LowCardinality(String),
    platform          LowCardinality(String),
    country           LowCardinality(String),
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String)
) ENGINE = MergeTree
PARTITION BY event_date
ORDER BY (video_session_id, ts_ms);

-- ============ Tier 1: unit state (order/duplicate-insensitive) ============
-- unit = (video_session_id, platform, content_id): event-attributed slice semantics
CREATE TABLE IF NOT EXISTS ch.session_state (
    video_session_id  String,
    platform          LowCardinality(String),
    content_id        UInt64,
    user_id           SimpleAggregateFunction(anyLast, String),
    first_m           SimpleAggregateFunction(min, UInt32),   -- minute of first event (epoch s)
    last_m            SimpleAggregateFunction(max, UInt32),   -- minute of last event
    end_ts            SimpleAggregateFunction(max, UInt64),   -- max VideoSessionEnd ts_ms (0 = open)
    last_activity_ts  SimpleAggregateFunction(max, UInt64),
    act_minutes       AggregateFunction(groupUniqArray, UInt32),  -- distinct activity-event minutes
    bg_ts             AggregateFunction(groupUniqArray, UInt64),
    fg_ts             AggregateFunction(groupUniqArray, UInt64),
    dirty_seq         SimpleAggregateFunction(max, UInt64)    -- ingest sequence, drives compaction
) ENGINE = AggregatingMergeTree
ORDER BY (video_session_id, platform, content_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS ch.mv_session_state TO ch.session_state AS
SELECT
    video_session_id,
    platform,
    content_id,
    anyLast(user_id)                                            AS user_id,
    min(toUInt32(intDiv(intDiv(ts_ms, 1000), 60) * 60))         AS first_m,
    max(toUInt32(intDiv(intDiv(ts_ms, 1000), 60) * 60))         AS last_m,
    maxIf(ts_ms, event_type = 'VideoSessionEnd')                AS end_ts,
    maxIf(ts_ms, event_type IN {ACTIVITY})                      AS last_activity_ts,
    groupUniqArrayStateIf(toUInt32(intDiv(intDiv(ts_ms,1000),60)*60), event_type IN {ACTIVITY}) AS act_minutes,
    groupUniqArrayStateIf(ts_ms, event_type = 'AppBackgrounded') AS bg_ts,
    groupUniqArrayStateIf(ts_ms, event_type = 'AppForegrounded') AS fg_ts,
    max(toUInt64(toUnixTimestamp64Milli(now64(3, 'UTC'))))       AS dirty_seq  -- ingest wall-clock: watermark driver
FROM ch.raw_events
GROUP BY video_session_id, platform, content_id;

-- ============ Tier 2: serving deltas ============
CREATE TABLE IF NOT EXISTS ch.concurrency_deltas (
    day        Date,
    platform   LowCardinality(String),
    content_id UInt64,
    video_type LowCardinality(String),
    m          UInt32,          -- minute (epoch s) of the delta edge
    delta      Int32
) ENGINE = SummingMergeTree(delta)
PARTITION BY day
ORDER BY (platform, content_id, m);

CREATE TABLE IF NOT EXISTS ch.concurrency_deltas_global (
    day   Date,
    m     UInt32,
    delta Int32
) ENGINE = SummingMergeTree(delta)
PARTITION BY day
ORDER BY m;

-- memo of what each unit last published (for incremental corrections)
CREATE TABLE IF NOT EXISTS ch.emitted_intervals (
    scope             LowCardinality(String),  -- 'dim' or 'global'
    video_session_id  String,
    platform          LowCardinality(String),  -- '' for global scope
    content_id        UInt64,                  -- 0 for global scope
    intervals         Array(Tuple(UInt32, UInt32)),  -- [start_m, end_m_exclusive)
    version           UInt64
) ENGINE = ReplacingMergeTree(version)
ORDER BY (scope, video_session_id, platform, content_id);

-- ============ content dictionary ============
CREATE TABLE IF NOT EXISTS ch.content (
    content_id UInt64, title String, video_type LowCardinality(String), category LowCardinality(String)
) ENGINE = MergeTree ORDER BY content_id;
"""

# Interval reconstruction, shared by both scopes.
# Input columns required: act_arr (Array(UInt32) minutes), bg_arr, fg_arr (Array(UInt64) ms),
# first_m, last_m (UInt32). Produces `runs` = Array(Tuple(UInt32,UInt32)) of [start, end) minute runs.
INTERVALS_EXPR = """
    arraySort(arrayDistinct(arrayFlatten(arrayMap(mm -> [mm, mm + 60, mm + 120], act_arr)))) AS cov_raw,
    arrayFilter(mm -> mm >= first_m AND mm <= last_m, cov_raw) AS covered,
    arraySort(bg_arr) AS bgs,
    arraySort(fg_arr) AS fgs,
    /* for each bg, the next fg strictly after it (sentinel: far future) */
    arrayMap(b -> (
        toUInt32(greatest(intDiv(intDiv(b, 1000) + 59, 60) * 60, toUInt64(first_m))),
        toUInt32(least(
            intDiv(intDiv(arrayFirst(f -> f > b, arrayConcat(fgs, [toUInt64(9000000000000)])), 1000) - 60, 60) * 60,
            toUInt64(last_m)))
    ), bgs) AS excl_ranges,
    arrayFilter(mm -> NOT arrayExists(r -> mm >= r.1 AND mm <= r.2, excl_ranges), covered) AS act,
    /* consecutive-minute runs -> [start, end) intervals */
    arrayFilter((mm, i) -> i = 1 OR mm != (act[i-1] + 60), act, arrayEnumerate(act)) AS run_starts,
    arrayFilter((mm, i) -> i = length(act) OR (act[i+1]) != mm + 60, act, arrayEnumerate(act)) AS run_ends,
    arrayMap(s, e -> (s, e + 60), run_starts, run_ends) AS runs
"""

def day_split_deltas(runs_col: str) -> str:
    """SQL fragment: explode [start,end) runs into day-split delta triples
    (day_num UInt32 = days-since-epoch, minute UInt32, delta Int32)."""
    return f"""
    arrayFlatten(arrayMap(r ->
        arrayFlatten(arrayMap(d ->
            [(toUInt32(intDiv(d, 86400)), greatest(r.1, toUInt32(d)), toInt32(1)),
             (toUInt32(intDiv(d, 86400)), least(r.2, toUInt32(d + 86400)), toInt32(-1))],
            range(toUInt64(intDiv(r.1, 86400) * 86400), toUInt64(intDiv(r.2 - 1, 86400) * 86400 + 86400), 86400)
        )),
    {runs_col}))
    """

def open_session(name="proto_pipeline"):
    return chs.Session(f"{DATA}/{name}")

def create_all(s):
    for stmt in DDL.split(";"):
        if stmt.strip():
            s.query(stmt)

def load_content(s):
    s.query(f"""
        INSERT INTO ch.content
        SELECT toUInt64(assumeNotNull(content_id)),
               assumeNotNull(title),
               if(assumeNotNull(video_type) = '', 'unknown', assumeNotNull(video_type)),
               assumeNotNull(category)
        FROM file('{DATA}/content.parquet')
    """)

def load_events(s, where="1"):
    """Normalizing ingest (the same SELECT works for the unseen-day CSV)."""
    s.query(f"""
        INSERT INTO ch.raw_events
        SELECT
            toUInt64(assumeNotNull(event_timestamp))              AS ts_ms,
            assumeNotNull(user_id)                                AS user_id,
            assumeNotNull(video_session_id)                       AS video_session_id,
            toUInt64(assumeNotNull(session_start_epoch))          AS session_start_ms,
            toUInt64(assumeNotNull(content_id))                   AS content_id,
            assumeNotNull(event_type)                             AS event_type,
            assumeNotNull(event)                                  AS event,
            assumeNotNull(platform)                               AS platform,
            assumeNotNull(country)                                AS country,
            assumeNotNull(app_version)                            AS app_version,
            lower(extract(assumeNotNull(audio_language), '^[a-zA-Z]*'))    AS audio_language,
            lower(extract(assumeNotNull(subtitle_language), '^[a-zA-Z]*')) AS subtitle_language,
            assumeNotNull(player_version)                         AS player_version
        FROM file('{DATA}/raw_events.parquet')
        WHERE {where}
    """)

def compact(s, scope="both", since_seq=0):
    """Watermark compactor: rebuild foreground intervals for units dirtied since
    `since_seq` (0 = all) and emit correction deltas (new - old) against the
    emitted_intervals memo. Returns (elapsed_seconds, new_watermark)."""
    t0 = time.time()
    new_wm = int(str(s.query(
        "SELECT coalesce(max(dirty_seq), 0) FROM ch.session_state", "CSV")).strip() or 0)
    jobs = []
    if scope in ("dim", "both"):
        jobs.append(("dim",
            "video_session_id, platform, content_id",
            "ch.concurrency_deltas",
            "toDate(d.1) AS day, platform, content_id, dictGetOrDefault('ch.dict_content','video_type', content_id, 'unknown') AS video_type, d.2 AS m, d.3 AS delta"))
    if scope in ("global", "both"):
        jobs.append(("global",
            "video_session_id",
            "ch.concurrency_deltas_global",
            "toDate(d.1) AS day, d.2 AS m, d.3 AS delta"))

    for scope_name, unit_key, target, emit_cols in jobs:
        # 1. compute fresh intervals for all units (prototype: full pass; production:
        #    WHERE dirty_seq > watermark — identical SQL, bounded input)
        s.query(f"""
            CREATE OR REPLACE TABLE ch.fresh_{scope_name} ENGINE = Memory AS
            WITH merged AS (
                SELECT video_session_id,
                       {"platform, content_id," if scope_name == "dim" else ""}
                       min(first_m) AS first_m, max(last_m) AS last_m,
                       groupUniqArrayMerge(act_minutes) AS act_arr,
                       groupUniqArrayMerge(bg_ts) AS bg_arr,
                       groupUniqArrayMerge(fg_ts) AS fg_arr
                FROM ch.session_state
                GROUP BY {unit_key}
                HAVING max(dirty_seq) > {since_seq}
            )
            SELECT video_session_id,
                   {"platform, content_id," if scope_name == "dim" else "'' AS platform, toUInt64(0) AS content_id,"}
                   runs
            FROM (SELECT *, {INTERVALS_EXPR} FROM merged)
        """)
        # 2. correction deltas = emit(new) - emit(old)  [old = memo]
        s.query(f"""
            INSERT INTO {target}
            SELECT {emit_cols}
            FROM (
                SELECT s.video_session_id AS video_session_id,
                       s.platform AS platform, s.content_id AS content_id,
                       arrayJoin(arrayConcat(
                           {day_split_deltas("s.runs")},
                           arrayMap(x -> (x.1, x.2, -x.3), {day_split_deltas("e.intervals")})
                       )) AS d
                FROM ch.fresh_{scope_name} s
                LEFT JOIN (
                    SELECT video_session_id, platform, content_id, intervals
                    FROM ch.emitted_intervals FINAL WHERE scope = '{scope_name}'
                ) e USING (video_session_id, platform, content_id)
                WHERE s.runs != e.intervals
            )
            WHERE d.3 != 0
        """)
        # 3. update memo
        s.query(f"""
            INSERT INTO ch.emitted_intervals
            SELECT '{scope_name}', video_session_id, platform, content_id, runs,
                   toUInt64(toUnixTimestamp64Milli(now64(3, 'UTC')))
            FROM ch.fresh_{scope_name}
        """)
    return time.time() - t0, new_wm

def create_dict(s):
    s.query("""
        CREATE DICTIONARY IF NOT EXISTS ch.dict_content (
            content_id UInt64, title String, video_type String, category String
        ) PRIMARY KEY content_id
        SOURCE(CLICKHOUSE(DATABASE 'ch' TABLE 'content'))
        LAYOUT(HASHED()) LIFETIME(MIN 0 MAX 0)
    """)

if __name__ == "__main__":
    s = open_session()
    t0 = time.time()
    create_all(s)
    load_content(s)
    create_dict(s)
    print(f"DDL + content: {time.time()-t0:.2f}s")

    t0 = time.time()
    load_events(s)
    print(f"ingest (raw + Tier-1 MV): {time.time()-t0:.2f}s")
    print(s.query("SELECT count() FROM ch.raw_events", "CSV"))
    print(s.query("SELECT count() FROM ch.session_state", "CSV"))

    dt, wm = compact(s)
    print(f"compactor (full first pass, both scopes): {dt:.2f}s")
    print(s.query("SELECT count(), sum(delta) FROM ch.concurrency_deltas_global", "CSV"))
