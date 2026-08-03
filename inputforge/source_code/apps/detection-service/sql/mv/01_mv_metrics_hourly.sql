-- Replaces the old hourly-cron rollup (sql/incremental/01_metrics_hourly_tick.sql,
-- deleted). Fires on every INSERT into inmobi.ad_events, aggregating exactly
-- the block just inserted — no "target = now() - 1 HOUR" polling, no
-- watermark check, no orchestrator step. A bulk load spanning many hours
-- just produces many (hour_ts,d,dow,hod) groups in one firing, which is fine
-- here: this stage is a pure per-row aggregation, no trailing-window/self-join
-- risk (that risk lives in mv_zr_hourly, see sql/mv/02).

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_metrics_hourly
TO inmobi.metrics_hourly
AS
SELECT
    toStartOfHour(event_time) AS hour_ts,
    toDate(event_time)        AS d,
    toDayOfWeek(event_time)   AS dow,
    toHour(event_time)        AS hod,
    count()                   AS requests,
    sum(is_filled)             AS fills,
    sum(is_impression)         AS impressions,
    sum(is_click)               AS clicks,
    sum(revenue)                 AS revenue
FROM inmobi.ad_events
GROUP BY hour_ts, d, dow, hod;
