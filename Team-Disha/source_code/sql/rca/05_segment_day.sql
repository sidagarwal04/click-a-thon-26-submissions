-- Single-dimension segment WoW (os_version, region, ad_format, category).
-- Probe days from eda.ad_events; T−7 baselines from default.ad_events when needed
-- (unseen-only eda), with attributes via eda dictionaries (regenerated dims).

TRUNCATE TABLE rca_segment_day;

INSERT INTO rca_segment_day
WITH
probe_dates AS
(
    SELECT DISTINCT event_date FROM ad_events
),
baseline_dates AS
(
    SELECT DISTINCT event_date - 7 AS event_date FROM probe_dates
),
os_agg AS
(
    SELECT
        event_date,
        dictGetOrDefault('eda.dict_geo_device', 'os_version', geo_device_id, '') AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM ad_events
    GROUP BY event_date, dim_value

    UNION ALL

    SELECT
        toDate(event_time) AS event_date,
        dictGetOrDefault('eda.dict_geo_device', 'os_version', geo_device_id, '') AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN (SELECT event_date FROM baseline_dates)
      AND toDate(event_time) NOT IN (SELECT event_date FROM probe_dates)
    GROUP BY event_date, dim_value
),
region_agg AS
(
    SELECT
        event_date,
        dictGetOrDefault('eda.dict_geo_device', 'region', geo_device_id, '') AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM ad_events
    GROUP BY event_date, dim_value

    UNION ALL

    SELECT
        toDate(event_time) AS event_date,
        dictGetOrDefault('eda.dict_geo_device', 'region', geo_device_id, '') AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN (SELECT event_date FROM baseline_dates)
      AND toDate(event_time) NOT IN (SELECT event_date FROM probe_dates)
    GROUP BY event_date, dim_value
),
format_agg AS
(
    SELECT
        event_date,
        ad_format AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM ad_events
    GROUP BY event_date, dim_value

    UNION ALL

    SELECT
        toDate(event_time) AS event_date,
        ad_format AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN (SELECT event_date FROM baseline_dates)
      AND toDate(event_time) NOT IN (SELECT event_date FROM probe_dates)
    GROUP BY event_date, dim_value
),
cat_agg AS
(
    SELECT
        event_date,
        dictGetOrDefault('eda.dict_apps', 'category', app_id, '') AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM ad_events
    GROUP BY event_date, dim_value

    UNION ALL

    SELECT
        toDate(event_time) AS event_date,
        dictGetOrDefault('eda.dict_apps', 'category', app_id, '') AS dim_value,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN (SELECT event_date FROM baseline_dates)
      AND toDate(event_time) NOT IN (SELECT event_date FROM probe_dates)
    GROUP BY event_date, dim_value
),
joined AS
(
    SELECT 'os_version' AS dimension, t.event_date, t.dim_value,
        t.requests AS req_t, b.requests AS req_b,
        t.fills AS fills_t, b.fills AS fills_b,
        t.impressions AS imp_t, b.impressions AS imp_b,
        t.revenue AS rev_t, b.revenue AS rev_b
    FROM os_agg AS t
    INNER JOIN os_agg AS b ON b.dim_value = t.dim_value AND b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM probe_dates)
      AND t.requests > 2000 AND b.requests > 2000
      AND t.dim_value != ''

    UNION ALL

    SELECT 'region', t.event_date, t.dim_value,
        t.requests, b.requests, t.fills, b.fills, t.impressions, b.impressions, t.revenue, b.revenue
    FROM region_agg AS t
    INNER JOIN region_agg AS b ON b.dim_value = t.dim_value AND b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM probe_dates)
      AND t.requests > 2000 AND b.requests > 2000
      AND t.dim_value != ''

    UNION ALL

    SELECT 'ad_format', t.event_date, t.dim_value,
        t.requests, b.requests, t.fills, b.fills, t.impressions, b.impressions, t.revenue, b.revenue
    FROM format_agg AS t
    INNER JOIN format_agg AS b ON b.dim_value = t.dim_value AND b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM probe_dates)
      AND t.requests > 2000 AND b.requests > 2000

    UNION ALL

    SELECT 'category', t.event_date, t.dim_value,
        t.requests, b.requests, t.fills, b.fills, t.impressions, b.impressions, t.revenue, b.revenue
    FROM cat_agg AS t
    INNER JOIN cat_agg AS b ON b.dim_value = t.dim_value AND b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM probe_dates)
      AND t.requests > 2000 AND b.requests > 2000
      AND t.dim_value != ''
)
SELECT
    event_date,
    event_date - 7 AS baseline_day,
    dimension,
    toString(dim_value) AS dim_value,
    concat(dimension, '=', toString(dim_value)) AS segment,
    req_t,
    req_b,
    fills_t,
    fills_b,
    imp_t,
    imp_b,
    rev_t,
    rev_b,
    rca_fill_rate(fills_t, req_t) AS fill_t,
    rca_fill_rate(fills_b, req_b) AS fill_b,
    ifNull(rca_abs_chg(rca_fill_rate(fills_t, req_t), rca_fill_rate(fills_b, req_b)), 0) AS fill_chg,
    rca_ecpm(rev_t, imp_t) AS ecpm_t,
    rca_ecpm(rev_b, imp_b) AS ecpm_b,
    ifNull(rca_abs_chg(rca_ecpm(rev_t, imp_t), rca_ecpm(rev_b, imp_b)), 0) AS ecpm_chg,
    ifNull(rca_pct_chg(req_t, req_b), 0) AS req_chg,
    rev_t - rev_b AS d_rev,
    abs(ifNull(rca_abs_chg(rca_fill_rate(fills_t, req_t), rca_fill_rate(fills_b, req_b)), 0)) * req_t AS fill_impact,
    now() AS built_at
FROM joined;
