-- =====================================================================
-- 030 — Live viewership state: sonyliv.session_live_now
-- =====================================================================
--
-- The LIVE path. Best-effort "how many are watching right now", served
-- independently of the analytics compaction in 010/011/020/022.
--
-- Definition: solution/policy.yaml (the single source of truth).
-- A session is live when it is started, not terminated, foregrounded,
-- playing, and has emitted any event within the last 120s.
--
-- ---------------------------------------------------------------------
-- WHY THIS PATH EXISTS
-- ---------------------------------------------------------------------
-- The analytics path is built for exactness and pays for it with a
-- compaction pass, a watermark, and a sealed region that lags real time.
-- "Right now" does not need exactness; it needs to be fast.
--
-- The property that makes this cheap: IT NEEDS NO WATCHDOG, NO SWEEP,
-- NO TIMER. The read filters `last_event_ts > now() - 120s`, so a
-- session that goes silent simply falls out of the WHERE clause. Nothing
-- has to be WRITTEN when a session goes quiet — which is the entire hard
-- problem the analytics path exists to solve. ClickHouse has no
-- primitive that fires on absence (materialized views trigger on INSERT
-- only; TTL is merge-lazy and silent), so avoiding the need for one is
-- the whole design.
--
-- ---------------------------------------------------------------------
-- WHY AggregatingMergeTree AND NOT ReplacingMergeTree
-- ---------------------------------------------------------------------
-- ReplacingMergeTree keyed by session_key keeps the WHOLE LATEST ROW,
-- and the latest row is usually a stateless heartbeat. Measured on the
-- live cohort in this service:
--   * 31.7% of sessions have a `liveness` heartbeat as their newest row
--     — it carries no state, so "was paused" is lost
--   * 447 sessions (2.97% of all terminated sessions) emit heartbeats
--     UP TO 22s AFTER their session_end — latest-row-wins resurrects them
-- A materialized view cannot fix this by carrying state forward; it only
-- ever sees its own insert block.
--
-- argMaxIf tracks the state-changing signals and the liveness clock as
-- INDEPENDENT columns, so heartbeats extend liveness without touching
-- state. Verified on this service — an argMaxIf state built from a block
-- containing no state-changing events merges harmlessly and does not
-- clobber an earlier real state:
--
--   SELECT argMaxIfMerge(s) FROM (
--       SELECT argMaxIfState(toInt8(5), toDateTime64('2026-08-01 10:01:00',3,'UTC'), toUInt8(1)) AS s
--       UNION ALL
--       SELECT argMaxIfState(toInt8(0), toDateTime64('2026-08-01 10:05:00',3,'UTC'), toUInt8(0)));
--   -- returns 5 (the earlier pause), not 0 (the later heartbeats)
--
-- CoalescingMergeTree (25.6+, Cloud-supported) was considered: heartbeats
-- write NULL, latest non-NULL per column wins. Simpler, but it orders by
-- INSERT order with no version column, so a late-arriving event can
-- clobber newer state. Rejected.
-- =====================================================================

CREATE TABLE IF NOT EXISTS sonyliv.session_live_now
(
    session_start_date Date,
    session_key        UInt64,

    -- Liveness clock. ANY event renews it (policy.yaml: a `pause` still
    -- proves the app is alive and visible). One clock, not two.
    last_event_ts      SimpleAggregateFunction(max, DateTime64(3, 'UTC')),

    -- Sticky: once a session_end is seen it can never be un-seen. This is
    -- what defends against the 447 post-session_end heartbeat sessions.
    terminated         SimpleAggregateFunction(max, UInt8),

    -- +1 / -1 / 0, resolved from the LAST state-changing event only.
    -- Kept as two separate columns, never collapsed into one flag, so the
    -- permissive "foreground-only" reading stays a one-line change and can
    -- be served alongside for comparison (see 031).
    fg_state           AggregateFunction(argMaxIf, Int8, DateTime64(3, 'UTC'), UInt8),
    play_state         AggregateFunction(argMaxIf, Int8, DateTime64(3, 'UTC'), UInt8),

    -- Session-static dimensions, first-seen by event_ts.
    -- NOTE: LowCardinality is dropped inside AggregateFunction on 26.2 —
    -- these are plain String by necessity, not by oversight.
    platform           AggregateFunction(argMin, String, DateTime64(3, 'UTC')),
    country            AggregateFunction(argMin, String, DateTime64(3, 'UTC')),
    content_id         AggregateFunction(argMin, Int64,  DateTime64(3, 'UTC')),
    app_version        AggregateFunction(argMin, String, DateTime64(3, 'UTC'))
)
ENGINE = SharedAggregatingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY session_start_date
ORDER BY (session_start_date, session_key)
TTL toDateTime(session_start_date) + INTERVAL 3 DAY
SETTINGS index_granularity = 8192
-- One string literal, deliberately. ClickHouse has no C-style implicit
-- concatenation, so 'part one' 'part two' is a syntax error, not a joined
-- string. The same split broke 040 on its first real run.
COMMENT 'LIVE path. One row per session, best-effort. The MV in this file is the ONLY writer. Not to be confused with session_live_state, which the analytics compactor owns. Definition: solution/policy.yaml. 3-day TTL exceeds the 43.6h longest observed session.';

