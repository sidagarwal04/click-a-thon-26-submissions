-- INSIGHTS PIPELINE: rebuild playback_health_minute for a window of minutes.
--
--   Parameters: tolerance_s, from_ts, to_ts
--
-- active_sessions comes from audience_minute_snapshot rather than being recomputed, so the
-- denominator of every rate here is by construction the same number the trend panel shows. Two
-- tables computing "active sessions" two ways is how two dashboards end up disagreeing about
-- the same minute.
INSERT INTO playback_health_minute
WITH
    {tolerance_s:UInt32} AS tol,
    parseDateTimeBestEffort({from_ts:String}) AS w_from,
    parseDateTimeBestEffort({to_ts:String})   AS w_to,

    active AS
    (
        SELECT minute, content_id, platform, country, app_version, video_type,
               argMax(concurrent_sessions, version) AS active_sessions
        FROM audience_minute_snapshot
        WHERE minute >= w_from AND minute < w_to
        GROUP BY minute, content_id, platform, country, app_version, video_type
    ),
    dims AS
    (
        SELECT video_session_id AS sid,
               argMax(content_id, version)   AS content_id,
               argMax(platform, version)     AS platform,
               argMax(country, version)      AS country,
               argMax(app_version, version)  AS app_version,
               argMax(video_type, version)   AS video_type,
               argMax(last_active_at, version) AS last_active_at,
               argMax(abandoned, version)      AS abandoned,
               argMax(timed_out, version)      AS timed_out
        FROM session_insight_facts
        GROUP BY video_session_id
    ),
    -- Distinct SESSIONS, not error events: a session throwing six errors in one minute is one
    -- unhealthy session, and counting events would make a retry loop look like an outage.
    errs AS
    (
        SELECT toStartOfMinute(toDateTime(r.event_timestamp)) AS minute,
               d.content_id AS content_id, d.platform AS platform, d.country AS country,
               d.app_version AS app_version, d.video_type AS video_type,
               uniqExact(r.video_session_id) AS video_error_sessions
        FROM raw_events AS r
        INNER JOIN dims AS d ON d.sid = r.video_session_id
        WHERE r.event_type = 'VideoError'
          AND toDateTime(r.event_timestamp) >= w_from AND toDateTime(r.event_timestamp) < w_to
        GROUP BY minute, content_id, platform, country, app_version, video_type
    ),
    -- A timeout is attributed to the minute the session STOPPED being active, which is where a
    -- dashboard looking at a concurrency drop will be looking.
    outs AS
    (
        SELECT toStartOfMinute(last_active_at) AS minute,
               content_id, platform, country, app_version, video_type,
               toUInt32(countIf(timed_out = 1))  AS heartbeat_timeout_sessions,
               toUInt32(countIf(abandoned = 1))  AS abandoned_sessions
        FROM dims
        WHERE last_active_at > toDateTime(0)
          AND last_active_at >= w_from AND last_active_at < w_to
        GROUP BY minute, content_id, platform, country, app_version, video_type
    ),
    keys AS
    (
        SELECT minute, content_id, platform, country, app_version, video_type FROM active
        UNION DISTINCT
        SELECT minute, content_id, platform, country, app_version, video_type FROM errs
        UNION DISTINCT
        SELECT minute, content_id, platform, country, app_version, video_type FROM outs
    )
SELECT
    k.minute, k.content_id, k.platform, k.country, k.app_version, k.video_type,
    toUInt32(ifNull(a.active_sessions, 0))            AS active_sessions,
    toUInt32(ifNull(e.video_error_sessions, 0))       AS video_error_sessions,
    toUInt32(ifNull(o.heartbeat_timeout_sessions, 0)) AS heartbeat_timeout_sessions,
    toUInt32(ifNull(o.abandoned_sessions, 0))         AS abandoned_sessions,
    -- greatest(active, 1) rather than a NULL rate: a minute with errors and no active sessions
    -- is possible (the error is the last thing a session does) and dividing by zero there would
    -- poison every aggregate downstream. The rate reads as the count, which is honest: one
    -- error out of an active population of zero is not a 100 percent error rate, and the count
    -- column beside it is what anyone should be reading in that case.
    toFloat32(round(ifNull(e.video_error_sessions, 0)       / greatest(ifNull(a.active_sessions, 0), 1), 6)) AS video_error_rate,
    toFloat32(round(ifNull(o.heartbeat_timeout_sessions, 0) / greatest(ifNull(a.active_sessions, 0), 1), 6)) AS heartbeat_timeout_rate,
    toFloat32(round(ifNull(o.abandoned_sessions, 0)         / greatest(ifNull(a.active_sessions, 0), 1), 6)) AS abandonment_rate,
    toUInt64(toUnixTimestamp64Milli(now64(3))) AS version,
    now()                                      AS updated_at
FROM keys AS k
LEFT JOIN active AS a USING (minute, content_id, platform, country, app_version, video_type)
LEFT JOIN errs   AS e USING (minute, content_id, platform, country, app_version, video_type)
LEFT JOIN outs   AS o USING (minute, content_id, platform, country, app_version, video_type);
