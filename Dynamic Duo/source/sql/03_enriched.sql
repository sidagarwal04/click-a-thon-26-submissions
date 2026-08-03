-- Enriched fact: the substrate for every investigator query (Q1-Q5 port target).
-- Dimensions are glued on ONCE at insert time via dictionaries, so every downstream
-- query is single-table and every logged sql_text is self-contained/reproducible.
--
-- Semantics of the 'unknown' bucket (LEFT-JOIN rule from agent_queries.md, enforced
-- at insert):
--   app/geo attributes:  key missing from dims -> 'unknown'
--   advertiser attributes: ''  = unfilled request (advertiser_id empty by design)
--                          'unknown' = filled but key missing from dims
-- A growing 'unknown' bucket on the unseen slice is itself a finding.
--
-- event_date is MATERIALIZED and leads the sort key: Q1-Q5 filter on event_date and
-- get granule pruning; drill-downs filter event_time and prune too (sorted within date).

CREATE TABLE IF NOT EXISTS rca.ad_events_enriched
(
    event_time     DateTime('UTC') CODEC(Delta, ZSTD),
    event_date     Date MATERIALIZED toDate(event_time),
    app_id         LowCardinality(String),
    advertiser_id  LowCardinality(String),
    geo_device_id  LowCardinality(String),
    ad_format      LowCardinality(String),
    category       LowCardinality(String),
    publisher_tier LowCardinality(String),
    vertical       LowCardinality(String),
    campaign_type  LowCardinality(String),
    region         LowCardinality(String),
    country        LowCardinality(String),
    device_model   LowCardinality(String),
    os_version     LowCardinality(String),
    is_filled      UInt8,
    is_impression  UInt8,
    is_click       UInt8,
    revenue        Float64,
    dataset        LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_time);

CREATE MATERIALIZED VIEW IF NOT EXISTS rca.mv_enrich TO rca.ad_events_enriched AS
SELECT
    event_time,
    app_id,
    advertiser_id,
    geo_device_id,
    ad_format,
    dictGetOrDefault('rca.dict_apps', 'category',       tuple(app_id), 'unknown')        AS category,
    dictGetOrDefault('rca.dict_apps', 'publisher_tier', tuple(app_id), 'unknown')        AS publisher_tier,
    if(advertiser_id = '', '',
       dictGetOrDefault('rca.dict_advertisers', 'vertical',      tuple(advertiser_id), 'unknown')) AS vertical,
    if(advertiser_id = '', '',
       dictGetOrDefault('rca.dict_advertisers', 'campaign_type', tuple(advertiser_id), 'unknown')) AS campaign_type,
    dictGetOrDefault('rca.dict_geo_device', 'region',       tuple(geo_device_id), 'unknown') AS region,
    dictGetOrDefault('rca.dict_geo_device', 'country',      tuple(geo_device_id), 'unknown') AS country,
    dictGetOrDefault('rca.dict_geo_device', 'device_model', tuple(geo_device_id), 'unknown') AS device_model,
    dictGetOrDefault('rca.dict_geo_device', 'os_version',   tuple(geo_device_id), 'unknown') AS os_version,
    is_filled,
    is_impression,
    is_click,
    revenue,
    dataset
FROM rca.ad_events;
