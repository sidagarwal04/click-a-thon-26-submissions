-- Incremental derivation. Processes only sessions that received events in a window, and
-- corrects what they contributed before instead of rebuilding anything.
--
-- Parameters: from_ts, to_ts (the arrival window), tolerance_s, pause_inactive.
--
-- Two statements, in order:
--   1. retract: write sign = -1 rows for every run those sessions currently assert
--   2. assert:  re-derive them from their full event history and write sign = +1 rows
-- The delta MV turns both into additive rows, so the serving table self-corrects. Other
-- sessions are never read, never rewritten, and the dashboard never sees a gap: the
-- retraction and the assertion land in the same tick.
--
-- Why re-derive a whole session rather than only its new minutes: an arriving heartbeat can
-- extend a run, close one, or bridge two, and a session's event history is ~80 rows on the
-- session-ordered primary key. Cheap, and it removes a whole class of edge cases.

-- The aggregation lives in a subquery on purpose: writing `-1 AS sign` in the same SELECT
-- shadows the table's own `sign` inside HAVING, so `sum(sign)` evaluates the constant and
-- the filter silently matches nothing. That failure is invisible, the insert just writes
-- zero rows, and the serving layer then double-counts every re-derived session.
INSERT INTO session_minute_runs
    (video_session_id, user_id, content_id, platform, country, app_version,
     audio_language, subtitle_language, player_version, video_resolution,
     video_type, run_start, run_end, sign)
SELECT
    video_session_id, user_id, content_id, platform, country, app_version,
    audio_language, subtitle_language, player_version, video_resolution,
    video_type,
    run_start, run_end, -1 AS sign
FROM
(
    SELECT
        video_session_id, user_id, content_id, platform, country, app_version,
        audio_language, subtitle_language, player_version, video_resolution,
        video_type,
        run_start, run_end,
        sum(sign) AS s
    FROM session_minute_runs
    WHERE video_session_id IN (
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
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3))
    GROUP BY video_session_id, user_id, content_id, platform, country, app_version,
 audio_language, subtitle_language, player_version, video_resolution,
 video_type,
             run_start, run_end
    HAVING s > 0   -- only retract what is currently asserted
)
-- One -1 PER EXCESS ASSERTION, not one per group. A single -1 leaves a doubly-asserted run
-- at +1 forever: the retract can then never catch up, and a run that was double-counted
-- once is double-counted for life. Emitting exactly s retractions zeroes the group
-- whatever state it is in, which makes every tick self-healing. Doubles are not
-- hypothetical: raw_events keeps receiving inserts between this statement and the assert
-- below, so a session can enter the assert's touched-set without having been retracted
-- here. That race is unavoidable across two statements; with an exact retract the next
-- tick that touches the session repairs it. Measured on live phoenix 2026-08-01: 1,165
-- doubled and 832 negative run keys accumulated in the unfrozen slice before this fix.
ARRAY JOIN range(toUInt32(s)) AS _r;

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
    -- Same bound as the batch path, for the same measured reason: 385 intervals ran past their
    -- session's last VideoSessionEnd. Both paths must agree or parity fails, so this is the
    -- second of three independent statements of the rule (01_derive_intervals.sql and
    -- validation/oracle_concurrency.sql are the others).
    --
    -- Scoped to touched sessions like everything else here. That is safe because a session's end
    -- events are part of the session: if a re-derive touches the session at all, its whole event
    -- history is in scope, so last_end is the true last end and not a window-local maximum.
    ends AS
    (
        SELECT
            video_session_id,
            max(event_timestamp) AS last_end
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
            -- epoch 0 means the session has no end event, so leave it unbounded. An unmatched
            -- LEFT JOIN yields the type DEFAULT here, not NULL, so testing IS NULL would clamp
            -- every such session to 1970.
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
          -- An event at or after the last end opens nothing. Capping alone leaves a zero-length
          -- interval per post-end event, and timeSlots still yields its minute.
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
SELECT
    r.video_session_id,
    d.user_id, d.content_id, d.platform, d.country, d.app_version,
    d.audio_language, d.subtitle_language, d.player_version, d.video_resolution,
    c.video_type,
    r.run[1]  AS run_start,
    r.run[-1] AS run_end,
    1 AS sign
FROM runs AS r
INNER JOIN dims AS d ON r.video_session_id = d.video_session_id
LEFT JOIN content AS c ON d.content_id = c.content_id;
