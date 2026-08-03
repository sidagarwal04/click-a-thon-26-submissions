-- Analyst-friendly wide view: one row per hour, every metric as its own set
-- of columns (value, z-score, which methods flagged it) — the same shape as
-- the notebook's `df`, but live off the actual pipeline tables instead of
-- recomputed in Python each time. A plain VIEW, not materialized: no storage,
-- no maintenance, always reflects the current state of metrics_hourly /
-- metric_zr_hourly / anomalies.
--
-- `SELECT * FROM inmobi.hourly_analyst_view WHERE fill_rate_flagged_by != []`
-- is the kind of query this exists for — no need to know the long/unpivoted
-- internal schema, join keys, or how zr/shrinkage/thresholds work.

CREATE VIEW IF NOT EXISTS inmobi.hourly_analyst_view AS
WITH zr_pivot AS (
  SELECT hour_ts,
    anyIf(zr, metric = 'requests')    AS requests_zr,
    anyIf(zr, metric = 'fill_rate')   AS fill_rate_zr,
    anyIf(zr, metric = 'render_rate') AS render_rate_zr,
    anyIf(zr, metric = 'ctr')         AS ctr_zr,
    anyIf(zr, metric = 'revenue')     AS revenue_zr,
    anyIf(zr, metric = 'ecpm')        AS ecpm_zr,
    anyIf(zr, metric = 'rpr')         AS rpr_zr
  FROM inmobi.metric_zr_hourly
  GROUP BY hour_ts
),
flags AS (
  SELECT time_window AS hour_ts,
    groupUniqArrayIf(method, metric = 'requests')    AS requests_flagged_by,
    groupUniqArrayIf(method, metric = 'fill_rate')   AS fill_rate_flagged_by,
    groupUniqArrayIf(method, metric = 'render_rate') AS render_rate_flagged_by,
    groupUniqArrayIf(method, metric = 'ctr')         AS ctr_flagged_by,
    groupUniqArrayIf(method, metric = 'revenue')     AS revenue_flagged_by,
    groupUniqArrayIf(method, metric = 'ecpm')        AS ecpm_flagged_by,
    groupUniqArrayIf(method, metric = 'rpr')         AS rpr_flagged_by
  FROM inmobi.anomalies
  GROUP BY time_window
)
SELECT
  m.hour_ts AS hour_ts, m.d AS d, m.dow AS dow, m.hod AS hod,

  m.requests AS requests,
  z.requests_zr AS requests_zr,
  ifNull(f.requests_flagged_by, [])       AS requests_flagged_by,

  m.fills / m.requests AS fill_rate,
  z.fill_rate_zr AS fill_rate_zr,
  ifNull(f.fill_rate_flagged_by, [])      AS fill_rate_flagged_by,

  m.impressions / nullif(m.fills, 0) AS render_rate,
  z.render_rate_zr AS render_rate_zr,
  ifNull(f.render_rate_flagged_by, [])    AS render_rate_flagged_by,

  m.clicks / nullif(m.impressions, 0) AS ctr,
  z.ctr_zr AS ctr_zr,
  ifNull(f.ctr_flagged_by, [])            AS ctr_flagged_by,

  m.revenue AS revenue,
  z.revenue_zr AS revenue_zr,
  ifNull(f.revenue_flagged_by, [])        AS revenue_flagged_by,

  m.revenue / nullif(m.impressions, 0) * 1000 AS ecpm,
  z.ecpm_zr AS ecpm_zr,
  ifNull(f.ecpm_flagged_by, [])           AS ecpm_flagged_by,

  m.revenue / m.requests AS rpr,
  z.rpr_zr AS rpr_zr,
  ifNull(f.rpr_flagged_by, [])            AS rpr_flagged_by

FROM inmobi.metrics_hourly_v m
LEFT JOIN zr_pivot z USING (hour_ts)
LEFT JOIN flags f USING (hour_ts)
ORDER BY hour_ts;
