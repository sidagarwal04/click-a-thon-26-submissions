#!/usr/bin/env bash
# Exhaustive EDA: hunt for patterns beyond the three known incidents.
# Read-only on eda.*
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"
OUT="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/docs/eda_exhaustive.txt"
: > "$OUT"

run() {
  local title="$1"; local sql="$2"
  { echo; echo "===== $title ====="; curl -sS --fail-with-body -u "${USER}:${PASS}" --get "$URL" --data-urlencode "query=${sql}"; echo; } | tee -a "$OUT"
}

# ---------------------------------------------------------------------------
# 1) Full global wow: all funnel metrics + spikes
# ---------------------------------------------------------------------------
run "1 FULL WOW ALL METRICS (all days vs -7)" "
WITH daily AS (
  SELECT event_date, event_dow,
    sum(requests) AS requests, sum(fills) AS fills,
    sum(impressions) AS impressions, sum(clicks) AS clicks, sum(revenue) AS revenue
  FROM eda.metrics_hourly GROUP BY event_date, event_dow
)
SELECT
  t.event_date AS day, t.event_dow AS dow,
  round((t.requests - b.requests) / b.requests, 4) AS req_chg,
  round((t.revenue - b.revenue) / b.revenue, 4) AS rev_chg,
  round(t.fills/t.requests - b.fills/b.requests, 4) AS fill_chg,
  round(t.impressions/t.fills - b.impressions/b.fills, 4) AS render_chg,
  round(t.clicks/t.impressions - b.clicks/b.impressions, 4) AS ctr_chg,
  round(t.revenue/t.impressions*1000 - b.revenue/b.impressions*1000, 4) AS ecpm_chg,
  round(t.revenue/t.requests - b.revenue/b.requests, 6) AS rpr_chg
FROM daily t INNER JOIN daily b ON b.event_date = t.event_date - 7
ORDER BY t.event_date
FORMAT PrettyCompact
"

run "1b TOP |rev_chg| days" "
WITH daily AS (
  SELECT event_date, sum(requests) AS requests, sum(fills) AS fills,
    sum(impressions) AS impressions, sum(clicks) AS clicks, sum(revenue) AS revenue
  FROM eda.metrics_hourly GROUP BY event_date
)
SELECT t.event_date AS day,
  round((t.revenue-b.revenue)/b.revenue,4) AS rev_chg,
  round((t.requests-b.requests)/b.requests,4) AS req_chg,
  round(t.fills/t.requests - b.fills/b.requests,4) AS fill_chg,
  round(t.revenue/t.impressions*1000 - b.revenue/b.impressions*1000,4) AS ecpm_chg,
  round(t.clicks/t.impressions - b.clicks/b.impressions,5) AS ctr_chg,
  round(t.impressions/t.fills - b.impressions/b.fills,5) AS render_chg
FROM daily t INNER JOIN daily b ON b.event_date = t.event_date - 7
ORDER BY abs((t.revenue-b.revenue)/b.revenue) DESC
LIMIT 15
FORMAT PrettyCompact
"

run "1c TOP |ctr_chg| / |render_chg| days" "
WITH daily AS (
  SELECT event_date, sum(fills) AS fills, sum(impressions) AS impressions, sum(clicks) AS clicks
  FROM eda.metrics_hourly GROUP BY event_date
)
SELECT t.event_date AS day,
  round(t.clicks/t.impressions,5) AS ctr_t,
  round(b.clicks/b.impressions,5) AS ctr_b,
  round(t.clicks/t.impressions - b.clicks/b.impressions,5) AS ctr_chg,
  round(t.impressions/t.fills,5) AS render_t,
  round(b.impressions/b.fills,5) AS render_b,
  round(t.impressions/t.fills - b.impressions/b.fills,5) AS render_chg
