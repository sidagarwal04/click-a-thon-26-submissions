-- Seasonal z-residual, refreshable — not reactive. This used to cascade off
-- mv_metrics_hourly (fire on inmobi.metrics_hourly inserts), but that's
-- exactly the failure mode found in production: a *cascaded* MV (one
-- sourced from another MV's target table, not directly from ad_events)
-- does not reliably fire on a large bulk INSERT — mv_metrics_hourly itself
-- (a single hop off ad_events) fired correctly, but this one silently
-- stalled downstream of it. A refreshable MV sidesteps the problem
-- entirely: it doesn't depend on trigger propagation at all, it just
-- recomputes the full series on its own schedule and atomically replaces
-- inmobi.metric_zr_hourly (REPLACE semantics, not APPEND — same pattern as
-- mv_noise_baseline_daily/mv_incidents).
--
-- No `touched` scoping anymore — a refreshable MV has no concept of "just
-- this block," it always recomputes the whole thing. That's fine here:
-- metrics_hourly_v stays cheap indefinitely (a year of hourly rollup is
-- ~8,760 rows), so a full rescan every cycle is not expensive at this
-- data scale. mv_detect_global (sql/mv/03) DEPENDS ON this view, so it
-- only runs after this one's refresh has actually completed.

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_zr_hourly
REFRESH EVERY 10 MINUTE
TO inmobi.metric_zr_hourly
AS
WITH daily AS (
  SELECT d, any(dow) AS dow, sum(requests) AS req_total, sum(revenue) AS rev_total
  FROM inmobi.metrics_hourly_v GROUP BY d
),
daily_trend AS (
  SELECT d, dow, req_total, rev_total,
    avg(req_total) OVER (ORDER BY d ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS req_trend,
    avg(rev_total) OVER (ORDER BY d ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS rev_trend,
    count(req_total) OVER (ORDER BY d ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS trend_n
  FROM daily
),
values_unpivoted AS (
  SELECT h.hour_ts AS hour_ts, h.d AS d, h.dow AS dow, h.hod AS hod,
    'requests' AS metric, h.requests / dt.req_trend AS value
  FROM inmobi.metrics_hourly_v h INNER JOIN daily_trend dt ON h.d = dt.d WHERE dt.trend_n >= 2
  UNION ALL
  SELECT h.hour_ts, h.d, h.dow, h.hod, 'revenue', h.revenue / dt.rev_trend
  FROM inmobi.metrics_hourly_v h INNER JOIN daily_trend dt ON h.d = dt.d WHERE dt.trend_n >= 2
  UNION ALL SELECT hour_ts, d, dow, hod, 'fill_rate', fills / requests FROM inmobi.metrics_hourly_v
  UNION ALL SELECT hour_ts, d, dow, hod, 'render_rate', impressions / fills FROM inmobi.metrics_hourly_v
  UNION ALL SELECT hour_ts, d, dow, hod, 'ctr', clicks / impressions FROM inmobi.metrics_hourly_v
  UNION ALL SELECT hour_ts, d, dow, hod, 'ecpm', revenue / impressions * 1000 FROM inmobi.metrics_hourly_v
  UNION ALL SELECT hour_ts, d, dow, hod, 'rpr', revenue / requests FROM inmobi.metrics_hourly_v
),
seasonal AS (
  SELECT *,
    avg(value) OVER w AS mean_v, varSamp(value) OVER w AS var_v, count(value) OVER w AS baseline_n
  FROM values_unpivoted
  WINDOW w AS (PARTITION BY metric, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
),
noise AS (
  SELECT metric, argMax(pooled_var, computed_at) AS pooled_var
  FROM inmobi.metric_noise_baseline GROUP BY metric
)
SELECT s.metric AS metric, s.hour_ts AS hour_ts, s.d AS d, s.dow AS dow, s.hod AS hod,
  (s.value - s.mean_v) / sqrt((s.baseline_n * ifNull(s.var_v, 0) + 3 * n.pooled_var) / (s.baseline_n + 3)) AS zr,
  now() AS computed_at
FROM seasonal s
JOIN noise n USING (metric)
WHERE s.baseline_n >= 2;
