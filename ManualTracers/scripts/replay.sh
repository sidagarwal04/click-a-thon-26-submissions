#!/usr/bin/env bash
# =====================================================================
# InMobi Click-a-thon 2026 — replay ad_events into ClickHouse Cloud
# =====================================================================
#
#   ./scripts/replay.sh              apply SQL, then replay AD_EVENTS_FILE
#   ./scripts/replay.sh --schema     apply SQL only, no data
#   ./scripts/replay.sh --data       replay data only, no DDL
#   ./scripts/replay.sh --dims       also reload the 3 dimension CSVs
#   ./scripts/replay.sh --rebuild-silver  re-apply schema + JOIN-backfill silver
#   ./scripts/replay.sh --sealed     the whole sealed-dataset pipeline in one shot:
#                                    truncate ad_events(_enriched) only, replace
#                                    apps/advertisers/geo_device with SEALED_DIM_DIR,
#                                    replay AD_EVENTS_FILE + SEALED_EVENTS_FILES[]
#                                    (same shift, so the sealed slice lands right
#                                    after the main dataset's tail — no gap, one
#                                    consistent dim taxonomy across the whole
#                                    timeline), then compress_replay.py and
#                                    provision_alerts.py --apply. Re-runnable: this
#                                    is what to run again each time the sealed
#                                    dataset changes or the demo pace gets retuned.
#
# For any OTHER dataset swap: change AD_EVENTS_FILE below to the new file,
# truncate manually (see TRUNCATE HELPER at the bottom), then run.
# Only --sealed truncates on its own; every other mode never does.
# ---------------------------------------------------------------------

set -euo pipefail

# ===================== CHANGE THIS FOR THE JURY FILE =================
AD_EVENTS_FILE="InMobi/data/ad_events.parquet"

# Shift every event_time forward by N WEEKS on ingest.
#
# Why this exists: ClickStack alert rules are evaluated against WALL CLOCK
# time. The shipped data ends 2026-07-05, which is 4 weeks in the past, so
# a "last 1 hour" alert rule sees an empty window and can never fire.
#
# Why WEEKS and not days/hours: shifting by a whole number of weeks keeps
# day-of-week AND hour-of-day alignment intact, so the seasonal baseline
# (RCA/app/metric_sql.py, partitioned on hour-of-day and weekday/weekend)
# stays valid. An arbitrary offset would silently corrupt every comparison.
#
# 0 = load timestamps exactly as delivered (correct for offline analysis).
# Set to the output of scripts/suggest_shift.sh for a live alerting demo.
# 6 puts the 2026-07-05 tail of the shipped file at ~2026-08-16 (2 weeks of
# future headroom past today, 2026-08-02).
TIME_SHIFT_WEEKS=6
# =====================================================================

# ===================== --sealed mode config ===========================
# Sealed dims carry the SAME ID space as the main dataset (spec.md) but
# regenerated attribute values, so they REPLACE apps/advertisers/geo_device
# rather than append — appending would give every id two rows and fan out
# the enrichment JOIN (measured once: 9M rows became 19.6M). One dim set is
# used for the whole replayed timeline, main dataset included.
SEALED_DIM_DIR="click-a-thon-2026/InMobi/unseen_data"

# Extra event file(s) appended after AD_EVENTS_FILE, same TIME_SHIFT_WEEKS,
# so the sealed slice is contiguous with the main dataset's tail — that
# contiguity is what gives the sealed incident window a real trailing
# baseline (RCA/app/metric_sql.py HISTORY_WEEKS) instead of ~5 days alone.
SEALED_EVENTS_FILES=(
  "click-a-thon-2026/InMobi/unseen_data/ad_events.parquet"
)

# compress_replay.py bucket size used at the end of --sealed.
COMPRESS_BUCKET_SECONDS=2
# =====================================================================

DIM_DIR="InMobi/data"
DB="inmobi"
SQL_DIR="sql"
# metric_sql.py uses `X | None` annotations (3.10+); the system python3 here is 3.9.
# .venv is the same interpreter `uv run` gives RCA, so this stays in sync with it.
PY=".venv/bin/python3"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------- env
if [[ ! -f .env ]]; then echo "FATAL: .env not found in $REPO_ROOT" >&2; exit 1; fi
set -a; # shellcheck disable=SC1091
source .env; set +a

