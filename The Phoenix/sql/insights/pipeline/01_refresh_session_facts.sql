-- INSIGHTS PIPELINE: rebuild session_insight_facts for the sessions a batch touched.
--
--   Parameters: tolerance_s, from_ts, to_ts
--
-- Incremental by design. `touched` is every session with an event inside [from_ts, to_ts), and
-- only those sessions are rebuilt. A full refresh is the same statement with a wide window,
-- so there is one code path rather than two that can drift.
--
-- IDEMPOTENT WITHOUT A GUARD, which is the difference between this and sql/pipeline/02. That
-- file asserts sign = +1 and APPENDS, so a second run doubles every run and derive.sh has to
-- refuse re-entry to make the corruption unreachable. Here the target is a
-- ReplacingMergeTree(version) keyed on the session, and every run stamps a higher version, so a
-- second run over the same batch supersedes rather than adds. Read with FINAL, or with any
-- aggregation that takes argMax(version).
--
-- WHY IT READS foreground_intervals RATHER THAN RE-DERIVING FROM raw_events. That table already
-- carries the validated interval boundaries: the tolerance cap, the pause ruling, and the D8
-- end bound. Re-deriving them here would be a second implementation of the state machine inside
-- the product, which is the one place a second implementation is not wanted. The independent
-- implementation belongs in the validation pair, and it is there.
--
-- BOUNDARY CONVENTION, repeated verbatim from the DDL and from the ground truth:
--   active_seconds = sum over foreground intervals of dateDiff('second', start, end)
-- Plain dateDiff. Not the `- 1` the concurrency oracle applies, which is about minute occupancy
-- and would be wrong here once per interval.
INSERT INTO session_insight_facts
WITH
    {tolerance_s:UInt32} AS tol,
    -- Far-future sentinel for `first X` over a set that may be empty. min(if(...)) and not
    -- minIf(...): on this server the -If combinator over a possibly-empty set yields a Variant
    -- with no common supertype for the comparison that follows, which fails to compile with
    -- NO_COMMON_TYPE. Same workaround, same reason, as serving/average_definitions.sql.
    toDateTime64('2100-01-01 00:00:00', 3) AS never,
    toDateTime64(0, 3) AS epoch0,

    touched AS
    (
        SELECT DISTINCT video_session_id
        FROM raw_events
        WHERE event_timestamp >= parseDateTimeBestEffort({from_ts:String})
          AND event_timestamp <  parseDateTimeBestEffort({to_ts:String})
    ),

    -- Everything derivable by counting events. Dimensions come from the session's FIRST event
    -- and are held constant, matching D5 and sql/pipeline/01_derive_intervals.sql: 95 sessions
    -- report more than one platform and 120 more than one user_id, and holding them constant is
    -- what keeps session-to-dimension one to one.
    ev AS
    (
        SELECT
            r.video_session_id                              AS sid,
            argMin(r.user_id, r.event_timestamp)            AS user_id,
            argMin(r.content_id, r.event_timestamp)         AS content_id,
            argMin(r.platform, r.event_timestamp)           AS platform,
            argMin(r.country, r.event_timestamp)            AS country,
            argMin(r.app_version, r.event_timestamp)        AS app_version,
            min(r.event_timestamp)                          AS first_event_at,
            max(r.event_timestamp)                          AS last_event_at,
            min(if(r.event_type = 'VideoPlay', r.event_timestamp, never))       AS first_play_raw,
            -- LAST end, per D13. max over an empty set is epoch 0, which is the sentinel, so no
            -- guard is needed in this direction.
            max(if(r.event_type = 'VideoSessionEnd', r.event_timestamp, epoch0)) AS last_end,
            min(if(r.event_type = 'VideoSessionEnd', r.event_timestamp, never))  AS first_end_raw,
            -- If the LAST reactivating event is after the FIRST end, then some reactivating
            -- event arrived after that end. One aggregate answers an existence question.
            max(if(r.event_type IN ('VideoSessionStart', 'VideoPlay', 'AppForegrounded')
                   OR (r.event_type = 'VideoHeartbeat' AND r.event IN ('resume', 'speed-resume', 'AdResume')),
                   r.event_timestamp, epoch0))              AS last_reactivating,
            countIf(r.event_type = 'AppBackgrounded')       AS background_count,
            countIf(r.event_type = 'AppForegrounded')       AS foreground_return_count,
            countIf(r.event_type = 'VideoHeartbeat' AND r.event IN ('pause', 'speed-pause', 'AdPause'))     AS pause_count,
            countIf(r.event_type = 'VideoHeartbeat' AND r.event IN ('resume', 'speed-resume', 'AdResume'))  AS resume_count,
            countIf(r.event_type = 'VideoHeartbeat')        AS heartbeat_count,
            countIf(r.event_type = 'VideoError')            AS video_error_count
        FROM raw_events AS r
        INNER JOIN touched AS t ON r.video_session_id = t.video_session_id
        GROUP BY r.video_session_id
    ),

    iv AS
    (
        SELECT
            i.video_session_id AS sid,
            toUInt32(sum(dateDiff('second', i.interval_start, i.interval_end))) AS active_seconds,
            toUInt16(count())                                                   AS active_interval_count,
            min(i.interval_start)                                               AS first_active_at,
            max(i.interval_end)                                                 AS last_active_at,
            -- The LAST interval, by start. Closed by silence if it ran the full tolerance;
            -- an interval clipped by the session end is shorter and is not a timeout.
            argMax(dateDiff('second', i.interval_start, i.interval_end), i.interval_start) AS last_interval_seconds
        FROM foreground_intervals AS i
        INNER JOIN touched AS t ON i.video_session_id = t.video_session_id
        GROUP BY i.video_session_id
    ),

    -- Retention is evaluated at an INSTANT, not over a span: was there a foreground interval
    -- covering first_active_at + N minutes. A session that has not ended but is backgrounded at
    -- the checkpoint is NOT retained, which is the distinction the plan's Phase 5 gate calls out.
    -- max(if(...)) rather than an -If combinator, for the NO_COMMON_TYPE reason above.
    ret AS
    (
        SELECT
            f.sid AS sid,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(1)  AND i.interval_end > f.first_active_at + toIntervalMinute(1),  1, 0)) AS active_after_1m,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(5)  AND i.interval_end > f.first_active_at + toIntervalMinute(5),  1, 0)) AS active_after_5m,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(10) AND i.interval_end > f.first_active_at + toIntervalMinute(10), 1, 0)) AS active_after_10m,
            max(if(i.interval_start <= f.first_active_at + toIntervalMinute(15) AND i.interval_end > f.first_active_at + toIntervalMinute(15), 1, 0)) AS active_after_15m
        FROM iv AS f
        INNER JOIN foreground_intervals AS i ON i.video_session_id = f.sid
        GROUP BY f.sid
    )
