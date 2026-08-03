export const CREATE_AD_EVENTS_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS ad_events
(
    event_time    DateTime,
    app_id        LowCardinality(String),
    geo_device_id LowCardinality(String),
    advertiser_id Nullable(String),
    ad_format     LowCardinality(String),
    is_filled     UInt8,
    is_impression UInt8,
    is_click      UInt8,
    revenue       Float64
)
ENGINE = MergeTree
PARTITION BY toStartOfWeek(event_time)
ORDER BY (event_time, ad_format, app_id);
`;

export const CREATE_APPS_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS apps
(
    app_id         String,
    category       LowCardinality(String),
    publisher_tier LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY app_id;
`;

export const CREATE_APPS_DICT_SQL = `
CREATE DICTIONARY IF NOT EXISTS apps_dict
(
    app_id         String,
    category       String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 0 MAX 3600);
`;

export const CREATE_ADVERTISERS_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS advertisers
(
    advertiser_id String,
    vertical      LowCardinality(String),
    campaign_type LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY advertiser_id;
`;

export const CREATE_ADVERTISERS_DICT_SQL = `
CREATE DICTIONARY IF NOT EXISTS advertisers_dict
(
    advertiser_id String,
    vertical      String,
    campaign_type String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 0 MAX 3600);
`;

export const CREATE_GEO_DEVICE_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS geo_device
(
    geo_device_id String,
    region        LowCardinality(String),
    country       LowCardinality(String),
    device_model  LowCardinality(String),
    os_version    LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY geo_device_id;
`;

export const CREATE_GEO_DEVICE_DICT_SQL = `
CREATE DICTIONARY IF NOT EXISTS geo_device_dict
(
    geo_device_id String,
    region        String,
    country       String,
    device_model  String,
    os_version    String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(TABLE 'geo_device'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 0 MAX 3600);
`;

export const VERIFY_TABLE_COUNTS_SQL = `
SELECT 'ad_events' AS table_name, count() AS row_count FROM ad_events
UNION ALL
SELECT 'apps' AS table_name, count() AS row_count FROM apps
UNION ALL
SELECT 'advertisers' AS table_name, count() AS row_count FROM advertisers
UNION ALL
SELECT 'geo_device' AS table_name, count() AS row_count FROM geo_device;
`;

export const CREATE_AD_EVENTS_HOURLY_ROLLUP_TABLE_SQL = `
CREATE TABLE IF NOT EXISTS ad_events_hourly_rollup
(
    event_hour DateTime,
    dim_name LowCardinality(String),
    dim_val LowCardinality(String),
    requests AggregateFunction(count),
    fills AggregateFunction(sum, UInt8),
    impressions AggregateFunction(sum, UInt8),
    clicks AggregateFunction(sum, UInt8),
    revenue AggregateFunction(sum, Float64)
)
ENGINE = AggregatingMergeTree
ORDER BY (event_hour, dim_name, dim_val);
`;

export const VERIFY_DICTIONARY_LOOKUP_SQL = `
SELECT 
  dictGet('apps_dict', 'category', app_id) AS app_category,
  dictGet('geo_device_dict', 'region', geo_device_id) AS region,
  dictGet('advertisers_dict', 'vertical', advertiser_id) AS adv_vertical,
  count() AS requests,
  sum(is_filled) AS fills,
  sum(is_impression) AS impressions,
  sum(revenue) AS total_revenue
FROM ad_events
GROUP BY app_category, region, adv_vertical
LIMIT 5;
`;

