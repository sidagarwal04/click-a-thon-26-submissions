-- =============================================================================
-- 007_fleet_sessions.sql — durable state for the interactive session fleet
--
-- The fleet in internal/fleet holds live sessions in memory: their play/visibility
-- state, their recorded active intervals, and when each one expires. A restart used
-- to lose all of it while the events those sessions wrote stayed in events_raw —
-- so the graph's ground-truth line vanished and its ClickHouse line did not, which
-- is the one failure that makes the comparison lie.
--
-- This table is that state, so the process can reconcile itself on startup.
--
-- It is NOT part of the concurrency pipeline. Nothing here feeds events_clean,
-- session_state or the serving layer; it is the simulator's own bookkeeping, and
-- it is kept in ClickHouse only because that is the one datastore this deployment
-- already has credentials for.
-- =============================================================================

-- One row per session, replaced in place as the session changes.
--
-- ReplacingMergeTree, not SummingMergeTree or an append log: the registry holds
-- exactly one current state per session, which is replacement semantics by
-- definition. Additive corrections would be the wrong model — a session's
-- `playing` flag has no meaningful sum, and the interval array is a set that gets
-- rewritten, not accumulated.
--
-- `version` is the update timestamp in milliseconds. It is monotonic per session
-- because the registry stamps it from one clock under one mutex, so the newest
-- write always wins the merge regardless of insert order or retry.
CREATE TABLE IF NOT EXISTS {{db}}.fleet_sessions
(
    video_session_id  String   COMMENT '64-char uppercase hex, matches events_raw',
    user_id           String,
    content_id        Int64,
    content_title     String   DEFAULT '',
    video_type        LowCardinality(String) DEFAULT '',

    platform          LowCardinality(String),
    app_version       LowCardinality(String),
    country           LowCardinality(String),

    -- Constant for the session's whole life; events_raw partitions on it.
    start_epoch       DateTime64(3, 'UTC'),
    cadence_seconds   UInt16   COMMENT 'Heartbeat interval',

    -- When the simulator retires this session on its own. A fleet left running
    -- would otherwise heartbeat into events_raw forever, which is how a demo
    -- becomes an unattended writer.
    expires_at        DateTime64(3, 'UTC'),

    -- Who drives. Autonomous sessions pause, background and end themselves from
    -- the measured rates; manual ones hold whatever an operator set. The two
    -- schedule columns are the autonomous plan, unset for manual — persisted so a
    -- restart resumes a session's own lifecycle instead of restarting it.
    mode              LowCardinality(String) DEFAULT 'manual',
    ends_at           DateTime64(3, 'UTC')   DEFAULT toDateTime64(0, 3, 'UTC'),
    next_behaviour    DateTime64(3, 'UTC')   DEFAULT toDateTime64(0, 3, 'UTC'),

    -- The five terms of the activity predicate, stored individually because that
    -- is how the pipeline models them. foreground and playing are independent:
    -- collapsing them was measured at 38,958 disagreements across 98.8% of
    -- sessions, so a single state enum here could not round-trip.
    started           Bool,
    ended             Bool,
    foreground        Bool,
    playing           Bool,
    -- False means "app killed": the ticker is stopped and NO event is written, so
    -- the pipeline only learns of it when the lease expires. This flag is the only
    -- record that it was deliberate.
    heartbeating      Bool,

    -- Lease bookkeeping. last_eligible is the newest liveness signal that landed
    -- while the session was otherwise active; the lease runs to it plus the
    -- configured timeout.
    last_eligible     DateTime64(3, 'UTC'),
    -- Start of the in-flight active interval, or the epoch when inactive. Restored
    -- verbatim so an interval that was open across a restart stays one interval
    -- rather than being split into two by the restart itself.
    open_since        DateTime64(3, 'UTC'),
    intervals         Array(Tuple(start_time DateTime64(3, 'UTC'),
                                  end_time   DateTime64(3, 'UTC')))
                      COMMENT 'Closed active intervals, half-open [start, end)',

    events_sent       UInt32,
    next_tick         DateTime64(3, 'UTC'),

    -- Set when the operator clears ended sessions from the listing. Filtered on
    -- read rather than deleted: a mutation per click would be absurd for a
    -- bookkeeping table, and the TTL below reaps the rows anyway.
    removed           Bool DEFAULT false,

    updated_at        DateTime64(3, 'UTC'),
    version           UInt64   COMMENT 'toUnixTimestamp64Milli(updated_at); newest write wins'
)
ENGINE = ReplacingMergeTree(version)
ORDER BY video_session_id
-- No partitioning: the table is bounded by the registry's own MaxLive cap, so it
-- is thousands of rows, not billions. A partition key would create more parts
-- than it eliminates.
TTL toDateTime(updated_at) + INTERVAL 7 DAY
SETTINGS index_granularity = 8192
COMMENT 'Simulator bookkeeping: one replaceable row per interactive fleet session.';


-- Migrations. CREATE TABLE IF NOT EXISTS is a no-op on a table that already
-- exists, so columns added after the first deploy need their own statement —
-- otherwise the schema step reports success while the new columns are missing,
-- which is exactly how this was found.
--
-- ADD COLUMN IF NOT EXISTS is idempotent, so these stay in the file rather than
-- becoming a one-off script somebody has to remember to run.
ALTER TABLE {{db}}.fleet_sessions
    ADD COLUMN IF NOT EXISTS mode LowCardinality(String) DEFAULT 'manual';

ALTER TABLE {{db}}.fleet_sessions
    ADD COLUMN IF NOT EXISTS ends_at DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC');

ALTER TABLE {{db}}.fleet_sessions
    ADD COLUMN IF NOT EXISTS next_behaviour DateTime64(3, 'UTC') DEFAULT toDateTime64(0, 3, 'UTC');
