-- =====================================================================
--  ALERTS, scored against the June books, over the full history.
--
--  Rate metrics use a binomial standard error with an overdispersion
--  factor phi = 1.6, so the threshold self-calibrates with window size.
--  eCPM uses a relative deviation against the price-book expectation,
--  with a 0.5% noise floor -- 20x the 0.025pp residual measured
--  out-of-sample on 7 held-out June/July days.
-- =====================================================================

CREATE TABLE IF NOT EXISTS `inmobi-hari`.alerts_unseen (
    day Date, scope LowCardinality(String), dimension LowCardinality(String), segment String,
    metric LowCardinality(String), baseline Float64, observed Float64, deviation_pct Float64,
    z Float64, severity LowCardinality(String), revenue_impact_usd Float64,
    baseline_source LowCardinality(String)
) ENGINE = MergeTree ORDER BY (day, metric, dimension, segment);

TRUNCATE TABLE `inmobi-hari`.alerts_unseen;

-- ---------------- fill_rate / render_rate ----------------
INSERT INTO `inmobi-hari`.alerts_unseen
WITH 1.6 AS PHI
SELECT day,
       if(dimension = 'TOTAL', 'total', 'segment') AS scope,
       dimension, value AS segment, m.1 AS metric,
       round(m.2, 6) AS baseline, round(m.3, 6) AS observed,
       round((m.3/m.2 - 1)*100, 2) AS deviation_pct,
       round((m.3 - m.2)/(PHI*sqrt(m.2*(1-m.2)/m.4) + 1e-12), 2) AS z,
       multiIf(abs(z) >= 15, 'P1', abs(z) >= 8, 'P2', 'P3') AS severity,
       round(m.5, 2) AS revenue_impact_usd,
       'jun_fillbook_tier_x_format' AS baseline_source
FROM `inmobi-hari`.fill_expected_1d
ARRAY JOIN [
    ('fill_rate',   fills_expected/requests, fills/requests, toFloat64(requests),
                    (fills - fills_expected) * (impressions/fills) * (revenue/impressions)),
    ('render_rate', imps_expected/fills_expected, impressions/fills, toFloat64(fills),
                    (impressions - fills*(imps_expected/fills_expected)) * (revenue/impressions))
] AS m
WHERE requests >= 5000
  AND abs((m.3 - m.2)/(PHI*sqrt(m.2*(1-m.2)/m.4) + 1e-12)) > 8;

-- ---------------- eCPM ----------------
INSERT INTO `inmobi-hari`.alerts_unseen
WITH 0.005 AS SIGMA
SELECT day, if(dimension = 'TOTAL', 'total', 'segment') AS scope, dimension, value AS segment,
       'ecpm' AS metric,
       round(revenue_expected/impressions*1000, 6)     AS baseline,
       round(revenue/impressions*1000, 6)              AS observed,
       round((revenue/revenue_expected - 1)*100, 2)    AS deviation_pct,
       round((revenue/revenue_expected - 1)/SIGMA, 2)  AS z,
       multiIf(abs(z) >= 15, 'P1', abs(z) >= 8, 'P2', 'P3') AS severity,
       round(revenue - revenue_expected, 2) AS revenue_impact_usd,
       'jun_pricebook_country_x_format' AS baseline_source
FROM `inmobi-hari`.ecpm_expected_1d
WHERE impressions >= 2000
  AND abs((revenue/revenue_expected - 1)/SIGMA) > 8;

-- ---------------- collapse the alert stream into root causes ----------------
-- Over the full window, ~2600 raw segment alerts reduce to 17 rows across
-- 6 rate/price incidents. Within a (day, metric) the driver is the segment
-- with the largest |z|; the rest are composition bleed-through from it.
-- A 19%-share segment dropping 40% moves every overlapping segment by
-- ~7.7% -- that is arithmetic, not a wave of independent incidents.
CREATE OR REPLACE VIEW `inmobi-hari`.v_incidents_unseen AS
WITH ranked AS (
    SELECT *, row_number() OVER (PARTITION BY day, metric ORDER BY abs(z) DESC) AS rk,
              count()      OVER (PARTITION BY day, metric)                      AS alerts_in_group
    FROM `inmobi-hari`.alerts_unseen
    WHERE scope = 'segment'
)
SELECT day, metric, dimension, segment AS root_cause_segment,
       round(baseline, 5) AS baseline, round(observed, 5) AS observed,
       deviation_pct, z, severity, revenue_impact_usd,
       alerts_in_group - 1 AS bleed_through_alerts, baseline_source
FROM ranked WHERE rk = 1 ORDER BY day, abs(z) DESC;

-- ---------------- unified timeline: rate/price incidents + volume ----------------
-- v_incidents_unseen only covers metrics with a per-request rate (fill,
-- render, eCPM). A whole-pipeline ingestion gap (Jun 21) looks identical to
-- healthy traffic at any fixed sampling rate on those metrics -- it only
-- shows up as a drop in the request COUNT, which needs v_request_alerts.
CREATE OR REPLACE VIEW `inmobi-hari`.v_incidents_full AS
SELECT day, 'requests' AS metric, 'TOTAL' AS dimension, 'all' AS root_cause_segment,
       baseline, requests AS observed, deviation_pct, z, severity,
       NULL AS revenue_impact_usd, 0 AS bleed_through_alerts, 'median_mad_same_daytype' AS baseline_source
FROM `inmobi-hari`.v_request_alerts
UNION ALL
SELECT day, metric, dimension, root_cause_segment, baseline, observed, deviation_pct, z, severity,
       revenue_impact_usd, bleed_through_alerts, baseline_source
FROM `inmobi-hari`.v_incidents_unseen
ORDER BY day, metric;
