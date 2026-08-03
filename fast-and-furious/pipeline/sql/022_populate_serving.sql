-- ============================================================================
-- Stage 02: populate the serving layer from active_intervals_current.
--
-- This is the second half of the one scheduled step. 011 derives intervals from
-- events; this derives the two serving structures from those intervals. It is
-- deliberately NOT a materialized view over active_intervals, for the same two
-- reasons 011 is not one over events_clean:
--
--   * the day anchor is a CUMULATIVE level, which is not insert-commutative --
--     late data landing before an anchor invalidates it and every later one
--   * session_live_state resolves by state_revision across a session's whole
--     revision history, which is not block-local
--
-- The one hop here that IS a materialized view -- concurrency_deltas ->
-- concurrency_bucket_net, defined in 020 -- fires by itself when statement A
-- inserts. Nothing in this file writes concurrency_bucket_net directly, and if
-- statement B comes back empty that is the MV having failed to fire, not a bug
-- in statement B. That is a deliberate canary.
--
-- Run with:
--   clickhouse-client --queries-file pipeline/sql/022_populate_serving.sql \
--     --param_policy_version=sonyliv-active-v1 \
--     --param_clip_variant=unclipped \
--     --param_state_revision=1 \
--     --param_allow_append=0 \
--     --param_insert_token='stage02:sonyliv-active-v1:full:rev1'
--
-- allow_append=0 is the safe default and refuses to run against a non-empty
-- target. To rebuild:
--   TRUNCATE TABLE sonyliv.concurrency_deltas;
--   TRUNCATE TABLE sonyliv.concurrency_bucket_net;
--   TRUNCATE TABLE sonyliv.concurrency_day_anchor;
--   TRUNCATE TABLE sonyliv.session_live_state;
--   TRUNCATE TABLE sonyliv.pipeline_watermark;
-- then re-run. TRUNCATE, not DROP: the tables carry deduplication settings that
-- CREATE TABLE IF NOT EXISTS would not reapply.
--
-- SCOPE, STATED PLAINLY. This is the FULL-REBUILD path only. Every interval in
-- active_intervals_current is treated as sealed, which is true for a frozen
-- extract -- evaluation_as_of is past the last observed event, so no interval
-- can still move. An incremental run against a live stream must additionally
-- apply the seal predicate described at statement A, and that is not
-- implemented here. Do not run this on a stream and assume it is correct.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Guard 1: the source must exist and must be balanced.
--
-- Every interval contributes exactly one open and one close, so opens must
-- equal closes and the running sum must return to zero. If it does not, the
-- interval builder produced unpaired boundaries and every concurrency number
-- derived from them is wrong -- silently, because an unbalanced curve still
-- returns a plausible-looking maximum. Checked here rather than after the
-- insert, because after the insert the damage is in a Summing table.
-- ----------------------------------------------------------------------------

SELECT throwIf(
    (SELECT count() FROM sonyliv.active_intervals_current
     WHERE policy_version = {policy_version:String}) = 0,
    'active_intervals_current is empty for this policy_version. Run 011 first.'
);

SELECT throwIf(
    (SELECT countIf(end_time <= start_time) FROM sonyliv.active_intervals_current
     WHERE policy_version = {policy_version:String}) > 0,
    'active_intervals_current contains intervals with end_time <= start_time. These produce a -1 before their +1 and drive the running sum negative.'
);


