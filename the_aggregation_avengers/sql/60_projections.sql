-- ===========================================================================
-- 60_projections.sql — alternate sort orders inside gold_ccu_minute
-- ===========================================================================
-- WHY PROJECTIONS AND NOT MORE MATERIALIZED VIEWS
--
-- The tempting design is one MV per dimension ordering, so each filter reads a
-- table sorted its way. Three reasons that is the wrong shape:
--
--   * IT DOES NOT BUY PRUNING FOR MOST OF THEM. Measured with EXPLAIN
--     indexes=1: only the column immediately AFTER `minute` prunes granules.
--     Everything later kept 7/12 granules, identical to no filter at all.
--   * THE COMBINATIONS EXPLODE. Ten dimensions is ten tables for single
--     filters -- but real filters combine. Pairs are 45 tables, triples 120.
--     You cannot pre-order your way out of a combinatorial filter space.
--   * EVERY MV MULTIPLIES WRITE COST. Ten MVs means each silver insert fans out
--     ten times, slowing the ingest the judges are also timing.
--
-- A projection is the same idea without any of that: an alternate sort order
-- stored INSIDE the table, chosen automatically by the optimiser. No routing
-- code in the API, no second table to keep in sync, no way for the two to
-- disagree -- because there is only one table.
--
-- The cost is real and worth stating: each projection is a second copy of the
-- columns it names, written on every insert and merged on every merge. So add
-- them for query shapes that actually happen, not for completeness.

-- deduplicate_merge_projection_mode='rebuild' is already set ON THE TABLE (see
-- 30_gold.sql). It is a MergeTree table setting, not a statement-level one: as a
-- SETTINGS clause on ADD PROJECTION it fails with UNKNOWN_SETTING (115), which
-- reads like the feature is unsupported rather than like it is in the wrong
-- place. Without it on the table, ADD PROJECTION on SharedMergeTree is rejected
-- outright with error 344.


-- 1. BY CONTENT — "how many people are watching this title right now"
-- The live-event question: an IPL match is a content_id, and the natural query
-- is one title across a time range. In the base table content_id is 3rd in the
-- sort key behind a RANGE on minute, so it prunes nothing. Sorted content-first
-- it becomes a point lookup followed by a contiguous time scan.
ALTER TABLE gold_ccu_minute
    ADD PROJECTION IF NOT EXISTS proj_content_first
    (SELECT content_id, minute, platform, video_type, category, audio_language, sessions, users
     ORDER BY content_id, minute);

-- 2. BY AUDIO LANGUAGE — the most-used dimension after platform on this data,
-- and the one that is NOT pinned per session, so it cannot be answered from
-- session dimensions alone.
ALTER TABLE gold_ccu_minute
    ADD PROJECTION IF NOT EXISTS proj_audio_first
    (SELECT audio_language, minute, platform, video_type, sessions, users
     ORDER BY audio_language, minute);

-- Materialise for rows already stored. Without this a projection only covers
-- parts written AFTER it was added, and the optimiser will refuse to use it for
-- a query whose range predates it -- silently falling back to a full scan.
ALTER TABLE gold_ccu_minute MATERIALIZE PROJECTION proj_content_first;
ALTER TABLE gold_ccu_minute MATERIALIZE PROJECTION proj_audio_first;

-- ---------------------------------------------------------------------------
-- Confirm they exist. Whether they are USED is a separate question -- check
-- system.query_log.projections after running a query, not this.
-- ---------------------------------------------------------------------------
SELECT
    'projections'                                  AS check,
    arrayStringConcat(groupArray(name), ', ')      AS present,
    if(count() >= 3, 'PASS', 'FAIL — expected 3')  AS verdict
FROM system.projections WHERE database = 'default' AND table = 'gold_ccu_minute';
