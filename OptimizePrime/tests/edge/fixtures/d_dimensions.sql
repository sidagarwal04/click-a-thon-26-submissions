-- ============================================================================
-- Family D — dimension attribution (Codex 003 §11.5, the derivation's share)
-- Pins ADR 0008/0009 (dominant value per interval, ties broken by the value)
-- and the 40_deltas merge rule (a merged minute-run keeps the EARLIER
-- interval's dimensions). User counting, catalog mapping and normalisation are
-- deliberately NOT here — see the not-implemented ledger in docs/TESTS.md §H.
-- Dates: 2026-07-01 / 2026-07-02. Constant dims except the one under test.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- D01 · dominant value with a TIE — broken by the smallest value, never by
--       thread luck (the determinism ADR 0009 exists for)
-- EVENTS  beats 10:00:00 hin, 10:00:40 ben, 10:01:20 hin, 10:02:00 ben,
--         10:02:40 tam (all else constant)
-- BY HAND one run + tail -> interval [10:00:00, 10:03:40]. Vote: hin 2,
--         ben 2, tam 1 -> tie between ben and hin -> sort by (-freq, value)
--         picks 'ben' (< 'hin'). Minutes 10:00..10:03 cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 501, 'D01_S1', 'U_D01', 'VideoHeartbeat', 'network-activity', '2026-07-01 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-07-01 10:00:00.000'),
(1, 501, 'D01_S1', 'U_D01', 'VideoHeartbeat', 'network-activity', '2026-07-01 10:00:40.000', 'web','1.0','IN','ben','none','p1','2026-07-01 10:00:00.000'),
(1, 501, 'D01_S1', 'U_D01', 'VideoHeartbeat', 'network-activity', '2026-07-01 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-07-01 10:00:00.000'),
(1, 501, 'D01_S1', 'U_D01', 'VideoHeartbeat', 'network-activity', '2026-07-01 10:02:00.000', 'web','1.0','IN','ben','none','p1','2026-07-01 10:00:00.000'),
(1, 501, 'D01_S1', 'U_D01', 'VideoHeartbeat', 'network-activity', '2026-07-01 10:02:40.000', 'web','1.0','IN','tam','none','p1','2026-07-01 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open, audio_language) VALUES
('D01_S1', '2026-07-01 10:00:00.000', '2026-07-01 10:03:40.000', 1, 'ben');

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D01', toDateTime('2026-07-01 10:00:00') + 60 * number, '*', 1 FROM numbers(4);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('D01', '2026-07-01 00:00:00', '2026-07-02 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- D02 · dimension changes mid-session across a pause; the minute-merge keeps
--       the EARLIER interval's platform (40_deltas first-wins rule)
-- EVENTS  web beat 10:00:00; web pause 10:00:40; android resume 10:01:10;
--         android beats 10:01:30, 10:01:50
-- BY HAND one run [10:00:00, 10:01:50]; window [10:00:40, 10:01:10).
--         Segment 1 (10:00:00, 10:00:40): events web beat + web pause -> web.
--         Segment 2 (10:01:10, 10:01:50) + tail -> (10:01:10, 10:02:50):
--         events android resume + 2 android beats -> android.
--         Interval rows keep their own platforms (asserted). At minute grain
--         the pairs (10:00,10:00) and (10:01,10:02) TOUCH, so they merge and
--         the merged run carries the EARLIER platform: every served minute is
--         web. Truth: web 10:00..10:02 cc=1; android 0 everywhere (explicit) —
--         deliberately pinning the known weirdness of first-wins attribution
--         (ADR 0008 measures the exposure; a per-segment attribution ruling
--         would flip the 10:01/10:02 rows to android).
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 502, 'D02_S1', 'U_D02', 'VideoHeartbeat', 'network-activity', '2026-07-02 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-07-02 10:00:00.000'),
(1, 502, 'D02_S1', 'U_D02', 'VideoHeartbeat', 'pause',            '2026-07-02 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-07-02 10:00:00.000'),
(1, 502, 'D02_S1', 'U_D02', 'VideoHeartbeat', 'resume',           '2026-07-02 10:01:10.000', 'android','1.0','IN','hin','none','p1','2026-07-02 10:00:00.000'),
(1, 502, 'D02_S1', 'U_D02', 'VideoHeartbeat', 'network-activity', '2026-07-02 10:01:30.000', 'android','1.0','IN','hin','none','p1','2026-07-02 10:00:00.000'),
(1, 502, 'D02_S1', 'U_D02', 'VideoHeartbeat', 'network-activity', '2026-07-02 10:01:50.000', 'android','1.0','IN','hin','none','p1','2026-07-02 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open, platform) VALUES
('D02_S1', '2026-07-02 10:00:00.000', '2026-07-02 10:00:40.000', 1, 'web'),
('D02_S1', '2026-07-02 10:01:10.000', '2026-07-02 10:02:50.000', 1, 'android');

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D02', toDateTime('2026-07-02 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D02', toDateTime('2026-07-02 10:00:00') + 60 * number, 'web', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D02', toDateTime('2026-07-02 10:00:00') + 60 * number, 'android', 0 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('D02', '2026-07-02 00:00:00', '2026-07-03 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- D03 · an unknown raw dimension map survives interval attribution intact.
--       The released video_resolution field is only an alias over that map.
-- BY HAND 3 beats at 40s cadence -> [10:00:00,10:02:20], open. The first
--         map appears twice, so it wins deterministically over the 1280 row.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version,
 session_start_epoch, extra)
VALUES
(1, 503, 'D03_S1', 'U_D03', 'VideoHeartbeat', 'network-activity', '2026-07-06 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-07-06 10:00:00.000', map('experiment_id','A','video_resolution','1920*1080')),
(1, 503, 'D03_S1', 'U_D03', 'VideoHeartbeat', 'video-resize',     '2026-07-06 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-07-06 10:00:00.000', map('experiment_id','A','video_resolution','1280*720')),
(1, 503, 'D03_S1', 'U_D03', 'VideoHeartbeat', 'network-activity', '2026-07-06 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-07-06 10:00:00.000', map('experiment_id','A','video_resolution','1920*1080'));

INSERT INTO edge_matrix.expected_intervals
(video_session_id, interval_start, interval_end, is_open, video_resolution, extra_dimensions)
VALUES
('D03_S1', '2026-07-06 10:00:00.000', '2026-07-06 10:02:20.000', 1,
 '1920*1080', map('experiment_id','A','video_resolution','1920*1080'));

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D03', toDateTime('2026-07-06 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('D03', '2026-07-06 00:00:00', '2026-07-07 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- D04 · dynamic keys vote independently, not as one composite Map.
-- Complete-map votes all tie, but per-key truth is experiment=A (2/3) and
-- resolution=720 (2/3). The middle event also reverses incoming key order;
-- derived map order is canonical and cannot affect the result.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version,
 session_start_epoch, extra)
VALUES
(1, 504, 'D04_S1', 'U_D04', 'VideoHeartbeat', 'network-activity', '2026-07-07 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-07-07 10:00:00.000', map('experiment_id','A','video_resolution','1080')),
(1, 504, 'D04_S1', 'U_D04', 'VideoHeartbeat', 'video-resize',     '2026-07-07 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-07-07 10:00:00.000', map('video_resolution','720','experiment_id','A')),
(1, 504, 'D04_S1', 'U_D04', 'VideoHeartbeat', 'network-activity', '2026-07-07 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-07-07 10:00:00.000', map('experiment_id','B','video_resolution','720'));

INSERT INTO edge_matrix.expected_intervals
(video_session_id, interval_start, interval_end, is_open, video_resolution, extra_dimensions)
VALUES
('D04_S1', '2026-07-07 10:00:00.000', '2026-07-07 10:02:20.000', 1,
 '720', map('experiment_id','A','video_resolution','720'));

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D04', toDateTime('2026-07-07 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('D04', '2026-07-07 00:00:00', '2026-07-08 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- D05 · missing and explicitly empty are distinct votes. One event omits
-- `cohort`; one carries cohort=''. The tie rule prefers presence, so the empty
-- value survives in the output Map instead of the key disappearing.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version,
 session_start_epoch, extra)
VALUES
(1, 505, 'D05_S1', 'U_D05', 'VideoHeartbeat', 'network-activity', '2026-07-08 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-07-08 10:00:00.000', map()),
(1, 505, 'D05_S1', 'U_D05', 'VideoHeartbeat', 'network-activity', '2026-07-08 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-07-08 10:00:00.000', map('cohort',''));

INSERT INTO edge_matrix.expected_intervals
(video_session_id, interval_start, interval_end, is_open, extra_dimensions)
VALUES
('D05_S1', '2026-07-08 10:00:00.000', '2026-07-08 10:01:40.000', 1,
 map('cohort',''));

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'D05', toDateTime('2026-07-08 10:00:00') + 60 * number, '*', 1 FROM numbers(2);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('D05', '2026-07-08 00:00:00', '2026-07-09 00:00:00', 0);
