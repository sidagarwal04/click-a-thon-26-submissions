-- INSIGHTS: one row per detected concurrency spike, carrying the verdict on whether the audience
-- it acquired actually stayed.
--
-- WHY A SPIKE NEEDS ITS OWN TABLE. Detecting a spike is a window function over
-- audience_minute_snapshot and is cheap. Deciding whether it SUSTAINED is not: it needs the
-- minute curve for the following fifteen minutes, plus per-session outcomes (did they background
-- and never come back, did their heartbeats stop, did they error) that live in a different table
-- at a different grain. A dashboard asking "was that spike real" should read one row, not
-- reconstruct a join across two grains on every request. That is the whole point of the serving
-- layer, applied one level up.
--
-- WHY THE RATES COME FROM session_insight_facts AND NOT FROM NEW SNAPSHOT COLUMNS. The
-- injection spec asks for heartbeat_timeouts and foreground_returns on
-- audience_minute_snapshot. That table's own header (03_audience_minute_snapshot.sql:64) explains
-- why they are not there: per-minute attribution of time to a STATE needs
-- session_state_transitions, which does not exist. But the rates a spike verdict actually needs
-- are PER SESSION, not per minute -- "what fraction of the sessions that arrived in this spike
-- timed out" -- and session_insight_facts already carries timed_out, background_count,
-- foreground_return_count and video_error_count per session. Reading them there is both correct
-- and cheaper than inventing a minute-grain column to aggregate back to sessions.
--
-- ReplacingMergeTree(version): a spike is re-classified as more of its aftermath arrives. The
-- window at +5 minutes and the same window at +15 minutes are the SAME spike with a better
-- answer, so they must supersede rather than accumulate.

CREATE TABLE IF NOT EXISTS concurrency_spike_events
(
    content_id   Int64,
    window_start DateTime,          -- minute the ramp began
    peak_minute  DateTime,

    baseline_concurrency UInt32,    -- concurrency in the minute before the ramp
    peak_concurrency     UInt32,
    absolute_growth      Int64,
    growth_percent       Float32,
    minutes_to_peak      UInt16,

    -- Sustain: the shape of the curve AFTER the peak. This is what separates a real audience
    -- from a thundering herd, and no single one of these is sufficient on its own.
    minutes_above_80pct_peak UInt16,
    concurrency_after_5m     UInt32,
    concurrency_after_10m    UInt32,
    concurrency_after_15m    UInt32,
    retention_5m_percent     Float32,
    retention_10m_percent    Float32,
    retention_15m_percent    Float32,

    -- Why they left, per session, over the sessions that entered during the ramp.
    entered_sessions           UInt32,
    background_rate_after_peak Float32,
    error_rate_after_peak      Float32,
    timeout_rate_after_peak    Float32,

    spike_type LowCardinality(String),   -- healthy_sustained | short_lived | inconclusive
    confidence Float32,

    version    UInt64,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
-- No partitioning. This table holds one row per spike, so it is thousands of rows at most, and
-- partitioning it would create more parts than it saves scans (rule schema-partition-start-without).
ORDER BY (content_id, window_start);
