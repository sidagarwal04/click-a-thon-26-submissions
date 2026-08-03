-- Classify concurrency spikes for one content id over one window.
--
-- Parameters: content_id, from_ts, to_ts, version.
--
-- NOT IN sql/insights/pipeline/. refresh_insights.sh globs that directory and runs every file
-- in it with only from_ts and to_ts bound. This statement also needs content_id and version,
-- so being globbed made refresh_insights.sh fail with an unbound-parameter error on every
-- run -- including runs that had nothing to do with spikes. A per-content classifier has a
-- different call signature from the window-only refresh steps and so gets its own directory.
--
-- WHAT A SPIKE IS HERE. The content's own minute curve, undimensioned: audience_minute_snapshot
-- stores one row per minute per dimension tuple, so concurrency for the content as a whole is the
-- SUM over tuples within a minute, never the max. Getting that wrong understates every spike by
-- however many platforms were watching.
--
-- WHY THE PEAK IS FOUND AND NOT ASSUMED. The injection scenarios peak around minute three by
-- construction, but a classifier that trusts that cannot run on real traffic. The peak is
-- argMax over the window, and every sustain metric is measured relative to where it actually
-- landed.
--
-- WHY THE PEAK AND THE BASELINE ARE TWO SEPARATE STEPS. The baseline is the quietest minute
-- BEFORE the peak, so it depends on the peak. Writing both in one SELECT nests argMax inside
-- minIf and ClickHouse rejects it outright (ILLEGAL_AGGREGATION). pk_peak finds the peak; pk
-- then aggregates the curve again against that fixed value.
--
-- THE CLASSIFICATION IS DELIBERATELY THREE-VALUED. healthy_sustained and short_lived are the two
-- outcomes the spec names, but a curve satisfying neither threshold set is `inconclusive`, not
-- silently rounded to the nearer one. A detector that always returns a confident answer is one
-- nobody can trust on the day it matters.

