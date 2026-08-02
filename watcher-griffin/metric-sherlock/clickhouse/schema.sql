-- ClickHouse star schema for the Click-a-thon 2026 ad-events dataset.
-- 1 fact table (ad_events) + 3 dimension tables (apps, advertisers, geo_device).
-- See ../CLAUDE.md and Docs/metrics_glossary.md for the data model and metric formulas.
--
-- Load order matters: run this file, then dictionaries.sql, then rollups.sql,
-- THEN load.sql. Materialized views only fire on rows inserted after they're
-- created, so creating the rollups before the bulk load lets them backfill
-- automatically as part of that same INSERT.


-- === Fact table ===
CREATE TABLE ad_events
(
    event_time     DateTime CODEC(Delta, ZSTD),
    app_id         LowCardinality(String),
    geo_device_id  LowCardinality(String),
    advertiser_id  LowCardinality(String),   -- '' (not NULL) on unfilled requests
    ad_format      LowCardinality(String),
    is_filled      UInt8,
    is_impression  UInt8,
    is_click       UInt8,
    revenue        Decimal64(6) CODEC(ZSTD)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, app_id, geo_device_id, advertiser_id)
SETTINGS index_granularity = 8192;
-- TTL event_time + INTERVAL 2 YEAR  -- uncomment for production retention; not needed for the hackathon dataset

-- Skip indexes: the sort key can only favor a couple of dimensions at once
-- (and only helps a query that also filters on the earlier key columns), so
-- every event-level dimension gets a cheap bloom filter as a fallback for the
-- common case of filtering on just that one dimension.
ALTER TABLE ad_events ADD INDEX idx_app    app_id        TYPE bloom_filter GRANULARITY 4;
ALTER TABLE ad_events ADD INDEX idx_geo    geo_device_id TYPE bloom_filter GRANULARITY 4;
ALTER TABLE ad_events ADD INDEX idx_adv    advertiser_id TYPE bloom_filter GRANULARITY 4;
ALTER TABLE ad_events ADD INDEX idx_format ad_format     TYPE bloom_filter GRANULARITY 4;

-- Projections: physically re-sorted copies for the two dimensions that don't
-- lead the main sort key, so a deep-dive on one already-identified advertiser
-- or geo/device (after the rollup tables in rollups.sql have localized it)
-- can range-scan directly instead of relying on bloom-filter pruning alone.
ALTER TABLE ad_events ADD PROJECTION proj_by_advertiser
(
    SELECT * ORDER BY (advertiser_id, event_time)
);
ALTER TABLE ad_events ADD PROJECTION proj_by_geo
(
    SELECT * ORDER BY (geo_device_id, event_time)
);

-- === Dimension tables ===
-- ReplacingMergeTree so re-loading (e.g. the unseen-incident dataset shipping
-- updated/additional dimension rows) is idempotent instead of duplicating rows.
-- Tables are small (500-5,000 rows) so FINAL/merge overhead is negligible.

CREATE TABLE apps
(
    app_id          LowCardinality(String),
    category        LowCardinality(String),
    publisher_tier  LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY app_id;

CREATE TABLE advertisers
(
    advertiser_id   LowCardinality(String),
    vertical        LowCardinality(String),
    campaign_type   LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY advertiser_id;

CREATE TABLE geo_device
(
    geo_device_id   LowCardinality(String),
    region          LowCardinality(String),
    country         LowCardinality(String),
    device_model    LowCardinality(String),
    os_version      LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY geo_device_id;
