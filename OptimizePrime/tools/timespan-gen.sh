#!/usr/bin/env bash
# ============================================================================
# tools/timespan-gen.sh — the TIME-SPAN axis: months of data, not more audience.
#
# > Summary: generates realistic MULTI-DAY / MULTI-MONTH event streams at GB
# > scale, with independent knobs for SPAN (days) and DENSITY (events/day), so
# > "we ran for six months" can be separated from "the audience grew". Fits
# > vocabularies from the real file (tools/scale-gen.sql), replaces the time
# > axis with a diurnal + weekday/weekend + event-day profile, rotates the hot
# > content set per 30-day epoch, and injects a DESIGNED-TRUTH probe block
# > (reserved platform TIMESPAN_PROBE) with an analytically known answer.
# > Builds all four tiers per (span x density) point, measures build cost,
# > storage, partitions, pruning, 1-day/1-month/whole-history query cost, runs
# > the reconcile gate, and prices an old-straggler publish. Writes
# > evidence/timespan/timespan.txt. Nothing here touches `sonyliv` or cloud.
#
# USAGE
#   tools/timespan-gen.sh                          # the default 5-point matrix
#   tools/timespan-gen.sh 12:694000 180:46000      # points as span_days:events_per_day
#   KEEP=1 tools/timespan-gen.sh 60:834000         # leave scratch databases behind
#
# THE MATRIX AND WHY. evidence/scale.txt scales the AUDIENCE inside the same
# 99-hour window; this file scales the CALENDAR. The default matrix holds
# VOLUME constant (~50M events) across spans 12 / 60 / 180 days — so anything
# that changes between those points is caused by span alone — and then holds
# SPAN constant while varying density, so the two axes are never conflated:
#
#     12:4170000   60:834000   180:278000     <- same ~50M events, span grows
#     12:694000                180:46000      <- same ~8.3M events, span grows
#
# ISOLATION. Every point gets its own database tspan_<label>; the real-file
# vocabularies live in tspan_real. All local docker ('ch'), never TARGET=cloud,
# never `sonyliv`. Scratch databases are dropped at the end unless KEEP=1.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
# .env lives in the MAIN checkout; a fresh worktree does not have one.
for envf in ./.env "$HOME/Developers/personal/clickathon-project/.env"; do
  [ -f "$envf" ] && { set -a; . "$envf"; set +a; break; }
done

