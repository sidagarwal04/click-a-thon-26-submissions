-- ============================================================================
-- Two dimension epochs — because the unseen dataset reused the same IDs
-- ============================================================================
-- The unseen slice ships regenerated dimension tables: the SAME geo_device_id
-- carries different attributes. `gd_00000` is NAM / Galaxy A54 / Android 12 in
-- the main dataset and APAC / iPhone 14 / iOS 17.5 in the unseen one.
--
-- The rollups already handle this — each period was built against its own
-- dimension tables, which is what made the boundary continuous. But the
-- COMPOUND scan does not read the rollups. An unpivoted rollup cannot represent
-- combinations, so pair analysis queries ad_events directly and resolves
-- dimensions with dictGet at query time — against whatever the dictionary holds
-- *now*, which is the July mapping.
--
-- The consequence, measured: the main dataset's compound findings were being
-- computed with July's attribute assignment. "iOS 18.1" in June resolved to a
-- different set of devices than it did when the data was generated, so the
-- 06-28 iOS 18.1 x APAC finding stopped reproducing.
--
-- These dictionaries hold the ORIGINAL mapping. engine/intersect.py picks
-- between them on event_time, so a pair scan spanning the boundary resolves
-- each event against the attributes that were true when it happened.
-- ============================================================================

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_geo_device_old
(
    geo_device_id String,
    region        String,
    country       String,
    device_model  String,
    os_version    String
)
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(TABLE 'geo_device_old' DB 'inmobi'))
LIFETIME(MIN 0 MAX 0)
LAYOUT(COMPLEX_KEY_HASHED());


CREATE DICTIONARY IF NOT EXISTS inmobi.dict_apps_old
(
    app_id         String,
    category       String,
    publisher_tier String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps_old' DB 'inmobi'))
LIFETIME(MIN 0 MAX 0)
LAYOUT(COMPLEX_KEY_HASHED());


CREATE DICTIONARY IF NOT EXISTS inmobi.dict_advertisers_old
(
    advertiser_id String,
    vertical      String,
    campaign_type String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers_old' DB 'inmobi'))
LIFETIME(MIN 0 MAX 0)
LAYOUT(COMPLEX_KEY_HASHED());


-- ---------------------------------------------------------------------------
-- ...and the CURRENT epoch, as its own dictionary rather than reusing
-- inmobi.dict_geo_device.
--
-- Why: on ClickHouse Cloud, SYSTEM RELOAD DICTIONARY reloads only the node it
-- is issued against. After the unseen load, dict_geo_device returned the new
-- mapping on the connection that reloaded it and the old mapping on others —
-- so a pair scan's answer depended on which replica served it. A dictionary
-- created fresh loads correctly everywhere, so the epoch dictionaries are
-- created once and never reloaded, and nothing reads the mutable one.
-- ---------------------------------------------------------------------------

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_geo_device_cur
(   geo_device_id String, region String, country String,
    device_model String, os_version String )
PRIMARY KEY geo_device_id
SOURCE(CLICKHOUSE(TABLE 'geo_device' DB 'inmobi'))
LIFETIME(MIN 0 MAX 0) LAYOUT(COMPLEX_KEY_HASHED());

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_apps_cur
(   app_id String, category String, publisher_tier String )
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps' DB 'inmobi'))
LIFETIME(MIN 0 MAX 0) LAYOUT(COMPLEX_KEY_HASHED());

CREATE DICTIONARY IF NOT EXISTS inmobi.dict_advertisers_cur
(   advertiser_id String, vertical String, campaign_type String )
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(TABLE 'advertisers' DB 'inmobi'))
LIFETIME(MIN 0 MAX 0) LAYOUT(COMPLEX_KEY_HASHED());
