-- Incremental derivation, ATOMIC variant: retract and assert in ONE INSERT statement.
--
-- Parameters: from_ts, to_ts (the window), tolerance_s, pause_inactive.
--
-- Why one statement where 03_derive_incremental.sql uses two, measured on live phoenix
-- 2026-08-01: with two statements, (a) a session whose first in-window event arrives
-- between the retract and the assert is asserted without retraction, and (b) on Cloud
-- SharedMergeTree the assert-statement's read can miss rows the retract statement just
-- wrote on another replica. Both races put the same run in twice. Accumulated damage
-- before this file existed: up to 1,165 doubled and 832 negative run keys in the live
-- slice, all invisible to the frozen-slice gates. In one statement both branches read the
-- SAME pinned part set, and the correction lands as one insert: neither race can exist.
--
-- The retract branch zeroes ANY nonzero group, in either direction: abs(s) rows of
-- sign = -sign(s). A doubled group gets two -1, a stranded negative gets +1 back to zero.
-- Every window is therefore self-healing for every session it touches, whatever state a
-- previous bug, race, or partial insert left behind.
INSERT INTO session_minute_runs
    (video_session_id, user_id, content_id, platform, country, app_version,
     audio_language, subtitle_language, player_version, video_resolution,
     video_type, run_start, run_end, sign)
WITH
    {tolerance_s:UInt32} AS tol,
    touched AS
    (
        SELECT DISTINCT video_session_id FROM raw_events
        -- INCLUSIVE upper bound. derive_tick.sh passes to_ts = max(event_timestamp), so a
        -- strict `<` here excludes precisely the newest rows -- the ones the tick exists to
        -- process. They are only picked up later, by a tick whose max has moved past them, so
        -- the serving curve lags one tick behind ingest and a batch whose rows all share the
        -- newest instant is skipped entirely. Measured 2026-08-01: a producer stamping one
        -- cycle with a single now64(3) put 2,024 rows exactly at the max and the derive built
        -- 0 intervals from them, leaving a flat zero curve while ingest looked healthy.
        --
        -- Safe to widen: the window is used to pick the TOUCHED SESSIONS, and re-touching a
        -- session is idempotent by construction (the retract zeroes whatever it currently
        -- asserts before the assert rewrites it from full history). Overlap costs work, never
        -- correctness -- the same guarantee derive_tick.sh's OVERLAP_S already relies on.
        WHERE event_timestamp >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3)
    ),
    dims AS
    (
        SELECT
            video_session_id,
            argMin(user_id, event_timestamp)     AS user_id,
            argMin(content_id, event_timestamp)  AS content_id,
            argMin(platform, event_timestamp)    AS platform,
            argMin(country, event_timestamp)     AS country,
            argMin(app_version, event_timestamp) AS app_version,
            argMin(audio_language, event_timestamp)    AS audio_language,
            argMin(subtitle_language, event_timestamp) AS subtitle_language,
            argMin(player_version, event_timestamp)    AS player_version,
            argMin(video_resolution, event_timestamp)  AS video_resolution
        FROM raw_events
        WHERE video_session_id IN (SELECT video_session_id FROM touched)
        GROUP BY video_session_id
    ),
    ends AS
    (
        SELECT video_session_id, max(event_timestamp) AS last_end
        FROM raw_events
        WHERE event_type = 'VideoSessionEnd'
          AND video_session_id IN (SELECT video_session_id FROM touched)
        GROUP BY video_session_id
    ),
    segments AS
    (
        SELECT
            es.video_session_id AS video_session_id,
            es.ts AS interval_start,
            if({pause_inactive:UInt8}, es.is_open, es.is_open_pause_active) AS is_open,
            e.last_end AS last_end,
            leadInFrame(es.ts) OVER (
                PARTITION BY es.video_session_id ORDER BY es.ts ASC
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_ts,
            least(
                least(if(next_ts > es.ts, next_ts, es.ts + tol), es.ts + tol),
                if(e.last_end > toDateTime64(0, 3), e.last_end, toDateTime64('2100-01-01 00:00:00', 3))
            ) AS interval_end
        FROM event_state AS es
        LEFT JOIN ends AS e ON es.video_session_id = e.video_session_id
        WHERE es.video_session_id IN (SELECT video_session_id FROM touched)
    ),
    per_session AS
    (
        SELECT
            video_session_id,
            arraySort(groupUniqArrayArray(
                timeSlots(toDateTime(interval_start),
                          toUInt32(greatest(dateDiff('second', interval_start, interval_end) - 1, 0)),
                          60))) AS minutes
        FROM segments
        WHERE is_open = 1
          AND (last_end = toDateTime64(0, 3) OR interval_start < last_end)
        GROUP BY video_session_id
    ),
    runs AS
    (
        SELECT
            video_session_id,
            arrayJoin(arraySplit(
                (m, i) -> (i > 1) AND (m - minutes[i - 1] > 60),
                minutes, arrayEnumerate(minutes))) AS run
        FROM per_session
    )
SELECT * FROM
(
    -- Retract branch: zero out whatever the touched sessions currently hold, exactly.
    SELECT
        video_session_id, user_id, content_id, platform, country, app_version,
        audio_language, subtitle_language, player_version, video_resolution,
        video_type,
        run_start, run_end,
        toInt8(if(s > 0, -1, 1)) AS sign
    FROM
    (
        SELECT
            video_session_id, user_id, content_id, platform, country, app_version,
            audio_language, subtitle_language, player_version, video_resolution,
            video_type,
            run_start, run_end, sum(sign) AS s
        FROM session_minute_runs
        WHERE video_session_id IN (SELECT video_session_id FROM touched)
        GROUP BY video_session_id, user_id, content_id, platform, country, app_version,
 audio_language, subtitle_language, player_version, video_resolution,
 video_type,
                 run_start, run_end
        HAVING s != 0
    )
    ARRAY JOIN range(toUInt32(abs(s))) AS _r

    UNION ALL

    -- Assert branch: the sessions' current truth, re-derived from full event history.
    SELECT
        r.video_session_id AS video_session_id,
        d.user_id AS user_id, d.content_id AS content_id, d.platform AS platform,
        d.country AS country, d.app_version AS app_version,
        d.audio_language AS audio_language, d.subtitle_language AS subtitle_language,
        d.player_version AS player_version, d.video_resolution AS video_resolution,
        c.video_type AS video_type,
        r.run[1]  AS run_start,
        r.run[-1] AS run_end,
        toInt8(1) AS sign
    FROM runs AS r
    INNER JOIN dims AS d ON r.video_session_id = d.video_session_id
    LEFT JOIN content AS c ON d.content_id = c.content_id
);
