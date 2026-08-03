-- INSIGHTS: one row per minute per dimension tuple, carrying every behavioural metric at once.
--
-- WHY IT EXISTS WHEN concurrency_deltas ALREADY ANSWERS CONCURRENCY. The delta table is the
-- authoritative concurrency source and stays that way: two rows per run, a cumulative sum at
-- read time, and it answers exactly one question very cheaply. A dashboard that also wants
-- starts, ends, background entries, returns, errors and active seconds for the same minute
-- would need six more passes over the runs. This table answers all of them in one read of one
-- row, which is what makes the multi-metric panels affordable at 100x, where a per-session scan
-- is not.
--
-- THE GATE THAT MATTERS: concurrent_sessions here must equal the authoritative
-- concurrency_deltas curve for every minute and every filter. If it ever does not, this table
-- is wrong and the delta table is right. Enforced by
-- sql/insights/validation/audience_snapshot_{ground_truth,optimized}.sql.
--
-- SESSIONS AND USERS ARE COMPUTED FROM DIFFERENT SOURCES ON PURPOSE, and this is the easiest
-- column in the table to get quietly wrong. concurrent_sessions comes from session_minute_runs.
-- concurrent_users does NOT come from counting distinct user_id in those same rows: one person
-- on a phone and a TV is two sessions and one viewer, and their two runs may overlap. It comes
-- from user_minute_runs, where a user's runs are already merged ACROSS their sessions before
-- any counting happens. Deriving users from session rows would count that person twice, which
-- is the specific failure the plan's correctness principle 7 names.
--
-- DENSE MEANS EVERY MINUTE A SESSION WAS ACTIVE, not every minute in the calendar. A row exists
-- for each minute a run covers, including the minutes in the middle of a run that emit no delta
-- and appear nowhere in concurrency_deltas. It does NOT store a zero row for every dimension
-- tuple in every quiet minute: that is a cross product of minutes and tuples, and the
-- densification a dashboard needs across quiet minutes is a bounded WITH FILL at read time,
-- which serving/concurrency_curve.sql already does correctly.

CREATE TABLE IF NOT EXISTS audience_minute_snapshot
(
    minute      DateTime,
    content_id  Int64,
    title       String,
    category    LowCardinality(String),
    video_type  LowCardinality(String),
    platform    LowCardinality(String),
    country     LowCardinality(String),
    app_version LowCardinality(String),

    concurrent_sessions UInt32,   -- gated against concurrency_deltas
    concurrent_users    UInt32,   -- gated against user_concurrency_deltas, and NOT derived from the line above

    session_starts      UInt32,   -- sessions whose first event lands in this minute
    first_plays         UInt32,   -- sessions whose first VideoPlay lands in this minute
    session_ends        UInt32,   -- sessions whose last VideoSessionEnd lands in this minute
    foreground_entries  UInt32,   -- AppForegrounded events in this minute
    background_entries  UInt32,   -- AppBackgrounded events in this minute
    video_errors        UInt32,   -- VideoError events in this minute

    version    UInt64,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMMDD(minute)
-- minute leads here, unlike concurrency_deltas where the dimensions lead. The reason is that
-- this table answers POINT-IN-TIME questions ("what did 10:56 look like") rather than
-- cumulative ones. concurrency_deltas has to put the dimensions first because a cumulative sum
-- must start at the first minute of the series, so a time predicate can never prune it; that
-- constraint does not apply to a table whose rows are already absolute values.
ORDER BY (minute, content_id, platform, country, video_type, app_version);

-- Columns the plan lists and this does not carry yet: foreground_returns, heartbeat_timeouts,
-- active_seconds, background_seconds. All four need per-minute attribution of time to a STATE,
-- which session_state_transitions produces and nothing does today. Shipping them from a single
-- implementation with no reference to check against is how docs/corrections.md got eleven
-- entries. Marked, not silently dropped.

-- TTL, written and NOT active. See docs/RETENTION.md.
-- TTL minute + INTERVAL 24 MONTH WHERE toDate(minute) >= toDate('2026-08-01')
