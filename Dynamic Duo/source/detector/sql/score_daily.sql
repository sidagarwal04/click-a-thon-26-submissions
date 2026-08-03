-- Daily scoring: same ensemble shape as score_hourly.sql at day grain. Exists for
-- slow drifts invisible at hourly z (e.g. a -1.2pp fill drift over 3 days): a day
-- aggregates 24x the volume, so small persistent shifts become large daily z.
-- Models: naive = trailing 10 days; how -> same weekday +/-2 weeks (two-sided);
-- stl period 7 (needs >= 14 days); flat = whole-series robust. No hour-of-day model.

WITH
bounds AS (
    SELECT toDate(min(window_start)) AS min_d, toDate(max(window_start)) AS max_d
    FROM rca.metrics_hourly_by_dim
),
days AS (
    SELECT arrayJoin(arrayMap(i -> min_d + i,
                              range(toUInt32(max_d - min_d + 1)))) AS day
    FROM bounds
),
per_day AS (
    SELECT dimension, value, toDate(window_start) AS day,
           sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS imps,
           sum(clicks) AS clicks, sum(revenue) AS rev
    FROM rca.metrics_hourly_by_dim
    WHERE dimension NOT IN ('app_id', 'advertiser_id')
    GROUP BY dimension, value, day
),
series_names AS (SELECT DISTINCT dimension, value FROM per_day),
grid AS (
    SELECT s.dimension AS dimension, s.value AS value, d.day AS day,
           coalesce(p.requests, 0) AS requests, coalesce(p.fills, 0) AS fills,
           coalesce(p.imps, 0)     AS imps,     coalesce(p.clicks, 0) AS clicks,
           coalesce(p.rev, 0.)     AS rev
    FROM series_names s
    CROSS JOIN days d
    LEFT JOIN per_day p ON p.dimension = s.dimension AND p.value = s.value AND p.day = d.day
),
long AS (
    SELECT dimension, value, day, m.1 AS metric, m.2 AS actual, m.3 AS vol
    FROM grid
    ARRAY JOIN [
        ('requests',    toNullable(toFloat64(requests)),          toFloat64(requests)),
        ('fill_rate',   if(requests > 0, fills / requests, NULL), toFloat64(requests)),
        ('render_rate', if(fills > 0, imps / fills, NULL),        toFloat64(fills)),
        ('ctr',         if(imps > 0, clicks / imps, NULL),        toFloat64(imps)),
        ('ecpm',        if(imps > 0, rev / imps * 1000, NULL),    toFloat64(imps)),
        ('revenue',     toNullable(rev),                          toFloat64(requests))
    ] AS m
),
prof AS (
    SELECT dimension, value, metric, chosen_model
    FROM rca.series_profile FINAL
    WHERE chosen_model NOT IN ('not_applicable', 'not_monitored')
),
base AS (
    SELECT l.dimension AS dimension, l.value AS value, l.metric AS metric,
           l.day AS day, l.actual AS actual, l.vol AS vol, p.chosen_model AS chosen_model
    FROM long l
    INNER JOIN prof p ON p.dimension = l.dimension AND p.value = l.value AND p.metric = l.metric
),
win AS (
    SELECT *,
        quantileExact(0.5)(actual) OVER w_naive AS e_naive,
        (quantileExact(0.75)(actual) OVER w_naive
           - quantileExact(0.25)(actual) OVER w_naive) / 1.349 AS s_naive,
        count(actual) OVER w_naive AS n_naive,
        quantileExact(0.5)(actual) OVER w_how AS e_how,
        (quantileExact(0.75)(actual) OVER w_how
           - quantileExact(0.25)(actual) OVER w_how) / 1.349 AS s_how,
        count(actual) OVER w_how AS n_how
    FROM base
    WINDOW
        w_naive AS (PARTITION BY dimension, value, metric
                    ORDER BY day ROWS BETWEEN 10 PRECEDING AND 1 PRECEDING),
        w_how   AS (PARTITION BY dimension, value, metric, toDayOfWeek(day)
                    ORDER BY day ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING)
),
arr AS (
    SELECT dimension, value, metric, any(chosen_model) AS chosen_model,
           arrayMap(t -> t.1, arraySort(t -> t.1, groupArray((day, actual)))) AS ws_arr,
           arrayMap(t -> t.2, arraySort(t -> t.1, groupArray((day, actual)))) AS vals
    FROM base
    GROUP BY dimension, value, metric
),
farr AS (
    SELECT dimension, value, metric, chosen_model, ws_arr,
           arrayReduce('medianExact', arrayFilter(v -> isNotNull(v), vals)) AS med,
           arrayMap(v -> toFloat64(coalesce(v, med, 0.)), vals) AS x
    FROM arr
),
stl AS (
    SELECT dimension, value, metric, ws_arr, x, med,
           seriesDecomposeSTL(x, 7) AS d
    FROM farr
),
stl_stats AS (
    SELECT dimension, value, metric, ws_arr, d,
           1.4826 * arrayReduce('medianExact',
               arrayMap(r -> abs(r - arrayReduce('medianExact', d[3])), d[3])) AS s_stl,
           toFloat64(med) AS e_flat,
           1.4826 * arrayReduce('medianExact',
               arrayMap(v -> abs(v - toFloat64(med)), x)) AS s_flat
    FROM stl
),
stl_rows AS (
    SELECT dimension, value, metric, ws AS day,
           toFloat64(seas) + toFloat64(tr) AS e_stl,
           s_stl, e_flat, s_flat
    FROM stl_stats
    ARRAY JOIN ws_arr AS ws, d[1] AS seas, d[2] AS tr
),
scored AS (
    SELECT w.dimension AS dimension, w.value AS value, w.metric AS metric,
           w.chosen_model AS chosen_model, w.day AS day,
           w.actual AS actual, w.vol AS vol,
           w.e_naive AS e_naive,
           if(w.n_naive >= 7,
              (w.actual - w.e_naive) / greatest(w.s_naive, 0.005 * abs(w.e_naive), 1e-9),
              NULL) AS z_naive,
           w.e_how AS e_how,
           if(w.n_how >= 3,
              (w.actual - w.e_how) / greatest(w.s_how, 0.005 * abs(w.e_how), 1e-9),
              NULL) AS z_how,
           s.e_stl AS e_stl,
           (w.actual - s.e_stl) / greatest(s.s_stl, 0.005 * abs(s.e_stl), 1e-9) AS z_stl,
           s.e_flat AS e_flat,
           (w.actual - s.e_flat) / greatest(s.s_flat, 0.005 * abs(s.e_flat), 1e-9) AS z_flat,
           -- daily primary for seasonal series = the SLOT MEDIAN, not STL: with only
           -- ~5 samples per weekday, one huge outlier (Jun 21) corrupts the STL
           -- seasonal component and manufactures false positives on its siblings;
           -- a +/-2-week same-weekday median shrugs it off. STL stays in the ensemble.
           if(w.chosen_model = 'flat_robust', s.e_flat,
              if(z_how IS NOT NULL, w.e_how, s.e_stl)) AS e_primary,
           if(w.chosen_model = 'flat_robust',
              (w.actual - s.e_flat) / greatest(s.s_flat, 0.005 * abs(s.e_flat), 1e-9),
              coalesce(z_how,
                       (w.actual - s.e_stl) / greatest(s.s_stl, 0.005 * abs(s.e_stl), 1e-9)))
              AS z_primary
    FROM win w
    INNER JOIN stl_rows s ON s.dimension = w.dimension AND s.value = w.value
                         AND s.metric = w.metric AND s.day = w.day
)
SELECT dimension, value, metric, chosen_model,
       toDateTime(day, 'UTC') AS window_start, actual, vol,
       e_naive, z_naive, NULL AS e_hod, NULL AS z_hod, e_how, z_how,
       e_stl, z_stl, e_flat, z_flat, e_primary, z_primary
FROM scored
WHERE coalesce(abs(z_primary), 0) >= {pre_z:Float64}
   OR coalesce(abs(z_naive), 0) >= {naive_z:Float64}
ORDER BY dimension, value, metric, window_start
