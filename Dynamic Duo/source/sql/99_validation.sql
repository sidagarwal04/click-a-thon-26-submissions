-- Data validation on load — run BEFORE any investigation (agent_requirements.md).
-- Every check emits a `pass` flag; violations change interpretation, they are not
-- assumed away. Informational rows have no pass column.

-- 0 · what got loaded
SELECT 'dataset_summary' AS check,
       dataset,
       count()                            AS rows,
       min(event_time)                    AS from_ts,
       max(event_time)                    AS to_ts
FROM rca.ad_events
GROUP BY dataset;

-- 1 · cascade integrity: every raw row enriched, rollup populated
SELECT 'cascade_integrity' AS check,
       (SELECT count() FROM rca.ad_events)            AS raw_rows,
       (SELECT count() FROM rca.ad_events_enriched)   AS enriched_rows,
       (SELECT count() FROM rca.metrics_hourly_by_dim) AS rollup_rows,
       raw_rows = enriched_rows AND rollup_rows > 0   AS pass;

-- 2 · funnel invariants: no click without impression, no impression without fill
SELECT 'funnel_invariants' AS check,
       countIf(is_click = 1 AND is_impression = 0)    AS click_wo_impression,
       countIf(is_impression = 1 AND is_filled = 0)   AS impression_wo_fill,
       click_wo_impression + impression_wo_fill = 0   AS pass
FROM rca.ad_events;

-- 3 · revenue earned on impressions only (else eCPM formula needs a filter)
SELECT 'revenue_on_impressions_only' AS check,
       countIf(revenue > 0 AND is_impression = 0)     AS violating_rows,
       round(sumIf(revenue, is_impression = 0), 6)    AS stray_revenue,
       violating_rows = 0                             AS pass
FROM rca.ad_events;

-- 4 · advertiser_id empty ⟺ unfilled (else vertical sweeps get a fake segment)
SELECT 'advertiser_iff_filled' AS check,
       countIf((advertiser_id = '') != (is_filled = 0)) AS mismatches,
       mismatches = 0                                   AS pass
FROM rca.ad_events;

-- 5 · dim coverage: events whose keys missed the dim tables (feeds 'unknown' bucket;
--     nonzero on the unseen slice is a finding, not a failure — review before pass)
SELECT 'dim_coverage_unknown' AS check,
       countIf(category = 'unknown')                  AS app_key_misses,
       countIf(region = 'unknown')                    AS geo_key_misses,
       countIf(vertical = 'unknown')                  AS advertiser_key_misses,
       app_key_misses + geo_key_misses + advertiser_key_misses = 0 AS pass
FROM rca.ad_events_enriched;

-- 6 · hourly continuity: gaps = ingestion holes (a "volume drop" that is missing data)
SELECT 'hourly_continuity' AS check,
       uniqExact(toStartOfHour(event_time))                    AS hours_present,
       dateDiff('hour', min(event_time), max(event_time)) + 1  AS hours_expected,
       hours_present = hours_expected                          AS pass
FROM rca.ad_events;

-- 7 · duplicate ingestion. Unfilled rows (revenue = 0) collide organically at second
--     precision — dev data shows ~130 across 33 days; only a sudden concentration is
--     suspicious. Revenue-bearing duplicates CANNOT occur organically (Float64 revenue
--     never collides) — any at all = double ingestion = hard fail.
SELECT 'exact_duplicate_rows' AS check,
       coalesce(sumIf(c - 1, has_revenue), 0)     AS dup_with_revenue,
       coalesce(sumIf(c - 1, NOT has_revenue), 0) AS dup_unfilled_organic,
       dup_with_revenue = 0                       AS pass
FROM
(
    SELECT revenue > 0 AS has_revenue, count() AS c
    FROM rca.ad_events
    GROUP BY event_time, app_id, geo_device_id, advertiser_id, ad_format,
             is_filled, is_impression, is_click, revenue
    HAVING c > 1
);

-- 8 · rollup reconciles with enriched (alert numbers == investigator numbers)
SELECT 'rollup_reconciles' AS check,
       (SELECT count() FROM rca.ad_events_enriched)  AS enriched_requests,
       (SELECT sum(requests) FROM rca.metrics_hourly_by_dim WHERE dimension = 'global') AS rollup_requests,
       (SELECT round(sum(revenue), 2) FROM rca.ad_events_enriched) AS enriched_revenue,
       (SELECT round(sum(revenue), 2) FROM rca.metrics_hourly_by_dim WHERE dimension = 'global') AS rollup_revenue,
       enriched_requests = rollup_requests
           AND abs(enriched_revenue - rollup_revenue) < 0.01 AS pass;

-- 9 · rollup shape (informational): distinct series per dimension
SELECT 'rollup_series' AS check,
       dimension,
       uniqExact(value) AS series
FROM rca.metrics_hourly_by_dim
GROUP BY dimension
ORDER BY dimension;
