-- Data quality ledger. Every anomaly we know about, counted, with the rule we applied.
--
-- Principle: raw_events is verbatim, exactly what the partner sent, so any number here can
-- be re-derived and audited. Cleaning happens on the way into the derived tables, never on
-- the way in from the CSV, and nothing is dropped silently: if a rule discards a row, this
-- query reports how many.
--
-- Run after every load, including the unseen day. A count that moves between days is the
-- cheapest early warning we have that the pipeline is about to be wrong.
SELECT * FROM
(
    SELECT 'events total' AS check, toInt64(count()) AS n, 'baseline' AS rule FROM raw_events WHERE event_timestamp < {frozen_before:String}
    UNION ALL
    SELECT 'content rows total', toInt64(count()), 'baseline' FROM content

    -- Impossible identifiers
    UNION ALL
    SELECT 'content_id negative (impossible id)', toInt64(count()),
           'kept in content, unreferenced by events; excluded if it ever is referenced'
    FROM content WHERE content_id <= 0
    UNION ALL
    SELECT 'events referencing a negative content_id', toInt64(count()),
           'would be counted, dimension reported as unknown'
    FROM raw_events WHERE content_id <= 0 AND event_timestamp < {frozen_before:String}

    -- Referential integrity
    UNION ALL
    SELECT 'events whose content_id is not in the catalogue', toInt64(count()),
           'kept: dropping them would understate concurrency, the one error we cannot afford'
    FROM raw_events WHERE content_id NOT IN (SELECT content_id FROM content) AND event_timestamp < {frozen_before:String}
    UNION ALL
    SELECT 'events whose content has a blank video_type', toInt64(count()),
           'kept, video_type reported as empty rather than guessed'
    FROM raw_events AS r INNER JOIN content AS c ON r.content_id = c.content_id
    WHERE c.video_type = '' AND r.event_timestamp < {frozen_before:String}

    -- Timestamp sanity
    UNION ALL
    SELECT 'events before their own session_start_epoch', toInt64(count()),
           'none observed; would be clamped to session start'
    FROM raw_events WHERE session_start_epoch > event_timestamp AND event_timestamp < {frozen_before:String}
    UNION ALL
    SELECT 'events with a non-positive timestamp', toInt64(count()), 'excluded from derivation'
    FROM raw_events WHERE toUnixTimestamp(event_timestamp) <= 0 AND event_timestamp < {frozen_before:String}
    UNION ALL
    SELECT 'duplicate (session, second) event groups', toInt64(count()),
           'collapsed to one row, a close beating an open: ties otherwise made the answer non-deterministic'
    FROM (SELECT video_session_id, toDateTime(event_timestamp) AS ts FROM raw_events WHERE event_timestamp < {frozen_before:String}
          GROUP BY 1, 2 HAVING count() > 1)

    -- Session shape
    UNION ALL
    SELECT 'sessions with more than one VideoSessionStart', toInt64(count()),
           'extra starts ignored, the state machine is idempotent on repeated opens'
    FROM (SELECT video_session_id FROM raw_events WHERE event_type = 'VideoSessionStart' AND event_timestamp < {frozen_before:String}
          GROUP BY 1 HAVING count() > 1)
    UNION ALL
    SELECT 'sessions with more than one VideoSessionEnd', toInt64(count()),
           'extra ends ignored, each simply closes an already-closed interval'
    FROM (SELECT video_session_id FROM raw_events WHERE event_type = 'VideoSessionEnd' AND event_timestamp < {frozen_before:String}
          GROUP BY 1 HAVING count() > 1)
    UNION ALL
    SELECT 'sessions with no VideoSessionStart', toInt64(count()),
           'kept: first event opens the session, a missing start is a lost event not a lost viewer'
    FROM (SELECT video_session_id FROM raw_events WHERE event_timestamp < {frozen_before:String}
          GROUP BY 1 HAVING countIf(event_type = 'VideoSessionStart') = 0)
    UNION ALL
    SELECT 'sessions still open (no VideoSessionEnd)', toInt64(count()),
           'provisional close at last event + tolerance, re-derived as heartbeats arrive'
    FROM (SELECT video_session_id FROM raw_events WHERE event_timestamp < {frozen_before:String}
          GROUP BY 1 HAVING countIf(event_type = 'VideoSessionEnd') = 0)

    -- Dimension drift inside a session
    UNION ALL
    SELECT 'sessions reporting more than one platform', toInt64(count()),
           'first-seen value wins, so one session maps to exactly one dimension tuple'
    FROM (SELECT video_session_id FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY 1 HAVING uniqExact(platform) > 1)
    UNION ALL
    SELECT 'sessions reporting more than one user_id', toInt64(count()),
           'first-seen value wins; affects user-level concurrency only'
    FROM (SELECT video_session_id FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY 1 HAVING uniqExact(user_id) > 1)
    UNION ALL
    SELECT 'sessions reporting more than one content_id', toInt64(count()),
           'first-seen value wins; a genuine content switch should be a new session'
    FROM (SELECT video_session_id FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY 1 HAVING uniqExact(content_id) > 1)

    -- State-marker consistency
    UNION ALL
    SELECT 'backgrounds never followed by a foreground', toInt64(
           countIf(event_type = 'AppBackgrounded') - countIf(event_type = 'AppForegrounded')),
           'expected: AppBackgrounded/AppForegrounded are not guaranteed, the gap cap covers it'
    FROM raw_events WHERE event_timestamp < {frozen_before:String}
    UNION ALL
    SELECT 'event gaps longer than one hour inside a session', toInt64(count()),
           'interval closed at the cap; the silence is not counted as watching'
    FROM (SELECT (toUnixTimestamp(event_timestamp) - lagInFrame(toUnixTimestamp(event_timestamp))
                    OVER (PARTITION BY video_session_id ORDER BY event_timestamp)) AS gap
          FROM raw_events WHERE event_timestamp < {frozen_before:String}) WHERE gap > 3600

    -- Derived-layer invariants: these must be zero, they are not observations
    UNION ALL
    SELECT 'INVARIANT concurrency ever negative', toInt64(count()), 'must be 0'
    FROM (SELECT sum(delta) OVER (ORDER BY minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c
          FROM (SELECT minute, sum(delta) AS delta FROM concurrency_deltas WHERE minute < {frozen_before:String} GROUP BY minute))
    WHERE c < 0
    UNION ALL
    SELECT 'INVARIANT concurrency does not return to zero at the end', toInt64(sum(delta) != 0), 'must be 0'
    FROM concurrency_deltas WHERE minute < {frozen_before:String}
    UNION ALL
    SELECT 'INVARIANT runs with end before start', toInt64(count()), 'must be 0'
    FROM session_minute_runs WHERE run_end < run_start AND run_start < {frozen_before:String}
)
ORDER BY check;
