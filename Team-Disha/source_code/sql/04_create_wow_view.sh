#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"

curl -sS --fail-with-body -u "${USER}:${PASS}" "$URL" --data-binary @- <<'SQL'
CREATE OR REPLACE VIEW eda.v_wow_daily AS
WITH daily AS (
  SELECT
    event_date,
    event_dow,
    is_weekend,
    sum(requests) AS requests,
    sum(fills) AS fills,
    sum(impressions) AS impressions,
    sum(clicks) AS clicks,
    sum(revenue) AS revenue
  FROM eda.metrics_hourly
  GROUP BY event_date, event_dow, is_weekend
)
SELECT
  t.event_date AS event_date,
  t.event_dow AS event_dow,
  t.is_weekend AS is_weekend,
  t.requests AS requests,
  b.requests AS base_requests,
  (t.requests - b.requests) / nullIf(b.requests, 0) AS requests_chg,
  t.fills / t.requests AS fill_rate,
  b.fills / b.requests AS base_fill_rate,
  (t.fills / t.requests) - (b.fills / b.requests) AS fill_rate_chg,
  t.revenue / nullIf(t.impressions, 0) * 1000 AS ecpm,
  b.revenue / nullIf(b.impressions, 0) * 1000 AS base_ecpm,
  (t.revenue / nullIf(t.impressions, 0) * 1000) - (b.revenue / nullIf(b.impressions, 0) * 1000) AS ecpm_chg,
  t.revenue AS revenue,
  b.revenue AS base_revenue,
  (t.revenue - b.revenue) / nullIf(b.revenue, 0) AS revenue_chg
FROM daily AS t
INNER JOIN daily AS b ON b.event_date = t.event_date - 7
SQL

curl -sS --fail-with-body -u "${USER}:${PASS}" --get "$URL" --data-urlencode "query=SHOW TABLES FROM eda FORMAT PrettyCompact"
echo
