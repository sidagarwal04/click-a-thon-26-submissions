-- ============================================================================
--  RCA PIPELINE — end to end, rca.ad_events → rca_test.v_narration
--  ClickHouse 26.2+ · idempotent · safe to re-run in full
--
--  SECTION 0  tables         one-time, CREATE IF NOT EXISTS
--  SECTION 1  views          CREATE OR REPLACE — re-run after any edit
--  SECTION 2  the run        TRUNCATE + INSERT chain, run after data lands
--  SECTION 3  automation     refreshable MVs, replaces SECTION 2 entirely
--
--  Source data (rca.ad_events) is never written to.
-- ============================================================================


-- ============================================================================
-- SECTION 0 · TABLES
-- ============================================================================

CREATE DATABASE IF NOT EXISTS rca_test;

-- hourly rollup: 1 event → 10 (dim, val) rows. 9M events → ~54,600 rows.
CREATE TABLE IF NOT EXISTS rca_test.seg_hourly
(
    ts          DateTime,
    dim         LowCardinality(String),
    val         LowCardinality(String),
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Float64
) ENGINE = SummingMergeTree ORDER BY (dim, val, ts);

-- every (metric × segment × day) that tripped a threshold
CREATE TABLE IF NOT EXISTS rca_test.anomalies
(
    d        Date,
    metric   LowCardinality(String),
    dim      LowCardinality(String),
    val      LowCardinality(String),
    value    Float64,
    baseline Float64,
    effect   Float64,
    z        Float64,
    n           UInt64,
    is_onset    UInt8,
    detected_at DateTime DEFAULT now()
) ENGINE = MergeTree ORDER BY (d, metric, dim, val);

-- consecutive anomaly days merged into one event
CREATE TABLE IF NOT EXISTS rca_test.incidents
(
    incident_id  String,
    metric       LowCardinality(String),
    dim          LowCardinality(String),
    val          LowCardinality(String),
    i0           Date,
    i1           Date,
    b0           Date,
    days         UInt16,
    worst_effect Float64,
    peak_z       Float64
) ENGINE = MergeTree ORDER BY incident_id;

-- every segment's contribution to every incident
CREATE TABLE IF NOT EXISTS rca_test.diagnoses
(
    incident_id   String,
    dim           LowCardinality(String),
    val           LowCardinality(String),
    share         Float64,
    rate_incident Float64,
    rate_baseline Float64,
    seg_delta     Float64,
    contribution  Float64,
    explains      Float64,
    n             UInt64
) ENGINE = MergeTree ORDER BY (incident_id, dim, val);

-- is the culprit's drop uniform across other dimensions, or an intersection?
CREATE TABLE IF NOT EXISTS rca_test.uniformity
(
    incident_id String,
    metric      LowCardinality(String),
    culprit_dim LowCardinality(String),
    culprit_val LowCardinality(String),
    other_dim   LowCardinality(String),
    spread      Float64,
    worst       Float64,
    best        Float64
) ENGINE = MergeTree ORDER BY (incident_id, other_dim);

-- days excluded from baselines because a prior incident poisoned them
CREATE TABLE IF NOT EXISTS rca_test.excluded_days
(
    d      Date,
    reason String
) ENGINE = MergeTree ORDER BY d;


-- ============================================================================
-- SECTION 1 · VIEWS
-- ============================================================================

-- ---- 1.1 unpivot dimensions -------------------------------------------------
-- Native types (no casts) so this view and mv_seg_hourly emit identical shapes.
CREATE OR REPLACE VIEW rca_test.v_seg_hourly AS
SELECT
    toStartOfHour(event_time) AS ts,
    kv.1 AS dim,
    kv.2 AS val,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM rca.ad_events
