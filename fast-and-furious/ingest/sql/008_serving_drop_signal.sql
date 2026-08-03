-- 008_serving_drop_signal.sql — drop detection for concurrency, per dimension value.
--
-- A ClickStack alert is a threshold on a tile's value. "Viewers dropped" is not a
-- threshold: 400 concurrent is a catastrophe for a slice that normally runs 4,000 and
-- a record for one that normally runs 40. So the *tile* has to compute the drop and the
-- alert thresholds on that. This view is that computation, in one reviewable place
-- rather than smeared across dashboard JSON.
--
-- Reads serving_concurrency_minute, NOT serving_concurrency_live. The live table is
-- ReplacingMergeTree with ORDER BY (dim_mask, bucket_start, content_id) and no country
-- column: adding one would make two countries in the same bucket collapse into a single
-- row, silently, because the sort key is also the dedup key. Re-keying needs DROP TABLE,
-- which the service user deliberately does not hold. The minute layer is a plain
-- MergeTree that already materialises country at masks 2 and 3, so it is both correct
-- and available. The cost is detection latency, quantified in the header of 009.
--
-- Four failure modes this is built around. The first is the one that matters.
--
--   1. ABSENCE OF DATA IS NOT A LOW VALUE. If a slice stops reporting entirely — the
--      thing you most want paged for — the naive query returns no row for it, and a
--      threshold on "value below X" never fires, because there is no value to compare.
--      The alert stays green through a total outage. Fixed by generating the full
--      minute x slice grid and LEFT JOINing observations onto it, so a slice that
--      vanishes reads 0 and breaches, instead of disappearing from the result set.
--
--   2. THE NEWEST BUCKET IS ALWAYS INCOMPLETE. The minute layer publishes on a lag, so
--      the most recent minutes are either absent or half-filled, and every evaluation
--      would see a cliff at the right-hand edge. is_settled comes from the layer's own
--      watermark, not from wall clock, and the alert tile requires it.
--
--   3. SMALL NUMBERS ARE NOISE. 3 viewers falling to 1 is a 67% drop and means nothing.
--      Slices whose baseline is under min_baseline report retention = 1.0 — "no
--      opinion" — rather than a breach.
--
--   4. AN EMPTY WINDOW FRAME YIELDS nan. The first minutes of any series have no
--      trailing history, and nan compares false against every threshold, which would
--      make the breach silently unevaluatable. Guarded explicitly.
--
-- Parameterized rather than now()-relative so the same definition serves the live
-- dashboard and a backtest against a known historical drop. 090_validate_serving.sql
-- exercises it against the 2026-07-26 ramp-down.
--
-- The baseline is a trailing MEDIAN, not a mean. A mean is dragged by the very spike or
-- gap being detected; the median ignores up to half the window. Deliberately no
-- same-time-yesterday seasonality term: the extract carries one traffic event, so a
-- day-over-day baseline would be fitted to a single sample.
--
-- Intended for dimensions of bounded cardinality — country, platform, video_type,
-- category. The grid is (minutes x slices), so pointing it at content (3,357 titles)
-- would materialise millions of rows to no purpose; per-title collapse is a
-- merchandising question, not a paging one.

