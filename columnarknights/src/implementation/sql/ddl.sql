-- Run with `clickhouse-client --database <db>` (or clickhouse-connect with database=<db>)
-- so these unqualified names land in the right database. See scripts/load_data.sh.

CREATE TABLE IF NOT EXISTS apps
(
    app_id String,
    category LowCardinality(String),
    publisher_tier LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY app_id;

CREATE TABLE IF NOT EXISTS advertisers
(
    advertiser_id String,
    vertical LowCardinality(String),
    campaign_type LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS geo_device
(
    geo_device_id String,
    region LowCardinality(String),
    country LowCardinality(String),
    device_model LowCardinality(String),
    os_version LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY geo_device_id;

-- Raw fact table, one row per ad event, exactly as delivered.
-- event_time is pinned to UTC explicitly: the source parquet has naive
-- timestamps, and leaving the column timezone-less would make ClickHouse
-- interpret them in the server's local timezone (wrong on any server that
-- isn't already UTC, e.g. a laptop set to Asia/Kolkata), shifting every
-- day/hour boundary and corrupting seasonality comparisons.
CREATE TABLE IF NOT EXISTS ad_events_raw
(
    event_time DateTime('UTC'),
    app_id String,
    geo_device_id String,
    advertiser_id String,
    ad_format LowCardinality(String),
    is_filled UInt8,
    is_impression UInt8,
    is_click UInt8,
    revenue Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, app_id);

-- Denormalized, analysis-ready fact table: every dimension pre-joined so every
-- drill-down query the investigation pipeline issues is a single-table GROUP BY,
-- with no joins at query time. Built once from ad_events_raw + the three dimension
-- tables (see sql/build_fact.sql).
CREATE TABLE IF NOT EXISTS fact_events
(
    event_time DateTime('UTC'),
    event_date Date MATERIALIZED toDate(event_time),
    app_id String,
    category LowCardinality(String),
    publisher_tier LowCardinality(String),
    geo_device_id String,
    region LowCardinality(String),
    country LowCardinality(String),
    device_model LowCardinality(String),
    os_version LowCardinality(String),
    advertiser_id String,
    vertical LowCardinality(String),
    campaign_type LowCardinality(String),
    ad_format LowCardinality(String),
    is_filled UInt8,
    is_impression UInt8,
    is_click UInt8,
    revenue Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (event_time, app_id, advertiser_id);

-- Persisted results of every investigation the pipeline has run (CLI, web app,
-- or MCP/chat). This is the only thing the LibreChat follow-up flow is allowed
-- to read from (see mcp_server.get_investigation/drill_deeper) — the chat
-- agent never gets raw SELECT access to fact_events, only to what a
-- deterministic run of the pipeline already validated and computed. Not
-- touched by scripts/load_data.sh's reload (it's app state, not source data).
CREATE TABLE IF NOT EXISTS investigations
(
    id String,
    metric LowCardinality(String),
    current_window_start Date,
    current_window_end Date,
    baseline_window_start Date,
    baseline_window_end Date,
    drill_factor LowCardinality(String),
    decomposition String,
    drill_down String,
    narrative String,
    langfuse_trace_url String,
    local_trace_path String,
    created_at DateTime('UTC') DEFAULT now()
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY id;
