-- Replaces sql/segment/02_populate_hourly.sql's TRUNCATE-and-full-reload
-- (deleted) — same reasoning as mv_metrics_hourly (sql/mv/01): fires on
-- every INSERT into inmobi.ad_events, aggregating exactly the block just
-- inserted, joined against the (slowly-changing, non-triggering) dimension
-- tables inmobi.apps / inmobi.geo_device / inmobi.advertisers.
--
-- vertical/campaign_type only exist on FILLED events (advertiser_id is
-- empty until a request fills — see metrics_glossary.md), so `requests` for
-- just those two dimensions is really "filled events with this vertical/
-- campaign_type", not true top-of-funnel requests — same caveat as the old
-- batch version, unchanged. sql/mv/08 and sql/mv/10 know this and skip
-- fill_rate/rpr for those two dimensions.
--
-- Deliberately excludes app_id (2000 values) and advertiser_id (500 values)
-- — too many cells for a trailing-baseline approach to have real power, and
-- too expensive to sweep on every insert. Those stay Stage 2's targeted
-- per-anomaly drill-down, not a blanket sweep.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_segment_metrics_hourly
TO inmobi.segment_metrics_hourly
AS
WITH base AS (
  SELECT
    toStartOfHour(event_time) AS hour_ts,
    toDate(toStartOfHour(event_time)) AS d,
    toDayOfWeek(toDate(toStartOfHour(event_time))) AS dow,
    toHour(toStartOfHour(event_time)) AS hod,
    app_id, geo_device_id, advertiser_id, ad_format,
    is_filled, is_impression, is_click, revenue
  FROM inmobi.ad_events
)
SELECT hour_ts, d, dow, hod, 'ad_format' AS dimension, ad_format AS segment,
  count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, sum(is_click) AS clicks, sum(revenue) AS revenue
FROM base GROUP BY hour_ts, d, dow, hod, ad_format

UNION ALL
SELECT b.hour_ts, b.d, b.dow, b.hod, 'category', a.category,
  count(), sum(b.is_filled), sum(b.is_impression), sum(b.is_click), sum(b.revenue)
FROM base b INNER JOIN inmobi.apps a ON b.app_id = a.app_id
GROUP BY b.hour_ts, b.d, b.dow, b.hod, a.category

UNION ALL
SELECT b.hour_ts, b.d, b.dow, b.hod, 'publisher_tier', a.publisher_tier,
  count(), sum(b.is_filled), sum(b.is_impression), sum(b.is_click), sum(b.revenue)
FROM base b INNER JOIN inmobi.apps a ON b.app_id = a.app_id
GROUP BY b.hour_ts, b.d, b.dow, b.hod, a.publisher_tier

UNION ALL
SELECT b.hour_ts, b.d, b.dow, b.hod, 'region', g.region,
  count(), sum(b.is_filled), sum(b.is_impression), sum(b.is_click), sum(b.revenue)
FROM base b INNER JOIN inmobi.geo_device g ON b.geo_device_id = g.geo_device_id
GROUP BY b.hour_ts, b.d, b.dow, b.hod, g.region

UNION ALL
SELECT b.hour_ts, b.d, b.dow, b.hod, 'country', g.country,
  count(), sum(b.is_filled), sum(b.is_impression), sum(b.is_click), sum(b.revenue)
FROM base b INNER JOIN inmobi.geo_device g ON b.geo_device_id = g.geo_device_id
GROUP BY b.hour_ts, b.d, b.dow, b.hod, g.country

UNION ALL
SELECT b.hour_ts, b.d, b.dow, b.hod, 'vertical', ad.vertical,
  count(), count(), sum(b.is_impression), sum(b.is_click), sum(b.revenue)
FROM base b INNER JOIN inmobi.advertisers ad ON b.advertiser_id = ad.advertiser_id
WHERE b.is_filled = 1
GROUP BY b.hour_ts, b.d, b.dow, b.hod, ad.vertical

UNION ALL
SELECT b.hour_ts, b.d, b.dow, b.hod, 'campaign_type', ad.campaign_type,
  count(), count(), sum(b.is_impression), sum(b.is_click), sum(b.revenue)
FROM base b INNER JOIN inmobi.advertisers ad ON b.advertiser_id = ad.advertiser_id
WHERE b.is_filled = 1
GROUP BY b.hour_ts, b.d, b.dow, b.hod, ad.campaign_type;
