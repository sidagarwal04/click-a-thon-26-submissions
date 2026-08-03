-- Monitoring rollups: the slices the original 12 hourly_by_* rollups cannot
-- answer. Run AFTER schema.sql / dictionaries.sql / rollups.sql. Applied by
-- scripts/apply_monitoring.py (the MCP ClickHouse connection is read-only, so
-- DDL/DML goes through a direct clickhouse-connect client).
--
-- Only two kinds of table are added here, and each earns its place:
--
-- 1. SUB-HOUR GRAIN (minute5_*). This is the one grain that genuinely cannot
--    be derived from the existing hourly rollups -- everything coarser (5h,
--    1d, 1w, 1mo, ...) is just a wider sum over hourly rows, so it needs no
--    storage at all. Measured on the live 9M-row dataset: 178.6 requests per
--    minute on average, so a 5-minute bucket holds ~893 requests globally.
--    Kept to the three lowest-cardinality scopes (overall / region / format)
--    because a 5-minute rollup keyed by app_id would be ~20M rows -- LARGER
--    than the 9M-row fact table. Sub-hour checks on a single app or advertiser
--    are raw-ad_events drills instead (partition-pruned, logged verbatim).
--
-- 2. COMPOSITE CELLS (hourly_geo_cell / _os_family_region / _format_region).
--    Docs/Mindmap/PRODUCTION_PLAN.md principle #2 says "never a wider
--    composite-key rollup whose cardinality could approach the fact table's".
--    These are a deliberate, measured exception, not a drift: the concern is
--    cardinality, and the combination counts were checked against the live
--    data before this file was written --
--        (region, country, device_model) -> 128 combos  -> 107,503 rows
--        (os_family, region)             ->  10 combos  ->   8,400 rows
--        (ad_format, region)             ->  25 combos  ->  21,000 rows
--    hourly_geo_cell is ~9% the size of the already-shipped hourly_by_app
--    (1,235,633 rows). The rejected design is still rejected, and now with a
--    number: app x format x geo x hour is ~7.8M rows against 9M raw -- the raw
--    table wearing a costume.
--
--    The reason to accept the exception is concrete. A region x device
--    breakdown is reachable today ONLY through engine/drilldown.py's raw
--    fallback, which runs solely INSIDE an investigation that something else
--    already triggered. So an incident that is invisible at every 1-D scope --
--    fill rate collapsing for one device generation in one region while
--    top-line revenue RISES -- can never be detected at all. These tables are
--    what make that class of incident detectable rather than merely
--    explainable after the fact.
--
-- All 5 measures are additive (Docs/metrics_glossary.md), so SummingMergeTree
-- suffices and rates are computed at read time -- never stored, because rates
-- cannot be merged. Always wrap columns in sum(...) when querying, since
-- SummingMergeTree only collapses same-key rows in the background.
--
-- IF NOT EXISTS throughout so re-running against a partially-applied database
-- (or the unseen-incident dataset) is safe.


-- ===========================================================================
-- 1. Sub-hour grain
-- ===========================================================================
-- The time column is `bucket`, not `hour`, precisely so that a query written
-- against the wrong grain fails loudly instead of silently reading hourly rows
-- as if they were 5-minute ones. engine/grains.py carries the column name per
-- table rather than assuming it.