-- ----------------------------------------------------------------------------
-- Guard 2: the target must be empty.
--
-- MEASURED, THE HARD WAY. concurrency_deltas is a Summing table: a second
-- insert ADDS to the first, so a re-run does not overwrite the curve, it
-- doubles it. Observed on this service on 2026-08-01 -- statement A run twice,
-- four seconds apart, with a byte-identical insert_deduplication_token:
--
--   20:12:18  QueryFinish  written_rows = 524292  token = stage02:...:rev1
--   20:12:22  QueryFinish  written_rows = 524292  token = stage02:...:rev1
--
-- Both wrote. The peak went to 4,610, exactly 2 x 2,305, and every invariant
-- still passed: sum(net) = 0, min(running) = 0, opens = closes. A doubled
-- curve is perfectly balanced, so the balance checks cannot see it. That is
-- the entire problem -- it is a silent 2x on the one number being scored.
--
-- DO NOT RELY ON insert_deduplication_token FOR THIS. A 524k-row INSERT SELECT
-- is split into several blocks and the token is suffixed per block, so two runs
-- whose block boundaries differ produce different dedup keys. The token still
-- has value against an exact single-block replay; it is not an idempotency
-- guarantee for a large INSERT SELECT, and this file no longer treats it as one.
--
-- The guard is the mechanism. To rebuild, TRUNCATE first -- deliberately, as a
-- separate act -- or pass allow_append=1 if adding to an existing curve is
-- genuinely what you mean.
-- ----------------------------------------------------------------------------

SELECT throwIf(
    {allow_append:UInt8} = 0
        AND (SELECT count() FROM sonyliv.concurrency_deltas
             WHERE policy_version = {policy_version:String}) > 0,
    'concurrency_deltas already holds rows for this policy_version. It is a Summing table, so inserting again ADDS to the curve and silently doubles the peak, and every balance invariant still passes. TRUNCATE sonyliv.concurrency_deltas, sonyliv.concurrency_bucket_net and sonyliv.concurrency_day_anchor and re-run, or pass allow_append=1 if you really mean to accumulate.'
);

SELECT throwIf(
    {allow_append:UInt8} = 0
        AND (SELECT count() FROM sonyliv.session_live_state
             WHERE policy_version = {policy_version:String}) > 0,
    'session_live_state already holds rows for this policy_version. Re-running at the SAME state_revision leaves two states tied on the argMax ordering key and the winner becomes arbitrary. Either TRUNCATE, or bump state_revision so the new rows strictly win.'
);


-- ----------------------------------------------------------------------------
-- Statement A: boundaries -> concurrency_deltas.
--
-- Each interval emits +1 at start_time and +1 close at end_time, replicated
-- across all ten rollup masks from solution/policy.yaml.
--
-- GROUP BY here rather than leaving it to the merge, for two reasons: the merge
-- is eventual and may never run, and pre-aggregating means the inserted block
-- is already at the table's grain so a reader is correct at zero merges.
--
-- SEAL PREDICATE -- what an incremental run must add and this does not:
--     AND end_time <= (watermark - lateness_allowance)
-- An open session's trailing interval end moves forward with every liveness
-- ping (93% of the stream), so publishing it would mean retracting and
-- re-adding a boundary per ping. Omitted here because a frozen extract has no
-- unsealed intervals: evaluation_as_of already sits past the last event.
--
-- THE TEN MASKS ARE WRITTEN OUT LITERALLY, not computed from the bits. They
-- have to be diffable by eye against solution/policy.yaml `default_masks`,
-- because getting one wrong produces a populated, plausible, wrong slice rather
-- than an error. Bits: platform=1, country=2, content_id=4, video_type=8.
-- 63,894 intervals x 2 boundaries x 10 masks = 1,277,880 rows before collapse.
-- ----------------------------------------------------------------------------

INSERT INTO sonyliv.concurrency_deltas
    (policy_version, clip_variant, rollup_mask, platform, country, content_id,
     video_type, boundary_ts, opens, closes)
SELECT
    policy_version,
    clip_variant,
    rollup_mask,
    CAST(platform_v   AS LowCardinality(String)) AS platform,
    CAST(country_v    AS LowCardinality(String)) AS country,
    content_id_v                                 AS content_id,
    CAST(video_type_v AS LowCardinality(String)) AS video_type,
    boundary_ts,
    sum(is_open)  AS opens,
    sum(is_close) AS closes
