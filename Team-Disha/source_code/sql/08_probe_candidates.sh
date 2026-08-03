#!/usr/bin/env bash
# Probe candidate 4th incidents: EU interstitial window + iOS 18.1 APAC fill
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"
OUT="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/docs/eda_exhaustive.txt"

run() {
  local title="$1"; local sql="$2"
  { echo; echo "===== $title ====="; curl -sS --fail-with-body -u "${USER}:${PASS}" --get "$URL" --data-urlencode "query=${sql}"; echo; } | tee -a "$OUT"
}

run "15 EU interstitial vs EU native eCPM daily" "
SELECT e.event_date,
  round(sumIf(e.revenue, e.ad_format='interstitial')/nullIf(sumIf(e.is_impression, e.ad_format='interstitial'),0)*1000,4) AS eu_int_ecpm,
  round(sumIf(e.revenue, e.ad_format='native')/nullIf(sumIf(e.is_impression, e.ad_format='native'),0)*1000,4) AS eu_nat_ecpm,
  round(sum(e.revenue)/sum(e.is_impression)*1000,4) AS eu_ecpm
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.region='EU'
GROUP BY e.event_date ORDER BY e.event_date
FORMAT PrettyCompact
"

run "15b finance category eCPM daily" "
SELECT e.event_date,
  round(sum(e.revenue)/sum(e.is_impression)*1000,4) AS finance_ecpm,
  sum(e.is_impression) AS imp
FROM eda.ad_events e
LEFT JOIN eda.apps a ON e.app_id=a.app_id
WHERE a.category='finance'
GROUP BY e.event_date ORDER BY e.event_date
FORMAT PrettyCompact
"

run "15c global eCPM decomposition mid-June" "
SELECT event_date,
  round(sum(revenue)/sum(is_impression)*1000,4) AS ecpm,
  round(sumIf(revenue, ad_format='interstitial')/nullIf(sumIf(is_impression, ad_format='interstitial'),0)*1000,4) AS int_ecpm,
  round(sumIf(revenue, ad_format='native')/nullIf(sumIf(is_impression, ad_format='native'),0)*1000,4) AS nat_ecpm
FROM eda.ad_events
WHERE event_date BETWEEN toDate('2026-06-12') AND toDate('2026-06-26')
GROUP BY event_date ORDER BY event_date
FORMAT PrettyCompact
"

run "16 iOS 18.1 fill by region daily" "
SELECT e.event_date, g.region,
  round(sum(e.is_filled)/count(),4) AS fill,
  count() AS req,
  round(sum(e.revenue),2) AS rev
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.os_version='iOS 18.1'
GROUP BY e.event_date, g.region
ORDER BY e.event_date, g.region
FORMAT PrettyCompact
"

run "16b iOS 18.1 APAC fill only (compact)" "
SELECT e.event_date,
  round(sum(e.is_filled)/count(),4) AS fill_apac_ios181,
  count() AS req,
  round(sum(e.is_filled)/count() - lagInFrame(sum(e.is_filled)/count()) OVER (ORDER BY e.event_date),4) AS d_fill
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.os_version='iOS 18.1' AND g.region='APAC'
GROUP BY e.event_date ORDER BY e.event_date
FORMAT PrettyCompact
"

run "16c iOS 18.1 global fill daily" "
SELECT e.event_date,
  round(sum(e.is_filled)/count(),4) AS fill,
  count() AS req
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.os_version='iOS 18.1'
GROUP BY e.event_date ORDER BY e.event_date
FORMAT PrettyCompact
"

run "16d OTHER OS in APAC fill Jun 25-Jul 5" "
SELECT e.event_date, g.os_version,
  round(sum(e.is_filled)/count(),4) AS fill,
  count() AS req
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.region='APAC' AND e.event_date BETWEEN toDate('2026-06-25') AND toDate('2026-07-05')
GROUP BY e.event_date, g.os_version
ORDER BY e.event_date, g.os_version
FORMAT PrettyCompact
"

run "16e iOS 18.1 APAC deep: country/format/device during crash" "
SELECT 'country' AS kind, g.country AS dim,
  round(sumIf(e.is_filled, e.event_date=toDate('2026-06-29'))/nullIf(countIf(e.event_date=toDate('2026-06-29')),0),4) AS fill_t,
  round(sumIf(e.is_filled, e.event_date=toDate('2026-06-22'))/nullIf(countIf(e.event_date=toDate('2026-06-22')),0),4) AS fill_b,
  countIf(e.event_date=toDate('2026-06-29')) AS req_t
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.os_version='iOS 18.1' AND g.region='APAC'
  AND e.event_date IN (toDate('2026-06-29'), toDate('2026-06-22'))
GROUP BY dim
ORDER BY req_t DESC
FORMAT PrettyCompact
"

run "16f iOS 18.1 APAC x format Jun 29 vs 22" "
SELECT e.ad_format,
  round(sumIf(e.is_filled, e.event_date=toDate('2026-06-29'))/nullIf(countIf(e.event_date=toDate('2026-06-29')),0),4) AS fill_t,
  round(sumIf(e.is_filled, e.event_date=toDate('2026-06-22'))/nullIf(countIf(e.event_date=toDate('2026-06-22')),0),4) AS fill_b,
  countIf(e.event_date=toDate('2026-06-29')) AS req_t
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.os_version='iOS 18.1' AND g.region='APAC'
  AND e.event_date IN (toDate('2026-06-29'), toDate('2026-06-22'))
GROUP BY e.ad_format ORDER BY req_t DESC
FORMAT PrettyCompact
"

run "16g contribution: how much does iOS18.1 APAC move global fill Jun 28-30" "
SELECT e.event_date,
  round(sum(e.is_filled)/count(),4) AS global_fill,
  round(sumIf(e.is_filled, g.os_version='iOS 18.1' AND g.region='APAC')/nullIf(countIf(g.os_version='iOS 18.1' AND g.region='APAC'),0),4) AS seg_fill,
  countIf(g.os_version='iOS 18.1' AND g.region='APAC') AS seg_req,
  round(countIf(g.os_version='iOS 18.1' AND g.region='APAC')/count(),4) AS seg_share,
  round(sumIf(e.is_filled, NOT (g.os_version='iOS 18.1' AND g.region='APAC'))/nullIf(countIf(NOT (g.os_version='iOS 18.1' AND g.region='APAC')),0),4) AS other_fill
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.event_date BETWEEN toDate('2026-06-25') AND toDate('2026-07-05')
GROUP BY e.event_date ORDER BY e.event_date
FORMAT PrettyCompact
"

run "17 any other OS x region with |fill-0.78|>0.15 sustained" "
SELECT g.os_version, g.region, e.event_date,
  round(sum(e.is_filled)/count(),4) AS fill,
  count() AS req
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
GROUP BY g.os_version, g.region, e.event_date
HAVING req > 1500 AND abs(fill - 0.78) > 0.15
ORDER BY e.event_date, fill
FORMAT PrettyCompact
"

echo done
