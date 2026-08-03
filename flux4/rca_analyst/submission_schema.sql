-- ============================================================================
--  METRIC FORENSICS — complete schema
--  Dumped from the live ClickHouse Cloud deployment (v26.2).
--
--  Two databases:
--    rca        raw facts + dimensions + the stream replay
--    rca_orch   the analysis chain and its self-scheduling orchestration
--
--  Run order: this file, top to bottom, on a clean service.
--  Everything is CREATE IF NOT EXISTS / CREATE OR REPLACE — safe to re-run.
--
--  A note on engines: these are written as MergeTree / ReplacingMergeTree.
--  ClickHouse Cloud transparently materialises them as SharedMergeTree and
--  SharedReplacingMergeTree (which is what `SHOW CREATE` returns on the live
--  service). Writing them this way keeps the script runnable on OSS too.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS rca;
CREATE DATABASE IF NOT EXISTS rca_orch;


-- ============================================================================
-- SECTION 1 · rca — raw facts and dimensions
-- ============================================================================

-- Landing table. Narrow: IDs only, no denormalised dimensions.
CREATE TABLE IF NOT EXISTS rca.ad_events_stage
(
    `event_time`     DateTime,
    `app_id`         LowCardinality(String),
    `geo_device_id`  LowCardinality(String),
    `advertiser_id`  LowCardinality(String),
    `ad_format`      LowCardinality(String),
    `is_filled`      UInt8,
    `is_impression`  UInt8,
    `is_click`       UInt8,
    `revenue`        Float64
)
ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY event_time;


-- The analysis fact table. Dimensions are joined in at ingest so that every
-- downstream view is join-free — the whole analysis chain reads one table.
-- ORDER BY leads with event_time because every query is time-windowed.
CREATE TABLE IF NOT EXISTS rca.ad_events
(
    `event_time`      DateTime,
    `ingest_batch_id` UInt32,

    `app_id`          LowCardinality(String),
    `category`        LowCardinality(String),
    `publisher_tier`  LowCardinality(String),

    `geo_device_id`   LowCardinality(String),
    `region`          LowCardinality(String),
    `country`         LowCardinality(String),
    `device_model`    LowCardinality(String),
    `os_version`      LowCardinality(String),

    `advertiser_id`   LowCardinality(String),
    `vertical`        LowCardinality(String),
    `campaign_type`   LowCardinality(String),

    `ad_format`       LowCardinality(String),
    `is_filled`       UInt8,
    `is_impression`   UInt8,
    `is_click`        UInt8,
    `revenue`         Float64
)
ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (event_time, ad_format, app_id);


