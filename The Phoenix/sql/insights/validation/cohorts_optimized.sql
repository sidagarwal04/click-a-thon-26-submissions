-- OPTIMIZED side of the content_entry_cohorts gate. Reads the cohort table and nothing else.
-- Same columns, same order, same composite key as cohorts_reference.sql.
--
-- The retention_* ratios are deliberately NOT compared. They are the counts above divided by
-- entered_sessions, so comparing them adds no information and subtracts some: two Float32
-- values that are arithmetically identical can render differently, and the diff would report a
-- failure that is a formatting artifact. The counts are the facts; the ratios are a
-- presentation of them, and if the counts match the ratios cannot disagree.
SELECT
    concat(toString(cohort_minute), '|', toString(content_id), '|',
           platform, '|', country, '|', app_version, '|', video_type) AS cohort_key,
    toUInt32(argMax(entered_sessions, version)) AS entered_sessions,
    toUInt32(argMax(active_after_1m, version))  AS active_after_1m,
    toUInt32(argMax(active_after_5m, version))  AS active_after_5m,
    toUInt32(argMax(active_after_10m, version)) AS active_after_10m,
    toUInt32(argMax(active_after_15m, version)) AS active_after_15m,
    toString(round(argMax(avg_active_seconds, version), 4))    AS avg_active_seconds,
    toString(toUInt32(argMax(median_active_seconds, version))) AS median_active_seconds,
    toString(toUInt32(argMax(p90_active_seconds, version)))    AS p90_active_seconds
FROM content_entry_cohorts
WHERE cohort_minute < {frozen_before:String}
GROUP BY cohort_key
ORDER BY cohort_key;
