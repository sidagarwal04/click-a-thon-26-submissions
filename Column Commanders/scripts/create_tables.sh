#!/bin/bash
# create_tables.sh — create all InMobi ad-analytics tables & materialized views
# on a ClickHouse Cloud (or any ClickHouse) instance.
#
# Usage:
#   CLICKHOUSE_HOST=<host> \
#   CLICKHOUSE_USER=default \
#   CLICKHOUSE_PASSWORD=<pw> \
#   CLICKHOUSE_DB=inmobi \
#   ./scripts/create_tables.sh
#
# Or simply copy .env.example → .env, fill in values, then:
#   set -a && source .env && set +a && ./scripts/create_tables.sh

set -euo pipefail

CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-localhost}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-default}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-}"
CLICKHOUSE_DB="${CLICKHOUSE_DB:-inmobi-analytics}"

CH() {
  clickhouse client \
    --host     "${CLICKHOUSE_HOST}" \
    --secure \
    --user     "${CLICKHOUSE_USER}" \
    --password "${CLICKHOUSE_PASSWORD}" \
    "$@"
}

# ─── database ────────────────────────────────────────────────────────────────

echo "creating database ${CLICKHOUSE_DB}"
CH --query "CREATE DATABASE IF NOT EXISTS \`${CLICKHOUSE_DB}\`"

# ─── dimension tables ────────────────────────────────────────────────────────

echo "creating apps"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.apps
(
    app_id         String,
    category       LowCardinality(String),   -- gaming|social|entertainment|news|ecommerce|utility|finance
    publisher_tier LowCardinality(String)    -- tier_1|tier_2|tier_3
)
ENGINE = MergeTree()
ORDER BY app_id
"

echo "creating advertisers"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.advertisers
(
    advertiser_id String,
    vertical      LowCardinality(String),    -- gaming|ecommerce|finance|travel|entertainment|auto|cpg
    campaign_type LowCardinality(String)     -- CPM|CPC|CPI
)
ENGINE = MergeTree()
ORDER BY advertiser_id
"

echo "creating geo_device"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.geo_device
(
    geo_device_id String,
    region        LowCardinality(String),    -- NAM|EU|APAC|LATAM|MEA
    country       LowCardinality(String),    -- US|CA|UK|DE|IN|JP|BR|MX|ZA|AE ...
    device_model  String,                   -- iPhone / Pixel / Galaxy / Redmi models
    os_version    LowCardinality(String)     -- iOS 16.4/17.2/17.5/18.1 | Android 12/13/14/15
)
ENGINE = MergeTree()
ORDER BY geo_device_id
"

# ─── fact table ──────────────────────────────────────────────────────────────

echo "creating ad_events"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_events
(
    event_time    DateTime64(3),
    app_id        String,
    geo_device_id String,
    advertiser_id String,                    -- empty on unfilled requests
    ad_format     LowCardinality(String),    -- banner|interstitial|native|rewarded|video
    is_filled     UInt8,
    is_impression UInt8,
    is_click      UInt8,
    revenue       Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (toDate(event_time), ad_format, app_id)
"

# ─── hourly rollup (all traffic) ─────────────────────────────────────────────

echo "creating ad_metrics_hourly"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_metrics_hourly
(
    hour        DateTime,
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Float64
)
ENGINE = SummingMergeTree((requests, fills, impressions, clicks, revenue))
ORDER BY hour
"

echo "creating ad_metrics_hourly_mv"
CH --query "
CREATE MATERIALIZED VIEW IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_metrics_hourly_mv
TO \`${CLICKHOUSE_DB}\`.ad_metrics_hourly
AS
SELECT
    toStartOfHour(event_time) AS hour,
    count()                   AS requests,
    sum(is_filled)            AS fills,
    sum(is_impression)        AS impressions,
    sum(is_click)             AS clicks,
    sum(revenue)              AS revenue
FROM \`${CLICKHOUSE_DB}\`.ad_events
GROUP BY hour
"

# ─── hourly rollup by ad format ───────────────────────────────────────────────

echo "creating ad_metrics_hourly_by_format"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_metrics_hourly_by_format
(
    hour        DateTime,
    ad_format   LowCardinality(String),
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Float64
)
ENGINE = SummingMergeTree((requests, fills, impressions, clicks, revenue))
ORDER BY (hour, ad_format)
"

echo "creating ad_metrics_hourly_by_format_mv"
CH --query "
CREATE MATERIALIZED VIEW IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_metrics_hourly_by_format_mv
TO \`${CLICKHOUSE_DB}\`.ad_metrics_hourly_by_format
AS
SELECT
    toStartOfHour(event_time) AS hour,
    ad_format,
    count()                   AS requests,
    sum(is_filled)            AS fills,
    sum(is_impression)        AS impressions,
    sum(is_click)             AS clicks,
    sum(revenue)              AS revenue
FROM \`${CLICKHOUSE_DB}\`.ad_events
GROUP BY hour, ad_format
"

# ─── daily rollup by ad format (lighter for trend queries) ────────────────────

echo "creating ad_metrics_daily_by_format"
CH --query "
CREATE TABLE IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_metrics_daily_by_format
(
    day         Date,
    ad_format   LowCardinality(String),
    requests    UInt64,
    fills       UInt64,
    impressions UInt64,
    clicks      UInt64,
    revenue     Float64
)
ENGINE = SummingMergeTree((requests, fills, impressions, clicks, revenue))
ORDER BY (day, ad_format)
"

echo "creating ad_metrics_daily_by_format_mv"
CH --query "
CREATE MATERIALIZED VIEW IF NOT EXISTS \`${CLICKHOUSE_DB}\`.ad_metrics_daily_by_format_mv
TO \`${CLICKHOUSE_DB}\`.ad_metrics_daily_by_format
AS
SELECT
    toDate(event_time) AS day,
    ad_format,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM \`${CLICKHOUSE_DB}\`.ad_events
GROUP BY day, ad_format
"

# ─── done ────────────────────────────────────────────────────────────────────

echo ""
echo "All tables and materialized views created in database '${CLICKHOUSE_DB}'."
echo ""
echo "Backfill MVs after loading historical data:"
echo "  INSERT INTO \`${CLICKHOUSE_DB}\`.ad_metrics_hourly SELECT toStartOfHour(event_time) AS hour, count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, sum(is_click) AS clicks, sum(revenue) AS revenue FROM \`${CLICKHOUSE_DB}\`.ad_events GROUP BY hour;"
echo "  INSERT INTO \`${CLICKHOUSE_DB}\`.ad_metrics_hourly_by_format SELECT toStartOfHour(event_time) AS hour, ad_format, count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, sum(is_click) AS clicks, sum(revenue) AS revenue FROM \`${CLICKHOUSE_DB}\`.ad_events GROUP BY hour, ad_format;"
echo "  INSERT INTO \`${CLICKHOUSE_DB}\`.ad_metrics_daily_by_format SELECT toDate(event_time) AS day, ad_format, count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, sum(is_click) AS clicks, sum(revenue) AS revenue FROM \`${CLICKHOUSE_DB}\`.ad_events GROUP BY day, ad_format;"
