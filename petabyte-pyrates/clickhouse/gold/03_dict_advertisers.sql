CREATE DICTIONARY gold.dict_advertisers
(
    `advertiser_id` String,
    `vertical` String,
    `campaign_type` String
)
PRIMARY KEY advertiser_id
SOURCE(CLICKHOUSE(USER 'default' PASSWORD '{CLICKHOUSE_PASSWORD}' QUERY 'SELECT advertiser_id, vertical, campaign_type FROM silver.dim_advertisers'))
LIFETIME(MIN 0 MAX 3600)
LAYOUT(COMPLEX_KEY_HASHED())
COMMENT 'Advertiser attribute dictionary. 500 rows in memory, refreshed hourly. LOOKUP: dictGet(\'gold.dict_advertisers\', \'vertical\', \'adv_0123\'). Also queryable as a table. USE: translate advertiser_ids from gold.metrics_hourly.advertiser_ids back to human-readable attributes. ATTRIBUTES: advertiser_id (PK, String, format "adv_NNNN"; empty-string sentinel "" for unfilled requests does NOT exist here — it is a gold-only convention); vertical (String, enum: gaming|entertainment|finance|ecommerce|auto|travel|cpg); campaign_type (String, enum: CPM|CPC|CPI — pricing/optimisation model).'
