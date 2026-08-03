-- REFERENCE for audience_minute_snapshot: the authoritative concurrency curves.
--
-- The plan's Phase 3 gate states the requirement literally: snapshot.concurrent_sessions must
-- equal the concurrency_deltas curve for all benchmark minutes and filters. So the reference is
-- that curve, and the user curve beside it, both read from the delta tables that are already
-- proven against the brute-force oracle at zero diffs `[V:oracle_parity]`.
--
-- THIS IS THE WEAKER KIND OF REFERENCE AND THE HARNESS SAYS SO. It shares an engine and a
-- derivation with the thing it checks, unlike session_facts, whose ground truth re-implements
-- the state machine in `clickhouse local`. What it does catch is the entire class of error this
-- table can actually make: exploding runs into the wrong minutes, dropping the collapse filter
-- so retracted runs count as live, double counting a user across devices, and losing a minute
-- in the middle of a run. Those are the failure modes, and they all show up here.
--
-- WHY THE CURVE HAS TO BE DENSIFIED. concurrency_deltas holds a row only where a delta occurs,
-- so a cumulative sum over its rows produces values only at run boundaries. The snapshot, by
-- design, holds a row for every minute a session was active, including the quiet middle of a
-- long run. Comparing them without WITH FILL would report thousands of missing keys that are
-- the entire point of the table existing.
--
-- WHY sessions AND users COME FROM DIFFERENT TABLES: one person on a phone and a TV is two
-- sessions and one viewer. user_concurrency_deltas is built from runs already merged across a
-- user's sessions. Deriving users from the session curve would count that person twice.
WITH
    -- Corpus start, floored to the minute, so both series begin at the same instant. Widened by
    -- nothing: WITH FILL needs a real FROM or it spans only the rows that already exist, which
    -- is the sparse-average bug this repo restated eleven numbers over.
    -- assumeNotNull, because a scalar subquery comes back Nullable(DateTime) and WITH FILL
    -- rejects a Nullable bound with INVALID_WITH_FILL_EXPRESSION. The set is never empty:
    -- concurrency_deltas has rows below frozen_before or this whole comparison is moot.
    assumeNotNull((SELECT min(minute) FROM concurrency_deltas WHERE minute < {frozen_before:String})) AS c_from,
    assumeNotNull((SELECT max(minute) FROM concurrency_deltas WHERE minute < {frozen_before:String})) AS c_to,

    s AS
    (
        SELECT minute, sum(delta) AS d
        FROM concurrency_deltas
        WHERE minute < {frozen_before:String}
        GROUP BY minute
    ),
    scurve AS
    (
        SELECT minute,
               toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS sessions
        FROM s
    ),
    u AS
    (
        SELECT minute, sum(delta) AS d
        FROM user_concurrency_deltas
        WHERE minute < {frozen_before:String}
        GROUP BY minute
    ),
    ucurve AS
    (
        SELECT minute,
               toInt64(sum(d) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS users
        FROM u
    ),
    -- EACH CURVE IS DENSIFIED SEPARATELY, THEN JOINED. The first version of this file merged the
    -- two sparse series first and densified the result, and it was wrong in a way worth keeping
    -- a note about: the session and user delta tables have rows at DIFFERENT minutes, so the
    -- merge produced a row at every session-delta minute carrying users = 0, and WITH FILL then
    -- had nothing to fix because the row already existed. INTERPOLATE only fills minutes that
    -- are ABSENT; it cannot correct a present row that says zero.
    --
    -- That reported 171 differing rows against the snapshot, and the snapshot was right. It is
    -- the same sparse-series mistake this repo restated eleven headline numbers over, made once
    -- more inside the thing whose job is to catch it. Densify first, join second.
    sdense AS
    (
        SELECT minute, sessions
        FROM scurve
        ORDER BY minute ASC
        WITH FILL FROM c_from TO c_to + toIntervalMinute(1) STEP toIntervalMinute(1)
        INTERPOLATE (sessions AS sessions)
    ),
    udense AS
    (
        SELECT minute, users
        FROM ucurve
        ORDER BY minute ASC
        WITH FILL FROM c_from TO c_to + toIntervalMinute(1) STEP toIntervalMinute(1)
        INTERPOLATE (users AS users)
    )
SELECT
    toString(s.minute) AS minute,
    s.sessions         AS sessions,
    u.users            AS users
FROM sdense AS s
LEFT JOIN udense AS u ON u.minute = s.minute
-- Only minutes with an audience. The snapshot stores a row per active minute; it does not store
-- a zero row for a minute nobody watched, and neither side should invent one.
WHERE s.sessions > 0
ORDER BY s.minute;
