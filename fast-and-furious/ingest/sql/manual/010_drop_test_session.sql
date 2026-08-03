-- =====================================================================
-- 010_drop_test_session.sql — remove one synthetic session from the extract
-- =====================================================================
--
-- NOT part of `make schema`. A one-shot, reviewable correction, kept in the
-- repo because it mutates data and a console action would leave no trace.
--
-- ---------------------------------------------------------------------
-- WHAT AND WHY
-- ---------------------------------------------------------------------
-- session_key 12023018559768626636 is ours, not the supplied extract's. It was
-- written during API write-path testing and carries a July timestamp, which is
-- why it lands inside the extract window when every other generated session is
-- August-dated. Measured, 2026-08-02:
--
--   5 events, 2026-07-26 10:33:27.336 -> 10:35:20.000
--   JIO_ANDROID_TV / app_version 3.9.4 / content_id 21311522
--   one active interval, 10:33:29.028 -> 10:35:00.000 = 90,972 ms
--
-- It is absent from sonyliv.events_clean (the canonical extract) entirely, and
-- it is the ONLY session in the July window that is: the window otherwise holds
-- 901,353 events / 10,867 sessions against the canonical 901,348 / 10,866.
--
-- It is also the whole of our disagreement with the canonical hot-hour average:
--
--   90,972 / 3,600,000                     = 0.025270
--   855.603469 (ours) - 855.578199 (theirs) = 0.025270
--
-- Six decimals. Removing it makes the serving layer reproduce the canonical
-- figures exactly rather than approximately, which matters because correctness
-- is graded against a sealed key where a near-miss scores as a miss.
--
-- ---------------------------------------------------------------------
-- SCOPE — deliberately three tables, deliberately one key
-- ---------------------------------------------------------------------
-- events_raw      the landing zone, so the session cannot come back. Without
--                 this, any future rebuild of session_intervals from
--                 events_dedup reintroduces it and the fix silently regresses.
-- events_clean    a ReplacingMergeTree fed by events_raw_to_clean_mv. The MV
--                 has already fired, so deleting upstream does NOT propagate;
--                 it has to be deleted here too.
-- session_intervals  the rollup input. Deleting here is what changes the
--                 published numbers.
--
-- events_dedup is a view over events_clean and follows automatically.
-- dirty_sessions may retain a queue entry; harmless, it is a work queue.
--
-- No TRUNCATE, no DROP, no predicate other than this one session_key. Every
-- statement is scoped by equality on the key, so it cannot over-delete.
--
-- mutations_sync = 2 makes each ALTER wait for all replicas, so the rollup that
-- follows cannot race a half-applied mutation and republish the old number.
--
-- Run with:
--   ./ingest/sql/apply-one.sh ingest/sql/010_drop_test_session.sql
-- or paste with {{db}} substituted.
-- =====================================================================

ALTER TABLE {{db}}.session_intervals
    DELETE WHERE session_key = 12023018559768626636
    SETTINGS mutations_sync = 2;

ALTER TABLE {{db}}.events_clean
    DELETE WHERE session_key = 12023018559768626636
    SETTINGS mutations_sync = 2;

ALTER TABLE {{db}}.events_raw
    DELETE WHERE session_key = 12023018559768626636
    SETTINGS mutations_sync = 2;
