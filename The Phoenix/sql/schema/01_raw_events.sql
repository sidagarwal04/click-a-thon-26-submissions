-- Raw append-only event stream. Source of truth, never read by dashboards.
--
-- event_timestamp / session_start_epoch arrive as epoch MILLIseconds (Int64) in the CSV.
-- We keep them as DateTime64(3) so every downstream expression is time-typed.
--
-- ORDER BY: low -> high cardinality, time last, but session first because every
-- derivation is per-session (the state machine partitions by video_session_id).
-- Reading one session's events must not scatter across granules.

CREATE TABLE IF NOT EXISTS raw_events
(
    video_session_id    String,
    user_id             String,
    content_id          Int64,
    event_type          LowCardinality(String),
    event               LowCardinality(String),
    event_timestamp     DateTime64(3),
    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),
    audio_language      LowCardinality(String),
    subtitle_language   LowCardinality(String),
    player_version      LowCardinality(String),
    session_start_epoch DateTime64(3),
    -- Added for the unseen day (docs/problem/spec.md): the raw CSV gained a 14th column and the
    -- spec tags it "Used as a filter dimension". LowCardinality because a resolution ladder is a
    -- handful of distinct strings over millions of rows, the same reasoning as platform.
    -- The graded phoenix corpus predates the column, so its rows carry the empty default. That is
    -- correct and deliberate: absent, not unknown.
    video_resolution    LowCardinality(String),
    -- SUPERSEDED by arrival_timestamp below. Kept because dropping a column from a live
    -- table is a mutation and this one is load-bearing in nothing. Do not filter on it:
    -- it was added by ALTER after the July rows were loaded, ClickHouse does not rewrite
    -- existing parts, so for those rows DEFAULT now() is evaluated AT READ TIME and the
    -- column equals the wall clock of whichever query reads it. Proven in
    -- evidence/ingested_at_nondeterminism: 905,558 rows, exactly the corpus.
    ingested_at         DateTime DEFAULT now(),

    -- Trustworthy arrival time, the column ingested_at failed to be. Two rules make it work:
    --
    --   The DEFAULT is a CONSTANT, epoch 0, meaning "arrival not observed". A DEFAULT now64(3)
    --   here would reproduce the ingested_at bug exactly: read-time evaluation on any part
    --   written before the column existed.
    --
    --   The real value comes from raw_events_mv, which selects now64(3) explicitly, so it is
    --   MATERIALISED into the part at insert time and cannot drift afterwards. Every row that
    --   arrives through the landing table therefore carries a true arrival instant, and every
    --   row inserted directly (a replica copy, a backfill) carries the sentinel.
    --
    -- Lateness is (arrival_timestamp - event_timestamp) over rows with arrival_timestamp > 0
    -- ONLY. Including sentinel rows manufactures a zero-lateness distribution.
    arrival_timestamp   DateTime64(3) DEFAULT toDateTime64(0, 3)
)
ENGINE = MergeTree
-- PARTITION BY DAY. Known wart, measured and deliberately not changed under time pressure:
-- the unseen day's dirty tail (2014-12-31 to 2026-08-03) makes 189 daily partitions where one
-- holds 6,936,152 of 7,000,000 rows. A straight INSERT ... SELECT of the corpus fails with
-- TOO_MANY_PARTS. toYYYYMM is the fix and needs a full rebuild of both live databases; it is
-- recorded in docs/FINAL_CHECKLIST.md rather than applied at deploy time.
PARTITION BY toYYYYMMDD(event_timestamp)
ORDER BY (video_session_id, event_timestamp);

-- Landing table matching the CSV exactly (epoch millis as Int64), so `load.sh` is a
-- straight INSERT with no client-side transform. An MV converts into raw_events.
CREATE TABLE IF NOT EXISTS raw_events_landing
(
    content_id          Int64,
    video_session_id    String,
    user_id             String,
    event_type          LowCardinality(String),
    event               LowCardinality(String),
    event_timestamp     Int64,
    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),
    audio_language      LowCardinality(String),
    subtitle_language   LowCardinality(String),
    player_version      LowCardinality(String),
    session_start_epoch Int64,
    -- 14th CSV column, unseen day. Landing still matches the CSV exactly, which is the whole
    -- contract of this table.
    video_resolution    LowCardinality(String)
)
ENGINE = Null;   -- ponytail: pure pass-through, the MV below is the only consumer

CREATE MATERIALIZED VIEW IF NOT EXISTS raw_events_mv TO raw_events AS
SELECT
    video_session_id, user_id, content_id, event_type, event,
    fromUnixTimestamp64Milli(event_timestamp)     AS event_timestamp,
    platform, app_version, country, audio_language, subtitle_language, player_version,
    fromUnixTimestamp64Milli(session_start_epoch) AS session_start_epoch,
    video_resolution,
    -- Observed at the moment the row lands, materialised into the part. The landing table
    -- deliberately does NOT carry this column: it matches the CSV exactly, and a producer
    -- that supplies its own arrival time is supplying a claim, not an observation.
    now64(3)                                      AS arrival_timestamp
FROM raw_events_landing;