CREATE OR REPLACE VIEW {{db}}.serving_drop_signal AS
WITH
    -- Truncated to the minute, and this is load-bearing rather than cosmetic. The grid
    -- below is built as read_from + N minutes and LEFT JOINed to minute_start, which is
    -- always minute-aligned. A caller passing 11:00:17 — which every dashboard range
    -- does, since it is whatever wall clock the page loaded at — generates grid keys at
    -- :17 past, the join matches nothing, every slice reads 0 observed, every baseline
    -- collapses to 0, has_opinion goes false, and retention pins to 1.0. The detector
    -- reports perfect health for a window it cannot see, and no alert can ever fire.
    -- Silent, permanently green, and indistinguishable from a healthy service.
    toStartOfMinute(parseDateTimeBestEffort({win_from:String}, 'UTC')) AS win_from,
    toStartOfMinute(parseDateTimeBestEffort({win_to:String}, 'UTC'))   AS win_to,
    {baseline_minutes:UInt16}                              AS baseline_minutes,
    {min_baseline:Float64}                                 AS min_baseline,

    -- The read window reaches back before the display window, so the first displayed
    -- minute already has a full baseline behind it. Without this the detector is blind
    -- for its first baseline_minutes on every load.
    win_from - toIntervalMinute(baseline_minutes)           AS read_from,

    -- Anchored to the layer, not to now(). The minute layer is rebuilt on a lag; its
    -- watermark is the only honest statement of what is complete.
    (SELECT max(watermark_ts) FROM {{db}}.serving_watermark FINAL WHERE layer = 'minute')
                                                           AS minute_watermark,
    slices AS
    (
        -- Every slice seen anywhere in the read window, so one that later goes to zero
        -- still has a grid row to report zero *on*. This is what makes failure mode 1
        -- detectable rather than invisible.
        SELECT DISTINCT dim_values
        FROM {{db}}.serving_minute_current
        WHERE grouping = {grouping_key:String}
          AND minute_start >= read_from
          AND minute_start <  win_to
    ),
    grid AS
    (
        SELECT read_from + toIntervalMinute(number) AS minute_start
        FROM numbers(greatest(toInt64(0), dateDiff('minute', read_from, win_to)))
    ),
    observed AS
    (
        SELECT
            minute_start,
            dim_values,
            sum(active_ms) / 60000.0 AS observed,
            max(minute_peak)         AS minute_peak
        FROM {{db}}.serving_minute_current
        WHERE grouping = {grouping_key:String}
          AND minute_start >= read_from
          AND minute_start <  win_to
        GROUP BY minute_start, dim_values
    ),
    dense AS
    (
        SELECT
            g.minute_start                     AS minute_start,
            s.dim_values                       AS dim_values,
            coalesce(o.observed, 0.0)          AS observed,
            coalesce(o.minute_peak, toUInt32(0)) AS minute_peak
        FROM grid AS g
        CROSS JOIN slices AS s
        LEFT JOIN observed AS o
               ON o.minute_start = g.minute_start
              AND o.dim_values   = s.dim_values
    ),
    scored AS
    (
        SELECT
            minute_start,
            dim_values,
            observed,
            minute_peak,
            -- Trailing window ENDS at 1 PRECEDING: the minute under test is excluded
            -- from its own baseline, or a gradual slide would keep re-baselining itself
            -- downward and never breach.
            median(observed) OVER (
                PARTITION BY dim_values
                ORDER BY minute_start
                ROWS BETWEEN {baseline_minutes:UInt16} PRECEDING AND 1 PRECEDING
            ) AS baseline_raw
        FROM dense
    ),
    signal AS
    (
        SELECT
            minute_start,
            dim_values,
            round(observed, 6)                                  AS observed,
            minute_peak,
            round(if(isNaN(baseline_raw), 0.0, baseline_raw), 6) AS baseline,

            -- has_opinion folds failure modes 3 and 4 into one flag the tiles can trust.
            (NOT isNaN(baseline_raw)) AND baseline_raw >= min_baseline AS has_opinion,

            -- 1.0 = holding, 0.0 = gone. Clamped so a legitimate surge cannot mask a
            -- concurrent drop elsewhere by dragging a min() upward.
            if((NOT isNaN(baseline_raw)) AND baseline_raw >= min_baseline,
               least(1.0, round(observed / baseline_raw, 6)),
               1.0)                                             AS retention,
            minute_start < minute_watermark                      AS is_settled
        FROM scored
    )
SELECT
    minute_start,
    {grouping_key:String} AS grouping,
    dim_values,
    observed,
    minute_peak,
    baseline,
    has_opinion,
    retention,
    round(100.0 * (1.0 - retention), 3)              AS drop_pct,
    if(has_opinion, observed - baseline, 0.0)         AS delta_viewers,

    -- Persistence, expressed so that it stays independent of the threshold. The rolling
    -- MAX over the last (persist_minutes + 1) minutes is below T only when EVERY one of
    -- those minutes was below T, so a single threshold on this column means "sustained
    -- for that many consecutive minutes" without the view ever knowing what T is.
    --
    -- This is what makes the alert usable rather than merely correct. Backtested over
    -- the whole extract at T = 0.7, the raw retention column breaches in three episodes:
    -- a lone minute at 0.6475 on 2026-07-26 08:53 (a blip), the genuine 19-minute
    -- broadcast ramp-down from 11:19, and an 8-minute generator stop on 2026-08-01.
    -- Requiring two consecutive minutes drops the blip and keeps both real events.
    --
    -- A no-opinion minute carries retention = 1.0 and therefore breaks a run, which is
    -- the intended reading: a slice that fell below the noise floor has not demonstrated
    -- anything, so it must not be counted toward sustained failure.
    max(retention) OVER (
        PARTITION BY dim_values
        ORDER BY minute_start
        ROWS BETWEEN {persist_minutes:UInt16} PRECEDING AND CURRENT ROW
    ) AS retention_sustained,

    is_settled
FROM signal
WHERE minute_start >= win_from
ORDER BY minute_start, dim_values;
