#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"
OUT="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/docs/rca_exploration.txt"
: > "$OUT"

run() {
  local title="$1"; local sql="$2"
  { echo; echo "===== $title ====="; curl -sS --fail-with-body -u "${USER}:${PASS}" --get "$URL" --data-urlencode "query=${sql}"; echo; } | tee -a "$OUT"
}

run "SHOW VIEW COLS" "SELECT * FROM eda.v_daily_metrics LIMIT 1 FORMAT Vertical"

run "ANOMALY SCAN vs same DOW prior week" "
WITH daily AS (
  SELECT event_date, event_dow, sum(requests) AS requests, sum(fills) AS fills,
    sum(impressions) AS impressions, sum(clicks) AS clicks, sum(revenue) AS revenue
  FROM eda.metrics_hourly
  GROUP BY event_date, event_dow
)
SELECT
  t.event_date AS day,
  t.event_dow AS dow,
  t.requests AS req,
  b.requests AS base_req,
  (t.requests - b.requests) / b.requests AS req_chg,
  t.revenue AS rev,
  b.revenue AS base_rev,
  (t.revenue - b.revenue) / b.revenue AS rev_chg,
  t.fills / t.requests AS fill_rt,
  b.fills / b.requests AS base_fill,
  (t.fills / t.requests) - (b.fills / b.requests) AS fill_chg,
  t.revenue / t.impressions * 1000 AS ecpm,
  b.revenue / b.impressions * 1000 AS base_ecpm
FROM daily AS t
INNER JOIN daily AS b ON b.event_date = t.event_date - 7
ORDER BY abs((t.revenue - b.revenue) / b.revenue) DESC
FORMAT PrettyCompact
"

run "Jun 23 REGION vs Jun 16" "
SELECT
  t.region AS region,
  t.requests AS req, b.requests AS base_req,
  t.fills / t.requests AS fill_rt, b.fills / b.requests AS base_fill,
  (t.fills / t.requests) - (b.fills / b.requests) AS fill_chg,
  t.revenue AS rev, b.revenue AS base_rev, t.revenue - b.revenue AS d_rev
FROM eda.metrics_daily_region AS t
INNER JOIN eda.metrics_daily_region AS b ON b.region = t.region AND b.event_date = t.event_date - 7
WHERE t.event_date = toDate('2026-06-23')
ORDER BY d_rev ASC
FORMAT PrettyCompact
"

run "Jun 23 DEVICE fill" "
SELECT
  g.device_model AS device_model,
  countIf(e.event_date = toDate('2026-06-23')) AS req_t,
  countIf(e.event_date = toDate('2026-06-16')) AS req_b,
  sumIf(e.is_filled, e.event_date = toDate('2026-06-23')) / countIf(e.event_date = toDate('2026-06-23')) AS fill_t,
  sumIf(e.is_filled, e.event_date = toDate('2026-06-16')) / countIf(e.event_date = toDate('2026-06-16')) AS fill_b,
  fill_t - fill_b AS fill_chg,
  sumIf(e.revenue, e.event_date = toDate('2026-06-23')) - sumIf(e.revenue, e.event_date = toDate('2026-06-16')) AS d_rev
FROM eda.ad_events AS e
LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-23'), toDate('2026-06-16'))
GROUP BY device_model
HAVING req_t > 0 AND req_b > 0
ORDER BY fill_chg ASC
LIMIT 12
FORMAT PrettyCompact
"

run "Jun 23 FORMAT fill" "
SELECT
  ad_format,
  countIf(event_date = toDate('2026-06-23')) AS req_t,
  sumIf(is_filled, event_date = toDate('2026-06-23')) / countIf(event_date = toDate('2026-06-23')) AS fill_t,
  sumIf(is_filled, event_date = toDate('2026-06-16')) / countIf(event_date = toDate('2026-06-16')) AS fill_b,
  fill_t - fill_b AS fill_chg,
  sumIf(revenue, event_date = toDate('2026-06-23')) - sumIf(revenue, event_date = toDate('2026-06-16')) AS d_rev
FROM eda.ad_events
WHERE event_date IN (toDate('2026-06-23'), toDate('2026-06-16'))
GROUP BY ad_format
ORDER BY fill_chg ASC
FORMAT PrettyCompact
"