POINTS=("$@"); [ ${#POINTS[@]} -eq 0 ] && POINTS=(12:694000 180:46000 12:4170000 60:834000 180:278000)
SEED="${SEED:-20260202}"
KEEP="${KEEP:-0}"
# Every log_comment carries this. system.query_log is server-wide and keeps
# hours of history, so a bare 'tspan_d12_e20k_gen' comment matches the previous
# run's rows too — and stage_stats picks the SLOWEST match, which would silently
# report a stale, larger point's timing as this run's. One run, one namespace.
RUNID="${RUNID:-r$(date -u +%m%d%H%M%S)}"
# Every log_comment carries this nonce. stage_stats reads system.query_log by
# log_comment and takes the slowest match, so WITHOUT a per-run nonce a re-run
# of the same point silently reports the PREVIOUS run's timings — which is
# exactly what happened between the first and second smoke runs of this script.
RUNID="$(date -u +%Y%m%d%H%M%S)"
# Overridable so a focused sub-run (one axis, a follow-up question) can write its
# own evidence file instead of truncating the matrix's.
OUT="${OUT:-evidence/timespan/timespan.txt}"
REAL_DB="tspan_real"
T0DATE="2026-02-01"           # a Sunday; DOW0 below encodes that
T0=$(python3 -c "from datetime import datetime,timezone;print(int(datetime(2026,2,1,tzinfo=timezone.utc).timestamp()))")
DOW0=0                        # 2026-02-01 is a SUNDAY -> (d + DOW0) % 7 in {0,6} is a weekend
EV_PER_SESS=83.3              # measured mean of the provided file (905,558 / 10,866)
BASE_CONTENT=3357
mkdir -p evidence/timespan

find_csv() { local n="$1" c
  for c in "data/$n" "$HOME/Developers/personal/clickathon-project/data/$n"; do
    [ -s "$c" ] && { echo "$c"; return 0; }
  done; echo "data/$n"; }
RAW_CSV="${RAW_CSV:-$(find_csv ch-hackathon-raw-data.csv)}"
CONTENT_CSV="${CONTENT_CSV:-$(find_csv ch-hackathon-content-data.csv)}"

# --- single-run lock ---------------------------------------------------------
# Two copies of this script share database names (tspan_*) AND the evidence
# file, so a second run DROPs the first run's scratch database out from under
# it mid-build. That is not hypothetical: it happened, and it surfaced as
# "Database tspan_d12_e694k does not exist" in the middle of the users stage —
# a failure that reads like a model limit and is nothing of the kind. A stale
# lock (previous run killed) is taken over rather than obeyed.
LOCK="evidence/timespan/.run.lock"
mkdir -p evidence/timespan
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  printf 'timespan-gen.sh: another run is live (pid %s). Refusing to share scratch databases.\n' "$(cat "$LOCK")" >&2
  exit 1
fi
printf '%s' "$$" > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

say() { printf '%s\n' "$*" | tee -a "$OUT"; }
hr()  { say "--------------------------------------------------------------------------"; }
qd()  { docker exec ch clickhouse-client --database "$1" --query "$2" 2>&1; }

LAST_ERR=""
run_stage() {  # run_stage <db> <label> <file> [extra-setting ...]
  local db="$1" label="$2" file="$3" rc; shift 3
  LAST_ERR=$(docker exec -i ch clickhouse-client --database "$db" --log_comment "$label" \
               "$@" --multiquery < "$file" 2>&1); rc=$?
  return $rc
}
run_sql() {  # run_sql <db> <label> [extra-setting ...] ; SQL on stdin
  local db="$1" label="$2" rc; shift 2
  LAST_ERR=$(docker exec -i ch clickhouse-client --database "$db" --log_comment "$label" \
               "$@" --multiquery 2>&1); rc=$?
  return $rc
}
err_line()  { printf '%s' "$LAST_ERR" | tr '\n' ' ' | cut -c1-300; }

stage_stats() {  # <label> -> ms | peak bytes | read rows | written rows | ext-agg bytes
  qd default "SYSTEM FLUSH LOGS" >/dev/null
  qd default "
    SELECT query_duration_ms, memory_usage, read_rows, written_rows,
           ProfileEvents['ExternalAggregationCompressedBytes']
    FROM system.query_log
    WHERE type='QueryFinish' AND log_comment='$1' AND positionCaseInsensitive(query,'INSERT INTO')>0
    ORDER BY query_duration_ms DESC LIMIT 1 FORMAT TSV"
}
spill_note() { local ext; ext=$(printf '%s' "$1" | cut -f5)
  [ -z "$ext" ] || [ "$ext" = 0 ] && return 0
  printf '  ·  SPILLED %s to disk' "$(fmt "$ext")"; }

# HTTP with X-ClickHouse-Summary: latency + rows/bytes read with no observer
# effect, same idiom as tools/scale-test.sh. extra ($3) carries URL params
# (already encoded) — used for the {p_*} parameters of v_cc_window_range.
summary() {  # summary <db> <sql> [extra-url] -> "read_rows read_bytes elapsed_ns result"
  local db="$1" sql="$2" extra="${3:-}" hdr body
  hdr=$(mktemp); body=$(mktemp)
  curl -sS -D "$hdr" -o "$body" \
    "${CH_LOCAL_URL}/?user=app&password=${CH_PASSWORD_LOCAL}&database=${db}&wait_end_of_query=1${extra}" \
    --data-binary "$sql" >/dev/null 2>&1
  local s; s=$(grep -i '^x-clickhouse-summary' "$hdr" | tail -1 | cut -d: -f2-)
  # tabs -> '/' rather than deleted: a multi-column TSV answer with its tabs
  # stripped reads as one long meaningless integer.
  python3 - "$s" "$(head -c 160 "$body" | tr '\t' '/' | tr -d '\n')" <<'PY'
import json, sys
try: d = json.loads(sys.argv[1].strip())
except Exception: d = {}
print("%s\t%s\t%s\t%s" % (d.get("read_rows","?"), d.get("read_bytes","?"),
                          d.get("elapsed_ns","?"), sys.argv[2].strip()))
PY
  rm -f "$hdr" "$body"
}

fmt() { python3 -c "
import sys
def h(n):
    try: n=float(n)
    except Exception: return sys.argv[1]
    for u in ['B','KiB','MiB','GiB','TiB']:
        if n<1024: return '%.2f %s'%(n,u)
        n/=1024
    return '%.2f PiB'%n
print(h(sys.argv[1]))" "$1"; }
comma() { python3 -c "import sys;print(f'{int(float(sys.argv[1])):,}')" "$1" 2>/dev/null || echo "$1"; }

# ============================================================================
# 0 — preflight
# ============================================================================
: > "$OUT"
say "TIMESPAN EVIDENCE — span (days..months) vs density (events/day), varied independently"
say "generated $(date -u +%Y-%m-%dT%H:%M:%SZ)   commit $(git rev-parse --short HEAD)$(git diff --quiet HEAD -- sql tools || echo ' (sql+tools DIRTY)')"
say "host: $(qd default "SELECT concat(version(),'  cores ',toString(getSetting('max_threads')))" | head -1)  mem $(fmt "$(qd default "SELECT value FROM system.asynchronous_metrics WHERE metric='OSMemoryTotal'" | head -1 | cut -d. -f1)")"
say "points: ${POINTS[*]}   seed $SEED   span start $T0DATE (UTC)"
DISK0=$(df -k /System/Volumes/Data | awk 'NR==2{print $4}')
say "free disk at start: $(fmt $((DISK0 * 1024)))"
hr
say "WHAT IS BEING SCALED"
say "  The CALENDAR, not the audience — the complement of evidence/scale.txt."
say "  Sessions keep the provided file's shape (length, beats, bursts, pauses,"
say "  gaps, dimensions — all fitted by tools/scale-gen.sql) but their START"
say "  TIMES follow a synthetic multi-day profile:"
say "    * diurnal curve: overnight floor, midday bump (13:00), prime-time peak"
say "      centred 21:00 — not the provided file's single launch-event spike"
say "    * weekday/weekend rhythm: weekends x1.35"
say "    * seasonal drift: +/-12% sinusoid over the year"
say "    * EVENT DAYS every 45 days (d%45==7): x2.2 traffic with a sharp 20:30"
say "      spike — the big-match shape that stresses partition heterogeneity"
say "    * hot-content rotation each 30-day epoch: 65% of picks come from a"
say "      rotated Zipf head (titles launch and decay), 35% evergreen"
say "    * sessions cross midnight naturally (counted per point below)"
say "  Volume is held CONSTANT across spans 12/60/180 so any change is caused"
say "  by span alone; a constant-span density pair isolates the other axis."
say ""
say "  DESIGNED TRUTH: every point carries probe blocks on reserved platform"
say "  TIMESPAN_PROBE (40 sessions 20:00-20:29 + 30 sessions 23:45-00:14, on"
say "  day 0, a month-end mid-span day, and the last day) whose minute-by-"
say "  minute concurrency is known in closed form — a THIRD implementation of"
say "  the counting spec, python sets vs arraySplit vs window functions, same"
say "  as tools/unseen-gen.sh. The rest of the stream has no analytic answer;"
say "  there the reconcile gate (delta tier vs interval expansion) is the"
say "  check, run at every point."
hr

# ============================================================================
# 1 — real-file vocabularies, once
# ============================================================================
say "PHASE 0 — fit vocabularies from the provided file (tools/scale-gen.sql)"
qd default "DROP DATABASE IF EXISTS $REAL_DB" >/dev/null
qd default "CREATE DATABASE $REAL_DB" >/dev/null
for f in sql/00_schema.sql; do
  docker exec -i ch clickhouse-client --database "$REAL_DB" --multiquery < "$f" >/dev/null 2>&1
done
RAW_COLS='content_id Int64, video_session_id String, user_id String, event_type String, event String, event_timestamp UInt64, platform String, app_version String, country String, audio_language String, subtitle_language String, player_version String, session_start_epoch UInt64'
CONTENT_COLS='content_id Int64, title String, video_type String, category String'
docker exec -i ch clickhouse-client --database "$REAL_DB" --query \
  "INSERT INTO content_dim (content_id, title, video_type, category) SELECT content_id,title,video_type,category FROM input('$CONTENT_COLS') FORMAT CSVWithNames" < "$CONTENT_CSV"
docker exec -i ch clickhouse-client --database "$REAL_DB" --query \
  "INSERT INTO ev_raw (content_id, video_session_id, user_id, event_type, event, event_timestamp, platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch) SELECT content_id, video_session_id, user_id, event_type, event, toDateTime64(event_timestamp/1000,3), platform, app_version, country, audio_language, subtitle_language, player_version, toDateTime64(session_start_epoch/1000,3) FROM input('$RAW_COLS') FORMAT CSVWithNames" < "$RAW_CSV"
REAL_N=$(qd "$REAL_DB" 'SELECT count() FROM ev_raw' | head -1)
REAL_C=$(qd "$REAL_DB" 'SELECT count() FROM content_dim' | head -1)
say "  loaded $(comma "$REAL_N") real events, $(comma "$REAL_C") catalog rows"
# The INSERTs above name their columns EXPLICITLY, and this guard exists,
# because the positional form silently loaded NOTHING once ADR 0024 added the
# `extra` Map to both tables: 13 selected columns into a 14-column table is an
# error the discarded stderr swallowed. The generator then fitted its
# vocabularies from an empty table and produced a full, plausible-looking,
# entirely blank-dimensioned stream that PASSED every correctness gate — the
# exact "plausible garbage" failure tools/scale-gen.sql warns about. A
# generator whose vocabularies are empty must stop, not measure.
[ "${REAL_N:-0}" -lt 900000 ] && { say "  ABORT: expected ~905,558 real events, got '${REAL_N:-0}'. Vocabularies would be empty."; exit 1; }
[ "${REAL_C:-0}" -lt 30000 ]  && { say "  ABORT: expected ~33,464 catalog rows, got '${REAL_C:-0}'. Content vocabulary would be empty."; exit 1; }
docker exec -i ch clickhouse-client --database "$REAL_DB" --multiquery < tools/scale-gen.sql >/dev/null 2>&1 \
  || { say "  FAILED to fit vocabularies"; exit 1; }
VOC=$(qd "$REAL_DB" "SELECT concat(toString((SELECT uniqExact(dim) FROM gen_lut)), ' dims / ',
                                   toString((SELECT count() FROM gen_lut)), ' values, ',
                                   toString((SELECT count() FROM gen_content)), ' content ranks, ',
                                   toString((SELECT count() FROM gen_ev)), ' event slots')" | head -1)
case "$VOC" in
  7*) say "  vocabularies fitted: $VOC  (gen_start unused — the time axis is the thing this file replaces)" ;;
  *)  say "  ABORT: vocabularies did not fit as expected ($VOC)"; exit 1 ;;
esac

declare -a SUMROWS=() BUILDROWS=() BENCHROWS=()
PEAK_DISK_TOTAL=0

# ============================================================================
# 2 — one (span x density) point
# ============================================================================
run_point() {
  local D="$1" EPD="$2"
  local LBL="d${D}_e$((EPD / 1000))k"
  local DBN="tspan_${LBL}"
  local S NC NEV_TARGET
  S=$(python3 -c "print(round($D * $EPD / $EV_PER_SESS))")
  NEV_TARGET=$((D * EPD))
  # Catalog in play: audience-sqrt growth (as evidence/scale.txt argues) PLUS
  # ~20 launches/day over the span — a six-month service has six months of new
  # titles. Capped at the shipped catalog.
  NC=$(python3 -c "import math; print(min(33464, round($BASE_CONTENT * math.sqrt(max(1, $NEV_TARGET/905558))) + 20*$D))")

  hr
  say "POINT ${LBL} — span $D days, density $(comma $EPD) events/day"
  say "  target $(comma $NEV_TARGET) events, $(comma $S) sessions, $(comma $NC) content ids in play"
  hr
  qd default "DROP DATABASE IF EXISTS $DBN" >/dev/null
  qd default "CREATE DATABASE $DBN" >/dev/null
  for f in sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql sql/20_views.sql; do
    docker exec -i ch clickhouse-client --database "$DBN" --multiquery < "$f" >/dev/null 2>&1
  done
  local t
  for t in gen_lut gen_content gen_ev content_dim; do
    qd default "CREATE TABLE IF NOT EXISTS $DBN.$t AS $REAL_DB.$t" >/dev/null
    qd default "INSERT INTO $DBN.$t SELECT * FROM $REAL_DB.$t" >/dev/null
  done

  # ---- time-profile LUTs (the whole point of this generator) ---------------
  # 65,536-slot inverse-CDF LUTs, same O(1)-per-session idiom as gen_start in
  # tools/scale-gen.sql — but built from the synthetic multi-day profile
  # instead of the provided file's launch-event histogram.
  run_sql "$DBN" "tspan_${RUNID}_${LBL}_luts" <<SQL
DROP TABLE IF EXISTS ts_day;
CREATE TABLE ts_day (slot UInt32, d UInt32) ENGINE = MergeTree ORDER BY slot;
INSERT INTO ts_day
SELECT n.number + 1,
       toUInt32(arrayFirstIndex(c -> c >= (n.number + 0.5) / 65536.0, w.cdf) - 1)
FROM numbers(65536) AS n
CROSS JOIN
(   SELECT arrayCumSum(arrayMap(x -> x / arraySum(ws), ws)) AS cdf
    FROM
    (   SELECT arrayMap(d ->
              if(((d + ${DOW0}) % 7) IN (0, 6), 1.35, 1.0)
            * (1 + 0.12 * sin(2 * pi() * d / 365.0 + 0.7))
            * if((d % 45) = 7, 2.2, 1.0),
            range(${D})) AS ws)
) AS w;

DROP TABLE IF EXISTS ts_min_n;
CREATE TABLE ts_min_n (slot UInt32, m UInt16) ENGINE = MergeTree ORDER BY slot;
INSERT INTO ts_min_n
SELECT n.number + 1,
       toUInt16(arrayFirstIndex(c -> c >= (n.number + 0.5) / 65536.0, w.cdf) - 1)
FROM numbers(65536) AS n
CROSS JOIN
(   SELECT arrayCumSum(arrayMap(x -> x / arraySum(ws), ws)) AS cdf
    FROM
    (   SELECT arrayMap(m ->
              0.12
            + 0.25 * exp(-pow((m - 780.0)  / 240.0, 2))
            + 1.00 * exp(-pow((m - 1260.0) / 110.0, 2)),
            range(1440)) AS ws)
) AS w;

DROP TABLE IF EXISTS ts_min_e;
CREATE TABLE ts_min_e (slot UInt32, m UInt16) ENGINE = MergeTree ORDER BY slot;
INSERT INTO ts_min_e
SELECT n.number + 1,
       toUInt16(arrayFirstIndex(c -> c >= (n.number + 0.5) / 65536.0, w.cdf) - 1)
FROM numbers(65536) AS n
CROSS JOIN
(   SELECT arrayCumSum(arrayMap(x -> x / arraySum(ws), ws)) AS cdf
    FROM
    (   SELECT arrayMap(m ->
              0.12
            + 0.25 * exp(-pow((m - 780.0)  / 240.0, 2))
            + 1.00 * exp(-pow((m - 1260.0) / 110.0, 2))
            + 2.50 * exp(-pow((m - 1230.0) / 45.0,  2)),
            range(1440)) AS ws)
) AS w;
SQL
  # shellcheck disable=SC2181
  [ $? -ne 0 ] && { say "  LUT build FAILED: $(err_line)"; return 1; }

  # ---- designed-truth probe blocks -----------------------------------------
  # Probe days: day 0, a mid-span MONTH-END day (so the 23:45 block crosses a
  # month boundary — the cc_hour_agg partition edge), and the last day. Truth
  # per counting spec: active [a, b+60], minutes floor(a/60)..floor((b+60)/60)
  # INCLUSIVE. Blocks are minute-aligned so the truth is exact integers.
  local PROBE_META
  PROBE_META=$(python3 - "$D" "$T0" <<'PY'
import sys, calendar
from datetime import datetime, timezone, timedelta
D, T0 = int(sys.argv[1]), int(sys.argv[2])
t0 = datetime.fromtimestamp(T0, timezone.utc)
mid = t0 + timedelta(days=D // 2)
month_end = datetime(mid.year, mid.month,
                     calendar.monthrange(mid.year, mid.month)[1], tzinfo=timezone.utc)
mid_idx = (month_end - t0).days
if not (0 < mid_idx < D - 1): mid_idx = D // 2      # short span: no month edge inside
days = sorted({0, mid_idx, D - 1})
blocks = []      # (a_epoch, dur_s, n, id)
for p in days:
    blocks.append((T0 + p*86400 + 20*3600,        1740, 40, f"p1d{p}"))
    blocks.append((T0 + p*86400 + 23*3600 + 2700, 1740, 30, f"p2d{p}"))
truth = {}
for a, dur, n, _ in blocks:
    m = (a // 60) * 60
    while m <= ((a + dur + 60) // 60) * 60:
        truth[m] = truth.get(m, 0) + n
        m += 60
print(",".join(str(p) for p in days))
print("[" + ",".join(f"(toUInt32({a}),toUInt32({dur}),toUInt32({n}),'{i}',{k})"
                     for k, (a, dur, n, i) in enumerate(blocks)) + "]")
for m in sorted(truth):
    print(f"{m}\t{truth[m]}")
PY
)
  local PROBE_DAYS BLKS
  PROBE_DAYS=$(printf '%s\n' "$PROBE_META" | sed -n 1p)
  BLKS=$(printf '%s\n' "$PROBE_META" | sed -n 2p)
  printf '%s\n' "$PROBE_META" | tail -n +3 > "evidence/timespan/probe-truth-${LBL}.tsv"
  say "  probe days (of $D): $PROBE_DAYS  ·  designed truth in evidence/timespan/probe-truth-${LBL}.tsv"
  run_sql "$DBN" "tspan_${RUNID}_${LBL}_probe" --max_partitions_per_insert_block=400 <<SQL
INSERT INTO ev_raw (content_id, video_session_id, user_id, event_type, event,
                    event_timestamp, platform, app_version, country,
                    audio_language, subtitle_language, player_version, session_start_epoch)
SELECT
    toInt64(990000000 + blk.5)                       AS content_id,
    concat('ts_probe_', blk.4, '_', toString(n))     AS video_session_id,
    concat('ts_probe_u_', blk.4, '_', toString(n))   AS user_id,
    multiIf(t = blk.1, 'VideoSessionStart', t = blk.1 + blk.2, 'VideoSessionEnd', 'VideoHeartbeat') AS event_type,
    multiIf(t = blk.1, 'VideoSessionStart', t = blk.1 + blk.2, 'VideoSessionEnd', 'network-activity') AS event,
    toDateTime64(t, 3)                               AS event_timestamp,
    'TIMESPAN_PROBE', '9.9.9', 'probe', 'hin', 'eng', '9.9.9',
    toDateTime64(blk.1, 3)
FROM (SELECT arrayJoin(${BLKS}) AS blk)
ARRAY JOIN range(toUInt32(blk.3)) AS n
ARRAY JOIN arrayConcat([blk.1],
                       arrayFilter(x -> x < blk.1 + blk.2,
                                   arrayMap(i -> blk.1 + 40 * toUInt32(i), range(1, 100))),
                       [blk.1 + blk.2]) AS t;
SQL
  # shellcheck disable=SC2181
  [ $? -ne 0 ] && { say "  probe insert FAILED: $(err_line)"; return 1; }

  # ---- the main generation --------------------------------------------------
  # One shot at DEFAULT settings first, at the largest span, so the
  # max_partitions_per_insert_block=100 trip is RECORDED rather than silently
  # engineered around — a 180-day INSERT whose squashed blocks span the whole
  # calendar is precisely how a naive backfill would hit it in production.
  local GEN_SETTINGS=(--max_partitions_per_insert_block=400)
  if [ "$D" -gt 100 ] && [ -z "${PARTLIMIT_SHOWN:-}" ]; then
    PARTLIMIT_SHOWN=1
    say "  [gen] first attempt at DEFAULT settings (max_partitions_per_insert_block=100):"
    GENRC=0
    run_sql "$DBN" "tspan_${RUNID}_${LBL}_gen_default" <<SQL || GENRC=$?
$(gen_sql "$S" "$NC" "$D")
SQL
    if [ "$GENRC" -ne 0 ]; then
      say "    TRIPPED, as a naive $D-day bulk insert would: $(printf '%s' "$LAST_ERR" | tr '\n' ' ' | sed 's/.*DB::Exception: //' | cut -c1-220)"
      qd "$DBN" "TRUNCATE TABLE ev_raw" >/dev/null; qd "$DBN" "TRUNCATE TABLE cc_minute_stateless" >/dev/null
      # the probe rows died with the truncate — put them back
      run_sql "$DBN" "tspan_${RUNID}_${LBL}_probe2" --max_partitions_per_insert_block=400 <<SQL
INSERT INTO ev_raw (content_id, video_session_id, user_id, event_type, event,
                    event_timestamp, platform, app_version, country,
                    audio_language, subtitle_language, player_version, session_start_epoch)
SELECT
    toInt64(990000000 + blk.5), concat('ts_probe_', blk.4, '_', toString(n)),
    concat('ts_probe_u_', blk.4, '_', toString(n)),
    multiIf(t = blk.1, 'VideoSessionStart', t = blk.1 + blk.2, 'VideoSessionEnd', 'VideoHeartbeat'),
    multiIf(t = blk.1, 'VideoSessionStart', t = blk.1 + blk.2, 'VideoSessionEnd', 'network-activity'),
    toDateTime64(t, 3), 'TIMESPAN_PROBE', '9.9.9', 'probe', 'hin', 'eng', '9.9.9', toDateTime64(blk.1, 3)
FROM (SELECT arrayJoin(${BLKS}) AS blk)
ARRAY JOIN range(toUInt32(blk.3)) AS n
ARRAY JOIN arrayConcat([blk.1],
                       arrayFilter(x -> x < blk.1 + blk.2,
                                   arrayMap(i -> blk.1 + 40 * toUInt32(i), range(1, 100))),
                       [blk.1 + blk.2]) AS t;
SQL
      say "    retrying with max_partitions_per_insert_block=400 (the fix any span >100 days needs)"
    else
      say "    ...did NOT trip (squashed blocks stayed under 100 partitions on this run)"
      GEN_SETTINGS=()   # already generated
    fi
  fi
  if [ ${#GEN_SETTINGS[@]} -gt 0 ]; then
    GENRC=0
    run_sql "$DBN" "tspan_${RUNID}_${LBL}_gen" "${GEN_SETTINGS[@]}" <<SQL || GENRC=$?
$(gen_sql "$S" "$NC" "$D")
SQL
    [ "$GENRC" -ne 0 ] && { say "  [gen] FAILED: $(err_line)"; return 1; }
  fi
  local GS NEV
  GS=$(stage_stats "tspan_${RUNID}_${LBL}_gen"); [ -z "$GS" ] && GS=$(stage_stats "tspan_${RUNID}_${LBL}_gen_default")
  NEV=$(qd "$DBN" 'SELECT count() FROM ev_raw')
  say "  [gen]  $(comma "$NEV") events  ·  $(printf '%s' "$GS" | cut -f1) ms  ·  peak mem $(fmt "$(printf '%s' "$GS" | cut -f2)")$(spill_note "$GS")"

  # ---- did the generator produce the SHAPE it promises? ---------------------
  say ""
  say "  GENERATOR SHAPE (background stream only, probe excluded):"
  say "$(qd "$DBN" "
    WITH perday AS (
      SELECT toDate(event_timestamp) AS dt,
             dateDiff('day', toDate('$T0DATE'), toDate(event_timestamp)) AS d, count() AS c
      FROM ev_raw WHERE platform != 'TIMESPAN_PROBE' GROUP BY dt, d)
    SELECT concat('    events/day  weekday ', formatReadableQuantity(avgIf(c, ((d + $DOW0) % 7) NOT IN (0,6) AND (d % 45) != 7)),
                  '  ·  weekend ', formatReadableQuantity(avgIf(c, ((d + $DOW0) % 7) IN (0,6) AND (d % 45) != 7)),
                  '  ·  event-day ', formatReadableQuantity(avgIf(c, (d % 45) = 7)),
                  '  ·  days with data ', toString(count()))
    FROM perday FORMAT TSVRaw")"
  say "$(qd "$DBN" "
    SELECT concat('    hour-of-day shares  prime 19-23h ', toString(round(100 * countIf(toHour(event_timestamp) BETWEEN 19 AND 23) / count(), 1)),
                  '%  ·  overnight 0-5h ', toString(round(100 * countIf(toHour(event_timestamp) <= 5) / count(), 1)), '%')
    FROM ev_raw WHERE platform != 'TIMESPAN_PROBE' FORMAT TSVRaw")"
  say "$(qd "$DBN" "
    SELECT concat('    sessions crossing midnight: ', toString(countIf(cross)), ' of ', toString(count()))
    FROM (SELECT toDate(min(event_timestamp)) != toDate(max(event_timestamp)) AS cross
          FROM ev_raw WHERE platform != 'TIMESPAN_PROBE' GROUP BY video_session_id)
    FORMAT TSVRaw" )"
  # Dimension vocabulary actually reaching the stream. Printed because a run
  # whose vocabularies failed to fit produces blank dimensions everywhere and
  # still passes every correctness gate — see the guard in PHASE 0.
  say "$(qd "$DBN" "
    SELECT concat('    distinct dims in stream: platform ', toString(uniqExact(platform)),
                  ' · country ', toString(uniqExact(country)),
                  ' · app ', toString(uniqExact(app_version)),
                  ' · content ', toString(uniqExact(content_id)),
                  ' · blank-platform rows ', toString(countIf(platform = '')))
    FROM ev_raw WHERE platform != 'TIMESPAN_PROBE' FORMAT TSVRaw")"
  if [ "$D" -ge 60 ]; then
    say "$(qd "$DBN" "
      WITH f AS (SELECT groupArray(content_id) AS a FROM (
              SELECT content_id FROM ev_raw
              WHERE dateDiff('day', toDate('$T0DATE'), toDate(event_timestamp)) < 30
                AND platform != 'TIMESPAN_PROBE'
              GROUP BY content_id ORDER BY count() DESC LIMIT 20)),
           l AS (SELECT groupArray(content_id) AS a FROM (
              SELECT content_id FROM ev_raw
              WHERE dateDiff('day', toDate('$T0DATE'), toDate(event_timestamp)) >= ($D - 30)
                AND platform != 'TIMESPAN_PROBE'
              GROUP BY content_id ORDER BY count() DESC LIMIT 20))
      SELECT concat('    content rotation: ', toString(length(arrayIntersect(f.a, l.a))),
                    ' of the top-20 titles of the first month are still top-20 in the last month')
      FROM f, l FORMAT TSVRaw")"
  fi

  # ---- build the four tiers -------------------------------------------------
  # This local-only harness raises max_partitions_per_insert_block for every
  # stage so the experiment can continue past the default limit. ClickHouse
  # Cloud pins that setting read-only; production must chunk inserts to <=100
  # daily partitions or migrate the affected tiers to monthly partitions.
  say ""
  local BUILD_STAGES=("30_build_intervals:intervals" "45_user_concurrency:users" "40_deltas:deltas" "50_hour_agg:houragg")
  local stage f lbl st BUILD_FAILED=""
  for stage in "${BUILD_STAGES[@]}"; do
    f="sql/${stage%%:*}.sql"; lbl="${stage##*:}"
    local ok="" tiername
    case "$lbl" in intervals) tiername=session_intervals ;; users) tiername=cc_user_minute ;;
                   deltas) tiername=cc_minute_delta ;; houragg) tiername=cc_hour_agg ;; esac
    local tier targs tname
    for tier in "default:" \
                "spill:--max_bytes_before_external_group_by=1073741824" \
                "spill+2threads:--max_bytes_before_external_group_by=1073741824 --max_threads=2"; do
      tname="${tier%%:*}"; targs="${tier#*:}"
      qd "$DBN" "TRUNCATE TABLE IF EXISTS $tiername" >/dev/null 2>&1
      # shellcheck disable=SC2086
      if run_stage "$DBN" "tspan_${RUNID}_${LBL}_${lbl}_${tname}" "$f" --max_partitions_per_insert_block=400 $targs; then
        st=$(stage_stats "tspan_${RUNID}_${LBL}_${lbl}_${tname}")
        say "  [$lbl$([ "$tname" != default ] && echo "+$tname")]  $(printf '%s' "$st" | cut -f1) ms  ·  peak mem $(fmt "$(printf '%s' "$st" | cut -f2)")  ·  read $(comma "$(printf '%s' "$st" | cut -f3)") rows  ·  wrote $(comma "$(printf '%s' "$st" | cut -f4)") rows$(spill_note "$st")"
        BUILDROWS+=("${LBL}|$lbl$([ "$tname" != default ] && echo "+$tname")|$(printf '%s' "$st" | cut -f1)|$(printf '%s' "$st" | cut -f2)")
        ok=1; break
      fi
      say "  [$lbl]  FAILED at $tname: $(err_line)"
      BUILDROWS+=("${LBL}|$lbl+$tname|FAILED|-")
    done
    [ -z "$ok" ] && { BUILD_FAILED="$lbl"; break; }
  done
  if [ -n "$BUILD_FAILED" ]; then
    say "  point ${LBL} did not complete: stage '$BUILD_FAILED' failed — the error above IS the measurement."
    SUMROWS+=("${LBL}|$D|$EPD|$NEV|FAILED:$BUILD_FAILED|-|-|-|-|-")
    [ "$KEEP" = 1 ] || qd default "DROP DATABASE $DBN" >/dev/null
    return 0
  fi
  docker exec -i ch clickhouse-client --database "$DBN" --multiquery < sql/85_windows.sql >/dev/null 2>&1 \
    || say "  WARNING: sql/85_windows.sql failed to apply — window-range bench will fail"

  # ---- row counts and the hour-cube-vs-delta question -----------------------
  local iv dl ha um st_rows
  iv=$(qd "$DBN" "SELECT count() FROM session_intervals FINAL")
  dl=$(qd "$DBN" "SELECT count() FROM cc_minute_delta")
  ha=$(qd "$DBN" "SELECT count() FROM cc_hour_agg FINAL")
  um=$(qd "$DBN" "SELECT count() FROM cc_user_minute FINAL")
  st_rows=$(qd "$DBN" "SELECT count() FROM cc_minute_stateless")
  say ""
  say "  ROWS  intervals $(comma "$iv")  ·  delta $(comma "$dl")  ·  hour cube $(comma "$ha")  ·  user $(comma "$um")  ·  stateless $(comma "$st_rows")"
  say "$(qd "$DBN" "
    SELECT concat('  hour cube vs delta tier: ', toString(round($ha / greatest($dl, 1), 2)),
                  'x the rows  ·  ',
                  toString(round((SELECT sum(data_compressed_bytes) FROM system.parts WHERE database='$DBN' AND active AND table='cc_hour_agg')
                        / greatest((SELECT sum(data_compressed_bytes) FROM system.parts WHERE database='$DBN' AND active AND table='cc_minute_delta'), 1), 2)),
                  'x the bytes') FORMAT TSVRaw")"

  # ---- storage, partitions, parts ------------------------------------------
  say ""
  say "  STORAGE — system.parts, active only, no OPTIMIZE FINAL beforehand."
  say "  $(printf '%-22s %14s %12s %14s %8s %8s %10s' 'table' 'rows' 'on disk' 'uncompressed' 'parts' 'partns' 'max p/ptn')"
  say "$(qd "$DBN" "
    SELECT concat('  ', rpad(table, 22, ' '),
                  lpad(formatReadableQuantity(sum(rows)), 14, ' '),
                  lpad(formatReadableSize(sum(data_compressed_bytes)), 12, ' '),
                  lpad(formatReadableSize(sum(data_uncompressed_bytes)), 14, ' '),
                  lpad(toString(count()), 8, ' '),
                  lpad(toString(uniqExact(partition)), 8, ' '),
                  lpad(toString(max(ppp)), 10, ' '))
    FROM (SELECT table, partition, rows, data_compressed_bytes, data_uncompressed_bytes,
                 count() OVER (PARTITION BY table, partition) AS ppp
          FROM system.parts WHERE database='$DBN' AND active)
    GROUP BY table ORDER BY sum(data_compressed_bytes) DESC FORMAT TSVRaw")"
  local PDISK
  PDISK=$(qd "$DBN" "SELECT toUInt64(sum(bytes_on_disk)) FROM system.parts WHERE database='$DBN' AND active")
  PEAK_DISK_TOTAL=$((PEAK_DISK_TOTAL + PDISK))
  say "  point on-disk total: $(fmt "$PDISK")"

  # ---- serving cost: 1 day vs 1 month vs whole history ----------------------
  # The ADR 0003 claim under test: a long range reads O(range_hours) stored
  # rows, not O(range_minutes) — so the whole history should cost hour-tier
  # money, not minute-tier money. b10 showed it at 13 days; this is 6 months.
  local MIDD=$((D / 2))
  local W1S W1E WMS WME W3S W3E MSTART
  W1S=$((T0 + MIDD * 86400));        W1E=$((W1S + 86400))
  MSTART=$((MIDD - 15)); [ $MSTART -lt 0 ] && MSTART=0
  WMS=$((T0 + MSTART * 86400));      WME=$((WMS + 86400 * (D < 30 ? D : 30)))
  W3S=$T0;                           W3E=$((T0 + D * 86400))
  enc() { python3 -c "import sys,datetime;print(datetime.datetime.fromtimestamp(int(sys.argv[1]),datetime.timezone.utc).strftime('%Y-%m-%d%%20%H:%M:%S'))" "$1"; }
  wrange_sql() { echo "SELECT peak, integral, round(avg_concurrent,2), hours_from_hour_tier, change_points_from_minute_tier FROM v_cc_window_range(p_start={p_start:DateTime}, p_end={p_end:DateTime}, p_platform={p_platform:String}, p_country={p_country:String}, p_content_id={p_content_id:Int64}) FORMAT TSV"; }
  local -a BN=() BQ=() BX=()
  BN+=("W1 window-range, ONE day (hour tier)");    BQ+=("$(wrange_sql)"); BX+=("&param_p_start=$(enc $W1S)&param_p_end=$(enc $W1E)&param_p_platform=*&param_p_country=*&param_p_content_id=-1")
  BN+=("W2 window-range, 30 days");                BQ+=("$(wrange_sql)"); BX+=("&param_p_start=$(enc $WMS)&param_p_end=$(enc $WME)&param_p_platform=*&param_p_country=*&param_p_content_id=-1")
  BN+=("W3 window-range, WHOLE history ($D d)");   BQ+=("$(wrange_sql)"); BX+=("&param_p_start=$(enc $W3S)&param_p_end=$(enc $W3E)&param_p_platform=*&param_p_country=*&param_p_content_id=-1")
  BN+=("M1 minute tier, whole history (contrast)"); BQ+=("SELECT max(concurrent) FROM (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS concurrent FROM cc_minute_delta GROUP BY minute) FORMAT TSV"); BX+=("")
  BN+=("M2 minute tier, one day (pruning check)");  BQ+=("SELECT max(concurrent) FROM (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS concurrent FROM cc_minute_delta WHERE minute >= toDateTime($W1S) AND minute < toDateTime($W1E) GROUP BY minute) FORMAT TSV"); BX+=("")
  say ""
  say "  SERVING COST — median of 3, plus parts/marks actually selected (query_log):"
  say "  $(printf '%-42s %9s %13s %12s %7s %8s  %s' 'query' 'ms' 'rows read' 'bytes read' 'parts' 'marks' 'result')"
  local i j r rr rb res lblq
  for i in "${!BN[@]}"; do
    local tms=()
    lblq="tspan_${RUNID}_${LBL}_q${i}"
    for j in 1 2 3; do
      r=$(summary "$DBN" "${BQ[$i]}" "${BX[$i]}&log_comment=$lblq")
      tms+=("$(printf '%s' "$r" | cut -f3)")
      rr=$(printf '%s' "$r" | cut -f1); rb=$(printf '%s' "$r" | cut -f2); res=$(printf '%s' "$r" | cut -f4)
    done
    qd default "SYSTEM FLUSH LOGS" >/dev/null
    local pm
    pm=$(qd default "SELECT concat(toString(ProfileEvents['SelectedParts']), ' ', toString(ProfileEvents['SelectedMarks'])) FROM system.query_log WHERE type='QueryFinish' AND log_comment='$lblq' ORDER BY event_time_microseconds DESC LIMIT 1" | head -1)
    local med
    med=$(python3 -c "
import sys
v=sorted(float(x) for x in sys.argv[1:] if x.replace('.','',1).isdigit())
print(round(v[len(v)//2]/1e6,1) if v else '?')" "${tms[@]}")
    say "  $(printf '%-42s %9s %13s %12s %7s %8s  %s' "${BN[$i]}" "$med" "$(comma "$rr")" "$(fmt "$rb")" "${pm%% *}" "${pm##* }" "$(printf '%.60s' "$res")")"
    BENCHROWS+=("${LBL}|${BN[$i]%% *}|$med|$rr|$rb|${pm%% *}")
  done

  # ---- correctness gates ----------------------------------------------------
  say ""
  local RECON
  RECON=$(qd "$DBN" "
    WITH dense AS (
      SELECT minute, concurrent FROM v_concurrency_minute_delta_total
      ORDER BY minute WITH FILL STEP toIntervalSecond(60) INTERPOLATE (concurrent AS concurrent)
    )
    SELECT if(countIf(dense.concurrent != i.concurrent) = 0,
              concat('PASS  ', toString(count()), ' minutes compared, peak ', toString(max(i.concurrent))),
              concat('FAIL  ', toString(countIf(dense.concurrent != i.concurrent)), ' of ', toString(count()), ' minutes disagree'))
    FROM dense INNER JOIN v_concurrency_minute_intervals i USING (minute)
    SETTINGS max_bytes_before_external_group_by = 1073741824 FORMAT TSVRaw" | head -1)
  say "  reconcile (delta serving vs interval expansion, every minute of $D days): $RECON"

  # User-tier gate (ADR 0016) at the LOW-density points only: the uniqExact
  # expansion is audience-bound, and evidence/scale.txt already prices it at
  # 1M sessions — what is new here is running it over a 180-day calendar.
  if [ "$S" -le 150000 ]; then
    local UGATE
    UGATE=$(qd "$DBN" "
      WITH truth AS (
        SELECT toDateTime(m) AS minute, uniqExact(user_id) AS u
        FROM (
          SELECT user_id, arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
                                          toUInt32(toStartOfMinute(interval_end)) + 1, 60)) AS m
          FROM session_intervals FINAL
        ) GROUP BY minute
      ),
      served AS (SELECT minute, concurrent_users AS u FROM v_user_concurrency_minute_total)
      SELECT if(countIf(served.u != truth.u) = 0,
                concat('PASS  ', toString(count()), ' minutes, user peak ', toString(max(truth.u))),
                concat('FAIL  ', toString(countIf(served.u != truth.u)), ' of ', toString(count()), ' minutes disagree'))
      FROM served FULL OUTER JOIN truth USING (minute)
      SETTINGS max_bytes_before_external_group_by = 1073741824, max_threads = 4 FORMAT TSVRaw" | head -1)
    case "$UGATE" in
      PASS*|FAIL*) say "  reconcile (user tier vs interval expansion): $UGATE" ;;
      *) say "  reconcile (user tier): DID NOT COMPLETE — $(printf '%s' "$UGATE" | tr '\n' ' ' | cut -c1-180)" ;;
    esac
  fi

  # ---- designed-truth probe check ------------------------------------------
  # Chain of proof: designed truth == interval expansion (checked here, python
  # sets vs arraySplit) and interval expansion == delta serving (the reconcile
  # gate above) => designed truth == what a dashboard reads.
  local PROBECHK
  qd "$DBN" "
    SELECT toUnixTimestamp(toStartOfMinute(m_dt)) AS m, count() AS c FROM (
      SELECT toDateTime(arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
                                        toUInt32(toStartOfMinute(interval_end)) + 1, 60))) AS m_dt
      FROM session_intervals FINAL WHERE platform = 'TIMESPAN_PROBE'
    ) GROUP BY m ORDER BY m FORMAT TSV" > "evidence/timespan/probe-served-${LBL}.tsv"
  PROBECHK=$(python3 - "evidence/timespan/probe-truth-${LBL}.tsv" "evidence/timespan/probe-served-${LBL}.tsv" <<'PY'
import sys
def load(p):
    d = {}
    for ln in open(p):
        ln = ln.strip()
        if ln:
            k, v = ln.split("\t"); d[int(k)] = int(v)
    return d
t, s = load(sys.argv[1]), load(sys.argv[2])
bad = [(m, t.get(m, 0), s.get(m, 0)) for m in sorted(set(t) | set(s)) if t.get(m, 0) != s.get(m, 0)]
if bad:
    print(f"FAIL  {len(bad)} of {len(t)} designed minutes disagree; first: minute {bad[0][0]} designed {bad[0][1]} served {bad[0][2]}")
else:
    print(f"PASS  {len(t)} designed minutes, peak {max(t.values())}, month/midnight-crossing blocks included")
PY
)
  say "  designed-truth probe (python truth vs interval expansion): $PROBECHK"
  case "$PROBECHK" in PASS*) rm -f "evidence/timespan/probe-served-${LBL}.tsv" ;; esac

  # ---- old-straggler publish, at the longest span only ----------------------
  # Q11's span question: session_dirty / cc_publish_batch / cc_publish_consumed
  # carry 7-DAY TTLs. Those TTLs are on marked_at — PROCESSING time — so a
  # straggler whose EVENT time is months old must still publish cleanly. Proved
  # here by bridging a gap in a session from the FIRST WEEK of a 180-day span.
  # STRAGGLER_MIN_EV exists so this branch is reachable in a cheap smoke run;
  # the default keeps it at the one point the brief asks for (180 d / 50M).
  if [ "$D" -ge 100 ] && [ "$NEV" -gt "${STRAGGLER_MIN_EV:-20000000}" ]; then
    say ""
    say "  OLD-STRAGGLER PUBLISH — event-time ~$((D - 7)) days before span end:"
    if docker exec -i ch clickhouse-client --database "$DBN" --multiquery < sql/12_publish.sql >/dev/null 2>&1; then
      local pick sess ts
      pick=$(qd "$DBN" "
        SELECT video_session_id, toString(interval_end + toIntervalSecond(intDiv(gap_s, 2))) AS ts
        FROM (
          SELECT video_session_id, interval_end,
                 dateDiff('second', interval_end,
                          leadInFrame(interval_start) OVER (PARTITION BY video_session_id ORDER BY interval_start
                                                            ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)) AS gap_s
          FROM session_intervals FINAL
          WHERE interval_start < toDateTime($((T0 + 7 * 86400))))
        WHERE gap_s BETWEEN 180 AND 300
        ORDER BY video_session_id, interval_end LIMIT 1" | head -1)
      sess=$(printf '%s' "$pick" | cut -f1); ts=$(printf '%s' "$pick" | cut -f2)
      if [ -n "$sess" ] && [ -n "$ts" ]; then
        say "    straggler: ${sess:0:20}…  heartbeat at $ts (bridges a gap in week 1)"
        # gap_s is capped at 300 so the midpoint beat sits <= 150 s from BOTH
        # sides and the two intervals actually merge — a wider gap would insert
        # a beat that changes nothing and prove nothing. Columns are named for
        # the ADR 0024 reason documented in PHASE 0.
        qd "$DBN" "INSERT INTO ev_raw
             (content_id, video_session_id, user_id, event_type, event, event_timestamp,
              platform, app_version, country, audio_language, subtitle_language,
              player_version, session_start_epoch)
           SELECT content_id, video_session_id, user_id, 'VideoHeartbeat', 'network-activity',
                  toDateTime64('$ts', 3), platform, app_version, country, audio_language,
                  subtitle_language, player_version, session_start_epoch
           FROM ev_raw WHERE video_session_id = '$sess'
           ORDER BY event_timestamp LIMIT 1" >/dev/null
        sleep 4
        local pout prc=0
        pout=$(PUBLISH_SETTLE_S=2 TARGET=local tools/publish.sh --database "$DBN" 2>&1) || prc=$?
        printf '%s\n' "$pout" | sed 's/^/      /' | tail -20 | tee -a "$OUT" >/dev/null
        if [ "$prc" = 0 ]; then
          local run
          run=$(qd "$DBN" "SELECT max(run_id) FROM cc_publish_runs WHERE phase = 'committed'")
          say "$(qd "$DBN" "
            SELECT concat('    per-phase: ', arrayStringConcat(groupArray(concat(phase, ' ', toString(elapsed_ms), 'ms')), ' · '))
            FROM (SELECT phase, elapsed_ms FROM cc_publish_runs
                  WHERE run_id = $run AND phase NOT IN ('claimed','committed') ORDER BY at) FORMAT TSVRaw")"
          RECON=$(qd "$DBN" "
            WITH dense AS (
              SELECT minute, concurrent FROM v_concurrency_minute_delta_total
              ORDER BY minute WITH FILL STEP toIntervalSecond(60) INTERPOLATE (concurrent AS concurrent)
            )
            SELECT if(countIf(dense.concurrent != i.concurrent) = 0,
                      concat('PASS  ', toString(count()), ' minutes'),
                      concat('FAIL  ', toString(countIf(dense.concurrent != i.concurrent)), ' minutes disagree'))
            FROM dense INNER JOIN v_concurrency_minute_intervals i USING (minute)
            SETTINGS max_bytes_before_external_group_by = 1073741824 FORMAT TSVRaw" | head -1)
          say "    reconcile after the old-straggler publish: $RECON"
        else
          say "    *** publish FAILED (exit $prc) — the output above is the measurement ***"
        fi
      else
        say "    no week-1 session with a 180-400 s gap found — probe skipped"
      fi
    else
      say "    sql/12_publish.sql failed to apply — probe skipped"
    fi
  fi

  SUMROWS+=("${LBL}|$D|$EPD|$NEV|$iv|$dl|$ha|$um|$PDISK|${RECON%% *}")
  [ "$KEEP" = 1 ] || qd default "DROP DATABASE $DBN" >/dev/null
  return 0
}

# ============================================================================
# the generator SQL — tools/scale-load.sql with the TIME AXIS replaced.
# Everything below the t0 / content lines is the scale generator's fitted
# session shape, verbatim (same constants, same salts), so a timespan point and
# a scale point differ ONLY in when sessions start and what they watch.
# ============================================================================
gen_sql() {  # gen_sql <S> <NC> <D>
  local S="$1" NC="$2" D="$3"
cat <<SQL
INSERT INTO ev_raw
    (content_id, video_session_id, user_id, event_type, event, event_timestamp,
     platform, app_version, country, audio_language, subtitle_language,
     player_version, session_start_epoch)
WITH
    (a, k) -> bitShiftRight(cityHash64(a, k, ${SEED}), 11) * pow(2, -53) AS U,
    (a, k1, k2) -> sqrt(-2 * log(greatest(U(a, k1), 1e-12))) * cos(2 * pi() * U(a, k2)) AS N01,
    (u, cdf) -> greatest(1, arrayFirstIndex(x -> x >= u, cdf)) AS PICK,

    -- The model's gap threshold, from the one declaration (ADR 0032); this was
    -- a literal 150 below, the same circularity as tools/scale-load.sql §D1.
    (SELECT gap_s FROM v_model_policy) AS GAP_S,

    3.4    AS BURST_MEAN,
    53.0   AS SESS_MEDIAN,
    0.951  AS SESS_SIGMA,
    0.0153 AS P_BIG_GAP,
    223.0  AS BIG_GAP_MEDIAN,
    1.417  AS BIG_GAP_SIGMA,
    0.102  AS P_PAUSE,
    0.23   AS P_PAUSE_UNCLOSED,
    0.060  AS P_BARE_RESUME,
    0.885  AS P_OWN_USER,
    3.4    AS CONTENT_ZIPF,
    0.18   AS P_BLANK_SENTINEL,
    0.35   AS P_EVERGREEN,       -- share of picks NOT subject to hot-set rotation

    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, d))))   FROM ts_day)   AS day_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, m))))   FROM ts_min_n) AS minN_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, m))))   FROM ts_min_e) AS minE_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'platform')          AS plat_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'platform')          AS plat_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'country')           AS ctry_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'country')           AS ctry_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'app_version')       AS app_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'app_version')       AS app_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'player_version')    AS ply_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'player_version')    AS ply_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'audio_language')    AS aud_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'audio_language')    AS aud_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, value)))) FROM gen_lut WHERE dim = 'subtitle_language') AS sub_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((idx, cum))))   FROM gen_lut WHERE dim = 'subtitle_language') AS sub_c,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((rank, content_id)))) FROM gen_content WHERE rank <= ${NC})   AS cont_v,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, event))))      FROM gen_ev) AS ev_lut,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, event_type)))) FROM gen_ev) AS et_lut