FROM
(
    SELECT
        i.policy_version AS policy_version,
        i.clip_variant   AS clip_variant,
        m.1              AS rollup_mask,
        m.2              AS platform_v,
        m.3              AS country_v,
        m.4              AS content_id_v,
        m.5              AS video_type_v,
        b.1              AS boundary_ts,
        b.2              AS is_open,
        b.3              AS is_close
    FROM sonyliv.active_intervals_current AS i
    -- Two boundaries per interval. Half-open [start, end): the start raises the
    -- curve at start_time, the end lowers it at end_time.
    ARRAY JOIN
        [
            (i.start_time, toUInt32(1), toUInt32(0)),
            (i.end_time,   toUInt32(0), toUInt32(1))
        ] AS b
    -- (mask, platform, country, content_id, video_type). A dimension whose bit
    -- is clear carries the neutral value, so a mask filter alone can never mix
    -- grains and a mistyped dimension returns nothing rather than the total.
    ARRAY JOIN
        [
            -- mask  platform                country                content_id           video_type
            (toUInt16( 0), '',                    '',                    toInt64(0),          ''                     ),
            (toUInt16( 1), toString(i.platform),  '',                    toInt64(0),          ''                     ),
            (toUInt16( 2), '',                    toString(i.country),   toInt64(0),          ''                     ),
            (toUInt16( 4), '',                    '',                    i.content_id,        ''                     ),
            (toUInt16( 8), '',                    '',                    toInt64(0),          toString(i.video_type) ),
            (toUInt16( 3), toString(i.platform),  toString(i.country),   toInt64(0),          ''                     ),
            (toUInt16( 5), toString(i.platform),  '',                    i.content_id,        ''                     ),
            (toUInt16( 9), toString(i.platform),  '',                    toInt64(0),          toString(i.video_type) ),
            (toUInt16(12), '',                    '',                    i.content_id,        toString(i.video_type) ),
            (toUInt16(15), toString(i.platform),  toString(i.country),   i.content_id,        toString(i.video_type) )
        ] AS m
    WHERE i.policy_version = {policy_version:String}
)
GROUP BY policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, boundary_ts
SETTINGS
    -- Belt, not braces. This catches an exact single-block replay; it does NOT
    -- make a large INSERT SELECT idempotent, because the token is suffixed per
    -- block and this insert spans several. Measured: two runs with this exact
    -- token four seconds apart both wrote 524,292 rows. Guard 2 above is what
    -- actually prevents the double; this is a cheap second line only.
    insert_deduplication_token = {insert_token:String},
    max_execution_time = 300;


-- ----------------------------------------------------------------------------
-- Statement B: concurrency_bucket_net -> concurrency_day_anchor.
--
-- The absolute level at each UTC midnight, so the peak read's `base` lookup is
-- bounded at 1,440 minute rows rather than growing with retained history.
--
-- Built over a DAY SPINE, not over the days that happen to have deltas. A day
-- with no boundary at all still needs an anchor row: without one the peak read
-- for that day finds no base, silently substitutes zero, and under-reports by
-- however many sessions were already open at midnight. Generating the spine
-- from min..max and left-joining the nets makes that impossible by
-- construction rather than by luck.
--
-- level(D) = sum of every net strictly BEFORE D, hence the 1 PRECEDING frame.
-- The first day is therefore always 0, which is the correct starting level.
-- ----------------------------------------------------------------------------

INSERT INTO sonyliv.concurrency_day_anchor
    (policy_version, clip_variant, rollup_mask, platform, country, content_id, video_type, day, level)
