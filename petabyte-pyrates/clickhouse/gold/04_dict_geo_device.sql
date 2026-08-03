CREATE DICTIONARY gold.dict_geo_device
(
    `geo_device_id` String,
    `region` String,
    `country` String,
    `device_model` String,
    `os_version` String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(USER 'default' PASSWORD '{CLICKHOUSE_PASSWORD}' QUERY 'SELECT geo_device_id, region, country, device_model, os_version FROM silver.dim_geo_device'))
LIFETIME(MIN 0 MAX 3600)
LAYOUT(COMPLEX_KEY_HASHED())
COMMENT 'Geo/device attribute dictionary. 5000 rows in memory (one row per unique country×device×OS profile), refreshed hourly. LOOKUP: dictGet(\'gold.dict_geo_device\', \'region\', \'gd_00042\'). Also queryable as a table. USE: translate geo_device_ids from gold.metrics_hourly.geo_device_ids back to human-readable attributes. ATTRIBUTES: geo_device_id (PK, String, format "gd_NNNNN"); region (String, enum: EU|NAM|APAC|LATAM|MEA); country (String, ISO 3166-1 alpha-2, e.g. DE, US, IN, BR); device_model (String, e.g. "Pixel 7", "iPhone 15"); os_version (String, e.g. "Android 14", "iOS 17").'
