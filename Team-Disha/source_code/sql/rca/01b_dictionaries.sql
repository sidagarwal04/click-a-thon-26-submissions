-- ClickHouse dictionaries for star-schema enrichment (Cloud DDL).
-- Prefer dictGet over repeated LEFT JOINs in segment/combo materialize.

DROP DICTIONARY IF EXISTS dict_apps;
CREATE DICTIONARY dict_apps
(
    app_id String,
    category String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(DB 'eda' TABLE 'apps'))
LAYOUT(HASHED())
LIFETIME(MIN 0 MAX 3600);

DROP DICTIONARY IF EXISTS dict_geo_device;
CREATE DICTIONARY dict_geo_device
(
    geo_device_id String,
    region String,
    country String,
    os_version String,
    device_model String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(DB 'eda' TABLE 'geo_device'))
LAYOUT(HASHED())
LIFETIME(MIN 0 MAX 3600);

DROP DICTIONARY IF EXISTS dict_advertisers;
CREATE DICTIONARY dict_advertisers
(
    advertiser_id String,
    vertical String,
    campaign_type String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(DB 'eda' TABLE 'advertisers'))
LAYOUT(HASHED())
LIFETIME(MIN 0 MAX 3600);
