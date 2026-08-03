#!/usr/bin/env bash
# Deep multi-dimension RCA for each known drop window (eda.* only)
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"
OUT="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/docs/rca_deep.txt"
: > "$OUT"

run() {
  local title="$1"; local sql="$2"
  { echo; echo "===== $title ====="; curl -sS --fail-with-body -u "${USER}:${PASS}" --get "$URL" --data-urlencode "query=${sql}"; echo; } | tee -a "$OUT"
}

# Generic: compare target vs baseline day across a dimension expression.
# Args embedded in SQL via env-like placeholders substituted below.

drill_fill() {
  local title="$1" tgt="$2" base="$3" dim_select="$4" from_join="$5" where_extra="${6:-1}"
  run "$title" "
SELECT
  dim,
  req_t, req_b,
  fill_t, fill_b,
  fill_t - fill_b AS fill_chg,
  rev_t - rev_b AS d_rev,
  /* contribution to global fill-point loss weighted by target request share */
  (fill_t - fill_b) * req_t AS fill_impact
FROM (
  SELECT
    ${dim_select} AS dim,
    countIf(e.event_date = toDate('${tgt}')) AS req_t,
    countIf(e.event_date = toDate('${base}')) AS req_b,
    sumIf(e.is_filled, e.event_date = toDate('${tgt}')) / nullIf(countIf(e.event_date = toDate('${tgt}')), 0) AS fill_t,
    sumIf(e.is_filled, e.event_date = toDate('${base}')) / nullIf(countIf(e.event_date = toDate('${base}')), 0) AS fill_b,
    sumIf(e.revenue, e.event_date = toDate('${tgt}')) AS rev_t,
    sumIf(e.revenue, e.event_date = toDate('${base}')) AS rev_b
  FROM eda.ad_events AS e
  ${from_join}
  WHERE e.event_date IN (toDate('${tgt}'), toDate('${base}')) AND (${where_extra})
  GROUP BY dim
  HAVING req_t > 1000 AND req_b > 1000
)
ORDER BY fill_impact ASC
LIMIT 20
FORMAT PrettyCompact
"
}

drill_ecpm() {
  local title="$1" tgt="$2" base="$3" dim_select="$4" from_join="$5" where_extra="${6:-1}"
  run "$title" "
SELECT
  dim,
  imp_t, imp_b,
  ecpm_t, ecpm_b,
  ecpm_t - ecpm_b AS ecpm_chg,
  rev_t - rev_b AS d_rev,
  (ecpm_t - ecpm_b) * imp_t / 1000 AS ecpm_impact
FROM (
  SELECT
    ${dim_select} AS dim,
    sumIf(e.is_impression, e.event_date = toDate('${tgt}')) AS imp_t,
    sumIf(e.is_impression, e.event_date = toDate('${base}')) AS imp_b,
    sumIf(e.revenue, e.event_date = toDate('${tgt}')) / nullIf(sumIf(e.is_impression, e.event_date = toDate('${tgt}')), 0) * 1000 AS ecpm_t,
    sumIf(e.revenue, e.event_date = toDate('${base}')) / nullIf(sumIf(e.is_impression, e.event_date = toDate('${base}')), 0) * 1000 AS ecpm_b,
    sumIf(e.revenue, e.event_date = toDate('${tgt}')) AS rev_t,
    sumIf(e.revenue, e.event_date = toDate('${base}')) AS rev_b
  FROM eda.ad_events AS e
  ${from_join}
  WHERE e.event_date IN (toDate('${tgt}'), toDate('${base}')) AND (${where_extra})
  GROUP BY dim
  HAVING imp_t > 1000 AND imp_b > 1000
)
ORDER BY d_rev ASC
LIMIT 20
FORMAT PrettyCompact
"
}

drill_volume() {
  local title="$1" tgt="$2" base="$3" dim_select="$4" from_join="$5" where_extra="${6:-1}"
  run "$title" "
SELECT
  dim,
  req_t, req_b,
  (req_t - req_b) / nullIf(req_b, 0) AS req_chg,
  req_t - req_b AS d_req,
  rev_t - rev_b AS d_rev
FROM (
  SELECT
    ${dim_select} AS dim,
    countIf(e.event_date = toDate('${tgt}')) AS req_t,
    countIf(e.event_date = toDate('${base}')) AS req_b,
    sumIf(e.revenue, e.event_date = toDate('${tgt}')) AS rev_t,
    sumIf(e.revenue, e.event_date = toDate('${base}')) AS rev_b
  FROM eda.ad_events AS e
  ${from_join}
  WHERE e.event_date IN (toDate('${tgt}'), toDate('${base}')) AND (${where_extra})
  GROUP BY dim
  HAVING req_b > 1000
)
ORDER BY d_req ASC
LIMIT 20
FORMAT PrettyCompact
"
}

