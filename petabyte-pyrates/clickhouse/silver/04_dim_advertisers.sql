CREATE VIEW silver.dim_advertisers
(
    `advertiser_id` String,
    `vertical` LowCardinality(String),
    `campaign_type` LowCardinality(String)
)
AS SELECT
    advertiser_id,
    CAST(vertical, 'LowCardinality(String)') AS vertical,
    CAST(campaign_type, 'LowCardinality(String)') AS campaign_type
FROM default.clickathon_advertisers
