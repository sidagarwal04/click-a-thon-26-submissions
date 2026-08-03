-- The serving layer. Three tables, and the only one a dashboard ever reads is the last.
--
--   foreground_intervals   one row per active interval inside a session
--   session_minute_runs    those intervals merged into contiguous minute runs, per session
--   concurrency_deltas     +1 at run start, -1 after run end, per dimension tuple
--
-- Why runs and not intervals: a session pauses and resumes several times inside one minute
-- (measured: our spot-check session fragments 4 times in 60 seconds). Emitting a delta per
-- interval would count that session 4 times in that minute. Concurrency asks "was this
-- session watching during minute M", which is once. Merging to minute runs first makes the
-- delta model answer exactly that, and keeps cost proportional to boundaries, not watch time.

CREATE TABLE IF NOT EXISTS foreground_intervals
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    app_version      LowCardinality(String),
    audio_language LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version LowCardinality(String),
    video_resolution LowCardinality(String),
    video_type       LowCardinality(String),
    interval_start   DateTime,
    interval_end     DateTime          -- exclusive
)
ENGINE = MergeTree
-- PARTITION BY, added 2026-08-01 to match the live schema (scripts/repartition_derived.sh).
-- Daily, mirroring raw_events. The purpose is LIFECYCLE, not scan pruning: these are exactly the
-- tables scripts/reset_live.sh must clear, and without a partition key that clearing has to be a
-- lightweight DELETE. That is a mutation, and worse, a DELETE followed by re-inserting rows which
-- match its predicate leaves the new rows MASKED, measured in this repo at 108,521 rows
-- physically present in system.parts and invisible to every SELECT.
-- Daily rather than monthly because the unseen day lands in the same month as the demo rows, and
-- a monthly key would make the mandatory pre-unseen-day cleanup impossible to do by partition.
-- PARTITION BY DAY. Known wart, measured and deliberately not changed under time pressure:
-- the unseen day's dirty tail (2014-12-31 to 2026-08-03) makes 189 daily partitions where one
-- holds 6,936,152 of 7,000,000 rows. A straight INSERT ... SELECT of the corpus fails with
-- TOO_MANY_PARTS. toYYYYMM is the fix and needs a full rebuild of both live databases; it is
-- recorded in docs/FINAL_CHECKLIST.md rather than applied at deploy time.
PARTITION BY toYYYYMMDD(interval_start)
ORDER BY (video_session_id, interval_start);

CREATE TABLE IF NOT EXISTS session_minute_runs
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    app_version      LowCardinality(String),
    audio_language LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version LowCardinality(String),
    video_resolution LowCardinality(String),
    video_type       LowCardinality(String),
    run_start        DateTime,         -- first minute the session is active in
    run_end          DateTime,         -- last minute the session is active in, inclusive
    -- +1 asserts a run, -1 retracts one previously asserted. An open session whose runs
    -- grow is re-derived by writing -1 rows for what it had and +1 rows for what it has
    -- now. The delta MV multiplies by sign, so the serving layer absorbs the correction
    -- as two more additive rows. No mutation, no rebuild, no recompute of other sessions.
    sign             Int8 DEFAULT 1,

    -- FOUND LIVE, ABSENT FROM THIS FILE until now. phoenix.session_minute_runs carries this
    -- index; nothing in the repo created it, so it came from an out-of-band ALTER. That made
    -- rebuild_swap.sh a live hazard: it builds the shadow from THIS file and then EXCHANGEs
    -- the tables into phoenix, so the next rebuild would have silently deleted the index from
    -- production, and the shadow verify (closure, overshoot, row counts) would not have
    -- noticed. Declared here so the repo and the server agree and scripts/schema_drift.sh
    -- keeps them that way.
    INDEX idx_run_range (run_start, run_end) TYPE minmax GRANULARITY 4,
    -- user_id is NOT in the sort key, and 04c_merge_user_runs_atomic.sql filters on it every
    -- tick. Measured before this existed: Parts 11/11, Granules 18/18, a full scan of total
    -- history every 60 seconds, forever. After: 118,497 rows read becomes 2.
    INDEX idx_user_id user_id TYPE bloom_filter GRANULARITY 4
)
ENGINE = CollapsingMergeTree(sign)
-- PARTITION BY DAY. Known wart, measured and deliberately not changed under time pressure:
-- the unseen day's dirty tail (2014-12-31 to 2026-08-03) makes 189 daily partitions where one
-- holds 6,936,152 of 7,000,000 rows. A straight INSERT ... SELECT of the corpus fails with
-- TOO_MANY_PARTS. toYYYYMM is the fix and needs a full rebuild of both live databases; it is
-- recorded in docs/FINAL_CHECKLIST.md rather than applied at deploy time.
PARTITION BY toYYYYMMDD(run_start)
ORDER BY (video_session_id, run_start, run_end);

