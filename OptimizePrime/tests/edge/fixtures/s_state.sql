-- ============================================================================
-- Family S — state combinations (Codex 003 §11.2)
-- Pins the SHIPPED state semantics (ADR 0007, interval-math skill): liveness is
-- granted by every event including bg/fg (doubts/10, doubts/11 measure the
-- alternative); pause windows are the only explicit subtraction; trailing pause
-- vs interior pause differ in tail credit (doubts/07). Where a mentor ruling
-- would flip an expectation, the fixture header names the dossier.
-- Dates: 2026-04-xx, one per fixture. Constant dims: web/1.0/IN/hin/none/p1.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- S01 · pause, then background, then silence — interior pause earns NO tail
-- EVENTS  beats 10:00:00, 10:00:40; pause 10:01:00; AppBackgrounded 10:01:30
-- BY HAND the bg event RENEWS liveness (shipped fail-open reading), so the run
--         is [10:00:00, 10:01:30] and the pause at 10:01:00 is INTERIOR
--         (p < run end). Unclosed -> window to run end. Segment
--         (10:00:00, 10:01:00) ends at a pause -> no tail.
--         Minutes 10:00, 10:01 cc=1.
-- FORK    contrast with S06: remove the bg event and the same pause becomes
--         TRAILING and collects +60 tail — the doubts/07 perversity, pinned
--         from both sides.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 201, 'S01_S1', 'U_S01', 'VideoHeartbeat', 'network-activity', '2026-04-01 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-04-01 10:00:00.000'),
(1, 201, 'S01_S1', 'U_S01', 'VideoHeartbeat', 'network-activity', '2026-04-01 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-04-01 10:00:00.000'),
(1, 201, 'S01_S1', 'U_S01', 'VideoHeartbeat', 'pause',            '2026-04-01 10:01:00.000', 'web','1.0','IN','hin','none','p1','2026-04-01 10:00:00.000'),
(1, 201, 'S01_S1', 'U_S01', 'AppBackgrounded','AppBackgrounded',  '2026-04-01 10:01:30.000', 'web','1.0','IN','hin','none','p1','2026-04-01 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S01_S1', '2026-04-01 10:00:00.000', '2026-04-01 10:01:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'S01', toDateTime('2026-04-01 10:00:00') + 60 * number, '*', 1 FROM numbers(2);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S01', '2026-04-01 00:00:00', '2026-04-02 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- S02 · heartbeats DURING a pause do not reopen it — and the minute dips
-- EVENTS  beat 10:00:00; pause 10:00:30; beats 10:01:10, 10:01:50 (paused);
--         resume 10:02:30; beat 10:03:10
-- BY HAND one run [10:00:00, 10:03:10] (every gap <= 80 s). Pause window
--         [10:00:30, 10:02:30) — the two beats inside it keep the RUN alive
--         but must not count as watching (the ADR 0007 correction).
--         Segments: (10:00:00, 10:00:30) no tail; (10:02:30, 10:03:10) at run
--         end -> tail -> (10:02:30, 10:04:10).
--         Minute pairs (10:00,10:00) and (10:02,10:04) do NOT merge
--         (10:02 > 10:00 + 1 min): minutes 10:00 cc=1, 10:01 cc=0 (the dip,
--         asserted explicitly), 10:02..10:04 cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 202, 'S02_S1', 'U_S02', 'VideoHeartbeat', 'network-activity', '2026-04-02 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-04-02 10:00:00.000'),
(1, 202, 'S02_S1', 'U_S02', 'VideoHeartbeat', 'pause',            '2026-04-02 10:00:30.000', 'web','1.0','IN','hin','none','p1','2026-04-02 10:00:00.000'),
(1, 202, 'S02_S1', 'U_S02', 'VideoHeartbeat', 'network-activity', '2026-04-02 10:01:10.000', 'web','1.0','IN','hin','none','p1','2026-04-02 10:00:00.000'),
(1, 202, 'S02_S1', 'U_S02', 'VideoHeartbeat', 'network-activity', '2026-04-02 10:01:50.000', 'web','1.0','IN','hin','none','p1','2026-04-02 10:00:00.000'),
(1, 202, 'S02_S1', 'U_S02', 'VideoHeartbeat', 'resume',           '2026-04-02 10:02:30.000', 'web','1.0','IN','hin','none','p1','2026-04-02 10:00:00.000'),
(1, 202, 'S02_S1', 'U_S02', 'VideoHeartbeat', 'network-activity', '2026-04-02 10:03:10.000', 'web','1.0','IN','hin','none','p1','2026-04-02 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S02_S1', '2026-04-02 10:00:00.000', '2026-04-02 10:00:30.000', 1),
('S02_S1', '2026-04-02 10:02:30.000', '2026-04-02 10:04:10.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc) VALUES
('S02', '2026-04-02 10:00:00', '*', 1),
('S02', '2026-04-02 10:01:00', '*', 0),
('S02', '2026-04-02 10:02:00', '*', 1),
('S02', '2026-04-02 10:03:00', '*', 1),
('S02', '2026-04-02 10:04:00', '*', 1);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S02', '2026-04-02 00:00:00', '2026-04-03 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- S03 · unmatched resume (no prior pause) — no state effect, liveness only
-- EVENTS  beats 10:00:00, 10:00:40; resume 10:01:20; beat 10:02:00
-- BY HAND no pause exists, so the resume closes nothing and opens nothing; it
--         is one more liveness timestamp (doubts/02: resume also fires for
--         seeks/buffer recovery). One run + tail -> [10:00:00, 10:03:00].
--         Minutes 10:00..10:03 cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 203, 'S03_S1', 'U_S03', 'VideoHeartbeat', 'network-activity', '2026-04-03 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-04-03 10:00:00.000'),
(1, 203, 'S03_S1', 'U_S03', 'VideoHeartbeat', 'network-activity', '2026-04-03 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-04-03 10:00:00.000'),
(1, 203, 'S03_S1', 'U_S03', 'VideoHeartbeat', 'resume',           '2026-04-03 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-04-03 10:00:00.000'),
(1, 203, 'S03_S1', 'U_S03', 'VideoHeartbeat', 'network-activity', '2026-04-03 10:02:00.000', 'web','1.0','IN','hin','none','p1','2026-04-03 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S03_S1', '2026-04-03 10:00:00.000', '2026-04-03 10:03:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'S03', toDateTime('2026-04-03 10:00:00') + 60 * number, '*', 1 FROM numbers(4);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S03', '2026-04-03 00:00:00', '2026-04-04 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- S04 · repeated pause/pause then one resume — overlapping windows fold to one
-- EVENTS  beat 10:00:00; pause 10:00:40; pause 10:01:20; resume 10:02:00;
--         beat 10:02:40
-- BY HAND both pauses close at the SAME first resume >= p (10:02:00), giving
--         overlapping windows [10:00:40,10:02:00) and [10:01:20,10:02:00) —
--         the arrayFold complement must not double-subtract. Segments:
--         (10:00:00, 10:00:40) no tail; (10:02:00, 10:02:40) at run end ->
--         tail -> (10:02:00, 10:03:40). Minute pairs (10:00,10:00) and
--         (10:02,10:03) stay separate: 10:00 cc=1, 10:01 cc=0 (explicit),
--         10:02, 10:03 cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 204, 'S04_S1', 'U_S04', 'VideoHeartbeat', 'network-activity', '2026-04-04 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-04-04 10:00:00.000'),
(1, 204, 'S04_S1', 'U_S04', 'VideoHeartbeat', 'pause',            '2026-04-04 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-04-04 10:00:00.000'),
(1, 204, 'S04_S1', 'U_S04', 'VideoHeartbeat', 'pause',            '2026-04-04 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-04-04 10:00:00.000'),
(1, 204, 'S04_S1', 'U_S04', 'VideoHeartbeat', 'resume',           '2026-04-04 10:02:00.000', 'web','1.0','IN','hin','none','p1','2026-04-04 10:00:00.000'),
(1, 204, 'S04_S1', 'U_S04', 'VideoHeartbeat', 'network-activity', '2026-04-04 10:02:40.000', 'web','1.0','IN','hin','none','p1','2026-04-04 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S04_S1', '2026-04-04 10:00:00.000', '2026-04-04 10:00:40.000', 1),
('S04_S1', '2026-04-04 10:02:00.000', '2026-04-04 10:03:40.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc) VALUES
('S04', '2026-04-04 10:00:00', '*', 1),
('S04', '2026-04-04 10:01:00', '*', 0),
('S04', '2026-04-04 10:02:00', '*', 1),
('S04', '2026-04-04 10:03:00', '*', 1);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S04', '2026-04-04 00:00:00', '2026-04-05 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- S06 · TRAILING pause (last event of its run) — collects the +60 tail
-- EVENTS  beats 10:00:00, 10:00:40; pause 10:01:00; then silence
-- BY HAND run [10:00:00, 10:01:00]. The pause filter keeps only p < run end,
--         so a pause AT the run end is not a window; the segment ends at the
--         run end and is granted the tail: interval [10:00:00, 10:02:00].
--         Minutes 10:00..10:02 cc=1.
-- FORK    doubts/07 measured this at -141 peak / -4.8% if a mentor rules that
--         an explicit stop gets no tail. This fixture pins the SHIPPED reading
--         (60 s of credit AFTER an explicit pause); S01 pins the interior
--         complement. If the ruling flips, flip this expectation with it.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 205, 'S06_S1', 'U_S06', 'VideoHeartbeat', 'network-activity', '2026-04-05 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-04-05 10:00:00.000'),
(1, 205, 'S06_S1', 'U_S06', 'VideoHeartbeat', 'network-activity', '2026-04-05 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-04-05 10:00:00.000'),
(1, 205, 'S06_S1', 'U_S06', 'VideoHeartbeat', 'pause',            '2026-04-05 10:01:00.000', 'web','1.0','IN','hin','none','p1','2026-04-05 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S06_S1', '2026-04-05 10:00:00.000', '2026-04-05 10:02:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'S06', toDateTime('2026-04-05 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S06', '2026-04-05 00:00:00', '2026-04-06 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- S07 · bg/fg events BRIDGE what would otherwise be gaps (fail-open pin)
-- EVENTS  beat 10:00:00; AppBackgrounded 10:02:20; AppForegrounded 10:04:40;
--         beat 10:07:00 — consecutive gaps all exactly 140 s (< 150)
-- BY HAND shipped model: EVERY event renews liveness, so this is ONE run
--         [10:00:00, 10:07:00] + tail -> [10:00:00, 10:08:00], minutes
--         10:00..10:08 cc=1 — nine minutes credited on ONE real heartbeat,
--         most of them provably backgrounded.
-- FORK    doubts/10 (fail-closed gates: -10.7% peak) and doubts/11 (allow-list
--         liveness) both attack exactly this. The fixture pins the SHIPPED
--         fail-open reading so any silent change of semantics is caught; a
--         mentor ruling for either dossier means rewriting this expectation.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 206, 'S07_S1', 'U_S07', 'VideoHeartbeat', 'network-activity', '2026-04-06 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-04-06 10:00:00.000'),
(1, 206, 'S07_S1', 'U_S07', 'AppBackgrounded','AppBackgrounded',  '2026-04-06 10:02:20.000', 'web','1.0','IN','hin','none','p1','2026-04-06 10:00:00.000'),
(1, 206, 'S07_S1', 'U_S07', 'AppForegrounded','AppForegrounded',  '2026-04-06 10:04:40.000', 'web','1.0','IN','hin','none','p1','2026-04-06 10:00:00.000'),
(1, 206, 'S07_S1', 'U_S07', 'VideoHeartbeat', 'network-activity', '2026-04-06 10:07:00.000', 'web','1.0','IN','hin','none','p1','2026-04-06 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S07_S1', '2026-04-06 10:00:00.000', '2026-04-06 10:08:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'S07', toDateTime('2026-04-06 10:00:00') + 60 * number, '*', 1 FROM numbers(9);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S07', '2026-04-06 00:00:00', '2026-04-07 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- S08 · pause AND resume inside one minute — the same-minute merge (44% of
--       real sessions hit this; the bug /reconcile caught: 556 minutes wrong)
-- EVENTS  beat 10:00:10; pause 10:00:30; resume 10:00:50; beat 10:01:30
-- BY HAND run [10:00:10, 10:01:30]; window [10:00:30, 10:00:50). Segments
--         (10:00:10, 10:00:30) and (10:00:50, 10:01:30)+tail -> 10:02:30.
--         Two intervals, but ONE viewer: minute pairs (10:00,10:00) and
--         (10:00,10:02) MERGE in 40_deltas, so minute 10:00 gets ONE +1,
--         never two. Minutes 10:00..10:02 cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 207, 'S08_S1', 'U_S08', 'VideoHeartbeat', 'network-activity', '2026-04-07 10:00:10.000', 'web','1.0','IN','hin','none','p1','2026-04-07 10:00:10.000'),
(1, 207, 'S08_S1', 'U_S08', 'VideoHeartbeat', 'pause',            '2026-04-07 10:00:30.000', 'web','1.0','IN','hin','none','p1','2026-04-07 10:00:10.000'),
(1, 207, 'S08_S1', 'U_S08', 'VideoHeartbeat', 'resume',           '2026-04-07 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-04-07 10:00:10.000'),
(1, 207, 'S08_S1', 'U_S08', 'VideoHeartbeat', 'network-activity', '2026-04-07 10:01:30.000', 'web','1.0','IN','hin','none','p1','2026-04-07 10:00:10.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('S08_S1', '2026-04-07 10:00:10.000', '2026-04-07 10:00:30.000', 1),
('S08_S1', '2026-04-07 10:00:50.000', '2026-04-07 10:02:30.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'S08', toDateTime('2026-04-07 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('S08', '2026-04-07 00:00:00', '2026-04-08 00:00:00', 0);
