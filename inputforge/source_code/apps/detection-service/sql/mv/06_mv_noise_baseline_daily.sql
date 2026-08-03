-- Replaces sql/incremental/02_noise_baseline_daily.sql (deleted) and the
-- app-level dailyNoiseBaselineJob cron entry. A REFRESHABLE materialized
-- view: unlike the reactive MVs in this directory (which fire on INSERT),
-- this one reschedules itself inside ClickHouse on a wall-clock cadence —
-- no node-cron trigger needed for this stage either.
--
-- REFRESH EVERY 1 DAY, no APPEND: each refresh atomically replaces the
-- entire content of inmobi.metric_noise_baseline with a fresh full-history
-- recompute, rather than appending one more row per metric per day. This is
-- a genuine improvement over the old cron version, not just a mechanical
-- port — mv_zr_hourly's argMax(pooled_var, computed_at) read still works
-- unchanged (there's now exactly one row per metric to "pick", so argMax is
-- a no-op), but the table itself no longer grows unboundedly or depends on
-- ReplacingMergeTree merges to stay small.
--
-- Pooled residual variance is a slow-moving property of a metric's overall
-- noise level (see 00_schema.sql's metric_noise_baseline comment) — a daily
-- cadence stays safely representative for the reactive detection MVs
-- (sql/mv/02) that read it, same as before.
--
-- If ClickHouse Cloud rejects this with "unknown setting" on first run,
-- refreshable views were still experimental on that version — add
-- `SET allow_experimental_refreshable_materialized_view = 1;` before this
-- statement (omitted here since it's GA on current ClickHouse Cloud and an
-- unrecognized SETTINGS/SET can itself error on some versions).

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_noise_baseline_daily
REFRESH EVERY 1 DAY
TO inmobi.metric_noise_baseline
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
  SELECT h.dow AS dow, h.hod AS hod, 'requests' AS metric, h.requests / dt.req_trend AS value
  FROM inmobi.metrics_hourly_v h INNER JOIN daily_trend dt ON h.d = dt.d WHERE dt.trend_n >= 2
  UNION ALL
  SELECT h.dow, h.hod, 'revenue', h.revenue / dt.rev_trend
  FROM inmobi.metrics_hourly_v h INNER JOIN daily_trend dt ON h.d = dt.d WHERE dt.trend_n >= 2
  UNION ALL SELECT dow, hod, 'fill_rate', fills / requests FROM inmobi.metrics_hourly_v
  UNION ALL SELECT dow, hod, 'render_rate', impressions / fills FROM inmobi.metrics_hourly_v
  UNION ALL SELECT dow, hod, 'ctr', clicks / impressions FROM inmobi.metrics_hourly_v
  UNION ALL SELECT dow, hod, 'ecpm', revenue / impressions * 1000 FROM inmobi.metrics_hourly_v
  UNION ALL SELECT dow, hod, 'rpr', revenue / requests FROM inmobi.metrics_hourly_v
),
cell_mean AS (SELECT metric, dow, hod, avg(value) AS ca FROM values_unpivoted GROUP BY metric, dow, hod)
SELECT u.metric AS metric, varSamp(u.value - cm.ca) AS pooled_var, now() AS computed_at
FROM values_unpivoted u JOIN cell_mean cm USING (metric, dow, hod)
GROUP BY u.metric;
