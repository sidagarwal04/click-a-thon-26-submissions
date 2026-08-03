-- ============================================================================
-- 20_views.sql — read-only views for charting and ad-hoc reads.
--
-- These exist because a chart tool cannot read an AggregateFunction column.
-- cc_minute_stateless.active_state is AggregateFunction(uniqExact, String):
-- correct for storage and merging, but HyperDX (or any BI tool) needs a plain
-- number. The merge belongs in a view, once, rather than being re-typed into
-- every chart definition where it can be got subtly wrong.
--
-- Views are free: no storage, no merge cost, and re-running this file is
-- idempotent, so it is safe on every boot and every target.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Minute-grain concurrency from the SESSION-INDEPENDENT (stateless) model.
--
-- Named _stateless deliberately: `v_concurrency_minute` is reserved for the
-- accurate gap-based model (TODOS H3). Two models, two views, and the
-- comparison between them is an explicit deliverable — so they must never be
-- silently swapped behind one name.
--
-- Grain: one row per (minute, platform, country, content_id). Summing
-- `concurrent` across dimensions is NOT valid — a session active on two
-- content_ids would be counted twice. Filter, then read; do not aggregate up.
-- Use v_concurrency_minute_total for the all-dimensions curve.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_concurrency_minute_stateless AS
SELECT
    minute,
    platform,
    country,
    content_id,
    uniqExactMerge(active_state) AS concurrent
FROM cc_minute_stateless
GROUP BY minute, platform, country, content_id;

-- ---------------------------------------------------------------------------
-- The headline curve: total concurrency per minute, all dimensions collapsed.
--
-- This re-merges the states rather than summing the per-dimension view, which
-- is the whole point — uniqExactMerge over the underlying states deduplicates a
-- session that appears under several content_ids, and SUM() would not.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_concurrency_minute_total AS
SELECT
    minute,
    uniqExactMerge(active_state) AS concurrent
FROM cc_minute_stateless
GROUP BY minute;

-- ---------------------------------------------------------------------------
-- THE ACCURATE MODEL. Minute-grain concurrency from session_intervals — the
-- gap+pause hybrid built in 30_build_intervals.sql, not the stateless baseline.
--
-- This expands each active interval across the minutes it covers. That is the
-- O(sessions x minutes) explosion the statement warns about, and it is NOT the
-- serving path: cc_minute_delta (TODOS H3) is. At this size the expansion is
-- ~140K rows and answers instantly, so it is a legitimate way to chart the real
-- model today without waiting on H3. Swap the source to the delta table when it
-- lands; the columns are identical on purpose.
--
-- A session spanning minutes M..N is counted in every one of them, and
-- uniqExact dedupes a session whose intervals touch the same minute twice.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_concurrency_minute_intervals AS
SELECT
    toDateTime(m) AS minute,
    uniqExact(video_session_id) AS concurrent
FROM
(
    SELECT
        video_session_id,
        arrayJoin(range(
            toUInt32(toStartOfMinute(interval_start)),
            toUInt32(toStartOfMinute(interval_end)) + 1,
            60
        )) AS m
    FROM session_intervals FINAL
)
GROUP BY minute;

-- Same, split by the dimensions dashboards filter on.
CREATE OR REPLACE VIEW v_concurrency_minute_intervals_dim AS
SELECT
    toDateTime(m) AS minute,
    platform,
    country,
    content_id,
    uniqExact(video_session_id) AS concurrent
FROM
(
    SELECT
        video_session_id, platform, country, content_id,
        arrayJoin(range(
            toUInt32(toStartOfMinute(interval_start)),
            toUInt32(toStartOfMinute(interval_end)) + 1,
            60
        )) AS m
    FROM session_intervals FINAL
)
GROUP BY minute, platform, country, content_id;

-- ---------------------------------------------------------------------------
-- THE SERVING PATH (ADR 0003). Concurrency from cc_minute_delta, not from
-- expanding intervals: O(intervals) rows instead of O(sessions x minutes).
--
-- The running sum MUST partition by hour. Deltas are hour-clipped, so each
-- hour's sum is absolute and standalone — that is what removes the carry-in
-- scan from t=0. Forgetting the PARTITION BY produces numbers that look
-- plausible and are wrong; docs/CONVENTIONS.md flags it.
--
-- These emit a row only where concurrency CHANGES. A dashboard wanting every
-- minute should add `ORDER BY minute WITH FILL STEP 60` at query time rather
-- than densifying here, which would defeat the whole point of a delta model.
--
-- The outer aggregate is deliberate: AggregatingMergeTree merges in the
-- background, so before a merge there can be several parts holding rows for the
-- same key. Summing inside the window makes the view correct at any merge state.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_concurrency_minute AS
SELECT
    minute,
    platform,
    country,
    content_id,
    toInt64(sum(sum(delta)) OVER (
        PARTITION BY platform, country, content_id, toStartOfHour(minute)
        ORDER BY minute
    )) AS concurrent
FROM cc_minute_delta
GROUP BY minute, platform, country, content_id;

-- Headline curve off the delta model. Deltas ARE summable across dimensions
-- (peak is not) because session_intervals assigns one dimension tuple per
-- interval, so no session is double counted here.
CREATE OR REPLACE VIEW v_concurrency_minute_delta_total AS
SELECT
    minute,
    toInt64(sum(sum(delta)) OVER (
        PARTITION BY toStartOfHour(minute)
        ORDER BY minute
    )) AS concurrent
FROM cc_minute_delta
GROUP BY minute;