WITH
    daily AS
    (
        SELECT
            policy_version, clip_variant, rollup_mask,
            platform, country, content_id, video_type,
            toDate(bucket)                     AS day,
            toInt64(sum(opens) - sum(closes))  AS net
        FROM sonyliv.concurrency_bucket_net
        WHERE policy_version = {policy_version:String}
        GROUP BY policy_version, clip_variant, rollup_mask,
                 platform, country, content_id, video_type, day
    ),
    span AS
    (
        SELECT
            min(day) AS first_day,
            -- +2: one extra day so the anchor after the last boundary exists,
            -- which is what a window starting the morning after reads.
            toUInt64(dateDiff('day', min(day), max(day)) + 2) AS n_days
        FROM daily
    ),
    spine AS
    (
        SELECT
            d.policy_version AS policy_version,
            d.clip_variant   AS clip_variant,
            d.rollup_mask    AS rollup_mask,
            d.platform       AS platform,
            d.country        AS country,
            d.content_id     AS content_id,
            d.video_type     AS video_type,
            (SELECT first_day FROM span) + toIntervalDay(offset) AS day
        FROM (SELECT DISTINCT policy_version, clip_variant, rollup_mask,
                     platform, country, content_id, video_type FROM daily) AS d
        ARRAY JOIN range((SELECT n_days FROM span)) AS offset
    )
SELECT
    s.policy_version,
    s.clip_variant,
    s.rollup_mask,
    s.platform,
    s.country,
    s.content_id,
    s.video_type,
    s.day,
    sum(ifNull(dl.net, 0)) OVER
    (
        PARTITION BY s.policy_version, s.clip_variant, s.rollup_mask,
                     s.platform, s.country, s.content_id, s.video_type
        ORDER BY s.day
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS level
FROM spine AS s
LEFT JOIN daily AS dl
    ON  s.policy_version = dl.policy_version
    AND s.clip_variant   = dl.clip_variant
    AND s.rollup_mask    = dl.rollup_mask
    AND s.platform       = dl.platform
    AND s.country        = dl.country
    AND s.content_id     = dl.content_id
    AND s.video_type     = dl.video_type
    AND s.day            = dl.day
SETTINGS
    join_algorithm = 'full_sorting_merge',
    insert_deduplication_token = {insert_token:String},
    max_execution_time = 300;


-- ----------------------------------------------------------------------------
-- Statement C: active_intervals_current + events_clean -> session_live_state.
--
-- One resolved row per session. Every non-monotone field goes through
-- argMaxState(..., state_revision) rather than max(), because max is a ratchet
-- and a later revision can legitimately move a value BACKWARD -- a late pause
-- shortens a lease. Only state_revision and recompacted_at use
-- SimpleAggregateFunction(max, ...), and only because those two are monotone
-- by construction.
--
-- Read via argMaxMerge under GROUP BY session_key. Never FINAL, never a bare
-- SELECT: the -Merge form is correct against a completely unmerged table, and
-- merge here is eventual and may never happen.
--
-- lease_expiry comes from the UNCLIPPED variant deliberately. The clipped
-- variant truncates at the observation horizon, which would make every open
-- session look as though its lease expired exactly when the data ran out.
--
-- HONEST NOTE ON A FROZEN EXTRACT. is_active_now is derived here as "the
-- session's lease still ran past the last event we observed", which is the only
-- thing a static extract can tell us. Against a live stream this field must
-- instead carry the three-axis conjunction at the session's last event, taken
-- straight out of 011's state machine -- gating on play/pause state alone moves
-- measured active-time inflation from +26.12% to +0.27%, and taking it from the
-- builder makes the residual zero rather than small. The read path is unchanged
-- either way, because the lease is always evaluated against now() at read time.
-- ----------------------------------------------------------------------------

INSERT INTO sonyliv.session_live_state
    (policy_version, session_key, state_revision, lease_expiry, is_active_now,
     is_terminated, open_interval_start, user_key, content_id,
     platform, country, video_type, recompacted_at)
WITH
    -- toUInt64 is NOT redundant. The ordering argument's type is part of an
    -- AggregateFunction's type IDENTITY, not a value that gets coerced: a bare
    -- literal parses as UInt8, producing argMax(DateTime64, UInt8), and the
    -- insert then fails with "Conversion from AggregateFunction(argMax,
    -- DateTime64(3,'UTC'), UInt8) to ... UInt64 is not supported". The bound
    -- parameter is already UInt64, so this only matters when the parameter is
    -- inlined as a literal -- which is exactly what happens when these
    -- statements are pasted into a console. Pinning it here makes both paths
    -- behave the same.
    toUInt64({state_revision:UInt64}) AS rev,
    assumeNotNull((SELECT max(event_ts) FROM sonyliv.events_clean)) AS observation_horizon,
    terminal AS
    (
        SELECT session_key, toUInt8(1) AS ended
        FROM sonyliv.events_clean
        WHERE signal = 'session_end'
        GROUP BY session_key
    )
