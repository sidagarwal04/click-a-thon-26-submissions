-- In-memory dictionaries over the (tiny) dimension tables, so rollups.sql can
-- enrich ad_events with dimension attributes via dictGet(...) instead of a
-- hash JOIN on every aggregation. Run after schema.sql (needs the dimension
-- tables as source) and before rollups.sql (which reads these dictionaries).
--
-- LIFETIME triggers a periodic reload from the source table so dimension
-- updates (e.g. a re-loaded apps/advertisers/geo_device file) get picked up
-- without restarting ClickHouse; harmless for a static hackathon dataset.
--
-- LAYOUT is COMPLEX_KEY_HASHED, not HASHED: every key here is a String, and
-- HASHED() only accepts a single UInt64 key. This file previously said HASHED()
-- while all three live dictionaries were COMPLEX_KEY_HASHED -- ClickHouse had
-- resolved it, so nothing was broken, but the file no longer described the
-- database. Stating it explicitly keeps a DDL diff meaningful.

CREATE DICTIONARY apps_dict
(
    app_id         String,
    category       String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);

CREATE DICTIONARY advertisers_dict
(
    advertiser_id  String,
    vertical       String,
    campaign_type  String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);

CREATE DICTIONARY geo_device_dict
(
    geo_device_id  String,
    region         String,
    country        String,
    device_model   String,
    os_version     String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(TABLE 'geo_device'))
LAYOUT(COMPLEX_KEY_HASHED())
LIFETIME(MIN 300 MAX 600);

-- Usage:
--   dictGet('apps_dict', 'category', app_id)
--   dictGetOrDefault('advertisers_dict', 'vertical', advertiser_id, '')
--     ^ use *OrDefault* for advertiser-derived fields: advertiser_id is '' on
--       unfilled requests, which has no dictionary entry and would otherwise
--       raise an error.
