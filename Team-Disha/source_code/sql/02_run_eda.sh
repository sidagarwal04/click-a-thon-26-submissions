#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/.env"
HOST=$(grep -E '^CLICKHOUSE_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
USER=$(grep -E '^CLICKHOUSE_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
PASS=$(grep -E '^CLICKHOUSE_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
URL="https://${HOST}:8443/"
OUT="/mnt/f/Clickhouse hackathon/click-a-thon-2026/Clickathon/docs/eda_raw.txt"
mkdir -p "$(dirname "$OUT")"
: > "$OUT"

run() {
  local title="$1"
  local sql="$2"
  {
    echo
    echo "===== $title ====="
    curl -sS --fail-with-body -u "${USER}:${PASS}" \
      --get "$URL" \
      --data-urlencode "query=${sql}"
    echo
  } | tee -a "$OUT"
}

run "GLOBAL FUNNEL" "SELECT count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions, sum(is_click) AS clicks, sum(revenue) AS rev, sum(is_filled)/count() AS fill_rt, sum(is_impression)/sum(is_filled) AS render_rt, sum(is_click)/sum(is_impression) AS ctr, sum(revenue)/sum(is_impression)*1000 AS ecpm, sum(revenue)/count() AS rpr, avg(has_advertiser) AS adv_share FROM eda.ad_events FORMAT PrettyCompact"

run "FUNNEL CONSISTENCY" "SELECT countIf(is_impression > is_filled) AS imp_gt_fill, countIf(is_click > is_impression) AS click_gt_imp, countIf(revenue > 0 AND is_impression = 0) AS rev_without_imp, countIf(is_filled = 1 AND has_advertiser = 0) AS filled_no_adv, countIf(is_filled = 0 AND has_advertiser = 1) AS unfilled_with_adv FROM eda.ad_events FORMAT PrettyCompact"

run "AD FORMAT" "SELECT ad_format, count() AS requests, sum(is_filled)/count() AS fill_rt, sum(revenue) AS rev, sum(revenue)/sum(is_impression)*1000 AS ecpm FROM eda.ad_events GROUP BY ad_format ORDER BY requests DESC FORMAT PrettyCompact"

run "REGION" "SELECT g.region AS region, count() AS requests, sum(e.is_filled)/count() AS fill_rt, sum(e.revenue) AS rev, sum(e.revenue)/sum(e.is_impression)*1000 AS ecpm FROM eda.ad_events AS e LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id GROUP BY region ORDER BY rev DESC FORMAT PrettyCompact"

run "APP CATEGORY" "SELECT a.category AS category, count() AS requests, sum(e.is_filled)/count() AS fill_rt, sum(e.revenue) AS rev FROM eda.ad_events AS e LEFT JOIN eda.apps AS a ON e.app_id = a.app_id GROUP BY category ORDER BY requests DESC FORMAT PrettyCompact"

run "PUBLISHER TIER" "SELECT a.publisher_tier AS publisher_tier, count() AS requests, sum(e.is_filled)/count() AS fill_rt, sum(e.revenue) AS rev, sum(e.revenue)/sum(e.is_impression)*1000 AS ecpm FROM eda.ad_events AS e LEFT JOIN eda.apps AS a ON e.app_id = a.app_id GROUP BY publisher_tier ORDER BY publisher_tier FORMAT PrettyCompact"

run "ADVERTISER VERTICAL" "SELECT adv.vertical AS vertical, count() AS fills, sum(e.revenue) AS rev, sum(e.revenue)/sum(e.is_impression)*1000 AS ecpm FROM eda.ad_events AS e INNER JOIN eda.advertisers AS adv ON e.advertiser_id = adv.advertiser_id WHERE e.has_advertiser = 1 GROUP BY vertical ORDER BY rev DESC FORMAT PrettyCompact"

run "CAMPAIGN TYPE" "SELECT adv.campaign_type AS campaign_type, count() AS fills, sum(e.revenue) AS rev, sum(e.is_click)/sum(e.is_impression) AS ctr FROM eda.ad_events AS e INNER JOIN eda.advertisers AS adv ON e.advertiser_id = adv.advertiser_id WHERE e.has_advertiser = 1 GROUP BY campaign_type ORDER BY fills DESC FORMAT PrettyCompact"

run "TOP DEVICES" "SELECT g.device_model AS device_model, count() AS requests, sum(e.is_filled)/count() AS fill_rt, sum(e.revenue) AS rev FROM eda.ad_events AS e LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id GROUP BY device_model ORDER BY requests DESC LIMIT 15 FORMAT PrettyCompact"

run "OS VERSION" "SELECT g.os_version AS os_version, count() AS requests, sum(e.is_filled)/count() AS fill_rt, sum(e.revenue) AS rev FROM eda.ad_events AS e LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id GROUP BY os_version ORDER BY requests DESC FORMAT PrettyCompact"

run "WEEKEND" "SELECT is_weekend, count() AS requests, sum(is_filled)/count() AS fill_rt, sum(revenue) AS rev, sum(revenue)/count() AS rpr FROM eda.ad_events GROUP BY is_weekend FORMAT PrettyCompact"

run "DOW" "SELECT event_dow, count() AS requests, sum(is_filled)/count() AS fill_rt, sum(revenue) AS rev FROM eda.ad_events GROUP BY event_dow ORDER BY event_dow FORMAT PrettyCompact"

run "HOUR" "SELECT event_hour, count() AS requests, sum(is_filled)/count() AS fill_rt, sum(revenue) AS rev FROM eda.ad_events GROUP BY event_hour ORDER BY event_hour FORMAT PrettyCompact"

run "DAILY SERIES" "SELECT event_date, event_dow, is_weekend, requests, revenue AS rev, fill_rate AS fill_rt, ctr, ecpm, rpr FROM eda.v_daily_metrics ORDER BY event_date FORMAT PrettyCompact"

run "CARDINALITY" "SELECT uniqExact(app_id) AS apps, uniqExact(geo_device_id) AS geos, uniqExact(advertiser_id) AS advertisers, uniqExact(ad_format) AS formats FROM eda.ad_events FORMAT PrettyCompact"

run "REVENUE QUANTILES" "SELECT quantile(0.5)(revenue) AS p50, quantile(0.9)(revenue) AS p90, quantile(0.99)(revenue) AS p99, max(revenue) AS max_rev, countIf(revenue = 0) AS zero_rev FROM eda.ad_events WHERE is_impression = 1 FORMAT PrettyCompact"

run "COUNTRY TOP 12" "SELECT g.country AS country, count() AS requests, sum(e.is_filled)/count() AS fill_rt, sum(e.revenue) AS rev FROM eda.ad_events AS e LEFT JOIN eda.geo_device AS g ON e.geo_device_id = g.geo_device_id GROUP BY country ORDER BY rev DESC LIMIT 12 FORMAT PrettyCompact"

echo "Wrote $OUT"