-- The per-session scalars are folded in the inner query and the -State
-- functions applied in the outer one. They cannot be combined: an aggregate
-- inside an aggregate -- argMaxState(max(x), rev) -- is rejected outright
-- ("Aggregate function is found inside another aggregate function"). The outer
-- GROUP BY session_key groups a relation that already has one row per session,
-- so it reshapes rather than aggregates.
SELECT
    {policy_version:String} AS policy_version,
    session_key,
    rev AS state_revision,

    argMaxState(lease_val,      rev) AS lease_expiry,
    argMaxState(active_val,     rev) AS is_active_now,
    argMaxState(terminated_val, rev) AS is_terminated,
    argMaxState(last_start_val, rev) AS open_interval_start,
    argMaxState(user_val,       rev) AS user_key,
    argMaxState(content_val,    rev) AS content_id,
    argMaxState(platform_val,   rev) AS platform,
    argMaxState(country_val,    rev) AS country,
    argMaxState(video_val,      rev) AS video_type,

    now64(3, 'UTC') AS recompacted_at
FROM
(
    SELECT
        i.session_key                                        AS session_key,
        max(i.end_time)                                      AS lease_val,
        -- The lease outlives the last event we ever saw => the session was
        -- still open when observation stopped. On a live stream, replace with
        -- 011's three-axis state (see the note above).
        toUInt8(max(i.end_time) > observation_horizon)       AS active_val,
        toUInt8(max(ifNull(t.ended, toUInt8(0))) = 1)        AS terminated_val,
        -- Start of the session's LAST interval, which is the open one if any is.
        max(i.start_time)                                    AS last_start_val,
        any(i.user_key)                                      AS user_val,
        any(i.content_id)                                    AS content_val,
        toString(any(i.platform))                            AS platform_val,
        toString(any(i.country))                             AS country_val,
        toString(any(i.video_type))                          AS video_val
    FROM sonyliv.active_intervals_current AS i
    LEFT JOIN terminal AS t ON i.session_key = t.session_key
    WHERE i.policy_version = {policy_version:String}
      AND i.clip_variant   = 'unclipped'
    GROUP BY i.session_key
)
GROUP BY session_key
SETTINGS
    join_algorithm = 'full_sorting_merge',
    insert_deduplication_token = {insert_token:String},
    max_execution_time = 300;


-- ----------------------------------------------------------------------------
-- Statement D: advance the watermark.
--
-- Written LAST and only on success. Every statement above either completed or
-- threw; there is no partial-success path that reaches here. The watermark is
-- a timestamp taken from dirty_sessions, never dirty_operation_id -- that
-- column is an xxHash64, not a sequence, and a `>` predicate against it selects
-- a pseudo-random half of the queue.
-- ----------------------------------------------------------------------------

INSERT INTO sonyliv.pipeline_watermark
    (stage, policy_version, watermark, state_revision, sessions_applied)
SELECT
    'stage02_serving' AS stage,
    {policy_version:String} AS policy_version,
    ifNull((SELECT max(last_ingested_at) FROM sonyliv.dirty_sessions), toDateTime64(0, 3, 'UTC')) AS watermark,
    {state_revision:UInt64} AS state_revision,
    (SELECT uniqExact(session_key) FROM sonyliv.active_intervals_current
     WHERE policy_version = {policy_version:String}) AS sessions_applied;


