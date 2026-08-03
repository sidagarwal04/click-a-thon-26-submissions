-- INSIGHTS: one row per state CHANGE per session. The session's life as a sequence of edges.
--
-- WHY THIS EXISTS WHEN session_insight_facts ALREADY COUNTS BACKGROUNDS. That table stores
-- COUNTS per session (background_count, resume_count, timed_out). This one stores the EDGES:
-- which state, to which state, at what instant, and how long the session sat in the state it
-- left. Counts cannot answer "how long was the average background before a return", "what
-- fraction of errors recovered", or draw a Sankey of the user flow -- all of which the change
-- plan lists under Phase 2 insights. Edges can answer both; counts are a projection of edges.
--
-- THE SEVEN STATES are fixed by the change plan and are NOT free-form:
--   created, playing_foreground, paused_foreground, background, stale_heartbeat, error, ended
--
-- stale_heartbeat IS THE ONLY STATE WITH NO EVENT BEHIND IT, and it is the reason this table is
-- more than a relabelling of raw_events. Every other state is entered because something arrived.
-- This one is entered because nothing did: the session went quiet for longer than tolerance_s and
-- stopped counting toward concurrency. It is synthesised at last_event + tolerance, which is the
-- same instant the concurrency model stops counting the session, so the two layers agree by
-- construction rather than by coincidence. A session that simply stops (no end event) therefore
-- has a terminal stale_heartbeat edge and not a missing one.
--
-- CollapsingMergeTree, NOT Replacing. A re-derive must be able to REMOVE a transition that no
-- longer exists, not merely overwrite it. Late-arriving events legitimately change the edge
-- sequence: a heartbeat landing inside a 100-second gap deletes the stale_heartbeat edge that
-- gap had produced. Replacing keyed on the transition instant would strand that row forever
-- because nothing would ever write a newer version of a transition that should not exist.
-- The refresh retracts everything a touched session currently asserts, then re-asserts from full
-- history, exactly as sql/pipeline/03b does for the runs.
--
-- PARTITION BY month, per the change plan. Transitions are a small fraction of raw events
-- (edges, not samples) so daily partitions would be needlessly fine; monthly keeps the count far
-- inside the 100-1,000 band rule schema-partition-low-cardinality asks for, and still lets a
-- retention drop take whole partitions instead of a mutation.

CREATE TABLE IF NOT EXISTS session_state_transitions
(
    video_session_id     String,
    -- Increments when a session emits a second VideoSessionStart after having ended. Per decision
    -- D13 the LAST end is terminal for concurrency, so a reopened session is a second playback
    -- instance rather than a resurrection of the first; keeping them separate stops a reopen from
    -- manufacturing a single impossible edge from `ended` back to `playing_foreground`.
    playback_instance_no UInt16,
    user_id              String,
    content_id           Int64,
    platform             LowCardinality(String),
    country              LowCardinality(String),
    app_version          LowCardinality(String),
    video_type           LowCardinality(String),

    transition_at        DateTime64(3),
    from_state           LowCardinality(String),
    to_state             LowCardinality(String),
    trigger_event_type   LowCardinality(String),
    trigger_event        LowCardinality(String),
    -- How long the session sat in from_state before leaving it. This is the column the duration
    -- questions are answered from ("average background before a return"), so it is stored rather
    -- than recomputed with a window function at read time.
    seconds_in_previous_state UInt32,
    transition_sequence  UInt32,

    version              UInt64,
    sign                 Int8
)
ENGINE = CollapsingMergeTree(sign)
PARTITION BY toYYYYMM(transition_at)
-- Session first: every consumer of this table reads one session's edges in order, or aggregates
-- edges grouped by session. Reading a session's sequence must not scatter across granules.
-- transition_sequence tie-breaks the case where two decisive events share a millisecond.
ORDER BY (video_session_id, playback_instance_no, transition_at, transition_sequence);