SELECT
    content_id,
    video_session_id,
    user_id,
    multiIf(is_first, 'VideoSessionStart',
            is_last,  'VideoSessionEnd',
            is_pause_ev OR is_resume_ev, 'VideoHeartbeat',
            et_lut[lut_slot])                                       AS event_type,
    multiIf(is_first, 'VideoSessionStart',
            is_last,  'VideoSessionEnd',
            is_pause_ev,  'pause',
            is_resume_ev, 'resume',
            ev_lut[lut_slot])                                       AS event,
    toDateTime64(bt + ((cityHash64(sid, bi, k, ${SEED}) % 1000) / 1000.0), 3) AS event_timestamp,
    platform,
    app_version,
    country,
    if(bi = 1, if(U(sid, 11) < P_BLANK_SENTINEL, '', 'unk'), audio_resolved)  AS audio_language,
    if(bi = 1, if(U(sid, 12) < P_BLANK_SENTINEL, '', 'unk'), sub_resolved)    AS subtitle_language,
    player_version,
    session_start_epoch
FROM
(
    SELECT
        sid, bi, bt, nb, bsz, k,
        content_id, video_session_id, user_id, platform, app_version, country,
        player_version, audio_resolved, sub_resolved, session_start_epoch,
        (bi = 1)  AND (k = 0)         AS is_first,
        (bi = nb) AND (k = (bsz - 1)) AS is_last,
        is_pause_beat  AND (k = 0)                             AS is_pause_ev,
        is_resume_beat AND (k = (bsz - 1)) AND NOT is_pause_ev AS is_resume_ev,
        1 + toUInt32(cityHash64(sid, bi, k, ${SEED}) % 4096) AS lut_slot
    FROM
    (
        SELECT
            sid, bi, bt, nb,
            content_id, video_session_id, user_id, platform, app_version, country,
            player_version, audio_resolved, sub_resolved, session_start_epoch,
            least(20, 1 + toUInt32(round(-(BURST_MEAN - 1) * log(greatest(U(sid, 5000000 + bi), 1e-12))))) AS bsz,
            U(sid, 6000000 + bi) < P_PAUSE AS is_pause_beat,
            (
                ((bi > 1) AND (U(sid, 5999999 + bi) < P_PAUSE) AND ((cityHash64(sid, 6999999 + bi, ${SEED}) % 3) = 0) AND (U(sid, 7999999 + bi) >= P_PAUSE_UNCLOSED))
             OR ((bi > 2) AND (U(sid, 5999998 + bi) < P_PAUSE) AND ((cityHash64(sid, 6999998 + bi, ${SEED}) % 3) = 1) AND (U(sid, 7999998 + bi) >= P_PAUSE_UNCLOSED))
             OR ((bi > 3) AND (U(sid, 5999997 + bi) < P_PAUSE) AND ((cityHash64(sid, 6999997 + bi, ${SEED}) % 3) = 2) AND (U(sid, 7999997 + bi) >= P_PAUSE_UNCLOSED))
             OR (U(sid, 9000000 + bi) < P_BARE_RESUME)
            ) AS is_resume_beat
        FROM
        (
            SELECT
                sid, nb, beat_ts, platform, country, app_version, player_version,
                audio_resolved, sub_resolved, content_id, video_session_id,
                user_id, session_start_epoch
            FROM
            (
                SELECT
                    number AS sid,

                    -- ==== THE TIME AXIS — the one thing this file changes ====
                    -- day from the weekday/weekend/event-day/seasonal LUT,
                    -- minute-of-day from the diurnal LUT (event days use the
                    -- spiked one), second uniform inside the minute.
                    day_v[1 + toUInt32(cityHash64(number, 1, ${SEED}) % 65536)] AS dd,
                    if((dd % 45) = 7,
                       minE_v[1 + toUInt32(cityHash64(number, 91, ${SEED}) % 65536)],
                       minN_v[1 + toUInt32(cityHash64(number, 91, ${SEED}) % 65536)]) AS mnt,
                    toUInt32(${T0} + 86400 * dd + 60 * mnt + toUInt32(floor(U(number, 2) * 60))) AS t0,

                    least(2000, greatest(3, toUInt32(round(SESS_MEDIAN * exp(SESS_SIGMA * N01(number, 3, 4)))))) AS nev,
                    greatest(1, toUInt32(round(nev / BURST_MEAN))) AS nb,
                    arrayMap(x -> t0 + x, arrayCumSum(arrayMap(j -> if(j = 1, toUInt32(0),
                        if(U(number, 1000000 + j) < P_BIG_GAP,
                           least(toUInt32(3600), toUInt32(GAP_S + round(exp(log(BIG_GAP_MEDIAN) + (BIG_GAP_SIGMA * N01(number, 2000000 + j, 3000000 + j)))))),
                           toUInt32(40 + floor(U(number, 4000000 + j) * 2)))
                        ), range(1, nb + 1)))) AS beat_ts,

                    plat_v[PICK(U(number, 21), plat_c)] AS platform,
                    ctry_v[PICK(U(number, 22), ctry_c)] AS country,
                    app_v[PICK(U(number, 23), app_c)]   AS app_version,
                    ply_v[PICK(U(number, 24), ply_c)]   AS player_version,
                    aud_v[PICK(U(number, 25), aud_c)]   AS audio_resolved,
                    sub_v[PICK(U(number, 26), sub_c)]   AS sub_resolved,

                    -- ==== CONTENT LAUNCH-AND-DECAY ====
                    -- Zipf rank as in the scale generator, but 65% of picks go
                    -- through a hot-set rotation: each 30-day epoch shifts the
                    -- Zipf head by a fixed stride, so titles launch into the
                    -- head and decay out of it. 35% stay evergreen. Coarse —
                    -- real decay is continuous — but it moves the top of the
                    -- catalog the way a six-month service actually would.
                    1 + least(${NC} - 1, toUInt32(floor(${NC} * pow(U(number, 27), CONTENT_ZIPF)))) AS r0,
                    if(U(number, 28) < P_EVERGREEN, r0,
                       toUInt32(1 + ((r0 - 1 + ((intDiv(dd, 30) * 977) % ${NC})) % ${NC}))) AS rk,
                    cont_v[rk] AS content_id,

                    hex(SHA256(concat('tsess:', toString(number), ':', toString(${SEED})))) AS video_session_id,
                    hex(SHA256(concat('tuser:', toString(
                        if(U(number, 7) < P_OWN_USER, number,
                           toUInt64(floor(U(number, 8) * greatest(1, intDiv(${S}, 50)))))
                    )))) AS user_id,
                    toDateTime64(t0, 3) AS session_start_epoch
                FROM numbers_mt(${S})
            )
        )
        ARRAY JOIN
            beat_ts                 AS bt,
            arrayEnumerate(beat_ts) AS bi
    )
    ARRAY JOIN range(bsz) AS k
);
SQL
}