SELECT
    ev.sid                                          AS video_session_id,
    ev.user_id,
    ev.content_id,
    -- LEFT, so a session whose content_id is missing from the catalogue is still a session:
    -- losing it would understate every insight, the same reasoning as 01_derive_intervals.sql.
    -- ANY, so the lookup cannot fan out. Those are two independent choices and the join below
    -- makes both; 01_derive_intervals.sql makes only the first, which is flagged in the audit.
    c.title                                         AS title,
    c.category                                      AS category,
    c.video_type                                    AS video_type,
    ev.platform,
    ev.country,
    ev.app_version,

    ev.first_event_at                               AS session_start,
    if(ev.first_play_raw = never, epoch0, ev.first_play_raw) AS first_play_at,
    ev.last_end                                     AS session_end_at,
    iv.first_active_at,
    iv.last_active_at,

    ifNull(iv.active_seconds, 0)                    AS active_seconds,
    ifNull(iv.active_interval_count, 0)             AS active_interval_count,

    toUInt16(ev.background_count)                   AS background_count,
    toUInt16(ev.foreground_return_count)            AS foreground_return_count,
    toUInt16(ev.pause_count)                        AS pause_count,
    toUInt16(ev.resume_count)                       AS resume_count,
    toUInt32(ev.heartbeat_count)                    AS heartbeat_count,
    toUInt16(ev.video_error_count)                  AS video_error_count,

    toUInt8(ev.heartbeat_count > 0)                 AS reached_first_heartbeat,

    toUInt8(ifNull(ret.active_after_1m, 0))         AS active_after_1m,
    toUInt8(ifNull(ret.active_after_5m, 0))         AS active_after_5m,
    toUInt8(ifNull(ret.active_after_10m, 0))        AS active_after_10m,
    toUInt8(ifNull(ret.active_after_15m, 0))        AS active_after_15m,

    toUInt8(ev.last_end > epoch0)                   AS ended_normally,
    toUInt8(ev.last_end = epoch0)                   AS abandoned,
    toUInt8(ifNull(iv.last_interval_seconds, -1) = toInt64(tol)) AS timed_out,
    toUInt8(ev.first_end_raw < never AND ev.last_reactivating > ev.first_end_raw) AS reopened_after_end,

    ev.first_event_at,
    ev.last_event_at,

    toUInt64(toUnixTimestamp64Milli(now64(3)))      AS version,
    now()                                           AS updated_at
FROM ev
LEFT JOIN iv  ON iv.sid  = ev.sid
LEFT JOIN ret ON ret.sid = ev.sid
-- LEFT ANY JOIN, not LEFT JOIN, per clickhouse-best-practices rule query-join-use-any. This is a
-- one-row-per-key lookup, and `content` is a ReplacingMergeTree: duplicate content_id rows exist
-- between a reload and the merge that collapses them, and a plain LEFT JOIN would fan out and
-- multiply every row that matched. Measured 0 duplicates today, so this closes a latent hazard
-- rather than a live defect.
LEFT ANY JOIN content AS c ON c.content_id = ev.content_id;