-- ---- dimensions ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rca.apps
(
    `app_id`         LowCardinality(String),
    `category`       LowCardinality(String),
    `publisher_tier` LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY app_id;


CREATE TABLE IF NOT EXISTS rca.geo_device
(
    `geo_device_id` LowCardinality(String),
    `region`        LowCardinality(String),
    `country`       LowCardinality(String),
    `device_model`  LowCardinality(String),
    `os_version`    LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY geo_device_id;


CREATE TABLE IF NOT EXISTS rca.advertisers
(
    `advertiser_id` LowCardinality(String),
    `vertical`      LowCardinality(String),
    `campaign_type` LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY advertiser_id;


-- ---- application observability ---------------------------------------------
-- Every API call the app layer makes is logged here: latency, rows returned,
-- error, and the trace id that ties the row back to the LLM trace.
-- 30-day TTL because this is operational telemetry, not analysis data.
CREATE TABLE IF NOT EXISTS rca.app_events
(
    `event_id`      UUID DEFAULT generateUUIDv4(),
    `ts`            DateTime64(3) DEFAULT now64(3),
    `endpoint`      LowCardinality(String),
    `run_id`        String,
    `status`        LowCardinality(String),
    `stage`         LowCardinality(String),
    `latency_ms`    UInt32,
    `rows_returned` UInt32,
    `error`         String,
    `trace_id`      String
)
ENGINE = MergeTree
ORDER BY (ts, endpoint)
TTL toDateTime(ts) + INTERVAL 30 DAY;


-- ============================================================================
-- SECTION 2 · rca — stream replay
--
-- Turns the static stage table into a moving stream so the detector is
-- exercised against arriving data rather than a finished table. Each tick
-- advances a watermark and loads the next slice, joining dimensions on the way.
--
-- The watermark is the max event_time already loaded, so the replay catches up
-- automatically after any missed tick and stops on its own once the stage table
-- is exhausted (the window moves past the data and returns zero rows).
--
-- nullIf(..., toDateTime(0)) is load-bearing: max() over an empty DateTime
-- column returns 1970-01-01, not NULL, so a plain ifNull() never bootstraps.
--
-- Exactly ONE refreshable MV may target rca.ad_events. APPEND does not
-- deduplicate, so two concurrent refreshes would each insert the same slice.
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS rca.replay
REFRESH EVERY 30 SECOND APPEND
TO rca.ad_events
AS
WITH
    nullIf((SELECT max(event_time) FROM rca.ad_events), toDateTime(0)) AS wm,
    (SELECT min(event_time) FROM rca.ad_events_stage)                  AS t0,
    ifNull(toStartOfHour(wm) + INTERVAL 1 HOUR, t0)                    AS lo
SELECT
    e.event_time                            AS event_time,
    toUInt32(dateDiff('hour', t0, lo) / 6)  AS ingest_batch_id,

    e.app_id                                AS app_id,
    a.category                              AS category,
    a.publisher_tier                        AS publisher_tier,

    e.geo_device_id                         AS geo_device_id,
    g.region                                AS region,
    g.country                               AS country,
    g.device_model                          AS device_model,
    g.os_version                            AS os_version,

    e.advertiser_id                                         AS advertiser_id,
    if(e.advertiser_id = '', 'UNFILLED', adv.vertical)      AS vertical,
    if(e.advertiser_id = '', 'UNFILLED', adv.campaign_type) AS campaign_type,

    e.ad_format                             AS ad_format,
    e.is_filled                             AS is_filled,
    e.is_impression                         AS is_impression,
    e.is_click                              AS is_click,
    e.revenue                               AS revenue
FROM rca.ad_events_stage AS e
LEFT JOIN rca.apps        AS a   ON e.app_id        = a.app_id
LEFT JOIN rca.geo_device  AS g   ON e.geo_device_id = g.geo_device_id
LEFT JOIN rca.advertisers AS adv ON e.advertiser_id = adv.advertiser_id
WHERE e.event_time >= lo
  AND e.event_time <  lo + INTERVAL 6 HOUR;


-- ============================================================================
-- SECTION 3 · rca_orch — result tables
--
-- Engine per write pattern:
--   MergeTree           append-only results and history
--   ReplacingMergeTree  anything a re-run may re-emit, so replays collapse
--                       on the sort key instead of double-counting
-- ============================================================================

-- Every (metric x segment x day) that tripped a threshold.
CREATE TABLE IF NOT EXISTS rca_orch.anomalies
(
    `d`        Date,
    `metric`   LowCardinality(String),
    `dim`      LowCardinality(String),
    `val`      String,
    `value`    Float64,
    `baseline` Float64,
    `effect`   Float64,
    `z`        Float64,
    `n`        UInt64,
    `is_onset` Bool
)
ENGINE = MergeTree
ORDER BY (metric, dim, val, d);


-- Consecutive anomalous days merged into a single incident.
CREATE TABLE IF NOT EXISTS rca_orch.incidents
(
    `incident_id`  String,
    `metric`       LowCardinality(String),
    `dim`          LowCardinality(String),
    `val`          String,
    `i0`           Date,     -- incident window start
    `i1`           Date,     -- incident window end
    `b0`           Date,     -- baseline window start
    `days`         UInt64,
    `worst_effect` Float64,
    `peak_z`       Float64
)
ENGINE = MergeTree
ORDER BY incident_id;


-- Every segment's contribution to every incident.
CREATE TABLE IF NOT EXISTS rca_orch.diagnoses
(
    `incident_id`   String,
    `dim`           LowCardinality(String),
    `val`           String,
    `share`         Float64,
    `rate_incident` Float64,
    `rate_baseline` Float64,
    `seg_delta`     Float64,
    `contribution`  Float64,
    `explains`      Float64,
    `n`             UInt64
)
ENGINE = MergeTree
ORDER BY (incident_id, dim, val);


-- Is the culprit's move uniform across other dimensions, or an intersection?
-- Replacing: recomputed in full each tick, so re-emits must collapse.
CREATE TABLE IF NOT EXISTS rca_orch.uniformity
(
    `incident_id` String,
    `metric`      LowCardinality(String),
    `culprit_dim` LowCardinality(String),
    `culprit_val` LowCardinality(String),
    `other_dim`   LowCardinality(String),
    `spread`      Float64,   -- stddev of relative change across that dim's values
    `worst`       Float64,
    `best`        Float64
)
ENGINE = ReplacingMergeTree
ORDER BY (incident_id, other_dim);


-- ---- audit trail -----------------------------------------------------------

-- Append-only lifecycle log: one row per (incident, stage, record) observation.
-- event_hash is a sipHash64 of the payload, so an unchanged record re-emitted
-- on the next tick produces an identical key and is collapsed by Replacing.
-- Only a genuine change writes a new row.
CREATE TABLE IF NOT EXISTS rca_orch.incident_lifecycle_trace
(
    `observed_at`  DateTime64(3, 'UTC'),
    `incident_id`  String,
    `stage`        LowCardinality(String),
    `stage_order`  UInt8,
    `record_key`   String,
    `metric`       LowCardinality(String),
    `dim`          LowCardinality(String),
    `val`          String,
    `anomaly_date` Nullable(Date),
    `details`      String,     -- JSON: every figure behind this stage
    `event_hash`   UInt64
)
ENGINE = ReplacingMergeTree(observed_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (incident_id, stage, record_key, event_hash)
TTL observed_at + INTERVAL 180 DAY;


CREATE TABLE IF NOT EXISTS rca_orch.anomalies_history
(
    `captured_at` DateTime64(3, 'UTC'),
    `snapshot_id` String,
    `d`           Date,
    `metric`      LowCardinality(String),
    `dim`         LowCardinality(String),
    `val`         String,
    `value`       Float64,
    `baseline`    Float64,
    `effect`      Float64,
    `z`           Float64,
    `n`           UInt64,
    `is_onset`    Bool
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(captured_at)
ORDER BY (metric, dim, val, d, captured_at)
TTL captured_at + INTERVAL 180 DAY;


CREATE TABLE IF NOT EXISTS rca_orch.narration_history
(
    `captured_at`                     DateTime64(3, 'UTC'),
    `snapshot_id`                     String,
    `incident_id`                     String,
    `metric`                          LowCardinality(String),
    `window_start`                    Date,
    `window_end`                      Date,
    `days`                            UInt64,
    `metric_change_pct`               Float64,
    `peak_z`                          Float64,
    `culprit_dim`                     LowCardinality(String),
    `culprit_val`                     String,
    `culprit_baseline`                Float64,
    `culprit_value`                   Float64,
    `culprit_change_pct`              Nullable(Float64),
    `culprit_share_pct`               Float64,
    `explains_pct`                    Float64,
    `global_without_culprit`          Float64,
    `global_without_culprit_baseline` Float64,
    `clears_anomaly`                  Bool,
    `ruled_out_segments`              Array(Tuple(String, Float64)),
    `ruled_out_dimensions`            Array(Tuple(String, Float64)),
    `verdict`                         LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(captured_at)
ORDER BY (incident_id, captured_at)
TTL captured_at + INTERVAL 180 DAY;


-- ============================================================================
-- SECTION 4 · rca_orch — the analysis chain
--
-- Seven views. The whole investigation is declarative SQL; nothing is
-- materialised except the results.
-- ============================================================================

-- ---- 4.1 unpivot dimensions ------------------------------------------------
-- One event fans out into 10 (dim, val) rows, so a single scan produces every
-- dimensional breakdown at once. '__all__' is the global sentinel row.
CREATE OR REPLACE VIEW rca_orch.v_seg_hourly AS
SELECT
    toStartOfHour(event_time)     AS ts,
    kv.1                          AS dim,
    kv.2                          AS val,
    toFloat64(count())            AS requests,
    toFloat64(sum(is_filled))     AS fills,
    toFloat64(sum(is_impression)) AS impressions,
    toFloat64(sum(is_click))      AS clicks,
    sum(revenue)                  AS revenue
FROM rca.ad_events
ARRAY JOIN
[
    ('__all__',        'all'),
    ('region',         region),
    ('country',        country),
    ('device_model',   device_model),
    ('os_version',     os_version),
    ('ad_format',      ad_format),
    ('category',       category),
    ('publisher_tier', publisher_tier),
    ('vertical',       vertical),
    ('campaign_type',  campaign_type)
] AS kv
GROUP BY ts, dim, val;


-- ---- 4.2 unpivot metrics ---------------------------------------------------
-- Ratios are carried as numerator + denominator and divided only at read time,
-- so every aggregate is sum-over-sum and never an average of ratios.
-- den = 1 marks a volume metric.
--
-- The WHERE is the single chokepoint guarding demand-side dimensions: an
-- unfilled request has no advertiser, so vertical/campaign_type have no
-- denominator for requests, fill_rate or rpr. Dropping those rows here makes
-- "fill rate fell for vertical X" structurally unsayable.
CREATE OR REPLACE VIEW rca_orch.v_metric AS
SELECT ts, dim, val, m.1 AS metric, m.2 AS num, m.3 AS den, m.4 AS is_ratio
FROM rca_orch.v_seg_hourly
ARRAY JOIN
[
    ('requests',    toFloat64(requests),    1.,                     0),
    ('revenue',     revenue,                1.,                     0),
    ('fill_rate',   toFloat64(fills),       toFloat64(requests),    1),
    ('render_rate', toFloat64(impressions), toFloat64(fills),       1),
    ('ctr',         toFloat64(clicks),      toFloat64(impressions), 1),
    ('ecpm',        revenue * 1000,         toFloat64(impressions), 1),
    ('rpr',         revenue,                toFloat64(requests),    1)
] AS m
WHERE NOT (dim IN ('vertical', 'campaign_type')
       AND (val = 'UNFILLED' OR metric IN ('requests', 'fill_rate', 'rpr')));


-- ---- 4.3 detect ------------------------------------------------------------
-- Baseline is a trailing 14-day window, and volume metrics are divided by a
-- day-of-week factor first. Without that de-seasonalisation every weekend
-- reads as a 20% revenue anomaly.
--
-- Ratio metrics are left unadjusted: fill rate varies ~0.1% across weekdays,
-- so a factor would only add noise.
--
-- `baseline` is reported as sum/sum over the window (the honest published
-- figure); `b_adj` is the de-seasonalised mean used for scoring only.
CREATE OR REPLACE VIEW rca_orch.v_detect AS
WITH
daily AS
(
    SELECT
        metric, dim, val, is_ratio,
        toDate(ts)          AS d,
        sum(num)            AS num_s,
        sum(den)            AS den_s,
        sum(num) / sum(den) AS value,
        toUInt64(sum(den))  AS n
    FROM rca_orch.v_metric
    WHERE NOT (metric IN ('fill_rate', 'rpr', 'requests')
           AND dim IN ('vertical', 'campaign_type'))
    GROUP BY metric, dim, val, d, is_ratio
),
dowf AS
(
    SELECT
        metric, dim, val, dw,
        dv / avg(dv) OVER (PARTITION BY metric, dim, val) AS factor
    FROM
    (
        SELECT metric, dim, val, toDayOfWeek(d) AS dw, avg(value) AS dv
        FROM daily
        WHERE is_ratio = 0
        GROUP BY metric, dim, val, dw
    )
),
adj AS
(
    SELECT
        daily.*,
        if(is_ratio = 1, value, value / nullIf(dowf.factor, 0)) AS v_adj
    FROM daily
    LEFT JOIN dowf
           ON dowf.metric = daily.metric
          AND dowf.dim    = daily.dim
          AND dowf.val    = daily.val
          AND dowf.dw     = toDayOfWeek(daily.d)
)
SELECT
    metric, dim, val, d, value, n,
    sum(num_s) OVER w / sum(den_s) OVER w AS baseline,
    avg(v_adj) OVER w                     AS b_adj,
    stddevPop(v_adj) OVER w               AS sd_adj,
    (v_adj - b_adj) / nullIf(sd_adj, 0)   AS z,
    v_adj / nullIf(b_adj, 0) - 1          AS effect
FROM adj
WINDOW w AS (PARTITION BY metric, dim, val ORDER BY d ASC
             ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING);


-- ---- 4.4 which factor of the revenue identity moved ------------------------
-- Revenue = Requests x FillRate x RenderRate x eCPM/1000.
--
-- The identity is multiplicative, so deltas of each factor would interact and
-- leave an unexplained remainder. In log space it is exactly additive, so the
-- four terms sum to the total move.
--
-- b_rev is DERIVED from the four factor baselines rather than measured
-- independently, which makes residual = 0 by construction.
CREATE OR REPLACE VIEW rca_orch.v_factor AS
SELECT
    d,
    rev / b_rev - 1                AS rev_change,
    log(r / b_r)                   AS l_requests,
    log((f / r) / b_fill)          AS l_fill_rate,
    log((i / f) / b_render)        AS l_render_rate,
    log((rev / i * 1000) / b_ecpm) AS l_ecpm,
    log(rev / b_rev)
      - log(r / b_r)
      - log((f / r) / b_fill)
      - log((i / f) / b_render)
      - log((rev / i * 1000) / b_ecpm) AS residual
FROM
(
    SELECT
        d, r, f, i, rev,
        avg(r) OVER w                           AS b_r,       -- level: average
        sum(f) OVER w / sum(r) OVER w           AS b_fill,    -- ratios: sum/sum
        sum(i) OVER w / sum(f) OVER w           AS b_render,
        sum(rev) OVER w / sum(i) OVER w * 1000  AS b_ecpm,
        b_r * b_fill * b_render * b_ecpm / 1000 AS b_rev
    FROM
    (
        SELECT
            toDate(ts)       AS d,
            sum(requests)    AS r,
            sum(fills)       AS f,
            sum(impressions) AS i,
            sum(revenue)     AS rev
        FROM rca_orch.v_seg_hourly
        WHERE dim = '__all__'
        GROUP BY d
    )
    -- same-weekday baseline: compares Monday against the last 4 Mondays
    WINDOW w AS (PARTITION BY toDayOfWeek(d) ORDER BY d ASC
                 ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
);


-- ---- 4.5 attribute ---------------------------------------------------------
-- No parameters: windows come from the incidents table.
-- contribution = share of traffic x that segment's own delta.
-- explains     = this segment's share of the total company-wide move.
--
-- The dimensions are Zipfian, so ranking by absolute delta would name the
-- largest segment every time. Ranking by contribution finds the segment that
-- actually moved the number.
CREATE OR REPLACE VIEW rca_orch.v_attribute AS
SELECT
    incident_id, dim, val,
    di / g_di                                  AS share,
    ni / di                                    AS rate_incident,
    nb / db                                    AS rate_baseline,
    ni / di - nb / db                          AS seg_delta,
    (di / g_di) * (ni / di - nb / db)          AS contribution,
    contribution / (g_ni / g_di - g_nb / g_db) AS explains,
    toUInt64(di)                               AS n
FROM
(
    SELECT
        incident_id, dim, val, ni, di, nb, db,
        sumIf(ni, dim = '__all__') OVER (PARTITION BY incident_id) AS g_ni,
        sumIf(di, dim = '__all__') OVER (PARTITION BY incident_id) AS g_di,
        sumIf(nb, dim = '__all__') OVER (PARTITION BY incident_id) AS g_nb,
        sumIf(db, dim = '__all__') OVER (PARTITION BY incident_id) AS g_db
    FROM
    (
        SELECT
            inc.incident_id AS incident_id,
            m.dim           AS dim,
            m.val           AS val,
            sumIf(m.num, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS ni,
            sumIf(m.den, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS di,
            sumIf(m.num, toDate(m.ts) <  inc.i0)                 AS nb,
            sumIf(m.den, toDate(m.ts) <  inc.i0)                 AS db
        FROM rca_orch.incidents AS inc
        INNER JOIN rca_orch.v_metric AS m ON m.metric = inc.metric
        WHERE toDate(m.ts) BETWEEN inc.b0 AND inc.i1
        GROUP BY incident_id, dim, val
    )
)
WHERE dim != '__all__';


-- ---- 4.6 rule out ----------------------------------------------------------
-- Recompute the global metric with each candidate segment removed. If the
-- anomaly disappears, that segment is the cause; if it survives, the segment
-- is cleared. This is what backs the "checked and ruled out" claim.
--
-- Counters are additive, so "global without X" is a subtraction — no re-scan.
-- If NO row clears, the incident is diffuse and probably shouldn't have opened.
CREATE OR REPLACE VIEW rca_orch.v_ruleout AS
SELECT
    incident_id, dim, val,
    (g_ni - ni) / (g_di - di)                      AS excl_incident,
    (g_nb - nb) / (g_db - db)                      AS excl_baseline,
    abs(excl_incident / excl_baseline - 1) < 0.005 AS clears_anomaly,
    abs(excl_incident / excl_baseline - 1)         AS residual_effect
FROM
(
    SELECT
        incident_id, dim, val, ni, di, nb, db,
        sumIf(ni, dim = '__all__') OVER (PARTITION BY incident_id) AS g_ni,
        sumIf(di, dim = '__all__') OVER (PARTITION BY incident_id) AS g_di,
        sumIf(nb, dim = '__all__') OVER (PARTITION BY incident_id) AS g_nb,
        sumIf(db, dim = '__all__') OVER (PARTITION BY incident_id) AS g_db
    FROM
    (
        SELECT
            inc.incident_id AS incident_id,
            m.dim           AS dim,
            m.val           AS val,
            sumIf(m.num, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS ni,
            sumIf(m.den, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS di,
            sumIf(m.num, toDate(m.ts) <  inc.i0)                 AS nb,
            sumIf(m.den, toDate(m.ts) <  inc.i0)                 AS db
        FROM rca_orch.incidents AS inc
        INNER JOIN rca_orch.v_metric AS m ON m.metric = inc.metric
        WHERE toDate(m.ts) BETWEEN inc.b0 AND inc.i1
        GROUP BY incident_id, dim, val
    )
)
WHERE dim != '__all__'
ORDER BY incident_id ASC, residual_effect ASC;


-- ---- 4.7 narration payload -------------------------------------------------
-- One row per incident. This is the ONLY thing the LLM ever reads. Every
-- figure it may print is a column here; the model joins them into sentences
-- and never computes, infers, or supplies a number of its own.
--
-- `verdict` is a deterministic branch computed in SQL, so the narrator picks a
-- template rather than deciding how confident to sound.
CREATE OR REPLACE VIEW rca_orch.v_narration AS
SELECT
    -- what moved
    i.incident_id                  AS incident_id,
    i.metric                       AS metric,
    i.i0                           AS window_start,
    i.i1                           AS window_end,
    i.days                         AS days,
    round(100 * i.worst_effect, 2) AS metric_change_pct,
    round(i.peak_z, 1)             AS peak_z,

    -- who caused it
    c.dim                          AS culprit_dim,
    c.val                          AS culprit_val,
    round(c.rate_baseline, 4)      AS culprit_baseline,
    round(c.rate_incident, 4)      AS culprit_value,
    round(100 * (c.rate_incident / nullIf(c.rate_baseline, 0) - 1), 2)
                                   AS culprit_change_pct,
    round(100 * c.share, 1)        AS culprit_share_pct,
    round(100 * c.explains, 1)     AS explains_pct,

    -- the proof: the global metric recomputed with the culprit removed
    round(c.excl_incident, 4)      AS global_without_culprit,
    round(c.excl_baseline, 4)      AS global_without_culprit_baseline,
    c.clears_anomaly               AS clears_anomaly,

    -- what was checked and cleared
    r.ruled_out                    AS ruled_out_segments,
    u.uniform_dims                 AS ruled_out_dimensions,

    -- deterministic verdict the narrator branches on
    multiIf(
        c.explains IS NULL,                         'no_attribution',
        c.clears_anomaly = 0,                       'ambiguous_no_slice_clears',
        u.max_spread > 0.05,                        'intersection_descend',
        c.explains >= 0.9 AND c.clears_anomaly = 1, 'confirmed',
                                                    'weak'
    ) AS verdict

FROM rca_orch.incidents AS i

-- culprit + its exclusion test, joined together HERE so the outer query only
-- ever uses USING (mixing USING and ON makes incident_id ambiguous)
LEFT JOIN
(
    SELECT
        d.incident_id     AS incident_id,
        d.dim             AS dim,
        d.val             AS val,
        d.rate_baseline   AS rate_baseline,
        d.rate_incident   AS rate_incident,
        d.share           AS share,
        d.explains        AS explains,
        ro.excl_incident  AS excl_incident,
        ro.excl_baseline  AS excl_baseline,
        ro.clears_anomaly AS clears_anomaly
    FROM
    (
        SELECT * FROM
        (
            SELECT *,
                   row_number() OVER (PARTITION BY incident_id
                                      ORDER BY abs(contribution) DESC) AS rk
            FROM rca_orch.diagnoses
        )
        WHERE rk = 1
    ) AS d
    INNER JOIN rca_orch.v_ruleout AS ro
            ON ro.incident_id = d.incident_id
           AND ro.dim = d.dim
           AND ro.val = d.val
) AS c USING (incident_id)

-- runners-up: checked, not the cause
LEFT JOIN
(
    SELECT
        incident_id,
        groupArray((concat(dim, '=', val), round(100 * explains, 1))) AS ruled_out
    FROM
    (
        SELECT *,
               row_number() OVER (PARTITION BY incident_id
                                  ORDER BY abs(contribution) DESC) AS rk
        FROM rca_orch.diagnoses
    )
    WHERE rk BETWEEN 2 AND 6
    GROUP BY incident_id
) AS r USING (incident_id)

-- dimensions the move was uniform across
LEFT JOIN
(
    SELECT
        incident_id,
        groupArray((other_dim, round(spread, 4))) AS uniform_dims,
        max(spread)                               AS max_spread
    FROM rca_orch.uniformity
    GROUP BY incident_id
) AS u USING (incident_id);


-- ============================================================================
-- SECTION 5 · rca_orch — orchestration
--
-- Ten refreshable materialized views drive the entire run loop from inside the
-- database. No Airflow, no cron, no external worker.
--
--   hot path  15s   detect -> incidents -> diagnose -> uniformity -> trace
--   history   60s   point-in-time snapshots for audit
--
-- DEPENDS ON chains the stages so a downstream view refreshes only after its
-- upstream has committed, rather than racing it on a timer.
-- ============================================================================

-- ---- 5.1 detect ------------------------------------------------------------
-- Two thresholds: the outer one opens a candidate, is_onset marks a move
-- severe enough to justify opening an incident. n >= 20000 suppresses thin
-- segments whose ratios are noise.
CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.anomalies_refresh
REFRESH EVERY 15 SECOND
TO rca_orch.anomalies
AS
SELECT
    d, metric, dim, val, value, baseline, effect, z, n,
    abs(z) >= 4 AND abs(effect) >= 0.02 AS is_onset
FROM rca_orch.v_detect
WHERE n >= 20000
  AND abs(z) >= 2
  AND abs(effect) >= 0.01;


-- ---- 5.2 merge consecutive anomalous days into incidents -------------------
-- The date-minus-row_number trick: consecutive days share a constant grp.
CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.incidents_refresh
REFRESH EVERY 15 SECOND
DEPENDS ON rca_orch.anomalies_refresh
TO rca_orch.incidents
AS
SELECT
    concat(metric, '|', dim, '=', val, '@', toString(min(d))) AS incident_id,
    metric, dim, val,
    min(d)                      AS i0,
    max(d)                      AS i1,
    min(d) - 7                  AS b0,
    count()                     AS days,
    argMax(effect, abs(effect)) AS worst_effect,
    argMax(z, abs(z))           AS peak_z
FROM
(
    SELECT *,
           d - toIntervalDay(row_number() OVER (PARTITION BY metric, dim, val
                                                ORDER BY d ASC)) AS grp
    FROM rca_orch.anomalies
    WHERE dim = '__all__'
)
GROUP BY metric, dim, val, grp
HAVING max(is_onset) = 1;


-- ---- 5.3 attribute every open incident -------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.diagnoses_refresh
REFRESH EVERY 15 SECOND
DEPENDS ON rca_orch.incidents_refresh
TO rca_orch.diagnoses
AS
SELECT * FROM rca_orch.v_attribute;


-- ---- 5.4 uniformity / intersection test ------------------------------------
-- Is the culprit's move uniform across every other dimension, or concentrated
-- in an intersection? Low spread means the culprit is the whole story; high
-- spread means the real cause is a narrower slice inside it.
--
-- Reads rca.ad_events directly because it needs the raw cross-tabulation of
-- the culprit against every other dimension, which the rollup cannot provide.
CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.uniformity_refresh
REFRESH EVERY 15 SECOND
DEPENDS ON rca_orch.diagnoses_refresh
TO rca_orch.uniformity
AS
WITH culprit AS
(
    SELECT incident_id, dim AS cdim, val AS cval
    FROM
    (
        SELECT incident_id, dim, val,
               row_number() OVER (PARTITION BY incident_id
                                  ORDER BY abs(contribution) DESC) AS rk
        FROM rca_orch.diagnoses
    )
    WHERE rk = 1
)
SELECT
    incident_id, metric, culprit_dim, culprit_val, other_dim,
    stddevPop(rel) AS spread,
    min(rel)       AS worst,
    max(rel)       AS best
FROM
(
    SELECT
        incident_id, metric, culprit_dim, culprit_val,
        kv.1 AS other_dim,
        kv.2 AS other_val,
        (sumIf(num, w = 'i') / sumIf(den, w = 'i'))
          / nullIf(sumIf(num, w = 'b') / sumIf(den, w = 'b'), 0) - 1 AS rel,
        sumIf(den, w = 'i') AS n
    FROM
    (
        SELECT
            c.incident_id AS incident_id,
            i.metric      AS metric,
            c.cdim        AS culprit_dim,
            c.cval        AS culprit_val,
            if(toDate(e.event_time) BETWEEN i.i0 AND i.i1, 'i', 'b') AS w,
            multiIf(
                i.metric = 'fill_rate',   toFloat64(e.is_filled),
                i.metric = 'render_rate', toFloat64(e.is_impression),
                i.metric = 'ctr',         toFloat64(e.is_click),
                i.metric = 'ecpm',        e.revenue * 1000,
                i.metric = 'rpr',         e.revenue,
                0.
            ) AS num,
            multiIf(
                i.metric = 'render_rate',    toFloat64(e.is_filled),
                i.metric IN ('ctr', 'ecpm'), toFloat64(e.is_impression),
                1.
            ) AS den,
            map(
                'region',         e.region,
                'country',        e.country,
                'device_model',   e.device_model,
                'os_version',     e.os_version,
                'ad_format',      e.ad_format,
                'category',       e.category,
                'publisher_tier', e.publisher_tier
            ) AS dims
        FROM rca.ad_events AS e
        CROSS JOIN culprit AS c
        INNER JOIN rca_orch.incidents AS i ON i.incident_id = c.incident_id
        WHERE toDate(e.event_time) BETWEEN i.b0 AND i.i1
          AND i.metric IN ('fill_rate', 'render_rate', 'ctr', 'ecpm', 'rpr')
          AND dims[c.cdim] = c.cval
    )
    ARRAY JOIN arrayFilter(x -> x.1 != culprit_dim,
                           CAST(dims, 'Array(Tuple(String,String))')) AS kv
    GROUP BY incident_id, metric, culprit_dim, culprit_val, other_dim, other_val
    HAVING n > 1000
)
GROUP BY incident_id, metric, culprit_dim, culprit_val, other_dim;


-- ---- 5.5 lifecycle trace ---------------------------------------------------
-- Four APPEND views, one per stage, all writing to the same trace table.
-- stage_order gives a single incident's full history in sequence:
--   10 anomaly_detected -> 20 incident_created -> 30 diagnosis -> 40 narration
--
-- details is a JSON map of every figure behind that stage, and event_hash is
-- a sipHash64 over it. An unchanged record re-emitted next tick hashes
-- identically and collapses under ReplacingMergeTree, so the trace records
-- state CHANGES rather than one row per tick.

CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.trace_anomaly_refresh
REFRESH EVERY 15 SECOND APPEND
TO rca_orch.incident_lifecycle_trace
AS
WITH now64(3, 'UTC') AS observed_at
SELECT
    observed_at,
    i.incident_id,
    'anomaly_detected' AS stage,
    toUInt8(10)        AS stage_order,
    concat(a.metric, '|', a.dim, '=', a.val, '@', toString(a.d)) AS record_key,
    a.metric, a.dim, a.val,
    CAST(a.d, 'Nullable(Date)') AS anomaly_date,
    toJSONString(map(
        'value',    toString(a.value),
        'baseline', toString(a.baseline),
        'effect',   toString(a.effect),
        'z',        toString(a.z),
        'n',        toString(a.n),
        'is_onset', toString(a.is_onset)
    )) AS details,
    sipHash64(concat(stage, '|', i.incident_id, '|', record_key, '|', details))
        AS event_hash
FROM rca_orch.anomalies AS a
INNER JOIN rca_orch.incidents AS i
        ON i.metric = a.metric
       AND i.dim    = a.dim
       AND i.val    = a.val
       AND a.d BETWEEN i.i0 AND i.i1;


CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.trace_incident_refresh
REFRESH EVERY 15 SECOND APPEND
TO rca_orch.incident_lifecycle_trace
AS
WITH now64(3, 'UTC') AS observed_at
SELECT
    observed_at,
    incident_id,
    'incident_created_or_updated' AS stage,
    toUInt8(20)                   AS stage_order,
    incident_id                   AS record_key,
    metric, dim, val,
    CAST(NULL, 'Nullable(Date)')  AS anomaly_date,
    toJSONString(map(
        'window_start',   toString(i0),
        'window_end',     toString(i1),
        'baseline_start', toString(b0),
        'days',           toString(days),
        'worst_effect',   toString(worst_effect),
        'peak_z',         toString(peak_z)
    )) AS details,
    sipHash64(concat(stage, '|', incident_id, '|', record_key, '|', details))
        AS event_hash
FROM rca_orch.incidents;


CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.trace_diagnosis_refresh
REFRESH EVERY 15 SECOND APPEND
TO rca_orch.incident_lifecycle_trace
AS
WITH now64(3, 'UTC') AS observed_at
SELECT
    observed_at,
    d.incident_id,
    'diagnosis'                  AS stage,
    toUInt8(30)                  AS stage_order,
    concat(d.dim, '=', d.val)    AS record_key,
    i.metric, d.dim, d.val,
    CAST(NULL, 'Nullable(Date)') AS anomaly_date,
    toJSONString(map(
        'share',         toString(d.share),
        'rate_incident', toString(d.rate_incident),
        'rate_baseline', toString(d.rate_baseline),
        'seg_delta',     toString(d.seg_delta),
        'contribution',  toString(d.contribution),
        'explains',      toString(d.explains),
        'n',             toString(d.n)
    )) AS details,
    sipHash64(concat(stage, '|', d.incident_id, '|', record_key, '|', details))
        AS event_hash
FROM rca_orch.diagnoses AS d
INNER JOIN rca_orch.incidents AS i ON i.incident_id = d.incident_id;


CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.trace_narration_refresh
REFRESH EVERY 15 SECOND APPEND
TO rca_orch.incident_lifecycle_trace
AS
WITH now64(3, 'UTC') AS observed_at
SELECT
    observed_at,
    incident_id,
    'narration'                  AS stage,
    toUInt8(40)                  AS stage_order,
    incident_id                  AS record_key,
    metric,
    culprit_dim                  AS dim,
    culprit_val                  AS val,
    CAST(NULL, 'Nullable(Date)') AS anomaly_date,
    toJSONString(map(
        'window_start',      toString(window_start),
        'window_end',        toString(window_end),
        'metric_change_pct', toString(metric_change_pct),
        'peak_z',            toString(peak_z),
        'culprit_baseline',  toString(culprit_baseline),
        'culprit_value',     toString(culprit_value),
        'explains_pct',      toString(explains_pct),
        'clears_anomaly',    toString(clears_anomaly),
        'verdict',           verdict
    )) AS details,
    sipHash64(concat(stage, '|', incident_id, '|', record_key, '|', details))
        AS event_hash
FROM rca_orch.v_narration;


-- ---- 5.6 point-in-time snapshots -------------------------------------------
-- Slower cadence: these answer "what did the system believe at 14:32?", which
-- is what makes a published diagnosis auditable after the fact.

CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.anomalies_history_refresh
REFRESH EVERY 1 MINUTE
DEPENDS ON rca_orch.anomalies_refresh
APPEND
TO rca_orch.anomalies_history
AS
WITH now64(3, 'UTC') AS captured_at
SELECT
    captured_at,
    concat('anomalies@', toString(captured_at)) AS snapshot_id,
    d, metric, dim, val, value, baseline, effect, z, n, is_onset
FROM rca_orch.anomalies;


CREATE MATERIALIZED VIEW IF NOT EXISTS rca_orch.narration_history_refresh
REFRESH EVERY 1 MINUTE
DEPENDS ON rca_orch.uniformity_refresh
APPEND
TO rca_orch.narration_history
AS
WITH now64(3, 'UTC') AS captured_at
SELECT
    captured_at,
    concat('narration@', toString(captured_at)) AS snapshot_id,
    incident_id, metric, window_start, window_end, days,
    metric_change_pct, peak_z,
    culprit_dim, culprit_val, culprit_baseline, culprit_value,
    culprit_change_pct, culprit_share_pct, explains_pct,
    global_without_culprit, global_without_culprit_baseline, clears_anomaly,
    ruled_out_segments, ruled_out_dimensions, verdict
FROM rca_orch.v_narration;


-- ============================================================================
-- SECTION 6 · operations
-- ============================================================================

-- Force the chain to run now, in order:
--   SYSTEM REFRESH VIEW rca_orch.anomalies_refresh;
--   SYSTEM REFRESH VIEW rca_orch.incidents_refresh;
--   SYSTEM REFRESH VIEW rca_orch.diagnoses_refresh;
--   SYSTEM REFRESH VIEW rca_orch.uniformity_refresh;

-- Inspect schedule and runtime state:
--   SELECT view, status, last_success_time, next_refresh_time, exception
--   FROM system.view_refreshes
--   WHERE database IN ('rca', 'rca_orch');

-- Pause / resume the whole pipeline:
--   SYSTEM STOP VIEWS;
--   SYSTEM START VIEWS;

-- The current diagnosis for every open incident:
--   SELECT * FROM rca_orch.v_narration ORDER BY window_start;

-- Full audit trail for one incident:
--   SELECT observed_at, stage, record_key, details
--   FROM rca_orch.incident_lifecycle_trace FINAL
--   WHERE incident_id = ?
--   ORDER BY stage_order, observed_at;

-- Replay integrity check — these two must be equal:
--   SELECT
--       (SELECT count() FROM rca.ad_events)       AS loaded,
--       (SELECT count() FROM rca.ad_events_stage) AS source;
