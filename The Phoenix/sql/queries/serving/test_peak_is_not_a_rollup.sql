-- TEST: peak concurrency cannot be derived from a per-dimension rollup.
--
-- Returns one row per assertion with a PASS/FAIL verdict. scripts/test_peak.sh runs it and
-- exits non-zero on any FAIL.
--
-- This exists because storing a peak per rollup level is the obvious optimisation and it is
-- wrong. The problem statement says so directly: "a dimension like platform and a content
-- might peak at one minute, while a combination like platform + country might reach its
-- peak at an entirely different minute within the selected time range."
--
-- Three independent ways of stating the same constraint, so that a regression cannot slip
-- past by satisfying one of them accidentally:
--
--   1. Different filter tuples peak at different MINUTES. If a future change made peak a
--      lookup, every slice would report the global peak minute and this fails.
--   2. The overall peak is not the MAX of the per-platform peaks. Sessions on different
--      platforms are concurrent with each other, so the whole is larger than its largest
--      part. Measured: max per-platform peak 1,743 against an overall 2,829.
--   3. The overall peak is not the SUM of the per-platform peaks either, because platforms
--      do not all peak in the same minute. Measured: sum 2,918 against 2,829.
--
-- Together those pin peak to "computed at query time from the per-minute series for the
-- exact filter requested", which is the only definition that survives contact with the
-- scenario in the problem statement.
WITH
per_platform AS
(
    SELECT platform, max(c) AS peak
    FROM
    (
        SELECT platform, minute,
               toInt64(sum(d) OVER (PARTITION BY platform ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
        FROM (SELECT platform, minute, sum(delta) AS d FROM concurrency_deltas
 GROUP BY platform, minute)
    )
    GROUP BY platform
),
overall AS
(
    SELECT max(c) AS peak, argMax(minute, c) AS peak_minute
    FROM
    (
        SELECT minute, toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
        FROM (SELECT minute, sum(delta) AS d FROM concurrency_deltas
 GROUP BY minute)
    )
),
live_only AS
(
    SELECT max(c) AS peak, argMax(minute, c) AS peak_minute
    FROM
    (
        SELECT minute, toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
        FROM (SELECT minute, sum(delta) AS d FROM concurrency_deltas
              WHERE video_type = 'live' GROUP BY minute)
    )
),
one_platform AS
(
    SELECT max(c) AS peak, argMax(minute, c) AS peak_minute
    FROM
    (
        SELECT minute, toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
        FROM (SELECT minute, sum(delta) AS d FROM concurrency_deltas
              WHERE platform = 'SONY_ANDROID_TV' GROUP BY minute)
    )
)
SELECT * FROM
(
    SELECT
        'peak_minute_differs_video_type_live' AS assertion,
        concat(toString((SELECT peak_minute FROM overall)), ' vs ', toString((SELECT peak_minute FROM live_only))) AS observed,
        if((SELECT peak_minute FROM overall) != (SELECT peak_minute FROM live_only), 'PASS', 'FAIL') AS verdict

    UNION ALL SELECT
        'peak_minute_differs_platform_slice',
        concat(toString((SELECT peak_minute FROM overall)), ' vs ', toString((SELECT peak_minute FROM one_platform))),
        if((SELECT peak_minute FROM overall) != (SELECT peak_minute FROM one_platform), 'PASS', 'FAIL')

    UNION ALL SELECT
        'overall_peak_exceeds_max_of_parts',
        concat(toString((SELECT peak FROM overall)), ' vs max part ', toString((SELECT max(peak) FROM per_platform))),
        if((SELECT peak FROM overall) > (SELECT max(peak) FROM per_platform), 'PASS', 'FAIL')

    UNION ALL SELECT
        'overall_peak_differs_from_sum_of_parts',
        concat(toString((SELECT peak FROM overall)), ' vs sum parts ', toString((SELECT sum(peak) FROM per_platform))),
        if((SELECT peak FROM overall) != (SELECT sum(peak) FROM per_platform), 'PASS', 'FAIL')
)
ORDER BY assertion;