GEO="LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id"
APP="LEFT JOIN eda.apps AS a ON e.app_id = a.app_id"
ADV="LEFT JOIN eda.advertisers AS adv ON e.advertiser_id = adv.advertiser_id"

echo "################ INCIDENT A: 2026-06-21 VOLUME vs 2026-06-14 (Sundays)" | tee -a "$OUT"
run "A factor snapshot" "
SELECT
  t.event_date AS day, t.requests, b.requests AS base_req,
  (t.requests-b.requests)/b.requests AS req_chg,
  t.fills/t.requests AS fill_t, b.fills/b.requests AS fill_b,
  t.revenue/t.impressions*1000 AS ecpm_t, b.revenue/b.impressions*1000 AS ecpm_b,
  t.revenue AS rev, b.revenue AS base_rev, (t.revenue-b.revenue)/b.revenue AS rev_chg
FROM eda.v_daily_metrics t
INNER JOIN eda.v_daily_metrics b ON b.event_date = toDate('2026-06-14')
WHERE t.event_date = toDate('2026-06-21')
FORMAT PrettyCompact
"

drill_volume "A region"   2026-06-21 2026-06-14 "g.region" "$GEO"
drill_volume "A country"  2026-06-21 2026-06-14 "g.country" "$GEO"
drill_volume "A category" 2026-06-21 2026-06-14 "a.category" "$APP"
drill_volume "A tier"     2026-06-21 2026-06-14 "a.publisher_tier" "$APP"
drill_volume "A format"   2026-06-21 2026-06-14 "e.ad_format" ""
drill_volume "A device"   2026-06-21 2026-06-14 "g.device_model" "$GEO"
drill_volume "A OS"       2026-06-21 2026-06-14 "g.os_version" "$GEO"
drill_volume "A vertical (filled)" 2026-06-21 2026-06-14 "adv.vertical" "$ADV" "e.has_advertiser=1"

# Hourly shape for volume crash
run "A hourly request profile vs prior Sunday" "
SELECT
  t.event_hour AS hour,
  t.requests AS req_t,
  b.requests AS req_b,
  t.requests - b.requests AS d_req,
  (t.requests - b.requests) / nullIf(b.requests,0) AS req_chg
FROM eda.metrics_hourly t
INNER JOIN eda.metrics_hourly b ON b.event_hour = t.event_hour AND b.event_date = toDate('2026-06-14')
WHERE t.event_date = toDate('2026-06-21')
ORDER BY hour
FORMAT PrettyCompact
"

echo "################ INCIDENT B: 2026-06-23 FILL vs 2026-06-16" | tee -a "$OUT"
run "B factor snapshot" "
SELECT
  t.event_date AS day, t.requests, b.requests AS base_req,
  t.fills/t.requests AS fill_t, b.fills/b.requests AS fill_b,
  (t.fills/t.requests)-(b.fills/b.requests) AS fill_chg,
  t.revenue/t.impressions*1000 AS ecpm_t, b.revenue/b.impressions*1000 AS ecpm_b,
  t.revenue AS rev, b.revenue AS base_rev, (t.revenue-b.revenue)/b.revenue AS rev_chg
FROM eda.v_daily_metrics t
INNER JOIN eda.v_daily_metrics b ON b.event_date = toDate('2026-06-16')
WHERE t.event_date = toDate('2026-06-23')
FORMAT PrettyCompact
"

drill_fill "B region"   2026-06-23 2026-06-16 "g.region" "$GEO"
drill_fill "B country"  2026-06-23 2026-06-16 "g.country" "$GEO"
drill_fill "B category" 2026-06-23 2026-06-16 "a.category" "$APP"
drill_fill "B tier"     2026-06-23 2026-06-16 "a.publisher_tier" "$APP"
drill_fill "B format"   2026-06-23 2026-06-16 "e.ad_format" ""
drill_fill "B device"   2026-06-23 2026-06-16 "g.device_model" "$GEO"
drill_fill "B OS"       2026-06-23 2026-06-16 "g.os_version" "$GEO"
drill_fill "B vertical (filled)" 2026-06-23 2026-06-16 "adv.vertical" "$ADV" "e.has_advertiser=1"
drill_fill "B campaign (filled)" 2026-06-23 2026-06-16 "adv.campaign_type" "$ADV" "e.has_advertiser=1"

# Deep: Android 15 crossed with region / format / category / device
drill_fill "B deep Android15 x region" 2026-06-23 2026-06-16 "g.region" "$GEO" "g.os_version='Android 15'"
drill_fill "B deep Android15 x country" 2026-06-23 2026-06-16 "g.country" "$GEO" "g.os_version='Android 15'"
drill_fill "B deep Android15 x format" 2026-06-23 2026-06-16 "e.ad_format" "$GEO" "g.os_version='Android 15'"
drill_fill "B deep Android15 x category" 2026-06-23 2026-06-16 "a.category" "$APP LEFT JOIN eda.geo_device AS g ON e.geo_device_id=g.geo_device_id" "g.os_version='Android 15'"
drill_fill "B deep Android15 x device" 2026-06-23 2026-06-16 "g.device_model" "$GEO" "g.os_version='Android 15'"
drill_fill "B deep Android15 x tier" 2026-06-23 2026-06-16 "a.publisher_tier" "$APP LEFT JOIN eda.geo_device AS g ON e.geo_device_id=g.geo_device_id" "g.os_version='Android 15'"

