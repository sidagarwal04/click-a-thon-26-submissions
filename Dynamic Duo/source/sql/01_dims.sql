-- Dimension tables + dictionaries.
-- Dictionaries are the enrichment seam: in production the SOURCE clause points at the
-- OLTP system of record (Postgres / CDC feed) — nothing downstream changes. See
-- ARCHITECTURE.md. On ClickHouse Cloud, if dictionary load hits an auth error, add
-- USER/PASSWORD to the SOURCE clause (loopback credentials are instance-configured).

CREATE TABLE IF NOT EXISTS rca.dim_apps
(
    app_id         String,
    category       LowCardinality(String),
    publisher_tier LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY app_id;

CREATE TABLE IF NOT EXISTS rca.dim_advertisers
(
    advertiser_id String,
    vertical      LowCardinality(String),
    campaign_type LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS rca.dim_geo_device
(
    geo_device_id String,
    region        LowCardinality(String),
    country       LowCardinality(String),
    device_model  LowCardinality(String),
    os_version    LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY geo_device_id;

CREATE DICTIONARY IF NOT EXISTS rca.dict_apps
(
    app_id         String,
    category       String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(DB 'rca' TABLE 'dim_apps'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);

CREATE DICTIONARY IF NOT EXISTS rca.dict_advertisers
(
    advertiser_id String,
    vertical      String,
    campaign_type String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(DB 'rca' TABLE 'dim_advertisers'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);

CREATE DICTIONARY IF NOT EXISTS rca.dict_geo_device
(
    geo_device_id String,
    region        String,
    country       String,
    device_model  String,
    os_version    String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(DB 'rca' TABLE 'dim_geo_device'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);
