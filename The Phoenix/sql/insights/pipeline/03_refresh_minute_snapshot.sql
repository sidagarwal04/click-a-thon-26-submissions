-- INSIGHTS PIPELINE: rebuild audience_minute_snapshot for a window of minutes.
--
--   Parameters: tolerance_s (unused here, accepted so one driver can pass one parameter set),
--               from_ts, to_ts
--
-- Idempotent for the same reason 01 is: ReplacingMergeTree(version), a higher version per run,
-- so a second pass over the same window supersedes rather than adds.
--
-- THE COLLAPSE FILTER IS NOT OPTIONAL. session_minute_runs and user_minute_runs are
-- CollapsingMergeTree: a re-derived session carries sign = -1 rows for what it had alongside
-- sign = +1 rows for what it has now, and both are physically present until a merge removes
-- them. Reading the table without GROUP BY ... HAVING sum(sign) > 0 counts retracted runs as
-- live ones, and the error appears only after an incremental re-derive, which is exactly when
-- nobody is looking. The delta MVs avoid this by multiplying by sign; a row-level reader has to
-- do it explicitly.
INSERT INTO audience_minute_snapshot
WITH
    parseDateTimeBestEffort({from_ts:String}) AS w_from,
    parseDateTimeBestEffort({to_ts:String})   AS w_to,
    toDateTime64(0, 3) AS epoch0,

    -- Live session runs, retractions removed.
    sruns AS
    (
        SELECT video_session_id, content_id, platform, country, video_type, app_version,
               run_start, run_end
        FROM session_minute_runs
        WHERE run_end >= w_from AND run_start < w_to
        GROUP BY video_session_id, content_id, platform, country, video_type, app_version,
                 run_start, run_end
        HAVING sum(sign) > 0
    ),
    -- One row per (session, minute it was active in). run_end is INCLUSIVE, so the duration
    -- handed to timeSlots is the difference plus one second: without the plus one, a run that
    -- starts and ends in the same minute yields no slots at all and the session vanishes from
    -- its own minute.
    smin AS
    (
        SELECT content_id, platform, country, video_type, app_version,
               video_session_id,
               arrayJoin(timeSlots(run_start,
                                   toUInt32(dateDiff('second', run_start, run_end) + 1),
                                   60)) AS minute
        FROM sruns
    ),
    sessions_per_minute AS
    (
        SELECT minute, content_id, platform, country, video_type, app_version,
               uniqExact(video_session_id) AS concurrent_sessions
        FROM smin
        WHERE minute >= w_from AND minute < w_to
        GROUP BY minute, content_id, platform, country, video_type, app_version
    ),

    -- Users, from the table where a user's overlapping sessions are ALREADY merged. Counting
    -- distinct user_id in sruns instead would count one person on two devices twice.
    uruns AS
    (
        SELECT user_id, content_id, platform, country, video_type, app_version, run_start, run_end
        FROM user_minute_runs
        WHERE run_end >= w_from AND run_start < w_to
        GROUP BY user_id, content_id, platform, country, video_type, app_version, run_start, run_end
        HAVING sum(sign) > 0
    ),
    users_per_minute AS
    (
        SELECT minute, content_id, platform, country, video_type, app_version,
               uniqExact(user_id) AS concurrent_users
        FROM
        (
            SELECT content_id, platform, country, video_type, app_version, user_id,
                   arrayJoin(timeSlots(run_start,
                                       toUInt32(dateDiff('second', run_start, run_end) + 1),
                                       60)) AS minute
            FROM uruns
        )
        WHERE minute >= w_from AND minute < w_to
        GROUP BY minute, content_id, platform, country, video_type, app_version
    ),

    -- Event counts, from the session facts rather than from raw_events, so a minute's starts
    -- and ends agree with the per-session table by construction instead of by luck. Deduped by
    -- version first: session_insight_facts is a ReplacingMergeTree too.
    facts AS
    (
        SELECT
            video_session_id,
            argMax(content_id, version)   AS content_id,
            argMax(platform, version)     AS platform,
            argMax(country, version)      AS country,
            argMax(video_type, version)   AS video_type,
            argMax(app_version, version)  AS app_version,
            argMax(session_start, version)  AS session_start,
            argMax(first_play_at, version)  AS first_play_at,
            argMax(session_end_at, version) AS session_end_at,
            argMax(background_count, version)        AS background_count,
            argMax(foreground_return_count, version) AS foreground_return_count,
            argMax(video_error_count, version)       AS video_error_count
        FROM session_insight_facts
        GROUP BY video_session_id
    ),
    starts_per_minute AS
    (
        SELECT toStartOfMinute(toDateTime(session_start)) AS minute,
               content_id, platform, country, video_type, app_version,
               count() AS session_starts
        FROM facts
        WHERE toDateTime(session_start) >= w_from AND toDateTime(session_start) < w_to
        GROUP BY minute, content_id, platform, country, video_type, app_version
    ),
    plays_per_minute AS
    (
        SELECT toStartOfMinute(toDateTime(first_play_at)) AS minute,
               content_id, platform, country, video_type, app_version,
               count() AS first_plays
        FROM facts
        WHERE first_play_at > epoch0
          AND toDateTime(first_play_at) >= w_from AND toDateTime(first_play_at) < w_to
        GROUP BY minute, content_id, platform, country, video_type, app_version
    ),
    ends_per_minute AS
    (
        SELECT toStartOfMinute(toDateTime(session_end_at)) AS minute,
               content_id, platform, country, video_type, app_version,
               count() AS session_ends
        FROM facts
        WHERE session_end_at > epoch0
          AND toDateTime(session_end_at) >= w_from AND toDateTime(session_end_at) < w_to
        GROUP BY minute, content_id, platform, country, video_type, app_version
    ),
    -- These three are per-EVENT and have no per-event table to come from other than raw_events,
    -- which a pipeline job may read even though a serving query may not.
    events_per_minute AS
    (
        SELECT
            toStartOfMinute(toDateTime(r.event_timestamp)) AS minute,
            -- Aliased explicitly. A bare `d.content_id` names the output column `d.content_id`,
            -- and the UNION and USING below both look for `content_id`, so the CTE compiles and
            -- then fails to resolve two hundred lines later.
            d.content_id  AS content_id,
            d.platform    AS platform,
            d.country     AS country,
            d.video_type  AS video_type,
            d.app_version AS app_version,
            countIf(r.event_type = 'AppForegrounded') AS foreground_entries,
            countIf(r.event_type = 'AppBackgrounded') AS background_entries,
            countIf(r.event_type = 'VideoError')      AS video_errors
        FROM raw_events AS r
        INNER JOIN facts AS d ON d.video_session_id = r.video_session_id
        WHERE toDateTime(r.event_timestamp) >= w_from AND toDateTime(r.event_timestamp) < w_to
          AND r.event_type IN ('AppForegrounded', 'AppBackgrounded', 'VideoError')
        GROUP BY minute, content_id, platform, country, video_type, app_version
    ),

    -- FULL OUTER across every contributor, because a minute can have ends and no active
    -- sessions, or errors and no starts. An INNER JOIN chain would silently drop those minutes,
    -- and the missing rows would look like quiet minutes rather than lost ones.
    keys AS
    (
        SELECT minute, content_id, platform, country, video_type, app_version FROM sessions_per_minute
        UNION DISTINCT
        SELECT minute, content_id, platform, country, video_type, app_version FROM users_per_minute
        UNION DISTINCT
        SELECT minute, content_id, platform, country, video_type, app_version FROM starts_per_minute
        UNION DISTINCT
        SELECT minute, content_id, platform, country, video_type, app_version FROM plays_per_minute
        UNION DISTINCT
        SELECT minute, content_id, platform, country, video_type, app_version FROM ends_per_minute
        UNION DISTINCT
        SELECT minute, content_id, platform, country, video_type, app_version FROM events_per_minute
    )
