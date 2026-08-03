-- ============================================================================
-- 70_truncation_test.sql — H4/H8. Open-session absorption + late-arrival proof.
--
-- Answers the scored question "update handling: incrementally, or by
-- recomputing?" with a measurement instead of an assertion. The shape:
--
--   1. Cut the stream mid-event at the global peak (2026-07-26 10:56:00), so
--      3,516 sessions are genuinely mid-flight and 4,207 have not started.
--   2. Build the FULL model on that truncated slice — this is "what the serving
--      layer believed at 10:56".
--   3. Insert the remaining 447,081 events as a late arrival.
--   4. Absorb them INCREMENTALLY (ADR 0006 correction-by-diff): re-derive only
--      the touched sessions, append the NEGATION of their old deltas and the
--      new ones. cc_minute_delta is never truncated and never mutated.
--   5. Compare against the from-scratch full build. Convergence is the claim;
--      byte-identical minute curves are the evidence.
--
-- EVERYTHING RUNS IN `sonyliv_trunc`. The graded `sonyliv` database is read
-- with SELECT only and must never be written by this file. Every table
-- reference below is database-qualified for exactly that reason — an
-- unqualified TRUNCATE run in the wrong session context would destroy the
-- graded state.
--
-- Driver: tools/truncation-test.sh (it templates the __MARKED__ blocks below
-- for the three derivations: truncated build, correction-by-diff, control
-- rebuild). Findings land in evidence/truncation.txt.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS sonyliv_trunc;

-- ---------------------------------------------------------------------------
-- Mirror of sonyliv.ev_raw. Same engine, same sort key, same settings — the
-- test is worthless if the storage layout differs from production, because
-- interval derivation reads through that layout.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.ev_raw
(
    content_id          Int64,
    video_session_id    String,
    user_id             String,
    event_type          LowCardinality(String),
    event               LowCardinality(String),
    event_timestamp     DateTime64(3),
    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),
    audio_language      LowCardinality(String),
    subtitle_language   LowCardinality(String),
    player_version      LowCardinality(String),
    session_start_epoch DateTime64(3),
    -- ADR 0024's unknown-column Map. DEFAULT map() so the explicit-column
    -- INSERTs above still work, and so this mirror is valid whether or not
    -- the graded ev_raw has adopted the column yet — it has not, as of
    -- 2026-08-02, which is recorded in REMAINING.md.
    extra             Map(LowCardinality(String), String) DEFAULT map(),
    INDEX idx_content content_id TYPE bloom_filter(0.01) GRANULARITY 1,
    INDEX idx_ts      event_timestamp TYPE minmax GRANULARITY 1
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_timestamp)
ORDER BY (toStartOfHour(event_timestamp), platform, video_session_id, event_timestamp)
SETTINGS index_granularity = 8192,
         min_bytes_for_wide_part = 0,
         non_replicated_deduplication_window = 1000;

