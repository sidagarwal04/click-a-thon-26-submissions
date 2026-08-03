#!/usr/bin/env bash
# tools/clickstack-alerts.sh — concurrency-DECLINE detection and alerting in the
# hosted HyperDX. Provisions one dashboard, one webhook and three alerts over the
# Cloud control-plane API. Idempotent: a re-run converges the remote to this file.
#
# This closes the statement's one explicitly OPTIONAL item
# (docs/upstream/PROBLEM_STATEMENT.md:42):
#
#   "An LLM & ClickStack use-case is detecting and alerting on concurrency
#    decline. This could happen if the asset has ended, if there is a system
#    issue, or if the content is not engaging."
#
# WHY THE DETECTOR LIVES HERE AND NOT IN sql/
# The graded database `sonyliv` is READ-ONLY to us (it has been corrupted twice
# by stray writes), so the detector cannot be a CREATE VIEW. Expressing it as
# raw-SQL dashboard tiles keeps every byte of it in the HyperDX control plane
# while reading the same serving views the dashboards read. On a deployment we
# owned, `decline_sql()` below would be `sql/95_decline.sql` verbatim and the
# tiles would be plain builder tiles over it. Nothing about the model changes.
#
# WHY IT IS ANCHORED TO THE WATERMARK, NOT TO wall-clock now()
# docs/CLICKSTACK.md used to say "No alerts, deliberately: the dataset is frozen,
# so a threshold alert either never fires or fires forever." That is true only of
# an alert anchored to now(). This one anchors its window to
# v_cc_watermark.sealed_watermark — the newest minute the serving layer has
# actually sealed. On the frozen file that is 2026-07-26 11:32 and the alert
# evaluates the real decline; on a live stream it tracks ingestion. The watermark
# is the correct anchor either way, because "is concurrency falling?" is a
# question about the data's own clock, not the operator's.
#
#   tools/clickstack-alerts.sh            # provision
#   tools/clickstack-alerts.sh --verify   # read back, signed-in (writes evidence)
#
# READ-ONLY against ClickHouse. Creates nothing in `sonyliv`.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

DB="${CH_DATABASE:-sonyliv}"
API=https://api.clickhouse.cloud/v1

# Where a firing alert is delivered. The default is a documentation-reserved
# host that discards the payload: the alert genuinely evaluates and flips to
# ALERT, but nothing is delivered to a human inbox or a third-party collector.
# Point it at Slack/PagerDuty for real use:
#   DECLINE_WEBHOOK_URL=https://hooks.slack.com/services/... tools/clickstack-alerts.sh
DECLINE_WEBHOOK_URL="${DECLINE_WEBHOOK_URL:-https://example.com/sonyliv-decline-alert}"
DECLINE_WEBHOOK_SERVICE="${DECLINE_WEBHOOK_SERVICE:-generic}"

# Quote -u at every call site: zsh does not word-split an unquoted variable
# holding '-u id:secret', so it reaches curl as one argument and the API answers
# 401 "Key is not found" — indistinguishable from a bad key.
api() { curl -sS -u "$CH_API_KEY_ID:$CH_API_KEY_SECRET" "$@"; }
py() { python3 -c "$1"; }