-- Both non-aggregate columns (session_start_date, session_key) are in the
-- ORDER BY, so the AggregatingMergeTree "column outside the sorting key
-- takes an arbitrary value on merge" hazard does not apply here.


-- ---------------------------------------------------------------------
-- The materialized view
-- ---------------------------------------------------------------------
-- Chained off events_clean, which is itself the target of
-- events_raw_to_clean_mv. An MV fires on INSERT into its source table and
-- MV-target writes are inserts, so this fires correctly — verified by V5
-- in 032.
--
-- IDEMPOTENT UNDER DUPLICATION: this fires on the raw INSERT, BEFORE
-- events_clean's ReplacingMergeTree collapses duplicate keys. Every
-- aggregate used here (max, argMax, argMin) is idempotent, so a
-- double-delivered row changes nothing. That is a property, not an
-- accident — do not add count()/sum() to this view.
--
-- The play_state expression must stay semantically identical to
-- `playing_setter` in 011_build_active_intervals.sql. If you change one,
-- change both, and re-run 032.
-- ---------------------------------------------------------------------

CREATE MATERIALIZED VIEW IF NOT EXISTS sonyliv.events_clean_to_live_mv
TO sonyliv.session_live_now
AS
SELECT
    toDate(session_start_ts)                                          AS session_start_date,
    session_key,

    max(event_ts)                                                     AS last_event_ts,
    maxIf(toUInt8(1), signal = 'session_end')                         AS terminated,

    -- Foreground axis. End and background clear; start and foreground set.
    argMaxIfState(
        multiIf(signal IN ('session_end', 'background'),   toInt8(-1),
                signal IN ('session_start', 'foreground'), toInt8(1),
                toInt8(0)),
        event_ts,
        signal IN ('session_end', 'background', 'session_start', 'foreground')
    )                                                                 AS fg_state,

    -- Playback axis. pause and error stop; play and resume start.
    -- `error` stops playback but is NOT terminal — policy.yaml
    -- error_is_terminal: false, and VideoError never ends a session
    -- (293 events, one per affected session; a quality signal).
    -- AppForegrounded deliberately does NOT resume a paused player.
    argMaxIfState(
        multiIf(signal IN ('session_end', 'error', 'pause'), toInt8(-1),
                signal IN ('play', 'resume'),               toInt8(1),
                toInt8(0)),
        event_ts,
        signal IN ('session_end', 'error', 'pause', 'play', 'resume')
    )                                                                 AS play_state,

    argMinState(toString(platform),    event_ts)                      AS platform,
    argMinState(toString(country),     event_ts)                      AS country,
    argMinState(content_id,            event_ts)                      AS content_id,
    argMinState(toString(app_version), event_ts)                      AS app_version
FROM sonyliv.events_clean
GROUP BY session_start_date, session_key;


-- ---------------------------------------------------------------------
-- Backfill — run ONCE, immediately after creating the MV above
-- ---------------------------------------------------------------------
-- Incremental MVs do not process rows that already exist. Overlap with
-- the MV is harmless: every aggregate here is idempotent, so rows landing
-- in both the backfill and the live MV merge to the same state.
-- ---------------------------------------------------------------------

INSERT INTO sonyliv.session_live_now
SELECT
    toDate(session_start_ts)                  AS session_start_date,
    session_key,
    max(event_ts)                             AS last_event_ts,
    maxIf(toUInt8(1), signal = 'session_end') AS terminated,
    argMaxIfState(
        multiIf(signal IN ('session_end', 'background'),   toInt8(-1),
                signal IN ('session_start', 'foreground'), toInt8(1),
                toInt8(0)),
        event_ts,
        signal IN ('session_end', 'background', 'session_start', 'foreground')) AS fg_state,
    argMaxIfState(
        multiIf(signal IN ('session_end', 'error', 'pause'), toInt8(-1),
                signal IN ('play', 'resume'),               toInt8(1),
                toInt8(0)),
        event_ts,
        signal IN ('session_end', 'error', 'pause', 'play', 'resume'))          AS play_state,
    argMinState(toString(platform),    event_ts) AS platform,
    argMinState(toString(country),     event_ts) AS country,
    argMinState(content_id,            event_ts) AS content_id,
    argMinState(toString(app_version), event_ts) AS app_version
FROM sonyliv.events_clean
GROUP BY session_start_date, session_key;
