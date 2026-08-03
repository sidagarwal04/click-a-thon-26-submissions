-- Same-DOW (T vs T-7) daily wow + ClickHouse window seasonality residuals.
-- Baseline rows may come from default.ad_events when eda is an unseen-only slice
-- (eda keeps probe days; default supplies T−7 history without appending into eda).

TRUNCATE TABLE rca_daily_wow;

INSERT INTO rca_daily_wow
WITH daily AS
(
    SELECT
        event_date,
        sum(requests) AS requests,
        sum(fills) AS fills,
        sum(impressions) AS impressions,
        sum(clicks) AS clicks,
        sum(revenue) AS revenue
    FROM metrics_hourly
    GROUP BY event_date

    UNION ALL

    -- T−7 history from the original Cloud load (read-only), for short/unseen eda windows
    SELECT
        toDate(event_time) AS event_date,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(is_click) AS clicks,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN
    (
        SELECT DISTINCT event_date - 7
        FROM metrics_hourly
    )
      AND toDate(event_time) NOT IN
    (
        SELECT DISTINCT event_date FROM metrics_hourly
    )
    GROUP BY event_date
),
wow AS
(
    SELECT
        t.event_date AS event_date,
        b.event_date AS baseline_day,
        t.requests,
        t.fills,
        t.impressions,
        t.clicks,
        t.revenue,
        rca_fill_rate(t.fills, t.requests) AS fill_rate,
        rca_ecpm(t.revenue, t.impressions) AS ecpm,
        rca_ctr(t.clicks, t.impressions) AS ctr,
        rca_rpr(t.revenue, t.requests) AS rpr,
        b.requests AS base_requests,
        b.fills AS base_fills,
        b.impressions AS base_impressions,
        b.clicks AS base_clicks,
        b.revenue AS base_revenue,
        rca_fill_rate(b.fills, b.requests) AS base_fill_rate,
        rca_ecpm(b.revenue, b.impressions) AS base_ecpm,
        rca_ctr(b.clicks, b.impressions) AS base_ctr,
        rca_rpr(b.revenue, b.requests) AS base_rpr,
        rca_pct_chg(t.requests, b.requests) AS req_chg,
        rca_pct_chg(t.revenue, b.revenue) AS rev_chg,
        rca_abs_chg(
            rca_fill_rate(t.fills, t.requests),
            rca_fill_rate(b.fills, b.requests)
        ) AS fill_chg,
        rca_abs_chg(
            rca_ecpm(t.revenue, t.impressions),
            rca_ecpm(b.revenue, b.impressions)
        ) AS ecpm_chg
    FROM daily AS t
    INNER JOIN daily AS b ON b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM metrics_hourly)
),
scored AS
(
    SELECT
        *,
        toUInt8(rca_flag_volume(req_chg)) AS flag_volume,
        toUInt8(rca_flag_fill(fill_chg)) AS flag_fill,
        toUInt8(rca_flag_ecpm(ecpm_chg)) AS flag_ecpm,
        toUInt8(rca_flag_revenue(rev_chg)) AS flag_revenue,
        toUInt8(
            rca_flag_volume(req_chg)
            OR rca_flag_fill(fill_chg)
            OR rca_flag_ecpm(ecpm_chg)
            OR rca_flag_revenue(rev_chg)
        ) AS is_anomaly,
        count() OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS seasonal_history_n,
        avg(ifNull(req_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS mean_req_chg,
        stddevPop(ifNull(req_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS std_req_chg,
        avg(ifNull(rev_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS mean_rev_chg,
        stddevPop(ifNull(rev_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS std_rev_chg,
        avg(ifNull(fill_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS mean_fill_chg,
        stddevPop(ifNull(fill_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS std_fill_chg,
        avg(ifNull(ecpm_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS mean_ecpm_chg,
        stddevPop(ifNull(ecpm_chg, 0)) OVER (
            PARTITION BY toDayOfWeek(event_date)
            ORDER BY event_date
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS std_ecpm_chg
    FROM wow
)
SELECT
    event_date,
    baseline_day,
    'same_dow_minus_7' AS baseline_rule,
    requests,
    fills,
    impressions,
    clicks,
    revenue,
    fill_rate,
    ecpm,
    ctr,
    rpr,
    base_requests,
    base_fills,
    base_impressions,
    base_clicks,
    base_revenue,
    base_fill_rate,
    base_ecpm,
    base_ctr,
    base_rpr,
    req_chg,
    rev_chg,
    fill_chg,
    ecpm_chg,
    flag_volume,
    flag_fill,
    flag_ecpm,
    flag_revenue,
    is_anomaly,
    if(seasonal_history_n < 2 OR ifNull(std_req_chg, 0) = 0, 0,
        (ifNull(req_chg, 0) - mean_req_chg) / std_req_chg) AS z_requests,
    if(seasonal_history_n < 2 OR ifNull(std_rev_chg, 0) = 0, 0,
        (ifNull(rev_chg, 0) - mean_rev_chg) / std_rev_chg) AS z_revenue,
    if(seasonal_history_n < 2 OR ifNull(std_fill_chg, 0) = 0, 0,
        (ifNull(fill_chg, 0) - mean_fill_chg) / std_fill_chg) AS z_fill,
    if(seasonal_history_n < 2 OR ifNull(std_ecpm_chg, 0) = 0, 0,
        (ifNull(ecpm_chg, 0) - mean_ecpm_chg) / std_ecpm_chg) AS z_ecpm,
    toUInt8(seasonal_history_n) AS seasonal_history_n,
    toUInt8(
        seasonal_history_n < 2
        OR abs(if(seasonal_history_n < 2 OR ifNull(std_rev_chg, 0) = 0, 0,
            (ifNull(rev_chg, 0) - mean_rev_chg) / std_rev_chg)) >= 1.25
        OR abs(if(seasonal_history_n < 2 OR ifNull(std_fill_chg, 0) = 0, 0,
            (ifNull(fill_chg, 0) - mean_fill_chg) / std_fill_chg)) >= 1.25
        OR abs(if(seasonal_history_n < 2 OR ifNull(std_ecpm_chg, 0) = 0, 0,
            (ifNull(ecpm_chg, 0) - mean_ecpm_chg) / std_ecpm_chg)) >= 1.25
        OR abs(if(seasonal_history_n < 2 OR ifNull(std_req_chg, 0) = 0, 0,
            (ifNull(req_chg, 0) - mean_req_chg) / std_req_chg)) >= 1.25
    ) AS seasonal_ok,
    toUInt8(
        is_anomaly = 1
        AND (
            seasonal_history_n < 2
            OR abs(if(seasonal_history_n < 2 OR ifNull(std_rev_chg, 0) = 0, 0,
                (ifNull(rev_chg, 0) - mean_rev_chg) / std_rev_chg)) >= 1.25
            OR abs(if(seasonal_history_n < 2 OR ifNull(std_fill_chg, 0) = 0, 0,
                (ifNull(fill_chg, 0) - mean_fill_chg) / std_fill_chg)) >= 1.25
            OR abs(if(seasonal_history_n < 2 OR ifNull(std_ecpm_chg, 0) = 0, 0,
                (ifNull(ecpm_chg, 0) - mean_ecpm_chg) / std_ecpm_chg)) >= 1.25
            OR abs(if(seasonal_history_n < 2 OR ifNull(std_req_chg, 0) = 0, 0,
                (ifNull(req_chg, 0) - mean_req_chg) / std_req_chg)) >= 1.25
        )
    ) AS is_anomaly_gated,
    now() AS built_at
FROM scored;
