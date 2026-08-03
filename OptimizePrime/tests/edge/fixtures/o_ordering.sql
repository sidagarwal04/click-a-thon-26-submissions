-- ============================================================================
-- Family O — event ordering and identity (Codex 003 §11.1)
-- ADR 0009 exists because of a real bug in this family (the same-second
-- pause/resume tie). These fixtures pin: second-truncation tie handling, batch
-- order independence, non-terminal VideoSessionEnd, duplicate-row harmlessness,
-- and multiple end events. Millisecond-ordering semantics (doubts/08) remain a
-- FORK — the fixtures pin the shipped truncated-second reading.
-- Dates: 2026-05-xx, one per fixture. Constant dims: web/1.0/IN/hin/none/p1.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- O01 · resume BEFORE pause inside one truncated second (ADR 0009 pin)
-- EVENTS  beat 10:00:00; resume 10:01:00.100; pause 10:01:00.900;
--         beats 10:01:40, 10:02:20
-- BY HAND timestamps truncate to whole seconds, so pause and resume BOTH land
--         on 10:01:00 — in true millisecond order the resume came FIRST, i.e.
--         this pause has no later resume at all. The shipped `>=` lookup finds
--         the same-second resume, yields a zero-length window (p, p), and the
--         w.2 > w.1 filter drops it: the pause has NO effect. One run + tail
--         -> interval [10:00:00, 10:03:20], minutes 10:00..10:03 cc=1.
-- FORK    doubts/08: millisecond-precise processing would treat the pause as
--         unclosed (paused to run end) -> interval [10:00:00, 10:01:00.9],
--         measured -52 peak / -1.8% on the real file. Pinned to SHIPPED.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 301, 'O01_S1', 'U_O01', 'VideoHeartbeat', 'network-activity', '2026-05-01 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-05-01 10:00:00.000'),
(1, 301, 'O01_S1', 'U_O01', 'VideoHeartbeat', 'resume',           '2026-05-01 10:01:00.100', 'web','1.0','IN','hin','none','p1','2026-05-01 10:00:00.000'),
(1, 301, 'O01_S1', 'U_O01', 'VideoHeartbeat', 'pause',            '2026-05-01 10:01:00.900', 'web','1.0','IN','hin','none','p1','2026-05-01 10:00:00.000'),
(1, 301, 'O01_S1', 'U_O01', 'VideoHeartbeat', 'network-activity', '2026-05-01 10:01:40.000', 'web','1.0','IN','hin','none','p1','2026-05-01 10:00:00.000'),
(1, 301, 'O01_S1', 'U_O01', 'VideoHeartbeat', 'network-activity', '2026-05-01 10:02:20.000', 'web','1.0','IN','hin','none','p1','2026-05-01 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('O01_S1', '2026-05-01 10:00:00.000', '2026-05-01 10:03:20.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'O01', toDateTime('2026-05-01 10:00:00') + 60 * number, '*', 1 FROM numbers(4);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('O01', '2026-05-01 00:00:00', '2026-05-02 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- O02 · out-of-order ARRIVAL — same events inserted newest-first
-- EVENTS  beats 10:02:00, 10:01:20, 10:00:40, 10:00:00 (this insert order)
-- BY HAND the batch derivation arraySorts per session, so arrival order must
--         not matter: identical to the B01 shape — run [10:00:00, 10:02:00]
--         + tail -> [10:00:00, 10:03:00], minutes 10:00..10:03 cc=1.
--         (Streaming/publisher arrival-order effects are publish-test.sh
--         territory; this pins the BATCH property only.)
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 302, 'O02_S1', 'U_O02', 'VideoHeartbeat', 'network-activity', '2026-05-02 10:02:00.000', 'web','1.0','IN','hin','none','p1','2026-05-02 10:00:00.000'),
(1, 302, 'O02_S1', 'U_O02', 'VideoHeartbeat', 'network-activity', '2026-05-02 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-05-02 10:00:00.000'),
(1, 302, 'O02_S1', 'U_O02', 'VideoHeartbeat', 'network-activity', '2026-05-02 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-05-02 10:00:00.000'),
(1, 302, 'O02_S1', 'U_O02', 'VideoHeartbeat', 'network-activity', '2026-05-02 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-05-02 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('O02_S1', '2026-05-02 10:00:00.000', '2026-05-02 10:03:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'O02', toDateTime('2026-05-02 10:00:00') + 60 * number, '*', 1 FROM numbers(4);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('O02', '2026-05-02 00:00:00', '2026-05-03 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- O03 · events AFTER VideoSessionEnd — end is not terminal (shipped reading)
-- EVENTS  beats 10:00:00, 10:00:40; VideoSessionEnd 10:01:20; beat 10:02:40
--         (80 s after the end — inside GAP_S, so the run continues)
-- BY HAND the end event is liveness like any other and does NOT close the run;
--         it only sets is_open = 0. One run [10:00:00, 10:02:40] + tail ->
--         interval [10:00:00, 10:03:40], is_open = 0. Minutes 10:00..10:03.
-- FORK    doubts/07 / evidence/liveness Q2: end-is-terminal would clip at
--         10:01:20 (measured -119 peak on the real file). Pinned to SHIPPED.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 303, 'O03_S1', 'U_O03', 'VideoHeartbeat',  'network-activity', '2026-05-03 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-05-03 10:00:00.000'),
(1, 303, 'O03_S1', 'U_O03', 'VideoHeartbeat',  'network-activity', '2026-05-03 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-05-03 10:00:00.000'),
(1, 303, 'O03_S1', 'U_O03', 'VideoSessionEnd', 'VideoSessionEnd',  '2026-05-03 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-05-03 10:00:00.000'),
(1, 303, 'O03_S1', 'U_O03', 'VideoHeartbeat',  'network-activity', '2026-05-03 10:02:40.000', 'web','1.0','IN','hin','none','p1','2026-05-03 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('O03_S1', '2026-05-03 10:00:00.000', '2026-05-03 10:03:40.000', 0);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'O03', toDateTime('2026-05-03 10:00:00') + 60 * number, '*', 1 FROM numbers(4);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('O03', '2026-05-03 00:00:00', '2026-05-04 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- O04 · exact duplicate rows — harmless to the derivation
-- EVENTS  beats 10:00:00 x2 (identical rows), 10:00:40 x2, 10:01:20
-- BY HAND duplicate timestamps produce 0-length gaps, split nothing, and move
--         no lookup (adversarial ledger row 18); identical payloads cannot
--         shift a dominant-dimension vote. Run [10:00:00, 10:01:20] + tail ->
--         interval [10:00:00, 10:02:20], minutes 10:00..10:02 cc=1.
--         (Replay of a whole INSERT block is a dedup/ops concern —
--         load-guard/publish-test territory, not this fixture's.)
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 304, 'O04_S1', 'U_O04', 'VideoHeartbeat', 'network-activity', '2026-05-04 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-05-04 10:00:00.000'),
(1, 304, 'O04_S1', 'U_O04', 'VideoHeartbeat', 'network-activity', '2026-05-04 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-05-04 10:00:00.000'),
(1, 304, 'O04_S1', 'U_O04', 'VideoHeartbeat', 'network-activity', '2026-05-04 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-05-04 10:00:00.000'),
(1, 304, 'O04_S1', 'U_O04', 'VideoHeartbeat', 'network-activity', '2026-05-04 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-05-04 10:00:00.000'),
(1, 304, 'O04_S1', 'U_O04', 'VideoHeartbeat', 'network-activity', '2026-05-04 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-05-04 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('O04_S1', '2026-05-04 10:00:00.000', '2026-05-04 10:02:20.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'O04', toDateTime('2026-05-04 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('O04', '2026-05-04 00:00:00', '2026-05-05 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- O05 · multiple VideoSessionEnd events + a lone restart beyond the gap
-- EVENTS  beat 10:00:00; end 10:00:40; end 10:01:00; beat 10:09:00
-- BY HAND two end events are fine (14 real sessions carry several); is_open=0.
--         Run 1 = [10:00:00, 10:01:00] (both ends inside) + tail ->
--         [10:00:00, 10:02:00]. The 10:09:00 restart is 480 s away -> its own
--         SINGLETON run -> dropped (B04 rule): no interval at 10:09, asserted
--         via expected_no_interval and the 10:09 cc=0 row.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 305, 'O05_S1', 'U_O05', 'VideoHeartbeat',  'network-activity', '2026-05-05 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-05-05 10:00:00.000'),
(1, 305, 'O05_S1', 'U_O05', 'VideoSessionEnd', 'VideoSessionEnd',  '2026-05-05 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-05-05 10:00:00.000'),
(1, 305, 'O05_S1', 'U_O05', 'VideoSessionEnd', 'VideoSessionEnd',  '2026-05-05 10:01:00.000', 'web','1.0','IN','hin','none','p1','2026-05-05 10:00:00.000'),
(1, 305, 'O05_S1', 'U_O05', 'VideoHeartbeat',  'network-activity', '2026-05-05 10:09:00.000', 'web','1.0','IN','hin','none','p1','2026-05-05 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('O05_S1', '2026-05-05 10:00:00.000', '2026-05-05 10:02:00.000', 0);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'O05', toDateTime('2026-05-05 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc) VALUES
('O05', '2026-05-05 10:09:00', '*', 0);

INSERT INTO edge_matrix.expected_no_interval (video_session_id, interval_start) VALUES
('O05_S1', '2026-05-05 10:09:00.000');

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('O05', '2026-05-05 00:00:00', '2026-05-06 00:00:00', 0);
