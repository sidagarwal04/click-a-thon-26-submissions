-- =====================================================================
-- Click-a-thon 2026 — SonyLIV: foreground-only concurrency
-- Team: RealTime Raiders
-- Revision 5 — no query parameters anywhere, ingest everything
--
-- The ClickHouse Cloud console scans the WHOLE file for {param} tokens
-- and refuses to run until every one has a value. This revision has
-- zero parameters: run it top to bottom.
--
-- Probe results this schema is built on:
--   n_sessions  10,866    64-char, not uuid, not numeric
--   n_users      9,618    64-char, not uuid, not numeric
--   n_content    3,357    NUMERIC
--   has_subsecond  904,654 of ~905K rows
--
-- RUN ORDER MATTERS. Materialized views only fire on rows inserted
-- AFTER they are created. Sections 1-4 must complete before section 5.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS liv;
USE liv;


-- =====================================================================
-- SECTION 0 — TEARDOWN (idempotent re-run)
-- =====================================================================

DROP VIEW IF EXISTS liv.mv_conc_minute;
DROP VIEW IF EXISTS liv.mv_session_minute;
DROP VIEW IF EXISTS liv.mv_events_sample;
DROP VIEW IF EXISTS liv.concurrency_minute;

DROP TABLE IF EXISTS liv.conc_minute;
DROP TABLE IF EXISTS liv.session_minute;
DROP TABLE IF EXISTS liv.session_minute_ref;
DROP TABLE IF EXISTS liv.events_raw;
DROP TABLE IF EXISTS liv.events_landing;

DROP DICTIONARY IF EXISTS liv.content_dict;
DROP TABLE IF EXISTS liv.content_join;
DROP TABLE IF EXISTS liv.content;

-- DROP VIEW works for materialized views too. If the refreshable MV is
-- mid-refresh: SYSTEM STOP VIEW liv.mv_conc_minute; first.


-- =====================================================================
-- SECTION 1 — TYPE DECISIONS AND WHY
-- =====================================================================
--
-- video_session_id / user_id  ->  UInt64 via cityHash64()
--   64-byte opaque strings used purely as identity tokens. Nothing in
--   the model ever outputs a session or user ID — they exist only to be
--   counted distinctly. The identity must survive; the value need not.
--   8 fixed bytes instead of 64, and every comparison in the FINAL
--   merge and every GROUP BY becomes an integer compare.
--
--   Collisions: 10,866 values against 2^64 is ~3e-12. Reaches ~2.7% at
--   a billion sessions, which is where you move to cityHash128/UInt128.
--
--   REJECTED LowCardinality(String): it would work beautifully at this
--   size (10,866 distinct is its sweet spot) but session-ID cardinality
--   is UNBOUNDED as data grows, and the per-part dictionary becomes the
--   dominant cost at 100x. Hashing is size-invariant.
--
--   Original 64-char IDs survive in events_raw (sample) for debugging.
--
-- content_id  ->  UInt32
--   Numeric, 3,357 distinct. 4 fixed bytes in the sort key of BOTH
--   session_minute and conc_minute. Best single type win here.
--
-- event_timestamp  ->  DateTime64(3) in events_raw
--   904,654 of ~905K rows carry sub-second precision. DateTime would
--   silently truncate. session_minute buckets to minutes, where
--   sub-second is meaningless.
--
-- minute  ->  DateTime + DoubleDelta. Sort-key prefix, ascending,
--   compresses to ~1 byte/row.
--
-- sessions  ->  UInt32. Caps at 4.29 billion concurrent sessions per
--   dimension tuple. Never binds.
--
-- users  ->  AggregateFunction(uniqExact, UInt64). Exact, because
--   correctness is scored. Cheap now the key is 8 bytes not 64.
--
-- event_type  ->  LowCardinality(String), NOT Enum8. Seven documented
--   values makes Enum8 tempting, but an unseen-day file with an eighth
--   value fails the insert outright. LowCardinality degrades gracefully.


-- =====================================================================
-- SECTION 2 — CONTENT DIMENSION + LOOKUP
-- =====================================================================
-- Enrichment happens inside a materialized view, which only sees the
-- block being inserted. A JOIN per block is slow and fragile. An
-- in-memory hash probe is O(1) and matters MORE at scale, not less.