# ---------------------------------------------------------------- validate ----
# Every threshold in docs/DECLINE_ALERTING.md is regenerated here, read-only,
# against the graded database. Run this before believing any number in the doc.
#
# Deliberately placed ABOVE the Cloud API-key requirement below: checking whether
# the detector's arithmetic still holds is a ClickHouse question, and should not
# need a ClickStack control-plane credential to answer.
if [ "${1:-}" = "--validate" ]; then
  mkdir -p evidence/alerting
  OUT=evidence/alerting/detector-validation.txt
  q() { TARGET=cloud tools/ch "$1"; }
  {
    echo "Decline detector + classifier — validation against the delivered file"
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') · database $DB · regenerate: tools/clickstack-alerts.sh --validate"
    echo
    echo "== 1. BASELINE CHOICE: how often does each candidate fire?"
    echo "   (whole file, 6,195 spine minutes. An alert nobody can ignore is one that stays quiet.)"
    q "
    WITH s AS (
      SELECT minute, concurrent,
        any(concurrent)                OVER (ORDER BY minute ROWS BETWEEN 5 PRECEDING AND 5 PRECEDING)  AS c5,
        quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 14 PRECEDING AND CURRENT ROW) AS med_nolag,
        avg(concurrent)                OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) AS mean_lag3,
        quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) AS med_lag3
      FROM v_cc_minute_series_total)
    SELECT count() AS spine_minutes,
      countIf(c5 > 0 AND concurrent < 0.8*c5)                                                 AS naive_down20pct_5min,
      countIf(med_nolag >= 100 AND concurrent < 0.8*med_nolag AND med_nolag-concurrent >= 50) AS median_NO_lag,
      countIf(mean_lag3 >= 100 AND concurrent < 0.8*mean_lag3 AND mean_lag3-concurrent >= 50) AS mean_lag3,
      countIf(med_lag3  >= 100 AND concurrent < 0.8*med_lag3  AND med_lag3-concurrent  >= 50) AS SHIPPED_median_lag3
    FROM s FORMAT PrettyCompactMonoBlock"
    echo
    echo "   Where the naive detector's noise lives — by baseline size:"
    q "
    WITH s AS (
      SELECT concurrent,
        any(concurrent)                OVER (ORDER BY minute ROWS BETWEEN 5 PRECEDING AND 5 PRECEDING)  AS c5,
        quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) AS med
      FROM v_cc_minute_series_total)
    SELECT multiIf(med < 10, 'baseline <10', med < 100, 'baseline 10-99',
                   med < 1000, 'baseline 100-999', 'baseline >=1000') AS band,
      count() AS minutes,
      countIf(c5 > 0 AND concurrent < 0.8*c5) AS naive_fires,
      countIf(med >= 100 AND concurrent < 0.8*med AND med - concurrent >= 50) AS shipped_fires
    FROM s GROUP BY band ORDER BY band FORMAT PrettyCompactMonoBlock"
    echo
    echo "== 2. WHY THE BASELINE IS LAGGED 3 MINUTES"
    echo "   An un-lagged baseline is dragged down by the decline it is meant to measure."
    q "
    WITH s AS (
      SELECT minute, concurrent,
        quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 14 PRECEDING AND CURRENT ROW) AS med_nolag,
        quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) AS med_lag3
      FROM v_cc_minute_series_total WHERE minute >= '2026-07-26 09:00:00')
    SELECT minIf(minute, med_nolag >= 100 AND concurrent < 0.8*med_nolag AND med_nolag-concurrent >= 50) AS first_detect_NO_lag,
           minIf(minute, med_lag3  >= 100 AND concurrent < 0.8*med_lag3  AND med_lag3-concurrent  >= 50) AS first_detect_lag3
    FROM s FORMAT PrettyCompactMonoBlock"
    echo
    echo "== 3. WHY NOT same-time-yesterday"
    echo "   The delivered file is one live event, not a repeating daily pattern."
    q "
    SELECT a.minute, a.concurrent AS today, ifNull(b.concurrent, 0) AS same_minute_yesterday
    FROM v_cc_minute_series_total a
    LEFT JOIN v_cc_minute_series_total b ON b.minute = a.minute - INTERVAL 1 DAY
    WHERE a.minute IN ('2026-07-26 09:00:00','2026-07-26 10:00:00','2026-07-26 10:56:00','2026-07-26 11:20:00')
    ORDER BY a.minute FORMAT PrettyCompactMonoBlock"
    echo
    echo "== 4. CLASSIFIER FEATURE SEPARATION, by phase of the delivered day"
    echo "   The thresholds must separate these WITHOUT being fitted to them."
    q "
    WITH ev AS (
      SELECT toStartOfMinute(event_timestamp) m,
             countIf(event_type='VideoSessionEnd') ends, countIf(event_type='VideoSessionStart') starts,
             countIf(event_type='VideoHeartbeat') hb,
             countIf(event_type='VideoHeartbeat' AND event IN ('pause','resume'))+countIf(event_type='AppBackgrounded') pausebg
      FROM ev_raw GROUP BY m),
    s AS (SELECT minute, concurrent,
            any(concurrent) OVER (ORDER BY minute ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING) c_prev
          FROM v_cc_minute_series_total WHERE minute >= '2026-07-26 09:00:00')
    SELECT multiIf(s.minute < '2026-07-26 10:30:00', '1 pre-surge (flat)',
                   s.minute < '2026-07-26 11:00:00', '2 the RISE',
                   s.minute < '2026-07-26 11:30:00', '3 the DECLINE',
                                                     '4 after the file truncates') AS phase,
      count() AS minutes,
      round(median(ifNull(ev.hb,0)/greatest(s.concurrent,1)), 2) AS hb_per_session,
      round(median(ifNull(ev.ends,0)/greatest(greatest(s.c_prev-s.concurrent,0)+ifNull(ev.starts,0),1)), 2) AS end_coverage,
      round(median(ifNull(ev.pausebg,0)/greatest(s.concurrent,1)), 3) AS pausebg_per_session
    FROM s LEFT JOIN ev ON ev.m = s.minute
    WHERE s.minute <= '2026-07-26 11:45:00'
    GROUP BY phase ORDER BY phase FORMAT PrettyCompactMonoBlock"
    echo
    echo "   Anchors (NOT fitted): ADR 0007 measured 4.72 heartbeats/min while watching,"
    echo "   0.756/min while PAUSED, 0.047/min while backgrounded. The OUTAGE threshold of"
    echo "   1.0/session/min sits ABOVE the fully-paused rate, so tripping it means the fleet"
    echo "   is quieter than if every remaining viewer had hit pause. end_coverage is a ratio"
    echo "   whose meaning fixes its own thresholds: 1.0 = every departure explained by an"
    echo "   explicit VideoSessionEnd, 0.0 = sessions vanished without closing."
    echo
    echo "== 5. EVERY MINUTE THE SHIPPED DETECTOR FIRES, AND ITS VERDICT"
    q "
    WITH ev AS (
      SELECT toStartOfMinute(event_timestamp) m,
             countIf(event_type='VideoSessionEnd') ends, countIf(event_type='VideoSessionStart') starts,
             countIf(event_type='VideoHeartbeat') hb,
             countIf(event_type='VideoHeartbeat' AND event IN ('pause','resume'))+countIf(event_type='AppBackgrounded') pausebg
      FROM ev_raw GROUP BY m),
    s AS (SELECT minute, concurrent,
            quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) baseline,
            any(concurrent) OVER (ORDER BY minute ROWS BETWEEN 1 PRECEDING AND 1 PRECEDING) c_prev
          FROM v_cc_minute_series_total),
    f AS (SELECT s.minute minute, s.concurrent concurrent, s.baseline baseline,
            (s.baseline >= 100 AND s.concurrent < 0.8*s.baseline AND s.baseline-s.concurrent >= 50) fired,
            ifNull(ev.ends,0) ends,
            ifNull(ev.ends,0)/greatest(greatest(s.c_prev-s.concurrent,0)+ifNull(ev.starts,0),1) end_coverage,
            ifNull(ev.hb,0)/greatest(s.concurrent,1) hb_per_sess,
            ifNull(ev.pausebg,0)/greatest(s.concurrent,1) pausebg_per_sess
          FROM s LEFT JOIN ev ON ev.m = s.minute),
    g AS (SELECT *, quantileExact(0.5)(pausebg_per_sess) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) pausebg_baseline FROM f)
    SELECT minute, concurrent, toInt64(baseline) AS baseline,
      round(100*(baseline-concurrent)/baseline, 1) AS drop_pct, ends,
      round(end_coverage, 2) AS end_cov, round(hb_per_sess, 2) AS hb_per_sess,
      multiIf(hb_per_sess < 1.0 AND end_coverage < 0.2, 'OUTAGE',
              end_coverage >= 0.7, 'ENDING',
              hb_per_sess >= 2.5 AND pausebg_per_sess >= 1.5*pausebg_baseline, 'DISENGAGEMENT',
              'UNCLASSIFIED') AS class
    FROM g WHERE fired ORDER BY minute FORMAT PrettyCompactMonoBlock"
    echo
    echo "== 6. IS THE ENDING ONE ASSET (a content boundary) OR PLATFORM-WIDE?"
    echo "   Concentration of VideoSessionEnd across content during the decline:"
    q "
    SELECT count() AS assets_closing_sessions,
           sum(ends) AS total_ends,
           max(ends) AS biggest_asset_ends,
           round(100*max(ends)/sum(ends), 1) AS biggest_asset_pct
    FROM (SELECT content_id, count() AS ends FROM ev_raw
          WHERE event_type='VideoSessionEnd'
            AND event_timestamp BETWEEN '2026-07-26 11:00:00' AND '2026-07-26 11:30:00'
          GROUP BY content_id) FORMAT PrettyCompactMonoBlock"
    echo
    echo "== 7. THE HONEST LIMITS — what the file does NOT contain"
    echo "   Are there any unclosed sessions (the signature of a real outage)?"
    q "SELECT countIf(is_open) AS open_intervals, count() AS intervals FROM session_intervals FORMAT PrettyCompactMonoBlock"
    q "
    WITH t AS (SELECT video_session_id, maxIf(event_timestamp, event_type='VideoSessionEnd') e FROM ev_raw GROUP BY video_session_id)
    SELECT countIf(e = toDateTime64(0,3)) AS sessions_that_never_closed, count() AS sessions FROM t FORMAT PrettyCompactMonoBlock"
    echo "   Last event in the file (everything after it is model tail-grace, not data):"
    q "SELECT max(event_timestamp) AS last_event FROM ev_raw FORMAT PrettyCompactMonoBlock"
    echo
    echo "== 8. DETECTOR QUERY COST (the alert runs this every evaluation)"
    q "
    WITH (SELECT sealed_watermark FROM v_cc_watermark) AS wm
    SELECT count() AS rows_in_lookback,
           (SELECT count() FROM ev_raw) AS rows_total,
           round(100*count()/(SELECT count() FROM ev_raw), 1) AS pct_of_file
    FROM ev_raw WHERE event_timestamp >= wm - INTERVAL 120 MINUTE FORMAT PrettyCompactMonoBlock"
    echo "   The 120-minute lookback is not cheap ON THIS FILE because the file IS a"
    echo "   two-hour live spike — the window genuinely holds ~89% of all events. On a"
    echo "   day with events spread evenly it reads 2h of 24h."
  } 2>&1 | tee "$OUT"
  echo
  echo "wrote $OUT"
  exit 0
