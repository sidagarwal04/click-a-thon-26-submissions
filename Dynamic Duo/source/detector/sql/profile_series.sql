-- Series profiler: measure each monitored series' structure — nothing assumed.
-- One pass over the rollup; per (dimension, value, metric):
--   fft_period            dominant period the data itself reports (seriesPeriodDetectFFT)
--   acf_24 / acf_168      autocorrelation at daily / weekly lag
--   seasonal_strength_*   STL variance share: 1 - Var(resid)/Var(seasonal+resid)
--   trend_slope           % per week, from the STL-168 trend component
--   median_hourly_volume  denominator volume (floor gate for standalone monitoring)
--
-- Gap handling: series are evaluated on a full hourly grid (missing hours -> zero
-- counts); ratio metrics get NULL on zero denominators, filled with the series
-- median so STL/FFT see a defined value — such hours can never *flag* anyway
-- (volume gate), they just must not distort the decomposition.

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
    WHERE dimension NOT IN ('app_id', 'advertiser_id')   -- entities: below floor by construction
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
    SELECT dimension, value, window_start, m.1 AS metric, m.2 AS raw_val, m.3 AS vol
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
arr AS (
    SELECT dimension, value, metric,
           arrayMap(t -> t.2, arraySort(t -> t.1, groupArray((window_start, raw_val)))) AS vals,
           arrayMap(t -> t.2, arraySort(t -> t.1, groupArray((window_start, vol))))     AS vols,
           count() AS n_hours
    FROM long
    GROUP BY dimension, value, metric
),
filled AS (
    SELECT dimension, value, metric, n_hours, vols,
           arrayReduce('medianExact', arrayFilter(v -> isNotNull(v), vals)) AS med,
           arrayMap(v -> toFloat64(coalesce(v, med, 0.)), vals)               AS x
    FROM arr
    WHERE length(arrayFilter(v -> isNotNull(v), vals)) >= {min_nonnull:UInt32}
),
stl AS (
    SELECT dimension, value, metric, n_hours, vols, x,
           seriesDecomposeSTL(x, 24)  AS d24,
           seriesDecomposeSTL(x, 168) AS d168
    FROM filled
)
SELECT
    dimension,
    value,
    metric,
    n_hours,
    arrayReduce('medianExact', vols) AS median_hourly_volume,
    seriesPeriodDetectFFT(x)         AS fft_period,
    arrayReduce('corr', arraySlice(x, 25),  arraySlice(x, 1, length(x) - 24))  AS acf_24,
    arrayReduce('corr', arraySlice(x, 169), arraySlice(x, 1, length(x) - 168)) AS acf_168,
    greatest(0., 1 - arrayReduce('varPop', d24[3])
                    / nullIf(arrayReduce('varPop', arrayMap((s, r) -> s + r, d24[1], d24[3])), 0))
        AS seasonal_strength_24,
    greatest(0., 1 - arrayReduce('varPop', d168[3])
                    / nullIf(arrayReduce('varPop', arrayMap((s, r) -> s + r, d168[1], d168[3])), 0))
        AS seasonal_strength_168,
    arrayReduce('simpleLinearRegression',
                arrayMap(i -> toFloat64(i), range(length(x))), d168[2]).1
        * 168 / nullIf(arrayReduce('avg', x), 0) * 100
        AS trend_slope
FROM stl
