-- ============================================================================
-- Family L — late data and the correction-by-diff algebra (Codex 003 §11.4)
-- batch=1 is the world BEFORE the late events; batch=2 arrives late. The
-- harness builds both worlds through the REAL derivation, emits the ADR 0006
-- correction (negate every old row, append every new row, one block), and
-- asserts old + (-old + new) lands on the HAND-DERIVED final truth — including
-- minutes and dimension tuples that must NET TO ZERO because they exist only
-- on the old side. What is NOT tested here: the publisher's claim protocol,
-- fencing, crash points, TTLs (tools/publish-test.sh territory).
-- Dates: 2026-06-xx. Constant dims web/1.0/IN/hin/none/p1 except L04.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- L01 · late heartbeat EXTENDS an interval
-- OLD     beats 10:00:00, 10:00:40 -> run + tail -> [10:00:00, 10:01:40],
--         minutes 10:00, 10:01
-- LATE    beat 10:01:20
-- BY HAND final run [10:00:00, 10:01:20] + tail -> [10:00:00, 10:02:20].
--         Final minutes 10:00..10:02 cc=1; the correction must add exactly
--         minute 10:02 and move the close.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 401, 'L01_S1', 'U_L01', 'VideoHeartbeat', 'network-activity', '2026-06-01 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-06-01 10:00:00.000'),
(1, 401, 'L01_S1', 'U_L01', 'VideoHeartbeat', 'network-activity', '2026-06-01 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-06-01 10:00:00.000'),
(2, 401, 'L01_S1', 'U_L01', 'VideoHeartbeat', 'network-activity', '2026-06-01 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-06-01 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('L01_S1', '2026-06-01 10:00:00.000', '2026-06-01 10:02:20.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'L01', toDateTime('2026-06-01 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('L01', '2026-06-01 00:00:00', '2026-06-02 00:00:00', 1);

-- ---------------------------------------------------------------------------
-- L02 · late pause SHRINKS an interval — vanished minutes must net to zero
-- OLD     beats 10:00:00, 10:00:40, 10:01:20, 10:02:00 -> [10:00:00, 10:03:00],
--         minutes 10:00..10:03
-- LATE    pause 10:00:50 (no resume ever)
-- BY HAND final: unclosed pause -> conservative window [10:00:50, run end];
--         one segment (10:00:00, 10:00:50), ends at a pause -> no tail.
--         Interval [10:00:00, 10:00:50]; ONLY minute 10:00 cc=1. Minutes
--         10:01..10:03 exist only in the old world and must come back to 0 —
--         the correction that forgets vanished minutes serves them for ever
--         (the CORRMODE=drop-vanished sabotage proves this fixture catches it).
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 402, 'L02_S1', 'U_L02', 'VideoHeartbeat', 'network-activity', '2026-06-02 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-06-02 10:00:00.000'),
(1, 402, 'L02_S1', 'U_L02', 'VideoHeartbeat', 'network-activity', '2026-06-02 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-06-02 10:00:00.000'),
(1, 402, 'L02_S1', 'U_L02', 'VideoHeartbeat', 'network-activity', '2026-06-02 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-06-02 10:00:00.000'),
(1, 402, 'L02_S1', 'U_L02', 'VideoHeartbeat', 'network-activity', '2026-06-02 10:02:00.000', 'web','1.0','IN','hin','none','p1','2026-06-02 10:00:00.000'),
(2, 402, 'L02_S1', 'U_L02', 'VideoHeartbeat', 'pause',            '2026-06-02 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-06-02 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('L02_S1', '2026-06-02 10:00:00.000', '2026-06-02 10:00:50.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc) VALUES
('L02', '2026-06-02 10:00:00', '*', 1),
('L02', '2026-06-02 10:01:00', '*', 0),
('L02', '2026-06-02 10:02:00', '*', 0),
('L02', '2026-06-02 10:03:00', '*', 0);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('L02', '2026-06-02 00:00:00', '2026-06-03 00:00:00', 1);

-- ---------------------------------------------------------------------------
-- L03 · late events BRIDGE two runs — a logical interval VANISHES
-- OLD     beats 10:00:00, 10:00:40 | gap 320 s | beats 10:06:00, 10:06:40
--         -> two intervals [10:00:00, 10:01:40] and [10:06:00, 10:07:40]
-- LATE    beats 10:03:00, 10:05:20 (every gap now <= 140 s)
-- BY HAND final: ONE run [10:00:00, 10:06:40] + tail -> [10:00:00, 10:07:40].
--         The old interval keyed (L03_S1, 10:06:00) no longer exists — in the
--         fresh rebuild trivially absent (asserted for the contract); in
--         production the ReplacingMergeTree orphan needs the publisher's prune
--         phase, which publish-test.sh proves. Minutes 10:00..10:07 cc=1;
--         the correction must fill 10:02..10:05 and remove nothing.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 403, 'L03_S1', 'U_L03', 'VideoHeartbeat', 'network-activity', '2026-06-03 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-06-03 10:00:00.000'),
(1, 403, 'L03_S1', 'U_L03', 'VideoHeartbeat', 'network-activity', '2026-06-03 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-06-03 10:00:00.000'),
(1, 403, 'L03_S1', 'U_L03', 'VideoHeartbeat', 'network-activity', '2026-06-03 10:06:00.000', 'web','1.0','IN','hin','none','p1','2026-06-03 10:00:00.000'),
(1, 403, 'L03_S1', 'U_L03', 'VideoHeartbeat', 'network-activity', '2026-06-03 10:06:40.000', 'web','1.0','IN','hin','none','p1','2026-06-03 10:00:00.000'),
(2, 403, 'L03_S1', 'U_L03', 'VideoHeartbeat', 'network-activity', '2026-06-03 10:03:00.000', 'web','1.0','IN','hin','none','p1','2026-06-03 10:00:00.000'),
(2, 403, 'L03_S1', 'U_L03', 'VideoHeartbeat', 'network-activity', '2026-06-03 10:05:20.000', 'web','1.0','IN','hin','none','p1','2026-06-03 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('L03_S1', '2026-06-03 10:00:00.000', '2026-06-03 10:07:40.000', 1);

INSERT INTO edge_matrix.expected_no_interval (video_session_id, interval_start) VALUES
('L03_S1', '2026-06-03 10:06:00.000');

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'L03', toDateTime('2026-06-03 10:00:00') + 60 * number, '*', 1 FROM numbers(8);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('L03', '2026-06-03 00:00:00', '2026-06-04 00:00:00', 1);

-- ---------------------------------------------------------------------------
-- L04 · late events FLIP the dominant dimension without moving time
-- OLD     web beats 10:00:00, 10:00:40, 10:01:20 -> [10:00:00, 10:02:20] web
-- LATE    android beats 10:00:20, 10:00:50, 10:01:00, 10:01:10
-- BY HAND final: same run [10:00:00, 10:01:20] + tail, same boundaries, but
--         the vote is now android 4 : web 3 -> the interval and every minute
--         row re-attribute to android. Per-platform truth: android 10:00..10:02
--         cc=1, web 0 everywhere (explicit rows). The correction must net the
--         old web tuple to zero — a diff keyed only on new-side tuples leaves
--         a phantom web viewer (caught by the drop-vanished sabotage too).
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000'),
(1, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000'),
(1, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000'),
(2, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:00:20.000', 'android','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000'),
(2, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:00:50.000', 'android','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000'),
(2, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:01:00.000', 'android','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000'),
(2, 404, 'L04_S1', 'U_L04', 'VideoHeartbeat', 'network-activity', '2026-06-04 10:01:10.000', 'android','1.0','IN','hin','none','p1','2026-06-04 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open, platform) VALUES
('L04_S1', '2026-06-04 10:00:00.000', '2026-06-04 10:02:20.000', 1, 'android');

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'L04', toDateTime('2026-06-04 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'L04', toDateTime('2026-06-04 10:00:00') + 60 * number, 'android', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'L04', toDateTime('2026-06-04 10:00:00') + 60 * number, 'web', 0 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('L04', '2026-06-04 00:00:00', '2026-06-05 00:00:00', 1);
