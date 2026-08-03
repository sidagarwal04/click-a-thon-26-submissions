-- Session-independent concurrency: how many distinct USERS are watching, not how many
-- sessions. The problem statement asks for both readings and for the divergence between
-- them, and they are genuinely different questions: one person on a phone and a TV is two
-- sessions and one viewer.
--
-- Deltas cannot be reused from the session rollup, because summing session deltas counts
-- that person twice. A user's runs are therefore merged ACROSS all of their sessions first,
-- so overlapping sessions collapse into one run before any +1 is emitted.
--
-- Dimension attribution: a user is filed under the dimensions of their FIRST run. 7 users of
-- 9,510 watch on more than one platform, and for those a platform filter attributes them to
-- the platform they started on. Keying user runs by dimension instead would make the
-- unfiltered total wrong for exactly those users, which is the worse trade: the unfiltered
-- number is the one on the wall.

CREATE TABLE IF NOT EXISTS user_minute_runs
(
    user_id     String,
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  Int64,
    app_version LowCardinality(String),
    audio_language LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version LowCardinality(String),
    video_resolution LowCardinality(String),
    run_start   DateTime,
    run_end     DateTime,
    sign        Int8 DEFAULT 1,
    -- The twin of session_minute_runs.idx_run_range, which this table was missing. On reach.sql's
    -- overlap predicate the session table pruned to 10/18 granules and this one pruned nothing.
    INDEX idx_run_range (run_start, run_end) TYPE minmax GRANULARITY 4
)
ENGINE = CollapsingMergeTree(sign)
-- PARTITION BY DAY. Known wart, measured and deliberately not changed under time pressure:
-- the unseen day's dirty tail (2014-12-31 to 2026-08-03) makes 189 daily partitions where one
-- holds 6,936,152 of 7,000,000 rows. A straight INSERT ... SELECT of the corpus fails with
-- TOO_MANY_PARTS. toYYYYMM is the fix and needs a full rebuild of both live databases; it is
-- recorded in docs/FINAL_CHECKLIST.md rather than applied at deploy time.
PARTITION BY toYYYYMMDD(run_start)
ORDER BY (user_id, run_start, run_end);

CREATE TABLE IF NOT EXISTS user_concurrency_deltas
(
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  Int64,
    app_version LowCardinality(String),
    audio_language LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version LowCardinality(String),
    video_resolution LowCardinality(String),
    minute      DateTime,
    delta       Int32
)
ENGINE = SummingMergeTree(delta)
-- PARTITION BY DAY. Known wart, measured and deliberately not changed under time pressure:
-- the unseen day's dirty tail (2014-12-31 to 2026-08-03) makes 189 daily partitions where one
-- holds 6,936,152 of 7,000,000 rows. A straight INSERT ... SELECT of the corpus fails with
-- TOO_MANY_PARTS. toYYYYMM is the fix and needs a full rebuild of both live databases; it is
-- recorded in docs/FINAL_CHECKLIST.md rather than applied at deploy time.
PARTITION BY toYYYYMMDD(minute)
ORDER BY (platform, country, video_type, content_id, app_version, audio_language, subtitle_language, player_version, video_resolution, minute);

CREATE MATERIALIZED VIEW IF NOT EXISTS user_concurrency_deltas_mv TO user_concurrency_deltas AS
SELECT
    platform, country, video_type, content_id, app_version,
    audio_language, subtitle_language, player_version, video_resolution,
    d.1 AS minute,
    d.2 * sign AS delta
FROM user_minute_runs
ARRAY JOIN [(run_start, 1), (run_end + INTERVAL 1 MINUTE, -1)] AS d;
