-- INSIGHTS: one row per time a user moved from one piece of content to another.
--
-- Answers the plan's Phase 6: content switching and cannibalization. "Did this premiere bring new
-- viewers, or did it eat the audience of the match already running" is a question about the SAME
-- user appearing on two different contents in sequence, which nothing in the concurrency engine
-- can express: the delta tables count bodies per minute and have no memory of who moved where.
--
-- THE TRAP THIS TABLE EXISTS TO AVOID, named in the plan's own acceptance checklist: do not
-- classify simultaneous sessions on different devices as a switch. A viewer with the match on the
-- TV and a highlights clip on their phone has not switched anything. Their two sessions OVERLAP in
-- time, and overlap is the discriminator, so `transition_type` carries `parallel_multi_device` as
-- a first-class outcome rather than letting it contaminate the switch counts.
--
-- SOURCED FROM session_insight_facts, NOT from raw_events. That table already carries
-- first_active_at and last_active_at per session, which are derived from the validated foreground
-- intervals, so a switch here inherits the foreground-only definition rather than re-deriving it.
-- Re-deriving would be a second implementation of the state machine inside the product, which is
-- the one place a second implementation is not wanted.
--
-- ORDER OF A TRANSITION IS BY ACTIVITY, NOT BY SESSION START. Two sessions can be created in one
-- order and become active in the other, and it is the moment a viewer actually started watching
-- that orders their journey.

CREATE TABLE IF NOT EXISTS user_content_transitions
(
    user_id String,

    from_content_id  Int64,
    from_title       String,
    from_category    LowCardinality(String),
    from_video_type  LowCardinality(String),
    to_content_id    Int64,
    to_title         String,
    to_category      LowCardinality(String),
    to_video_type    LowCardinality(String),

    from_session_id String,
    to_session_id   String,

    -- The instant the new content became active. DateTime64(3) to match session_insight_facts.
    transition_at DateTime64(3),

    -- Int32 and SIGNED, deliberately. A negative gap is not corrupt data, it is the overlap case:
    -- the new session became active before the old one stopped. Declaring this UInt32 would wrap a
    -- legitimate -240 into four billion, which is the kind of number that survives a review
    -- because nobody expects it.
    gap_seconds     Int32,
    overlap_seconds Int32,

    from_platform LowCardinality(String),
    to_platform   LowCardinality(String),

    -- direct_switch | switch_after_background | switch_after_end | parallel_multi_device |
    -- return_to_previous_content
    transition_type LowCardinality(String),

    version    UInt64,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(transition_at)
-- KEYED FOR THE SERVING QUERIES, not for point lookup, per clickhouse-best-practices rules
-- schema-pk-prioritize-filters and schema-pk-cardinality-order.
--
-- The plan suggests (transition_at, from_content_id, to_content_id, user_id). transition_at is
-- effectively unique, so leading with it means no query can ever prune on anything else. Every
-- serving query this table has is an aggregate over a time RANGE grouped by a dimension, so the
-- date leads (the one predicate all of them carry, which is the guidebook's tiebreaker for putting
-- a known hot filter ahead of pure cardinality order), then transition_type at 5 values, then the
-- content pair.
--
-- The tail is the identity. This is a ReplacingMergeTree and ORDER BY IS the dedup key: to_session_id
-- must stay, or two different viewers moving between the same two contents in the same second
-- collapse into one row and one of them is silently lost.
PRIMARY KEY (toDate(transition_at), transition_type, from_content_id, to_content_id)
ORDER BY (toDate(transition_at), transition_type, from_content_id, to_content_id, transition_at, user_id, to_session_id);

-- TTL written and NOT active, consistent with every other insight table. See docs/RETENTION.md:
-- a rule expressed in days from now deletes the frozen corpus as soon as now moves far enough.
-- TTL toDateTime(transition_at) + INTERVAL 18 MONTH
--   WHERE toDate(transition_at) >= toDate('2026-08-01')
