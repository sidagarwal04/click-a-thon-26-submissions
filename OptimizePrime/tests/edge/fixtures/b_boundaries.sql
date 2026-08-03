-- ============================================================================
-- Family B — interval and bucket boundaries (Codex 003 §11.3)
-- Every expected value below is derived BY HAND from the spec:
--   run  = maximal event chain with gaps  > GAP_S (150 s), strict >  (ADR 0007)
--   pause window = [p, first resume >= p), unclosed -> run end (conservative)
--   tail = +60 s ONLY on a segment ending at the run end (interval-math skill)
--   minute membership = floor(start)..floor(end) INCLUSIVE — the shipped
--   floor(e)+60 close (doubts/05, doubts/09: the exact-boundary end minute IS
--   counted; a half-open mentor ruling would flip B02/B08 — flagged per fixture)
-- Dates: each fixture owns one UTC date in 2026-03 so minute windows are disjoint.
-- Constant dims unless stated: web / 1.0 / IN / hin / none / p1.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- B01 · start exactly on a minute boundary
-- EVENTS  beats 10:00:00.000, 10:00:40, 10:01:20, 10:02:00 (gaps 40 s)
-- BY HAND one run [10:00:00, 10:02:00]; no pauses; segment ends at run end so
--         tail +60 -> interval [10:00:00, 10:03:00]. Merged minute pair
--         (10:00, 10:03): +1@10:00, -1@10:04 -> minutes 10:00..10:03 cc=1.
--         The end 10:03:00 lands exactly on a boundary via the tail: minute
--         10:03 is counted under the shipped inclusive close.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 101, 'B01_S1', 'U_B01', 'VideoHeartbeat', 'network-activity', '2026-03-01 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-03-01 10:00:00.000'),
(1, 101, 'B01_S1', 'U_B01', 'VideoHeartbeat', 'network-activity', '2026-03-01 10:00:40.000', 'web','1.0','IN','hin','none','p1','2026-03-01 10:00:00.000'),
(1, 101, 'B01_S1', 'U_B01', 'VideoHeartbeat', 'network-activity', '2026-03-01 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-03-01 10:00:00.000'),
(1, 101, 'B01_S1', 'U_B01', 'VideoHeartbeat', 'network-activity', '2026-03-01 10:02:00.000', 'web','1.0','IN','hin','none','p1','2026-03-01 10:00:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B01_S1', '2026-03-01 10:00:00.000', '2026-03-01 10:03:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'B01', toDateTime('2026-03-01 10:00:00') + 60 * number, '*', 1 FROM numbers(4);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B01', '2026-03-01 00:00:00', '2026-03-02 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B02 · interior segment ending EXACTLY on a minute boundary (doubts/05 pin)
-- EVENTS  beats 10:00:30, 10:01:10; pause 10:02:00.000; beats 10:02:40, 10:03:20
-- BY HAND one run [10:00:30, 10:03:20] (gaps 40,50,40,40). Pause 10:02:00 has
--         no resume -> conservative window [10:02:00, run end]. One segment
--         (10:00:30, 10:02:00), ends at a pause -> NO tail.
--         Minute pair (10:00, 10:02): minutes 10:00, 10:01, 10:02 cc=1.
-- FORK    minute 10:02 holds ZERO active seconds; it is counted only because
--         the shipped close is floor(e)+60. A half-open ruling (doubts/05,
--         Codex 003 §12.3 Q11) would expect 10:00..10:01 only.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 102, 'B02_S1', 'U_B02', 'VideoHeartbeat', 'network-activity', '2026-03-02 10:00:30.000', 'web','1.0','IN','hin','none','p1','2026-03-02 10:00:30.000'),
(1, 102, 'B02_S1', 'U_B02', 'VideoHeartbeat', 'network-activity', '2026-03-02 10:01:10.000', 'web','1.0','IN','hin','none','p1','2026-03-02 10:00:30.000'),
(1, 102, 'B02_S1', 'U_B02', 'VideoHeartbeat', 'pause',            '2026-03-02 10:02:00.000', 'web','1.0','IN','hin','none','p1','2026-03-02 10:00:30.000'),
(1, 102, 'B02_S1', 'U_B02', 'VideoHeartbeat', 'network-activity', '2026-03-02 10:02:40.000', 'web','1.0','IN','hin','none','p1','2026-03-02 10:00:30.000'),
(1, 102, 'B02_S1', 'U_B02', 'VideoHeartbeat', 'network-activity', '2026-03-02 10:03:20.000', 'web','1.0','IN','hin','none','p1','2026-03-02 10:00:30.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B02_S1', '2026-03-02 10:00:30.000', '2026-03-02 10:02:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'B02', toDateTime('2026-03-02 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B02', '2026-03-02 00:00:00', '2026-03-03 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B03 · interval starts AND ends inside one minute
-- EVENTS  beat 10:00:10; pause 10:00:50; beats 10:01:30, 10:02:10
-- BY HAND one run [10:00:10, 10:02:10]. Unclosed pause 10:00:50 -> window to
--         run end. Segment (10:00:10, 10:00:50) only — both endpoints inside
--         minute 10:00, ends at a pause -> no tail. Minutes: 10:00 cc=1 only.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 103, 'B03_S1', 'U_B03', 'VideoHeartbeat', 'network-activity', '2026-03-03 10:00:10.000', 'web','1.0','IN','hin','none','p1','2026-03-03 10:00:10.000'),
(1, 103, 'B03_S1', 'U_B03', 'VideoHeartbeat', 'pause',            '2026-03-03 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-03-03 10:00:10.000'),
(1, 103, 'B03_S1', 'U_B03', 'VideoHeartbeat', 'network-activity', '2026-03-03 10:01:30.000', 'web','1.0','IN','hin','none','p1','2026-03-03 10:00:10.000'),
(1, 103, 'B03_S1', 'U_B03', 'VideoHeartbeat', 'network-activity', '2026-03-03 10:02:10.000', 'web','1.0','IN','hin','none','p1','2026-03-03 10:00:10.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B03_S1', '2026-03-03 10:00:10.000', '2026-03-03 10:00:50.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc) VALUES
('B03', '2026-03-03 10:00:00', '*', 1);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B03', '2026-03-03 00:00:00', '2026-03-04 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B04 · zero-length interval — isolated single events produce NOTHING
-- EVENTS  beat 10:00:00; beat 10:10:00 (gap 600 s > 150 -> two singleton runs)
-- BY HAND each singleton run yields segment (t, t), dropped by the x.2 > x.1
--         filter BEFORE tail credit is applied — a lone event earns no
--         interval, no tail, no minute. Expect ZERO intervals, ZERO minutes.
--         (The check is the "unexpected" arm of both comparisons.)
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 104, 'B04_S1', 'U_B04', 'VideoHeartbeat', 'network-activity', '2026-03-04 10:00:00.000', 'web','1.0','IN','hin','none','p1','2026-03-04 10:00:00.000'),
(1, 104, 'B04_S1', 'U_B04', 'VideoHeartbeat', 'network-activity', '2026-03-04 10:10:00.000', 'web','1.0','IN','hin','none','p1','2026-03-04 10:00:00.000');

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B04', '2026-03-04 00:00:00', '2026-03-05 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B05 · hour-boundary crossing + a gap of EXACTLY GAP_S (strict > pin)
-- EVENTS  beats 10:58:00; 11:00:30 (gap exactly 150 s); 11:02:00 (gap 90 s)
-- BY HAND gap comparison is strict >, so 150 does NOT split: one run
--         [10:58:00, 11:02:00], tail +60 -> interval [10:58:00, 11:03:00].
--         Minute pair (10:58, 11:03) spans two hours (ADR 0003 clipping):
--         hour 10: +1@10:58, no close (interval survives the hour)
--         hour 11: +1@11:00 re-open, -1@11:04
--         Minutes 10:58, 10:59 cc=1 and 11:00..11:03 cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 105, 'B05_S1', 'U_B05', 'VideoHeartbeat', 'network-activity', '2026-03-05 10:58:00.000', 'web','1.0','IN','hin','none','p1','2026-03-05 10:58:00.000'),
(1, 105, 'B05_S1', 'U_B05', 'VideoHeartbeat', 'network-activity', '2026-03-05 11:00:30.000', 'web','1.0','IN','hin','none','p1','2026-03-05 10:58:00.000'),
(1, 105, 'B05_S1', 'U_B05', 'VideoHeartbeat', 'network-activity', '2026-03-05 11:02:00.000', 'web','1.0','IN','hin','none','p1','2026-03-05 10:58:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B05_S1', '2026-03-05 10:58:00.000', '2026-03-05 11:03:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'B05', toDateTime('2026-03-05 10:58:00') + 60 * number, '*', 1 FROM numbers(6);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B05', '2026-03-05 00:00:00', '2026-03-06 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B06 · interval ends in the LAST minute of an hour — the suppressed close
-- EVENTS  beat 10:57:30; pause 10:59:10; beats 10:59:50, 11:00:30
-- BY HAND one run [10:57:30, 11:00:30]. Unclosed pause 10:59:10 -> window to
--         run end. Segment (10:57:30, 10:59:10), no tail. Minute pair
--         (10:57, 10:59): close would be 10:59+60 = 11:00 which is NOT inside
--         hour 10, so the -1 is NOT emitted (40_deltas edge case) — hour 11
--         must show NOTHING, not a stray -1. Minutes 10:57..10:59 cc=1,
--         and 11:00 cc=0 asserted explicitly.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 106, 'B06_S1', 'U_B06', 'VideoHeartbeat', 'network-activity', '2026-03-06 10:57:30.000', 'web','1.0','IN','hin','none','p1','2026-03-06 10:57:30.000'),
(1, 106, 'B06_S1', 'U_B06', 'VideoHeartbeat', 'pause',            '2026-03-06 10:59:10.000', 'web','1.0','IN','hin','none','p1','2026-03-06 10:57:30.000'),
(1, 106, 'B06_S1', 'U_B06', 'VideoHeartbeat', 'network-activity', '2026-03-06 10:59:50.000', 'web','1.0','IN','hin','none','p1','2026-03-06 10:57:30.000'),
(1, 106, 'B06_S1', 'U_B06', 'VideoHeartbeat', 'network-activity', '2026-03-06 11:00:30.000', 'web','1.0','IN','hin','none','p1','2026-03-06 10:57:30.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B06_S1', '2026-03-06 10:57:30.000', '2026-03-06 10:59:10.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'B06', toDateTime('2026-03-06 10:57:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc) VALUES
('B06', '2026-03-06 11:00:00', '*', 0);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B06', '2026-03-06 00:00:00', '2026-03-07 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B07 · interval crossing the UTC day boundary
-- EVENTS  beats 23:58:30, 23:59:50 (03-07); 00:01:10, 00:02:30 (03-08) — gaps 80 s
-- BY HAND one run, tail +60 -> interval [23:58:30, 00:03:30]. Hour 23: +1@23:58,
--         no close. Hour 00 (next day, next partition): +1@00:00, -1@00:04.
--         Minutes 23:58, 23:59 then 00:00..00:03, all cc=1.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 107, 'B07_S1', 'U_B07', 'VideoHeartbeat', 'network-activity', '2026-03-07 23:58:30.000', 'web','1.0','IN','hin','none','p1','2026-03-07 23:58:30.000'),
(1, 107, 'B07_S1', 'U_B07', 'VideoHeartbeat', 'network-activity', '2026-03-07 23:59:50.000', 'web','1.0','IN','hin','none','p1','2026-03-07 23:58:30.000'),
(1, 107, 'B07_S1', 'U_B07', 'VideoHeartbeat', 'network-activity', '2026-03-08 00:01:10.000', 'web','1.0','IN','hin','none','p1','2026-03-07 23:58:30.000'),
(1, 107, 'B07_S1', 'U_B07', 'VideoHeartbeat', 'network-activity', '2026-03-08 00:02:30.000', 'web','1.0','IN','hin','none','p1','2026-03-07 23:58:30.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B07_S1', '2026-03-07 23:58:30.000', '2026-03-08 00:03:30.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'B07', toDateTime('2026-03-07 23:58:00') + 60 * number, '*', 1 FROM numbers(6);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B07', '2026-03-07 00:00:00', '2026-03-09 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- B08 · interval ends EXACTLY on an hour boundary (doubts/05 at hour grain)
-- EVENTS  beat 10:58:00; pause 11:00:00.000; beats 11:00:40, 11:01:20
-- BY HAND one run [10:58:00, 11:01:20]. Unclosed pause exactly at 11:00:00 ->
--         window to run end. Segment (10:58:00, 11:00:00) ends at a pause ->
--         no tail. Minute pair (10:58, 11:00) spans both hours:
--         hour 10: +1@10:58, close 11:01 outside hour 10 -> suppressed
--         hour 11: +1@11:00 re-open, -1@11:01
--         Minutes 10:58, 10:59, 11:00 cc=1.
-- FORK    minute 11:00 holds zero active seconds (same inclusive-close fork as
--         B02, here interacting with the ADR 0003 hour re-open).
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 108, 'B08_S1', 'U_B08', 'VideoHeartbeat', 'network-activity', '2026-03-09 10:58:00.000', 'web','1.0','IN','hin','none','p1','2026-03-09 10:58:00.000'),
(1, 108, 'B08_S1', 'U_B08', 'VideoHeartbeat', 'pause',            '2026-03-09 11:00:00.000', 'web','1.0','IN','hin','none','p1','2026-03-09 10:58:00.000'),
(1, 108, 'B08_S1', 'U_B08', 'VideoHeartbeat', 'network-activity', '2026-03-09 11:00:40.000', 'web','1.0','IN','hin','none','p1','2026-03-09 10:58:00.000'),
(1, 108, 'B08_S1', 'U_B08', 'VideoHeartbeat', 'network-activity', '2026-03-09 11:01:20.000', 'web','1.0','IN','hin','none','p1','2026-03-09 10:58:00.000');

INSERT INTO edge_matrix.expected_intervals (video_session_id, interval_start, interval_end, is_open) VALUES
('B08_S1', '2026-03-09 10:58:00.000', '2026-03-09 11:00:00.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'B08', toDateTime('2026-03-09 10:58:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('B08', '2026-03-09 00:00:00', '2026-03-10 00:00:00', 0);
