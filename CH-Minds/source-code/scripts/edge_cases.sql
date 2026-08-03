-- Reusable edge-case probe, re-run after any data change. Findings and
-- consequences are written up in EDGE_CASES.md; this is the executable form.
--
--   docker compose exec -T clickhouse clickhouse-client --user ro \
--     --password <pw> --multiquery --format PrettyCompactMonoBlock \
--     < scripts/edge_cases.sql

-- PART 1 - Funnel integrity. Expected: all zero.
SELECT 'A1 clicks without impression'      AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_click = 1 AND is_impression = 0;
SELECT 'A2 impressions without fill'       AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_impression = 1 AND is_filled = 0;
SELECT 'A3 revenue on unfilled request'    AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_filled = 0 AND revenue != 0;
SELECT 'A4 revenue without impression'     AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_impression = 0 AND revenue != 0;
SELECT 'A5 negative revenue'               AS check, count() AS n FROM inmobi_rca.ad_events WHERE revenue < 0;
SELECT 'A6 filled but no advertiser'       AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_filled = 1 AND advertiser_id = '';
SELECT 'A7 unfilled but has advertiser'    AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_filled = 0 AND advertiser_id != '';
SELECT 'A8 flags outside {0,1}'            AS check, count() AS n FROM inmobi_rca.ad_events WHERE is_filled > 1 OR is_impression > 1 OR is_click > 1;

-- PART 2 - Referential integrity. Expected: all zero.
SELECT 'B1 orphan app_id' AS check, count() AS n
FROM inmobi_rca.ad_events e LEFT ANTI JOIN inmobi_rca.apps a ON e.app_id = a.app_id;
SELECT 'B2 orphan geo_device_id' AS check, count() AS n
FROM inmobi_rca.ad_events e LEFT ANTI JOIN inmobi_rca.geo_device g ON e.geo_device_id = g.geo_device_id;
SELECT 'B3 orphan advertiser_id (non-blank)' AS check, count() AS n
FROM (SELECT advertiser_id FROM inmobi_rca.ad_events WHERE advertiser_id != '') e
LEFT ANTI JOIN inmobi_rca.advertisers d ON e.advertiser_id = d.advertiser_id;

-- PART 3 - Ratio bounds. Expected: all zero.
SELECT 'C1 ratio bound violations (day x country)' AS check,
       countIf(fills > reqs) AS fill_rate_gt_1,
       countIf(imps > fills) AS render_rate_gt_1,
       countIf(clicks > imps) AS ctr_gt_1
FROM (SELECT toDate(hour) AS d, country AS sv, countMerge(requests) AS reqs, sumMerge(fills) AS fills,
             sumMerge(impressions) AS imps, sumMerge(clicks) AS clicks
      FROM inmobi_rca.hourly_segment_metrics GROUP BY d, sv);

-- PART 4 - Day completeness. Not expected empty on Day 2; hours_present < 24
-- means backend/app/coverage.py should be restricting that day's baselines.
SELECT 'D1 partial days' AS check, toDate(hour) AS day,
       uniqExact(toHour(hour)) AS hours_present, max(toHour(hour)) AS max_hour
FROM inmobi_rca.hourly_segment_metrics
GROUP BY day HAVING hours_present < 24 ORDER BY day;

-- PART 5 - Baseline coverage. Days with < 2 prior samples should show as
-- "Not evaluated" on the dashboard, not green/normal.
SELECT 'E1 prior same-weekday samples per day' AS check, day, prior_samples,
       if(prior_samples < 2, 'NOT EVALUATED', 'evaluated') AS status
