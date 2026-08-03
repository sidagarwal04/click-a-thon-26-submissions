-- REFERENCE for content_entry_cohorts.
--
-- Recomputed from foreground_intervals and raw_events, NOT from session_insight_facts, which is
-- what the pipeline reads. That is the whole value of this file: reading the same table the
-- refresh reads and applying the same GROUP BY would check nothing except that ClickHouse can
-- add. Going back to the intervals re-derives first_active_at, active_seconds, the four
-- retention flags and the dimension attribution independently of the facts table, so an error
-- in the refresh has somewhere to show up.
--
-- Still the WEAKER kind of reference and the harness labels it so: it shares an engine and it
-- shares the interval derivation. What it cannot catch is an error in foreground_intervals
-- itself, and it does not need to, because session_insight_facts is already validated against a
-- second implementation in a second engine at zero diffs `[V:insight_parity_session_facts]`.
--
-- The first column is a composite key because the harness diffs on field one and a cohort is
-- identified by six columns, not one.
WITH
    iv AS
    (
        SELECT
            video_session_id AS sid,
            min(interval_start) AS first_active_at,
            toUInt32(sum(dateDiff('second', interval_start, interval_end))) AS active_seconds
        FROM foreground_intervals
        GROUP BY video_session_id
    ),
    ret AS
    (
        SELECT
            f.sid AS sid,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(1)  AND i.interval_end > f.first_active_at + toIntervalMinute(1),  1, 0)) AS a1,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(5)  AND i.interval_end > f.first_active_at + toIntervalMinute(5),  1, 0)) AS a5,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(10) AND i.interval_end > f.first_active_at + toIntervalMinute(10), 1, 0)) AS a10,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(15) AND i.interval_end > f.first_active_at + toIntervalMinute(15), 1, 0)) AS a15
        FROM iv AS f
        INNER JOIN foreground_intervals AS i ON i.video_session_id = f.sid
        GROUP BY f.sid
    ),
    -- Dimensions from the session's FIRST event, re-deriving D5 rather than trusting the copy
    -- of it that the facts table stores.
    dims AS
    (
        SELECT
            video_session_id AS sid,
            argMin(content_id, event_timestamp)  AS content_id,
            argMin(platform, event_timestamp)    AS platform,
            argMin(country, event_timestamp)     AS country,
            argMin(app_version, event_timestamp) AS app_version
        FROM raw_events
        GROUP BY video_session_id
    )
SELECT
    concat(toString(toStartOfMinute(iv.first_active_at)), '|', toString(d.content_id), '|',
           d.platform, '|', d.country, '|', d.app_version, '|', ifNull(c.video_type, '')) AS cohort_key,
    toUInt32(count())    AS entered_sessions,
    toUInt32(sum(r.a1))  AS active_after_1m,
    toUInt32(sum(r.a5))  AS active_after_5m,
    toUInt32(sum(r.a10)) AS active_after_10m,
    toUInt32(sum(r.a15)) AS active_after_15m,
    toString(round(avg(iv.active_seconds), 4))          AS avg_active_seconds,
    toString(quantileExact(0.5)(iv.active_seconds))     AS median_active_seconds,
    toString(quantileExact(0.9)(iv.active_seconds))     AS p90_active_seconds
FROM iv
INNER JOIN ret  AS r ON r.sid = iv.sid
INNER JOIN dims AS d ON d.sid = iv.sid
-- LEFT ANY JOIN, not LEFT JOIN, per clickhouse-best-practices rule query-join-use-any. This is a
-- one-row-per-key lookup, and `content` is a ReplacingMergeTree: duplicate content_id rows exist
-- between a reload and the merge that collapses them, and a plain LEFT JOIN would fan out and
-- multiply every row that matched. Measured 0 duplicates today, so this closes a latent hazard
-- rather than a live defect.
LEFT ANY JOIN content AS c ON c.content_id = d.content_id
WHERE iv.first_active_at < {frozen_before:String}
GROUP BY cohort_key
ORDER BY cohort_key;