-- ---------------------------------------------------------------------------
-- The sealed tier, verbatim from sql/10_intervals.sql.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.session_intervals
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    -- ADR 0008: the four raw dimensions that used to be dropped at derivation.
    -- Order must match sql/10_intervals.sql exactly — truncation-test.sh seds
    -- the REAL 30/40 derivations into this schema, so a mismatch is Code: 16.
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    extra_dimensions  Map(LowCardinality(String), String) DEFAULT map(),
    interval_start   DateTime64(3),
    interval_end     DateTime64(3),
    is_open          UInt8,
    build_version    UInt64,
    INDEX idx_start interval_start TYPE minmax GRANULARITY 1
)
ENGINE = ReplacingMergeTree(interval_end)
ORDER BY (video_session_id, interval_start)
SETTINGS min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS sonyliv_trunc.cc_minute_delta
(
    minute      DateTime,
    platform    LowCardinality(String),
    country     LowCardinality(String),
    content_id  Int64,
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    audio_language    LowCardinality(String),
    app_version       LowCardinality(String),
    delta       SimpleAggregateFunction(sum, Int64),
    starts      SimpleAggregateFunction(sum, Int64),
    ends        SimpleAggregateFunction(sum, Int64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMMDD(minute)
ORDER BY (platform, country, content_id, minute)
SETTINGS min_bytes_for_wide_part = 0;

-- ---------------------------------------------------------------------------
-- Snapshot of session_intervals as it stood BEFORE absorption, for the touched
-- sessions only. ADR 0006 says "emit the negation of the deltas for the old
-- derivation" — this table is that old derivation. It is NOT extra bookkeeping
-- in production: the finalizer can re-derive the old rows from
-- session_intervals itself before overwriting them. It exists here so the test
-- can hold both derivations side by side and prove they cancel.
--
-- Plain MergeTree, not Replacing: we want every historical version, not the
-- latest one.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.session_intervals_prev
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    -- ADR 0008: the four raw dimensions that used to be dropped at derivation.
    -- Order must match sql/10_intervals.sql exactly — truncation-test.sh seds
    -- the REAL 30/40 derivations into this schema, so a mismatch is Code: 16.
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    extra_dimensions  Map(LowCardinality(String), String) DEFAULT map(),
    interval_start   DateTime64(3),
    interval_end     DateTime64(3),
    is_open          UInt8,
    build_version    UInt64
)
ENGINE = MergeTree
ORDER BY (video_session_id, interval_start)
SETTINGS min_bytes_for_wide_part = 0;

-- ---------------------------------------------------------------------------
-- Control: a from-scratch full build over the complete stream, in this same
-- database. The incremental result is compared against THIS, not only against
-- sonyliv — so a difference cannot be blamed on environment drift.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.cc_minute_delta_control
(
    minute      DateTime,
    platform    LowCardinality(String),
    country     LowCardinality(String),
    content_id  Int64,
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    audio_language    LowCardinality(String),
    app_version       LowCardinality(String),
    delta       SimpleAggregateFunction(sum, Int64),
    starts      SimpleAggregateFunction(sum, Int64),
    ends        SimpleAggregateFunction(sum, Int64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMMDD(minute)
ORDER BY (platform, country, content_id, minute)
SETTINGS min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS sonyliv_trunc.session_intervals_control
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    -- ADR 0008: the four raw dimensions that used to be dropped at derivation.
    -- Order must match sql/10_intervals.sql exactly — truncation-test.sh seds
    -- the REAL 30/40 derivations into this schema, so a mismatch is Code: 16.
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    extra_dimensions  Map(LowCardinality(String), String) DEFAULT map(),
    interval_start   DateTime64(3),
    interval_end     DateTime64(3),
    is_open          UInt8,
    build_version    UInt64
)
ENGINE = ReplacingMergeTree(interval_end)
ORDER BY (video_session_id, interval_start)
SETTINGS min_bytes_for_wide_part = 0;

-- ---------------------------------------------------------------------------
-- The stump: cc_minute_delta exactly as it stood after the truncated build,
-- kept so PHASE 7 can measure how far BACK from the cut truncation corrupted
-- the answer. That distance is the watermark width, measured rather than
-- guessed (ADR 0004 says W "should be set from the measured distribution").
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.cc_minute_delta_stump
(
    minute      DateTime,
    platform    LowCardinality(String),
    country     LowCardinality(String),
    content_id  Int64,
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    audio_language    LowCardinality(String),
    app_version       LowCardinality(String),
    delta       SimpleAggregateFunction(sum, Int64),
    starts      SimpleAggregateFunction(sum, Int64),
    ends        SimpleAggregateFunction(sum, Int64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMMDD(minute)
ORDER BY (platform, country, content_id, minute)
SETTINGS min_bytes_for_wide_part = 0;

CREATE OR REPLACE VIEW sonyliv_trunc.v_concurrency_minute_delta_total_stump AS
SELECT
    minute,
    toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS concurrent
FROM sonyliv_trunc.cc_minute_delta_stump
GROUP BY minute;

-- ---------------------------------------------------------------------------
-- Isolation probe: deltas rebuilt from scratch off the INCREMENTAL interval
-- table. Comparing this against the incrementally-corrected cc_minute_delta
-- separates two failure modes that would otherwise be indistinguishable —
-- a bug in the correction-by-diff arithmetic vs a bug in session_intervals.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.cc_minute_delta_probe
    AS sonyliv_trunc.cc_minute_delta;

-- ---------------------------------------------------------------------------
-- THE FIX under test. Identical to session_intervals except the version column
-- is a monotonic BUILD counter rather than `interval_end`.
--
-- `ReplacingMergeTree(interval_end)` resolves duplicates by keeping the row
-- with the LARGEST interval_end, on the assumption that a re-derivation can
-- only ever extend an interval. Truncation falsifies that: a provisional
-- interval carries TAIL_S seconds of grace because its run appeared to end,
-- and the completed derivation may place the true end EARLIER (at a pause, or
-- at a real VideoSessionEnd inside the grace window). The stale, longer,
-- provisional row then outranks the correct one forever — and drags a stale
-- `is_open = 1` along with it. Measured: 316 intervals, up to 60 s too long.
--
-- `build_version` is monotonic by construction, so the newest derivation wins
-- whether the interval grew or shrank.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.session_intervals_fix
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    -- ADR 0008: the four raw dimensions that used to be dropped at derivation.
    -- Order must match sql/10_intervals.sql exactly — truncation-test.sh seds
    -- the REAL 30/40 derivations into this schema, so a mismatch is Code: 16.
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    extra_dimensions  Map(LowCardinality(String), String) DEFAULT map(),
    interval_start   DateTime64(3),
    interval_end     DateTime64(3),
    is_open          UInt8,
    build_version    UInt64
)
ENGINE = ReplacingMergeTree(build_version)
ORDER BY (video_session_id, interval_start)
SETTINGS min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS sonyliv_trunc.session_intervals_fix_prev
(
    video_session_id String,
    user_id          String,
    content_id       Int64,
    platform         LowCardinality(String),
    country          LowCardinality(String),
    -- ADR 0008: the four raw dimensions that used to be dropped at derivation.
    -- Order must match sql/10_intervals.sql exactly — truncation-test.sh seds
    -- the REAL 30/40 derivations into this schema, so a mismatch is Code: 16.
    app_version       LowCardinality(String),
    audio_language    LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String),
    extra_dimensions  Map(LowCardinality(String), String) DEFAULT map(),
    interval_start   DateTime64(3),
    interval_end     DateTime64(3),
    is_open          UInt8,
    build_version    UInt64
)
ENGINE = MergeTree
ORDER BY (video_session_id, interval_start)
SETTINGS min_bytes_for_wide_part = 0;

CREATE TABLE IF NOT EXISTS sonyliv_trunc.cc_minute_delta_fix
    AS sonyliv_trunc.cc_minute_delta;

CREATE OR REPLACE VIEW sonyliv_trunc.v_concurrency_minute_delta_total_fix AS
SELECT
    minute,
    toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS concurrent
FROM sonyliv_trunc.cc_minute_delta_fix
GROUP BY minute;

-- ---------------------------------------------------------------------------
-- Two-row probe for the second finding: `starts` / `ends` are
-- SimpleAggregateFunction(sum, Int64), so the negative corrective row ADR 0006
-- mandates cannot be represented. Inserting -100 stores 2^64-100 silently.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sonyliv_trunc.probe_uint
(
    k      UInt8,
    starts SimpleAggregateFunction(sum, Int64)
)
ENGINE = AggregatingMergeTree ORDER BY k;

-- ---------------------------------------------------------------------------
-- Serving views over the test tables. Identical arithmetic to sql/20_views.sql
-- (hour-partitioned running sum, ADR 0003) — if these diverged from production
-- the test would be measuring the wrong thing.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW sonyliv_trunc.v_concurrency_minute_delta_total AS
SELECT
    minute,
    toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS concurrent
FROM sonyliv_trunc.cc_minute_delta
GROUP BY minute;

CREATE OR REPLACE VIEW sonyliv_trunc.v_concurrency_minute_delta_total_control AS
SELECT
    minute,
    toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS concurrent
FROM sonyliv_trunc.cc_minute_delta_control
GROUP BY minute;

-- Independent cross-check: expand the intervals instead of summing deltas.
-- Same answer by a different route, so a bug in the delta arithmetic cannot
-- hide behind a bug in the interval arithmetic.
CREATE OR REPLACE VIEW sonyliv_trunc.v_concurrency_minute_intervals AS
SELECT toDateTime(m) AS minute, uniqExact(video_session_id) AS concurrent
FROM (
    SELECT video_session_id,
           arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
                           toUInt32(toStartOfMinute(interval_end)) + 1, 60)) AS m
    FROM sonyliv_trunc.session_intervals FINAL
)
GROUP BY minute;
