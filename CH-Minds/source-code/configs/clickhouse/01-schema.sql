-- Runs after 00-init-db.sh; the ro user it creates must exist before the
-- GRANT at the bottom.

CREATE DATABASE IF NOT EXISTS inmobi_rca;

CREATE TABLE IF NOT EXISTS inmobi_rca.ad_events
(
    event_time      DateTime CODEC(DoubleDelta, ZSTD),
    app_id          LowCardinality(String),
    geo_device_id   String,
    advertiser_id   String,
    ad_format       LowCardinality(String),
    is_filled       UInt8,
    is_impression   UInt8,
    is_click        UInt8,
    revenue         Float64
)
ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (event_time, ad_format, app_id);

CREATE TABLE IF NOT EXISTS inmobi_rca.apps
(
    app_id          String,
    category        LowCardinality(String),
    publisher_tier  LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY app_id;

CREATE TABLE IF NOT EXISTS inmobi_rca.advertisers
(
    advertiser_id   String,
    vertical        LowCardinality(String),
    campaign_type   LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS inmobi_rca.geo_device
(
    geo_device_id   String,
    region          LowCardinality(String),
    country         LowCardinality(String),
    device_model    LowCardinality(String),
    os_version      LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY geo_device_id;

-- ORDER BY must list all 10 grouping columns - for AggregatingMergeTree,
-- ORDER BY is a row's merge identity, and any column left out gets silently
-- corrupted on background merge. See INMOBI_CONTEXT.md for the incident.
CREATE TABLE IF NOT EXISTS inmobi_rca.hourly_segment_metrics
(
    hour            DateTime,
    ad_format       LowCardinality(String),
    category        LowCardinality(String),
    publisher_tier  LowCardinality(String),
    vertical        LowCardinality(String),
    campaign_type   LowCardinality(String),
    region          LowCardinality(String),
    country         LowCardinality(String),
    device_model    LowCardinality(String),
    os_version      LowCardinality(String),
    requests        AggregateFunction(count),
    fills           AggregateFunction(sum, UInt8),
    impressions     AggregateFunction(sum, UInt8),
    clicks          AggregateFunction(sum, UInt8),
    revenue         AggregateFunction(sum, Float64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toDate(hour)
ORDER BY (hour, ad_format, category, publisher_tier, vertical, campaign_type, region, country, device_model, os_version);

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi_rca.mv_hourly_segment_metrics
TO inmobi_rca.hourly_segment_metrics
AS
SELECT
    toStartOfHour(e.event_time)     AS hour,
    e.ad_format                     AS ad_format,
    a.category                      AS category,
    a.publisher_tier                AS publisher_tier,
    coalesce(adv.vertical, '')      AS vertical,
    coalesce(adv.campaign_type, '') AS campaign_type,
    g.region                        AS region,
    g.country                       AS country,
    g.device_model                  AS device_model,
    g.os_version                    AS os_version,
    countState()                    AS requests,
    sumState(e.is_filled)           AS fills,
    sumState(e.is_impression)       AS impressions,
    sumState(e.is_click)            AS clicks,
    sumState(e.revenue)             AS revenue
FROM inmobi_rca.ad_events AS e
LEFT JOIN inmobi_rca.apps AS a ON e.app_id = a.app_id
LEFT JOIN inmobi_rca.advertisers AS adv ON e.advertiser_id = adv.advertiser_id
LEFT JOIN inmobi_rca.geo_device AS g ON e.geo_device_id = g.geo_device_id
GROUP BY hour, ad_format, category, publisher_tier, vertical, campaign_type, region, country, device_model, os_version;

CREATE TABLE IF NOT EXISTS inmobi_rca.anomaly_candidates
(
    id             UUID DEFAULT generateUUIDv4(),
    detected_at    DateTime DEFAULT now(),
    day            Date,
    metric         LowCardinality(String),
    segment_dims   Map(String, String),
    baseline_value Float64,
    actual_value   Float64,
    pct_deviation  Float64,
    z_score        Float64,
    status         Enum8('open' = 1, 'investigated' = 2, 'dismissed' = 3) DEFAULT 'open',
    baseline_n     UInt8 DEFAULT 0,
    evaluated_hours String DEFAULT ''
)
ENGINE = MergeTree
ORDER BY (day, metric);

CREATE TABLE IF NOT EXISTS inmobi_rca.investigations
(
    id                     UUID DEFAULT generateUUIDv4(),
    created_at             DateTime DEFAULT now(),
    anomaly_candidate_id   Nullable(UUID),
    metric                 LowCardinality(String),
    day                    Date,
    diagnosis_text         String,
    responsible_segment    Map(String, String),
    checked_and_ruled_out  Array(String),
    cited_numbers          String,
    confidence             Float32,
    langfuse_trace_id      String
)
ENGINE = MergeTree
ORDER BY (day, metric, created_at);

CREATE TABLE IF NOT EXISTS inmobi_rca.chat_queries
(
    id                UUID DEFAULT generateUUIDv4(),
    created_at        DateTime DEFAULT now(),
    question          String,
    answer_text       String,
    cited_numbers     String,
    langfuse_trace_id String
)
ENGINE = MergeTree
ORDER BY created_at;

-- Per-call latency log backing p50/p95/p99 (see backend/app/timing.py).
CREATE TABLE IF NOT EXISTS inmobi_rca.request_latencies
(
    created_at   DateTime DEFAULT now(),
    endpoint     LowCardinality(String),
    total_ms     Float64,
    clickhouse_ms Float64,
    llm_ms       Float64
)
ENGINE = MergeTree
ORDER BY (endpoint, created_at);

GRANT SELECT ON inmobi_rca.* TO ro;