FROM daily t INNER JOIN daily b ON b.event_date = t.event_date - 7
ORDER BY greatest(abs(t.clicks/t.impressions - b.clicks/b.impressions), abs(t.impressions/t.fills - b.impressions/b.fills)) DESC
LIMIT 12
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 2) Hidden segment anomalies: global quiet but segment loud
# ---------------------------------------------------------------------------
run "2 HIDDEN: OS fill wow outliers (min 5k req)" "
WITH d AS (
  SELECT e.event_date, g.os_version AS dim,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e
  LEFT JOIN eda.geo_device g ON e.geo_device_id = g.geo_device_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  t.req AS req_t, b.req AS req_b,
  round(t.fills/t.req - b.fills/b.req, 4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000, 4) AS ecpm_chg,
  round((t.req-b.req)/b.req, 4) AS req_chg,
  round(t.rev - b.rev, 2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.req > 5000 AND b.req > 5000
ORDER BY abs(t.fills/t.req - b.fills/b.req) DESC
LIMIT 20
FORMAT PrettyCompact
"

run "2b HIDDEN: format eCPM wow outliers" "
WITH d AS (
  SELECT event_date, ad_format AS dim,
    count() AS req, sum(is_filled) AS fills, sum(revenue) AS rev, sum(is_impression) AS imp
  FROM eda.ad_events GROUP BY event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round(t.rev/t.imp*1000,3) AS ecpm_t, round(b.rev/b.imp*1000,3) AS ecpm_b,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev - b.rev, 2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.imp > 5000 AND b.imp > 5000
ORDER BY abs(t.rev/t.imp*1000 - b.rev/b.imp*1000) DESC
LIMIT 20
FORMAT PrettyCompact
"

run "2c HIDDEN: region fill+eCPM wow outliers" "
WITH d AS (
  SELECT e.event_date, g.region AS dim,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.req > 10000
ORDER BY greatest(abs(t.fills/t.req-b.fills/b.req)*100, abs(t.rev/t.imp*1000-b.rev/b.imp*1000)*10) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "2d HIDDEN: country outliers (fill or eCPM or req)" "
WITH d AS (
  SELECT e.event_date, g.country AS dim,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev, t.req
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.req > 3000 AND b.req > 3000
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "2e HIDDEN: category outliers" "
WITH d AS (
  SELECT e.event_date, a.category AS dim,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e LEFT JOIN eda.apps a ON e.app_id=a.app_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.req > 5000
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "2f HIDDEN: tier outliers" "
WITH d AS (
  SELECT e.event_date, a.publisher_tier AS dim,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e LEFT JOIN eda.apps a ON e.app_id=a.app_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 20
FORMAT PrettyCompact
"

run "2g HIDDEN: device_model outliers (min 2k)" "
WITH d AS (
  SELECT e.event_date, g.device_model AS dim,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, dim
)
SELECT t.event_date AS day, t.dim,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev, t.req
FROM d t INNER JOIN d b ON b.dim=t.dim AND b.event_date=t.event_date-7
WHERE t.req > 2000 AND b.req > 2000
ORDER BY abs(t.fills/t.req - b.fills/b.req) DESC
LIMIT 20
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 3) Mix shifts (share of traffic changing without rate change)
# ---------------------------------------------------------------------------
run "3b MIX: largest OS share deltas wow" "
WITH d AS (
  SELECT e.event_date, g.os_version AS dim, count() AS req
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, dim
), s AS (
  SELECT event_date, dim, req, req/sum(req) OVER (PARTITION BY event_date) AS share FROM d
)
SELECT t.event_date AS day, t.dim,
  round(t.share,4) AS share_t, round(b.share,4) AS share_b,
  round(t.share - b.share,4) AS share_chg
FROM s t INNER JOIN s b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.share - b.share) DESC
LIMIT 20
FORMAT PrettyCompact
"

run "3c MIX: format share deltas wow" "
WITH d AS (
  SELECT event_date, ad_format AS dim, count() AS req FROM eda.ad_events GROUP BY event_date, dim
), s AS (
  SELECT event_date, dim, req, req/sum(req) OVER (PARTITION BY event_date) AS share FROM d
)
SELECT t.event_date AS day, t.dim,
  round(t.share,4) AS share_t, round(b.share,4) AS share_b,
  round(t.share - b.share,4) AS share_chg
FROM s t INNER JOIN s b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.share - b.share) DESC
LIMIT 15
FORMAT PrettyCompact
"

run "3d MIX: region share deltas wow" "
WITH d AS (
  SELECT e.event_date, g.region AS dim, count() AS req
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, dim
), s AS (
  SELECT event_date, dim, req, req/sum(req) OVER (PARTITION BY event_date) AS share FROM d
)
SELECT t.event_date AS day, t.dim,
  round(t.share,4) AS share_t, round(b.share,4) AS share_b,
  round(t.share - b.share,4) AS share_chg
FROM s t INNER JOIN s b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.share - b.share) DESC
LIMIT 15
FORMAT PrettyCompact
"

run "3e MIX: category share deltas wow" "
WITH d AS (
  SELECT e.event_date, a.category AS dim, count() AS req
  FROM eda.ad_events e LEFT JOIN eda.apps a ON e.app_id=a.app_id
  GROUP BY e.event_date, dim
), s AS (
  SELECT event_date, dim, req, req/sum(req) OVER (PARTITION BY event_date) AS share FROM d
)
SELECT t.event_date AS day, t.dim,
  round(t.share,4) AS share_t, round(b.share,4) AS share_b,
  round(t.share - b.share,4) AS share_chg
FROM s t INNER JOIN s b ON b.dim=t.dim AND b.event_date=t.event_date-7
ORDER BY abs(t.share - b.share) DESC
LIMIT 15
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 4) App-level & advertiser tails
# ---------------------------------------------------------------------------
run "4 TOP apps by |d_rev| wow (any day, min 200 req)" "
WITH d AS (
  SELECT event_date, app_id,
    count() AS req, sum(is_filled) AS fills, sum(revenue) AS rev, sum(is_impression) AS imp
  FROM eda.ad_events GROUP BY event_date, app_id
)
SELECT t.event_date AS day, t.app_id,
  a.category, a.publisher_tier,
  t.req, round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/nullIf(t.imp,0)*1000 - b.rev/nullIf(b.imp,0)*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,3) AS d_rev
FROM d t
INNER JOIN d b ON b.app_id=t.app_id AND b.event_date=t.event_date-7
LEFT JOIN eda.apps a ON a.app_id=t.app_id
WHERE t.req > 200 AND b.req > 200
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "4b TOP advertisers by |d_rev| wow (filled)" "
WITH d AS (
  SELECT event_date, advertiser_id,
    count() AS fills, sum(revenue) AS rev, sum(is_impression) AS imp, sum(is_click) AS clicks
  FROM eda.ad_events WHERE has_advertiser=1
  GROUP BY event_date, advertiser_id
)
SELECT t.event_date AS day, t.advertiser_id,
  adv.vertical, adv.campaign_type,
  t.fills, round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.clicks/t.imp - b.clicks/b.imp,5) AS ctr_chg,
  round(t.rev - b.rev,3) AS d_rev
