-- =====================================================================
--  BASELINES, scored over the FULL history (2026-06-01 -> 2026-07-10).
--
--  `inmobi-hari` is self-contained: it holds BOTH the main-batch dimension
--  snapshot (apps_v1 / geo_device_v1 / advertisers_v1, June's own labels)
--  and the current one (apps / geo_device / advertisers, the unseen
--  batch's regenerated labels) alongside a single unified `ad_events`
--  fact table spanning both batches.
--
--  The critical rule, discovered the hard way (see README.md "batch-aware
--  join"): an event must ALWAYS be interpreted through the dimension
--  snapshot that shipped with its own batch, never the other one.
--  Main-batch events (event_time < 2026-07-06) use the _v1 dictionaries;
--  unseen-batch events use the current ones. Getting this backwards for
--  even one direction reintroduces the relabeling artifact and manufactures
--  a spurious ~162% eCPM "incident" on almost every June day.
--
--  Two books, keyed on the driver each metric actually depends on:
--    fill_rate / render_rate  <-  publisher_tier x ad_format
--    eCPM                     <-  country x ad_format
--  Both are built once from the June weekday window (2026-06-08 to
--  2026-07-05) using dict_*_v1, and reused to score every day in history.
-- =====================================================================

-- ---------------- eCPM: June price book ----------------
CREATE OR REPLACE VIEW `inmobi-hari`.v_pricebook_jun AS
SELECT dictGetOrDefault('inmobi-hari.dict_geo_v1','country', tuple(geo_device_id), '?') AS country,
       ad_format,
       sum(revenue) / sum(is_impression) * 1000 AS ecpm
FROM `inmobi-hari`.ad_events
WHERE is_impression = 1
  AND toDate(event_time) BETWEEN '2026-06-08' AND '2026-07-05'
  AND toDayOfWeek(event_time) <= 5
GROUP BY country, ad_format;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.ecpm_expected_1d (
    day Date, dimension LowCardinality(String), value LowCardinality(String),
    impressions UInt64, revenue Float64, revenue_expected Float64
) ENGINE = SummingMergeTree ORDER BY (dimension, value, day);

TRUNCATE TABLE `inmobi-hari`.ecpm_expected_1d;

INSERT INTO `inmobi-hari`.ecpm_expected_1d
WITH priced AS (
    SELECT toDate(e.event_time) AS day, e.revenue AS revenue, e.ad_format AS ad_format,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','country', tuple(e.geo_device_id), '?'),
              dictGetOrDefault('inmobi-hari.dict_geo','country',    tuple(e.geo_device_id), '?')) AS ev_country,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_apps_v1','category',       tuple(e.app_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_apps','category',          tuple(e.app_id), 'unknown')) AS ev_category,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_apps_v1','publisher_tier', tuple(e.app_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_apps','publisher_tier',    tuple(e.app_id), 'unknown')) AS ev_tier,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','region',       tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','region',          tuple(e.geo_device_id), 'unknown')) AS ev_region,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','device_model', tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','device_model',    tuple(e.geo_device_id), 'unknown')) AS ev_device,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','os_version',   tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','os_version',      tuple(e.geo_device_id), 'unknown')) AS ev_os,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_adv_v1','vertical',      tuple(e.advertiser_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_adv','vertical',         tuple(e.advertiser_id), 'unknown')) AS ev_vertical,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_adv_v1','campaign_type', tuple(e.advertiser_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_adv','campaign_type',    tuple(e.advertiser_id), 'unknown')) AS ev_campaign,
           pb.ecpm / 1000 AS rev_exp
    FROM `inmobi-hari`.ad_events e
    INNER JOIN `inmobi-hari`.v_pricebook_jun pb
        ON pb.country = if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','country', tuple(e.geo_device_id), '?'),
              dictGetOrDefault('inmobi-hari.dict_geo','country',    tuple(e.geo_device_id), '?'))
       AND pb.ad_format = e.ad_format
    WHERE e.is_impression = 1
)
SELECT day, dv.1, dv.2, count(), sum(revenue), sum(rev_exp)
FROM priced
ARRAY JOIN [
    ('TOTAL',          'all'),
    ('ad_format',      toString(ad_format)),
    ('category',       ev_category),
    ('publisher_tier', ev_tier),
    ('region',         ev_region),
    ('country',        ev_country),
    ('device_model',   ev_device),
    ('os_version',     ev_os),
    ('vertical',       ev_vertical),
    ('campaign_type',  ev_campaign)
] AS dv
GROUP BY day, dv.1, dv.2;

