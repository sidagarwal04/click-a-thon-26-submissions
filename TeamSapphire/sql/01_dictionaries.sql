-- Dimension tables are tiny (2000 / 500 / 5000 rows). Loading them as
-- dictionaries lets the rollup MV resolve dimensions with dictGet() at insert
-- time instead of running a JOIN inside the MV trigger, which is both faster
-- and far less fragile.
--
-- LIFETIME(MIN 0 MAX 0) = never auto-reload. The harness issues an explicit
-- SYSTEM RELOAD DICTIONARY after loading new data, so reload timing is
-- deterministic rather than incidental.

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_apps
(
    app_id         String,
    category       String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps' DB 'inmobi'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 0 MAX 0);

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_advertisers
(
    advertiser_id String,
    vertical      String,
    campaign_type String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers' DB 'inmobi'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 0 MAX 0);

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
LIFETIME(MIN 0 MAX 0);
