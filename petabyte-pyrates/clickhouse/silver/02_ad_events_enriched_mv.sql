CREATE MATERIALIZED VIEW silver.ad_events_enriched_mv TO silver.ad_events_enriched
(
    `event_time` DateTime('UTC'),
    `ad_format` String,
    `app_id` String,
    `geo_device_id` String,
    `advertiser_id` String,
    `is_filled` UInt8,
    `is_impression` UInt8,
    `is_click` UInt8,
    `revenue` Float32
)
AS SELECT
    toDateTime(event_time, 'UTC') AS event_time,
    ad_format,
    app_id,
    geo_device_id,
    coalesce(advertiser_id, '') AS advertiser_id,
    toUInt8(is_filled) AS is_filled,
    toUInt8(is_impression) AS is_impression,
    toUInt8(is_click) AS is_click,
    toFloat32(revenue) AS revenue
FROM default.clickathon_ad_events
