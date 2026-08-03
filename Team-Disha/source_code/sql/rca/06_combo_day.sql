-- Combo segment WoW: os×region and format×region (dictGet enrichment).
-- Probe from eda.ad_events; T−7 from default.ad_events when eda is unseen-only.

TRUNCATE TABLE rca_combo_day;

INSERT INTO rca_combo_day
WITH
probe_dates AS
(
    SELECT DISTINCT event_date FROM ad_events
),
baseline_dates AS
(
    SELECT DISTINCT event_date - 7 AS event_date FROM probe_dates
),
os_region_agg AS
(
    SELECT
        event_date,
        concat(
            dictGetOrDefault('eda.dict_geo_device', 'os_version', geo_device_id, ''),
            ' x ',
            dictGetOrDefault('eda.dict_geo_device', 'region', geo_device_id, '')
        ) AS segment,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM ad_events
    GROUP BY event_date, segment

    UNION ALL

    SELECT
        toDate(event_time) AS event_date,
        concat(
            dictGetOrDefault('eda.dict_geo_device', 'os_version', geo_device_id, ''),
            ' x ',
            dictGetOrDefault('eda.dict_geo_device', 'region', geo_device_id, '')
        ) AS segment,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN (SELECT event_date FROM baseline_dates)
      AND toDate(event_time) NOT IN (SELECT event_date FROM probe_dates)
    GROUP BY event_date, segment
),
format_region_agg AS
(
    SELECT
        event_date,
        concat(
            ad_format,
            ' x ',
            dictGetOrDefault('eda.dict_geo_device', 'region', geo_device_id, '')
        ) AS segment,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM ad_events
    GROUP BY event_date, segment

    UNION ALL

    SELECT
        toDate(event_time) AS event_date,
        concat(
            ad_format,
            ' x ',
            dictGetOrDefault('eda.dict_geo_device', 'region', geo_device_id, '')
        ) AS segment,
        count() AS requests,
        sum(is_filled) AS fills,
        sum(is_impression) AS impressions,
        sum(revenue) AS revenue
    FROM default.ad_events
    WHERE toDate(event_time) IN (SELECT event_date FROM baseline_dates)
      AND toDate(event_time) NOT IN (SELECT event_date FROM probe_dates)
    GROUP BY event_date, segment
),
joined AS
(
    SELECT
        'os_region' AS combo_kind,
        t.event_date AS event_date,
        t.segment AS segment,
        t.requests AS req_t,
        b.requests AS req_b,
        t.fills AS fills_t,
        b.fills AS fills_b,
        t.impressions AS imp_t,
        b.impressions AS imp_b,
        t.revenue AS rev_t,
        b.revenue AS rev_b
    FROM os_region_agg AS t
    INNER JOIN os_region_agg AS b
        ON b.segment = t.segment AND b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM probe_dates)
      AND t.requests > 1000 AND b.requests > 1000
      AND t.segment NOT LIKE ' x %'
      AND t.segment NOT LIKE '% x '

    UNION ALL

    SELECT
        'format_region',
        t.event_date,
        t.segment,
        t.requests,
        b.requests,
        t.fills,
        b.fills,
        t.impressions,
        b.impressions,
        t.revenue,
        b.revenue
    FROM format_region_agg AS t
    INNER JOIN format_region_agg AS b
        ON b.segment = t.segment AND b.event_date = t.event_date - 7
    WHERE t.event_date IN (SELECT event_date FROM probe_dates)
      AND t.impressions > 800 AND b.impressions > 800
      AND t.segment NOT LIKE '% x '
)
SELECT
    event_date,
    event_date - 7 AS baseline_day,
    combo_kind,
    segment,
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