ARRAY JOIN [
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

-- keeps seg_hourly current on every insert into rca.ad_events
CREATE MATERIALIZED VIEW IF NOT EXISTS rca_test.mv_seg_hourly
TO rca_test.seg_hourly AS
SELECT
    toStartOfHour(event_time) AS ts,
    kv.1 AS dim,
    kv.2 AS val,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM rca.ad_events
ARRAY JOIN [
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


-- ---- 1.2 unpivot metrics ----------------------------------------------------
-- den = 1 marks a volume metric. The WHERE is the single chokepoint guarding
-- demand-side dimensions: they exist only on filled events.
CREATE OR REPLACE VIEW rca_test.v_metric AS
SELECT ts, dim, val, m.1 AS metric, m.2 AS num, m.3 AS den, m.4 AS is_ratio
FROM rca_test.seg_hourly
ARRAY JOIN [
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


-- ---- 1.3 detect -------------------------------------------------------------
-- n means TRAFFIC in both cases: sum(den) for ratios, sum(num) for volume.
-- Getting this wrong makes every volume metric invisible.
CREATE OR REPLACE VIEW rca_test.v_detect AS
WITH daily AS (
    SELECT metric, dim, val, is_ratio, toDate(ts) AS d,
           sum(num) AS num_s,
           sum(den) AS den_s,
           sum(num) / sum(den) AS value,
           toUInt64(if(is_ratio = 1, sum(den), sum(num))) AS n
    FROM rca_test.v_metric
    GROUP BY metric, dim, val, d, is_ratio
),
dowf AS (
    SELECT metric, dim, val, dw,
           dv / avg(dv) OVER (PARTITION BY metric, dim, val) AS factor
    FROM (
        SELECT metric, dim, val, toDayOfWeek(d) AS dw, avg(value) AS dv
        FROM daily
        WHERE is_ratio = 0
          AND d NOT IN (SELECT d FROM rca_test.excluded_days)
        GROUP BY metric, dim, val, dw
    )
),
adj AS (
    SELECT daily.*,
           if(is_ratio = 1, value, value / nullIf(dowf.factor, 0)) AS v_adj
    FROM daily
    LEFT JOIN dowf
           ON dowf.metric = daily.metric
          AND dowf.dim    = daily.dim
          AND dowf.val    = daily.val
          AND dowf.dw     = toDayOfWeek(daily.d)
)
SELECT metric, dim, val, d, value, n, is_ratio,
       count() OVER w                        AS hist,   -- days of history behind the baseline
       sum(num_s) OVER w / sum(den_s) OVER w AS baseline,
       avg(v_adj)       OVER w               AS b_adj,
       stddevPop(v_adj) OVER w               AS sd_adj,
       (v_adj - b_adj) / nullIf(sd_adj, 0)   AS z,
       (v_adj / nullIf(b_adj, 0)) - 1        AS effect
FROM adj
WINDOW w AS (PARTITION BY metric, dim, val ORDER BY d ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING);


-- ---- 1.4 which factor of the revenue identity ------------------------------
-- b_rev is DERIVED from the four factor baselines, so residual = 0 by construction.
-- b_r is a level (avg); the rest are ratios (sum/sum).
CREATE OR REPLACE VIEW rca_test.v_factor AS
SELECT d,
       rev / b_rev - 1                AS rev_change,
       log(r / b_r)                   AS l_requests,
       log((f / r) / b_fill)          AS l_fill_rate,
       log((i / f) / b_render)        AS l_render_rate,
       log((rev / i * 1000) / b_ecpm) AS l_ecpm,
       log(rev / b_rev) - log(r / b_r) - log((f / r) / b_fill)
         - log((i / f) / b_render) - log((rev / i * 1000) / b_ecpm) AS residual
FROM (
    SELECT d, r, f, i, rev,
           avg(r) OVER w                           AS b_r,
           sum(f) OVER w / sum(r) OVER w           AS b_fill,
           sum(i) OVER w / sum(f) OVER w           AS b_render,
           sum(rev) OVER w / sum(i) OVER w * 1000  AS b_ecpm,
           b_r * b_fill * b_render * b_ecpm / 1000 AS b_rev
    FROM (
        SELECT toDate(ts) AS d, sum(requests) AS r, sum(fills) AS f,
               sum(impressions) AS i, sum(revenue) AS rev
        FROM rca_test.seg_hourly WHERE dim = '__all__' GROUP BY d
    )
    WINDOW w AS (PARTITION BY toDayOfWeek(d) ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
);


-- ---- 1.5 attribute ----------------------------------------------------------
-- No parameters: windows come from the incidents table. contribution = share × delta.
-- VOLUME METRICS: den = 1, so di counts HOURS, identical for every segment
-- including __all__. Using di/g_di would make every segment 100% of traffic.
-- For volume, a segment's size is its COUNT (ni/g_ni).
CREATE OR REPLACE VIEW rca_test.v_attribute AS
SELECT incident_id, dim, val,
       if(is_ratio = 1, di / g_di, ni / g_ni)     AS share,
       ni / di                                    AS rate_incident,
       nb / db                                    AS rate_baseline,
       ni / di - nb / db                          AS seg_delta,
       share * (ni / di - nb / db)                AS contribution,
       contribution / (g_ni / g_di - g_nb / g_db) AS explains,
       toUInt64(if(is_ratio = 1, di, ni))         AS n
FROM (
    SELECT incident_id, dim, val, is_ratio, ni, di, nb, db,
           sumIf(ni, dim = '__all__') OVER (PARTITION BY incident_id) AS g_ni,
           sumIf(di, dim = '__all__') OVER (PARTITION BY incident_id) AS g_di,
           sumIf(nb, dim = '__all__') OVER (PARTITION BY incident_id) AS g_nb,
           sumIf(db, dim = '__all__') OVER (PARTITION BY incident_id) AS g_db
    FROM (
        SELECT inc.incident_id AS incident_id, m.dim AS dim, m.val AS val,
               any(m.is_ratio) AS is_ratio,
               sumIf(m.num, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS ni,
               sumIf(m.den, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS di,
               sumIf(m.num, toDate(m.ts) <  inc.i0)                 AS nb,
               sumIf(m.den, toDate(m.ts) <  inc.i0)                 AS db
        FROM rca_test.incidents AS inc
        INNER JOIN rca_test.v_metric AS m ON m.metric = inc.metric
        WHERE toDate(m.ts) BETWEEN inc.b0 AND inc.i1
        GROUP BY incident_id, dim, val
    )
)
WHERE dim != '__all__';


-- ---- 1.6 rule out -----------------------------------------------------------
-- Counters are additive, so "global without X" is subtraction — no re-scan.
-- If NO row clears, the incident is diffuse and probably shouldn't have opened.
-- VOLUME METRICS again: removing a segment removes its EVENTS, not the hours.
-- (g_di - di) would be 0 and every exclusion would come back NULL.
CREATE OR REPLACE VIEW rca_test.v_ruleout AS
SELECT incident_id, dim, val,
       (g_ni - ni) / if(is_ratio = 1, g_di - di, g_di) AS excl_incident,
       (g_nb - nb) / if(is_ratio = 1, g_db - db, g_db) AS excl_baseline,
       abs(excl_incident / excl_baseline - 1) < 0.005  AS clears_anomaly,
       abs(excl_incident / excl_baseline - 1)          AS residual_effect
FROM (
    SELECT incident_id, dim, val, is_ratio, ni, di, nb, db,
           sumIf(ni, dim = '__all__') OVER (PARTITION BY incident_id) AS g_ni,
           sumIf(di, dim = '__all__') OVER (PARTITION BY incident_id) AS g_di,
           sumIf(nb, dim = '__all__') OVER (PARTITION BY incident_id) AS g_nb,
           sumIf(db, dim = '__all__') OVER (PARTITION BY incident_id) AS g_db
    FROM (
        SELECT inc.incident_id AS incident_id, m.dim AS dim, m.val AS val,
               any(m.is_ratio) AS is_ratio,
               sumIf(m.num, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS ni,
               sumIf(m.den, toDate(m.ts) BETWEEN inc.i0 AND inc.i1) AS di,
               sumIf(m.num, toDate(m.ts) <  inc.i0)                 AS nb,
               sumIf(m.den, toDate(m.ts) <  inc.i0)                 AS db
        FROM rca_test.incidents AS inc
        INNER JOIN rca_test.v_metric AS m ON m.metric = inc.metric
        WHERE toDate(m.ts) BETWEEN inc.b0 AND inc.i1
        GROUP BY incident_id, dim, val
    )
)
WHERE dim != '__all__';


-- ---- 1.7 narration payload --------------------------------------------------
-- One row per incident. The LLM reads this and nothing else.
-- v_ruleout is joined INSIDE the culprit subquery: mixing USING and ON in the
-- outer query makes incident_id ambiguous.
CREATE OR REPLACE VIEW rca_test.v_narration AS
SELECT
    i.incident_id                  AS incident_id,
    i.metric                       AS metric,
    i.i0                           AS window_start,
    i.i1                           AS window_end,
    i.days                         AS days,
    round(100 * i.worst_effect, 2) AS metric_change_pct,
    round(i.peak_z, 1)             AS peak_z,

    c.dim                          AS culprit_dim,
    c.val                          AS culprit_val,
    round(c.rate_baseline, 4)      AS culprit_baseline,
    round(c.rate_incident, 4)      AS culprit_value,
    round(100 * (c.rate_incident / nullIf(c.rate_baseline, 0) - 1), 2) AS culprit_change_pct,
    round(100 * c.share, 1)        AS culprit_share_pct,
    round(100 * c.explains, 1)     AS explains_pct,

    round(c.excl_incident, 4)      AS global_without_culprit,
    round(c.excl_baseline, 4)      AS global_without_culprit_baseline,
    c.clears_anomaly               AS clears_anomaly,

    r.ruled_out                    AS ruled_out_segments,
    u.uniform_dims                 AS ruled_out_dimensions,

    round(m.revenue_actual, 1)     AS revenue_actual,
    round(m.revenue_expected, 1)   AS revenue_expected,
    round(m.revenue_shortfall, 1)  AS revenue_shortfall,

    multiIf(c.explains IS NULL,                         'no_attribution',
            c.clears_anomaly = 0,                       'ambiguous_no_slice_clears',
            u.max_spread > 0.05,                        'intersection_descend',
            c.explains >= 0.9 AND c.clears_anomaly = 1, 'confirmed',
                                                        'weak') AS verdict
FROM rca_test.incidents AS i

LEFT JOIN (
    SELECT d.incident_id AS incident_id, d.dim AS dim, d.val AS val,
           d.rate_baseline AS rate_baseline, d.rate_incident AS rate_incident,
           d.share AS share, d.explains AS explains,
           ro.excl_incident AS excl_incident, ro.excl_baseline AS excl_baseline,
           ro.clears_anomaly AS clears_anomaly
    FROM (
        SELECT * FROM (
            SELECT *, row_number() OVER (PARTITION BY incident_id
                                         ORDER BY abs(contribution) DESC) AS rk
            FROM rca_test.diagnoses
        ) WHERE rk = 1
    ) AS d
    INNER JOIN rca_test.v_ruleout AS ro
            ON ro.incident_id = d.incident_id AND ro.dim = d.dim AND ro.val = d.val
) AS c USING (incident_id)

LEFT JOIN (
    SELECT incident_id,
           groupArray((concat(dim, '=', val), round(100 * explains, 1))) AS ruled_out
    FROM (
        SELECT *, row_number() OVER (PARTITION BY incident_id
                                     ORDER BY abs(contribution) DESC) AS rk
        FROM rca_test.diagnoses
    ) WHERE rk BETWEEN 2 AND 6
    GROUP BY incident_id
) AS r USING (incident_id)

LEFT JOIN (
    SELECT incident_id,
           groupArray((other_dim, round(spread, 4))) AS uniform_dims,
           max(spread)                               AS max_spread
    FROM rca_test.uniformity
    GROUP BY incident_id
) AS u USING (incident_id)

LEFT JOIN (
    SELECT x.incident_id AS incident_id,
           sum(x.r)                                    AS revenue_actual,
           sum(x.r) / (1 + any(x.eff))                 AS revenue_expected,
           sum(x.r) / (1 + any(x.eff)) - sum(x.r)      AS revenue_shortfall
    FROM (
        SELECT inc.incident_id AS incident_id, inc.worst_effect AS eff, g.r AS r
        FROM rca_test.incidents AS inc
        INNER JOIN (SELECT toDate(ts) AS d, sum(revenue) AS r
                    FROM rca_test.seg_hourly WHERE dim = '__all__' GROUP BY d) AS g
                ON g.d >= inc.i0
        WHERE g.d <= inc.i1
    ) AS x
    GROUP BY x.incident_id
) AS m USING (incident_id);


-- ============================================================================
-- SECTION 2 · THE RUN — this is where data actually moves.
--                       Execute top to bottom, after data lands in ad_events.
-- ============================================================================
-- Every stage is TRUNCATE + INSERT, so the whole section is idempotent: run it
-- as many times as you like and the result is identical.
--
-- Total runtime ~10s, of which 2.4 is ~9s. Everything else is milliseconds.

-- ---- 2.0 rebuild the rollup -------------------------------------------------
-- mv_seg_hourly only sees rows inserted AFTER it existed, so it can never
-- populate history on its own — and it does not fire at all for ATTACH PARTITION
-- or part-level loads. This rebuild is the source of truth; the MV just keeps
-- things fresh between runs.
--
-- TRUNCATE is not optional. seg_hourly is a SummingMergeTree: inserting the same
-- rows twice ADDS the counters rather than replacing them, silently doubling
-- every number downstream.
TRUNCATE TABLE rca_test.seg_hourly;

INSERT INTO rca_test.seg_hourly (ts, dim, val, requests, fills, impressions, clicks, revenue)
SELECT ts, dim, val, requests, fills, impressions, clicks, revenue
FROM rca_test.v_seg_hourly;

-- sanity check — should equal count(*) from rca.ad_events
-- SELECT sum(requests) FROM rca_test.seg_hourly WHERE dim = '__all__';

-- ---- 2.1 detect -------------------------------------------------------------
TRUNCATE TABLE rca_test.anomalies;

-- Explicit column list: the table also has detected_at (DEFAULT now()), and a
-- positional INSERT would fail on the count mismatch.
INSERT INTO rca_test.anomalies (d, metric, dim, val, value, baseline, effect, z, n, is_onset)
SELECT d, metric, dim, val, value, baseline, effect, z, n,
       abs(z) >= 4 AND abs(effect) >= 0.02 AS is_onset   -- strict = opens an incident
FROM rca_test.v_detect
WHERE n >= 20000
  AND abs(z) >= 2 AND abs(effect) >= 0.01                -- loose = extends one
  AND z IS NOT NULL
  AND hist >= 14;   -- cold-start guard. Without it, day 7 scores z=65.9 off six
                    -- samples and the first fortnight fires on nothing.

-- ---- 2.2 merge consecutive days into incidents -----------------------------
-- Gap-and-islands: date minus row_number is constant across a run of days.
TRUNCATE TABLE rca_test.incidents;

INSERT INTO rca_test.incidents
    (incident_id, metric, dim, val, i0, i1, b0, days, worst_effect, peak_z)
SELECT concat(metric, '|', dim, '=', val, '@', toString(min(d))) AS incident_id,
       metric, dim, val,
       min(d)     AS i0,
       max(d)     AS i1,
       min(d) - 7 AS b0,
       count()    AS days,
       argMax(effect, abs(effect)) AS worst_effect,
       argMax(z, abs(z))           AS peak_z
FROM (
    SELECT *, d - toIntervalDay(row_number() OVER (PARTITION BY metric, dim, val ORDER BY d)) AS grp
    FROM rca_test.anomalies
    WHERE dim = '__all__'        -- NOTE: global moves only. Segment-only incidents
)                                -- cannot open — see the caveat at the foot of this file.
GROUP BY metric, dim, val, grp
HAVING max(is_onset) = 1;        -- at least one day cleared the strict gate

-- ---- 2.3 attribute ----------------------------------------------------------
TRUNCATE TABLE rca_test.diagnoses;

INSERT INTO rca_test.diagnoses SELECT * FROM rca_test.v_attribute;

-- ---- 2.4 uniformity — the only step that touches raw ad_events (~10s) -------
TRUNCATE TABLE rca_test.uniformity;

INSERT INTO rca_test.uniformity
    (incident_id, metric, culprit_dim, culprit_val, other_dim, spread, worst, best)
WITH culprit AS (
    SELECT incident_id, dim AS cdim, val AS cval FROM (
        SELECT incident_id, dim, val,
               row_number() OVER (PARTITION BY incident_id ORDER BY abs(contribution) DESC) AS rk
        FROM rca_test.diagnoses
    ) WHERE rk = 1
)
SELECT incident_id, metric, culprit_dim, culprit_val, other_dim,
       stddevPop(rel) AS spread, min(rel) AS worst, max(rel) AS best
FROM (
    SELECT incident_id, metric, culprit_dim, culprit_val,
           kv.1 AS other_dim, kv.2 AS other_val,
           -- RELATIVE change: absolute delta would read eCPM's scale differences
           -- (video 6.5 vs banner 0.87) as non-uniformity.
           (sumIf(num, w = 'i') / sumIf(den, w = 'i'))
             / nullIf(sumIf(num, w = 'b') / sumIf(den, w = 'b'), 0) - 1 AS rel,
           sumIf(den, w = 'i') AS n
    FROM (
        SELECT c.incident_id AS incident_id, i.metric AS metric,
               c.cdim AS culprit_dim, c.cval AS culprit_val,
               if(toDate(e.event_time) BETWEEN i.i0 AND i.i1, 'i', 'b') AS w,
               multiIf(i.metric = 'fill_rate',   toFloat64(e.is_filled),
                       i.metric = 'render_rate', toFloat64(e.is_impression),
                       i.metric = 'ctr',         toFloat64(e.is_click),
                       i.metric = 'ecpm',        e.revenue * 1000,
                       i.metric = 'rpr',         e.revenue, 0.) AS num,
               multiIf(i.metric = 'render_rate',    toFloat64(e.is_filled),
                       i.metric IN ('ctr', 'ecpm'), toFloat64(e.is_impression), 1.) AS den,
               map('region', e.region, 'country', e.country, 'device_model', e.device_model,
                   'os_version', e.os_version, 'ad_format', e.ad_format,
                   'category', e.category, 'publisher_tier', e.publisher_tier) AS dims
        FROM rca.ad_events AS e
        CROSS JOIN culprit AS c
        INNER JOIN rca_test.incidents AS i ON i.incident_id = c.incident_id
        WHERE toDate(e.event_time) BETWEEN i.b0 AND i.i1
          AND i.metric IN ('fill_rate', 'render_rate', 'ctr', 'ecpm', 'rpr')
          AND dims[c.cdim] = c.cval
    )
    ARRAY JOIN arrayFilter(x -> x.1 != culprit_dim, CAST(dims, 'Array(Tuple(String,String))')) AS kv
    GROUP BY incident_id, metric, culprit_dim, culprit_val, other_dim, other_val
    HAVING n > 1000
)
GROUP BY incident_id, metric, culprit_dim, culprit_val, other_dim;

-- ---- 2.5 verify the run -----------------------------------------------------
-- Every stage must be non-zero. A zero anywhere means the stage below it is
-- describing nothing, and v_narration will be silently empty.
-- The union MUST be wrapped: in ClickHouse a trailing ORDER BY binds to the last
-- SELECT of a UNION ALL, not to the combined result.
SELECT stage, rows, expect FROM (
    SELECT 0 AS ord, 'seg_hourly' AS stage, count() AS rows, '~54,600 for 5 weeks' AS expect
      FROM rca_test.seg_hourly
    UNION ALL SELECT 1, 'anomalies',  count(), 'hundreds'         FROM rca_test.anomalies
    UNION ALL SELECT 2, 'incidents',  count(), 'a handful'        FROM rca_test.incidents
    UNION ALL SELECT 3, 'diagnoses',  count(), 'incidents x 64'   FROM rca_test.diagnoses
    UNION ALL SELECT 4, 'uniformity', count(), 'incidents x ~6'   FROM rca_test.uniformity
    UNION ALL SELECT 5, 'narration',  count(), 'one per incident' FROM rca_test.v_narration
) ORDER BY ord;

-- reconciliation: this must equal count(*) from rca.ad_events
SELECT sum(requests) AS rollup_requests FROM rca_test.seg_hourly WHERE dim = '__all__';

-- ---- 2.6 read the answer ----------------------------------------------------
SELECT * FROM rca_test.v_narration ORDER BY window_start;


-- ============================================================================
-- SECTION 3 · AUTOMATION — refreshable MVs replace SECTION 2 entirely
-- ============================================================================
-- DEPENDS ON chains them into a DAG: each refreshes only after its parent
-- completes. Every refresh REPLACES the target table, so the pipeline is
-- idempotent by construction — no TRUNCATE needed.
--
-- seg_hourly stays on the incremental MV — rescanning 9M rows every 15 minutes
-- would be wasteful. So you must still run SECTION 2.0 ONCE to load history
-- before enabling this; the refreshable chain starts at anomalies.
--
-- Drop the SECTION 2.1–2.4 statements if you enable this; running both double-works.
-- Every refresh period must match across the chain.
/*
SET allow_experimental_refreshable_materialized_view = 1;

CREATE MATERIALIZED VIEW rca_test.rmv_anomalies
REFRESH EVERY 15 MINUTE
TO rca_test.anomalies AS
SELECT d, metric, dim, val, value, baseline, effect, z, n,
       abs(z) >= 4 AND abs(effect) >= 0.02 AS is_onset
FROM rca_test.v_detect
WHERE n >= 20000 AND abs(z) >= 2 AND abs(effect) >= 0.01 AND z IS NOT NULL;

CREATE MATERIALIZED VIEW rca_test.rmv_incidents
REFRESH EVERY 15 MINUTE DEPENDS ON rca_test.rmv_anomalies
TO rca_test.incidents AS
SELECT concat(metric, '|', dim, '=', val, '@', toString(min(d))),
       metric, dim, val, min(d), max(d), min(d) - 7, count(),
       argMax(effect, abs(effect)), argMax(z, abs(z))
FROM (
    SELECT *, d - toIntervalDay(row_number() OVER (PARTITION BY metric, dim, val ORDER BY d)) AS grp
    FROM rca_test.anomalies WHERE dim = '__all__'
)
GROUP BY metric, dim, val, grp
HAVING max(is_onset) = 1;

CREATE MATERIALIZED VIEW rca_test.rmv_diagnoses
REFRESH EVERY 15 MINUTE DEPENDS ON rca_test.rmv_incidents
TO rca_test.diagnoses AS
SELECT * FROM rca_test.v_attribute;

CREATE MATERIALIZED VIEW rca_test.rmv_uniformity
REFRESH EVERY 15 MINUTE DEPENDS ON rca_test.rmv_diagnoses
TO rca_test.uniformity AS
<paste the SELECT body from section 2.4>;

-- inspect / force
SELECT view, status, last_success_time, last_refresh_result, exception
FROM system.view_refreshes WHERE database = 'rca_test';

SYSTEM REFRESH VIEW rca_test.rmv_anomalies;   -- run one now
SYSTEM STOP VIEW rca_test.rmv_anomalies;      -- pause
*/


-- ============================================================================
-- KNOWN GAPS — these change what the pipeline can report
-- ============================================================================
-- 1. Section 2.2 filters dim = '__all__', so an incident confined to one segment
--    cannot open. Dropping the filter alone is wrong: every pass-through segment
--    would open its own incident (~40 for one root cause). It needs a rule like
--    "open a segment incident only if no global incident overlaps its window".
--
-- 2. No factor-over-composite suppression: rpr fires alongside the ecpm incident
--    that causes it, double-counting the same revenue loss.
--
-- 3. Thresholds (z >= 4, effect >= 0.02, n >= 20000) are global. Quiet-day p95 of
--    |effect| varies 60x by metric — 0.17% for render_rate, 11% for requests — so
--    one gate is far too tight for volume and far too loose for render rate.
--    Per-metric gates are the highest-value tuning change.
--
-- 4. The first 14 days of any new dataset are unscoreable (hist >= 14 guard).
--    A fresh 5-week slice yields 3 usable weeks. Load history alongside it, or
--    lower the window and accept a noisier baseline.
--
-- 5. excluded_days must be populated by hand after a confirmed platform-wide
--    event, or its crash poisons the day-of-week factor for the next two weeks:
--       INSERT INTO rca_test.excluded_days VALUES ('2026-06-21', 'traffic loss');
-- ============================================================================