-- ---------------- fill / render: June fill book ----------------
-- Median across June weekdays, so June's OWN planted incidents (Jun 19-30)
-- cannot drag the baseline down. A sum/sum baseline over the same window
-- fires on every clean day instead.
CREATE OR REPLACE VIEW `inmobi-hari`.v_fillbook_jun AS
WITH d AS (
    SELECT dictGetOrDefault('inmobi-hari.dict_apps_v1','publisher_tier', tuple(app_id), '?') AS tier,
           ad_format, toDate(event_time) AS day,
           sum(is_filled) / count()            AS f,
           sum(is_impression) / sum(is_filled) AS r
    FROM `inmobi-hari`.ad_events
    WHERE toDate(event_time) BETWEEN '2026-06-08' AND '2026-07-05' AND toDayOfWeek(event_time) <= 5
    GROUP BY tier, ad_format, day
)
SELECT tier, ad_format, quantileExact(0.5)(f) AS fill_rate, quantileExact(0.5)(r) AS render_rate
FROM d GROUP BY tier, ad_format;

CREATE TABLE IF NOT EXISTS `inmobi-hari`.fill_expected_1d (
    day Date, dimension LowCardinality(String), value LowCardinality(String),
    requests UInt64, fills UInt64, fills_expected Float64,
    impressions UInt64, imps_expected Float64, revenue Float64
) ENGINE = SummingMergeTree ORDER BY (dimension, value, day);

TRUNCATE TABLE `inmobi-hari`.fill_expected_1d;

-- vertical / campaign_type are deliberately ABSENT: they are advertiser
-- attributes, and an unfilled request has no advertiser, so an 'UNFILLED'
-- bucket has fill_rate = 0 by construction and scores z ~ -280 on a
-- perfectly healthy day.
INSERT INTO `inmobi-hari`.fill_expected_1d
WITH scored AS (
    SELECT toDate(e.event_time) AS day, e.is_filled AS is_filled, e.is_impression AS is_impression,
           e.revenue AS revenue, e.ad_format AS ad_format, fb.fill_rate AS p_fill, fb.render_rate AS p_rend,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_apps_v1','category',       tuple(e.app_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_apps','category',          tuple(e.app_id), 'unknown')) AS ev_category,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_apps_v1','publisher_tier', tuple(e.app_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_apps','publisher_tier',    tuple(e.app_id), 'unknown')) AS ev_tier,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','region',       tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','region',          tuple(e.geo_device_id), 'unknown')) AS ev_region,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','country',      tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','country',         tuple(e.geo_device_id), 'unknown')) AS ev_country,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','device_model', tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','device_model',    tuple(e.geo_device_id), 'unknown')) AS ev_device,
           if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_geo_v1','os_version',   tuple(e.geo_device_id), 'unknown'),
              dictGetOrDefault('inmobi-hari.dict_geo','os_version',      tuple(e.geo_device_id), 'unknown')) AS ev_os
    FROM `inmobi-hari`.ad_events e
    INNER JOIN `inmobi-hari`.v_fillbook_jun fb
        ON fb.tier = if(e.event_time < '2026-07-06',
              dictGetOrDefault('inmobi-hari.dict_apps_v1','publisher_tier', tuple(e.app_id), '?'),
              dictGetOrDefault('inmobi-hari.dict_apps','publisher_tier',    tuple(e.app_id), '?'))
       AND fb.ad_format = e.ad_format
)
SELECT day, dv.1, dv.2, count(), sum(is_filled), sum(p_fill), sum(is_impression), sum(p_fill * p_rend), sum(revenue)
FROM scored
ARRAY JOIN [
    ('TOTAL',          'all'),
    ('ad_format',      toString(ad_format)),
    ('category',       ev_category),
    ('publisher_tier', ev_tier),
    ('region',         ev_region),
    ('country',        ev_country),
    ('device_model',   ev_device),
    ('os_version',     ev_os)
] AS dv
GROUP BY day, dv.1, dv.2;

