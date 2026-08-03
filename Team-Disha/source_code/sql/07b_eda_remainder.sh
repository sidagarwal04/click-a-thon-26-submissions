#!/usr/bin/env bash
# Remainder of exhaustive EDA (queries that failed / not reached)
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

run "10 CTR by format" "
SELECT ad_format AS dim,
  round(sum(is_click)/sum(is_impression),5) AS ctr,
  round(sum(is_impression)/sum(is_filled),5) AS render
FROM eda.ad_events GROUP BY dim ORDER BY dim FORMAT PrettyCompact
"
run "10 CTR by region" "
SELECT g.region AS dim,
  round(sum(e.is_click)/sum(e.is_impression),5) AS ctr,
  round(sum(e.is_impression)/sum(e.is_filled),5) AS render
FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
GROUP BY dim ORDER BY dim FORMAT PrettyCompact
"
run "10 CTR by campaign" "
SELECT adv.campaign_type AS dim,
  round(sum(e.is_click)/sum(e.is_impression),5) AS ctr,
  round(sum(e.is_impression)/sum(e.is_filled),5) AS render
FROM eda.ad_events e INNER JOIN eda.advertisers adv ON e.advertiser_id=adv.advertiser_id
WHERE e.has_advertiser=1 GROUP BY dim ORDER BY dim FORMAT PrettyCompact
"

run "10b CTR wow outliers by format" "
WITH d AS (
  SELECT event_date, ad_format AS dim,
    sum(is_click) AS clicks, sum(is_impression) AS imp, sum(is_filled) AS fills
  FROM eda.ad_events GROUP BY event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round(t.clicks/t.imp - b.clicks/b.imp,5) AS ctr_chg,
  round(t.imp/t.fills - b.imp/b.fills,5) AS render_chg
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.imp > 5000
ORDER BY abs(t.clicks/t.imp - b.clicks/b.imp) DESC
LIMIT 15
FORMAT PrettyCompact
"

run "11 ROLLING 3d fill & ecpm" "
WITH daily AS (
  SELECT event_date,
    sum(fills)/sum(requests) AS fill_rt,
    sum(revenue)/sum(impressions)*1000 AS ecpm,
    sum(requests) AS req
  FROM eda.metrics_hourly GROUP BY event_date
)
SELECT event_date,
  round(fill_rt,4) AS fill,
  round(avg(fill_rt) OVER (ORDER BY event_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),4) AS fill_3d,
  round(ecpm,4) AS ecpm,
  round(avg(ecpm) OVER (ORDER BY event_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),4) AS ecpm_3d,
  req
FROM daily ORDER BY event_date
FORMAT PrettyCompact
"

run "12 VERTICAL eCPM/volume wow outliers" "
WITH d AS (
  SELECT e.event_date, adv.vertical AS dim,
    count() AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e
  INNER JOIN eda.advertisers adv ON e.advertiser_id=adv.advertiser_id
  WHERE e.has_advertiser=1
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round((t.fills-b.fills)/b.fills,4) AS fill_vol_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 20
FORMAT PrettyCompact
"

run "12b CAMPAIGN TYPE wow" "
WITH d AS (
  SELECT e.event_date, adv.campaign_type AS dim,
    count() AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp, sum(e.is_click) AS clicks
  FROM eda.ad_events e
  INNER JOIN eda.advertisers adv ON e.advertiser_id=adv.advertiser_id
  WHERE e.has_advertiser=1
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round((t.fills-b.fills)/b.fills,4) AS vol_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.clicks/t.imp - b.clicks/b.imp,5) AS ctr_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 15
FORMAT PrettyCompact
"

# Extra: any quiet global day with a loud hidden segment?
run "13 HIDDEN residual: max |segment fill_chg| on quiet global days" "
WITH daily AS (
  SELECT event_date, sum(requests) AS req, sum(fills) AS fills, sum(impressions) AS imp, sum(revenue) AS rev
  FROM eda.metrics_hourly GROUP BY event_date
), quiet AS (
  SELECT t.event_date AS day
  FROM daily t INNER JOIN daily b ON b.event_date=t.event_date-7
  WHERE abs((t.rev-b.rev)/b.rev) < 0.03
    AND abs(t.fills/t.req - b.fills/b.req) < 0.01
    AND abs(t.rev/t.imp*1000 - b.rev/b.imp*1000) < 0.03
), osd AS (
  SELECT e.event_date, g.os_version AS dim,
    count() AS req, sum(e.is_filled) AS fills
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg, t.req
FROM osd t
INNER JOIN osd b ON b.dim=t.dim AND b.event_date=t.event_date-7
INNER JOIN quiet q ON q.day=t.event_date
WHERE t.req > 5000 AND b.req > 5000
ORDER BY abs(t.fills/t.req - b.fills/b.req) DESC
LIMIT 15
FORMAT PrettyCompact
"

run "13b HIDDEN residual: format eCPM on quiet global days" "
WITH daily AS (
  SELECT event_date, sum(requests) AS req, sum(fills) AS fills, sum(impressions) AS imp, sum(revenue) AS rev
  FROM eda.metrics_hourly GROUP BY event_date
), quiet AS (
  SELECT t.event_date AS day
  FROM daily t INNER JOIN daily b ON b.event_date=t.event_date-7
  WHERE abs((t.rev-b.rev)/b.rev) < 0.03
    AND abs(t.fills/t.req - b.fills/b.req) < 0.01
    AND abs(t.rev/t.imp*1000 - b.rev/b.imp*1000) < 0.03
), fd AS (
  SELECT event_date, ad_format AS dim, sum(revenue) AS rev, sum(is_impression) AS imp
  FROM eda.ad_events GROUP BY event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM fd t
INNER JOIN fd b ON b.dim=t.dim AND b.event_date=t.event_date-7
INNER JOIN quiet q ON q.day=t.event_date
WHERE t.imp > 5000
ORDER BY abs(t.rev/t.imp*1000 - b.rev/b.imp*1000) DESC
LIMIT 15
FORMAT PrettyCompact
"

run "14 Jun 21 vs Jun 19-22: is volume day also eCPM day?" "
SELECT event_date,
  count() AS req,
  round(sum(is_filled)/count(),4) AS fill,
  round(sum(revenue)/sum(is_impression)*1000,4) AS ecpm,
  round(sum(revenue),2) AS rev
FROM eda.ad_events
WHERE event_date BETWEEN toDate('2026-06-19') AND toDate('2026-06-25')
GROUP BY event_date ORDER BY event_date
FORMAT PrettyCompact
"

run "14b Jun 21 interstitial EU eCPM still soft?" "
SELECT e.event_date,
  round(sum(e.revenue)/sum(e.is_impression)*1000,4) AS eu_int_ecpm,
  count() AS req
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.ad_format='interstitial' AND g.region='EU'
  AND e.event_date BETWEEN toDate('2026-06-12') AND toDate('2026-06-26')
GROUP BY e.event_date ORDER BY e.event_date
FORMAT PrettyCompact
"

echo done
