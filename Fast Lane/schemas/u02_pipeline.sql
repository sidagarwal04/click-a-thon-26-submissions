CREATE DICTIONARY IF NOT EXISTS `inmobi-hari`.dict_geo (
    geo_device_id String, region String, country String, device_model String, os_version String
) PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(TABLE 'geo_device' DB 'inmobi-hari'))
LAYOUT(COMPLEX_KEY_HASHED()) LIFETIME(MIN 300 MAX 600);

CREATE DICTIONARY IF NOT EXISTS `inmobi-hari`.dict_adv (
    advertiser_id String, vertical String, campaign_type String
) PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers' DB 'inmobi-hari'))
LAYOUT(COMPLEX_KEY_HASHED()) LIFETIME(MIN 300 MAX 600);

CREATE TABLE IF NOT EXISTS `inmobi-hari`.rollup_totals_1m (
    minute DateTime, requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Float64
) ENGINE = SummingMergeTree PARTITION BY toYYYYMM(minute) ORDER BY minute;

CREATE MATERIALIZED VIEW IF NOT EXISTS `inmobi-hari`.mv_totals_1m TO `inmobi-hari`.rollup_totals_1m AS
SELECT toStartOfMinute(event_time) AS minute,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM `inmobi-hari`.ad_events GROUP BY minute;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.rollup_marginal_1h (
    dimension LowCardinality(String), value LowCardinality(String), hour DateTime,
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Float64
) ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (dimension, value, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS `inmobi-hari`.mv_marginal_1h TO `inmobi-hari`.rollup_marginal_1h AS
SELECT dv.1 AS dimension, dv.2 AS value, toStartOfHour(event_time) AS hour,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM `inmobi-hari`.ad_events
ARRAY JOIN [
    ('ad_format',      toString(ad_format)),
    ('category',       dictGetOrDefault('inmobi-hari.dict_apps','category',       tuple(app_id), 'unknown')),
    ('publisher_tier', dictGetOrDefault('inmobi-hari.dict_apps','publisher_tier', tuple(app_id), 'unknown')),
    ('region',         dictGetOrDefault('inmobi-hari.dict_geo','region',       tuple(geo_device_id), 'unknown')),
    ('country',        dictGetOrDefault('inmobi-hari.dict_geo','country',      tuple(geo_device_id), 'unknown')),
    ('device_model',   dictGetOrDefault('inmobi-hari.dict_geo','device_model', tuple(geo_device_id), 'unknown')),
    ('os_version',     dictGetOrDefault('inmobi-hari.dict_geo','os_version',   tuple(geo_device_id), 'unknown')),
    ('vertical',       if(advertiser_id = '', 'UNFILLED', dictGetOrDefault('inmobi-hari.dict_adv','vertical',      tuple(advertiser_id), 'unknown'))),
    ('campaign_type',  if(advertiser_id = '', 'UNFILLED', dictGetOrDefault('inmobi-hari.dict_adv','campaign_type', tuple(advertiser_id), 'unknown')))
] AS dv
GROUP BY dimension, value, hour;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.rollup_os_country_1h (
    os_version LowCardinality(String), country LowCardinality(String), hour DateTime,
    requests UInt64, fills UInt64, impressions UInt64, revenue Float64
) ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (os_version, country, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS `inmobi-hari`.mv_os_country_1h TO `inmobi-hari`.rollup_os_country_1h AS
SELECT dictGetOrDefault('inmobi-hari.dict_geo','os_version', tuple(geo_device_id), 'unknown') AS os_version,
       dictGetOrDefault('inmobi-hari.dict_geo','country',    tuple(geo_device_id), 'unknown') AS country,
       toStartOfHour(event_time) AS hour,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, sum(revenue) AS revenue
FROM `inmobi-hari`.ad_events GROUP BY os_version, country, hour;
