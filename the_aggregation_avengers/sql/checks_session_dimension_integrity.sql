-- Session/dimension integrity checks
--
-- Concurrency deltas are emitted per (minute, dimension-tuple), which silently
-- assumes each video_session_id has ONE value per dimension. It does not.
-- Run these after every load, including the unseen day.
--
-- Findings on the provided day (905,558 events / 10,866 sessions):
--   platform        95 sessions (0.87%)  span 2 values -- ALWAYS ANDROID_PHONE+ANDROID_TAB
--   user_id        120 sessions (1.10%)  span 2 values
--   content_id       1 session           spans 2 values
--   country / app_version / session_start_epoch   always 1 value  [clean]
--   player_version 1,600 (14.7%), audio_language 8,796 (81%),
--   subtitle_language 10,862 (99.96%)    -- these legitimately vary mid-session
--                                           (user switches audio track); they are
--                                           event attributes, not session attributes.

-- ===========================================================================
-- Q1. Is a video_session_id duplicated across multiple platforms?  [the ask]
-- ===========================================================================
SELECT
    video_session_id,
    uniqExact(platform)                    AS platform_count,
    arraySort(groupUniqArray(platform))    AS platforms,
    count()                                AS events,
    min(event_timestamp)                   AS first_seen,
    max(event_timestamp)                   AS last_seen
FROM events_raw
GROUP BY video_session_id
HAVING platform_count > 1
ORDER BY events DESC;
-- provided day -> 95 rows, every one ['ANDROID_PHONE','ANDROID_TAB']

-- Just the count, for a fast pass/fail:
SELECT countIf(c > 1) AS multi_platform_sessions,
       count()        AS total_sessions,
       round(100.0 * countIf(c > 1) / count(), 3) AS pct
FROM (SELECT video_session_id, uniqExact(platform) AS c
      FROM events_raw GROUP BY video_session_id);
-- provided day -> 95 / 10,866 / 0.874

-- ===========================================================================
-- Q2. Which platform PAIRS occur? Distinguishes noise from real migration.
-- ===========================================================================
SELECT arraySort(groupUniqArray(platform)) AS pair, count() AS sessions
FROM events_raw
GROUP BY video_session_id
HAVING uniqExact(platform) > 1
GROUP BY pair          -- (re-grouped in an outer scope; see nested form below)
ORDER BY sessions DESC;
-- ClickHouse needs this nested rather than double-GROUP BY:
SELECT pair, count() AS sessions FROM (
    SELECT video_session_id, arraySort(groupUniqArray(platform)) AS pair
    FROM events_raw GROUP BY video_session_id
    HAVING length(pair) > 1
) GROUP BY pair ORDER BY sessions DESC;
-- provided day -> ONE pair only: ['ANDROID_PHONE','ANDROID_TAB'] x95

-- ===========================================================================
-- Q3. Noise or migration? Count how many times platform CHANGES mid-session.
--     A real device handoff flips once. Detection noise oscillates.
-- ===========================================================================
SELECT changes, count() AS sessions FROM (
    SELECT video_session_id,
           countIf(platform != prev_platform AND prev_platform != '') AS changes
    FROM (SELECT video_session_id, platform,
                 any(platform) OVER (PARTITION BY video_session_id
                                     ORDER BY event_timestamp
                                     ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING) AS prev_platform
          FROM events_raw)
    GROUP BY video_session_id
) WHERE changes > 0
GROUP BY changes ORDER BY changes;
-- provided day -> only 1 session flips once; 94 flip 2-13 times.
-- A phone does not become a tablet 13 times in 24 minutes => CLASSIFICATION
-- NOISE, not cross-device continuation.
--
-- Two candidate causes were tested and RULED OUT:
--   screen casting -- only 4 sessions in the whole dataset emit any chromecast
--                     event (12 events), and ZERO of them are in the 95.
--   screen resize  -- video-resize is 0.31x ENRICHED at flips (5.6% vs 17.7%
--                     baseline), i.e. three times LESS likely than chance.
--                     Resize rate in affected sessions is 1.10x = noise.
--
-- What flips actually correlate with is app LIFECYCLE, not rendering:
--   Play 22.65x | AppBackgrounded 18.85x | upshift 9.48x | pause 4.20x
--   resume 3.61x | buffer-health 1.01x (control, no signal)
-- => the platform string is re-derived on every state transition and Android
--    form-factor detection returns an inconsistent device class. Systematic,
--    so expect it again on the unseen day.

-- ===========================================================================
-- Q4. Same check, every dimension at once.
-- ===========================================================================
SELECT 'platform' AS dim, countIf(c>1) AS multi, count() AS tot,
       round(100.0*countIf(c>1)/count(),2) AS pct
FROM (SELECT uniqExact(platform) c FROM events_raw GROUP BY video_session_id)
UNION ALL SELECT 'user_id', countIf(c>1), count(), round(100.0*countIf(c>1)/count(),2)
FROM (SELECT uniqExact(user_id) c FROM events_raw GROUP BY video_session_id)
UNION ALL SELECT 'content_id', countIf(c>1), count(), round(100.0*countIf(c>1)/count(),2)
FROM (SELECT uniqExact(content_id) c FROM events_raw GROUP BY video_session_id)
UNION ALL SELECT 'country', countIf(c>1), count(), round(100.0*countIf(c>1)/count(),2)
FROM (SELECT uniqExact(country) c FROM events_raw GROUP BY video_session_id)
UNION ALL SELECT 'app_version', countIf(c>1), count(), round(100.0*countIf(c>1)/count(),2)
FROM (SELECT uniqExact(app_version) c FROM events_raw GROUP BY video_session_id)
UNION ALL SELECT 'session_start_epoch', countIf(c>1), count(), round(100.0*countIf(c>1)/count(),2)
FROM (SELECT uniqExact(session_start_epoch) c FROM events_raw GROUP BY video_session_id)
ORDER BY pct DESC;

-- ===========================================================================
-- THE FIX: pin one value per session BEFORE emitting deltas.
-- ===========================================================================
-- Why this matters. Deltas are keyed by (minute, platform). If a session's
-- platform flips, the +1 lands under ANDROID_TAB and the -1 under
-- ANDROID_PHONE. The running sum then never returns to zero: the tab series
-- is stuck +1 high and the phone series -1 low, FOREVER, for every minute
-- after that session. One flipped session permanently corrupts two filtered
-- curves. The unfiltered total still balances, which is exactly why this bug
-- survives casual testing.
--
-- Resolution: majority vote, ties broken by earliest event. Deterministic and
-- idempotent under replay (PRD FR-1 R6).
CREATE OR REPLACE VIEW session_dims AS
SELECT
    video_session_id,
    topK(1)(platform)[1]   AS platform,     -- majority value
    topK(1)(user_id)[1]    AS user_id,
    topK(1)(content_id)[1] AS content_id,
    any(country)           AS country,
    min(event_timestamp)   AS session_start,
    max(event_timestamp)   AS session_end
FROM events_raw
GROUP BY video_session_id;

-- Sanity: must return 0 rows.
SELECT count() AS sessions_with_ambiguous_platform FROM (
    SELECT video_session_id FROM session_dims
    GROUP BY video_session_id HAVING uniqExact(platform) > 1);

-- NOTE ON THE OTHER THREE. player_version / audio_language / subtitle_language
-- vary within 81-99.96% of sessions -- a user switching audio track mid-play is
-- REAL behaviour, not corruption. Do not majority-vote those onto the session.
-- Either attribute them at event level (splitting the active interval at each
-- change) or accept them as approximate. Decide before they reach a filter.