FROM (
  SELECT toDate(hour) AS day,
         count() OVER (PARTITION BY toDayOfWeek(toDate(hour)) ORDER BY toDate(hour)
                       ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prior_samples
  FROM (SELECT DISTINCT toStartOfDay(hour) AS hour FROM inmobi_rca.hourly_segment_metrics)
) ORDER BY day;

-- PART 6 - Baseline contamination: `overstatement` is how much a mean
-- baseline exaggerates vs the robust median one the pipeline uses.
SELECT 'F1 mean vs median baseline (revenue)' AS check, day, round(revenue,2) AS revenue,
       round(base_mean,2) AS baseline_mean, round((revenue-base_mean)/base_mean,4) AS pct_dev_mean,
       round(base_median,2) AS baseline_median, round((revenue-base_median)/base_median,4) AS pct_dev_median,
       round(abs((revenue-base_mean)/base_mean) - abs((revenue-base_median)/base_median), 4) AS overstatement
FROM (
  SELECT day, revenue, avg(revenue) OVER w AS base_mean, quantileExact(0.5)(revenue) OVER w AS base_median
  FROM (SELECT toDate(hour) AS day, sumMerge(revenue) AS revenue
        FROM inmobi_rca.hourly_segment_metrics GROUP BY day)
  WINDOW w AS (PARTITION BY toDayOfWeek(day) ORDER BY day ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
)
WHERE isFinite(base_mean) AND base_mean > 0 AND base_median > 0
ORDER BY overstatement DESC LIMIT 10;

-- PART 7 - Degenerate cuts. Expected: fill_rate exactly 1 for every
-- non-blank vertical/campaign_type, 0 for blank. See metrics.py.
SELECT 'G1 fill_rate by vertical' AS check, vertical,
       round(sumMerge(fills)/countMerge(requests), 6) AS fill_rate
FROM inmobi_rca.hourly_segment_metrics GROUP BY vertical ORDER BY vertical;

SELECT 'G2 fill_rate by campaign_type' AS check, campaign_type,
       round(sumMerge(fills)/countMerge(requests), 6) AS fill_rate
FROM inmobi_rca.hourly_segment_metrics GROUP BY campaign_type ORDER BY campaign_type;

-- PART 8 - Blank pseudo-segment. Expected: all-zero metrics (unfilled
-- traffic, not a real segment - metrics.BLANK_SEGMENT_VALUE).
SELECT 'H1 blank vertical is all-zero' AS check,
       countMerge(requests) AS requests, sumMerge(fills) AS fills,
       sumMerge(impressions) AS impressions, sumMerge(clicks) AS clicks, sumMerge(revenue) AS revenue
FROM inmobi_rca.hourly_segment_metrics WHERE vertical = '';

SELECT 'H2 blank share of rollup rows' AS check,
       countIf(vertical = '') AS blank_rows, count() AS total_rows,
       round(countIf(vertical = '') / count(), 4) AS share
FROM inmobi_rca.hourly_segment_metrics;

-- PART 9 - Rollup vs raw cross-check, the one that caught the ORDER BY
-- corruption bug. H0 must be 0 before I1 means anything: dimension tables
-- dedupe only on merge, so a pending merge makes I1 falsely report
-- corruption (hit for real - see EDGE_CASES.md EC-8). If H0 is non-zero, run
-- OPTIMIZE TABLE inmobi_rca.{apps,advertisers,geo_device} FINAL and re-run.
SELECT 'H0 duplicate dimension rows (must be 0 before trusting I1)' AS check,
       (SELECT count() - uniqExact(app_id) FROM inmobi_rca.apps) AS dup_apps,
       (SELECT count() - uniqExact(advertiser_id) FROM inmobi_rca.advertisers) AS dup_advertisers,
       (SELECT count() - uniqExact(geo_device_id) FROM inmobi_rca.geo_device) AS dup_geo_device;

-- NOTE (added after the 2026-07-06..10 unseen slice load): this check compares
-- the rollup against a join with the CURRENT geo_device table. That table was
-- reloaded with the unseen slice's regenerated attribute values (same IDs,
-- different country/device/os - see spec.md), so it now only matches events
-- rolled up AFTER that reload. Rows before 2026-07-06 were materialized
-- against the OLD dimension snapshot and will legitimately mismatch here -
-- that's expected divergence, not corruption (proven by re-running this same
-- join against the frozen `data/inmobi/*.csv` snapshot: 0 mismatches, see
-- EDGE_CASES.md EC-9). Scoped to the unseen slice only, where the check's
-- assumption (rollup and live dimension table agree) actually holds.
SELECT 'I1 rollup vs raw by country (unseen slice, 2026-07-06+)' AS check,
       countIf(abs(rollup_rev - raw_rev) > 0.000001) AS mismatched_countries,
       max(abs(rollup_rev - raw_rev)) AS max_abs_diff
FROM (
  WITH
    rollup AS (SELECT country, sumMerge(revenue) AS rev FROM inmobi_rca.hourly_segment_metrics
               WHERE toDate(hour) >= '2026-07-06' GROUP BY country),
    raw AS (SELECT gd.country AS country, sum(e.revenue) AS rev
            FROM inmobi_rca.ad_events e
            INNER JOIN (SELECT geo_device_id, country FROM inmobi_rca.geo_device FINAL) AS gd
                    ON e.geo_device_id = gd.geo_device_id
            WHERE toDate(e.event_time) >= '2026-07-06'
            GROUP BY country)
  SELECT rollup.country AS country, rollup.rev AS rollup_rev, raw.rev AS raw_rev
  FROM rollup INNER JOIN raw ON rollup.country = raw.country
);

-- PART 10 - Scale/cardinality snapshot backing SCALABILITY.md's projections.
SELECT 'J1 cardinality snapshot' AS check,
       (SELECT count() FROM inmobi_rca.ad_events) AS raw_events,
       count() AS rollup_rows,
       uniqExact(hour) AS hours,
       round(count() / uniqExact(hour), 0) AS avg_rollup_rows_per_hour,
       uniqExact((ad_format,category,publisher_tier,vertical,campaign_type,region,country,device_model,os_version)) AS distinct_combinations
FROM inmobi_rca.hourly_segment_metrics;
