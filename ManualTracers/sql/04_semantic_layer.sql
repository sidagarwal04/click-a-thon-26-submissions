-- =====================================================================
-- 04 · SEMANTIC LAYER — the definition store
-- =====================================================================
-- Two tables. Together they are the whole RCA tree, and the only thing
-- that has to change to point this system at a different schema.
--
--   metric_def      what a metric IS and how it decomposes
--   metric_dim_map  which cut to try first, and what to cross it with
--
-- There are NO metric views and no pre-aggregated rollup. The formula in
-- metric_def.sql is executed directly against ad_events_enriched, both by
-- the HyperDX alert query (05) and by the RCA agent. One definition, one
-- executable copy, nothing to keep in sync — a metric is added by
-- inserting a row here, and nothing else in the system changes.
--
-- Formulas are taken verbatim from InMobi/metrics_glossary.md.

-- ---------------------------------------------------------------------
-- 4.1 metric_def: what each metric is, how it decomposes, how to test it
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.metric_def
(
    metric_id       String,
    sql             String,  -- the metric, as an aggregate over ad_events_enriched
    numerator       String,  -- the same formula split, for the proportion test
    denominator     String,  -- '' for additive metrics
    is_ratio        UInt8,
    detector        String,  -- proportion | robust_z
    -- Does this metric get a HyperDX tile? A measured decision, not a structural one:
    -- ctr's noisiest clean day (z~3.3) scores HIGHER than its worst real incident (z~2.5),
    -- so any threshold either fires on noise or catches nothing; render_rate never moves
    -- materially and is a free "ruled out" control rather than a detector. See
    -- docs/RCA_AGENT_DESIGN.md §2.2 for the separation table this comes from.
    -- Deriving alertability from structure instead (has dimensions / has dependencies) puts
    -- both back on tiles and they immediately cry wolf, which is the top scored criterion.
    alertable       UInt8,
    dependencies    Array(String), -- funnel factors this decomposes into, IN FUNNEL ORDER
    z_score_threshold Float64,     -- |z| this metric must clear to be an anomaly
    min_samples     UInt64,  -- minimum requests in the bucket to evaluate at all
    min_effect_rel  Float64, -- minimum relative move worth alerting on
    min_effect_abs  Float64, -- minimum absolute move (pp for rates)
    invalid_dims    Array(String), -- dimensions this metric is meaningless across
    updated_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY metric_id;

-- `sql` is what actually runs. It is written to be safe on an empty bucket:
-- every ratio divides by nullIf(..., 0), so a dead hour yields NULL rather
-- than inf, and the baseline window skips it instead of being poisoned.
--
-- `numerator` / `denominator` exist because proportionsZTest needs the raw
-- counts, not the rate — they are the same formula, split. For a ratio metric
-- `sql` and `numerator/denominator` agree by construction.
--
-- `dependencies` is the funnel decomposition, in funnel order:
-- Request -> Fill -> Impression, with revenue realised on impressions.
-- Non-empty means "decompose before slicing any dimension". The agent reads
-- the factor list from here, so the identity is part of the definition and
-- travels with it — there is no identity hardcoded in Python.
--
-- `z_score_threshold` is per-metric. ClickStack alerts have no SQL condition
-- field, so 05 renders it into each alert query's own is_anomaly expression
-- rather than evaluating it at alert time. Registry-driven either way.
--
-- min_samples is a guard against degenerate tiny slices ONLY. It must NOT be
-- used to buy statistical confidence — proportionsZTest already does that
-- correctly at small n. Calibrated against this stream's actual rate of
-- ~10.7K requests/hour globally: a 10%-of-traffic segment such as
-- os_version='Android 15' runs ~1,025 requests/hour, so a 5,000 threshold
-- would silently hide the single largest planted incident in the dataset.
-- Rule of thumb: min_samples ~= 5% of the global hourly request rate.
INSERT INTO inmobi.metric_def
(metric_id, sql, numerator, denominator, is_ratio, detector, alertable, dependencies,
 z_score_threshold, min_samples, min_effect_rel, min_effect_abs, invalid_dims) VALUES
-- the outcome. The only metric with dependencies, so the only one that decomposes.
('revenue', 'sum(revenue)',
 'sum(revenue)', '', 0, 'robust_z', 1,
 ['requests','fill_rate','render_rate','ecpm'], 4.0, 2000, 0.03, 0.0, []),
-- the identity factors: Revenue = Requests x FillRate x RenderRate x eCPM/1000
('requests', 'toFloat64(count())',
 'toFloat64(count())', '', 0, 'robust_z', 1,
 [], 4.0, 2000, 0.05, 0.0, ['vertical','campaign_type']),
('fill_rate', 'sum(is_filled) / nullIf(toFloat64(count()), 0)',
 'sum(is_filled)', 'toFloat64(count())', 1, 'proportion', 1,
 [], 4.0, 500, 0.02, 0.01, ['vertical','campaign_type']),
-- alertable = 0: separation ~1x. render_rate never moves materially, so it earns its keep
-- as a factor that gets *cleared* during decomposition, not as a detector.
('render_rate', 'sum(is_impression) / nullIf(toFloat64(sum(is_filled)), 0)',
 'sum(is_impression)', 'toFloat64(sum(is_filled))', 1, 'proportion', 0,
 [], 4.0, 500, 0.02, 0.01, ['vertical','campaign_type']),
('ecpm', 'sum(revenue) / nullIf(toFloat64(sum(is_impression)), 0) * 1000',
 'sum(revenue)', 'toFloat64(sum(is_impression))', 1, 'robust_z', 1,
 [], 4.0, 500, 0.03, 0.0, []),
-- context, not a revenue factor in a CPM model.
-- alertable = 0: separation < 1x — ctr's noisiest clean day outscores its worst real
-- incident, so a tile on it fires on noise by construction. Measured, see
-- docs/RCA_AGENT_DESIGN.md 2.2; confirmed again on the compressed replay, where a ctr
-- marginal tile flagged device_model='Galaxy S23' at a contribution of 9.
('ctr', 'sum(is_click) / nullIf(toFloat64(sum(is_impression)), 0)',
 'sum(is_click)', 'toFloat64(sum(is_impression))', 1, 'proportion', 0,
 [], 4.0, 500, 0.05, 0.002, []),
('rpr', 'sum(revenue) / nullIf(toFloat64(count()), 0)',
 'sum(revenue)', 'toFloat64(count())', 1, 'robust_z', 0,
 [], 4.0, 2000, 0.03, 0.0, ['vertical','campaign_type']);

-- ---------------------------------------------------------------------
-- 4.2 metric_dim_map: for a given metric, which cut to try first, and
-- which cuts to check after that one. Encodes domain reasoning — a fill
-- failure is supply-side, so OS and country lead; a price move is
-- demand-side, so tier and vertical lead.
--
-- This table is also the dimension whitelist: a dim_id has to appear here
-- before the agent will splice it into SQL as a column reference.
--
-- The alerting cardinality budget lives here by omission. Only dimensions
-- with <= ~50 distinct values are listed. app_id (2,000), geo_device_id
-- (5,000) and advertiser_id (500) are deliberately absent: the full
-- cross-product is 767,984 combinations on 9M rows, and scanning it is what
-- this design refuses to do. They remain reachable in ad_events_enriched
-- for a manual drill, but the agent never enumerates them.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.metric_dim_map
(
    metric_id    String,
    dim_id       String,  -- a column on ad_events_enriched
    priority     UInt8,   -- depth-1 drill order for this metric
    dependencies Array(String), -- cross with these, in order, once this cut leads
    rationale    String,
    updated_at   DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (metric_id, dim_id);

-- priority gives the depth-1 drill order; dependencies turns the same table
-- into a tree. Once a cut leads, the agent walks its dependencies in order and
-- asks whether the parent's move is uniform across that dimension or carried by
-- one stratum — the latter means the real culprit is the pair, not the parent.
-- Entries are the dimensions physically entangled with the parent (a device runs
-- an OS build; a vertical buys a campaign type), which is exactly where
-- bleed-through lives.
--
-- revenue has no rows: it decomposes through metric_def.dependencies and is
-- never sliced directly. The agent slices whichever factor is implicated.
INSERT INTO inmobi.metric_dim_map (metric_id, dim_id, priority, rationale, dependencies) VALUES
('fill_rate','os_version',1,'SDK/adapter faults track OS builds first',['device_model','country']),
('fill_rate','country',2,'demand availability is bid per market',['os_version','ad_format']),
('fill_rate','ad_format',3,'format-specific inventory can go unsold',['publisher_tier','country']),
('fill_rate','publisher_tier',4,'tier drives which demand is eligible',['category','country']),
('fill_rate','category',5,'category affects baseline fill materially',['publisher_tier','ad_format']),
('fill_rate','device_model',6,'narrower proxy for the OS signal',['os_version']),
('fill_rate','region',7,'usually dilutes a country-level fault',['country','os_version']),
('ecpm','publisher_tier',1,'price is tiered by publisher quality',['vertical','category']),
('ecpm','vertical',2,'advertiser vertical sets willingness to pay',['campaign_type','publisher_tier']),
('ecpm','campaign_type',3,'CPM vs CPC vs CPI price differently',['vertical','ad_format']),
('ecpm','country',4,'market-level price floors',['publisher_tier','ad_format']),
('ecpm','ad_format',5,'format carries a strong price prior',['vertical','publisher_tier']),
('ecpm','category',6,'secondary to tier',['publisher_tier','vertical']),
('ecpm','region',7,'aggregate of country',['country','publisher_tier']),
('ecpm','os_version',8,'rarely a pricing driver',['device_model']),
('requests','region',1,'traffic incidents are usually infra/geo shaped',['country','category']),
('requests','country',2,'narrows a regional traffic move',['category','ad_format']),
('requests','category',3,'app-mix driven volume shifts',['publisher_tier','ad_format']),
('requests','ad_format',4,'format demand changes',['category','publisher_tier']),
('requests','publisher_tier',5,'a large publisher leaving moves volume',['category','region']),
('requests','os_version',6,'client rollout can change request rate',['device_model','region']),
('requests','device_model',7,'narrow proxy for OS',['os_version']),
('render_rate','os_version',1,'render failures are client-side',['device_model','ad_format']),
('render_rate','device_model',2,'hardware/webview specific',['os_version','ad_format']),
('render_rate','ad_format',3,'video and interstitial fail differently',['os_version','country']),
('render_rate','country',4,'network conditions',['os_version','ad_format']),
('ctr','ad_format',1,'creative format dominates CTR',['category','os_version']),
('ctr','os_version',2,'client rendering affects tappability',['device_model','ad_format']),
('ctr','device_model',3,'screen size effects',['os_version']),
('ctr','category',4,'audience intent varies by app type',['ad_format','publisher_tier']),
('ctr','country',5,'market-level engagement differences',['category','ad_format']);

-- ---------------------------------------------------------------------
-- 4.3 replay_clock: how fast wall-clock time is running.
--
-- One row. bucket_seconds = wall-clock seconds per data-hour. 3600 is real
-- time and is the default; scripts/compress_replay.py rewrites this row when
-- it loads a time-compressed replay, so 35 days of history can stream past a
-- live HyperDX alert in minutes.
--
-- It lives in ClickHouse rather than in an env var because BOTH renderers
-- (the agent and scripts/metric_query.py) must agree on it. If they disagree,
-- the alert and the investigation bucket the same rows differently and the
-- agent reports not_reproducible on an alert that just fired.
--
-- anchor     = unix seconds of data-bucket 0
-- origin_dow = weekday of the first data day, 0 = Monday. Needed because a
--              compressed calendar cannot be read off the timestamp: the
--              baseline derives day-of-week from the bucket index instead.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.replay_clock
(
    id             UInt8 DEFAULT 1,
    bucket_seconds UInt32,
    anchor         Int64,
    origin_dow     UInt8,
    updated_at     DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id;

INSERT INTO inmobi.replay_clock (bucket_seconds, anchor, origin_dow) VALUES (3600, 0, 0);
