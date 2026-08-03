CREATE VIEW silver.dim_geo_device
(
    `geo_device_id` String,
    `region` LowCardinality(String),
    `country` LowCardinality(String),
    `device_model` LowCardinality(String),
    `os_version` LowCardinality(String)
)
AS SELECT
    geo_device_id,
    CAST(region, 'LowCardinality(String)') AS region,
    CAST(country, 'LowCardinality(String)') AS country,
    CAST(device_model, 'LowCardinality(String)') AS device_model,
    CAST(os_version, 'LowCardinality(String)') AS os_version
FROM default.clickathon_geo_device
