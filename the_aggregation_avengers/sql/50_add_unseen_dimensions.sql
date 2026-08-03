-- ===========================================================================
-- 50_add_unseen_dimensions.sql — video_resolution and show_name
-- ===========================================================================
-- The unseen dataset adds one column to each file:
--   raw     : video_resolution   (String, a filter dimension)
--   content : show_name          (String, a filter dimension)
--
-- Run this ONCE, BEFORE loading the unseen CSVs. It is additive and idempotent:
-- every statement is IF NOT EXISTS or a no-op when already applied, so existing
-- rows keep working and existing answers do not move.
--
-- WHY DEFAULT '' RATHER THAN Nullable
-- A Nullable column carries a separate null-mask stream, costs more to read,
-- and makes every downstream predicate think about three states instead of two.
-- Absent-means-empty is the same convention silver already uses for blank
-- player_version, and it keeps the provided day and the unseen day queryable
-- through one set of queries.
--
-- ⚠️  THE COST OF ADDING A GOLD DIMENSION IS MULTIPLICATIVE, NOT ADDITIVE.
-- gold_ccu_minute has one row per minute x dimension COMBINATION. Adding an
-- Nth dimension with k distinct values multiplies the row count by up to k.
-- On the provided data that is 105,083 rows -> potentially ~500,000 with a
-- 5-value resolution column, before accounting for 7M events in a single day.
-- This is exactly why gold_ccu_total exists: the unfiltered query, which is the
-- one asked first, does not pay that multiplier at all.

-- ---------------------------------------------------------------------------
-- 1. Bronze — as delivered, so the column is just carried
-- ---------------------------------------------------------------------------
ALTER TABLE bronze_events  ADD COLUMN IF NOT EXISTS video_resolution String DEFAULT '';
ALTER TABLE bronze_content ADD COLUMN IF NOT EXISTS show_name        String DEFAULT '';

-- ---------------------------------------------------------------------------
-- 2. Silver — LowCardinality, because these are dimensions
-- ---------------------------------------------------------------------------
-- Resolutions are a closed set ('1080p', '720p', ...): a dictionary-encoded
-- column stores one small integer per row instead of the string, which is both
-- smaller and faster to group by. show_name is higher cardinality but still far
-- below the ~10k rule of thumb where LowCardinality stops paying.
ALTER TABLE silver_events  ADD COLUMN IF NOT EXISTS video_resolution LowCardinality(String) DEFAULT '';
ALTER TABLE silver_content ADD COLUMN IF NOT EXISTS show_name        LowCardinality(String) DEFAULT '';

-- ---------------------------------------------------------------------------
-- 3. Gold — a new dimension, appended to the sort key
-- ---------------------------------------------------------------------------
-- ⚠️  TWO CONSTRAINTS HERE, BOTH FOUND BY HITTING THEM.
--
-- 1. ADD and MODIFY ORDER BY must be ONE statement. ClickHouse only extends a
--    sort key with columns added by the SAME ALTER. Split in two, the ADD
--    succeeds, the MODIFY fails with BAD_ARGUMENTS (36), and the column is now
--    permanently ineligible -- you must DROP it and start over.
--
-- 2. NO `DEFAULT ''` on this one. "Newly added column has a default expression,
--    so adding expressions that use it to the sorting key is forbidden." A
--    declared DEFAULT disqualifies a column from the sort key entirely. Omitting
--    it changes nothing about behaviour: the implicit default for
--    LowCardinality(String) is already '', which is what every existing row
--    gets. The clause only ever bought readability, and it costs the sort key.
ALTER TABLE gold_ccu_minute
    ADD COLUMN IF NOT EXISTS video_resolution LowCardinality(String),
    MODIFY ORDER BY (minute, platform, content_id, video_type, category,
                     country, audio_language, subtitle_language,
                     app_version, player_version, video_resolution);

-- Appended at the END of the sort key, deliberately, for two reasons:
--   * ClickHouse only permits extending a sort key at the end, and only with
--     columns that are not in the primary key.
--   * Even if it were free to place anywhere, it belongs last: a filter on a
--     column that is not the first after `minute` gets no granule pruning
--     (measured -- see PERFORMANCE.md), so its only remaining job is
--     compression, and the highest-cardinality columns belong at the end.
--
-- This is metadata-only. It does NOT rewrite existing parts: rows already
-- stored keep video_resolution = '' and merge correctly, because '' sorts as a
-- single group.
-- ---------------------------------------------------------------------------
-- 4. Confirm
-- ---------------------------------------------------------------------------
SELECT
    'unseen_dimensions_added'                                              AS check,
    hasAll(groupArray(name), ['video_resolution'])                         AS gold_has_resolution,
    if(hasAll(groupArray(name), ['video_resolution']), 'PASS', 'FAIL')     AS verdict
FROM system.columns WHERE database = 'default' AND table = 'gold_ccu_minute';