# Non-Android15 residual?
run "B fill Android15 vs rest" "
SELECT
  if(g.os_version='Android 15','Android 15','other') AS seg,
  countIf(e.event_date=toDate('2026-06-23')) AS req_t,
  sumIf(e.is_filled,e.event_date=toDate('2026-06-23'))/countIf(e.event_date=toDate('2026-06-23')) AS fill_t,
  sumIf(e.is_filled,e.event_date=toDate('2026-06-16'))/countIf(e.event_date=toDate('2026-06-16')) AS fill_b,
  fill_t-fill_b AS fill_chg
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE e.event_date IN (toDate('2026-06-23'), toDate('2026-06-16'))
GROUP BY seg
FORMAT PrettyCompact
"

# Multi-day fill crash persistence
run "B Android15 fill Jun 22-26" "
SELECT
  e.event_date AS day,
  count() AS req,
  sum(e.is_filled)/count() AS fill_rt,
  sum(e.revenue) AS rev
FROM eda.ad_events e
LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
WHERE g.os_version='Android 15' AND e.event_date BETWEEN toDate('2026-06-20') AND toDate('2026-06-28')
GROUP BY day
ORDER BY day
FORMAT PrettyCompact
"

echo "################ INCIDENT C: 2026-06-19 eCPM vs 2026-06-12" | tee -a "$OUT"
run "C factor snapshot" "
SELECT
  t.event_date AS day, t.requests, b.requests AS base_req,
  t.fills/t.requests AS fill_t, b.fills/b.requests AS fill_b,
  t.revenue/t.impressions*1000 AS ecpm_t, b.revenue/b.impressions*1000 AS ecpm_b,
  (t.revenue/t.impressions*1000)-(b.revenue/b.impressions*1000) AS ecpm_chg,
  t.revenue AS rev, b.revenue AS base_rev, (t.revenue-b.revenue)/b.revenue AS rev_chg
FROM eda.v_daily_metrics t
INNER JOIN eda.v_daily_metrics b ON b.event_date = toDate('2026-06-12')
WHERE t.event_date = toDate('2026-06-19')
FORMAT PrettyCompact
"

drill_ecpm "C region"   2026-06-19 2026-06-12 "g.region" "$GEO"
drill_ecpm "C country"  2026-06-19 2026-06-12 "g.country" "$GEO"
drill_ecpm "C category" 2026-06-19 2026-06-12 "a.category" "$APP"
drill_ecpm "C tier"     2026-06-19 2026-06-12 "a.publisher_tier" "$APP"
drill_ecpm "C format"   2026-06-19 2026-06-12 "e.ad_format" ""
drill_ecpm "C device"   2026-06-19 2026-06-12 "g.device_model" "$GEO"
drill_ecpm "C OS"       2026-06-19 2026-06-12 "g.os_version" "$GEO"
drill_ecpm "C vertical (filled)" 2026-06-19 2026-06-12 "adv.vertical" "$ADV" "e.has_advertiser=1"
drill_ecpm "C campaign (filled)" 2026-06-19 2026-06-12 "adv.campaign_type" "$ADV" "e.has_advertiser=1"

# Deep on interstitial (worst format)
drill_ecpm "C deep interstitial x region" 2026-06-19 2026-06-12 "g.region" "$GEO" "e.ad_format='interstitial'"
drill_ecpm "C deep interstitial x country" 2026-06-19 2026-06-12 "g.country" "$GEO" "e.ad_format='interstitial'"
drill_ecpm "C deep interstitial x device" 2026-06-19 2026-06-12 "g.device_model" "$GEO" "e.ad_format='interstitial'"
drill_ecpm "C deep interstitial x OS" 2026-06-19 2026-06-12 "g.os_version" "$GEO" "e.ad_format='interstitial'"
drill_ecpm "C deep interstitial x category" 2026-06-19 2026-06-12 "a.category" "$APP" "e.ad_format='interstitial'"
drill_ecpm "C deep interstitial x vertical" 2026-06-19 2026-06-12 "adv.vertical" "$ADV" "e.ad_format='interstitial' AND e.has_advertiser=1"

# eCPM persistence window
run "C daily eCPM Jun 12-26" "
SELECT event_date, revenue/impressions*1000 AS ecpm, fills/requests AS fill_rt, requests, revenue
FROM eda.v_daily_metrics
WHERE event_date BETWEEN toDate('2026-06-12') AND toDate('2026-06-26')
ORDER BY event_date
FORMAT PrettyCompact
"

echo "Wrote $OUT"
