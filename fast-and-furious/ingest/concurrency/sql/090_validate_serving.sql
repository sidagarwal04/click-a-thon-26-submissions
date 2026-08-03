-- =============================================================================
-- 090_validate_serving.sql — one row per invariant, with a verdict
--
--   make rollup-check
--   ./ingest/concurrency/ch.sh --file ingest/concurrency/sql/090_validate_serving.sql
--
-- Two kinds of check, and the distinction matters when reading the output:
--
--   REFERENCE   compares against a figure independently measured in chDB over
--               the hash-identified CSV bytes and recorded in
--               solution/evidence/MEASURED.md. A failure here means the model
--               changed answer.
--
--   INVARIANT   a property that must hold for any input, including an unseen
--               day. A failure here is a bug regardless of what the extract says.
--
-- The reference checks scope themselves to sessions whose events all came from
-- the packaged CSV, so synthetic rows written by the API, the mock dashboard or a
-- load generator cannot move a number that is supposed to be fixed. The
-- dashboards deliberately do NOT filter that way — they show everything in the
-- table — so the "as served" row reports what a tile will actually render.
--
-- Every check carries its own pass flag rather than having the final SELECT
-- compare two strings. The comparison genuinely differs per check — equality
-- against a measured constant, a count that must be zero, a cardinality — and
-- expressing that as string matching produced false failures.
-- =============================================================================