CREATE TABLE IF NOT EXISTS minute5_overall
(
    bucket      DateTime,
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(bucket) ORDER BY bucket;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_minute5_overall TO minute5_overall AS
SELECT toStartOfFiveMinute(event_time) AS bucket,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY bucket;

CREATE TABLE IF NOT EXISTS minute5_by_region
(
    bucket DateTime, region LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(bucket) ORDER BY (bucket, region);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_minute5_by_region TO minute5_by_region AS
SELECT toStartOfFiveMinute(event_time) AS bucket,
       dictGet('geo_device_dict', 'region', geo_device_id) AS region,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY bucket, region;

CREATE TABLE IF NOT EXISTS minute5_by_format
(
    bucket DateTime, ad_format LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(bucket) ORDER BY (bucket, ad_format);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_minute5_by_format TO minute5_by_format AS
SELECT toStartOfFiveMinute(event_time) AS bucket, ad_format,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY bucket, ad_format;


-- ===========================================================================
-- 2. Composite cells
-- ===========================================================================

-- The geo cell. Ordered (hour, region, country, device_model) so a region-only
-- or region+country filter is still a sort-key prefix range scan, and the
-- coarser geo scopes can be DERIVED from this table instead of needing their
-- own -- though hourly_by_region/_country/_device_model already exist and stay
-- the cheaper source for 1-D queries.
CREATE TABLE IF NOT EXISTS hourly_geo_cell
(
    hour         DateTime,
    region       LowCardinality(String),
    country      LowCardinality(String),
    device_model LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, region, country, device_model);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_geo_cell TO hourly_geo_cell AS
SELECT toStartOfHour(event_time) AS hour,
       dictGet('geo_device_dict', 'region', geo_device_id)       AS region,
       dictGet('geo_device_dict', 'country', geo_device_id)      AS country,
       dictGet('geo_device_dict', 'device_model', geo_device_id) AS device_model,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, region, country, device_model;

-- os_family x region. This table exists to make one specific rule-out
-- runnable as a query rather than asserted in prose: seasonality moves
-- PEOPLE, and people carry all devices, so nothing seasonal can crash one OS
-- family while the other stays flat. It is also the direct test for a demand
-- partner outage (one OS family down across many regions, uniform across apps
-- and formats).
--
-- os_family is derived here rather than added to ad_events: os_version values
-- are 'iOS 17.2' / 'Android 14', so splitByChar(' ', ...)[1] yields exactly
-- two families (verified live: iOS, Android). No fact-table schema change.
CREATE TABLE IF NOT EXISTS hourly_os_family_region
(
    hour DateTime, os_family LowCardinality(String), region LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, os_family, region);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_os_family_region TO hourly_os_family_region AS
SELECT toStartOfHour(event_time) AS hour,
       splitByChar(' ', dictGet('geo_device_dict', 'os_version', geo_device_id))[1] AS os_family,
       dictGet('geo_device_dict', 'region', geo_device_id) AS region,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, os_family, region;

-- ad_format x region. Formats have structurally different fill levels and
-- wildly different prices, so they are never compared to each other -- each
-- gets its own band. Crossing with region separates "this format's demand
-- source went dark globally" from "this region lost that format".
CREATE TABLE IF NOT EXISTS hourly_format_region
(
    hour DateTime, ad_format LowCardinality(String), region LowCardinality(String),
    requests UInt64, fills UInt64, impressions UInt64, clicks UInt64, revenue Decimal64(6)
)
ENGINE = SummingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY (hour, ad_format, region);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_format_region TO hourly_format_region AS
SELECT toStartOfHour(event_time) AS hour, ad_format,
       dictGet('geo_device_dict', 'region', geo_device_id) AS region,
       count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
       sum(is_click) AS clicks, sum(revenue) AS revenue
FROM ad_events GROUP BY hour, ad_format, region;


-- ===========================================================================
-- 3. Reach -- the "fewer users vs less per user" discriminator
-- ===========================================================================
-- Distinct counts are the one thing that is NOT additive, so this is the only
-- table here that needs AggregatingMergeTree + -State/-Merge. It answers a
-- question no sum can: when requests fall, did we lose devices (real traffic
-- loss) or are the same devices each sending fewer requests (throttling / an
-- SDK change)? Those have completely different owners and completely
-- different fixes, and without this table the two are indistinguishable.
--
-- geo_device_id/app_id are LowCardinality(String), so uniqState() over them
-- would produce AggregateFunction(uniq, LowCardinality(String)) and fail to
-- match the column type -- toString() normalizes it (verified: the expression
-- below is exactly AggregateFunction(uniq, String)).
--
-- Read with uniqMerge(uniq_devices) / uniqMerge(uniq_apps), never a bare
-- column reference.
CREATE TABLE IF NOT EXISTS reach_hourly
(
    hour         DateTime,
    requests     SimpleAggregateFunction(sum, UInt64),
    uniq_devices AggregateFunction(uniq, String),
    uniq_apps    AggregateFunction(uniq, String)
)
ENGINE = AggregatingMergeTree PARTITION BY toYYYYMM(hour) ORDER BY hour;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_reach_hourly TO reach_hourly AS
SELECT toStartOfHour(event_time) AS hour,
       count() AS requests,
       uniqState(toString(geo_device_id)) AS uniq_devices,
       uniqState(toString(app_id))        AS uniq_apps
FROM ad_events GROUP BY hour;