CREATE TABLE content
(
    content_id  UInt32,
    title       String CODEC(ZSTD(1)),
    video_type  LowCardinality(String),
    category    LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY content_id;

INSERT INTO content
SELECT toUInt32OrZero(content_id), title, video_type, category
FROM url(
  'https://media.githubusercontent.com/media/sidagarwal04/click-a-thon-2026/refs/heads/main/SonyLiv/data/ch-hackathon-content-data.csv',
  'CSVWithNames',
  'content_id String, title String, video_type String, category String'
);

-- Must return 0. The probe confirmed numeric IDs in the EVENTS; this
-- confirms the catalogue agrees.
SELECT countIf(content_id = 0) AS non_numeric_content_ids FROM content;


-- ---------------------------------------------------------------------
-- 2a. Join engine — no credentials required
-- ---------------------------------------------------------------------
-- ClickHouse Cloud does not run you as `default`, and a CLICKHOUSE
-- dictionary source assumes `default` unless given USER/PASSWORD. The
-- Join engine gives the same in-memory hash probe with no auth and no
-- password sitting in the DDL.

CREATE TABLE content_join
(
    content_id  UInt32,
    title       String,
    video_type  String,
    category    String
)
ENGINE = Join(ANY, LEFT, content_id);

INSERT INTO content_join SELECT content_id, title, video_type, category FROM content;

-- Trade-off: no LIFETIME, so no auto-refresh. Re-insert if the catalogue
-- changes. Irrelevant for a 24-hour run on a static catalogue.


-- =====================================================================
-- SECTION 3 — LANDING TABLE (Null engine — nothing is stored)
-- =====================================================================
-- Persisting the full raw event stream alongside session_minute is the
-- single largest storage mistake available in this problem: two full
-- copies of the same data. The Null engine discards rows once the
-- materialized views have consumed the inserted block.
--
-- Column types here cost ZERO storage — they only affect parse cost, so
-- they stay permissive. This layer has to swallow whatever the unseen
-- day looks like. All casting happens on the way OUT, in the MVs.

CREATE TABLE events_landing
(
    event_timestamp      DateTime64(3, 'UTC'),
    video_session_id     String,
    user_id              String,
    content_id           String,
    event_type           LowCardinality(String),
    event                LowCardinality(String),
    platform             LowCardinality(String),
    app_version          LowCardinality(String),
    country              LowCardinality(String),
    audio_language       LowCardinality(String),
    subtitle_language    LowCardinality(String),
    player_version       LowCardinality(String),
    session_start_epoch  DateTime('UTC')
)
ENGINE = Null;


-- =====================================================================
-- SECTION 4 — TIER 1: session_minute (durable detail tier)
-- =====================================================================
-- One row per (session, minute) that was actively watching. Row count
-- is ~= heartbeat count, because heartbeats already arrive once per
-- minute. NOT a per-minute explosion of session spans — storage grows
-- linearly with beats, the property that survives 100x.
--
-- Row width after the type work: ~27 bytes before compression, against
-- ~140 with String IDs.

CREATE TABLE session_minute
(
    minute            DateTime('UTC') CODEC(DoubleDelta, ZSTD(1)),
    platform          LowCardinality(String),
    country           LowCardinality(String),
    video_type        LowCardinality(String),
    content_id        UInt32 CODEC(ZSTD(1)),
    video_session_id  UInt64 CODEC(ZSTD(1)),
    user_id           UInt64 CODEC(ZSTD(1))
)
ENGINE = ReplacingMergeTree
PARTITION BY toDate(minute)
ORDER BY (minute, platform, country, video_type, content_id, video_session_id)
TTL minute + INTERVAL 30 DAY;

-- The ORDER BY is exactly the grain being deduplicated, which makes
-- FINAL cheap in section 6: a streaming merge over pre-sorted data
-- rather than a hash-set build.
--
-- NOTE: video_session_id here is ALREADY cityHash64 of the original.
-- To sample it, filter on  video_session_id % 100 = 0  — NOT
-- cityHash64(video_session_id) % 100 = 0, which would hash twice and
-- silently select a different set of sessions.


CREATE MATERIALIZED VIEW mv_session_minute TO session_minute AS
WITH
    toUInt32OrZero(content_id) AS cid,
    joinGet('liv.content_join', 'video_type', cid) AS vt
SELECT
    toStartOfMinute(event_timestamp) + toIntervalMinute(m) AS minute,
    platform,
    country,
    if(vt = '', 'unknown', vt)   AS video_type,
    cid                          AS content_id,
    cityHash64(video_session_id) AS video_session_id,
    cityHash64(user_id)          AS user_id
FROM events_landing
ARRAY JOIN range(0, 1) AS m
WHERE event_type IN ('VideoHeartbeat', 'VideoPlay', 'VideoSessionStart', 'AppForegrounded');

-- The if() wraps joinGet because it returns an empty string on a miss
-- rather than a default you can specify.
--
-- Two things doing the real work:
--
-- 1. The WHERE clause IS the foreground filter. AppBackgrounded and
--    VideoError emit nothing, and a backgrounded session stops beating,
--    so its minutes simply never appear. The gap rule needs no code —
--    it is the consequence of not filling gaps.
--
-- 2. range(0, 1) is the beat-coverage knob. Cadence is documented as
--    60s, so one beat covers one minute and this fans out 1:1. If the
--    measured cadence is 120s, change to range(0, 2).


-- ---------------------------------------------------------------------
-- 4b. Sampled raw — original IDs, for the reference path and debugging
-- ---------------------------------------------------------------------
-- The ONLY place the original 64-char IDs survive. Deliberate: it is a
-- fraction of the data, and it lets you trace a specific session when a
-- number looks wrong.
--
-- session_start_epoch is absent: nothing in the model reads it.

CREATE TABLE events_raw
(
    event_timestamp      DateTime64(3, 'UTC') CODEC(DoubleDelta, ZSTD(1)),
    video_session_id     String CODEC(ZSTD(1)),
    user_id              String CODEC(ZSTD(1)),
    content_id           UInt32 CODEC(ZSTD(1)),
    event_type           LowCardinality(String),
    event                LowCardinality(String),
    platform             LowCardinality(String),
    app_version          LowCardinality(String),
    country              LowCardinality(String),
    audio_language       LowCardinality(String),
    subtitle_language    LowCardinality(String),
    player_version       LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toDate(event_timestamp)
ORDER BY (video_session_id, event_timestamp)
TTL toDateTime(event_timestamp) + INTERVAL 7 DAY;

CREATE MATERIALIZED VIEW mv_events_sample TO events_raw AS
SELECT
    event_timestamp,
    video_session_id,
    user_id,
    toUInt32OrZero(content_id) AS content_id,
    event_type, event, platform, app_version, country,
    audio_language, subtitle_language, player_version
FROM events_landing
WHERE cityHash64(video_session_id) % 10 = 0;

-- 10% here, not 1%. Whole sessions, not whole events — hashing on
-- session id keeps every sampled session complete, which the window
-- functions in section 8 require. With only 10,866 sessions in the
-- provided data, 1% would be ~109 sessions: too thin for a meaningful
-- correctness comparison. Change to % 100 = 0 for the unseen day.


-- =====================================================================
-- SECTION 5 — INGEST EVERYTHING
-- =====================================================================
-- Parse in flight. No String staging layer: it existed for exploration
-- and would double write volume on the unseen day.
--
-- The parser handles epoch seconds, epoch millis, and ISO/text. Validate
-- once here, then reuse verbatim on the unseen day.

SET max_insert_threads = 16;
SET min_insert_block_size_rows = 1048576;
SET min_insert_block_size_bytes = 268435456;
SET max_insert_block_size = 1048576;

INSERT INTO events_landing
SELECT
    multiIf(
        match(event_timestamp, '^\d{13}$'), toDateTime64(toUInt64(event_timestamp) / 1000, 3, 'UTC'),
        match(event_timestamp, '^\d{10}$'), toDateTime64(toUInt32(event_timestamp), 3, 'UTC'),
        parseDateTime64BestEffortOrZero(event_timestamp, 3, 'UTC')
    ) AS event_timestamp,
    video_session_id, user_id, content_id, event_type, event,
    platform, app_version, country, audio_language, subtitle_language, player_version,
    multiIf(
        match(session_start_epoch, '^\d{13}$'), toDateTime(toUInt64(session_start_epoch) / 1000, 'UTC'),
        match(session_start_epoch, '^\d{10}$'), toDateTime(toUInt32(session_start_epoch), 'UTC'),
        parseDateTimeBestEffortOrZero(session_start_epoch, 'UTC')
    ) AS session_start_epoch
FROM url(
  'https://media.githubusercontent.com/media/sidagarwal04/click-a-thon-2026/refs/heads/main/SonyLiv/data/ch-hackathon-raw-data.csv',
  'CSVWithNames',
  'video_session_id String, user_id String, content_id String, event_type String, event String, event_timestamp String, platform String, app_version String, country String, audio_language String, subtitle_language String, player_version String, session_start_epoch String'
);

-- For a large unseen drop, swap url() for s3() with a glob so ClickHouse
-- parallelises across objects:
--   FROM s3('https://.../unseen-day/*.parquet', 'Parquet')


-- ---------------------------------------------------------------------
-- 5a. Post-load checks — run all four before continuing
-- ---------------------------------------------------------------------

-- Both must be 0.
SELECT
    countIf(event_timestamp = toDateTime64(0, 3, 'UTC')) AS bad_timestamps,
    countIf(content_id = 0)                              AS bad_content_ids
FROM events_raw;

-- Must be > 0. If it is 0, the MV was created after the load — re-run
-- section 5's INSERT.
SELECT count() AS session_minute_rows, min(minute), max(minute) FROM session_minute;

-- Every event_type / event value you must handle.
SELECT event_type, event, count() AS c
FROM events_raw GROUP BY event_type, event ORDER BY c DESC;

-- Do dimensions change mid-session? All three must be 0, or the
-- "concurrency is additive across dimensions" argument in section 7
-- breaks and dims must be pinned at session grain.
SELECT
    countIf(np > 1) AS platform_switchers,
    countIf(nc > 1) AS country_switchers,
    countIf(nk > 1) AS content_switchers
FROM (
    SELECT video_session_id,
           uniqExact(platform)   AS np,
           uniqExact(country)    AS nc,
           uniqExact(content_id) AS nk
    FROM events_raw GROUP BY video_session_id
);

-- Heartbeat cadence — sets the range(0, N) knob in section 4.
SELECT quantiles(0.5, 0.9, 0.99)(gap) AS cadence_seconds
FROM (
    SELECT dateDiff('second', event_timestamp,
             leadInFrame(event_timestamp) OVER (
               PARTITION BY video_session_id ORDER BY event_timestamp
               ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING)) AS gap
    FROM events_raw WHERE event_type = 'VideoHeartbeat'
) WHERE gap > 0;


-- =====================================================================
-- SECTION 6 — TIER 2: conc_minute (the serving layer)
-- =====================================================================
-- Grain: minute x every dimension. Peak is NEVER stored, because
-- platform+content and platform+country peak at different minutes.
-- Filter -> sum() across dims within each minute -> max()/avg() across
-- minutes. Sum first, then max. Not interchangeable.

CREATE TABLE conc_minute
(
    minute      DateTime('UTC') CODEC(DoubleDelta, ZSTD(1)),
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  UInt32 CODEC(ZSTD(1)),
    sessions    SimpleAggregateFunction(max, UInt32),
    users       AggregateFunction(uniqExact, UInt64),
    INDEX bf_content content_id TYPE bloom_filter(0.01) GRANULARITY 4
)
ENGINE = AggregatingMergeTree
PARTITION BY toDate(minute)
ORDER BY (minute, platform, country, video_type, content_id);

-- Why max() and not sum(): both the backfill and the refresh below
-- re-emit the same (minute, dims) rows. Sum semantics double-counts on
-- every re-run. Max is idempotent — re-emitting the same value is a
-- no-op, and when a late heartbeat pushes a minute from 300000 to
-- 300001, max wins. Valid only because concurrency for a finalized
-- minute can never DECREASE: late arrivals only ever add sessions.
-- Also makes the backfill safely re-runnable when a load fails halfway.
--
-- users: uniqExact over UInt64. Exact, because correctness is scored.
-- If user cardinality ever grows past ~1M, swap to
--   AggregateFunction(uniqCombined64(12), UInt64)
-- with uniqCombined64State(12) / uniqCombined64Merge(12).


-- ---------------------------------------------------------------------
-- 6a. BACKFILL — everything, no parameters
-- ---------------------------------------------------------------------
SET optimize_aggregation_in_order = 1;

INSERT INTO conc_minute
SELECT
    minute, platform, country, video_type, content_id,
    count()                 AS sessions,
    uniqExactState(user_id) AS users
FROM session_minute FINAL
GROUP BY minute, platform, country, video_type, content_id;

-- FINAL + count(), NOT uniqExact(video_session_id).
-- session_minute is already sorted by exactly the grain being
-- deduplicated, so FINAL is a streaming merge over pre-sorted data.
-- uniqExact would build a hash set per group held in memory,
-- proportional to concurrent-session cardinality — the thing that
-- explodes at 100x. FINAL is exact AND memory-flat.
-- optimize_aggregation_in_order applies because the GROUP BY is a
-- sort-key prefix.
--
-- user_id is already cityHash64'd, so uniqExactState takes it directly.
--
-- AT PETABYTE SCALE: scope this per day and drive it from a shell loop,
-- one statement per date, so it parallelises and a failure costs one
-- partition rather than the whole run:
--   ... FROM session_minute FINAL WHERE toDate(minute) = '2026-08-01' ...

-- Verify.
SELECT count() AS rows, min(minute), max(minute), max(sessions) AS busiest_tuple
FROM conc_minute;


-- ---------------------------------------------------------------------
-- 6b. LIVE TAIL — refreshable MV for the streaming demo
-- ---------------------------------------------------------------------
SET enable_refreshable_materialized_view = 1;
-- Older builds: SET allow_experimental_refreshable_materialized_view = 1;

CREATE MATERIALIZED VIEW mv_conc_minute
REFRESH EVERY 30 SECOND APPEND TO conc_minute AS
SELECT
    minute, platform, country, video_type, content_id,
    count()                 AS sessions,
    uniqExactState(user_id) AS users
FROM session_minute FINAL
WHERE minute >= (SELECT max(minute) - INTERVAL 20 MINUTE FROM session_minute)
GROUP BY minute, platform, country, video_type, content_id;

-- DATA-TIME WATERMARK, not now(). Bulk-ingested data has no relationship
-- to wall clock. `minute >= now() - INTERVAL 20 MINUTE` matches zero
-- rows whenever event timestamps are not from today, and it fails
-- SILENTLY — pipeline reports healthy, table stays empty.
--
-- REFRESHABLE, not incremental. An incremental MV chained off
-- session_minute would fire on INSERTED rows rather than deduplicated
-- ones, counting every repeat heartbeat again.
--
-- Only the trailing 20 data-minutes churn. Finalized minutes are written
-- once by 6a and never touched. That is the "absorbs updates
-- incrementally, without a full rebuild" requirement.


-- =====================================================================
-- SECTION 7 — BENCHMARK QUERIES
-- =====================================================================

-- 7a. Base view: per-minute concurrency across every dimension tuple.
--     Filter it however you like — no parameters, just a WHERE.
CREATE VIEW concurrency_minute AS
SELECT
    minute, platform, country, video_type, content_id,
    max(sessions)         AS sessions,
    uniqExactMerge(users) AS users
FROM conc_minute
GROUP BY minute, platform, country, video_type, content_id;


-- 7b. Peak / average concurrency, whole dataset, no filter.
--     The inner GROUP BY collapses the max-semantics rows. The outer
--     one sums across dimensions within each minute. Only then max/avg.
WITH per_minute AS
(
    SELECT minute, sum(sessions) AS c
    FROM concurrency_minute
    GROUP BY minute
)
SELECT
    max(c)            AS peak_concurrency,
    argMax(minute, c) AS peak_minute,
    sum(c) / (dateDiff('minute', min(minute), max(minute)) + 1) AS avg_concurrency
FROM per_minute;

-- The divisor is deliberate. avg(c) divides by minutes that HAVE rows —
-- any minute with zero concurrency vanishes and you overstate. Dividing
-- by the full span length is the correct definition. Confirm against
-- the judges' benchmark spec.


-- 7c. Same, filtered. Change the WHERE to whatever the benchmark asks.
WITH per_minute AS
(
    SELECT minute, sum(sessions) AS c
    FROM concurrency_minute
    WHERE platform = 'Android'
      AND country  = 'IN'
    GROUP BY minute
)
SELECT
    max(c)            AS peak_concurrency,
    argMax(minute, c) AS peak_minute,
    sum(c) / (dateDiff('minute', min(minute), max(minute)) + 1) AS avg_concurrency
FROM per_minute;


-- 7d. Proof that peak shifts per dimension combination — this is the
--     slide. Each row peaks at a different minute.
SELECT
    platform,
    max(c)            AS peak_concurrency,
    argMax(minute, c) AS peak_minute
FROM (
    SELECT platform, minute, sum(sessions) AS c
    FROM concurrency_minute
    GROUP BY platform, minute
)
GROUP BY platform
ORDER BY peak_concurrency DESC;


-- 7e. User grain. NOT additive: one user can hold two sessions on two
--     devices, so merge, never sum.
SELECT
    minute,
    uniqExactMerge(users) AS concurrent_users
FROM conc_minute
WHERE platform = 'Android'
GROUP BY minute
ORDER BY minute;


-- 7f. Hour grain. Peak-per-hour is the max over 60 minute values;
--     average is the mean of those 60. Never the average of averages.
WITH per_minute AS
(
    SELECT minute, sum(sessions) AS c
    FROM concurrency_minute
    GROUP BY minute
)
SELECT
    toStartOfHour(minute) AS hour,
    max(c)                AS peak_concurrency,
    sum(c) / 60           AS avg_concurrency
FROM per_minute
GROUP BY hour
ORDER BY hour;


-- 7g. Top content by peak concurrency, with titles.
SELECT
    c.content_id,
    joinGet('liv.content_join', 'title', c.content_id) AS title,
    max(c.peak) AS peak_concurrency,
    argMax(c.minute, c.peak) AS peak_minute
FROM (
    SELECT content_id, minute, sum(sessions) AS peak
    FROM concurrency_minute
    GROUP BY content_id, minute
) AS c
GROUP BY c.content_id
ORDER BY peak_concurrency DESC
LIMIT 20;


-- =====================================================================
-- SECTION 8 — SESSION-AWARE REFERENCE (validation instrument)
-- =====================================================================
-- The START_HERE asks for session-aware AND session-independent, plus a
-- comparison. Section 4 is the fast session-independent path. This
-- reconstructs explicit foreground intervals with carried-forward
-- background state.
--
-- SCOPE THIS DELIBERATELY. PARTITION BY video_session_id across a full
-- stream is a global shuffle — fine as a correctness oracle, fatal as a
-- pipeline stage. It runs on the 10% sample only. Say this out loud in
-- the deck: it is a validation instrument, not a serving path. That is
-- a trade-off answer, not a limitation.
--
-- IDs are hashed here too, so the comparison is like for like.

CREATE TABLE session_minute_ref
(
    minute            DateTime('UTC') CODEC(DoubleDelta, ZSTD(1)),
    platform          LowCardinality(String),
    country           LowCardinality(String),
    video_type        LowCardinality(String),
    content_id        UInt32 CODEC(ZSTD(1)),
    video_session_id  UInt64 CODEC(ZSTD(1)),
    user_id           UInt64 CODEC(ZSTD(1))
)
ENGINE = ReplacingMergeTree
PARTITION BY toDate(minute)
ORDER BY (minute, platform, country, video_type, content_id, video_session_id);


INSERT INTO session_minute_ref
WITH 120 AS max_gap_seconds   -- 2x the documented 60s cadence
SELECT
    toStartOfMinute(seg_start) + toIntervalMinute(m) AS minute,
    platform, country,
    if(joinGet('liv.content_join', 'video_type', content_id) = '',
       'unknown',
       joinGet('liv.content_join', 'video_type', content_id)) AS video_type,
    content_id,
    cityHash64(video_session_id) AS video_session_id,
    cityHash64(user_id)          AS user_id
FROM
(
    SELECT
        video_session_id, user_id, content_id, platform, country,
        event_timestamp AS seg_start,
        least(
            coalesce(next_ts, event_timestamp + toIntervalSecond(max_gap_seconds)),
            event_timestamp + toIntervalSecond(max_gap_seconds)
        ) AS seg_end
    FROM
    (
        SELECT
            *,
            last_value(
                if(event_type = 'AppBackgrounded', 1,
                   if(event_type = 'AppForegrounded', 0, NULL))
            ) IGNORE NULLS OVER w AS bg_state,
            leadInFrame(event_timestamp) OVER (
                PARTITION BY video_session_id ORDER BY event_timestamp
                ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING
            ) AS next_ts
        FROM events_raw
        WINDOW w AS (
            PARTITION BY video_session_id ORDER BY event_timestamp
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    )
    WHERE event_type IN ('VideoHeartbeat', 'VideoPlay', 'VideoSessionStart', 'AppForegrounded')
      AND coalesce(bg_state, 0) = 0
)
ARRAY JOIN range(0, toUInt32(greatest(1, dateDiff('minute', toStartOfMinute(seg_start), seg_end)))) AS m;


-- The comparison for the deck. Sample the fast path to the same subset.
-- session_minute.video_session_id is ALREADY cityHash64 — filter on it
-- directly, do NOT hash it again.
SELECT
    fast_rows,
    ref_rows,
    round(100 * (fast_rows - ref_rows) / ref_rows, 3) AS pct_delta
FROM (
    SELECT
        (SELECT count() FROM session_minute WHERE video_session_id % 10 = 0) AS fast_rows,
        (SELECT count() FROM session_minute_ref)                             AS ref_rows
);


-- THE key question, answerable now: do heartbeats fire while
-- backgrounded? If this is > 0, the stateless path in section 4
-- overcounts and this reference becomes the source of truth.
SELECT countIf(event_type = 'VideoHeartbeat' AND bg_state = 1) AS beats_while_backgrounded
FROM (
    SELECT
        event_type,
        last_value(
            if(event_type = 'AppBackgrounded', 1,
               if(event_type = 'AppForegrounded', 0, NULL))
        ) IGNORE NULLS OVER (
            PARTITION BY video_session_id ORDER BY event_timestamp
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS bg_state
    FROM events_raw
);


-- =====================================================================
-- SECTION 9 — VERIFY TYPE CHOICES EMPIRICALLY
-- =====================================================================
-- Whatever sits at the top of this list is where the next optimisation
-- goes; everything else is noise. Screenshot it — good slide material.

SELECT
    table, name, type,
    formatReadableSize(sum(data_compressed_bytes))   AS compressed,
    formatReadableSize(sum(data_uncompressed_bytes)) AS raw,
    round(sum(data_uncompressed_bytes) / sum(data_compressed_bytes), 1) AS ratio
FROM system.columns
WHERE database = 'liv' AND table IN ('session_minute', 'conc_minute', 'events_raw')
GROUP BY table, name, type
ORDER BY table, sum(data_compressed_bytes) DESC;


-- =====================================================================
-- SECTION 10 — PIPELINE EVIDENCE (required: no evidence, no credit)
-- =====================================================================
-- Capture immediately after the unseen-day benchmark run.

SELECT
    event_time,
    query_duration_ms,
    read_rows,
    formatReadableSize(read_bytes)   AS bytes_read,
    formatReadableSize(memory_usage) AS mem,
    normalized_query_hash,
    substring(query, 1, 200)         AS q
FROM system.query_log
WHERE type = 'QueryFinish'
  AND event_time > now() - INTERVAL 2 HOUR
  AND query ILIKE '%conc_minute%'
ORDER BY event_time DESC;

-- Judges look at what your queries READ, not just how fast they return.
-- read_rows and bytes_read are the columns that matter.
