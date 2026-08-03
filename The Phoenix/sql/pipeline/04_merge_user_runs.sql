-- session_minute_runs -> user_minute_runs
--
-- Collapses every session a user had into the minutes that user was watching at all, then
-- splits those into contiguous runs. Two sessions overlapping in a minute contribute that
-- minute once, which is the whole difference between session-level and user-level.
--
-- Reads only asserted runs (sum(sign) > 0), so retracted session runs never leak upward.
-- Writes with sign = +1; the incremental path retracts by user the same way the session
-- path does.
INSERT INTO user_minute_runs
    (user_id, platform, country, video_type, content_id, app_version,
     audio_language, subtitle_language, player_version, video_resolution,
     run_start, run_end, sign)
WITH
    asserted AS
    (
        SELECT
            user_id, video_session_id, platform, country, video_type, content_id,
            app_version, audio_language, subtitle_language, player_version, video_resolution, run_start, run_end
        FROM session_minute_runs
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
    runs AS
    (
        SELECT
            user_id, platform, country, video_type, content_id, app_version,
            audio_language, subtitle_language, player_version, video_resolution,
            arrayJoin(arraySplit(
                (m, i) -> (i > 1) AND (m - minutes[i - 1] > 60),
                minutes, arrayEnumerate(minutes))) AS run
        FROM per_user
    )
SELECT
    user_id, platform, country, video_type, content_id, app_version,
    audio_language, subtitle_language, player_version, video_resolution,
    run[1]  AS run_start,
    run[-1] AS run_end,
    1       AS sign
FROM runs;
