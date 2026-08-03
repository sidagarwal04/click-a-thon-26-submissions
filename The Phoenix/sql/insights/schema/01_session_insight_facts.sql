-- INSIGHTS: one row per logical playback session. The keystone of the insight layer.
--
-- Every other insight table in the plan rolls up from this one, so it is validated the hardest:
-- sql/insights/validation/session_facts_ground_truth.sql re-derives every column below from the
-- raw CSV in `clickhouse local`, with its own copy of the state machine, and the diff must be
-- empty. Two engines, two implementations, one answer.
--
-- NO playback_instance_no. The plan keys this table on (video_session_id, playback_instance_no)
-- to allow a session to be reopened after its end. D8 rejected reopening and D13 ruled that the
-- LAST VideoSessionEnd is terminal, so a video_session_id maps to exactly one logical playback
-- instance and that column would be the constant 1 in every row. A key nobody can vary is not
-- forward compatibility, it is a column to maintain. If an event contract ever permits reuse,
-- the upgrade is to add the column and extend the ORDER BY, and both sides of the validation
-- pair change together.
--
-- WHAT IS DELIBERATELY ABSENT: background_seconds, paused_seconds, heartbeat_gap_seconds.
-- The plan lists all three. The pipeline currently EXCLUDES that time rather than attributing
-- it, so there is no second implementation to check a number against, and a column that only
-- one query can produce is a claim rather than a measurement. Every entry in
-- docs/corrections.md has that shape. They belong to session_state_transitions, which computes
-- seconds_in_previous_state and can produce all three with a real reference. Marked here rather
-- than quietly omitted so the next reader knows it was a decision.

CREATE TABLE IF NOT EXISTS session_insight_facts
(
    video_session_id String,
    user_id          String,
    content_id       Int64,

    -- title and category are the two dimensions the serving layer never carried (TASK 3.5).
    -- Denormalised rather than joined at read time: content is a slowly changing 33K-row table
    -- and a dashboard that joins it on every query pays for that join on every query.
    title            String,
    category         LowCardinality(String),
    video_type       LowCardinality(String),
    platform         LowCardinality(String),
    country          LowCardinality(String),
    app_version      LowCardinality(String),

    session_start    DateTime64(3),          -- first event of any kind
    first_play_at    DateTime64(3),          -- first VideoPlay, epoch 0 if never
    session_end_at   DateTime64(3),          -- LAST VideoSessionEnd per D13, epoch 0 if none

    -- DateTime, not DateTime64(3), and the difference is load-bearing rather than cosmetic.
    -- These two come from foreground_intervals, whose bounds are `toDateTime(ts)`: the interval
    -- table truncates to whole seconds. Declaring them at millisecond precision here would
    -- promise a precision the source does not have, and the ground truth, which works from raw
    -- millisecond timestamps, would disagree on any session whose first active event carries
    -- fractional milliseconds. It must truncate the same way, and its header says so.
    first_active_at  DateTime,               -- start of the first foreground interval, epoch 0 if never
    last_active_at   DateTime,               -- end of the last foreground interval, epoch 0 if never

    -- Epoch 0 rather than Nullable throughout. The plan uses Nullable; this codebase already
    -- learned that lesson the other way round in 01_derive_intervals.sql, where ClickHouse fills
    -- an unmatched LEFT JOIN with the type DEFAULT and never with NULL, so `IS NULL` silently
    -- never fires. One sentinel convention, tested for the same way everywhere.

    -- THE BOUNDARY CONVENTION, stated once and repeated verbatim in the ground truth:
    --   active_seconds = sum over foreground intervals of dateDiff('second', start, end)
    -- Plain dateDiff, NOT the `- 1` the concurrency oracle uses. That subtraction exists because
    -- minute OCCUPANCY is half-open: a segment landing exactly on a boundary must not claim the
    -- minute it never entered. Summed DURATION is a different question and the same adjustment
    -- would be wrong for it, once per segment. Getting this wrong produces a disagreement of one
    -- second per interval, which reads like a rounding artifact and is not.
    active_seconds        UInt32,
    active_interval_count UInt16,

    background_count       UInt16,  -- AppBackgrounded events
    foreground_return_count UInt16, -- AppForegrounded events
    pause_count            UInt16,  -- pause, speed-pause, AdPause
    resume_count           UInt16,  -- resume, speed-resume, AdResume
    heartbeat_count        UInt32,
    video_error_count      UInt16,

    reached_first_heartbeat UInt8,

    -- RETENTION FLAGS, anchored on first_active_at and NOT on the session start.
    -- "Active after N minutes" means: at the instant first_active_at + N minutes, the session was
    -- in a foreground interval. It does NOT mean "had not ended yet". A session backgrounded at
    -- minute 5 is not retained at minute 5, which is exactly the trap the plan's Phase 5 gate
    -- names. Both implementations test the same instant the same way.
    active_after_1m  UInt8,
    active_after_5m  UInt8,
    active_after_10m UInt8,
    active_after_15m UInt8,

    ended_normally     UInt8,  -- carries at least one VideoSessionEnd
    abandoned          UInt8,  -- carries none
    -- The last foreground interval was closed by silence rather than by an event: its length is
    -- exactly tolerance_s. An interval clipped by the session end is shorter, so it is not a
    -- timeout, which is the distinction this flag exists to make.
    timed_out          UInt8,
    -- A reactivating event arrived after the session's FIRST end. Measured at 2 sessions on the
    -- frozen slice, and it is the population D13 turns on, so it is worth being able to find.
    reopened_after_end UInt8,

    first_event_at DateTime64(3),
    last_event_at  DateTime64(3),

    -- ReplacingMergeTree keeps the row with the highest version. The refresh stamps
    -- toUnixTimestamp64Milli(now64(3)), so a re-derived session supersedes its previous row
    -- without a mutation and re-running the same batch is idempotent rather than additive.
    version    UInt64,
    updated_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(session_start)
-- RE-KEYED after measurement, per clickhouse-best-practices rules schema-pk-cardinality-order and
-- schema-pk-prioritize-filters. The first key was (content_id, session_start, platform, country,
-- video_session_id), which put a 25,967-cardinality column ahead of platform at 15 and country at
-- 5, so neither could prune anything. The benchmark measured exactly that: every filter shape read
-- about 21,700 rows and the content shape read MORE bytes than unfiltered.
--
-- Measured cardinalities: toDate(session_start) about 30 per monthly partition, country 5,
-- platform 15, content_id 3,366, session_start 25,967, video_session_id 119,491. Ascending, apart
-- from the date leading country, which is deliberate: the one predicate every serving query
-- carries is a time range, and the guidebook tiebreaker puts a known hot filter ahead of pure
-- cardinality ordering.
--
-- PRIMARY KEY is a four-column prefix of ORDER BY, which is the point of separating them: the
-- sparse index stays small while ORDER BY stays long enough to be a correct dedup key.
-- video_session_id MUST remain last in ORDER BY. This is a ReplacingMergeTree and ORDER BY IS the
-- dedup key, so dropping it would silently collapse two different sessions into one row.
PRIMARY KEY (toDate(session_start), country, platform, content_id)
ORDER BY (toDate(session_start), country, platform, content_id, session_start, video_session_id);

-- TTL, written and NOT active. See docs/RETENTION.md for why nothing here is switched on: a rule
-- expressed in days from now deletes the frozen corpus the moment now moves far enough.
-- TTL toDateTime(session_start) + INTERVAL 18 MONTH
--   WHERE toDate(session_start) >= toDate('2026-08-01')
