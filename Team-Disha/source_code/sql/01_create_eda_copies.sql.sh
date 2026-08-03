#!/usr/bin/env bash
# Create eda.* copies, enrich columns, rollups, and views. Never mutates default.* facts beyond read.
set -euo pipefail

ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"

q() {
  local sql="$1"
  echo ">> ${sql:0:120}..."
  curl -sS --fail-with-body -u "${USER}:${PASS}" "$URL" --data-binary "$sql"
  echo
}

echo "=== CREATE DATABASE eda ==="
q "CREATE DATABASE IF NOT EXISTS eda"

echo "=== COPY DIMENSIONS ==="
q "DROP TABLE IF EXISTS eda.apps"
q "CREATE TABLE eda.apps ENGINE = MergeTree ORDER BY app_id AS SELECT * FROM default.apps"

q "DROP TABLE IF EXISTS eda.advertisers"
q "CREATE TABLE eda.advertisers ENGINE = MergeTree ORDER BY advertiser_id AS SELECT * FROM default.advertisers"

q "DROP TABLE IF EXISTS eda.geo_device"
q "CREATE TABLE eda.geo_device ENGINE = MergeTree ORDER BY geo_device_id AS SELECT * FROM default.geo_device"

echo "=== COPY + ENRICH ad_events (9M) ==="
q "DROP TABLE IF EXISTS eda.ad_events"
q "CREATE TABLE eda.ad_events
(
  event_time DateTime64(3),
  app_id String,
  geo_device_id String,
  advertiser_id String,
  ad_format LowCardinality(String),
  is_filled UInt8,
  is_impression UInt8,
  is_click UInt8,
  revenue Float64,
  event_date Date,
  event_hour UInt8,
  event_dow UInt8,
  is_weekend UInt8,
  has_advertiser UInt8
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_hour, app_id, geo_device_id)
AS SELECT
  event_time,
  app_id,
  geo_device_id,
  advertiser_id,
  ad_format,
  is_filled,
  is_impression,
  is_click,
  revenue,
  toDate(event_time) AS event_date,
  toUInt8(toHour(event_time)) AS event_hour,
  toUInt8(toDayOfWeek(event_time)) AS event_dow,
  toUInt8(toDayOfWeek(event_time) IN (6, 7)) AS is_weekend,
  toUInt8(advertiser_id != '') AS has_advertiser
FROM default.ad_events"

echo "=== HOURLY ROLLUP ==="
q "DROP TABLE IF EXISTS eda.metrics_hourly"
q "CREATE TABLE eda.metrics_hourly
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_hour)
AS SELECT
  event_date,
  event_hour,
  event_dow,
  is_weekend,
  count() AS requests,
  sum(is_filled) AS fills,
  sum(is_impression) AS impressions,
  sum(is_click) AS clicks,
  sum(revenue) AS revenue
FROM eda.ad_events
GROUP BY event_date, event_hour, event_dow, is_weekend"

echo "=== DAILY x REGION ROLLUP ==="
q "DROP TABLE IF EXISTS eda.metrics_daily_region"
q "CREATE TABLE eda.metrics_daily_region
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, region)
AS SELECT
  e.event_date AS event_date,
  e.event_dow AS event_dow,
  e.is_weekend AS is_weekend,
  g.region AS region,
  count() AS requests,
  sum(e.is_filled) AS fills,
  sum(e.is_impression) AS impressions,
  sum(e.is_click) AS clicks,
  sum(e.revenue) AS revenue
FROM eda.ad_events AS e
LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id
GROUP BY event_date, event_dow, is_weekend, region"

echo "=== VIEWS ==="
q "CREATE OR REPLACE VIEW eda.v_daily_metrics AS
SELECT
  event_date,
  any(event_dow) AS event_dow,
  any(is_weekend) AS is_weekend,
  sum(requests) AS requests,
  sum(fills) AS fills,
  sum(impressions) AS impressions,
  sum(clicks) AS clicks,
  sum(revenue) AS revenue,
  fills / requests AS fill_rate,
  clicks / nullIf(impressions, 0) AS ctr,
  revenue / nullIf(impressions, 0) * 1000 AS ecpm,
  revenue / requests AS rpr
FROM eda.metrics_hourly
GROUP BY event_date"

q "CREATE OR REPLACE VIEW eda.v_hourly_metrics AS
SELECT
  event_date,
  event_hour,
  event_dow,
  is_weekend,
  requests,
  fills,
  impressions,
  clicks,
  revenue,
  fills / requests AS fill_rate,
  clicks / nullIf(impressions, 0) AS ctr,
  revenue / nullIf(impressions, 0) * 1000 AS ecpm,
  revenue / requests AS rpr
FROM eda.metrics_hourly"

echo "=== VERIFY ==="
q "SHOW TABLES FROM eda"
q "SELECT 'ad_events' AS t, count() AS n FROM eda.ad_events
UNION ALL SELECT 'apps', count() FROM eda.apps
UNION ALL SELECT 'advertisers', count() FROM eda.advertisers
UNION ALL SELECT 'geo_device', count() FROM eda.geo_device
UNION ALL SELECT 'metrics_hourly', count() FROM eda.metrics_hourly
UNION ALL SELECT 'metrics_daily_region', count() FROM eda.metrics_daily_region
FORMAT PrettyCompact"

echo "DONE"
