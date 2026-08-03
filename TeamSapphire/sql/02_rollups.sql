-- ============================================================================
-- Rollup design — the measurement that drove it
-- ============================================================================
-- A fully-crossed hourly rollup (hour x all 9 dimensions) was measured first
-- and rejected: it produced 7,247,816 rows from 7.2M source events, i.e. 9,437
-- distinct dimension combinations per hour against ~9,400 events per hour.
-- Almost every event is its own combination, so the rollup compresses nothing
-- and costs a second copy of the data.
--
-- The unpivoted grain is the opposite. Across all 9 dimensions there are only
-- 62 distinct dimension VALUES in total, so (hour, dim_name, dim_value) is
-- 53,760 rows for the same window — 167x smaller than the 9M raw events and
-- 135x smaller than the fully-crossed rollup above — and it is exactly the
-- shape contribution ranking reads.
--
-- The trade: an unpivoted rollup cannot see dimension COMBINATIONS. Compound
-- anomalies (e.g. iOS 18.1 x APAC) are therefore found by querying ad_events
-- directly. That is a deliberate split, not an oversight: pair scanning is
-- rare and bounded, while single-dimension ranking runs on every metric of
-- every investigation and is what had to be cheap.
--
-- Engine: SummingMergeTree, not AggregatingMergeTree. Every measure here is
-- additive (requests / fills / impressions / clicks / revenue) and every ratio
-- in the glossary is defined as sum/sum computed on read. There is no uniq,
-- quantile or avg to preserve, so -State/-Merge would add ceremony and the
-- alias-shadowing failure mode without buying anything.
--
-- NOTE ON RATIOS: never store a ratio. Fill rate, CTR and eCPM are always
-- recomputed as sum/sum over whatever grouping the query asks for. Storing a
-- per-hour ratio and averaging it later is silently wrong once bucket sizes
-- differ, which is precisely the trap the metrics glossary warns about.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- Tier 1: hourly totals, no dimensions. Backs detection (depth 0).
-- ~840 rows for the full 5-week window.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.events_hourly
(
    hour        DateTime CODEC(Delta, ZSTD(1)),
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Float64
)
ENGINE = SummingMergeTree
ORDER BY hour;


-- ---------------------------------------------------------------------------
-- Tier 2: unpivoted per-dimension rollup. Backs contribution ranking
-- (depth 1 and 2). 53,760 rows.
--
-- ORDER BY (dim_name, dim_value, hour): lowest cardinality first, time last.
-- dim_name has 9 values, dim_value 62, hour ~840. Baseline queries filter a
-- specific dimension across scattered non-contiguous hours (same weekday+hour
-- over trailing weeks), so leading with time would not give a contiguous range
-- anyway. At 53,760 rows the whole table is ~7 granules regardless.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inmobi.events_hourly_by_dim
(
    hour        DateTime CODEC(Delta, ZSTD(1)),
    dim_name    LowCardinality(String),
    dim_value   LowCardinality(String),
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Float64
)
ENGINE = SummingMergeTree
ORDER BY (dim_name, dim_value, hour);


-- ---------------------------------------------------------------------------
-- Materialized views. These are INSERT TRIGGERS: they only see rows inserted
-- after creation. Creating them before the backfill means new data (including
-- the unseen incident) rolls up automatically, while historical data is
-- handled by the one-shot backfill in scripts/backfill.py.
-- ---------------------------------------------------------------------------

CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_events_hourly
TO inmobi.events_hourly
AS
SELECT
    toStartOfHour(event_time) AS hour,
    count()                   AS requests,
    sum(is_filled)            AS fills,
    sum(is_impression)        AS impressions,
    sum(is_click)             AS clicks,
    sum(revenue)              AS revenue
FROM inmobi.ad_events
GROUP BY hour;


-- The ARRAY JOIN fans each event out into one row per dimension, which is what
-- makes the unpivoted grain possible.
--
-- advertiser_id is empty on unfilled requests, so vertical and campaign_type
-- genuinely do not exist for those rows. They are emitted as '(unfilled)'
-- rather than '' so that (a) the bucket is explicit rather than an ambiguous
-- empty string, and (b) requests still sum to the true total within every
-- dimension. An unfilled request having no advertiser vertical is a fact about
-- the funnel, not missing data.
CREATE MATERIALIZED VIEW IF NOT EXISTS inmobi.mv_events_hourly_by_dim
TO inmobi.events_hourly_by_dim
AS
SELECT
    toStartOfHour(event_time) AS hour,
    d.1                       AS dim_name,
    d.2                       AS dim_value,
    count()                   AS requests,
    sum(is_filled)            AS fills,
    sum(is_impression)        AS impressions,
    sum(is_click)             AS clicks,
    sum(revenue)              AS revenue
FROM inmobi.ad_events
ARRAY JOIN
[
    ('ad_format',      CAST(ad_format AS String)),
    ('region',         dictGetString('inmobi.dict_geo_device', 'region',         geo_device_id)),
    ('country',        dictGetString('inmobi.dict_geo_device', 'country',        geo_device_id)),
    ('device_model',   dictGetString('inmobi.dict_geo_device', 'device_model',   geo_device_id)),
    ('os_version',     dictGetString('inmobi.dict_geo_device', 'os_version',     geo_device_id)),
    ('category',       dictGetString('inmobi.dict_apps',       'category',       app_id)),
    ('publisher_tier', dictGetString('inmobi.dict_apps',       'publisher_tier', app_id)),
    ('vertical',       if(advertiser_id = '', '(unfilled)', dictGetString('inmobi.dict_advertisers', 'vertical',      advertiser_id))),
    ('campaign_type',  if(advertiser_id = '', '(unfilled)', dictGetString('inmobi.dict_advertisers', 'campaign_type', advertiser_id)))
] AS d
GROUP BY hour, dim_name, dim_value;
