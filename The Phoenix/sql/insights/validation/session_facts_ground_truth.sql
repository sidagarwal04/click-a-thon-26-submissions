-- GROUND TRUTH for session_insight_facts. Deliberately slow, obviously correct.
--
-- Runs in `clickhouse local` over the raw CSV via scripts/oracle.sh. Two engines, two
-- implementations, one answer: the state machine below is written out AGAIN rather than reading
-- the event_state view, for the same reason sql/queries/validation/oracle_concurrency.sql does
-- it. A specification that imports the implementation cannot catch the implementation's bugs.
--
-- The optimized side reads foreground_intervals, which is where the tolerance cap, the pause
-- ruling and the D8 end bound already live. This side re-derives all three from events.
--
-- TWO CONVENTIONS THAT MUST MATCH THE OPTIMIZED SIDE EXACTLY, and both are easy to get wrong:
--
--   1. DURATION IS PLAIN dateDiff. The concurrency oracle subtracts one second inside
--      timeSlots because minute OCCUPANCY is half-open. Summed duration is a different
--      question and that subtraction would be wrong here, once per interval. A mismatch shows
--      up as active_seconds differing by exactly the interval count, which reads like a
--      rounding artifact and is not.
--
--   2. INTERVAL BOUNDS TRUNCATE TO WHOLE SECONDS. foreground_intervals stores DateTime, so the
--      pipeline applies toDateTime() to both ends AFTER computing them at millisecond
--      precision. This does the same, in the same order. Truncating before the least() would
--      move boundaries by up to a second on sessions with sub-second events.
--
-- Parameters: tolerance_s, pause_inactive. The retention checkpoints are literals because they
-- are definitional, not tunable.
WITH
    {tolerance_s:UInt32}  AS tol,
    {pause_inactive:UInt8} AS pause_off,
    toDateTime64('2100-01-01 00:00:00', 3) AS never,
    toDateTime64(0, 3) AS epoch0,

    collapsed AS
    (
        -- One row per (session, millisecond). min() skips NULLs, so a decisive event beats
        -- simultaneous telemetry and a close beats an open at the same instant.
        SELECT
            video_session_id,
            ts,
            min(cls)    AS cls,
            max(is_end) AS is_end
        FROM
        (
            SELECT
                video_session_id,
                event_timestamp AS ts,
                event_type = 'VideoSessionEnd' AS is_end,
                multiIf(
                    event_type IN ('AppBackgrounded', 'VideoSessionEnd', 'VideoError'), 0,
                    pause_off AND event_type = 'VideoHeartbeat'
                        AND event IN ('pause', 'speed-pause', 'AdPause'), 0,
                    event_type IN ('VideoSessionStart', 'VideoPlay', 'AppForegrounded'), 1,
                    event_type = 'VideoHeartbeat'
                        AND event IN ('resume', 'speed-resume', 'AdResume'), 1,
                    NULL) AS cls
            FROM events_src
        )
        GROUP BY video_session_id, ts
    ),
    stated AS
    (
        SELECT
            video_session_id, ts,
            coalesce(argMax(cls, if(cls IS NULL, epoch0, ts)) OVER (
                PARTITION BY video_session_id ORDER BY ts ASC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 1) AS is_open,
            -- The LAST end over the whole partition, per D13.
            maxIf(ts, is_end) OVER (PARTITION BY video_session_id) AS last_end
        FROM collapsed
    ),
    segments AS
    (
        SELECT
            video_session_id, ts AS seg_start, is_open, last_end,
            leadInFrame(ts) OVER (
                PARTITION BY video_session_id ORDER BY ts ASC
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_ts,
            least(
                least(if(next_ts > seg_start, next_ts, seg_start + tol), seg_start + tol),
                if(last_end > epoch0, last_end, never)
            ) AS seg_end
        FROM stated
    ),
    -- The foreground intervals, at the same precision the pipeline stores them.
    open_seg AS
    (
        SELECT
            video_session_id      AS sid,
            toDateTime(seg_start) AS istart,
            toDateTime(seg_end)   AS iend
        FROM segments
        WHERE is_open = 1
          AND (last_end = epoch0 OR seg_start < last_end)
    ),
    iv AS
    (
        SELECT
            sid,
            toUInt32(sum(dateDiff('second', istart, iend))) AS active_seconds,
            toUInt16(count())                               AS active_interval_count,
            min(istart)                                     AS first_active_at,
            max(iend)                                       AS last_active_at,
            argMax(dateDiff('second', istart, iend), istart) AS last_interval_seconds
        FROM open_seg
        GROUP BY sid
    ),
    -- Retention at an INSTANT: was a foreground interval covering first_active_at + N minutes.
    -- Not "had not ended yet". A session backgrounded at the checkpoint is not retained.
    ret AS
    (
        SELECT
            f.sid AS sid,
            max(if(o.istart <= f.first_active_at + toIntervalMinute(1)  AND o.iend > f.first_active_at + toIntervalMinute(1),  1, 0)) AS active_after_1m,
            max(if(o.istart <= f.first_active_at + toIntervalMinute(5)  AND o.iend > f.first_active_at + toIntervalMinute(5),  1, 0)) AS active_after_5m,
            max(if(o.istart <= f.first_active_at + toIntervalMinute(10) AND o.iend > f.first_active_at + toIntervalMinute(10), 1, 0)) AS active_after_10m,
            max(if(o.istart <= f.first_active_at + toIntervalMinute(15) AND o.iend > f.first_active_at + toIntervalMinute(15), 1, 0)) AS active_after_15m
        FROM iv AS f
        INNER JOIN open_seg AS o ON o.sid = f.sid
        GROUP BY f.sid
    ),
    ev AS
    (
        SELECT
            video_session_id                        AS sid,
            argMin(user_id, event_timestamp)        AS user_id,
            argMin(content_id, event_timestamp)     AS content_id,
            argMin(platform, event_timestamp)       AS platform,
            argMin(country, event_timestamp)        AS country,
            argMin(app_version, event_timestamp)    AS app_version,
            min(event_timestamp)                    AS first_event_at,
            max(event_timestamp)                    AS last_event_at,
            min(if(event_type = 'VideoPlay', event_timestamp, never))        AS first_play_raw,
            max(if(event_type = 'VideoSessionEnd', event_timestamp, epoch0)) AS last_end,
            min(if(event_type = 'VideoSessionEnd', event_timestamp, never))  AS first_end_raw,
            max(if(event_type IN ('VideoSessionStart', 'VideoPlay', 'AppForegrounded')
                   OR (event_type = 'VideoHeartbeat' AND event IN ('resume', 'speed-resume', 'AdResume')),
                   event_timestamp, epoch0))        AS last_reactivating,
            countIf(event_type = 'AppBackgrounded') AS background_count,
            countIf(event_type = 'AppForegrounded') AS foreground_return_count,
            countIf(event_type = 'VideoHeartbeat' AND event IN ('pause', 'speed-pause', 'AdPause'))    AS pause_count,
            countIf(event_type = 'VideoHeartbeat' AND event IN ('resume', 'speed-resume', 'AdResume')) AS resume_count,
            countIf(event_type = 'VideoHeartbeat') AS heartbeat_count,
            countIf(event_type = 'VideoError')     AS video_error_count
        FROM events_src
        GROUP BY video_session_id
    )
-- Column order is the contract with session_facts_optimized.sql. The two files are diffed line
-- by line, so a reordering here is a diff on every row.
SELECT
    ev.sid                                          AS video_session_id,
    ev.user_id,
    ev.content_id,
    ifNull(c.title, '')                             AS title,
    ifNull(c.category, '')                          AS category,
    ifNull(c.video_type, '')                        AS video_type,
    ev.platform,
    ev.country,
    ev.app_version,
    toString(ev.first_event_at)                     AS session_start,
    toString(if(ev.first_play_raw = never, epoch0, ev.first_play_raw)) AS first_play_at,
    toString(ev.last_end)                           AS session_end_at,
    toString(ifNull(iv.first_active_at, toDateTime(0))) AS first_active_at,
    toString(ifNull(iv.last_active_at,  toDateTime(0))) AS last_active_at,
    ifNull(iv.active_seconds, 0)                    AS active_seconds,
    ifNull(iv.active_interval_count, 0)             AS active_interval_count,
    ev.background_count,
    ev.foreground_return_count,
    ev.pause_count,
    ev.resume_count,
    ev.heartbeat_count,
    ev.video_error_count,
    toUInt8(ev.heartbeat_count > 0)                 AS reached_first_heartbeat,
    toUInt8(ifNull(ret.active_after_1m, 0))         AS active_after_1m,
    toUInt8(ifNull(ret.active_after_5m, 0))         AS active_after_5m,
    toUInt8(ifNull(ret.active_after_10m, 0))        AS active_after_10m,
    toUInt8(ifNull(ret.active_after_15m, 0))        AS active_after_15m,
    toUInt8(ev.last_end > epoch0)                   AS ended_normally,
    toUInt8(ev.last_end = epoch0)                   AS abandoned,
    toUInt8(ifNull(iv.last_interval_seconds, -1) = toInt64(tol)) AS timed_out,
    toUInt8(ev.first_end_raw < never AND ev.last_reactivating > ev.first_end_raw) AS reopened_after_end
FROM ev
LEFT JOIN iv  ON iv.sid  = ev.sid
LEFT JOIN ret ON ret.sid = ev.sid
-- LEFT ANY JOIN to stay symmetric with the optimized side. `content_src` is a CSV file view with
-- unique keys so it cannot fan out, but if the two sides of a validation pair disagree about
-- join semantics, the pair stops testing what it claims to test.
LEFT ANY JOIN content_src AS c ON c.content_id = ev.content_id
ORDER BY video_session_id;
