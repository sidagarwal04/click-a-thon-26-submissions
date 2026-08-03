-- ============================================================================
-- Family U — exact user concurrency and its non-additivity
--
-- These fixtures close the user-tier gap named in docs/TESTS.md §H. Expected
-- values are derived by hand from the active intervals, then counted as
-- distinct user_id values per minute. They deliberately prove that session
-- concurrency and user concurrency are different metrics and that neither
-- `users <= sessions` nor summing per-dimension user counts is a universal law.
-- Dates: 2026-07-03 through 2026-07-05. Constant non-platform dimensions.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- U01 · one user, two simultaneous sessions, same dimension tuple
-- EVENTS  each session has beats at 10:00:10 and 10:00:50
-- BY HAND each interval is [10:00:10, 10:01:50], covering 10:00 and 10:01.
--         Session concurrency is 2. Distinct-user concurrency is 1 because
--         both sessions belong to the same user in the same bucket.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 601, 'U01_S1', 'U_SHARED', 'VideoHeartbeat', 'network-activity', '2026-07-03 10:00:10.000', 'web','1.0','IN','hin','none','p1','2026-07-03 10:00:10.000'),
(1, 601, 'U01_S1', 'U_SHARED', 'VideoHeartbeat', 'network-activity', '2026-07-03 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-07-03 10:00:10.000'),
(1, 601, 'U01_S2', 'U_SHARED', 'VideoHeartbeat', 'network-activity', '2026-07-03 10:00:10.000', 'web','1.0','IN','hin','none','p1','2026-07-03 10:00:10.000'),
(1, 601, 'U01_S2', 'U_SHARED', 'VideoHeartbeat', 'network-activity', '2026-07-03 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-07-03 10:00:10.000');