-- ============================================================================
-- Verification. These are the point of the file: the serving layer has to
-- reproduce the interval layer's answer, or it is the serving layer that is
-- wrong.
-- ============================================================================

-- V0. CONSERVATION. The only check here that needs no prior knowledge of the
--     answer, and therefore the only one that works on an unseen day.
--
--     Every interval contributes exactly one open and one close, so for each
--     variant sum(opens) over the global mask must EQUAL the interval count in
--     the source. Nothing else in this file can detect a scalar multiple: a
--     doubled curve is perfectly balanced, so sum(net) = 0, min(running) = 0
--     and opens = closes all still pass. That is exactly how a 2x doubling
--     survived every other verification on 2026-08-01 and was caught only
--     because 2,305 happened to be known.
--
--     Ratio is reported alongside the throw so a failure says how wrong it is:
--     2.0 means the load ran twice, 0.5 means half of it is missing.
SELECT
    d.clip_variant                                   AS clip_variant,
    d.delta_opens                                    AS delta_opens,
    s.source_intervals                               AS source_intervals,
    round(d.delta_opens / s.source_intervals, 4)     AS ratio_must_be_1
FROM
(
    SELECT clip_variant, sum(opens) AS delta_opens
    FROM sonyliv.concurrency_deltas
    WHERE policy_version = {policy_version:String} AND rollup_mask = 0
    GROUP BY clip_variant
) AS d
INNER JOIN
(
    SELECT clip_variant, count() AS source_intervals
    FROM sonyliv.active_intervals_current
    WHERE policy_version = {policy_version:String}
    GROUP BY clip_variant
) AS s USING (clip_variant)
ORDER BY clip_variant;

SELECT throwIf(
    (
        SELECT max(abs(toInt64(d.delta_opens) - toInt64(s.source_intervals)))
        FROM
        (
            SELECT clip_variant, sum(opens) AS delta_opens
            FROM sonyliv.concurrency_deltas
            WHERE policy_version = {policy_version:String} AND rollup_mask = 0
            GROUP BY clip_variant
        ) AS d
        INNER JOIN
        (
            SELECT clip_variant, count() AS source_intervals
            FROM sonyliv.active_intervals_current
            WHERE policy_version = {policy_version:String}
            GROUP BY clip_variant
        ) AS s USING (clip_variant)
    ) > 0,
    'CONSERVATION VIOLATED: boundaries in concurrency_deltas do not match intervals in active_intervals_current. A ratio of 2.0 means the load ran twice into a Summing table and the concurrency curve is doubled -- balanced, plausible, and wrong. TRUNCATE the three concurrency tables and re-run once.'
);


-- V1. Boundaries are balanced and the curve never goes negative, read straight
--     out of concurrency_deltas. Expect peak 2305 at 2026-07-26 10:55:28.614,
--     must_be_zero = 0, must_be_ge_zero = 0, for BOTH clip variants.
SELECT
    clip_variant,
    max(running)          AS peak_concurrency,
    argMax(ts, running)   AS peak_instant,
    sum(net)              AS must_be_zero,
    min(running)          AS must_be_ge_zero