-- ORDER BY puts dimensions FIRST and minute LAST, inverting the usual reflex on purpose:
-- a cumulative sum must start at the first minute of the series, never at the start of the
-- queried range, so a time predicate prunes nothing. A dimension filter is the only thing
-- that can prune, so the dimensions have to lead the key.
--
-- THE FOUR LANGUAGE/DEVICE DIMENSIONS ARE APPENDED AFTER app_version, NOT INTERLEAVED BY
-- CARDINALITY. Low-to-high is the usual rule and it is deliberately not followed here, because
-- the first five columns are the key prefix every existing filter already prunes on and every
-- published read figure was measured against. Inserting video_resolution (2,071 distinct) in the
-- middle would silently change the pruning behaviour of the platform filter, and "30,662 rows in
-- 12 ms" would quietly become a different number for a reason no reader could see. Appending
-- leaves every existing prefix lookup byte-identical and makes the new dimensions prunable in
-- combination with the old ones.
--
-- Measured before committing to it: distinct key cardinality on the 7,000,000-row unseen day goes
-- from 547,310 to 876,542, i.e. 1.6x, not the explosion 2,071 distinct resolutions suggests. The
-- dimensions co-occur rather than multiply out.
CREATE TABLE IF NOT EXISTS concurrency_deltas
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

-- Insert-time MV: every run written becomes exactly two rows, +1 when it starts and -1 in
-- the minute after it ends. Additive, so a late run or a re-derived one is just more rows.
-- GROUP BY is absent by design: the SummingMergeTree collapses on its ORDER BY, which the
-- SELECT matches column for column.
CREATE MATERIALIZED VIEW IF NOT EXISTS concurrency_deltas_mv TO concurrency_deltas AS
SELECT
    platform,
    country,
    video_type,
    content_id,
    app_version,
    audio_language,
    subtitle_language,
    player_version,
    video_resolution,
    d.1 AS minute,
    d.2 * sign AS delta      -- sign = -1 retracts the pair this run contributed before
FROM session_minute_runs
ARRAY JOIN [(run_start, 1), (run_end + INTERVAL 1 MINUTE, -1)] AS d;

-- FILTER-KEY ACCELERATION, as a PROJECTION rather than a second table.
--
-- THE DEFECT IT FIXES, measured: content_id sits at key position 4 with 14,879 distinct values,
-- which makes the key effectively unique by position 4. A granule holds 8,192 rows, so every
-- granule's min/max spans essentially every value of positions 5 to 9 and generic exclusion
-- search excludes nothing. Filtering on a suffix dimension alone read 133,656 of 133,784 rows.
-- Confirmed this is NOT the `('' = '' OR col = x)` idiom: bare equality reads identically.
-- No query-text change can fix it. Only a second sort order can.
--
-- WHY A PROJECTION AND NOT A SECOND SummingMergeTree. A projection is auto-selected by the query
-- analyzer, so none of the eleven files in sql/queries/serving/ has to know it exists and none of
-- the published read figures moves for an invisible reason. A second table would need routing
-- logic in every serving query reproducing the `'' = all` semantics, and MV/target mismatch is
-- the top source of silently-wrong numbers.
--
-- WHY THE SETTING IS REQUIRED. ClickHouse refuses projections on SummingMergeTree under the
-- default `deduplicate_merge_projection_mode = throw`. `drop` silently discards the projection on
-- merge, which is worse than not having it. `rebuild` recomputes it from the merged part and is
-- safe HERE specifically because sum() is associative; verified correct both before and after
-- OPTIMIZE FINAL on a 2.5M-row MV-fed replica of this exact topology.
--
-- COST: about +64% storage on the delta table, and one extra sorted write per part on insert.
-- The delta table is the smallest thing in the database, so this is cheap in absolute terms.
--
-- HONEST LIMIT: nine independent filters is 2^9 combinations and no pair of sort orders serves
-- them all. This covers the four appended dimensions and their combinations. A filter on
-- app_version ALONE is still unprunable in both orders.
ALTER TABLE concurrency_deltas MODIFY SETTING deduplicate_merge_projection_mode = 'rebuild';

ALTER TABLE concurrency_deltas ADD PROJECTION IF NOT EXISTS p_suffix_first
(
    SELECT
        video_resolution, player_version, audio_language, subtitle_language,
        video_type, platform, country, app_version, content_id, minute,
        sum(delta)
    GROUP BY
        video_resolution, player_version, audio_language, subtitle_language,
        video_type, platform, country, app_version, content_id, minute
);