FROM d t
INNER JOIN d b ON b.advertiser_id=t.advertiser_id AND b.event_date=t.event_date-7
LEFT JOIN eda.advertisers adv ON adv.advertiser_id=t.advertiser_id
WHERE t.fills > 100 AND b.fills > 100
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "4c HHI concentration: daily advertiser revenue HHI" "
SELECT event_date,
  round(sum(share*share), 4) AS hhi,
  uniqExact(advertiser_id) AS n_adv
FROM (
  SELECT event_date, advertiser_id,
    sum(revenue)/sum(sum(revenue)) OVER (PARTITION BY event_date) AS share
  FROM eda.ad_events WHERE has_advertiser=1
  GROUP BY event_date, advertiser_id
)
GROUP BY event_date
ORDER BY event_date
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 5) Hourly anomalies within days (intra-day shocks)
# ---------------------------------------------------------------------------
run "5 HOURLY: worst hour vs same DOW-hour -7 (abs d_rev)" "
WITH h AS (
  SELECT event_date, event_hour, event_dow,
    sum(requests) AS req, sum(fills) AS fills, sum(impressions) AS imp, sum(revenue) AS rev
  FROM eda.metrics_hourly GROUP BY event_date, event_hour, event_dow
)
SELECT t.event_date AS day, t.event_hour AS hr,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,3) AS d_rev
FROM h t INNER JOIN h b ON b.event_hour=t.event_hour AND b.event_date=t.event_date-7
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 30
FORMAT PrettyCompact
"

run "5b HOURLY: days with uneven hour impact (std of hourly req_chg)" "
WITH h AS (
  SELECT event_date, event_hour, sum(requests) AS req FROM eda.metrics_hourly GROUP BY event_date, event_hour
), w AS (
  SELECT t.event_date AS day,
    (t.req - b.req) / b.req AS req_chg
  FROM h t INNER JOIN h b ON b.event_hour=t.event_hour AND b.event_date=t.event_date-7
)
SELECT day, round(avg(req_chg),4) AS avg_req_chg, round(stddevSamp(req_chg),4) AS std_req_chg,
  round(min(req_chg),4) AS min_chg, round(max(req_chg),4) AS max_chg
FROM w GROUP BY day
ORDER BY std_req_chg DESC
LIMIT 15
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 6) Multi-factor / overlapping windows
# ---------------------------------------------------------------------------
run "6 OVERLAP: factor flags per day (thresholds)" "
WITH daily AS (
  SELECT event_date,
    sum(requests) AS req, sum(fills) AS fills, sum(impressions) AS imp, sum(revenue) AS rev
  FROM eda.metrics_hourly GROUP BY event_date
)
SELECT t.event_date AS day,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round((t.rev-b.rev)/b.rev,4) AS rev_chg,
  if(abs((t.req-b.req)/b.req) >= 0.15, 1, 0) AS flag_vol,
  if(abs(t.fills/t.req - b.fills/b.req) >= 0.015, 1, 0) AS flag_fill,
  if(abs(t.rev/t.imp*1000 - b.rev/b.imp*1000) >= 0.04, 1, 0) AS flag_ecpm,
  flag_vol + flag_fill + flag_ecpm AS n_flags
