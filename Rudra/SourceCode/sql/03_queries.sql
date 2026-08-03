-- ============================================================================
-- Serving queries — LIVE (from live_sessions) and HISTORICAL (from hist_minute_full).
-- The benchmark = peak & average concurrency at minute/hour/day grain + filters.
-- ============================================================================

-- ── LIVE: concurrency right now, by any dimension ─────────────────────────────
WITH cur AS (
    SELECT video_session_id,
        argMaxMerge(state) AS st, maxMerge(last_beat) AS lb,
        argMaxMerge(platform) AS platform, argMaxMerge(video_type) AS video_type,
        argMaxMerge(audio_language) AS audio_language, argMaxMerge(video_resolution) AS video_resolution
    FROM sonyliv.live_sessions GROUP BY video_session_id
)
SELECT platform, count() AS live_now
FROM cur
WHERE st = 'active' AND lb > now64(3) - INTERVAL 90 SECOND        -- + AND video_type='live' etc.
GROUP BY platform ORDER BY live_now DESC;

-- ── HISTORICAL: overall peak & average concurrency over a day ─────────────────
-- Sum is exact for session-constant dims and fully-specified per-event dims.
SELECT max(c) AS peak, round(avg(c),1) AS avg_concurrency
FROM (
    SELECT minute, sum(cnt) AS c
    FROM sonyliv.hist_minute_full
    WHERE minute >= toDateTime('2026-07-31 00:00:00') AND minute < toDateTime('2026-08-01 00:00:00')
    GROUP BY minute
);

-- ── HISTORICAL: peak by platform (each peaks at its own minute) ───────────────
SELECT platform, max(c) AS peak
FROM (SELECT platform, minute, sum(cnt) AS c FROM sonyliv.hist_minute_full GROUP BY platform, minute)
GROUP BY platform ORDER BY peak DESC;

-- ── HISTORICAL: peak by video_resolution (the per-event dim) ──────────────────
SELECT video_resolution, max(c) AS peak
FROM (SELECT video_resolution, minute, sum(cnt) AS c FROM sonyliv.hist_minute_full GROUP BY video_resolution, minute)
GROUP BY video_resolution ORDER BY peak DESC;

-- ── HISTORICAL: hour grain (peak = max of the minute values in each hour) ─────
SELECT toStartOfHour(minute) AS hour, max(c) AS peak_hour, round(avg(c),1) AS avg_hour
FROM (SELECT minute, sum(cnt) AS c FROM sonyliv.hist_minute_full WHERE video_type='live' GROUP BY minute)
GROUP BY hour ORDER BY peak_hour DESC;
-- day grain in IST: GROUP BY toDate(minute, 'Asia/Kolkata')

-- ── HISTORICAL: concurrency curve for a filter (e.g. a show + resolution) ─────
SELECT minute, sum(cnt) AS concurrency
FROM sonyliv.hist_minute_full
WHERE video_type='live' AND video_resolution='1920*1080'
GROUP BY minute ORDER BY minute;
