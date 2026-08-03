-- ============================================================================
-- SonyLIV foreground-only concurrency — schema (tables + materialized views).
-- Session-INDEPENDENT live/historical model. All objects in database `sonyliv`.
-- Runner splits on ';' (no ';' appears inside a statement).
--
-- Refreshable MV needs the flag:  SET allow_experimental_refreshable_materialized_view = 1;
-- ============================================================================

CREATE DATABASE IF NOT EXISTS sonyliv;

-- ── raw_events: typed, normalized landing table ───────────────────────────────
-- ReplacingMergeTree collapses exact-duplicate events (same session+ts+type+event).
-- NO PARTITION BY: the feed contains garbage/outlier timestamps (seen spanning
-- 2015→2026); partitioning by day would scatter parts across hundreds of
-- partitions and trip "too many parts". For a bounded streaming deployment,
-- partition by toYYYYMM(event_timestamp) + a TTL, and clamp out-of-range ts.
CREATE TABLE IF NOT EXISTS sonyliv.raw_events
(
    content_id        String,
    video_session_id  String,
    user_id           String,
    event_type        LowCardinality(String),
    event             LowCardinality(String),
    event_timestamp   DateTime64(3, 'UTC') CODEC(Delta, ZSTD(1)),
    platform          LowCardinality(String),
    app_version       LowCardinality(String),
    country           LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    session_start_epoch DateTime64(3, 'UTC') CODEC(Delta, ZSTD(1)),
    video_resolution  LowCardinality(String) DEFAULT '',
    _ingested_at      DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree
ORDER BY (video_session_id, event_timestamp, event_type, event);

-- ── content_raw + content_dict: enrichment via dictGet (no runtime JOIN) ──────
CREATE TABLE IF NOT EXISTS sonyliv.content_raw
(
    content_id String, title String, video_type LowCardinality(String),
    category LowCardinality(String), show_name String DEFAULT ''
)
ENGINE = ReplacingMergeTree ORDER BY content_id;

CREATE DICTIONARY IF NOT EXISTS sonyliv.content_dict
(
    content_id String, title String, video_type String, category String, show_name String
)
PRIMARY KEY content_id
SOURCE(CLICKHOUSE(TABLE 'content_raw' DB 'sonyliv'))
LAYOUT(COMPLEX_KEY_HASHED()) LIFETIME(MIN 300 MAX 600);

-- ── live_sessions: ONE row per session = its current foreground state ─────────
-- AggregatingMergeTree. `state` = argMax over STATE-changing events only, so a
-- plain heartbeat (ts 0) can NEVER flip it → a stray beat during a pause bumps
-- freshness but keeps state='paused' (fixes the ~18% stateless over-count).
-- `last_beat` = max over ALL events; a SimpleAggregateFunction so it is directly readable
-- (no maxMerge) and can drive the table TTL below. dims = argMax (current value).
CREATE TABLE IF NOT EXISTS sonyliv.live_sessions
(
    video_session_id  String,
    state             AggregateFunction(argMax, String, DateTime64(3,'UTC')),  -- active|paused|background|ended
    last_beat         SimpleAggregateFunction(max, DateTime64(3,'UTC')),
    content_id        AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    platform          AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    app_version       AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    video_type        AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    country           AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    video_resolution  AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    audio_language    AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    subtitle_language AggregateFunction(argMax, String, DateTime64(3,'UTC')),
    player_version    AggregateFunction(argMax, String, DateTime64(3,'UTC'))
)
ENGINE = AggregatingMergeTree ORDER BY video_session_id
-- Physical TTL: a session idle > 15 min is gone; evict it so the state table stays
-- bounded and the per-minute refresh scans only recently-live sessions. 15 min >> the
-- 90 s freshness window, leaving slack for out-of-order / late-arriving heartbeats.
TTL toDateTime(last_beat) + INTERVAL 15 MINUTE;

-- ── hist_minute_full: per-minute concurrency by ALL dims (incl. per-event) ────
CREATE TABLE IF NOT EXISTS sonyliv.hist_minute_full
(
    minute            DateTime('UTC'),
    content_id        String,
    platform          LowCardinality(String),
    app_version       LowCardinality(String),
    video_type        LowCardinality(String),
    country           LowCardinality(String),
    video_resolution  LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    cnt               UInt32
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(minute)
ORDER BY (minute, content_id, platform, app_version, video_type, country, video_resolution, audio_language, subtitle_language, player_version);

-- ── mv_live_sessions: real-time — every event updates the session's live state ─
CREATE MATERIALIZED VIEW IF NOT EXISTS sonyliv.mv_live_sessions TO sonyliv.live_sessions AS
SELECT
    video_session_id,
    argMaxState(
        multiIf(event_type='VideoHeartbeat' AND event='pause','paused',
                event_type='AppBackgrounded','background',
                event_type='VideoSessionEnd','ended','active'),
        if((event_type='VideoHeartbeat' AND event IN ('pause','resume'))
           OR event_type IN ('AppBackgrounded','AppForegrounded','VideoPlay','VideoSessionStart','VideoSessionEnd'),
           event_timestamp, toDateTime64(0,3,'UTC'))
    ) AS state,
    max(event_timestamp)                            AS last_beat,
    argMaxState(content_id, event_timestamp)        AS content_id,
    argMaxState(platform, event_timestamp)          AS platform,
    argMaxState(app_version, event_timestamp)       AS app_version,
    argMaxState(vt, event_timestamp)                AS video_type,
    argMaxState(country, event_timestamp)           AS country,
    argMaxState(video_resolution, event_timestamp)  AS video_resolution,
    argMaxState(audio_language, event_timestamp)    AS audio_language,
    argMaxState(subtitle_language, event_timestamp) AS subtitle_language,
    argMaxState(player_version, event_timestamp)    AS player_version
FROM (
    SELECT video_session_id, event_type, event, event_timestamp,
           content_id, platform, app_version, country, video_resolution, audio_language, subtitle_language, player_version,
           if(empty(dictGetOrDefault('sonyliv.content_dict','video_type',tuple(content_id),'')),'unknown',
              dictGetOrDefault('sonyliv.content_dict','video_type',tuple(content_id),'unknown')) AS vt
    FROM sonyliv.raw_events
)
GROUP BY video_session_id;

-- ── mv_hist_refresh: the inbuilt per-minute "cron" (no external scheduler) ─────
-- Refreshable MV: snapshots active+fresh live_sessions into history every minute.
-- LIVE-streaming path (now()); for a batch/unseen-day CSV use 02_backfill_hist.sql.
CREATE MATERIALIZED VIEW IF NOT EXISTS sonyliv.mv_hist_refresh
REFRESH EVERY 1 MINUTE APPEND
TO sonyliv.hist_minute_full AS
SELECT
    toStartOfMinute(now()) AS minute,
    content_id, platform, app_version, video_type, country, video_resolution, audio_language, subtitle_language, player_version,
    toUInt32(count()) AS cnt
FROM (
    SELECT video_session_id,
        argMaxMerge(state) AS st, max(last_beat) AS lb,
        argMaxMerge(content_id) AS content_id, argMaxMerge(platform) AS platform,
        argMaxMerge(app_version) AS app_version,
        argMaxMerge(video_type) AS video_type, argMaxMerge(country) AS country,
        argMaxMerge(video_resolution) AS video_resolution, argMaxMerge(audio_language) AS audio_language,
        argMaxMerge(subtitle_language) AS subtitle_language, argMaxMerge(player_version) AS player_version
    FROM sonyliv.live_sessions GROUP BY video_session_id
)
WHERE st = 'active' AND lb > now64(3) - INTERVAL 90 SECOND
GROUP BY minute, content_id, platform, app_version, video_type, country, video_resolution, audio_language, subtitle_language, player_version;