FROM daily t INNER JOIN daily b ON b.event_date=t.event_date-7
ORDER BY n_flags DESC, abs((t.rev-b.rev)/b.rev) DESC
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 7) Positive spikes & recoveries
# ---------------------------------------------------------------------------
run "7 SPIKES: largest positive rev_chg / fill / ecpm" "
WITH daily AS (
  SELECT event_date, sum(requests) AS req, sum(fills) AS fills,
    sum(impressions) AS imp, sum(revenue) AS rev FROM eda.metrics_hourly GROUP BY event_date
)
SELECT t.event_date AS day,
  round((t.rev-b.rev)/b.rev,4) AS rev_chg,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg
FROM daily t INNER JOIN daily b ON b.event_date=t.event_date-7
ORDER BY (t.rev-b.rev)/b.rev DESC
LIMIT 12
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 8) Combo heat: format x region daily eCPM wow outside known windows
# ---------------------------------------------------------------------------
run "8 COMBO: format x region top |d_rev| any day" "
WITH d AS (
  SELECT e.event_date, e.ad_format, g.region,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev, sum(e.is_impression) AS imp
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, e.ad_format, g.region
)
SELECT t.event_date AS day, t.ad_format, t.region,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.ad_format=t.ad_format AND b.region=t.region AND b.event_date=t.event_date-7
WHERE t.imp > 1000 AND b.imp > 1000
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 30
FORMAT PrettyCompact
"

run "8b COMBO: OS x region fill outliers" "
WITH d AS (
  SELECT e.event_date, g.os_version, g.region,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev
  FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id
  GROUP BY e.event_date, g.os_version, g.region
)
SELECT t.event_date AS day, t.os_version, t.region,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev - b.rev,2) AS d_rev, t.req
FROM d t INNER JOIN d b ON b.os_version=t.os_version AND b.region=t.region AND b.event_date=t.event_date-7
WHERE t.req > 1000 AND b.req > 1000
ORDER BY abs(t.fills/t.req - b.fills/b.req) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "8c COMBO: format x category eCPM outliers" "
WITH d AS (
  SELECT e.event_date, e.ad_format, a.category,
    count() AS req, sum(e.revenue) AS rev, sum(e.is_impression) AS imp, sum(e.is_filled) AS fills
  FROM eda.ad_events e LEFT JOIN eda.apps a ON e.app_id=a.app_id
  GROUP BY e.event_date, e.ad_format, a.category
)
SELECT t.event_date AS day, t.ad_format, t.category,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg,
  round(t.rev - b.rev,2) AS d_rev
FROM d t INNER JOIN d b ON b.ad_format=t.ad_format AND b.category=t.category AND b.event_date=t.event_date-7
WHERE t.imp > 800 AND b.imp > 800
ORDER BY abs(t.rev - b.rev) DESC
LIMIT 25
FORMAT PrettyCompact
"