INSERT INTO concurrency_spike_events
(
    content_id, window_start, peak_minute, baseline_concurrency, peak_concurrency,
    absolute_growth, growth_percent, minutes_to_peak,
    minutes_above_80pct_peak, concurrency_after_5m, concurrency_after_10m, concurrency_after_15m,
    retention_5m_percent, retention_10m_percent, retention_15m_percent,
    entered_sessions, background_rate_after_peak, error_rate_after_peak, timeout_rate_after_peak,
    spike_type, confidence, version, updated_at
)
WITH
    curve AS
    (
        -- FINAL IS MANDATORY. audience_minute_snapshot is ReplacingMergeTree(version) and every
        -- refresh writes a new version per (minute, dimension tuple). Summing without FINAL adds
        -- the superseded versions too, so the peak scales with how many times the refresh has
        -- been run: measured 8,000 for a 2,000-session scenario after four runs, exactly 4x.
        -- The retention RATIOS survive it (numerator and denominator scale together), which is
        -- what makes it dangerous -- the verdict stays right while the headline number is wrong.
        SELECT minute, sum(concurrent_sessions) AS conc
        FROM audience_minute_snapshot FINAL
        WHERE content_id = {content_id:Int64}
          AND minute >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND minute <  parseDateTime64BestEffort({to_ts:String}, 3)
        GROUP BY minute
    ),
    -- ONE PASS OVER THE CURVE. `curve` was previously referenced by three separate CTEs
    -- (pk_peak, pk, sustain). ClickHouse CTEs are NOT memoized -- they re-execute on every
    -- reference, unlike Postgres -- so the FINAL scan over audience_minute_snapshot ran three
    -- times. Measured: 10,900 rows read to answer a query whose FINAL result is 172 rows.
    -- Harmless at demo scale (100ms); at a production curve of millions of minute-by-dimension
    -- rows it triples the cost of the most expensive step in the statement.
    --
    -- Fix: collect the whole curve into an array in a SINGLE aggregate pass, then answer every
    -- downstream question with array functions over that one materialisation. A per-content
    -- curve is bounded by minutes in the window, so the array is small and this is the idiomatic
    -- ClickHouse shape -- not a clever trick.
    agg AS
    (
        SELECT
            argMax(minute, conc)        AS peak_minute,
            max(conc)                   AS peak_concurrency,
            min(minute)                 AS window_start,
            groupArray((minute, conc))  AS pts
        FROM curve
    ),
    sustain AS
    (
        SELECT
            peak_minute, peak_concurrency, window_start,
            -- Quietest minute BEFORE the peak. arrayMin on an empty array throws, so a window
            -- that opens exactly at its peak reports a zero baseline rather than failing.
            arrayMin(arrayMap(x -> x.2, arrayFilter(x -> x.1 <  peak_minute, pts))) AS pre,
            if(length(arrayFilter(x -> x.1 < peak_minute, pts)) = 0, 0, pre)        AS baseline_concurrency,
            arrayMax(arrayMap(x -> x.2, arrayFilter(x -> x.1 = peak_minute + toIntervalMinute(5),  pts)) || [0]) AS after_5m,
            arrayMax(arrayMap(x -> x.2, arrayFilter(x -> x.1 = peak_minute + toIntervalMinute(10), pts)) || [0]) AS after_10m,
            arrayMax(arrayMap(x -> x.2, arrayFilter(x -> x.1 = peak_minute + toIntervalMinute(15), pts)) || [0]) AS after_15m,
            length(arrayFilter(x -> x.1 >= peak_minute AND x.2 >= (peak_concurrency * 80) / 100, pts)) AS mins_above_80,
            peak_concurrency AS peakc
        FROM agg
    ),
    -- Per-session outcomes for the sessions this spike acquired, scoped by session start so a
    -- session already watching before the ramp is not blamed on the spike.
    --
    -- Read from session_insight_facts rather than from new audience_minute_snapshot columns: the
    -- rates a verdict needs are PER SESSION ("what fraction of the sessions this spike brought in
    -- timed out"), and that table already carries timed_out, background_count and
    -- video_error_count at exactly that grain.
    outcomes AS
    (
        SELECT
            count()                    AS entered,
            avg(background_count > 0)  AS bg_rate,
            avg(video_error_count > 0) AS err_rate,
            avg(timed_out)             AS timeout_rate
        FROM session_insight_facts FINAL
        WHERE content_id = {content_id:Int64}
          AND session_start >= parseDateTime64BestEffort({from_ts:String}, 3)
          AND session_start <  parseDateTime64BestEffort({to_ts:String}, 3)
    ),
    metrics AS
    (
        SELECT
            p.window_start          AS window_start,
            p.peak_minute           AS peak_minute,
            p.baseline_concurrency  AS baseline_concurrency,
            p.peak_concurrency      AS peak_concurrency,
            p.after_5m              AS after_5m,
            p.after_10m             AS after_10m,
            p.after_15m             AS after_15m,
            p.mins_above_80         AS mins_above_80,
            o.entered               AS entered,
            o.bg_rate               AS bg_rate,
            o.err_rate              AS err_rate,
            o.timeout_rate          AS timeout_rate,
            if(p.peakc > 0, toFloat32(p.after_5m)  * 100 / p.peakc, 0) AS r5,
            if(p.peakc > 0, toFloat32(p.after_10m) * 100 / p.peakc, 0) AS r10,
            if(p.peakc > 0, toFloat32(p.after_15m) * 100 / p.peakc, 0) AS r15
        FROM sustain AS p
        CROSS JOIN outcomes AS o
    )
SELECT
    {content_id:Int64},
    window_start,
    peak_minute,
    baseline_concurrency,
    peak_concurrency,
    toInt64(peak_concurrency) - toInt64(baseline_concurrency),
    if(baseline_concurrency > 0,
       (toFloat32(peak_concurrency) - baseline_concurrency) * 100 / baseline_concurrency,
       100),
    toUInt16(dateDiff('minute', window_start, peak_minute)),

    toUInt16(mins_above_80),
    toUInt32(after_5m),
    toUInt32(after_10m),
    toUInt32(after_15m),
    r5, r10, r15,

    toUInt32(entered),
    toFloat32(bg_rate),
    toFloat32(err_rate),
    toFloat32(timeout_rate),

    -- The verdict. Retention at 10 minutes carries the most weight because it is the hardest to
    -- fake: a herd that is going to leave has left by then, and a real audience has not.
    -- minutes_above_80pct corroborates, so a curve that dips once and recovers is not condemned
    -- on a single unlucky sample.
    multiIf(
        r10 >= 70 AND mins_above_80 >= 8, 'healthy_sustained',
        r10 <  55 OR  mins_above_80 <= 4, 'short_lived',
        'inconclusive'),
    -- Distance from the decision boundary, clamped to [0,1]. A spike sitting on the threshold
    -- reports low confidence rather than a coin flip dressed as a verdict.
    least(toFloat32(1.0), greatest(toFloat32(0.0), abs(r10 - 62.5) / 37.5)),

    {version:UInt64},
    now()
FROM metrics
WHERE peak_concurrency > 0;
