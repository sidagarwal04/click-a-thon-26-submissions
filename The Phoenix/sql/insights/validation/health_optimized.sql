-- OPTIMIZED side of the playback_health_minute gate. Reads the health table and nothing else.
-- Same columns, same order, same composite key as health_reference.sql.
--
-- Rows where all three counted columns are zero are excluded. The pipeline writes a row for
-- every minute that has ANY activity, including minutes with active sessions and no trouble at
-- all, which is the right thing for a dashboard and the wrong thing for this comparison: the
-- reference is keyed on error and exit minutes only, so those healthy rows would all report as
-- unexpected keys. The filter is on the numerators the two sides share, not on the denominator.
SELECT
    concat(toString(minute), '|', toString(content_id), '|', platform, '|', country,
           '|', app_version, '|', video_type) AS health_key,
    toUInt32(argMax(video_error_sessions, version))       AS video_error_sessions,
    toUInt32(argMax(heartbeat_timeout_sessions, version)) AS heartbeat_timeout_sessions,
    toUInt32(argMax(abandoned_sessions, version))         AS abandoned_sessions
FROM playback_health_minute
WHERE minute < {frozen_before:String}
GROUP BY health_key
HAVING video_error_sessions > 0 OR heartbeat_timeout_sessions > 0 OR abandoned_sessions > 0
ORDER BY health_key;