run "8d COMBO: tier x format fill outliers" "
WITH d AS (
  SELECT e.event_date, a.publisher_tier AS tier, e.ad_format,
    count() AS req, sum(e.is_filled) AS fills, sum(e.revenue) AS rev
  FROM eda.ad_events e LEFT JOIN eda.apps a ON e.app_id=a.app_id
  GROUP BY e.event_date, tier, e.ad_format
)
SELECT t.event_date AS day, t.tier, t.ad_format,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev - b.rev,2) AS d_rev, t.req
FROM d t INNER JOIN d b ON b.tier=t.tier AND b.ad_format=t.ad_format AND b.event_date=t.event_date-7
WHERE t.req > 2000
ORDER BY abs(t.fills/t.req - b.fills/b.req) DESC
LIMIT 20
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 9) Quiet-day noise floor (for threshold calibration)
# ---------------------------------------------------------------------------
run "9 NOISE: exclude known incident windows — remaining wow distribution" "
WITH daily AS (
  SELECT event_date, sum(requests) AS req, sum(fills) AS fills,
    sum(impressions) AS imp, sum(revenue) AS rev FROM eda.metrics_hourly GROUP BY event_date
), w AS (
  SELECT t.event_date AS day,
    (t.rev-b.rev)/b.rev AS rev_chg,
    (t.req-b.req)/b.req AS req_chg,
    t.fills/t.req - b.fills/b.req AS fill_chg,
    t.rev/t.imp*1000 - b.rev/b.imp*1000 AS ecpm_chg
  FROM daily t INNER JOIN daily b ON b.event_date=t.event_date-7
  WHERE t.event_date NOT IN (
    toDate('2026-06-19'),toDate('2026-06-20'),toDate('2026-06-21'),toDate('2026-06-22'),
    toDate('2026-06-23'),toDate('2026-06-24'),toDate('2026-06-25'),
    toDate('2026-06-26'),toDate('2026-06-27'),toDate('2026-06-28'),toDate('2026-06-29'),
    toDate('2026-06-30'),toDate('2026-07-01'),toDate('2026-07-02')  -- recoveries vs crash baselines
  )
)
SELECT
  round(avg(abs(rev_chg)),5) AS mean_abs_rev,
  round(quantile(0.5)(abs(rev_chg)),5) AS p50_abs_rev,
  round(quantile(0.9)(abs(rev_chg)),5) AS p90_abs_rev,
  round(quantile(0.95)(abs(rev_chg)),5) AS p95_abs_rev,
  round(max(abs(rev_chg)),5) AS max_abs_rev,
  round(avg(abs(fill_chg)),5) AS mean_abs_fill,
  round(quantile(0.95)(abs(fill_chg)),5) AS p95_abs_fill,
  round(max(abs(fill_chg)),5) AS max_abs_fill,
  round(avg(abs(ecpm_chg)),5) AS mean_abs_ecpm,
  round(quantile(0.95)(abs(ecpm_chg)),5) AS p95_abs_ecpm,
  round(max(abs(ecpm_chg)),5) AS max_abs_ecpm,
  round(avg(abs(req_chg)),5) AS mean_abs_req,
  round(quantile(0.95)(abs(req_chg)),5) AS p95_abs_req,
  count() AS n_days
FROM w
FORMAT PrettyCompact
"

run "9b QUIET days list (remaining wow)" "
WITH daily AS (
  SELECT event_date, sum(requests) AS req, sum(fills) AS fills,
    sum(impressions) AS imp, sum(revenue) AS rev FROM eda.metrics_hourly GROUP BY event_date
)
SELECT t.event_date AS day,
  round((t.rev-b.rev)/b.rev,4) AS rev_chg,
  round((t.req-b.req)/b.req,4) AS req_chg,
  round(t.fills/t.req - b.fills/b.req,4) AS fill_chg,
  round(t.rev/t.imp*1000 - b.rev/b.imp*1000,4) AS ecpm_chg
FROM daily t INNER JOIN daily b ON b.event_date=t.event_date-7
WHERE t.event_date NOT IN (
  toDate('2026-06-19'),toDate('2026-06-20'),toDate('2026-06-21'),toDate('2026-06-22'),
  toDate('2026-06-23'),toDate('2026-06-24'),toDate('2026-06-25'),
  toDate('2026-06-26'),toDate('2026-06-27'),toDate('2026-06-28'),toDate('2026-06-29'),
  toDate('2026-06-30'),toDate('2026-07-01'),toDate('2026-07-02')
)
ORDER BY abs((t.rev-b.rev)/b.rev) DESC
FORMAT PrettyCompact
"

# ---------------------------------------------------------------------------
# 10) CTR / render by dim static + wow
# ---------------------------------------------------------------------------
run "10 CTR by format / region / campaign (static)" "
SELECT 'format' AS kind, ad_format AS dim,
  round(sum(is_click)/sum(is_impression),5) AS ctr,
  round(sum(is_impression)/sum(is_filled),5) AS render
FROM eda.ad_events GROUP BY dim
UNION ALL
SELECT 'region', g.region,
  round(sum(e.is_click)/sum(e.is_impression),5),
  round(sum(e.is_impression)/sum(e.is_filled),5)
FROM eda.ad_events e LEFT JOIN eda.geo_device g ON e.geo_device_id=g.geo_device_id GROUP BY g.region
UNION ALL
SELECT 'campaign', adv.campaign_type,
  round(sum(e.is_click)/sum(e.is_impression),5),
  round(sum(e.is_impression)/sum(e.is_filled),5)
FROM eda.ad_events e INNER JOIN eda.advertisers adv ON e.advertiser_id=adv.advertiser_id
WHERE e.has_advertiser=1 GROUP BY adv.campaign_type
ORDER BY kind, dim
FORMAT PrettyCompact
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

# ---------------------------------------------------------------------------
# 11) Gradual drift vs step: rolling 3-day fill/ecpm
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 12) Vertical / campaign wow (filled only) — any planted advertiser signal?
# ---------------------------------------------------------------------------
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

echo "Wrote $OUT"
echo done