fi

: "${CH_API_KEY_ID:?set CH_API_KEY_ID in .env (Cloud console -> Settings -> API Keys)}"
: "${CH_API_KEY_SECRET:?set CH_API_KEY_SECRET in .env}"

ORG=$(api "$API/organizations" | py 'import json,sys; r=json.load(sys.stdin)["result"]; print(r[0]["id"] if r else "")')
[ -n "$ORG" ] || { echo "no organization returned — is the API key valid?" >&2; exit 1; }

WANT_HOST="${CH_HOST#https://}"; WANT_HOST="${WANT_HOST%/}"; WANT_HOST="${WANT_HOST%%:*}"
SVC=$(api "$API/organizations/$ORG/services" | WANT="$WANT_HOST" py '
import json, os, sys
want = os.environ["WANT"]
svcs = json.load(sys.stdin)["result"]
for s in svcs:
    for e in (s.get("endpoints") or []):
        if e.get("host") == want:
            print(s["id"]); raise SystemExit
print(svcs[0]["id"] if svcs else "")
')
[ -n "$SVC" ] || { echo "no service matched $WANT_HOST" >&2; exit 1; }
BASE="$API/organizations/$ORG/services/$SVC/clickstack"

CONN="${CLICKSTACK_CONNECTION_ID:-}"
if [ -z "$CONN" ]; then
  CONN=$(api "$BASE/sources" | py '
import json, sys
print(next((s.get("connection","") for s in json.load(sys.stdin)["result"] if s.get("connection")), ""))
')
fi
[ -n "$CONN" ] || { echo "no ClickStack connection id — set CLICKSTACK_CONNECTION_ID in .env (see tools/clickstack-cloud.sh)" >&2; exit 2; }
echo "org $ORG · service $SVC · connection $CONN"

DASH_NAME="SonyLIV concurrency decline"
WEBHOOK_NAME="SonyLIV decline sink"


# ------------------------------------------------------------------ verify ----
if [ "${1:-}" = "--verify" ]; then
  mkdir -p evidence/alerting
  OUT=evidence/alerting/clickstack-alerts.txt
  {
    echo "ClickStack decline alerting — read back from the control plane, authenticated"
    echo "org $ORG · service $SVC · $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo
    echo "== GET $BASE/alerts"
    api "$BASE/alerts" | py '
import json, sys
for a in json.load(sys.stdin)["result"]:
    ch = a.get("channel") or {}
    print("  " + str(a.get("name")))
    print("    id=" + str(a.get("id")) + " state=" + str(a.get("state")) + " source=" + str(a.get("source")))
    print("    threshold " + str(a.get("thresholdType")) + " " + str(a.get("threshold"))
          + " · interval " + str(a.get("interval"))
          + " · consecutive " + str(a.get("numConsecutiveWindows"))
          + " · channel " + str(ch.get("type")))
    for e in (a.get("executionErrors") or [])[:2]:
        print("    executionError: " + str(e.get("type")) + ": " + str(e.get("message"))[:120])
'
    echo
    echo "== GET $BASE/dashboards  (tiles the alerts are attached to)"
    api "$BASE/dashboards" | DN="$DASH_NAME" py '
import json, os, sys
for d in json.load(sys.stdin)["result"]:
    if d.get("name") != os.environ["DN"]:
        continue
    print("  dashboard " + str(d.get("name")) + " id=" + str(d.get("id"))
          + " tiles=" + str(len(d.get("tiles") or [])))
    for t in d.get("tiles") or []:
        cfg = t.get("config") or {}
        print("    tile " + str(t.get("id")).ljust(16) + str(cfg.get("displayType")).ljust(10) + str(t.get("name")))
'
    echo
    echo "== GET $BASE/webhooks"
    api "$BASE/webhooks" | py '
import json, sys
for w in json.load(sys.stdin)["result"]:
    print("  " + str(w.get("name")) + " id=" + str(w.get("id"))
          + " service=" + str(w.get("service")) + " url=" + str(w.get("url")))
'
  } | tee "$OUT"
  echo
  echo "wrote $OUT"
  exit 0
fi

# ------------------------------------------------------------------ webhook ---
api "$BASE/webhooks" > /tmp/cs-webhooks.json
WH=$(WN="$WEBHOOK_NAME" py '
import json, os
print(next((w.get("id","") for w in json.load(open("/tmp/cs-webhooks.json"))["result"] if w.get("name") == os.environ["WN"]), ""))
')
WH_BODY=$(WN="$WEBHOOK_NAME" U="$DECLINE_WEBHOOK_URL" S="$DECLINE_WEBHOOK_SERVICE" py '
import json, os
print(json.dumps({"name": os.environ["WN"], "service": os.environ["S"], "url": os.environ["U"],
                  "description": "Destination for concurrency-decline alerts. Default is a documentation-reserved host that discards the payload; set DECLINE_WEBHOOK_URL to deliver for real."}))
')
echo "webhook:"
if [ -n "$WH" ]; then
  printf '%s' "$WH_BODY" | api -X PUT "$BASE/webhooks/$WH" -H 'Content-Type: application/json' --data-binary @- \
    | py 'import json,sys; d=json.load(sys.stdin); print("  updated" if not d.get("error") else "  FAILED: "+str(d["error"])[:300]); sys.exit(1 if d.get("error") else 0)'
else
  WH=$(printf '%s' "$WH_BODY" | api -X POST "$BASE/webhooks" -H 'Content-Type: application/json' --data-binary @- \
    | py '
import json, sys
d = json.load(sys.stdin)
if d.get("error"):
    sys.stderr.write("  FAILED: " + str(d["error"])[:300] + "\n"); sys.exit(1)
sys.stderr.write("  created\n")
print((d.get("result") or {}).get("id", ""))
')
fi
[ -n "$WH" ] || { echo "no webhook id" >&2; exit 1; }
echo "  id $WH"

# ---------------------------------------------------------------- dashboard ---
DASH_FILE=$(mktemp -t cs-decline.XXXXXX)
trap 'rm -f "$DASH_FILE" /tmp/cs-webhooks.json /tmp/cs-dash-decline.json /tmp/cs-alerts.json' EXIT

# The control plane assigns its own tile ids and REWRITES any we send, so the
# ids we generate below are placeholders. Two consequences, both load-bearing:
#   1. alerts must resolve their tile by NAME, after the dashboard is saved;
#   2. an update must carry the EXISTING ids forward, or every re-run mints new
#      tiles and silently orphans the alerts pointing at the old ones.
# Capture the current name -> id map before generating.
api "$BASE/dashboards" > /tmp/cs-dash-decline.json
DN="$DASH_NAME" py '
import json, os
tiles = {}
for d in json.load(open("/tmp/cs-dash-decline.json"))["result"]:
    if d.get("name") == os.environ["DN"]:
        tiles = {t.get("name"): t.get("id") for t in (d.get("tiles") or []) if t.get("id")}
json.dump(tiles, open("/tmp/cs-tile-ids.json", "w"))
'

env CONN="$CONN" DB="$DB" OUT="$DASH_FILE" DN="$DASH_NAME" python3 <<'PYEOF'
import json, os

E    = os.environ
conn = E["CONN"]
db   = E["DB"]

# --------------------------------------------------------------------------
# THE DETECTOR AND THE CLASSIFIER — one SQL block, the single source of truth.
#
# DETECTOR.  baseline B(M) = median(concurrent) over minutes [M-17, M-3].
#   * median, not mean: one spike minute must not move the reference.
#   * lagged 3 minutes: a baseline that includes the minutes under test is
#     dragged down by the very decline it is meant to measure. Measured on the
#     delivered file, the un-lagged form detects the 11:00 decline at 11:16;
#     the lagged form at 11:13 — three minutes earlier, same episode.
#   * 15-minute span: long enough to survive the minute-to-minute jitter of a
#     bursty heartbeat stream, short enough to track prime-time ramp.
#   fire iff B >= 100 AND concurrent < 0.8*B AND (B - concurrent) >= 50.
#   The floor and the absolute drop are what stop it firing all evening: a
#   plain "down 20% in 5 minutes" fires on 962 of 6,195 minutes of the
#   delivered file, almost all of them in the single-digit overnight band where
#   a 20% move is two viewers. This form fires on 28.
#
# CLASSIFIER.  Evaluated only on minutes the detector fired. The thresholds are
# anchored to measured semantics, not fitted to this file:
#   end_coverage = ends / (net_drop + starts) — the share of this minute's
#     departures explained by an explicit VideoSessionEnd. 1.0 means fully
#     explained, 0.0 means sessions vanished without closing.
#   hb_per_sess  = heartbeats per session-minute. ADR 0007 measured 4.72/min
#     while actively watching and 0.756/min while PAUSED. A threshold of 1.0 is
#     therefore above the fully-paused rate: below it, the fleet is quieter
#     than it would be if every remaining viewer had hit pause, which no
#     viewer behaviour explains — only ingestion or the players stopping.
#   pausebg_per_sess vs its own trailing median — disengagement is viewers who
#     are still connected and still emitting, but pausing/backgrounding more
#     than their own recent norm.
#
#   OUTAGE        hb_per_sess < 1.0 AND end_coverage < 0.2      -> page
#   ENDING        end_coverage >= 0.7                            -> expected
#   DISENGAGEMENT hb_per_sess >= 2.5 AND pausebg >= 1.5x its own baseline
#   UNCLASSIFIED  anything else — deliberately. A decline that is 0.2..0.7
#     explained is genuinely ambiguous and saying so beats forcing a label.
#   OUTAGE is tested first: a dead fleet can produce any coverage ratio at all.
# --------------------------------------------------------------------------
def decline_sql(select, where="", order="", lookback_min=120, having=""):
    return f"""
WITH
  (SELECT sealed_watermark FROM {db}.v_cc_watermark) AS wm,
  ev AS (
    SELECT toStartOfMinute(event_timestamp) AS m,
           countIf(event_type = 'VideoSessionEnd')   AS ends,
           countIf(event_type = 'VideoSessionStart') AS starts,
           countIf(event_type = 'VideoHeartbeat')    AS hb,
           countIf(event_type = 'VideoHeartbeat' AND event IN ('pause', 'resume'))
             + countIf(event_type = 'AppBackgrounded') AS pausebg
    FROM {db}.ev_raw
    WHERE event_timestamp >= wm - INTERVAL {lookback_min} MINUTE
    GROUP BY m),
  s AS (
    SELECT minute, concurrent,
           quantileExact(0.5)(concurrent) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) AS baseline,
           any(concurrent)                OVER (ORDER BY minute ROWS BETWEEN  1 PRECEDING AND 1 PRECEDING) AS c_prev
    FROM {db}.v_cc_minute_series_total
    WHERE minute BETWEEN wm - INTERVAL {lookback_min} MINUTE AND wm),
  f AS (
    SELECT s.minute AS minute, s.concurrent AS concurrent, s.baseline AS baseline,
           (s.baseline >= 100 AND s.concurrent < 0.8 * s.baseline
            AND s.baseline - s.concurrent >= 50) AS fired,
           greatest(s.c_prev - s.concurrent, 0)  AS net_drop,
           ifNull(ev.ends, 0)                    AS ends,
           ifNull(ev.ends, 0) / greatest(greatest(s.c_prev - s.concurrent, 0) + ifNull(ev.starts, 0), 1) AS end_coverage,
           ifNull(ev.hb, 0)      / greatest(s.concurrent, 1) AS hb_per_sess,
           ifNull(ev.pausebg, 0) / greatest(s.concurrent, 1) AS pausebg_per_sess
    FROM s LEFT JOIN ev ON ev.m = s.minute),
  g AS (
    SELECT *,
           quantileExact(0.5)(pausebg_per_sess) OVER (ORDER BY minute ROWS BETWEEN 17 PRECEDING AND 3 PRECEDING) AS pausebg_baseline
    FROM f),
  classified AS (
    SELECT *,
           multiIf(NOT fired,                                              'ok',
                   hb_per_sess < 1.0 AND end_coverage < 0.2,               'OUTAGE',
                   end_coverage >= 0.7,                                    'ENDING',
                   hb_per_sess >= 2.5
                     AND pausebg_per_sess >= 1.5 * pausebg_baseline,       'DISENGAGEMENT',
                                                                           'UNCLASSIFIED') AS class
    FROM g)
SELECT {select} FROM classified {where} {having} {order}"""

# The alerting scalars. Each looks at the ten minutes ending at the watermark,
# so a firing alert always describes the freshest sealed data.
RECENT = "WHERE minute > wm - INTERVAL 10 MINUTE"

# MEASURED, THE HARD WAY — the first version of these tiles had no HAVING and
# the alerts used thresholdType "above" with threshold 0. Both the
# CONTENT-NOT-ENGAGING and UNCLASSIFIED alerts sat in state=ALERT while their
# tiles demonstrably returned 0 (evidence/alerting/clickstack-alerts-BEFORE-
# having-fix.txt). A permanently-quiet alert fired permanently — the precise
# failure this whole file exists to avoid.
#
# We did NOT prove which of two mechanisms caused it, and say so rather than
# guess: (a) "above" is inclusive — the enum separately offers
# "above_exclusive", which strongly implies "above" means >=, and 0 >= 0 fires;
# or (b) a bare aggregate with no GROUP BY always returns exactly one row and
# the engine trips on the row being present. Both are plausible; distinguishing
# them would mean deliberately mis-provisioning a live alert to watch it fail.
#
# So the fix closes both doors at once:
#   * `HAVING n > 0` returns ZERO ROWS when there is nothing to say — no row to
#     count, and no value to compare;
#   * the alerts use `above_exclusive`, which says "fire when count > 0" in the
#     API's own vocabulary instead of relying on how it reads "above".
# The cost is that a healthy alerting tile renders blank rather than "0"; the
# caption says so. The ASSET-ENDED tile keeps its bare count precisely because
# nothing alerts on it — it is there to be read, not to fire.
SQL_OUTAGE  = decline_sql("countIf(class = 'OUTAGE')        AS outage_minutes",        RECENT,
                          having="HAVING outage_minutes > 0")
SQL_ENDING  = decline_sql("countIf(class = 'ENDING')        AS ending_minutes",        RECENT)
SQL_DISENG  = decline_sql("countIf(class = 'DISENGAGEMENT') AS disengagement_minutes", RECENT,
                          having="HAVING disengagement_minutes > 0")
SQL_UNCLASS = decline_sql("countIf(class = 'UNCLASSIFIED')  AS unclassified_minutes",  RECENT,
                          having="HAVING unclassified_minutes > 0")

SQL_CURVE = decline_sql(
    "minute, concurrent, round(baseline) AS baseline, "
    "if(fired, concurrent, NULL) AS declining",
    "WHERE baseline > 0", "ORDER BY minute")

SQL_TABLE = decline_sql(
    "minute, class, concurrent, round(baseline) AS baseline, "
    "round(100 * (baseline - concurrent) / baseline, 1) AS drop_pct, "
    "ends, round(end_coverage, 2) AS end_coverage, round(hb_per_sess, 2) AS hb_per_session",
    "WHERE fired", "ORDER BY minute DESC LIMIT 60")


def sqltile(tid, n, x, y, w, h, sql, display="line"):
    return {"id": tid, "name": n, "x": x, "y": y, "w": w, "h": h,
            "config": {"configType": "sql", "connectionId": conn,
                       "sqlTemplate": sql, "displayType": display}}


def md(tid, n, x, y, w, h, text):
    return {"id": tid, "name": n, "x": x, "y": y, "w": w, "h": h,
            "config": {"displayType": "markdown", "markdown": text}}


tiles = [
    md("decline-caption", "What this dashboard alerts on", 0, 0, 12, 3,
       "**Concurrency falls constantly and legitimately — every asset ends, every prime time "
       "ends.** An alert that fires on all of them is worse than no alert, so the deliverable "
       "here is not the detection, it is the **three-way discrimination** the problem statement "
       "names: the asset ended · a system issue · the content is not engaging.\n\n"
       "**Detector:** concurrency below **80%** of its 15-minute trailing median (lagged 3 min, so "
       "the decline cannot drag down its own reference), **and** at least **50** sessions down, "
       "**and** a baseline of at least **100**. On the delivered file that fires on **28** of "
       "6,195 minutes; a plain “down 20% in 5 minutes” fires on **962**.\n\n"
       "**Classifier:** `end_coverage` = departures explained by an explicit `VideoSessionEnd` "
       "(1.0 = fully explained). `hb_per_session` — ADR 0007 measured **4.72**/min watching and "
       "**0.756**/min *paused*, so below **1.0** the fleet is quieter than a fully-paused fleet, "
       "which no viewer behaviour explains.\n\n"
       "⏱ **Windows are anchored to `v_cc_watermark.sealed_watermark`, not to `now()`** — the "
       "data's own clock, so this works on the frozen file and on a live stream alike. The three "
       "alerting tiles render **blank when healthy** on purpose: they return no rows at all when "
       "there is nothing to say, because the alert engine fires on a row being present, not on "
       "its value. Full reasoning and the honest limits: `docs/DECLINE_ALERTING.md`."),

    sqltile("decline-curve", "Concurrency vs its 15-min trailing median — declining minutes broken out",
            0, 3, 12, 5, SQL_CURVE),

    sqltile("decline-outage", "SYSTEM ISSUE — minutes (page someone)", 0, 8, 3, 3, SQL_OUTAGE, "number"),
    sqltile("decline-ending", "ASSET ENDED — minutes (expected, no action)", 3, 8, 3, 3, SQL_ENDING, "number"),
    sqltile("decline-diseng", "NOT ENGAGING — minutes (a content call)", 6, 8, 3, 3, SQL_DISENG, "number"),
    sqltile("decline-unclass", "UNCLASSIFIED decline — minutes (look at it)", 9, 8, 3, 3, SQL_UNCLASS, "number"),

    sqltile("decline-detail", "Classified decline minutes — the evidence behind each verdict",
            0, 11, 12, 5, SQL_TABLE, "table"),
]

# Carry existing tile ids forward so the alerts stay attached across re-runs.
try:
    known = json.load(open("/tmp/cs-tile-ids.json"))
except Exception:
    known = {}
for t in tiles:
    if t["name"] in known:
        t["id"] = known[t["name"]]

dash = {"name": E["DN"], "tags": ["clickathon", "observability", "alerting"],
        "filters": [], "tiles": tiles}
with open(E["OUT"], "w") as fh:
    json.dump(dash, fh)
print("generated dashboard definition — " + str(len(tiles)) + " tiles, "
      + str(sum(1 for t in tiles if t["name"] in known)) + " ids carried forward")
PYEOF

DASH=$(DN="$DASH_NAME" py '
import json, os
print(next((d.get("id","") for d in json.load(open("/tmp/cs-dash-decline.json"))["result"] if d.get("name") == os.environ["DN"]), ""))
')

VALID=$(api -X POST "$BASE/dashboards/validate" -H 'Content-Type: application/json' --data-binary "@$DASH_FILE" \
  | py 'import json,sys; r=json.load(sys.stdin)["result"]; print("ok" if r["valid"] else "INVALID "+json.dumps(r["errors"])[:800])')
[ "$VALID" = ok ] || { echo "dashboard: $VALID" >&2; exit 1; }

echo "dashboard:"
if [ -n "$DASH" ]; then
  api -X PUT "$BASE/dashboards/$DASH" -H 'Content-Type: application/json' --data-binary "@$DASH_FILE" \
    | py 'import json,sys; d=json.load(sys.stdin); print("  updated" if not d.get("error") else "  FAILED: "+str(d["error"])[:400]); sys.exit(1 if d.get("error") else 0)'
else
  DASH=$(api -X POST "$BASE/dashboards" -H 'Content-Type: application/json' --data-binary "@$DASH_FILE" \
    | py 'import json,sys; d=json.load(sys.stdin); sys.stderr.write("  created\n" if not d.get("error") else "  FAILED: "+str(d["error"])[:400]+"\n"); print((d.get("result") or {}).get("id",""))')
fi
[ -n "$DASH" ] || { echo "no dashboard id" >&2; exit 1; }
echo "  id $DASH"

# ------------------------------------------------------------------- alerts ---
# Three alerts, because the three causes have completely different responses and
# collapsing them into one notification throws away the entire point of the
# classifier. Only the system-issue one is a page.
#
# numConsecutiveWindows=2 on the page: one minute of unexplained decline is
# noise, two consecutive evaluations is a trend. The ending/disengagement alerts
# are informational and fire on the first window.
api "$BASE/alerts" > /tmp/cs-alerts.json
api "$BASE/dashboards/$DASH" | py '
import json, sys
d = json.load(sys.stdin)["result"]
json.dump({t.get("name"): t.get("id") for t in (d.get("tiles") or [])}, open("/tmp/cs-tile-ids.json", "w"))
'

tile_id() {  # tile_id <tile name> — resolve the id the control plane actually assigned
  TN="$1" py '
import json, os, sys
tid = json.load(open("/tmp/cs-tile-ids.json")).get(os.environ["TN"], "")
if not tid:
    sys.stderr.write("no tile named " + os.environ["TN"] + "\n"); sys.exit(1)
print(tid)
'
}

save_alert() {  # save_alert <tile name> <alert name> <interval> <consecutive> <message>
  local tile name="$2" interval="$3" consec="$4" msg="$5" existing body
  tile=$(tile_id "$1") || return 1
  existing=$(AN="$name" py '
import json, os
print(next((a.get("id","") for a in json.load(open("/tmp/cs-alerts.json"))["result"] if a.get("name") == os.environ["AN"]), ""))
')
  body=$(N="$name" D="$DASH" T="$tile" W="$WH" I="$interval" C="$consec" M="$msg" py '
import json, os
E = os.environ
print(json.dumps({
    "name": E["N"], "source": "tile", "dashboardId": E["D"], "tileId": E["T"],
    "threshold": 0, "thresholdType": "above_exclusive",
    "interval": E["I"], "numConsecutiveWindows": int(E["C"]),
    "channel": {"type": "webhook", "webhookId": E["W"]},
    "message": E["M"],
    "note": ("Detector and three-way classifier: `docs/DECLINE_ALERTING.md`. "
             "Provisioned by `tools/clickstack-alerts.sh` — edit there, not here; "
             "a re-run overwrites hand edits."),
}))
')
  local verb=POST url="$BASE/alerts"
  if [ -n "$existing" ]; then verb=PUT; url="$BASE/alerts/$existing"; fi
  printf '%s' "$body" | api -X "$verb" "$url" -H 'Content-Type: application/json' --data-binary @- \
    | N="$name" V="$verb" py '
import json, os, sys
d = json.load(sys.stdin)
n = os.environ["N"]
if d.get("error"):
    print("  FAILED " + n + ": " + str(d["error"])[:300]); sys.exit(1)
print(("  updated  " if os.environ["V"] == "PUT" else "  created  ") + n)
'
}

echo "alerts:"
save_alert "SYSTEM ISSUE — minutes (page someone)" \
  "Concurrency decline — SYSTEM ISSUE (page)" 5m 2 \
  "Concurrency is falling and the departures are NOT explained by session closes: sessions are vanishing without closing and the heartbeat rate has collapsed below the fully-paused rate. This is an ingestion or playback failure, not audience behaviour. Runbook: docs/DECLINE_ALERTING.md."
save_alert "NOT ENGAGING — minutes (a content call)" \
  "Concurrency decline — CONTENT NOT ENGAGING" 15m 1 \
  "Concurrency is falling mid-asset while viewers remain connected and are still emitting heartbeats, but are pausing and backgrounding above their own recent rate. This is a content decision, not an ops one — no page."
save_alert "UNCLASSIFIED decline — minutes (look at it)" \
  "Concurrency decline — UNCLASSIFIED" 15m 1 \
  "Concurrency is falling and the cause does not match ending, outage or disengagement cleanly. Deliberately not forced into a label — open the decline dashboard and look."

echo
echo "Done. Verify signed-in with:  tools/clickstack-alerts.sh --verify"
echo "Dashboard time range: the alert tiles are watermark-anchored and ignore it;"
echo "the curve and detail tiles render over 2026-07-14 -> 2026-07-26."