: "${CLICKHOUSE_HOST:?missing in .env}"
: "${CLICKHOUSE_USER:?missing in .env}"
: "${CLICKHOUSE_PASSWORD:?missing in .env}"
PORT="${CLICKHOUSE_HTTPS_PORT:-8443}"
URL="https://${CLICKHOUSE_HOST}:${PORT}"
AUTH="${CLICKHOUSE_USER}:${CLICKHOUSE_PASSWORD}"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mFATAL: %s\033[0m\n' "$*" >&2; exit 1; }

# Run one SQL statement. Body on stdin so quoting never bites us.
#
# Sessions run against `default`, NOT ${DB}: this script has to be able to
# bootstrap a dropped database, and the connection check plus CREATE DATABASE
# both run before ${DB} exists. Every statement in sql/ is fully qualified
# (inmobi.x, and the dictionaries name DB 'inmobi' explicitly), so nothing
# depends on the session database.
ch() {
  local out
  out=$(curl -sS --fail-with-body -u "$AUTH" "${URL}/?database=default" \
          --data-binary @- 2>&1) || die "query failed: ${out}"
  printf '%s' "$out"
}
ch_sql() { printf '%s' "$1" | ch; }

# Stream a file in as a given FORMAT. Query goes in the URL, body is data.
ch_load() {
  local table="$1" file="$2" fmt="$3" extra="${4:-}"
  [[ -f "$file" ]] || die "input file not found: $file"
  local q; q=$(printf 'INSERT INTO %s.%s FORMAT %s' "$DB" "$table" "$fmt")
  local enc; enc=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$q")
  local out
  out=$(curl -sS --fail-with-body -u "$AUTH" \
          "${URL}/?query=${enc}${extra}" \
          --data-binary @- < "$file" 2>&1) || die "load into $table failed: ${out}"
}

# Split a .sql file on ';' at end-of-statement and execute sequentially.
# Uses process substitution (not a pipe) so a failing statement aborts the
# whole script instead of dying quietly in a subshell.
SPLIT_PY='
import re, sys
raw = open(sys.argv[1]).read()
body = re.sub(r"^\s*--.*$", "", raw, flags=re.M)   # strip line comments
for s in body.split(";"):
    if s.strip():
        sys.stdout.write(s.strip() + "\0")
'
apply_sql_file() {
  local f="$1" stmt
  log "applying $f"
  while IFS= read -r -d '' stmt; do
    printf '   · %s\n' "$(printf '%s' "$stmt" | head -c 72 | tr '\n' ' ')"
    ch_sql "$stmt" >/dev/null
  done < <(python3 -c "$SPLIT_PY" "$f")
}

MODE="${1:-all}"
DO_SCHEMA=1; DO_DATA=1; DO_DIMS=0; DO_REBUILD_SILVER=0; DO_SEALED=0
case "$MODE" in
  --schema) DO_DATA=0 ;;
  --data)   DO_SCHEMA=0 ;;
  --dims)   DO_DIMS=1 ;;
  --rebuild-silver) DO_SCHEMA=1; DO_DATA=0; DO_REBUILD_SILVER=1 ;;
  --sealed) DO_DATA=0; DO_SEALED=1 ;;
  all|"")   ;;
  *) die "unknown mode: $MODE" ;;
esac

# Shift-load one Parquet file into ad_events. input() transforms on ingest, so
# the shift costs one pass and no staging table. Column list must match the
# parquet schema exactly. Shared by --data (single AD_EVENTS_FILE) and
# --sealed (AD_EVENTS_FILE + SEALED_EVENTS_FILES[]) so the shift math lives
# in exactly one place.
load_events_shifted() {
  local file="$1"
  [[ -f "$file" ]] || die "input file not found: $file"
  if [[ "$TIME_SHIFT_WEEKS" -eq 0 ]]; then
    ch_load ad_events "$file" Parquet
    return
  fi
  echo "   shifting event_time by +${TIME_SHIFT_WEEKS} week(s): ${file}"
  local schema='event_time DateTime64(3), app_id String, geo_device_id String,
          advertiser_id String, ad_format String, is_filled UInt8,
          is_impression UInt8, is_click UInt8, revenue Float64'
  local q="INSERT INTO ${DB}.ad_events
     SELECT event_time + INTERVAL ${TIME_SHIFT_WEEKS} WEEK,
            app_id, geo_device_id, advertiser_id, ad_format,
            is_filled, is_impression, is_click, revenue
     FROM input('${schema}') FORMAT Parquet"
  local enc; enc=$(python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))' "$q")
  local out
  out=$(curl -sS --fail-with-body -u "$AUTH" "${URL}/?query=${enc}" \
          --data-binary @- < "$file" 2>&1) || die "shifted load of $file failed: ${out}"
}

log "target ${URL} · db=${DB}"
ch_sql "SELECT 1" >/dev/null && echo "   connection OK"

