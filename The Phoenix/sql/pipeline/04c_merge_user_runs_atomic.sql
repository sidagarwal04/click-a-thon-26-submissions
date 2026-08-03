-- session_minute_runs -> user_minute_runs, INCREMENTAL and ATOMIC. The user-side twin of
-- 03b_derive_incremental_atomic.sql, and the file derive_tick.sh calls every tick.
--
-- Parameters: from_ts, to_ts (the window).
--
-- WHY THIS EXISTS. 04_merge_user_runs.sql rebuilds user_minute_runs from ALL asserted session
-- runs and appends sign = +1 unconditionally, so it is correct exactly once per corpus. The tick
-- never ran it, which is why concurrency_deltas advanced live while user_concurrency_deltas
-- stayed pinned at the last batch derive and the console's Users tab read zero for every live
-- minute.
--
-- WHY IT IS SCOPED TO TOUCHED USERS rather than retract-all-and-rebuild. Retract-all was tried
-- first and measured: it writes one inverse delta and one fresh delta for EVERY user run on
-- EVERY tick, so user_concurrency_deltas reached 81,398 physical rows against 31,052 for the
-- session side of the same corpus, and the serving query's read budget tripped with
-- TOO_MANY_ROWS at 107.58k. The churn is the cost, not the row count: a SummingMergeTree only
-- collapses on merge, so a full rewrite per tick is unbounded physical growth between merges.
-- Restricting to users with an event in the window makes the write proportional to arrivals.
--
-- Correctness of the scope: a user's runs are a function of that user's whole session history,
-- so a touched user is re-derived from ALL of their asserted session runs, not just the ones in
-- the window. Only the SET of users is windowed, never the history each one is rebuilt from.
--
-- ONE STATEMENT, retract and assert as two branches of a UNION ALL, for the reason 03b spells
-- out: two statements let a user first seen between them get asserted without being retracted,
-- and on Cloud SharedMergeTree let the assert read a replica that has not seen the retract. One
-- statement pins one part set for both branches, so neither race exists.
--
-- The retract branch zeroes ANY nonzero group in either direction, abs(s) rows of -sign(s), so
-- a doubled group and a stranded negative both heal, whatever left them behind.
INSERT INTO user_minute_runs
    (user_id, platform, country, video_type, content_id, app_version,
     audio_language, subtitle_language, player_version, video_resolution,
     run_start, run_end, sign)
WITH
    touched AS
    (
        SELECT DISTINCT user_id FROM raw_events
        WHERE event_timestamp >= parseDateTime64BestEffort({from_ts:String}, 3)
          -- INCLUSIVE, for the same reason as 03b: derive_tick.sh passes
          -- to_ts = max(event_timestamp), so a strict `<` drops exactly the newest rows and the
          -- user-concurrency curve lags session concurrency by one tick. Widening is safe because
          -- the window only selects TOUCHED USERS and re-touching one is idempotent.
          AND event_timestamp <= parseDateTime64BestEffort({to_ts:String}, 3)
    ),
    asserted AS
    (
        SELECT
            user_id, video_session_id, platform, country, video_type, content_id,
            app_version, audio_language, subtitle_language, player_version, video_resolution, run_start, run_end
        FROM session_minute_runs
        WHERE user_id IN (SELECT user_id FROM touched)
        GROUP BY user_id, video_session_id, platform, country, video_type, content_id,
                 app_version, audio_language, subtitle_language, player_version, video_resolution, run_start, run_end
        HAVING sum(sign) > 0
    ),
    per_user AS
    (
        SELECT
            user_id,
            -- dimensions of the user's earliest run: see the note in 05_user_concurrency.sql
            argMin(platform, run_start)    AS platform,
            argMin(country, run_start)     AS country,
            argMin(video_type, run_start)  AS video_type,
            argMin(content_id, run_start)  AS content_id,
            argMin(app_version, run_start) AS app_version,
            argMin(audio_language, run_start)    AS audio_language,
            argMin(subtitle_language, run_start) AS subtitle_language,
            argMin(player_version, run_start)    AS player_version,
            argMin(video_resolution, run_start)  AS video_resolution,
            arraySort(groupUniqArrayArray(
                timeSlots(run_start, toUInt32(dateDiff('second', run_start, run_end)), 60)
            )) AS minutes
        FROM asserted
        GROUP BY user_id
    ),
    fresh AS
    (
        SELECT
            user_id, platform, country, video_type, content_id, app_version,
            audio_language, subtitle_language, player_version, video_resolution,
            arrayJoin(arraySplit(
                (m, i) -> (i > 1) AND (m - minutes[i - 1] > 60),
                minutes, arrayEnumerate(minutes))) AS run
        FROM per_user
    ),
    stale AS
    (
        SELECT
            user_id, platform, country, video_type, content_id, app_version,
            audio_language, subtitle_language, player_version, video_resolution,
            run_start, run_end, sum(sign) AS s
        FROM user_minute_runs
        WHERE user_id IN (SELECT user_id FROM touched)
        GROUP BY user_id, platform, country, video_type, content_id, app_version,
                 audio_language, subtitle_language, player_version, video_resolution,
                 run_start, run_end
        HAVING s != 0
    )
SELECT
    user_id, platform, country, video_type, content_id, app_version,
    audio_language, subtitle_language, player_version, video_resolution,
    run_start, run_end,
    toInt8(-1 * sign(s)) AS sign
FROM stale
ARRAY JOIN range(toUInt32(abs(s))) AS copy
UNION ALL
SELECT
    user_id, platform, country, video_type, content_id, app_version,
    audio_language, subtitle_language, player_version, video_resolution,
    run[1]  AS run_start,
    run[-1] AS run_end,
    toInt8(1) AS sign
FROM fresh;
