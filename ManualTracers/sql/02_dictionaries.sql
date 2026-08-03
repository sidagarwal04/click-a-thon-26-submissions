-- =====================================================================
-- 02 · DICTIONARIES — optional lookup cache (not used by the silver MV)
-- =====================================================================
-- The silver MV (03_silver.sql) JOINs dim tables directly at ingest.
-- These dictionaries remain for ad-hoc dictGet probes and tooling; reload
-- them after a dim CSV load via replay.sh (SYSTEM RELOAD DICTIONARY).
-- Keys are String, so COMPLEX_KEY_HASHED (HASHED requires UInt64 keys).
-- LIFETIME(0) = never auto-reload; we reload explicitly after a dim load.

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_apps
(
    app_id         String,
    category       String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps' DB 'inmobi'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(0);

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_advertisers
(
    advertiser_id String,
    vertical      String,
    campaign_type String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers' DB 'inmobi'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(0);

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_geo_device
(
    geo_device_id String,
    region        String,
    country       String,
    device_model  String,
    os_version    String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(TABLE 'geo_device' DB 'inmobi'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(0);
