-- ============================================================================
-- 05_unseen_data_schema.sql — exact, live DDL for the "_v2" pipeline
-- (unseen-day dataset: adds video_resolution + show_name columns).
-- Deployed on the same ClickHouse Cloud instance as the non-suffixed "_v1"
-- pipeline in 04_ddl_annotated.sql, side by side, zero shared objects.
--
-- STATUS: DEPLOYED. 1:1 mirror of `SHOW CREATE TABLE` on the live instance.
-- Full reasoning, worked examples, and the bug list live in
-- PIPELINE_LOGIC.md and README.md — this file is DDL only.
--
-- Build order:
--   1.  bronze_events_raw_v2, bronze_content_raw_v2
--   2.  session_live_state_v2
--   3.  session_transition_log_v2
--   4.  mv_session_transition_log_v2       (TO #3)
--   5.  mv_to_session_live_state_v2        (TO #2)
--   6.  silver_active_intervals_v2
--   7.  mv_to_silver_active_intervals_v2   (TO #6)
--   8.  gold_concurrency_minute_v2  (G1)
--   9.  mv_gold_concurrency_minute_v2      (TO #8)
--  10.  gold_concurrency_delta_v2   (G2)
--  11.  mv_gold_concurrency_delta_v2       (TO #10)
-- ============================================================================


-- ============================================================================
-- 1. BRONZE
-- ============================================================================
CREATE TABLE bronze_events_raw_v2
(
    `content_id`         Int64,
    `video_session_id`   String,
    `user_id`            String,
    `event_type`         String,
    `event`              String,
    `event_timestamp`    Int64,
    `platform`           String,
    `app_version`        String,
    `country`            String,
    `audio_language`     Nullable(String),
    `subtitle_language`  Nullable(String),
    `player_version`     Nullable(String),
    `video_resolution`   Nullable(String),
    `session_start_epoch` Int64,

    INDEX idx_app_version       app_version       TYPE bloom_filter GRANULARITY 4,
    INDEX idx_audio_language    audio_language    TYPE bloom_filter GRANULARITY 4,
    INDEX idx_subtitle_language subtitle_language TYPE bloom_filter GRANULARITY 4,
    INDEX idx_player_version    player_version     TYPE bloom_filter GRANULARITY 4
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY toYYYYMM(toDateTime(intDiv(session_start_epoch, 1000)))
ORDER BY (video_session_id, event, event_timestamp);

CREATE TABLE bronze_content_raw_v2
(
    `content_id` Int64,
    `title`      String,
    `video_type` LowCardinality(String),
    `category`   LowCardinality(String),
    `show_name`  LowCardinality(String)
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY content_id;


-- ============================================================================
-- 2. SILVER — session_live_state_v2 (current status per session)
-- ============================================================================
CREATE TABLE session_live_state_v2
(
    session_id                 FixedString(64),
    is_active                  UInt8,
    current_interval_start_ms  Int64,
    last_seen_ms               Int64,
    has_close                  UInt8,
    platform                   LowCardinality(String),
    country                    LowCardinality(String),
    content_id                 Int64,
    video_type                 LowCardinality(String),
    show_name                  LowCardinality(String),
    video_resolution           LowCardinality(String),
    version                    Int64
)
ENGINE = SharedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', version)
ORDER BY session_id;


-- ============================================================================
-- 3. SILVER — session_transition_log_v2 (staging table, not queried directly)
-- ============================================================================
CREATE TABLE session_transition_log_v2
(
    kind                       Enum8('state' = 1, 'interval' = 2),
    session_id                 FixedString(64),
    is_active                  UInt8,
    current_interval_start_ms  Int64,
    start_ms                   Int64,
    end_ms                     Int64,
    last_seen_ms               Int64,
    has_close                  UInt8,
    platform                   LowCardinality(String),
    country                    LowCardinality(String),
    content_id                 Int64,
    video_type                 LowCardinality(String),
    show_name                  LowCardinality(String),
    video_resolution           LowCardinality(String),
    version                    Int64,
    inserted_at                DateTime DEFAULT now()
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY (kind, session_id, version)
TTL inserted_at + INTERVAL 3 DAY DELETE;


-- ============================================================================
-- 4. SILVER — mv_session_transition_log_v2 (the whole state machine)
-- ============================================================================
CREATE MATERIALIZED VIEW mv_session_transition_log_v2
TO session_transition_log_v2 AS
SELECT * FROM (
WITH
    60000 AS gap_ms,
    tagged AS (
        SELECT
            CAST(b.video_session_id, 'FixedString(64)') AS session_id,
            b.event_timestamp AS ts,
            upper(trim(b.platform)) AS platform,
            b.country, b.content_id,
            coalesce(nullIf(c.video_type, ''), 'unk') AS video_type,
            coalesce(nullIf(c.show_name, ''), 'unk') AS show_name,
            coalesce(replace(b.video_resolution, ' ', ''), '') AS video_resolution_raw,
            isNotNull(b.video_resolution) AS has_resolution,
            CASE b.event_type
                 WHEN 'VideoSessionStart' THEN CAST(1  AS Int8)
                 WHEN 'VideoSessionEnd'   THEN CAST(-1 AS Int8)
                 WHEN 'AppBackgrounded'   THEN CAST(0  AS Int8)
                 WHEN 'AppForegrounded'   THEN CAST(1  AS Int8)
                 ELSE CASE WHEN b.event = 'Play' THEN CAST(1 AS Int8) ELSE NULL END
            END AS st
        FROM bronze_events_raw_v2 b
        LEFT JOIN bronze_content_raw_v2 c ON c.content_id = b.content_id
    ),
    prior AS (
        SELECT session_id,
               argMax(is_active, version) AS is_active,
               argMax(current_interval_start_ms, version) AS current_interval_start_ms,
               argMax(last_seen_ms, version) AS last_seen_ms,
               argMax(has_close, version) AS has_close,
               argMax(platform, version) AS platform,
               argMax(country, version) AS country,
               argMax(content_id, version) AS content_id,
               argMax(video_type, version) AS video_type,
               argMax(show_name, version) AS show_name,
               argMax(video_resolution, version) AS video_resolution
        FROM session_live_state_v2
        WHERE session_id IN (SELECT DISTINCT session_id FROM tagged)
        GROUP BY session_id
    ),
    all_pulses AS (
        SELECT session_id, ts FROM tagged
        UNION ALL
        SELECT session_id, last_seen_ms AS ts FROM prior
    ),
    lp AS (
        SELECT session_id, ts, lagInFrame(ts) OVER (PARTITION BY session_id ORDER BY ts) AS prev
        FROM all_pulses
    ),
    gaps AS (
        SELECT session_id, prev + gap_ms AS gap_ts, CAST(0 AS Int8) AS st FROM lp WHERE prev > 0 AND ts - prev > gap_ms
        UNION ALL
        SELECT session_id, ts AS gap_ts,             CAST(1 AS Int8) AS st FROM lp WHERE prev > 0 AND ts - prev > gap_ms
    ),
    seed AS (
        SELECT session_id, last_seen_ms AS gap_ts, toInt8(is_active) AS st, 1 AS is_seed
        FROM prior
    ),
    watermark_open AS (
        SELECT session_id, min(ts) AS gap_ts, CAST(1 AS Int8) AS st, 0 AS is_seed
        FROM tagged
        WHERE session_id NOT IN (SELECT session_id FROM prior)
        GROUP BY session_id
    ),
    combined AS (
        SELECT session_id, ts AS gap_ts, st, 0 AS is_seed FROM tagged WHERE st IS NOT NULL
        UNION ALL
        SELECT session_id, gap_ts, st, 0 AS is_seed FROM gaps
        UNION ALL
        SELECT session_id, gap_ts, st, is_seed FROM seed
        UNION ALL
        SELECT session_id, gap_ts, st, is_seed FROM watermark_open
    ),
    dedup AS (SELECT session_id, gap_ts, min(st) AS st, max(is_seed) AS is_seed FROM combined GROUP BY 1, 2),
    marked AS (
        SELECT *, lagInFrame(st) OVER (PARTITION BY session_id ORDER BY gap_ts) AS pv,
               count() OVER (PARTITION BY session_id ORDER BY gap_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS rn
        FROM dedup
    ),
    changed AS (SELECT session_id, gap_ts, st FROM marked WHERE (rn = 1 OR st != pv) AND is_seed = 0),
    changed_with_seed AS (
        SELECT session_id, gap_ts, st FROM changed
        UNION ALL
        SELECT session_id, gap_ts, st FROM seed
    ),
    paired AS (
        SELECT session_id, gap_ts AS a, st,
               leadInFrame(gap_ts) OVER (PARTITION BY session_id ORDER BY gap_ts ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS b,
               row_number() OVER (PARTITION BY session_id ORDER BY gap_ts DESC) AS rn_desc
        FROM changed_with_seed
    ),
    new_dims AS (
        SELECT session_id,
               argMin(platform, ts) AS platform, argMin(country, ts) AS country,
               argMin(content_id, ts) AS content_id, argMin(video_type, ts) AS video_type,
               argMin(show_name, ts) AS show_name,
               argMinIf(video_resolution_raw, ts, has_resolution) AS video_resolution
        FROM tagged GROUP BY session_id
    ),
    last_pulse AS ( SELECT session_id, max(ts) AS last_seen_ms FROM all_pulses GROUP BY session_id ),
    resolved AS (
        SELECT
            p.session_id AS session_id, p.a AS a, p.st AS st, p.b AS b, p.rn_desc AS rn_desc,
            coalesce(pr.platform, nd.platform) AS platform,
            coalesce(pr.country, nd.country) AS country,
            coalesce(pr.content_id, nd.content_id) AS content_id,
            coalesce(pr.video_type, nd.video_type) AS video_type,
            coalesce(pr.show_name, nd.show_name) AS show_name,
            coalesce(nullIf(coalesce(pr.video_resolution, nd.video_resolution), ''), 'unk') AS video_resolution,
            coalesce(pr.has_close, 0) AS prior_has_close,
            lp.last_seen_ms AS last_seen_ms
        FROM paired p
        JOIN new_dims nd ON nd.session_id = p.session_id
        JOIN last_pulse lp ON lp.session_id = p.session_id
        LEFT JOIN prior pr ON pr.session_id = p.session_id
        SETTINGS join_use_nulls = 1
    )
SELECT
    CAST('state' AS Enum8('state' = 1, 'interval' = 2)) AS kind,
    session_id, toUInt8(st = 1) AS is_active, if(st = 1, a, 0) AS current_interval_start_ms,
    0 AS start_ms, 0 AS end_ms,
    last_seen_ms, toUInt8(prior_has_close = 1 OR st = -1) AS has_close,
    platform, country, content_id, video_type, show_name, video_resolution, last_seen_ms AS version
FROM resolved WHERE rn_desc = 1

UNION ALL

SELECT
    CAST('interval' AS Enum8('state' = 1, 'interval' = 2)) AS kind,
    session_id, 0 AS is_active, 0 AS current_interval_start_ms,
    a AS start_ms, b AS end_ms,
    last_seen_ms, 0 AS has_close,
    platform, country, content_id, video_type, show_name, video_resolution, last_seen_ms AS version
FROM resolved WHERE st = 1 AND rn_desc > 1 AND b > a
);


-- ============================================================================
-- 5. SILVER — mv_to_session_live_state_v2
-- ============================================================================
CREATE MATERIALIZED VIEW mv_to_session_live_state_v2
TO session_live_state_v2 AS
SELECT session_id, is_active, current_interval_start_ms, last_seen_ms, has_close,
       platform, country, content_id, video_type, show_name, video_resolution, version
FROM session_transition_log_v2
WHERE kind = 'state';


-- ============================================================================
-- 6. SILVER — silver_active_intervals_v2 (completed [start,end) intervals)
-- ============================================================================
CREATE TABLE silver_active_intervals_v2
(
    session_id       FixedString(64),
    start_ms         Int64,
    end_ms           Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    content_id       Int64,
    video_type       LowCardinality(String),
    show_name        LowCardinality(String),
    video_resolution LowCardinality(String),
    version          Int64,

    INDEX idx_video_resolution video_resolution TYPE bloom_filter GRANULARITY 4
)
ENGINE = SharedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', version)
PARTITION BY toYYYYMM(fromUnixTimestamp64Milli(start_ms))
ORDER BY (session_id, start_ms)
TTL fromUnixTimestamp64Milli(end_ms) + INTERVAL 30 DAY DELETE;


-- ============================================================================
-- 7. SILVER — mv_to_silver_active_intervals_v2
-- ============================================================================
CREATE MATERIALIZED VIEW mv_to_silver_active_intervals_v2
TO silver_active_intervals_v2 AS
SELECT session_id, start_ms, end_ms, platform, country, content_id, video_type, show_name, video_resolution, version
FROM session_transition_log_v2
WHERE kind = 'interval';


-- ============================================================================
-- 8. GOLD — gold_concurrency_minute_v2 (G1, session-aware)
-- ============================================================================
CREATE TABLE gold_concurrency_minute_v2
(
    minute                DateTime,
    platform              LowCardinality(String),
    country               LowCardinality(String),
    video_type            LowCardinality(String),
    show_name             LowCardinality(String),
    video_resolution_tier LowCardinality(String),
    content_id            Int64,
    cnt_a                 AggregateFunction(uniqExact, FixedString(64)),
    cnt_b                 AggregateFunction(uniqExact, FixedString(64))
)
ENGINE = SharedAggregatingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY toYYYYMM(minute)
ORDER BY (country, video_type, show_name, video_resolution_tier, platform, content_id, minute);


-- ============================================================================
-- 9. GOLD — mv_gold_concurrency_minute_v2
-- ============================================================================
CREATE MATERIALIZED VIEW mv_gold_concurrency_minute_v2
TO gold_concurrency_minute_v2 AS
SELECT
    minute, platform, country, video_type, show_name,
    multiIf(
        mindim >= 2160, '4K',
        mindim >= 1080, '1080p',
        mindim >= 720,  '720p',
        mindim >= 540,  '540p',
        mindim >= 480,  '480p',
        mindim >= 360,  '360p',
        mindim >= 240,  '240p',
        mindim > 0,     'below_240p',
        'unk'
    ) AS video_resolution_tier,
    content_id,
    uniqExactStateIf(session_id, kind = 'a') AS cnt_a,
    uniqExactStateIf(session_id, kind = 'b') AS cnt_b
FROM
(
    SELECT
        toDateTime(minute_id * 60) AS minute,
        platform, country, video_type, show_name, content_id, session_id, 'a' AS kind,
        least(
            nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[1]), 0),
            nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[2]), 0)
        ) AS mindim
    FROM silver_active_intervals_v2
    ARRAY JOIN range(
        toUInt32(ceil(start_ms / 60000.)),
        toUInt32(ceil(end_ms   / 60000.))
    ) AS minute_id
    WHERE end_ms > start_ms

    UNION ALL

    SELECT
        toDateTime(minute_id * 60) AS minute,
        platform, country, video_type, show_name, content_id, session_id, 'b' AS kind,
        least(
            nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[1]), 0),
            nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[2]), 0)
        ) AS mindim
    FROM silver_active_intervals_v2
    ARRAY JOIN range(
        toUInt32(intDiv(start_ms, 60000)),
        toUInt32(intDiv(end_ms - 1, 60000)) + 1
    ) AS minute_id
    WHERE end_ms > start_ms
)
GROUP BY minute, platform, country, video_type, show_name, video_resolution_tier, content_id;


-- ============================================================================
-- 10. GOLD — gold_concurrency_delta_v2 (G2, session-independent)
-- ============================================================================
CREATE TABLE gold_concurrency_delta_v2
(
    minute                DateTime,
    platform              LowCardinality(String),
    country                LowCardinality(String),
    video_type             LowCardinality(String),
    show_name              LowCardinality(String),
    video_resolution_tier  LowCardinality(String),
    content_id             Int64,
    delta_kind             LowCardinality(FixedString(1)),
    delta                  Int64
)
ENGINE = SharedSummingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY toYYYYMM(minute)
ORDER BY (country, video_type, show_name, video_resolution_tier, platform, content_id, minute, delta_kind);


-- ============================================================================
-- 11. GOLD — mv_gold_concurrency_delta_v2
-- ============================================================================
CREATE MATERIALIZED VIEW mv_gold_concurrency_delta_v2
TO gold_concurrency_delta_v2 AS
SELECT minute, platform, country, video_type, show_name,
    multiIf(
        mindim >= 2160, '4K', mindim >= 1080, '1080p', mindim >= 720, '720p',
        mindim >= 540, '540p', mindim >= 480, '480p', mindim >= 360, '360p',
        mindim >= 240, '240p', mindim > 0, 'below_240p', 'unk'
    ) AS video_resolution_tier,
    content_id, delta_kind, sum(delta) AS delta
FROM
(
    SELECT toDateTime(toUInt32(ceil(start_ms / 60000.)) * 60) AS minute,
           platform, country, video_type, show_name, content_id,
           least(nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[1]), 0),
                 nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[2]), 0)) AS mindim,
           'a' AS delta_kind, toInt64(1) AS delta
    FROM silver_active_intervals_v2 WHERE end_ms > start_ms
    UNION ALL
    SELECT toDateTime(toUInt32(ceil(end_ms / 60000.)) * 60),
           platform, country, video_type, show_name, content_id,
           least(nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[1]), 0),
                 nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[2]), 0)),
           'a', toInt64(-1)
    FROM silver_active_intervals_v2 WHERE end_ms > start_ms

    UNION ALL

    SELECT toDateTime(toUInt32(intDiv(start_ms, 60000)) * 60),
           platform, country, video_type, show_name, content_id,
           least(nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[1]), 0),
                 nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[2]), 0)),
           'b', toInt64(1)
    FROM silver_active_intervals_v2 WHERE end_ms > start_ms
    UNION ALL
    SELECT toDateTime(toUInt32(intDiv(end_ms - 1, 60000) + 1) * 60),
           platform, country, video_type, show_name, content_id,
           least(nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[1]), 0),
                 nullIf(toUInt32OrZero(extractGroups(video_resolution, '(\\d+)\\s*\\*\\s*(\\d+)')[2]), 0)),
           'b', toInt64(-1)
    FROM silver_active_intervals_v2 WHERE end_ms > start_ms
)
GROUP BY minute, platform, country, video_type, show_name, video_resolution_tier, content_id, delta_kind;
