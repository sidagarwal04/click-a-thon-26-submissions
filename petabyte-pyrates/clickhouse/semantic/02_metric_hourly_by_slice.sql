CREATE VIEW gold.metric_hourly_by_slice
(
    `hour` DateTime('UTC') COMMENT 'Hour bucket in UTC, truncated to :00:00. One row per (hour, slice_type, slice_value). Filter WHERE hour >= ... AND hour < ...',
    `slice_type` String COMMENT 'Categorises what slice_value represents. Enum: global | region | ad_format | vertical | region_x_ad_format | region_x_vertical. Filter this first (LowCardinality index).',
    `slice_value` String COMMENT 'Slice identifier. Convention depends on slice_type: \'__ALL__\' for global; single dim value (e.g. \'EU\', \'video\', \'gaming\') for level-1 slices; \'dim1|dim2\' (e.g. \'EU|video\', \'EU|gaming\') for two-dim slices. splitByChar(\'|\', slice_value) to recover components.',
    `requests` UInt64 COMMENT 'Count of ad requests in this (hour, slice). Additive -- sum for aggregation. Denominator of fill_rate=sum(fills)/sum(requests).',
    `fills` UInt64 COMMENT 'Count of filled ad requests in this (hour, slice). Additive. Numerator of fill_rate; denominator of render_rate=sum(impressions)/sum(fills).',
    `impressions` UInt64 COMMENT 'Count of rendered impressions in this (hour, slice). Additive. Denominator of ecpm=sum(revenue)/sum(impressions)*1000 and ctr=sum(clicks)/sum(impressions).',
    `clicks` UInt64 COMMENT 'Count of clicks in this (hour, slice). Additive. Numerator of ctr.',
    `revenue` Float64 COMMENT 'Revenue in USD in this (hour, slice). Additive. Numerator of ecpm and rpr=sum(revenue)/sum(requests).'
)
COMMENT 'Roll-up view of gold.metrics_hourly at six canonical slice grains, the input for the anomaly-detection stack. One row per (hour, slice_type, slice_value) carrying the 5 additive measures. SLICE GRAINS: global (slice_value=\'__ALL__\'), region (5 values: EU|NAM|APAC|LATAM|MEA), ad_format (5 values: banner|native|interstitial|video|rewarded), vertical (7 values: gaming|entertainment|finance|ecommerce|auto|travel|cpg; unfilled excluded), region_x_ad_format (up to 25 values, \'region|format\'), region_x_vertical (up to 35 values, \'region|vertical\'). USE: filter WHERE slice_type=\'...\' AND slice_value=\'...\' for cheap scans. DERIVED METRICS at read time: fill_rate=sum(fills)/sum(requests); ecpm=sum(revenue)/sum(impressions)*1000; ctr=sum(clicks)/sum(impressions). All hours are UTC and truncated to :00:00.'
AS SELECT
    hour,
    'global' AS slice_type,
    '__ALL__' AS slice_value,
    sum(requests) AS requests,
    sum(fills) AS fills,
    sum(impressions) AS impressions,
    sum(clicks) AS clicks,
    sum(revenue) AS revenue
FROM gold.metrics_hourly
GROUP BY hour
UNION ALL
SELECT
    hour,
    'region' AS slice_type,
    region AS slice_value,
    sum(requests),
    sum(fills),
    sum(impressions),
    sum(clicks),
    sum(revenue)
FROM gold.metrics_hourly
WHERE region != ''
GROUP BY
    hour,
    region
UNION ALL
SELECT
    hour,
    'ad_format' AS slice_type,
    ad_format AS slice_value,
    sum(requests),
    sum(fills),
    sum(impressions),
    sum(clicks),
    sum(revenue)
FROM gold.metrics_hourly
WHERE ad_format != ''
GROUP BY
    hour,
    ad_format
UNION ALL
SELECT
    hour,
    'vertical' AS slice_type,
    vertical AS slice_value,
    sum(requests),
    sum(fills),
    sum(impressions),
    sum(clicks),
    sum(revenue)
FROM gold.metrics_hourly
WHERE vertical != ''
GROUP BY
    hour,
    vertical
UNION ALL
SELECT
    hour,
    'region_x_ad_format' AS slice_type,
    concat(region, '|', ad_format) AS slice_value,
    sum(requests),
    sum(fills),
    sum(impressions),
    sum(clicks),
    sum(revenue)
FROM gold.metrics_hourly
WHERE (region != '') AND (ad_format != '')
GROUP BY
    hour,
    region,
    ad_format
UNION ALL
SELECT
    hour,
    'region_x_vertical' AS slice_type,
    concat(region, '|', vertical) AS slice_value,
    sum(requests),
    sum(fills),
    sum(impressions),
    sum(clicks),
    sum(revenue)
FROM gold.metrics_hourly
WHERE (region != '') AND (vertical != '')
GROUP BY
    hour,
    region,
    vertical