FROM
(
    SELECT
        clip_variant, ts,
        sum(net) OVER (PARTITION BY clip_variant ORDER BY ts
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running,
        net
    FROM
    (
        SELECT clip_variant, boundary_ts AS ts,
               toInt64(sum(opens)) - toInt64(sum(closes)) AS net
        FROM sonyliv.concurrency_deltas
        WHERE policy_version = {policy_version:String} AND rollup_mask = 0
        GROUP BY clip_variant, ts
    )
)
GROUP BY clip_variant
ORDER BY clip_variant;


-- V2. The checkpoint path -- anchor + bucket nets + in-window deltas -- must
--     give the SAME peak for the hot hour as V1 gives for the whole extract.
--     This is the query the design exists to make cheap, so it is the one that
--     has to be right. Expect 2305.
--
--     GROUP BY boundary_ts before the running sum is load-bearing: it is what
--     implements stop-wins at the same millisecond, and it is the difference
--     between exactly 2305 and approximately right.
WITH
    toDateTime64('2026-07-26 10:00:00.000', 3, 'UTC') AS w0,
    toDateTime64('2026-07-26 11:00:00.000', 3, 'UTC') AS w1,
    base AS
    (
        SELECT
            ifNull((SELECT level FROM sonyliv.concurrency_day_anchor FINAL
                    WHERE policy_version = {policy_version:String}
                      AND clip_variant = {clip_variant:String}
                      AND rollup_mask = 0 AND platform = '' AND country = '' AND content_id = 0 AND video_type = ''
                      AND day = toDate(w0)), 0)
            + ifNull((SELECT toInt64(sum(opens)) - toInt64(sum(closes))
                      FROM sonyliv.concurrency_bucket_net
                      WHERE policy_version = {policy_version:String}
                        AND clip_variant = {clip_variant:String}
                        AND rollup_mask = 0 AND platform = '' AND country = '' AND content_id = 0 AND video_type = ''
                        AND bucket >= toStartOfDay(w0) AND bucket < w0), 0) AS lvl
    ),
    inner_prefix AS
    (
        SELECT
            boundary_ts,
            sum(toInt64(sum(opens)) - toInt64(sum(closes)))
                OVER (ORDER BY boundary_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS pfx
        FROM sonyliv.concurrency_deltas
        WHERE policy_version = {policy_version:String}
          AND clip_variant = {clip_variant:String}
          AND rollup_mask = 0 AND platform = '' AND country = '' AND content_id = 0 AND video_type = ''
          AND boundary_ts >= w0 AND boundary_ts < w1
        GROUP BY boundary_ts
    )
SELECT
    (SELECT lvl FROM base)                                                AS level_at_window_start,
    greatest((SELECT lvl FROM base),
             (SELECT lvl FROM base) + (SELECT max(pfx) FROM inner_prefix)) AS hot_hour_peak,
    (SELECT argMax(boundary_ts, pfx) FROM inner_prefix)                    AS peak_instant;


-- V3. Row counts and the zero-net-bucket hazard. n_deltas exists so that a
--     bucket netting to zero is not deleted on merge; buckets_net_zero > 0 with
--     all rows still present is the mitigation working.
SELECT
    (SELECT count() FROM sonyliv.concurrency_deltas)     AS delta_rows,
    (SELECT count() FROM sonyliv.concurrency_bucket_net) AS bucket_rows,
    (SELECT count() FROM sonyliv.concurrency_day_anchor) AS anchor_rows,
    (SELECT count() FROM sonyliv.session_live_state)     AS live_state_rows,
    (SELECT countIf(opens = closes) FROM sonyliv.concurrency_bucket_net) AS buckets_net_zero;


-- V4. The live-count read path. On this frozen extract every lease expired long
--     ago, so live_now is expected to be 0 -- the point is that the query shape
--     runs and resolves revisions correctly, not the number. still_open_at_horizon
--     is the meaningful figure here: sessions whose lease outlived the last event.
SELECT
    countIf(active = 1 AND terminated = 0)                         AS still_open_at_horizon,
    countIf(terminated = 1)                                        AS terminated_sessions,
    countIf(terminated = 0 AND active = 1 AND lease > now64(3))    AS live_now,
    count()                                                        AS sessions
FROM
(
    SELECT
        session_key,
        argMaxMerge(lease_expiry)  AS lease,
        argMaxMerge(is_active_now) AS active,
        argMaxMerge(is_terminated) AS terminated
    FROM sonyliv.session_live_state
    WHERE policy_version = {policy_version:String}
    GROUP BY session_key
);
