-- Hourly scoring: for every monitored (series, metric, hour), actual vs expected
-- under the full model ensemble. The sweep classifies candidates by model
-- DISAGREEMENT (see ARCHITECTURE.md):
--   naive   trailing-72h median (deliberately seasonality-blind — the foil)
--   hod     same hour-of-day, ±4 neighboring days
--   how     same hour-of-week slot, ±2 neighboring weeks (two-sided: sweep mode)
--   stl     STL residual (period 24 or 168 per series_profile) — trend-aware
--   flat    whole-series robust median/MAD (primary for non-seasonal ratio metrics)
-- Robust sigmas: IQR/1.349 (windows) or 1.4826*MAD (series) — the outlier being
-- hunted must not inflate its own yardstick.
--
-- Output is prefiltered to hours that could matter: |z_primary| >= {pre_z} (candidate
-- + merge context) OR |z_naive| >= {naive_z} (seasonality-trap candidates, which by
-- definition clear the seasonal models and exist only to be ruled out).

WITH
bounds AS (
    SELECT min(window_start) AS min_h, max(window_start) AS max_h
    FROM rca.metrics_hourly_by_dim
),
hours AS (
    SELECT arrayJoin(arrayMap(i -> min_h + toIntervalHour(i),
                              range(toUInt32(dateDiff('hour', min_h, max_h) + 1)))) AS window_start
    FROM bounds
),
per_hour AS (
    SELECT dimension, value, window_start,
           sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS imps,
           sum(clicks) AS clicks, sum(revenue) AS rev
    FROM rca.metrics_hourly_by_dim
    WHERE dimension NOT IN ('app_id', 'advertiser_id')
    GROUP BY dimension, value, window_start
),
series_names AS (SELECT DISTINCT dimension, value FROM per_hour),
grid AS (
    SELECT s.dimension AS dimension, s.value AS value, h.window_start AS window_start,
           coalesce(p.requests, 0) AS requests, coalesce(p.fills, 0) AS fills,
           coalesce(p.imps, 0)     AS imps,     coalesce(p.clicks, 0) AS clicks,
           coalesce(p.rev, 0.)     AS rev
    FROM series_names s
    CROSS JOIN hours h
    LEFT JOIN per_hour p ON p.dimension = s.dimension AND p.value = s.value
                        AND p.window_start = h.window_start
),
long AS (
    SELECT dimension, value, window_start, m.1 AS metric, m.2 AS actual, m.3 AS vol
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
           l.window_start AS window_start, l.actual AS actual, l.vol AS vol,
           p.chosen_model AS chosen_model
    FROM long l
    INNER JOIN prof p ON p.dimension = l.dimension AND p.value = l.value AND p.metric = l.metric
),
-- window-function models (aggregates skip NULL actuals inside frames)
win AS (
    SELECT *,
        quantileExact(0.5)(actual) OVER w_naive AS e_naive,
        (quantileExact(0.75)(actual) OVER w_naive
           - quantileExact(0.25)(actual) OVER w_naive) / 1.349 AS s_naive,
        count(actual) OVER w_naive AS n_naive,
        quantileExact(0.5)(actual) OVER w_hod AS e_hod,
        (quantileExact(0.75)(actual) OVER w_hod
           - quantileExact(0.25)(actual) OVER w_hod) / 1.349 AS s_hod,
        count(actual) OVER w_hod AS n_hod,
        quantileExact(0.5)(actual) OVER w_how AS e_how,
        (quantileExact(0.75)(actual) OVER w_how
           - quantileExact(0.25)(actual) OVER w_how) / 1.349 AS s_how,
        count(actual) OVER w_how AS n_how
    FROM base
    WINDOW
        w_naive AS (PARTITION BY dimension, value, metric
                    ORDER BY window_start ROWS BETWEEN 72 PRECEDING AND 1 PRECEDING),
        w_hod   AS (PARTITION BY dimension, value, metric, toHour(window_start)
                    ORDER BY window_start ROWS BETWEEN 4 PRECEDING AND 4 FOLLOWING),
        w_how   AS (PARTITION BY dimension, value, metric,
                                 toDayOfWeek(window_start), toHour(window_start)
                    ORDER BY window_start ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING)
),
-- array models: STL (both periods; the profile picks which counts) + whole-series flat
arr AS (
    SELECT dimension, value, metric, any(chosen_model) AS chosen_model,
           arrayMap(t -> t.1, arraySort(t -> t.1, groupArray((window_start, actual)))) AS ws_arr,
           arrayMap(t -> t.2, arraySort(t -> t.1, groupArray((window_start, actual)))) AS vals
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
           if(chosen_model = 'stl_24',
              seriesDecomposeSTL(x, 24),
              seriesDecomposeSTL(x, 168)) AS d
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
    -- multiple ARRAY JOIN arrays align by position: ws_arr[i] <-> d[1][i] <-> d[2][i]
    SELECT dimension, value, metric, ws AS window_start,
           toFloat64(seas) + toFloat64(tr) AS e_stl,
           s_stl, e_flat, s_flat
    FROM stl_stats
    ARRAY JOIN ws_arr AS ws, d[1] AS seas, d[2] AS tr
),
-- sigma floors: max(model sigma, 0.5% of expected) — a near-constant frame must not
-- manufacture million-z outliers. Frame-support guards: a model with too few points
-- (or only itself, at series edges) abstains (NULL) instead of voting.
scored AS (
    SELECT w.dimension AS dimension, w.value AS value, w.metric AS metric,
           w.chosen_model AS chosen_model, w.window_start AS window_start,
           w.actual AS actual, w.vol AS vol,
           w.e_naive AS e_naive,
           if(w.n_naive >= 24,
              (w.actual - w.e_naive) / greatest(w.s_naive, 0.005 * abs(w.e_naive), 1e-9),
              NULL) AS z_naive,
           w.e_hod AS e_hod,
           if(w.n_hod >= 5,
              (w.actual - w.e_hod) / greatest(w.s_hod, 0.005 * abs(w.e_hod), 1e-9),
              NULL) AS z_hod,
           w.e_how AS e_how,
           if(w.n_how >= 3,
              (w.actual - w.e_how) / greatest(w.s_how, 0.005 * abs(w.e_how), 1e-9),
              NULL) AS z_how,
           s.e_stl AS e_stl,
           (w.actual - s.e_stl) / greatest(s.s_stl, 0.005 * abs(s.e_stl), 1e-9) AS z_stl,
           s.e_flat AS e_flat,
           (w.actual - s.e_flat) / greatest(s.s_flat, 0.005 * abs(s.e_flat), 1e-9) AS z_flat,
           if(w.chosen_model = 'flat_robust', s.e_flat, s.e_stl) AS e_primary,
           if(w.chosen_model = 'flat_robust',
              (w.actual - s.e_flat) / greatest(s.s_flat, 0.005 * abs(s.e_flat), 1e-9),
              (w.actual - s.e_stl) / greatest(s.s_stl, 0.005 * abs(s.e_stl), 1e-9)) AS z_primary
    FROM win w
    INNER JOIN stl_rows s ON s.dimension = w.dimension AND s.value = w.value
                         AND s.metric = w.metric AND s.window_start = w.window_start
)
SELECT dimension, value, metric, chosen_model, window_start, actual, vol,
       e_naive, z_naive, e_hod, z_hod, e_how, z_how, e_stl, z_stl, e_flat, z_flat,
       e_primary, z_primary
FROM scored
WHERE coalesce(abs(z_primary), 0) >= {pre_z:Float64}
   OR coalesce(abs(z_naive), 0) >= {naive_z:Float64}
ORDER BY dimension, value, metric, window_start
