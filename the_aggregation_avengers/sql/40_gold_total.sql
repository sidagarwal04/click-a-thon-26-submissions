-- ===========================================================================
-- 40_gold_total.sql — the unfiltered serving layer
-- ===========================================================================
-- WHY A SECOND GOLD TABLE
--
-- `gold_ccu_minute` is keyed by minute × nine dimensions, so one minute is
-- roughly 27 rows on the provided data (105,083 rows / 3,856 minutes) and will
-- be far more on the unseen day — `video_resolution` adds a tenth dimension,
-- and every added dimension multiplies the combination count.
--
-- But the dashboard's DEFAULT view, and the answer the judges ask for first,
-- has no dimension filter at all. Serving that from the dimensional table means
-- reading ~27 rows and merging ~27 aggregate states to produce one number per
-- minute. This table holds exactly one row per minute, so the same answer costs
-- one row and one state.
--
-- IT IS NOT A PRE-COMPUTED PEAK. Storing peak would be wrong for the reason
-- documented in 30_gold.sql — max() does not decompose across a filter. What is
-- stored here is a per-minute distinct-count STATE for all traffic, which is
-- exactly what the unfiltered query computes anyway. Peak is still max() over
-- the series, after filtering, every time.
--
-- The API routes to this table only when no dimension filter is set, and falls
-- back to gold_ccu_minute otherwise. Both are fed from the same source rows, so
-- they cannot disagree.

-- ---------------------------------------------------------------------------
-- 1. The table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold_ccu_total
(
    -- DoubleDelta then ZSTD: minute values ascend by a near-constant step, so
    -- the delta of the delta is almost always zero and compresses to nearly
    -- nothing. Default LZ4 on a raw DateTime cannot see that structure.
    minute   DateTime CODEC(DoubleDelta, ZSTD(1)),
    sessions AggregateFunction(uniqExact, String),
    users    AggregateFunction(uniqExact, String),
    -- How many DISTINCT titles were being watched in this minute. Cheap to
    -- carry here and impossible to derive later: a distinct count cannot be
    -- reconstructed from other per-minute numbers, it has to be aggregated at
    -- the same time as everything else.
    --
    -- Int64 rather than String state: content_id is already numeric, and a
    -- numeric uniqExact state is materially smaller than one over 64-char
    -- session strings.
    contents AggregateFunction(uniqExact, Int64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toDate(minute)
ORDER BY minute;

-- ---------------------------------------------------------------------------
-- 2. Keep it current
-- ---------------------------------------------------------------------------
-- Same source and same predicate as mv_gold_ccu_minute, so the two tables are
-- two aggregations of one set of rows rather than two pipelines that could
-- drift. Any row that lands in silver feeds both.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_gold_ccu_total TO gold_ccu_total AS
SELECT
    event_minute                     AS minute,
    uniqExactState(video_session_id) AS sessions,
    uniqExactState(user_id)          AS users,
    uniqExactState(content_id)       AS contents
FROM silver_events
WHERE is_heartbeat = 1 AND is_duplicate = 0
GROUP BY minute;

-- ---------------------------------------------------------------------------
-- 3. Backfill history
-- ---------------------------------------------------------------------------
-- The MV only sees rows inserted after it exists.
--
-- GUARDED, unlike the backfill in 30_gold.sql — that one is a bare INSERT and
-- running it twice duplicates gold's stored rows. Here the TRUNCATE makes the
-- whole file safe to re-run, which matters because this will be run on the
-- unseen day by someone under time pressure.
TRUNCATE TABLE gold_ccu_total;

INSERT INTO gold_ccu_total
SELECT
    event_minute                     AS minute,
    uniqExactState(video_session_id) AS sessions,
    uniqExactState(user_id)          AS users,
    uniqExactState(content_id)       AS contents
FROM silver_events
WHERE is_heartbeat = 1 AND is_duplicate = 0
GROUP BY minute;

-- ---------------------------------------------------------------------------
-- 4. Prove the two tables agree
-- ---------------------------------------------------------------------------
-- If this ever returns anything other than PASS, the fast path is lying and the
-- API must not use it.
SELECT
    'total_matches_dimensional'                      AS check,
    t.peak                                           AS total_peak,
    d.peak                                           AS dimensional_peak,
    t.watch                                          AS total_watch_minutes,
    d.watch                                          AS dimensional_watch_minutes,
    if(t.peak = d.peak AND t.watch = d.watch, 'PASS',
       'FAIL — gold_ccu_total disagrees with gold_ccu_minute') AS verdict
FROM
    (SELECT max(c) AS peak, sum(c) AS watch FROM (
        SELECT minute, uniqExactMerge(sessions) AS c FROM gold_ccu_total GROUP BY minute)) AS t,
    (SELECT max(c) AS peak, sum(c) AS watch FROM (
        SELECT minute, uniqExactMerge(sessions) AS c FROM gold_ccu_minute GROUP BY minute)) AS d;
