#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"
OUT="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/docs/rca_deep.txt"

run() {
  local title="$1"; local sql="$2"
  { echo; echo "===== $title ====="; curl -sS --fail-with-body -u "${USER}:${PASS}" --get "$URL" --data-urlencode "query=${sql}"; echo; } | tee -a "$OUT"
}

run "C deep finance category x format" "
SELECT e.ad_format AS dim,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-19'))*1000 AS ecpm_t,
  sumIf(e.revenue,e.event_date=toDate('2026-06-12'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-12'))*1000 AS ecpm_b,
  ecpm_t-ecpm_b AS ecpm_chg,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))-sumIf(e.revenue,e.event_date=toDate('2026-06-12')) AS d_rev
FROM eda.ad_events e LEFT JOIN eda.apps a ON e.app_id=a.app_id
WHERE e.event_date IN (toDate('2026-06-19'),toDate('2026-06-12')) AND a.category='finance'
GROUP BY dim ORDER BY d_rev ASC FORMAT PrettyCompact
"

run "C deep finance category x region" "
SELECT g.region AS dim,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-19'))*1000 AS ecpm_t,
  sumIf(e.revenue,e.event_date=toDate('2026-06-12'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-12'))*1000 AS ecpm_b,
  ecpm_t-ecpm_b AS ecpm_chg,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))-sumIf(e.revenue,e.event_date=toDate('2026-06-12')) AS d_rev
FROM eda.ad_events e
LEFT JOIN eda.apps a ON e.app_id=a.app_id
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-19'),toDate('2026-06-12')) AND a.category='finance'
GROUP BY dim ORDER BY d_rev ASC FORMAT PrettyCompact
"

run "C deep finance x interstitial x region" "
SELECT g.region AS dim,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-19'))*1000 AS ecpm_t,
  sumIf(e.revenue,e.event_date=toDate('2026-06-12'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-12'))*1000 AS ecpm_b,
  ecpm_t-ecpm_b AS ecpm_chg,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))-sumIf(e.revenue,e.event_date=toDate('2026-06-12')) AS d_rev,
  sumIf(e.is_impression,e.event_date=toDate('2026-06-19')) AS imp_t
FROM eda.ad_events e
LEFT JOIN eda.apps a ON e.app_id=a.app_id
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-19'),toDate('2026-06-12')) AND a.category='finance' AND e.ad_format='interstitial'
GROUP BY dim ORDER BY d_rev ASC FORMAT PrettyCompact
"

run "C deep EU interstitial x category" "
SELECT a.category AS dim,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-19'))*1000 AS ecpm_t,
  sumIf(e.revenue,e.event_date=toDate('2026-06-12'))/sumIf(e.is_impression,e.event_date=toDate('2026-06-12'))*1000 AS ecpm_b,
  ecpm_t-ecpm_b AS ecpm_chg,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))-sumIf(e.revenue,e.event_date=toDate('2026-06-12')) AS d_rev
FROM eda.ad_events e
LEFT JOIN eda.apps a ON e.app_id=a.app_id
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-19'),toDate('2026-06-12')) AND g.region='EU' AND e.ad_format='interstitial'
GROUP BY dim ORDER BY d_rev ASC FORMAT PrettyCompact
"

run "C attribution: format x region revenue delta matrix" "
SELECT e.ad_format AS format, g.region AS region,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))-sumIf(e.revenue,e.event_date=toDate('2026-06-12')) AS d_rev,
  sumIf(e.revenue,e.event_date=toDate('2026-06-19'))/nullIf(sumIf(e.is_impression,e.event_date=toDate('2026-06-19')),0)*1000 AS ecpm_t,
  sumIf(e.revenue,e.event_date=toDate('2026-06-12'))/nullIf(sumIf(e.is_impression,e.event_date=toDate('2026-06-12')),0)*1000 AS ecpm_b
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-19'),toDate('2026-06-12'))
GROUP BY format, region
ORDER BY d_rev ASC
LIMIT 15
FORMAT PrettyCompact
"

echo "done"
