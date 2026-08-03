-- Incremental foreground_intervals, for the derive tick.
--
-- Parameters: tolerance_s, pause_inactive, from_ts, to_ts.
--
-- ============================================================================================
-- WHY THIS FILE HAD TO EXIST, and what its absence silently did.
--
-- foreground_intervals had exactly ONE writer: 01_derive_intervals.sql, which takes no window
-- parameters, reads the whole corpus, and appends. It therefore only ever runs inside
-- scripts/derive.sh's full-batch path, never inside scripts/derive_tick.sh. The tick writes
-- session_minute_runs and user_minute_runs and nothing else.
--
-- So under continuous ingest the intervals table simply stopped. Measured on phoenix_next:
-- session_minute_runs current at 2026-08-02 07:02 while foreground_intervals sat at
-- 2026-08-01 17:07, and of 120,336 sessions active in the previous six hours, ZERO had an
-- interval row while 112,812 had runs.
--
-- That did not surface as an empty table. It surfaced as PLAUSIBLE WRONG NUMBERS in tables the
-- console marks fresh, because 01_refresh_session_facts.sql LEFT JOINs this table:
--   session_insight_facts   4,003 recent sessions with first_active_at at epoch 0 and
--                           active_seconds, active_after_{1,5,10,15}m all zero. Zero populated.
--   playback_health_minute  0 heartbeat timeouts across 52,859 active sessions, because its
--                           outs CTE gates on last_active_at > toDateTime(0).
--   content_entry_cohorts   frozen, because 05_refresh_cohorts.sql correctly filters
--                           first_active_at > toDateTime(0) and nothing recent passes it.
--   user_*_transitions      frozen for the same reason.
--
-- ============================================================================================
-- WHY APPEND-ONLY IS SAFE HERE, WITHOUT A sign COLUMN.
--
-- The obvious fix is to make foreground_intervals a CollapsingMergeTree and retract/re-assert
-- like session_minute_runs does. That works, and it costs an engine change, an ORDER BY change
-- (immutable, so a drop-and-recreate) on two databases, plus sign-netting in every reader.
--
-- It is not necessary, because of one property: a SETTLED session's intervals never change
-- again. The derivation depends only on the session's own events, and a session that has not
-- emitted for longer than tolerance_s cannot gain another event that alters an earlier interval
-- (a later event would open a NEW interval, not move an old one).
--
-- So this statement derives intervals only for sessions that are BOTH settled AND absent from
-- the table. Nothing is ever rewritten, so nothing can be duplicated, so no sign column is
-- needed. In-flight sessions are deliberately skipped and land on a later tick once they go
-- quiet, which is the same tolerance-driven boundary the concurrency model already uses.
--
-- The cost is honest and bounded: a session is missing from session_insight_facts activity
-- columns for at most tolerance_s after its last event, instead of forever.
-- ============================================================================================

INSERT INTO foreground_intervals
    (video_session_id, user_id, content_id, platform, country, app_version,
     audio_language, subtitle_language, player_version, video_resolution,
     video_type, interval_start, interval_end)
WITH
    {tolerance_s:UInt32} AS tol,

    -- Sessions touched by this window that are SETTLED and NOT already derived.
    --
    -- The NOT IN is the duplicate guard and it is the whole reason this can stay append-only.
    -- foreground_intervals is a plain MergeTree: a second insert for the same session would
    -- double every one of its intervals, and because the table has no sign and no version,
    -- nothing downstream could tell the copies apart.
    todo AS
    (
        SELECT video_session_id
        FROM raw_events
        WHERE event_timestamp >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3)
        GROUP BY video_session_id
        HAVING max(event_timestamp) < now() - toIntervalSecond(tol)
           AND video_session_id NOT IN (SELECT DISTINCT video_session_id FROM foreground_intervals)
    ),

    -- Everything below is 01_derive_intervals.sql verbatim except for the `todo` scoping. It is
    -- duplicated rather than shared because the batch path must keep working standalone, and the
    -- two must agree: if this derivation ever diverges from that one, the incremental and batch
    -- tables stop being the same table. scripts/interval_parity.sh is what proves they agree.
    dims AS
    (
        SELECT
            video_session_id,
            argMin(user_id, event_timestamp)     AS user_id,
            argMin(content_id, event_timestamp)  AS content_id,
            argMin(platform, event_timestamp)    AS platform,
            argMin(country, event_timestamp)     AS country,
            argMin(app_version, event_timestamp) AS app_version,
            -- The four dimensions the unseen day made filterable. Same first-event rule as
            -- platform and app_version above: a session reporting two audio languages or two
            -- resolutions is dirty data, not two sessions.
            argMin(audio_language, event_timestamp)    AS audio_language,
            argMin(subtitle_language, event_timestamp) AS subtitle_language,
            argMin(player_version, event_timestamp)    AS player_version,
            argMin(video_resolution, event_timestamp)  AS video_resolution
        FROM raw_events
        WHERE video_session_id IN (SELECT video_session_id FROM todo)
        GROUP BY video_session_id
    ),
    ends AS
    (
        SELECT video_session_id, max(event_timestamp) AS last_end
        FROM raw_events
        WHERE event_type = 'VideoSessionEnd'
          AND video_session_id IN (SELECT video_session_id FROM todo)
        GROUP BY video_session_id
    ),
    segments AS
    (
        SELECT
            video_session_id,
            ts,
            if({pause_inactive:UInt8}, is_open, is_open_pause_active) AS is_open,
            leadInFrame(ts) OVER (
                PARTITION BY video_session_id ORDER BY ts ASC
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_ts,
            least(if(next_ts > ts, next_ts, ts + tol), ts + tol) AS seg_end
        FROM event_state
        WHERE video_session_id IN (SELECT video_session_id FROM todo)
    )
SELECT
    s.video_session_id,
    d.user_id, d.content_id, d.platform, d.country, d.app_version,
    d.audio_language, d.subtitle_language, d.player_version, d.video_resolution,
    c.video_type,
    toDateTime(s.ts) AS interval_start,
    toDateTime(if(e.last_end > toDateTime64(0, 3), least(s.seg_end, e.last_end), s.seg_end)) AS interval_end
FROM segments AS s
INNER JOIN dims    AS d ON s.video_session_id = d.video_session_id
LEFT  JOIN ends    AS e ON s.video_session_id = e.video_session_id
LEFT  JOIN content AS c ON d.content_id = c.content_id
WHERE s.is_open = 1
  AND (e.last_end = toDateTime64(0, 3) OR s.ts < e.last_end);
