-- The cube: the SAME data, pre-aggregated by day × low-card dimensions. The "Fast" enabler —
-- everything downstream reads this; nothing re-scans 9M raw rows. Stores SUMS only; every ratio
-- (fill_rate, ctr, ecpm) is computed sum/sum at read time so roll-ups stay correct.
-- NOT a new dataset: it's an index over the given data. High-card ids (app/geo/advertiser) are
-- intentionally excluded — DATA.md shows no anomaly lives there; slicing them is false-positive risk.
DROP TABLE IF EXISTS rca.cube;
CREATE TABLE rca.cube
(
    day           Date,
    region        LowCardinality(String),
    country       LowCardinality(String),
    device_model  LowCardinality(String),
    os_version    LowCardinality(String),
    category      LowCardinality(String),
    publisher_tier LowCardinality(String),
    vertical      LowCardinality(String),   -- '' on unfilled (no advertiser)
    campaign_type LowCardinality(String),   -- ''  "
    ad_format     LowCardinality(String),
    requests      UInt64,
    fills         UInt64,
    impressions   UInt64,
    clicks        UInt64,
    revenue       Float64
)
ENGINE = MergeTree
ORDER BY (day, region, os_version, category, ad_format);

INSERT INTO rca.cube
SELECT
    toDate(e.event_time)                 AS day,
    g.region, g.country, g.device_model, g.os_version,
    a.category, a.publisher_tier,
    ifNull(ad.vertical, '')              AS vertical,
    ifNull(ad.campaign_type, '')         AS campaign_type,
    e.ad_format,
    count()            AS requests,
    sum(e.is_filled)   AS fills,
    sum(e.is_impression) AS impressions,
    sum(e.is_click)    AS clicks,
    sum(e.revenue)     AS revenue
FROM rca.ad_events e
LEFT JOIN rca.geo_device  g  ON e.geo_device_id = g.geo_device_id
LEFT JOIN rca.apps        a  ON e.app_id        = a.app_id
LEFT JOIN rca.advertisers ad ON e.advertiser_id = ad.advertiser_id
GROUP BY day, region, country, device_model, os_version,
         category, publisher_tier, vertical, campaign_type, ad_format;
