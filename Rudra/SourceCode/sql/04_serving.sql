-- ============================================================================
-- Read-optimized serving tier, built from hist_minute_full (the base).
-- Two tables, each sorted for its own query pattern; a query is routed to the
-- smallest one that covers its filter set (see 05_benchmark.sql / ui/server.mjs):
--
--   dim_minute      (dim, value, minute)  -> total + ANY single-dim filter.
--                   Keyed so `dim='platform',value='X'` prunes to ONE granule.
--   concurrency_1m  (dims-first, minute LAST) -> multi-dim / content-attribute
--                   combos. Leading-dim equality prunes via the primary index.
--
-- n_sessions is a PLAIN ADDITIVE sum and that is EXACT: dimensions are frozen per
-- session (03_build), so each session lives in exactly one cell per minute and the
-- cells partition the sessions -> summing disjoint counts can never double-count.
-- (Set/uniq states would also be correct but were measured ~300x slower to merge.)
-- ============================================================================

-- ── concurrency_1m: full dimension grain, dims-first for multi-dim prefix pruning ──
CREATE TABLE IF NOT EXISTS sonyliv.concurrency_1m
(
    platform          LowCardinality(String),
    country           LowCardinality(String),
    video_type        LowCardinality(String),
    audio_language    LowCardinality(String),
    app_version       LowCardinality(String),
    player_version    LowCardinality(String),
    subtitle_language LowCardinality(String),
    video_resolution  LowCardinality(String),
    content_id        String,
    minute            DateTime('UTC'),
    n_sessions        SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(minute)
ORDER BY (platform, country, video_type, audio_language, app_version,
          player_version, subtitle_language, video_resolution, content_id, minute);

INSERT INTO sonyliv.concurrency_1m
SELECT platform, country, video_type, audio_language, app_version, player_version,
       subtitle_language, video_resolution, content_id, minute, sum(cnt)
FROM sonyliv.hist_minute_full
GROUP BY platform, country, video_type, audio_language, app_version, player_version,
         subtitle_language, video_resolution, content_id, minute;

-- ── dim_minute: per-(dimension,value,minute) marginals + a `_total` pseudo-dim ──
CREATE TABLE IF NOT EXISTS sonyliv.dim_minute
(
    dim        LowCardinality(String),
    value      String,
    minute     DateTime('UTC'),
    n_sessions SimpleAggregateFunction(sum, UInt64)
)
ENGINE = AggregatingMergeTree
ORDER BY (dim, value, minute);

-- one INSERT per dimension (exact, since cells partition sessions) + the grand total
INSERT INTO sonyliv.dim_minute SELECT 'platform',          platform,          minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY platform, minute;
INSERT INTO sonyliv.dim_minute SELECT 'country',           country,           minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY country, minute;
INSERT INTO sonyliv.dim_minute SELECT 'video_type',        video_type,        minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY video_type, minute;
INSERT INTO sonyliv.dim_minute SELECT 'audio_language',    audio_language,    minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY audio_language, minute;
INSERT INTO sonyliv.dim_minute SELECT 'app_version',       app_version,       minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY app_version, minute;
INSERT INTO sonyliv.dim_minute SELECT 'player_version',    player_version,    minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY player_version, minute;
INSERT INTO sonyliv.dim_minute SELECT 'subtitle_language', subtitle_language, minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY subtitle_language, minute;
INSERT INTO sonyliv.dim_minute SELECT 'video_resolution',  video_resolution,  minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY video_resolution, minute;
INSERT INTO sonyliv.dim_minute SELECT 'content_id',        content_id,        minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY content_id, minute;
INSERT INTO sonyliv.dim_minute SELECT '_total',            '',                minute, sum(cnt) FROM sonyliv.hist_minute_full GROUP BY minute;

-- Live path (optional): replace the INSERTs above with incremental MVs off the source
-- so the rollups stay current; on an immutable historical day the one-shot build suffices.