# ============================================================================
# 3 — run the matrix
# ============================================================================
for p in "${POINTS[@]}"; do
  run_point "${p%%:*}" "${p##*:}"
done

# ============================================================================
# 4 — the tables a reader needs
# ============================================================================
hr
say "SUMMARY — every point, side by side"
hr
say "$(printf '%-14s %6s %12s %13s %11s %13s %11s %11s %11s %8s' point days 'events/day' events intervals delta hour_cube user_bkts 'on disk' recon)"
for r in "${SUMROWS[@]}"; do
  IFS='|' read -r a b c d e f g h i j <<< "$r"
  say "$(printf '%-14s %6s %12s %13s %11s %13s %11s %11s %11s %8s' "$a" "$b" "$(comma "$c")" "$(comma "$d")" "$(comma "$e" 2>/dev/null || echo "$e")" "$(comma "$f" 2>/dev/null || echo "$f")" "$(comma "$g" 2>/dev/null || echo "$g")" "$(comma "$h" 2>/dev/null || echo "$h")" "$(fmt "$i")" "$j")"
done
hr
say "BUILD COST — per stage per point (system.query_log)"
hr
say "$(printf '%-14s %-22s %10s %14s' point stage ms 'peak memory')"
for r in "${BUILDROWS[@]}"; do
  IFS='|' read -r a b c d <<< "$r"
  say "$(printf '%-14s %-22s %10s %14s' "$a" "$b" "$c" "$(fmt "$d")")"
