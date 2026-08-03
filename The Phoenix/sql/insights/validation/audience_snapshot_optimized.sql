-- OPTIMIZED side of the audience_minute_snapshot gate. Reads the snapshot and nothing else.
--
-- Emits the same three columns as audience_snapshot_reference.sql, in the same order, so the
-- two diff line by line.
--
-- SUMMING ACROSS DIMENSION TUPLES IS VALID HERE, and it is worth saying why rather than leaving
-- a reader to assume it. A session's dimensions are taken from its FIRST event and held constant
-- (D5), so a session belongs to exactly one tuple and summing per-tuple session counts across
-- tuples cannot count it twice. The same holds for users: user_minute_runs files a user under
-- the dimensions of their first run. If either of those rulings ever changes, this sum silently
-- starts double counting and the gate below is what will catch it.
--
-- The inner GROUP BY with argMax(version) dedupes the ReplacingMergeTree without FINAL, the same
-- pattern the benchmark queries use.
SELECT
    toString(minute)                   AS minute,
    toInt64(sum(concurrent_sessions))  AS sessions,
    toInt64(sum(concurrent_users))     AS users
FROM
(
    SELECT
        minute, content_id, platform, country, video_type, app_version,
        argMax(concurrent_sessions, version) AS concurrent_sessions,
        argMax(concurrent_users, version)    AS concurrent_users
    FROM audience_minute_snapshot
    WHERE minute < {frozen_before:String}
    GROUP BY minute, content_id, platform, country, video_type, app_version
)
GROUP BY minute
HAVING sessions > 0
ORDER BY minute;
