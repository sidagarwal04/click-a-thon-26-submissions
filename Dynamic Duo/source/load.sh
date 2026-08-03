#!/usr/bin/env bash
# Loader: DDL + dims + events -> ClickHouse (local or Cloud), then validation.
# For a full from-scratch run (wipe + load + sweep + prefill + boot), use
# ./clean_run.sh — this script is the data-loading step it calls.
#
# Local (default when CH_HOST unset; state persisted in ./.chlocal):
#   ./load.sh
# Local docker server (plain TCP, e.g. the librechat/ compose stack):
#   CH_HOST=localhost CH_SECURE=0 CH_PASSWORD=clickhouse ./load.sh
# ClickHouse Cloud:
#   CH_HOST=xxx.clickhouse.cloud CH_PASSWORD=... ./load.sh
# Unseen slice on Day 2 (same tables, tagged — baselines carry over):
#   ./load.sh --events /path/to/unseen.parquet --dataset unseen
# Options:
#   --data-dir DIR   dim CSVs + default events parquet (default: env DATA_DIR or
#                    ../click-a-thon-2026/InMobi/data)
#   --events FILE    events parquet (default: DATA_DIR/ad_events.parquet)
#   --dataset NAME   provenance tag (default: main)
#   --reload         TRUNCATE events + derived tables first (ALL datasets — full wipe)
#   --local          force clickhouse-local even if CH_HOST is set
set -euo pipefail
cd "$(dirname "$0")"

DATA_DIR="${DATA_DIR:-../click-a-thon-2026/InMobi/data}"
EVENTS=""
DATASET="main"
RELOAD=0
FORCE_LOCAL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --events)   EVENTS="$2"; shift 2 ;;
    --dataset)  DATASET="$2"; shift 2 ;;
    --reload)   RELOAD=1; shift ;;
    --local)    FORCE_LOCAL=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done
EVENTS="${EVENTS:-$DATA_DIR/ad_events.parquet}"

for f in "$DATA_DIR/apps.csv" "$DATA_DIR/advertisers.csv" "$DATA_DIR/geo_device.csv" "$EVENTS"; do
  [[ -f "$f" ]] || { echo "missing: $f (set --data-dir / --events; see header)" >&2; exit 1; }
done

# ── connection ────────────────────────────────────────────────────────────────
if command -v clickhouse >/dev/null 2>&1; then CH_BIN=(clickhouse); else CH_BIN=(clickhouse-client); fi

if [[ -n "${CH_HOST:-}" && $FORCE_LOCAL -eq 0 ]]; then
  if [[ "${CH_SECURE:-1}" == "0" ]]; then
    MODE="server($CH_HOST:${CH_PORT:-9000} plain)"
    CH=("${CH_BIN[@]}" client --host "$CH_HOST" --port "${CH_PORT:-9000}" \
        --user "${CH_USER:-default}" --password "${CH_PASSWORD:-}")
  else
    MODE="cloud($CH_HOST)"
    CH=("${CH_BIN[@]}" client --host "$CH_HOST" --port "${CH_PORT:-9440}" --secure \
        --user "${CH_USER:-default}" --password "${CH_PASSWORD:?set CH_PASSWORD}")
  fi
else
  MODE="local(.chlocal)"
  mkdir -p .chlocal
  CH=("${CH_BIN[@]}" local --path .chlocal)
fi

q()      { "${CH[@]}" --query "$1"; }
qfile()  { "${CH[@]}" --queries-file "$1"; }
qpipe()  { "${CH[@]}" --query "$1" < "$2"; }   # stdin data insert — same path local & cloud

echo "== mode: $MODE  dataset: $DATASET  events: $EVENTS"

# ── 1 · DDL (idempotent). 07_librechat_user.sql is deliberately NOT here: it needs
#        CREATE USER rights and is applied by the compose init script / an admin. ──
for f in sql/0[0-6]*.sql; do echo "== ddl: $f"; qfile "$f"; done

if [[ $RELOAD -eq 1 ]]; then
  echo "== reload: truncating events + derived tables (all datasets)"
  for t in ad_events ad_events_enriched metrics_hourly_by_dim; do q "TRUNCATE TABLE rca.$t"; done
fi

# ── 2 · dims (static: truncate + reload is safe and idempotent) ──────────────
echo "== loading dims"
q "TRUNCATE TABLE rca.dim_apps";        qpipe "INSERT INTO rca.dim_apps FORMAT CSVWithNames"        "$DATA_DIR/apps.csv"
q "TRUNCATE TABLE rca.dim_advertisers"; qpipe "INSERT INTO rca.dim_advertisers FORMAT CSVWithNames" "$DATA_DIR/advertisers.csv"
q "TRUNCATE TABLE rca.dim_geo_device";  qpipe "INSERT INTO rca.dim_geo_device FORMAT CSVWithNames"  "$DATA_DIR/geo_device.csv"
q "SYSTEM RELOAD DICTIONARIES"
q "SELECT 'dims:', (SELECT count() FROM rca.dim_apps) AS apps, (SELECT count() FROM rca.dim_advertisers) AS advertisers, (SELECT count() FROM rca.dim_geo_device) AS geo_device FORMAT TSV"

# ── 3 · events via staging (portable stdin path + constant dataset tag;
#        MV cascade enriches + rolls up during the INSERT SELECT) ─────────────
EXISTING=$(q "SELECT count() FROM rca.ad_events WHERE dataset = '$DATASET'")
if [[ "$EXISTING" != "0" ]]; then
  echo "!! dataset '$DATASET' already has $EXISTING rows — refusing to double-load." >&2
  echo "   use --reload for a full wipe, or a different --dataset tag." >&2
  exit 1
fi

echo "== loading events ($(basename "$EVENTS"))"
q "DROP TABLE IF EXISTS rca._staging_events"
q "CREATE TABLE rca._staging_events
   (
       event_time    DateTime64(3, 'UTC'),
       app_id        String,
       geo_device_id String,
       advertiser_id String,
       ad_format     String,
       is_filled     UInt8,
       is_impression UInt8,
       is_click      UInt8,
       revenue       Float64
   ) ENGINE = MergeTree ORDER BY tuple()"
qpipe "INSERT INTO rca._staging_events FORMAT Parquet" "$EVENTS"

t0=$SECONDS
q "INSERT INTO rca.ad_events
   (event_time, app_id, geo_device_id, advertiser_id, ad_format,
    is_filled, is_impression, is_click, revenue, dataset)
   SELECT toDateTime(event_time), app_id, geo_device_id, advertiser_id, ad_format,
          is_filled, is_impression, is_click, revenue, '$DATASET'
   FROM rca._staging_events"
q "DROP TABLE rca._staging_events"
echo "== cascade (raw -> enriched -> rollup) done in $((SECONDS - t0))s"

# ── 4 · validation ───────────────────────────────────────────────────────────
echo "== validation (sql/99_validation.sql)"
"${CH[@]}" --queries-file sql/99_validation.sql --format PrettyCompactMonoBlock
echo "== load complete"