-- ---------------- requests: standing volume monitor ----------------
-- Counts, not a rate, so this uses median + MAD against the same-day-type
-- history rather than a binomial model. Catches whole-pipeline ingestion
-- gaps (e.g. Jun 21), which the rate/price detectors above cannot see —
-- a dropped stream of requests looks identical to a healthy stream at any
-- fixed sampling rate.
CREATE OR REPLACE VIEW `inmobi-hari`.v_request_alerts AS
WITH d AS (SELECT toDate(minute) AS day, toDayOfWeek(toDate(minute)) <= 5 AS wd, sum(requests) AS req
           FROM `inmobi-hari`.rollup_totals_1m GROUP BY day),
b AS (SELECT wd, groupArray(req) AS arr FROM d GROUP BY wd),
scored AS (
    SELECT d.day AS day, d.req AS requests,
           arrayReduce('median', b.arr) AS baseline,
           1.4826 * arrayReduce('median', arrayMap(x -> abs(x - arrayReduce('median', b.arr)), b.arr)) AS mad
    FROM d INNER JOIN b ON b.wd = d.wd
)
SELECT day, requests, round(baseline, 0) AS baseline,
       round((requests/baseline - 1)*100, 2) AS deviation_pct,
       round((requests - baseline)/(mad + 1e-9), 2) AS z,
       multiIf(abs(z) >= 10, 'P1', abs(z) >= 6, 'P2', 'P3') AS severity
FROM scored WHERE abs((requests - baseline)/(mad + 1e-9)) > 6
ORDER BY day;

-- ---------------- volume / mix: restated June baseline ----------------
-- Traffic volume follows the ID, not the label, so this one IS restated:
-- June events re-joined through the CURRENT dimension tables. Used for
-- mix / share checks only, never for rate or price.
CREATE TABLE IF NOT EXISTS `inmobi-hari`.baseline_restated_1h (
    dimension LowCardinality(String), value LowCardinality(String), hour DateTime,
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Float64
) ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (dimension, value, hour);

TRUNCATE TABLE `inmobi-hari`.baseline_restated_1h;

INSERT INTO `inmobi-hari`.baseline_restated_1h
SELECT dv.1, dv.2, toStartOfHour(event_time), count(), sum(is_filled),
       sum(is_impression), sum(is_click), sum(revenue)
FROM `inmobi-hari`.ad_events
ARRAY JOIN [
    ('ad_format',      toString(ad_format)),
    ('category',       dictGetOrDefault('inmobi-hari.dict_apps','category',       tuple(app_id),'unknown')),
    ('publisher_tier', dictGetOrDefault('inmobi-hari.dict_apps','publisher_tier', tuple(app_id),'unknown')),
    ('region',         dictGetOrDefault('inmobi-hari.dict_geo','region',       tuple(geo_device_id),'unknown')),
    ('country',        dictGetOrDefault('inmobi-hari.dict_geo','country',      tuple(geo_device_id),'unknown')),
    ('device_model',   dictGetOrDefault('inmobi-hari.dict_geo','device_model', tuple(geo_device_id),'unknown')),
    ('os_version',     dictGetOrDefault('inmobi-hari.dict_geo','os_version',   tuple(geo_device_id),'unknown')),
    ('vertical',       if(advertiser_id='','UNFILLED',dictGetOrDefault('inmobi-hari.dict_adv','vertical',      tuple(advertiser_id),'unknown'))),
    ('campaign_type',  if(advertiser_id='','UNFILLED',dictGetOrDefault('inmobi-hari.dict_adv','campaign_type', tuple(advertiser_id),'unknown')))
] AS dv
WHERE event_time < '2026-07-06'
GROUP BY 1, 2, 3;