# ------------------------------------------------------------- schema
if (( DO_SCHEMA )); then
  ch_sql "CREATE DATABASE IF NOT EXISTS ${DB}" >/dev/null
  for f in 01_schema 02_dictionaries 03_silver 04_semantic_layer; do
    apply_sql_file "${SQL_DIR}/${f}.sql"
  done
fi

# --------------------------------------------------------- dimensions
# Loaded when explicitly asked, or automatically when apps is empty.
APPS_N=$(ch_sql "SELECT count() FROM ${DB}.apps" | tr -d '[:space:]')
if (( DO_DIMS )) || [[ "$APPS_N" == "0" ]]; then
  log "loading dimension tables"
  CSV_OPTS="&input_format_with_names_use_header=1"
  ch_load apps        "${DIM_DIR}/apps.csv"        CSVWithNames "$CSV_OPTS"
  ch_load advertisers "${DIM_DIR}/advertisers.csv" CSVWithNames "$CSV_OPTS"
  ch_load geo_device  "${DIM_DIR}/geo_device.csv"  CSVWithNames "$CSV_OPTS"
  echo "   dims loaded"
else
  echo "   dimensions already present (${APPS_N} apps) — skipping CSV reload"
fi

# Dictionaries must reflect dim tables before any ad_events ingest (MV uses
# JOIN now, but reload is cheap insurance for dictGet tooling).
reload_dicts() {
  for d in dict_apps dict_advertisers dict_geo_device; do
    ch_sql "SYSTEM RELOAD DICTIONARY ${DB}.${d}" >/dev/null
  done
}
if (( DO_DIMS )) || [[ "$APPS_N" == "0" ]]; then
  reload_dicts
  echo "   dictionaries reloaded"
fi

# --------------------------------------------------------------- data
if (( DO_DATA )); then
  APPS_N=$(ch_sql "SELECT count() FROM ${DB}.apps" | tr -d '[:space:]')
  [[ "$APPS_N" != "0" ]] || die "dimension tables empty — run ./scripts/replay.sh --dims first"
  reload_dicts
  echo "   dictionaries synced before data replay"
  log "replaying ${AD_EVENTS_FILE}"
  echo "   MV1 will populate ad_events_enriched on insert"
  START=$(date +%s)
  load_events_shifted "$AD_EVENTS_FILE"
  echo "   done in $(( $(date +%s) - START ))s"
fi

# ---------------------------------------------------------------- sealed
# The whole sealed-dataset pipeline: truncate event tables only (dims are
# handled separately below since they REPLACE, not append), replay main +
# sealed files back to back under one dim set, then compress + provision.
if (( DO_SEALED )); then
  log "sealed refresh: truncating ad_events + ad_events_enriched"
  ch_sql "TRUNCATE TABLE ${DB}.ad_events" >/dev/null
  ch_sql "TRUNCATE TABLE ${DB}.ad_events_enriched" >/dev/null
  echo "   event tables empty (dimension tables untouched so far)"

  log "loading sealed dims from ${SEALED_DIM_DIR} (replaces apps/advertisers/geo_device)"
  ch_sql "TRUNCATE TABLE ${DB}.apps" >/dev/null
  ch_sql "TRUNCATE TABLE ${DB}.advertisers" >/dev/null
  ch_sql "TRUNCATE TABLE ${DB}.geo_device" >/dev/null
  CSV_OPTS="&input_format_with_names_use_header=1"
  ch_load apps        "${SEALED_DIM_DIR}/apps.csv"        CSVWithNames "$CSV_OPTS"
  ch_load advertisers "${SEALED_DIM_DIR}/advertisers.csv" CSVWithNames "$CSV_OPTS"
  ch_load geo_device  "${SEALED_DIM_DIR}/geo_device.csv"  CSVWithNames "$CSV_OPTS"
  reload_dicts
  echo "   sealed dims + dictionaries loaded"

  log "replaying ${AD_EVENTS_FILE} + ${#SEALED_EVENTS_FILES[@]} sealed file(s), shifted +${TIME_SHIFT_WEEKS}w"
  START=$(date +%s)
  load_events_shifted "$AD_EVENTS_FILE"
  for f in "${SEALED_EVENTS_FILES[@]}"; do
    load_events_shifted "$f"
  done
  echo "   done in $(( $(date +%s) - START ))s"
fi