WITH
    -- Canonical hot hour, solution/evidence/MEASURED.md:188.
    toDateTime64('2026-07-26 10:00:00.000', 3, 'UTC') AS hot_h0,
    toDateTime64('2026-07-26 11:00:00.000', 3, 'UTC') AS hot_h1,

    extract_sessions AS
    (
        SELECT DISTINCT sipHash64(video_session_id) AS session_key
        FROM {{db}}.events_raw
        WHERE _source_file = 'csv:ch-hackathon-raw-data.csv'
    ),

    iv AS
    (
        SELECT session_key, arrayJoin(intervals) AS ivl
        FROM {{db}}.session_intervals FINAL
    ),

    -- ---------------------------------------------------------------- REFERENCE
    r_intervals AS
    (
        SELECT
            'REFERENCE' AS kind,
            'session_intervals: interval count (extract only)' AS check,
            '31947' AS expected,
            toString(count()) AS actual,
            count() = 31947 AS pass
        FROM iv WHERE session_key IN extract_sessions
    ),

    r_hours AS
    (
        SELECT
            'REFERENCE',
            'session_intervals: session-hours (extract only)',
            '1779.502796',
            toString(round(sum(dateDiff('millisecond', ivl.1, ivl.2)) / 3600000.0, 6)),
            round(sum(dateDiff('millisecond', ivl.1, ivl.2)) / 3600000.0, 6) = 1779.502796
        FROM iv WHERE session_key IN extract_sessions
    ),

    r_sessions AS
    (
        SELECT
            'REFERENCE',
            'session_intervals: sessions with active time (extract only)',
            '10848',
            toString(count()),
            count() = 10848
        FROM
        (
            SELECT session_key FROM {{db}}.session_intervals FINAL
            WHERE session_key IN extract_sessions AND notEmpty(intervals)
        )
    ),

    -- Recomputed straight from the intervals rather than read out of the serving
    -- table, so this checks the model. The rollup is checked by the row below it.
    r_hot_avg AS
    (
        SELECT
            'REFERENCE',
            'hot hour 2026-07-26 10:00-11:00Z: time-weighted average (extract only)',
            '855.578199',
            toString(round(sum(dateDiff('millisecond', greatest(ivl.1, hot_h0), least(ivl.2, hot_h1))) / 3600000.0, 6)),
            round(sum(dateDiff('millisecond', greatest(ivl.1, hot_h0), least(ivl.2, hot_h1))) / 3600000.0, 6) = 855.578199
        FROM iv
        WHERE session_key IN extract_sessions AND ivl.1 < hot_h1 AND ivl.2 > hot_h0
    ),

    r_hot_peak AS
    (
        SELECT
            'REFERENCE',
            'hot hour: exact in-minute peak, dim_mask=0 (as served)',
            '2305',
            toString(max(minute_peak)),
            max(minute_peak) = 2305
        FROM {{db}}.serving_concurrency_minute
        WHERE dim_mask = 0 AND minute_start >= hot_h0 AND minute_start < hot_h1
    ),

    -- ---------------------------------------------------------------- INVARIANT
    -- The one that catches a dropped or double-counted session. active_ms is
    -- additive across every dimension, so every mask must total identically over
    -- the same window. A mask fan-out bug shows up here and almost nowhere else.
    i_conservation AS
    (
        SELECT
            'INVARIANT',
            'minute layer: sum(active_ms) identical across all dim_masks',
            '1 distinct total',
            concat(toString(uniqExact(total)), ' distinct: ',
                   arrayStringConcat(arraySort(groupUniqArray(toString(total))), ', ')),
            uniqExact(total) = 1
        FROM
        (
            SELECT dim_mask, sum(active_ms) AS total
            FROM {{db}}.serving_concurrency_minute
            GROUP BY dim_mask
        )
    ),

    -- ending_concurrency IS additive across the rows of one mask at one instant,
    -- because a session belongs to exactly one slice. So the per-content rows must
    -- sum to the precomputed ungrouped total, minute by minute.
    i_additive AS
    (
        SELECT
            'INVARIANT',
            'minute layer: sum(ending_concurrency) over mask 4 equals mask 0',
            '0 mismatched minutes',
            concat(toString(countIf(m4 != m0)), ' mismatched of ', toString(count()), ' minutes'),
            countIf(m4 != m0) = 0
        FROM
        (
            SELECT
                minute_start,
                sumIf(ending_concurrency, dim_mask = 4) AS m4,
                sumIf(ending_concurrency, dim_mask = 0) AS m0
            FROM {{db}}.serving_concurrency_minute
            WHERE dim_mask IN (0, 4)
            GROUP BY minute_start
        )
    ),

    -- A peak below the value at the closing edge is impossible: the closing value
    -- is one of the values the peak maximises over.
    i_peak_bounds AS
    (
        SELECT
            'INVARIANT',
            'minute layer: minute_peak >= ending_concurrency everywhere',
            '0 violations',
            toString(countIf(minute_peak < ending_concurrency)),
            countIf(minute_peak < ending_concurrency) = 0
        FROM {{db}}.serving_concurrency_minute
    ),

    -- A minute cannot hold more session-time than peak concurrency sustained for
    -- the whole minute.
    i_active_bounds AS
    (
        SELECT
            'INVARIANT',
            'minute layer: active_ms <= minute_peak * 60000',
            '0 violations',
            toString(countIf(active_ms > toUInt64(minute_peak) * 60000)),
            countIf(active_ms > toUInt64(minute_peak) * 60000) = 0
        FROM {{db}}.serving_concurrency_minute
    ),

    i_live_bounds AS
    (
        SELECT
            'INVARIANT',
            'live layer: bucket_peak >= ending_concurrency and active_ms <= peak*10000',
            '0 violations',
            concat(toString(countIf(bucket_peak < ending_concurrency OR active_ms > toUInt64(bucket_peak) * 10000)),
                   ' of ', toString(count()), ' buckets'),
            countIf(bucket_peak < ending_concurrency OR active_ms > toUInt64(bucket_peak) * 10000) = 0
        FROM {{db}}.serving_concurrency_live FINAL
    ),

    -- The two layers duplicate the same core logic in two files, so they are
    -- cross-checked where their time ranges overlap. This is the check that earned
    -- its keep: it caught the live rollup clipping its window's LEADING edge
    -- mid-bucket, which left seven consecutive minutes holding about a third of
    -- their real active_ms. Ground truth recomputed from session_intervals agreed
    -- with the minute layer, which is how the live layer was identified as the
    -- wrong one.
    --
    -- Compared on active_ms because it is the only metric both layers compute
    -- additively, and bounded twice.
    --
    -- Older than both watermarks: otherwise it compares a live layer rebuilt
    -- seconds ago against a minute layer rebuilt minutes ago and reports the lag
    -- between them, which is the design working.
    --
    -- And no older than 10 minutes: the live layer only rebuilds a trailing window,
    -- so once a bucket falls out of it the bucket is a FROZEN snapshot. It was
    -- written while those sessions were still open, when each interval ended at the
    -- optimistic last_signal + 120s lease, and it is never revisited. The minute
    -- layer later rebuilds the same minute from settled intervals that are shorter.
    -- Measured: every disagreement was 38-57 minutes old and the live value was
    -- always the higher one. That difference IS the correction the lagged layer
    -- exists to make, so it is reported below as evidence rather than asserted to be
    -- zero here.
    i_cross_layer AS
    (
        SELECT
            'INVARIANT',
            'live vs minute: agree on recent minutes settled in both',
            '0 disagreeing minutes',
            concat(toString(countIf(l != m)), ' of ', toString(count()), ' settled minutes'),
            countIf(l != m) = 0
        FROM
        (
            SELECT l.minute AS minute, l.active_ms AS l, m.active_ms AS m
            FROM
            (
                SELECT toStartOfMinute(bucket_start) AS minute, sum(active_ms) AS active_ms
                FROM {{db}}.serving_concurrency_live FINAL
                WHERE dim_mask = 0
                GROUP BY minute
                -- Only minutes the live layer covers completely: six 10s buckets.
                HAVING count() = 6
            ) AS l
            INNER JOIN
            (
                SELECT minute_start AS minute, sum(active_ms) AS active_ms
                FROM {{db}}.serving_concurrency_minute
                WHERE dim_mask = 0
                GROUP BY minute
            ) AS m USING (minute)
            WHERE minute + toIntervalMinute(1) <=
            (
                SELECT least(minIf(watermark_ts, layer = 'live'), minIf(watermark_ts, layer = 'minute'))
                FROM {{db}}.serving_watermark FINAL
                WHERE layer IN ('live', 'minute')
            )
            AND minute > now64(3) - toIntervalMinute(10)
        )
    ),

    -- Informational, not pass/fail: how much the lagged layer actually corrects.
    -- The live layer freezes each bucket with an optimistic lease-extended interval
    -- end; the minute layer rebuilds it from settled intervals. This quantifies the
    -- gap on minutes the live layer has stopped revisiting, which is the concrete
    -- answer to "what does waiting five minutes buy you".
    i_correction AS
    (
        SELECT
            'EVIDENCE',
            'live vs minute on frozen minutes: how much the lagged layer corrects',
            'informational',
            if(count() = 0, 'no frozen overlap yet',
               concat(toString(count()), ' minutes, live over-reports by ',
                      toString(round(100.0 * sum(toInt64(l) - toInt64(m)) / nullIf(sum(m), 0), 3)), '%')),
            1
        FROM
        (
            SELECT l.active_ms AS l, m.active_ms AS m
            FROM
            (
                SELECT toStartOfMinute(bucket_start) AS minute, sum(active_ms) AS active_ms
                FROM {{db}}.serving_concurrency_live FINAL
                WHERE dim_mask = 0 GROUP BY minute HAVING count() = 6
            ) AS l
            INNER JOIN
            (
                SELECT minute_start AS minute, sum(active_ms) AS active_ms
                FROM {{db}}.serving_concurrency_minute
                WHERE dim_mask = 0 GROUP BY minute
            ) AS m USING (minute)
            WHERE minute <= now64(3) - toIntervalMinute(10)
        )
    ),

    -- Gaps in the minute series are legitimate whenever concurrency reached zero.
    -- The extract has no events at all between Jul 15 and Jul 20, and the sparse
    -- days genuinely go idle a minute at a time — measured: all 24 single-minute
    -- gaps follow a minute that ended at zero concurrency. What WOULD be a bug is
    -- a gap while viewers were still present, which is what a failure of the
    -- zero-delta bucket rows to carry a plateau forward would look like.
    i_no_holes AS
    (
        SELECT
            'INVARIANT',
            'minute layer: no gap in the series while viewers were still present',
            '0 gaps',
            concat(toString(countIf(gap_s > 60 AND prev_ending > 0)), ' of ',
                   toString(countIf(gap_s > 60)), ' gaps had viewers present'),
            countIf(gap_s > 60 AND prev_ending > 0) = 0
        FROM
        (
            SELECT
                dateDiff('second', lagInFrame(minute_start) OVER w, minute_start) AS gap_s,
                lagInFrame(ending_concurrency) OVER w AS prev_ending
            FROM
            (
                SELECT minute_start, ending_concurrency
                FROM {{db}}.serving_concurrency_minute
                WHERE dim_mask = 0
            )
            WINDOW w AS (ORDER BY minute_start ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
    ),

    i_watermark AS
    (
        SELECT
            'INVARIANT',
            'serving_watermark: a row per built layer, none dated in the future',
            '0 future watermarks',
            concat(toString(countIf(watermark_ts > now64(3) + toIntervalMinute(1))), ' future of ',
                   toString(count()), ' layers: ', arrayStringConcat(arraySort(groupArray(layer)), ', ')),
            countIf(watermark_ts > now64(3) + toIntervalMinute(1)) = 0
        FROM {{db}}.serving_watermark FINAL
    ),

    -- The drop detector's failure mode is silence: if it stops seeing traffic it reports
    -- perfect retention, which is indistinguishable from a healthy service. So it is
    -- checked against a window whose answer is known, deliberately offset by 17 seconds
    -- because a dashboard passes whatever wall clock the page loaded at and never a
    -- minute boundary. An unaligned window once made the generated minute grid miss the
    -- join entirely: 0 observed, 0 baseline, retention pinned to 1.0, permanently green.
    -- check-tiles.sh cannot catch this — the SQL succeeds, it just answers "all well".
    d_alignment AS
    (
        SELECT
            'INVARIANT',
            'drop detector: an unaligned window still sees the 2026-07-26 11:00 traffic',
            'observed > 2000 concurrent',
            concat(toString(round(anyIf(observed, minute_start = '2026-07-26 11:00:00'), 2)),
                   ' concurrent, ', toString(countIf(has_opinion)), ' of ',
                   toString(count()), ' minutes with an opinion'),
            anyIf(observed, minute_start = '2026-07-26 11:00:00') > 2000
                AND countIf(has_opinion) = count()
        FROM {{db}}.serving_drop_signal(
            win_from = '2026-07-26 11:00:17', win_to = '2026-07-26 11:06:17',
            grouping_key = 'country', baseline_minutes = 15,
            min_baseline = 25, persist_minutes = 1)
    ),

    -- ---------------------------------------------------------------------
    -- Is video_resolution session-static? This DECIDES whether it may ever be
    -- a serving mask, and it is a question, not an assertion.
    --
    -- policy.yaml names five session_static dimensions and deliberately excludes
    -- audio_language, subtitle_language and player_version from serving masks,
    -- because a session that changes the value does not belong to exactly one
    -- slice -- which breaks ending_concurrency's additivity and makes a per-slice
    -- peak ill-defined. Measured violations there: 8,796 / 2,980 / 1,600 sessions.
    --
    -- video_resolution arrives with the unseen day and is defined as "resolution
    -- DURING video playback", which adaptive bitrate changes mid-session by
    -- design. So the prior is that it belongs with the excluded three, not with
    -- app_version (0 violations). This check settles it on real data rather than
    -- on the prior, and it PASSES either way: a non-zero count is information,
    -- not a failure. What would be a failure is materialising a mask on the
    -- assumption and reporting a wrong peak.
    d_resolution_static AS
    (
        SELECT
            'INVARIANT',
            'video_resolution: session-static? (decides mask eligibility)',
            'informational -- report, never fail',
            if(count() = 0,
               'no video_resolution data yet; unseen day not loaded',
               concat(toString(countIf(distinct_resolutions > 1)), ' of ',
                      toString(count()), ' sessions change resolution mid-session',
                      ' -> ', if(countIf(distinct_resolutions > 1) = 0,
                                 'ELIGIBLE as a session dimension',
                                 'NOT eligible; treat like audio_language'))),
            1
        FROM
        (
            SELECT session_key, uniqExact(video_resolution) AS distinct_resolutions
            FROM {{db}}.events_dedup
            WHERE video_resolution != ''
            GROUP BY session_key
        )
    ),

    -- ---------------------------------------------------------------------
    -- The dictionary-miss alarm the '__unknown__' sentinel exists to enable.
    --
    -- Dictionaries load per replica and an EMPTY one still reports LOADED, so a
    -- query routed to a cold replica silently returns the fallback for every row
    -- and then self-heals -- gone by the time anyone looks. '__unknown__' cannot
    -- occur in the catalogue ('unknown' can, and does, on 1,089 titles), so this
    -- count is zero when healthy and non-zero only on a real miss.
    --
    -- Scoped to rows that CARRY a content dimension: at masks without one the
    -- title is legitimately '' and no lookup was attempted.
    d_dict_resolves AS
    (
        SELECT
            'INVARIANT',
            'content_dict resolves every id it is asked about',
            '0 unresolved lookups',
            concat(toString(countIf(title = '__unknown__')), ' unresolved of ',
                   toString(count()), ' content-carrying rows'),
            countIf(title = '__unknown__') = 0
        FROM {{db}}.serving_minute_current
        WHERE grouping IN ('content', 'platform + content', 'all dimensions')
          AND minute_start >= hot_h0 AND minute_start < hot_h1
    ),

    -- Absence of data must read as zero, not as nothing. Traffic stops dead at 11:30 on
    -- 2026-07-26, so 11:31 onward have no source rows at all; the grid plus LEFT JOIN is
    -- what turns them into a breach instead of an empty result set that no threshold can
    -- fire on. Asserted on the count of ZERO-observed minutes, since a regression here
    -- removes rows rather than changing their values.
    d_absence AS
    (
        SELECT
            'INVARIANT',
            'drop detector: a slice that stops reporting breaches instead of vanishing',
            '>= 5 zero-viewer minutes, all at retention 0',
            concat(toString(countIf(observed = 0)), ' zero minutes, worst retention ',
                   toString(round(min(retention), 4))),
            countIf(observed = 0) >= 5
                AND countIf(observed = 0 AND has_opinion AND retention = 0) >= 5
        FROM {{db}}.serving_drop_signal(
            win_from = '2026-07-26 11:30:00', win_to = '2026-07-26 11:38:00',
            grouping_key = 'country', baseline_minutes = 15,
            min_baseline = 25, persist_minutes = 1)
    )

SELECT kind, check, expected, actual, if(pass, 'PASS', 'FAIL') AS verdict
FROM
(
    SELECT * FROM r_intervals
    UNION ALL SELECT * FROM r_hours
    UNION ALL SELECT * FROM r_sessions
    UNION ALL SELECT * FROM r_hot_avg
    UNION ALL SELECT * FROM r_hot_peak
    UNION ALL SELECT * FROM i_conservation
    UNION ALL SELECT * FROM i_additive
    UNION ALL SELECT * FROM i_peak_bounds
    UNION ALL SELECT * FROM i_active_bounds
    UNION ALL SELECT * FROM i_live_bounds
    UNION ALL SELECT * FROM i_cross_layer
    UNION ALL SELECT * FROM i_correction
    UNION ALL SELECT * FROM i_no_holes
    UNION ALL SELECT * FROM i_watermark
    UNION ALL SELECT * FROM d_alignment
    UNION ALL SELECT * FROM d_absence
    UNION ALL SELECT * FROM d_resolution_static
    UNION ALL SELECT * FROM d_dict_resolves
)
-- FAIL sorts before PASS, so anything wrong is the first thing on screen.
ORDER BY verdict, kind DESC, check
SETTINGS join_use_nulls = 0;
