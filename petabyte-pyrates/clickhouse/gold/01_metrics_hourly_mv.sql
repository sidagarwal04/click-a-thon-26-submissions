CREATE MATERIALIZED VIEW gold.metrics_hourly_mv TO gold.metrics_hourly
(
    `hour` DateTime('UTC'),
    `ad_format` LowCardinality(String),
    `app_category` LowCardinality(String),
    `publisher_tier` LowCardinality(String),
    `region` LowCardinality(String),
    `country` LowCardinality(String),
    `device_model` LowCardinality(String),
    `os_version` LowCardinality(String),
    `vertical` LowCardinality(String),
    `campaign_type` LowCardinality(String),
    `requests` UInt64,
    `fills` UInt64,
    `impressions` UInt64,
    `clicks` UInt64,
    `revenue` Float64,
    `app_ids` Array(String),
    `geo_device_ids` Array(String),
    `advertiser_ids` Array(String)
)
COMMENT 'Internal pipeline object — populates gold.metrics_hourly automatically. Not intended to be queried directly; read gold.metrics_hourly instead. Fires on each new block inserted into silver.ad_events_enriched (which itself is fed by silver.ad_events_enriched_mv from bronze). Buckets event_time to the hour, joins to attribute dims, and GROUP BYs at gold.metrics_hourly ORDER BY grain, writing pre-collapsed rows. SummingMergeTree background merges finish the collapse across blocks.'
AS SELECT
    toStartOfHour(e.event_time) AS hour,
    e.ad_format AS ad_format,
    coalesce(a.category, '') AS app_category,
    coalesce(a.publisher_tier, '') AS publisher_tier,
    coalesce(g.region, '') AS region,
    coalesce(g.country, '') AS country,
    coalesce(g.device_model, '') AS device_model,
    coalesce(g.os_version, '') AS os_version,
    coalesce(v.vertical, '') AS vertical,
    coalesce(v.campaign_type, '') AS campaign_type,
    sum(toUInt64(1)) AS requests,
    sum(toUInt64(e.is_filled)) AS fills,
    sum(toUInt64(e.is_impression)) AS impressions,
    sum(toUInt64(e.is_click)) AS clicks,
    sum(toFloat64(e.revenue)) AS revenue,
    groupUniqArray(e.app_id) AS app_ids,
    groupUniqArray(e.geo_device_id) AS geo_device_ids,
    groupUniqArrayIf(e.advertiser_id, e.advertiser_id != '') AS advertiser_ids
FROM silver.ad_events_enriched AS e
LEFT JOIN silver.dim_apps AS a ON a.app_id = e.app_id
LEFT JOIN silver.dim_geo_device AS g ON g.geo_device_id = e.geo_device_id
LEFT JOIN silver.dim_advertisers AS v ON v.advertiser_id = e.advertiser_id
GROUP BY
    hour,
    ad_format,
    app_category,
    publisher_tier,
    region,
    country,
    device_model,
    os_version,
    vertical,
    campaign_type