SELECT
    k.minute,
    k.content_id,
    ifNull(c.title, '')    AS title,
    ifNull(c.category, '') AS category,
    k.video_type,
    k.platform,
    k.country,
    k.app_version,
    toUInt32(ifNull(sp.concurrent_sessions, 0)) AS concurrent_sessions,
    toUInt32(ifNull(up.concurrent_users, 0))    AS concurrent_users,
    toUInt32(ifNull(st.session_starts, 0))      AS session_starts,
    toUInt32(ifNull(pl.first_plays, 0))         AS first_plays,
    toUInt32(ifNull(en.session_ends, 0))        AS session_ends,
    toUInt32(ifNull(ev.foreground_entries, 0))  AS foreground_entries,
    toUInt32(ifNull(ev.background_entries, 0))  AS background_entries,
    toUInt32(ifNull(ev.video_errors, 0))        AS video_errors,
    toUInt64(toUnixTimestamp64Milli(now64(3)))  AS version,
    now()                                       AS updated_at
FROM keys AS k
LEFT JOIN sessions_per_minute AS sp USING (minute, content_id, platform, country, video_type, app_version)
LEFT JOIN users_per_minute    AS up USING (minute, content_id, platform, country, video_type, app_version)
LEFT JOIN starts_per_minute   AS st USING (minute, content_id, platform, country, video_type, app_version)
LEFT JOIN plays_per_minute    AS pl USING (minute, content_id, platform, country, video_type, app_version)
LEFT JOIN ends_per_minute     AS en USING (minute, content_id, platform, country, video_type, app_version)
LEFT JOIN events_per_minute   AS ev USING (minute, content_id, platform, country, video_type, app_version)
-- LEFT ANY JOIN, not LEFT JOIN, per clickhouse-best-practices rule query-join-use-any. This is a
-- one-row-per-key lookup, and `content` is a ReplacingMergeTree: duplicate content_id rows exist
-- between a reload and the merge that collapses them, and a plain LEFT JOIN would fan out and
-- multiply every row that matched. Measured 0 duplicates today, so this closes a latent hazard
-- rather than a live defect.
LEFT ANY JOIN content             AS c  ON c.content_id = k.content_id;