run "Jun 23 CATEGORY fill" "
SELECT
  a.category AS category,
  countIf(e.event_date = toDate('2026-06-23')) AS req_t,
  sumIf(e.is_filled, e.event_date = toDate('2026-06-23')) / countIf(e.event_date = toDate('2026-06-23')) AS fill_t,
  sumIf(e.is_filled, e.event_date = toDate('2026-06-16')) / countIf(e.event_date = toDate('2026-06-16')) AS fill_b,
  fill_t - fill_b AS fill_chg,
  sumIf(e.revenue, e.event_date = toDate('2026-06-23')) - sumIf(e.revenue, e.event_date = toDate('2026-06-16')) AS d_rev
FROM eda.ad_events AS e
LEFT JOIN eda.apps AS a ON e.app_id = a.app_id
WHERE e.event_date IN (toDate('2026-06-23'), toDate('2026-06-16'))
GROUP BY category
ORDER BY fill_chg ASC
FORMAT PrettyCompact
"

run "Jun 23 OS fill" "
SELECT
  g.os_version AS os_version,
  countIf(e.event_date = toDate('2026-06-23')) AS req_t,
  sumIf(e.is_filled, e.event_date = toDate('2026-06-23')) / countIf(e.event_date = toDate('2026-06-23')) AS fill_t,
  sumIf(e.is_filled, e.event_date = toDate('2026-06-16')) / countIf(e.event_date = toDate('2026-06-16')) AS fill_b,
  fill_t - fill_b AS fill_chg,
  sumIf(e.revenue, e.event_date = toDate('2026-06-23')) - sumIf(e.revenue, e.event_date = toDate('2026-06-16')) AS d_rev
FROM eda.ad_events AS e
LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-23'), toDate('2026-06-16'))
GROUP BY os_version
ORDER BY fill_chg ASC
FORMAT PrettyCompact
"

run "Sundays volume (seasonality)" "
SELECT event_date, requests, revenue, fills/requests AS fill_rt, revenue/impressions*1000 AS ecpm
FROM (
  SELECT event_date, sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions, sum(revenue) AS revenue
  FROM eda.metrics_hourly
  WHERE event_dow = 7
  GROUP BY event_date
)
ORDER BY event_date
FORMAT PrettyCompact
"

run "Jun 19 eCPM by REGION vs Jun 12" "
SELECT
  g.region AS region,
  sumIf(e.revenue, e.event_date = toDate('2026-06-19')) / sumIf(e.is_impression, e.event_date = toDate('2026-06-19')) * 1000 AS ecpm_t,
  sumIf(e.revenue, e.event_date = toDate('2026-06-12')) / sumIf(e.is_impression, e.event_date = toDate('2026-06-12')) * 1000 AS ecpm_b,
  ecpm_t - ecpm_b AS ecpm_chg
FROM eda.ad_events AS e
LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-19'), toDate('2026-06-12'))
GROUP BY region
ORDER BY ecpm_chg ASC
FORMAT PrettyCompact
"

run "Jun 19 eCPM by FORMAT vs Jun 12" "
SELECT
  ad_format,
  sumIf(revenue, event_date = toDate('2026-06-19')) / sumIf(is_impression, event_date = toDate('2026-06-19')) * 1000 AS ecpm_t,
  sumIf(revenue, event_date = toDate('2026-06-12')) / sumIf(is_impression, event_date = toDate('2026-06-12')) * 1000 AS ecpm_b,
  ecpm_t - ecpm_b AS ecpm_chg
FROM eda.ad_events
WHERE event_date IN (toDate('2026-06-19'), toDate('2026-06-12'))
GROUP BY ad_format
ORDER BY ecpm_chg ASC
FORMAT PrettyCompact
"

run "Jun 19 eCPM by DEVICE vs Jun 12" "
SELECT
  g.device_model AS device_model,
  sumIf(e.revenue, e.event_date = toDate('2026-06-19')) / sumIf(e.is_impression, e.event_date = toDate('2026-06-19')) * 1000 AS ecpm_t,
  sumIf(e.revenue, e.event_date = toDate('2026-06-12')) / sumIf(e.is_impression, e.event_date = toDate('2026-06-12')) * 1000 AS ecpm_b,
  ecpm_t - ecpm_b AS ecpm_chg,
  sumIf(e.revenue, e.event_date = toDate('2026-06-19')) - sumIf(e.revenue, e.event_date = toDate('2026-06-12')) AS d_rev
FROM eda.ad_events AS e
LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-19'), toDate('2026-06-12'))
GROUP BY device_model
ORDER BY d_rev ASC
LIMIT 10
FORMAT PrettyCompact
"

echo "Wrote $OUT"
