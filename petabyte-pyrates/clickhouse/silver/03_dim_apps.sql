CREATE VIEW silver.dim_apps
(
    `app_id` String,
    `category` LowCardinality(String),
    `publisher_tier` LowCardinality(String)
)
AS SELECT
    app_id,
    CAST(category, 'LowCardinality(String)') AS category,
    CAST(publisher_tier, 'LowCardinality(String)') AS publisher_tier
FROM default.clickathon_apps
