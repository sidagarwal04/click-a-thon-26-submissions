-- =============================================================================
-- 020_rollup_live.sql — session_intervals -> serving_concurrency_live (10s grain)
--
-- Best-effort layer. It rebuilds a short trailing window every few seconds and
-- does NOT wait for late events, which is the honest trade for a "right now"
-- number. The corrected answer is 030_rollup_minute.sql.
--
-- Parameters (textual {{db}}; the rest bound server-side):
--   {window_start:String}   inclusive left edge, 'YYYY-MM-DD hh:mm:ss.SSS' UTC
--   {window_end:String}     exclusive right edge — the watermark
--   {lookback_days:UInt16}  how far back to scan session_intervals partitions
--   {version:UInt64}        ms since epoch; higher wins on replacement
--
-- lookback_days exists because session_intervals partitions on the session's
-- START date while this query filters on interval time. A session that opened
-- days ago can still be active now — the longest in the extract runs 43.64h — so
-- the scan has to reach back past the window. It is a parameter rather than a
-- constant so the bound is visible and tunable rather than a magic 3.
--
-- HOW THE PEAK IS MADE EXACT
-- ---------------------------------------------------------------------------
-- Concurrency changes only at interval endpoints, so the usual shape is ±1
-- boundary rows and a prefix sum. That alone produces two wrong answers:
--
--   * a bucket containing no endpoint gets no row at all, so a plateau reads as
--     a gap;
--   * a bucket's peak may occur BEFORE its first endpoint — concurrency 100
--     entering the bucket, one interval closing inside it, max over rows inside
--     the bucket = 99, true peak = 100.
--
-- Both are the same missing fact: the concurrency carried INTO each bucket. So
-- every bucket a session touches also emits a synthetic zero-delta row at its
-- left edge. The prefix sum carries the running value onto that row, which makes
--
--   max(c)         over the bucket = the true in-bucket peak
--   argMax(c, t)   over the bucket = concurrency at the bucket's closing edge
--
-- and no separate carry-forward or WITH FILL pass is needed.
--
-- Deltas are collapsed by timestamp BEFORE the prefix sum. Intervals are
-- half-open [start, end), so one interval ending exactly when another begins is
-- a net change of zero; summing them in row order would otherwise expose a
-- one-row dip or spike that never existed at any instant.
--
-- Both dim_mask values are produced in a single pass by fanning each interval
-- out over [0, 4] and blanking content_id for mask 0. Two passes over
-- session_intervals would read the same partitions twice to compute a total that
-- is a strict aggregate of what the first pass already saw.
-- =============================================================================

INSERT INTO {{db}}.serving_concurrency_live
    (bucket_start, dim_mask, content_id, bucket_peak, ending_concurrency, active_ms, version)
WITH
    toDateTime64({window_start:String}, 3, 'UTC') AS win_start,
    toDateTime64({window_end:String},   3, 'UTC') AS win_end,
    10000 AS bucket_ms,

    -- Active intervals clipped to the window. Clipping is what seeds the prefix
    -- sum correctly: an interval already open at win_start has its start pulled
    -- forward to win_start, so its +1 lands on the window's first instant and the
    -- running total begins at the true concurrency rather than at zero.
    bounds AS
    (
        SELECT
            content_id,
            toInt64(toUnixTimestamp64Milli(greatest(ivl.1, win_start))) AS s_ms,
            toInt64(toUnixTimestamp64Milli(least(ivl.2, win_end)))      AS e_ms
        FROM
        (
            SELECT content_id, arrayJoin(intervals) AS ivl
            FROM {{db}}.session_intervals FINAL
            WHERE session_start_date >= toDate(win_start) - {lookback_days:UInt16}
        )
        WHERE ivl.1 < win_end AND ivl.2 > win_start
    ),

    -- One row per (interval, mask). content_id is blanked for the ungrouped
    -- total so a single GROUP BY produces both grains.
    masked AS
    (
        SELECT
            m AS dim_mask,
            if(m = 0, toInt64(0), content_id) AS grp_content,
            s_ms,
            e_ms
        FROM bounds
        ARRAY JOIN [toUInt8(0), toUInt8(4)] AS m
        WHERE e_ms > s_ms
    ),

    -- Every 10s bucket each interval touches. The upper bound uses e_ms - 1
    -- because the interval is half-open: one ending exactly on a bucket edge does
    -- not reach into that bucket. Everything stays Int64 so the millisecond
    -- arithmetic below never mixes signed and unsigned operands.
    spans AS
    (
        SELECT
            dim_mask,
            grp_content,
            s_ms,
            e_ms,
            toInt64(arrayJoin(range(
                toUInt64(intDiv(s_ms, bucket_ms) * bucket_ms),
                toUInt64(intDiv(e_ms - 1, bucket_ms) * bucket_ms + bucket_ms),
                toUInt64(bucket_ms)
            ))) AS bkt_ms
        FROM masked
    ),

    -- Real endpoint deltas, plus a zero-delta at every touched bucket edge.
    events AS
    (
        SELECT dim_mask, grp_content, s_ms AS t_ms, toInt64(1) AS d FROM masked
        UNION ALL
        SELECT dim_mask, grp_content, e_ms AS t_ms, toInt64(-1) AS d FROM masked
        UNION ALL
        SELECT DISTINCT dim_mask, grp_content, bkt_ms AS t_ms, toInt64(0) AS d FROM spans
    ),

    net AS
    (
        SELECT dim_mask, grp_content, t_ms, sum(d) AS d
        FROM events
        GROUP BY dim_mask, grp_content, t_ms
    ),

    running AS
    (
        SELECT
            dim_mask, grp_content, t_ms,
            sum(d) OVER (
                PARTITION BY dim_mask, grp_content ORDER BY t_ms
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS c
        FROM net
    ),

    agg_peak AS
    (
        SELECT
            dim_mask,
            grp_content,
            intDiv(t_ms, bucket_ms) * bucket_ms AS bkt_ms,
            toUInt32(greatest(max(c), 0))       AS bucket_peak,
            toUInt32(greatest(argMax(c, t_ms), 0)) AS ending_concurrency
        FROM running
        GROUP BY dim_mask, grp_content, bkt_ms
    ),

    -- active_ms is an intersection measure, not a delta measure, so it is summed
    -- over interval-bucket overlaps rather than derived from the prefix sum.
    agg_time AS
    (
        SELECT
            dim_mask,
            grp_content,
            bkt_ms,
            sum(least(e_ms, bkt_ms + bucket_ms) - greatest(s_ms, bkt_ms)) AS active_ms
        FROM spans
        GROUP BY dim_mask, grp_content, bkt_ms
    )

SELECT
    toDateTime(intDiv(p.bkt_ms, 1000), 'UTC') AS bucket_start,
    p.dim_mask,
    p.grp_content AS content_id,
    p.bucket_peak,
    p.ending_concurrency,
    toUInt64(t.active_ms) AS active_ms,
    {version:UInt64} AS version
FROM agg_peak AS p
LEFT JOIN agg_time AS t USING (dim_mask, grp_content, bkt_ms)
-- A bucket can exist in agg_peak but not agg_time: an interval ending exactly on
-- a bucket edge puts its -1 in the next bucket without touching it. Such a row is
-- real only if something else was active there.
WHERE p.bucket_peak > 0 OR t.active_ms > 0
SETTINGS join_use_nulls = 0;
