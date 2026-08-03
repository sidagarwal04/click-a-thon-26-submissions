-- INSIGHTS: one row per time a user moved the SAME content to a different device.
--
-- Answers the plan's Phase 7: platform migration and multi-device flow. The question underneath it
-- is capacity, not curiosity. If a measurable share of viewers start on a phone and finish on a
-- TV, then phone concurrency and TV concurrency are not two independent audiences to provision
-- for, and the peak of each understates how much of the same person they are counting.
--
-- SAME CONTENT, DIFFERENT PLATFORM. That is what separates this table from
-- 06_user_content_transitions.sql, which is the same user on DIFFERENT content. A viewer who
-- changes both at once is a content switch, not a handoff, and is recorded there: making a device
-- change conditional on the content staying the same is what keeps the two tables from
-- double-counting one journey.
--
-- THE SAME TRAP, AND THE SAME DISCRIMINATOR. A viewer watching one match on a TV and the same
-- match on a phone at the same time has not handed anything off. Overlap distinguishes them, and
-- `parallel_multi_device` is a first-class outcome rather than noise inside the handoff count.
-- overlap_seconds is stored rather than derived at read time so a reader can see HOW MUCH the two
-- sessions overlapped, which is the difference between a clean handoff and a viewer who left one
-- device playing to an empty room.

CREATE TABLE IF NOT EXISTS user_platform_transitions
(
    user_id    String,
    content_id Int64,
    title      String,

    from_platform LowCardinality(String),
    to_platform   LowCardinality(String),

    from_session_id String,
    to_session_id   String,

    transition_at DateTime64(3),

    -- Signed, for the reason 06_user_content_transitions.sql gives: a negative gap IS the overlap
    -- case, and an unsigned type would wrap it into a plausible-looking four billion.
    gap_seconds     Int32,
    overlap_seconds Int32,

    -- handoff | parallel_multi_device | return_to_previous_device | unknown
    transition_type LowCardinality(String),

    version    UInt64,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(transition_at)
-- Same reasoning as 06: the date leads because every serving query carries a time range, then the
-- low-cardinality dimensions this table is actually grouped by, then the identity tail that keeps
-- the dedup key unique. from_platform and to_platform are 18 values each on the current corpus,
-- and the pair is what a handoff report groups by, so they sit directly behind the date.
PRIMARY KEY (toDate(transition_at), transition_type, from_platform, to_platform)
ORDER BY (toDate(transition_at), transition_type, from_platform, to_platform, content_id, transition_at, user_id, to_session_id);

-- TTL written and NOT active. See docs/RETENTION.md.
-- TTL toDateTime(transition_at) + INTERVAL 18 MONTH
--   WHERE toDate(transition_at) >= toDate('2026-08-01')