# ---------------------------------------------------- rebuild silver
# Re-run JOIN enrichment over existing bronze without re-loading parquet.
# Use after changing mv_ad_events_enriched (dictGet → JOIN fix, etc.).
backfill_silver() {
  log "rebuilding ad_events_enriched from ad_events (JOIN enrichment)"
  ch_sql "TRUNCATE TABLE ${DB}.ad_events_enriched" >/dev/null
  ch_sql "
INSERT INTO ${DB}.ad_events_enriched
SELECT
    e.event_time, e.app_id, e.geo_device_id, e.advertiser_id, e.ad_format,
    e.is_filled, e.is_impression, e.is_click, e.revenue,
    coalesce(a.category, 'unknown'),
    coalesce(a.publisher_tier, 'unknown'),
    coalesce(g.region, 'unknown'),
    coalesce(g.country, 'unknown'),
    coalesce(g.device_model, 'unknown'),
    coalesce(g.os_version, 'unknown'),
    if(e.advertiser_id = '', '', coalesce(ad.vertical, 'unknown')),
    if(e.advertiser_id = '', '', coalesce(ad.campaign_type, 'unknown'))
FROM ${DB}.ad_events AS e
LEFT JOIN ${DB}.apps AS a ON e.app_id = a.app_id
LEFT JOIN ${DB}.geo_device AS g ON e.geo_device_id = g.geo_device_id
LEFT JOIN ${DB}.advertisers AS ad
    ON e.advertiser_id = ad.advertiser_id AND e.advertiser_id != ''" >/dev/null
  echo "   silver backfill complete"
}

if (( DO_REBUILD_SILVER )); then
  APPS_N=$(ch_sql "SELECT count() FROM ${DB}.apps" | tr -d '[:space:]')
  [[ "$APPS_N" != "0" ]] || die "dimension tables empty — run ./scripts/replay.sh --dims first"
  EVENTS_N=$(ch_sql "SELECT count() FROM ${DB}.ad_events" | tr -d '[:space:]')
  [[ "$EVENTS_N" != "0" ]] || die "ad_events empty — run ./scripts/replay.sh --data first"
  backfill_silver
fi

# ---------------------------------------------------------- verify
log "row counts"
ch_sql "
SELECT 'ad_events' AS layer, count() AS rows, toString(min(event_time)) AS from_ts, toString(max(event_time)) AS to_ts FROM ${DB}.ad_events
UNION ALL SELECT 'ad_events_enriched', count(), toString(min(event_time)), toString(max(event_time)) FROM ${DB}.ad_events_enriched
FORMAT PrettyCompactMonoBlock"

log "enrichment health (want 0 unknowns)"
ch_sql "
SELECT
  countIf(category='unknown')   AS unknown_category,
  countIf(region='unknown')     AS unknown_region,
  countIf(os_version='unknown') AS unknown_os,
  countIf(advertiser_id!='' AND vertical='unknown') AS unknown_vertical
FROM ${DB}.ad_events_enriched
FORMAT PrettyCompactMonoBlock"

# Deviation is not a stored view — it is rendered from metric_def by the same
# builder the RCA agent uses, so this check exercises the real detection path
# rather than a parallel copy of the maths.
for m in fill_rate requests ecpm revenue; do
  log "top segments for ${m} (live deviation scan)"
  SCAN=$("$PY" scripts/metric_query.py scan "$m") || die "could not render scan for ${m}"
  ch_sql "${SCAN} FORMAT PrettyCompactMonoBlock"
done

# ------------------------------------------------- compress + provision
# Only --sealed does this automatically: compression is destructive to the
# uncompressed timeline (rewrites every event_time) and re-provisioning
# replaces the live dashboard, so every other mode leaves both alone.
if (( DO_SEALED )); then
  log "compressing replay (bucket_seconds=${COMPRESS_BUCKET_SECONDS})"
  "$PY" scripts/compress_replay.py --bucket-seconds "$COMPRESS_BUCKET_SECONDS"

  log "provisioning dashboard + alerts"
  if ! "$PY" scripts/provision_alerts.py --apply; then
    echo "   --apply needs CLICKHOUSE_CLOUD_KEY_ID/_SECRET in .env — spec was"
    echo "   still rendered to docs/rca_detection_dashboard.json; push it"
    echo "   through the ClickStack MCP instead (see provision_alerts.py)."
  fi
fi

log "done"

# =====================================================================
# TRUNCATE HELPER — deliberately NOT run by --schema/--data/--dims/
# --rebuild-silver. --sealed truncates ad_events(_enriched) itself (see
# above) since that mode exists specifically to be re-run.
# Paste manually before replaying a different dataset some other way:
#
#   TRUNCATE TABLE inmobi.ad_events;
#   TRUNCATE TABLE inmobi.ad_events_enriched;
# =====================================================================
