-- =====================================================================
-- 03 · SILVER — denormalised, cleaned event stream
-- =====================================================================
-- Purpose: THE surface. Every metric, every baseline, every drill-down and
-- every alert is computed from this table — there is no rollup and no metric
-- view, because metric_def.sql runs directly against these columns.
--   * Dimensions resolved at ingest via LEFT JOIN to the dim tables.
--     (dictGet was the original path, but it snapshots dictionary state at
--     reload time — if ad_events ingests before SYSTEM RELOAD DICTIONARY,
--     every lookup misses and the row is frozen as 'unknown'. JOIN reads
--     the dim table directly and matches replay.sh's load order.)
--   * coalesce(..., 'unknown') for keys genuinely absent from dim CSVs.
--
-- ORDER BY: time first — every query is time-bounded, and both the hourly
-- bucketing and the baseline lookback scan by event_time — then the dimensions
-- most often filtered on during a drill-down.
--
-- After changing this MV: DROP VIEW + TRUNCATE ad_events_enriched, then
-- re-insert ad_events (or full replay.sh) to backfill silver.

DROP VIEW IF EXISTS inmobi.mv_ad_events_enriched;

CREATE TABLE IF NOT EXISTS inmobi.ad_events_enriched
(
    event_time      DateTime64(3),
    app_id          LowCardinality(String),
    geo_device_id   LowCardinality(String),
    advertiser_id   LowCardinality(String),
    ad_format       LowCardinality(String),
    is_filled       UInt8,
    is_impression   UInt8,
    is_click        UInt8,
    revenue         Float64,
    category        LowCardinality(String),
    publisher_tier  LowCardinality(String),
    region          LowCardinality(String),
    country         LowCardinality(String),
    device_model    LowCardinality(String),
    os_version      LowCardinality(String),
    vertical        LowCardinality(String),
    campaign_type   LowCardinality(String),
    -- ALIAS => computed on read, costs zero storage. Keeps the HyperDX
    -- Search UI usable without paying ~100MB for a redundant string.
    message         String ALIAS concat(
                        ad_format, ' ', country, ' ', os_version,
                        ' filled=', toString(is_filled),
                        ' imp=', toString(is_impression),
                        ' clk=', toString(is_click),
                        ' rev=', toString(revenue))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, region, country, os_version, category, ad_format)
SETTINGS index_granularity = 8192;

-- ---------------------------------------------------------------------
-- MV1: bronze -> silver. Fires on every insert into ad_events, so a
-- replay of the sealed file populates this with no extra step.
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_ad_events_enriched
TO inmobi.ad_events_enriched AS
SELECT
    e.event_time                         AS event_time,
    e.app_id                             AS app_id,
    e.geo_device_id                      AS geo_device_id,
    e.advertiser_id                      AS advertiser_id,
    e.ad_format                          AS ad_format,
    e.is_filled                          AS is_filled,
    e.is_impression                      AS is_impression,
    e.is_click                           AS is_click,
    e.revenue                            AS revenue,
    coalesce(a.category, 'unknown')        AS category,
    coalesce(a.publisher_tier, 'unknown')  AS publisher_tier,
    coalesce(g.region, 'unknown')          AS region,
    coalesce(g.country, 'unknown')           AS country,
    coalesce(g.device_model, 'unknown')    AS device_model,
    coalesce(g.os_version, 'unknown')      AS os_version,
    -- '' (not 'unknown') when unfilled: absence of an advertiser is
    -- meaningful here, and must not be confused with a lookup miss.
    if(e.advertiser_id = '', '',
       coalesce(ad.vertical, 'unknown'))   AS vertical,
    if(e.advertiser_id = '', '',
       coalesce(ad.campaign_type, 'unknown')) AS campaign_type
FROM inmobi.ad_events AS e
LEFT JOIN inmobi.apps AS a
    ON e.app_id = a.app_id
LEFT JOIN inmobi.geo_device AS g
    ON e.geo_device_id = g.geo_device_id
LEFT JOIN inmobi.advertisers AS ad
    ON e.advertiser_id = ad.advertiser_id
    AND e.advertiser_id != '';
