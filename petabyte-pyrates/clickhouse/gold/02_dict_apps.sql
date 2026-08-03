CREATE DICTIONARY gold.dict_apps
(
    `app_id` String,
    `category` String,
    `publisher_tier` String
)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(USER 'default' PASSWORD '{CLICKHOUSE_PASSWORD}' QUERY 'SELECT app_id, category, publisher_tier FROM silver.dim_apps'))
LIFETIME(MIN 0 MAX 3600)
LAYOUT(COMPLEX_KEY_HASHED())
COMMENT 'App attribute dictionary. 2000 rows in memory, refreshed hourly. LOOKUP: dictGet(\'gold.dict_apps\', \'category\', \'app_00123\'). Also queryable as a table: SELECT * FROM gold.dict_apps WHERE app_id IN (...). USE: translate app_ids from gold.metrics_hourly.app_ids back to human-readable attributes. ATTRIBUTES: app_id (PK, String, format "app_NNNNN"); category (String, enum: gaming|ecommerce|entertainment|news|finance|social|utility, same domain as gold.metrics_hourly.app_category); publisher_tier (String, enum: tier_1 highest | tier_2 | tier_3, same domain as gold.metrics_hourly.publisher_tier).'
