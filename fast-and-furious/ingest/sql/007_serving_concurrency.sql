-- =============================================================================
-- 007_serving_concurrency.sql — the two layers a BI tool reads
--
-- Everything above session_intervals is per-session and order-dependent.
-- Everything here is a pure rollup of that one table, so both layers can be
-- rebuilt from scratch at any time and neither holds state the other needs.
--
--   serving_concurrency_live     10-second grain, content only, 3-day TTL
--   serving_concurrency_minute   1-minute grain, six dimension masks
--
-- Built by concurrency/sql/020_rollup_live.sql and 030_rollup_minute.sql,
-- driven by `sonyliv-ingest concurrency`.
--
-- WHICH METRIC IS ADDITIVE, AND WHY IT DECIDES THE WHOLE SCHEMA
-- ---------------------------------------------------------------------------
-- A dashboard aggregates. So the only question that matters for a serving table
-- is which columns survive a SUM across rows, and which do not:
--
--   active_ms           ADDITIVE across every dimension and across time.
--                       It is session-milliseconds inside the bucket, so
--                       sum(active_ms) / bucket_ms is the exact time-weighted
--                       average concurrency for any filter combination. This is
--                       one of the two policy-default metrics
--                       (solution/policy.yaml:111-116) and it is the metric the
--                       dashboards draw their main series from, precisely
--                       because it cannot be aggregated wrongly.
--
--   ending_concurrency  ADDITIVE across dimensions at a fixed instant, because
--                       one session belongs to exactly one slice. It is the
--                       concurrency sampled at the bucket's closing edge, so it
--                       is the honest answer to "how many right now".
--                       NOT additive across time — summing two buckets is
--                       meaningless.
--
--   bucket_peak /       NOT ADDITIVE, EVER. Two titles peak at different
--   minute_peak         instants, so summing their peaks invents viewers who
--                       were never simultaneously present. On the tuning
--                       extract, summing per-content peaks over the hot hour
--                       overstates the true 2,305 substantially.
--
-- That last line is the reason dim_mask exists. An exact peak for a given
-- grouping has to be computed at that grouping, so it is precomputed per mask
-- rather than derived at read time. A reader that wants peak picks the matching
-- mask; a reader that wants an average or an instantaneous count can use any
-- mask, including the full-grain one, and filter freely.
--
-- WHY THE TWO LAYERS USE DIFFERENT REPLACEMENT MECHANISMS
-- ---------------------------------------------------------------------------
-- Both layers are rebuilt repeatedly, and each needs a rebuild to REPLACE what
-- was there rather than add to it. They reach that differently because they are
-- rebuilt at very different rates.
--
--   live    ReplacingMergeTree(version) + FINAL on read. Rebuilt every ~10s
--           over a short trailing window, so a partition swap would rewrite far
--           more than it changed. The table is bounded to 3 days at 10-second
--           grain, which keeps FINAL cheap.
--
--   minute  Plain MergeTree, rebuilt a whole UTC day at a time into
--           serving_concurrency_minute_staging and swapped in with
--           ALTER TABLE ... REPLACE PARTITION. Atomic, needs no FINAL and no
--           version column, and — unlike replacement — it also removes rows
--           that a recompute no longer produces. That matters here: if late data
--           costs a session all of its active time in some minute, the row for
--           that minute must disappear, and a ReplacingMergeTree has nothing to
--           replace it with. Partition granularity is the day, so the swap unit
--           and the rebuild unit are the same thing.
--
-- Reads go through the three views at the bottom, which is where FINAL and the
-- content_dict join live. No dashboard tile should reference these tables
-- directly.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- serving_concurrency_live — 10-second grain, content dimension only
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {{db}}.serving_concurrency_live
(
    bucket_start        DateTime('UTC')
        COMMENT 'Left edge of a 10-second bucket, half-open [bucket_start, +10s)',

    dim_mask            UInt8
        COMMENT 'Which dimensions this row is grouped by. 0 = ungrouped total, 4 = content_id. Bit convention matches solution/policy.yaml:118-134 (platform=1, country=2, content_id=4, video_type=8)',

    content_id          Int64
        COMMENT 'Zero when dim_mask = 0. Int64 because the catalogue holds one negative id',

    bucket_peak         UInt32
        COMMENT 'NOT ADDITIVE. Max instantaneous concurrency inside the bucket, exact only at this row dim_mask. Never sum this across content_id',

    ending_concurrency  UInt32
        COMMENT 'Additive across dim_mask=4 rows at one bucket_start. Concurrency at the closing edge of the bucket',

    active_ms           UInt64
        COMMENT 'Additive everywhere. Session-milliseconds inside this bucket; active_ms/10000 is the exact time-weighted average concurrency',

    version             UInt64
        COMMENT 'Milliseconds since epoch at rollup time; higher wins on replacement'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toDate(bucket_start)
ORDER BY (dim_mask, bucket_start, content_id)
TTL bucket_start + INTERVAL 3 DAY
COMMENT 'Live concurrency at 10-second grain. Best-effort: rebuilt continuously over a trailing window and does NOT wait for late events. Read via serving_live_total / serving_live_content.';


-- -----------------------------------------------------------------------------
-- serving_concurrency_minute — 1-minute grain, six dimension masks
--
-- Masks materialized, and what each is for:
--
--    0  ungrouped                          the headline exact peak
--    1  platform                           exact peak per platform
--    2  country                            exact peak per country
--    3  platform + country                 named by the problem statement
--    4  content_id                         exact peak per title
--    5  platform + content                 named by the problem statement
--    8  video_type                         exact peak per VOD/live
--    9  platform + video_type
--   16  app_version                        exact peak per build
--   32  category                           exact peak per catalogue category
--   63  all six at once (full grain)       arbitrary filter combinations
--
-- 0/1/2/3/4/5/8/9 are policy masks (solution/policy.yaml:118-134); 16, 32 and 63
-- extend it with app_version, category and the full grain.
--
-- The policy's masks 12 and 15 are deliberately NOT materialized. A mask adds nothing
-- when the dimensions it introduces are functionally determined by the ones it already
-- has, and content_dim maps each content_id to exactly one video_type — so mask 12
-- cannot differ from mask 4, nor mask 15 from mask 5. Measured identical across 79,770
-- and 103,007 rows respectively, together 36.6% of the hot day for zero information.
-- That is a property of the catalogue, not of this extract, so it holds on any day.
--
-- Masks 2 and 3 are redundant today for the same reason (country is 'india'
-- throughout, verified identical to masks 0 and 1) but are kept: country is a business
-- dimension the problem statement names, the unseen day may carry more than one, and
-- they cost 0.58% of the day.
--
-- The combinations are the point, not padding. An exact peak has to be computed AT
-- the grouping it is reported for: measured on the hot hour, ANDROID_PHONE peaks at
-- 1,461 read from mask 1, while max() over mask 63 rows grouped by platform gives
-- 223 — understating it 6.5x, because a maximum of finer-grain peaks is not the peak
-- of the coarser grouping. The problem statement names platform+content and
-- platform+country as exactly this trap.
--
-- Combinations NOT in the list (platform + app_version, say) still get exact
-- averages and exact instantaneous counts from mask 63, because active_ms and
-- ending_concurrency are additive; only their peak degrades to an upper bound.
--
-- Mask 63 is what makes the dashboard's filters compose. Under a combined
-- filter, sum(active_ms) and sum(ending_concurrency) stay exact; max(minute_peak)
-- becomes an upper bound rather than the true peak, because the true peak for an
-- arbitrary dimension combination was never computed at that grouping. The
-- dashboard says so on its face rather than quietly rounding up.
--
-- Deliberately absent: audio_language, subtitle_language, player_version. All
-- three change mid-session — measured on the extract at 8,796 / 2,980 / 1,600
-- sessions respectively — so pinning a session to one value would move active
-- time between slices and break the conservation check in
-- concurrency/sql/090_validate_serving.sql. solution/policy.yaml:94-109 excludes
-- them from serving masks for the same reason. country IS carried, even though
-- the extract holds a single value ('india'), because an unseen day may not.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {{db}}.serving_concurrency_minute
(
    minute_start        DateTime('UTC')
        COMMENT 'Left edge of a 1-minute bucket, half-open [minute_start, +60s). Bucketed on absolute time, so an interval crossing midnight lands in both days without a clipping step',

    grouping            LowCardinality(String)
        COMMENT 'Readable 1:1 label for dim_mask. dim_mask is a bit field: right for computing, wrong in front of a business user, so nothing user-facing displays it. Carries a set index rather than leading the sort key — see the note below',

    dim_mask            UInt16
        COMMENT 'platform=1, country=2, content_id=4, video_type=8, app_version=16, category=32. Materialized: 0,1,2,3,4,5,8,9,16,32,63. Policy masks 12 and 15 are omitted as provably redundant — video_type is functionally determined by content_id',

    content_id          Int64,
    platform            LowCardinality(String) COMMENT 'Empty string when not selected by dim_mask',
    country             LowCardinality(String) COMMENT 'Empty string when not selected by dim_mask',
    app_version         LowCardinality(String) COMMENT 'Empty string when not selected by dim_mask',
    video_type          LowCardinality(String) COMMENT 'Empty string when not selected by dim_mask',
    category            LowCardinality(String) COMMENT 'Empty string when not selected by dim_mask',

    minute_peak         UInt32
        COMMENT 'NOT ADDITIVE. Exact max instantaneous concurrency in the minute at this row dim_mask only',

    ending_concurrency  UInt32
        COMMENT 'Additive across rows of one dim_mask at one minute_start',

    active_ms           UInt64
        COMMENT 'Additive everywhere. active_ms/60000 is the exact time-weighted average concurrency',

    sessions_active     UInt32 COMMENT 'Distinct sessions contributing any active time to this minute',
    sessions_started    UInt32 COMMENT 'Active intervals opening inside this minute',
    sessions_ended      UInt32 COMMENT 'Active intervals closing inside this minute',

    -- A dashboard selector filters on the readable label, not on the bit field, and a
    -- predicate on a non-key column normally reads every granule. This one does not,
    -- because the rows are physically clustered by dim_mask and grouping is 1:1 with
    -- it: every granule holds exactly one grouping value, so the set index resolves to
    -- the same granules a dim_mask predicate would. Leading the sort key with grouping
    -- would be equivalent, but changing ORDER BY needs DROP TABLE, which the service
    -- user deliberately does not hold.
    INDEX idx_grouping grouping TYPE set(16) GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(minute_start)
ORDER BY (dim_mask, minute_start, platform, video_type, category, app_version, content_id)
COMMENT 'Corrected concurrency at 1-minute grain, published on a lag so the late-arrival window has closed. Rebuilt a whole UTC day at a time via REPLACE PARTITION. Read via serving_minute_current.';


-- CREATE TABLE IF NOT EXISTS is a no-op against a database that already has these
-- tables, so a new column would never reach one. These make `schema` converge, the
-- same way 002 corrects its dedup settings. Metadata-only and idempotent.
ALTER TABLE {{db}}.serving_concurrency_minute
    ADD COLUMN IF NOT EXISTS grouping LowCardinality(String) AFTER minute_start;

ALTER TABLE {{db}}.serving_concurrency_minute
    ADD INDEX IF NOT EXISTS idx_grouping grouping TYPE set(16) GRANULARITY 1;


-- Staging table for the atomic day swap. Structure and engine must match
-- serving_concurrency_minute exactly or REPLACE PARTITION refuses the move.
-- Kept empty between rebuilds; the driver drops its partition after each swap.
CREATE TABLE IF NOT EXISTS {{db}}.serving_concurrency_minute_staging
    AS {{db}}.serving_concurrency_minute
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(minute_start)
ORDER BY (dim_mask, minute_start, platform, video_type, category, app_version, content_id)
COMMENT 'Scratch space for one day of serving_concurrency_minute, swapped in with REPLACE PARTITION. Never read directly.';

-- REPLACE PARTITION requires identical structure, so staging needs the column too.
ALTER TABLE {{db}}.serving_concurrency_minute_staging
    ADD COLUMN IF NOT EXISTS grouping LowCardinality(String) AFTER minute_start;

ALTER TABLE {{db}}.serving_concurrency_minute_staging
    ADD INDEX IF NOT EXISTS idx_grouping grouping TYPE set(16) GRANULARITY 1;


-- -----------------------------------------------------------------------------
-- serving_watermark — what each layer has published through
--
-- Both the freshness tiles and the "why is this layer behind" question read this
-- rather than inferring staleness from max(bucket_start). Those differ, and the
-- difference is the point: a live layer with no traffic has an old max bucket
-- but a current watermark, and conflating the two would show a healthy pipeline
-- as broken.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS {{db}}.serving_watermark
(
    layer           LowCardinality(String) COMMENT 'live | minute | intervals',
    watermark_ts    DateTime64(3, 'UTC')   COMMENT 'Events at or before this instant are reflected in the layer',
    built_at        DateTime64(3, 'UTC')   COMMENT 'Wall-clock completion of the rollup that set this watermark',
    policy_version  LowCardinality(String),
    intervals_in    UInt64 COMMENT 'session_intervals rows read',
    rows_out        UInt64 COMMENT 'serving rows written',
    build_ms        UInt64 COMMENT 'Rollup duration; the build-latency series on the observability dashboard',
    version         UInt64 COMMENT 'Milliseconds since epoch; higher wins'
)
ENGINE = ReplacingMergeTree(version)
ORDER BY layer
COMMENT 'One row per serving layer recording how current it is. Read with FINAL.';


-- Append-only history of the same rows, so the observability dashboard can plot
-- build duration over time. A ReplacingMergeTree keyed on layer cannot answer
-- that — it keeps exactly one row per layer by design.
CREATE TABLE IF NOT EXISTS {{db}}.serving_watermark_history
(
    layer           LowCardinality(String),
    watermark_ts    DateTime64(3, 'UTC'),
    built_at        DateTime64(3, 'UTC'),
    policy_version  LowCardinality(String),
    intervals_in    UInt64,
    rows_out        UInt64,
    build_ms        UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(built_at)
ORDER BY (layer, built_at)
TTL toDateTime(built_at) + INTERVAL 30 DAY
COMMENT 'Every rollup run, for the build-latency and throughput series.';


-- -----------------------------------------------------------------------------
-- Reader views. The only objects a dashboard tile should name.
--
-- They exist so that FINAL, the mask convention and the content_dict join are
-- written once here instead of being restated — and eventually mis-stated — in
-- every tile. dictGet rather than a JOIN because content_dict is already
-- resident and COMPLEX_KEY_HASHED, so enrichment costs a hash lookup per row
-- instead of a join build.
-- -----------------------------------------------------------------------------

-- Ungrouped live totals. The exact peak series, and the source of "concurrent now".
CREATE OR REPLACE VIEW {{db}}.serving_live_total AS
SELECT
    bucket_start,
    bucket_peak,
    ending_concurrency,
    active_ms,
    -- Exact time-weighted average concurrency across the 10-second bucket.
    active_ms / 10000.0 AS avg_concurrency
FROM {{db}}.serving_concurrency_live FINAL
WHERE dim_mask = 0;

-- Live per-title rows. ending_concurrency and active_ms may be summed across
-- titles at one bucket_start; bucket_peak may not.
CREATE OR REPLACE VIEW {{db}}.serving_live_content AS
SELECT
    bucket_start,
    content_id,
    -- Fallback is '__unknown__', NOT 'unknown'. 'unknown' is a REAL catalogue value —
    -- 1,089 of 33,464 titles carry video_type = 'unknown' — so using it as the miss
    -- default makes a cold-replica dictionary miss indistinguishable from real data.
    -- Dictionaries load per replica and an empty one still reports LOADED, so that
    -- miss is the documented silent failure, and it self-heals before you can look.
    -- With '__unknown__', `countIf(video_type = '__unknown__') > 0` is a valid alarm.
    -- '' is no good either: masks store '' for unselected dimensions, so it is
    -- ambiguous between "not carried by this mask" and "dictionary missed".
    -- Always carries content (mask 4), so there is no "not carried" case here and
    -- an unresolved id is the only reason to be empty. Name it.
    dictGetOrDefault({{db}}.content_dict, 'title',      tuple(content_id), '__unknown__') AS title,
    dictGetOrDefault({{db}}.content_dict, 'video_type', tuple(content_id), '__unknown__') AS video_type,
    dictGetOrDefault({{db}}.content_dict, 'category',   tuple(content_id), '__unknown__') AS category,
    bucket_peak,
    ending_concurrency,
    active_ms,
    active_ms / 10000.0 AS avg_concurrency
FROM {{db}}.serving_concurrency_live FINAL
WHERE dim_mask = 4;

-- The lagged analytical layer. No FINAL: the day-partition swap means every row
-- present is already the current one.
CREATE OR REPLACE VIEW {{db}}.serving_minute_current AS
SELECT
    minute_start,
    grouping,
    -- The dimension VALUES this row is for, as one readable label: 'IPHONE · live',
    -- 'ANDROID_PHONE · Some Title'. Only the dimensions the row's grouping selects are
    -- populated, so dropping the blanks yields exactly the right label without the
    -- caller needing to know which bits are set. Ungrouped rows have no dimensions at
    -- all and read 'all'.
    if(empty(dim_label), 'all', dim_label) AS dim_values,
    dim_mask,
    content_id,
    -- Two different absences, two different values, and tiles depend on the
    -- difference. '' means this row's mask does not carry a content dimension at
    -- all. '__unknown__' means it does, but the id did not resolve — either
    -- missing from the catalogue or a cold-replica dictionary.
    --
    -- Before this, both were '', so the leaderboard's `title != ''` predicate --
    -- there to drop rows that carry no content -- ALSO dropped real viewing of
    -- unresolvable titles, silently and with no row count to reveal it. Zero rows
    -- on this extract (all 3,352 titles resolve, all 1,779.50 viewer-hours kept),
    -- but the unseen day has a fresh catalogue and no such guarantee.
    if(content_id = 0, '',
       dictGetOrDefault({{db}}.content_dict, 'title', tuple(content_id), '__unknown__')) AS title,
    platform,
    country,
    app_version,
    -- video_type and category are FUNCTIONALLY DETERMINED by content_id — the catalogue
    -- maps each content_id to exactly one of each — so wherever a row carries a
    -- content_id they can be resolved from the dictionary even when the row's mask did
    -- not select them. Without this, masks 4 and 5 render both columns blank and a
    -- filter on either silently returns zero rows against 31,537 content rows that
    -- could have answered it. serving_live_content already resolves all three; this
    -- brings the minute layer in line.
    --
    -- Fill-only-when-blank, never overwrite: at masks 8/9/32/63 the value is stored on
    -- the row and is authoritative, so it is passed through untouched. The dictionary is
    -- consulted only where the mask left a placeholder AND a content_id is present.
    --
    -- This does NOT make a filtered peak correct at every grouping. minute_peak is exact
    -- only at the row's own mask: filter mask 4 by category and max(minute_peak) gives
    -- the busiest single TITLE in that category (measured 14), not the category's peak
    -- (measured 46). For a category peak, read grouping = 'category'. The average is
    -- safe either way — active_ms is additive, and both paths give 11.012060.
    -- '__unknown__' on a miss, not '' — see the note on serving_live_content above.
    -- '' would be ambiguous here in particular, because that is exactly what an
    -- unselected dimension already stores.
    if(empty(video_type) AND content_id != 0,
       dictGetOrDefault({{db}}.content_dict, 'video_type', tuple(content_id), '__unknown__'),
       video_type) AS video_type,
    if(empty(category) AND content_id != 0,
       dictGetOrDefault({{db}}.content_dict, 'category', tuple(content_id), '__unknown__'),
       category) AS category,
    minute_peak,
    ending_concurrency,
    active_ms,
    -- Exact time-weighted average concurrency across the minute. Safe to average
    -- over a window and to sum across dimensions — unlike minute_peak.
    active_ms / 60000.0 AS avg_concurrency,
    sessions_active,
    sessions_started,
    sessions_ended
FROM
(
    SELECT
        *,
        arrayStringConcat(arrayFilter(x -> x != '', [
            platform,
            country,
            video_type,
            category,
            app_version,
            if(content_id = 0, '',
               dictGetOrDefault({{db}}.content_dict, 'title', tuple(content_id), toString(content_id)))
        ]), ' · ') AS dim_label
    FROM {{db}}.serving_concurrency_minute
);