done
hr
say "SERVING COST — the span claim, side by side (median ms · bytes read · parts)"
hr
say "$(printf '%-14s %-6s %9s %13s %12s %7s' point query ms 'rows read' 'bytes read' parts)"
for r in "${BENCHROWS[@]}"; do
  IFS='|' read -r a b c d e f <<< "$r"
  say "$(printf '%-14s %-6s %9s %13s %12s %7s' "$a" "$b" "$c" "$(comma "$d")" "$(fmt "$e")" "$f")"
done
hr
DISK1=$(df -k /System/Volumes/Data | awk 'NR==2{print $4}')
say "DISK — peak scratch footprint across points (sum of per-point on-disk totals,"
say "       points built and dropped sequentially so concurrent peak is ~the largest"
say "       single point): $(fmt "$PEAK_DISK_TOTAL")"
say "free disk now: $(fmt $((DISK1 * 1024)))  (was $(fmt $((DISK0 * 1024))) at start)"
if [ "$KEEP" = 1 ]; then
  say "KEEP=1: scratch databases left behind — drop with:"
  say "  docker exec ch clickhouse-client --query \"DROP DATABASE tspan_...\""
else
  qd default "DROP DATABASE IF EXISTS $REAL_DB" >/dev/null
  say "all scratch databases (tspan_*) dropped."
fi
say "done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
