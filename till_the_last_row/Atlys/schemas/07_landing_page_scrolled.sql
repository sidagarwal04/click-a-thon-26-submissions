-- ============================================================================
-- Atlys ClickHouse schema — 07_landing_page_scrolled
-- Spec        : 07_landing_page_scrolled  (event: landing_page_scrolled)
-- Database    : atlys
-- Target      : ClickHouse Cloud (plain MergeTree / AggregatingMergeTree only)
-- Design      : ONE base table per spec, single JSON column `payload`.
--               Typed hints only for ORDER BY / PARTITION BY paths + skip-indexed
--               / boolean hot-filter paths. Numeric metric paths stay untyped in
--               `payload` and are skip-indexed via CAST(...) (see D1).
--
-- ORDER BY    : (payload.event, payload.destination, payload.page_version,
--                payload.user_id, payload.timestamp)  -- 5 cols
--               application_id EXCLUDED (empty on the majority of rows).
--               os EXCLUDED from key (Nullable in data) -> set skip-index only.
--
-- Deviations
--   D1  Skip-indexes cannot be attached to a dynamic JSON path directly
--       (ClickHouse Code:36/47). Every skip-indexed string/bool path is therefore
--       typed inside payload(...); numeric metric paths (scroll_depth_pct,
--       time_on_page_s) stay UNtyped and are minmax-indexed via CAST(payload.x,'T').
--   D2  The agg table's TTL is keyed on `agg_insert_time DEFAULT now64(3)`, NOT on
--       the event `day`. Keying TTL on historical event dates silently deletes
--       rollups on merge (server clock ~2026-08-01, events span back to 2026-02).
--
-- Metrics: see 07_landing_page_scrolled.metrics.json
-- ============================================================================

CREATE DATABASE IF NOT EXISTS atlys;

-- ---------------------------------------------------------------------------
-- Base table: one JSON `payload` column absorbs all envelope + spec fields.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS atlys.landing_page_scrolled
(
    payload JSON(
        event LowCardinality(String),
        destination LowCardinality(String),
        page_version LowCardinality(String),
        user_id String,
        timestamp DateTime64(3, 'UTC'),
        device_type LowCardinality(String),
        os Nullable(String),
        geoip_country_code LowCardinality(String),
        gclid String,
        fbclid String,
        is_guest UInt8,
        is_referral UInt8,
        is_enterprise UInt8,
        is_back_filled UInt8
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1)),
    INDEX idx_device_type payload.device_type TYPE set(0) GRANULARITY 1,
    INDEX idx_os payload.os TYPE set(0) GRANULARITY 1,
    INDEX idx_geo payload.geoip_country_code TYPE set(0) GRANULARITY 1,
    INDEX idx_gclid payload.gclid TYPE bloom_filter GRANULARITY 1,
    INDEX idx_fbclid payload.fbclid TYPE bloom_filter GRANULARITY 1,
    INDEX idx_scroll CAST(payload.scroll_depth_pct, 'UInt8') TYPE minmax GRANULARITY 1,
    INDEX idx_time CAST(payload.time_on_page_s, 'UInt16') TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.destination, payload.page_version, payload.user_id, payload.timestamp)
TTL toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1, index_granularity = 8192;

-- ---------------------------------------------------------------------------
-- Aggregating target: median (quantileState 0.5) + avg + count of
-- scroll_depth_pct / time_on_page_s by page_version x destination x
-- device_type x is_paid x day.  Serves PM Q1, Q3 (engagement half), Q4, Q5.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS atlys.landing_scroll_engagement_agg
(
    page_version LowCardinality(String),
    destination LowCardinality(String),
    device_type LowCardinality(String),
    is_paid UInt8,
    day Date,
    scroll_median AggregateFunction(quantile(0.5), UInt8),
    scroll_avg AggregateFunction(avg, UInt8),
    time_median AggregateFunction(quantile(0.5), UInt16),
    time_avg AggregateFunction(avg, UInt16),
    events AggregateFunction(count),
    agg_insert_time DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (page_version, destination, device_type, is_paid, day)
TTL toDateTime(agg_insert_time) + INTERVAL 90 DAY DELETE
SETTINGS ttl_only_drop_parts = 1;

-- ---------------------------------------------------------------------------
-- Incremental MV feeding the agg table. is_paid derived from gclid/fbclid.
-- ---------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.landing_scroll_engagement_agg_mv
TO atlys.landing_scroll_engagement_agg
AS
SELECT
    payload.page_version AS page_version,
    payload.destination AS destination,
    payload.device_type AS device_type,
    toUInt8(payload.gclid != '' OR payload.fbclid != '') AS is_paid,
    toDate(payload.timestamp) AS day,
    quantileState(0.5)(CAST(payload.scroll_depth_pct, 'UInt8')) AS scroll_median,
    avgState(CAST(payload.scroll_depth_pct, 'UInt8')) AS scroll_avg,
    quantileState(0.5)(CAST(payload.time_on_page_s, 'UInt16')) AS time_median,
    avgState(CAST(payload.time_on_page_s, 'UInt16')) AS time_avg,
    countState() AS events
FROM atlys.landing_page_scrolled
WHERE payload.event = 'landing_page_scrolled'
GROUP BY page_version, destination, device_type, is_paid, day;