INSERT INTO edge_matrix.expected_intervals
(video_session_id, interval_start, interval_end, is_open) VALUES
('U01_S1', '2026-07-03 10:00:10.000', '2026-07-03 10:01:50.000', 1),
('U01_S2', '2026-07-03 10:00:10.000', '2026-07-03 10:01:50.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'U01', toDateTime('2026-07-03 10:00:00') + 60 * number, '*', 2 FROM numbers(2);

INSERT INTO edge_matrix.expected_user_minutes (fixture, minute, platform, users)
SELECT 'U01', toDateTime('2026-07-03 10:00:00') + 60 * number, '*', 1 FROM numbers(2);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('U01', '2026-07-03 00:00:00', '2026-07-04 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- U02 · one user, two sessions on different platforms
-- EVENTS  same geometry as U01; one web session and one tv session
-- BY HAND total sessions=2, total distinct users=1. Per platform sessions=1
--         and users=1. Summing the two per-platform user counts gives 2 and is
--         therefore WRONG for the all-platform total, which must re-merge the
--         underlying uniqExact states.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 602, 'U02_S1', 'U_CROSS_DIM', 'VideoHeartbeat', 'network-activity', '2026-07-04 10:00:10.000', 'web','1.0','IN','hin','none','p1','2026-07-04 10:00:10.000'),
(1, 602, 'U02_S1', 'U_CROSS_DIM', 'VideoHeartbeat', 'network-activity', '2026-07-04 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-07-04 10:00:10.000'),
(1, 602, 'U02_S2', 'U_CROSS_DIM', 'VideoHeartbeat', 'network-activity', '2026-07-04 10:00:10.000', 'tv','1.0','IN','hin','none','p1','2026-07-04 10:00:10.000'),
(1, 602, 'U02_S2', 'U_CROSS_DIM', 'VideoHeartbeat', 'network-activity', '2026-07-04 10:00:50.000', 'tv','1.0','IN','hin','none','p1','2026-07-04 10:00:10.000');

INSERT INTO edge_matrix.expected_intervals
(video_session_id, interval_start, interval_end, is_open, platform) VALUES
('U02_S1', '2026-07-04 10:00:10.000', '2026-07-04 10:01:50.000', 1, 'web'),
('U02_S2', '2026-07-04 10:00:10.000', '2026-07-04 10:01:50.000', 1, 'tv');

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'U02', toDateTime('2026-07-04 10:00:00') + 60 * number, '*', 2 FROM numbers(2);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'U02', toDateTime('2026-07-04 10:00:00') + 60 * number, 'web', 1 FROM numbers(2);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'U02', toDateTime('2026-07-04 10:00:00') + 60 * number, 'tv', 1 FROM numbers(2);

INSERT INTO edge_matrix.expected_user_minutes (fixture, minute, platform, users)
SELECT 'U02', toDateTime('2026-07-04 10:00:00') + 60 * number, '*', 1 FROM numbers(2);

INSERT INTO edge_matrix.expected_user_minutes (fixture, minute, platform, users)
SELECT 'U02', toDateTime('2026-07-04 10:00:00') + 60 * number, 'web', 1 FROM numbers(2);

INSERT INTO edge_matrix.expected_user_minutes (fixture, minute, platform, users)
SELECT 'U02', toDateTime('2026-07-04 10:00:00') + 60 * number, 'tv', 1 FROM numbers(2);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('U02', '2026-07-04 00:00:00', '2026-07-05 00:00:00', 0);

-- ---------------------------------------------------------------------------
-- U03 · one session id legitimately carries two users across a pause boundary
-- EVENTS  user A beat 10:00:10, pause 10:00:30; user B resumes 10:00:50 and
--         beats 10:01:20
-- BY HAND the active segments are A [10:00:10,10:00:30] and B
--         [10:00:50,10:02:20] after tail. At session grain their minute ranges
--         touch and merge, so one session covers 10:00..10:02. At user grain
--         A and B remain distinct identities: 2 users at 10:00, then B only.
--         This is why `users <= sessions` is not a valid invariant when one
--         session id carries multiple user ids. The delivered file has nine
--         such session ids in active interval state, so this is not synthetic
--         fantasy; grouping the user fold only by session erases a viewer.
-- ---------------------------------------------------------------------------
INSERT INTO edge_matrix.ev_raw
(batch, content_id, video_session_id, user_id, event_type, event, event_timestamp,
 platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch)
VALUES
(1, 603, 'U03_S1', 'U_A', 'VideoHeartbeat', 'network-activity', '2026-07-05 10:00:10.000', 'web','1.0','IN','hin','none','p1','2026-07-05 10:00:10.000'),
(1, 603, 'U03_S1', 'U_A', 'VideoHeartbeat', 'pause',            '2026-07-05 10:00:30.000', 'web','1.0','IN','hin','none','p1','2026-07-05 10:00:10.000'),
(1, 603, 'U03_S1', 'U_B', 'VideoHeartbeat', 'resume',           '2026-07-05 10:00:50.000', 'web','1.0','IN','hin','none','p1','2026-07-05 10:00:10.000'),
(1, 603, 'U03_S1', 'U_B', 'VideoHeartbeat', 'network-activity', '2026-07-05 10:01:20.000', 'web','1.0','IN','hin','none','p1','2026-07-05 10:00:10.000');

INSERT INTO edge_matrix.expected_intervals
(video_session_id, interval_start, interval_end, is_open) VALUES
('U03_S1', '2026-07-05 10:00:10.000', '2026-07-05 10:00:30.000', 1),
('U03_S1', '2026-07-05 10:00:50.000', '2026-07-05 10:02:20.000', 1);

INSERT INTO edge_matrix.expected_minutes (fixture, minute, platform, cc)
SELECT 'U03', toDateTime('2026-07-05 10:00:00') + 60 * number, '*', 1 FROM numbers(3);

INSERT INTO edge_matrix.expected_user_minutes (fixture, minute, platform, users) VALUES
('U03', '2026-07-05 10:00:00', '*', 2),
('U03', '2026-07-05 10:01:00', '*', 1),
('U03', '2026-07-05 10:02:00', '*', 1);

INSERT INTO edge_matrix.fixture_span (fixture, t_from, t_to, is_late) VALUES
('U03', '2026-07-05 00:00:00', '2026-07-06 00:00:00', 0);
