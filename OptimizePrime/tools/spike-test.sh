#!/usr/bin/env bash
# ============================================================================
# tools/spike-test.sh — the cricketer spike: N viewers arriving in ONE minute.
#
# > Summary: answers the mentor question "what happens when concurrency jumps
# > suddenly?". Generates a spike-shaped day — the REAL provided file as the
# > normal day, plus N synthetic sessions that ALL arrive inside one minute
# > (10:40), all watch the SAME content, straddle the 11:00 hour-clip boundary
# > (ADR 0003), and mass-depart inside two minutes after a wicket at 11:14.
# > The spike is STREAMED in one-minute chunks with tools/publish.sh looping
# > concurrently, so publish lag through the spike is measured, not argued.
# > Then: reconcile gates (incremental AND batch path), hour-boundary delta
# > accounting, serving latency during ingest, and a full-rebuild cost ladder.
# > Writes evidence/spike/spike.txt. Nothing here touches `sonyliv`.
#
# USAGE
#   tools/spike-test.sh                    # 1000 10000 100000
#   tools/spike-test.sh 1000 10000        # a subset
#   KEEP=1 tools/spike-test.sh 1000       # leave the scratch database behind
#   CHUNK_PACE_S=0 tools/spike-test.sh    # no pacing between minute-chunks
#
# WHAT A "SPIKE" MEANS HERE — and why the scale ladder is blind to it.
# evidence/scale.txt grows the audience UNIFORMLY: N x the sessions drawn from
# the same start-minute histogram. A spike is the same audience with a
# radically different SHAPE: everyone arrives in one minute, watches one
# title, and leaves together. Row counts barely move; concentration explodes.
# The stress lands on (a) the publisher, whose per-run cost is audience x
# window (ADR 0016/scale.txt), and during a spike EVERY open session is
# re-marked dirty by EVERY heartbeat minute — so each publish run claims the
# whole spike audience; and (b) the correctness of arraySplit/attribution when
# thousands of sessions share timestamps — which is what the gates check.
#
# STREAMING REPLAY IS TIME-COMPRESSED. One spike minute of events is inserted
# per chunk, paced CHUNK_PACE_S seconds apart (default 2). Lag numbers are
# therefore read as: "a publish run absorbing minute-m markings takes T ms;
# at the real 1-minute heartbeat cadence the publisher is stable iff T < 60 s."
# The verdict table at the end applies exactly that test.
#
# LOCAL ONLY, deliberately — same rationale as tools/scale-test.sh: this is
# expected to push the publisher into MEMORY_LIMIT_EXCEEDED at some magnitude,
# and doing that to the graded service is an outage, not a measurement.
# Isolation: every magnitude gets its own database spike_x<N>, dropped at the
# end unless KEEP=1. `sonyliv` is never named in any statement here.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

MAGS=("$@"); [ ${#MAGS[@]} -eq 0 ] && MAGS=(1000 10000 100000)
SEED="${SEED:-20260802}"
KEEP="${KEEP:-0}"
CHUNK_PACE_S="${CHUNK_PACE_S:-2}"
OUTDIR="evidence/spike"
OUT="$OUTDIR/spike.txt"
mkdir -p "$OUTDIR"

# The spike timeline. Placed ON the real file's peak day so the spike rides on
# top of genuine load (baseline peak 2917 @ 2026-07-26 10:56). Arrival minute
# 10:40; the plateau crosses 11:00 (the ADR 0003 hour-clip boundary); wicket at
# 11:14 with everyone gone by 11:16.
ARRIVE="2026-07-26 10:40:00"
WICKET="2026-07-26 11:14:00"
SPIKE_END="2026-07-26 11:16:00"   # exclusive: last departure < this

find_csv() {  # data/ is gitignored; fall back to the main checkout
  local n="$1" c
  for c in "data/$n" "$HOME/Developers/personal/clickathon-project/data/$n"; do
    [ -s "$c" ] && { echo "$c"; return 0; }
  done
  echo "data/$n"
}
RAW_CSV="${RAW_CSV:-$(find_csv ch-hackathon-raw-data.csv)}"
CONTENT_CSV="${CONTENT_CSV:-$(find_csv ch-hackathon-content-data.csv)}"

say() { printf '%s\n' "$*" | tee -a "$OUT"; }
hr()  { say "--------------------------------------------------------------------------"; }
die() { printf 'spike-test FAILED: %s\n' "$*" >&2; exit 1; }

[ "${TARGET:-local}" = cloud ] && die "TARGET=cloud is forbidden here. This is a load generator."

# --- helpers, same idioms as tools/scale-test.sh ----------------------------
qd()  { docker exec ch clickhouse-client --database "$1" --query "$2" 2>&1; }

LAST_ERR=""
run_stage() {  # run_stage <db> <label> <file> [extra-setting ...]
  local db="$1" label="$2" file="$3"; shift 3
  local rc
  LAST_ERR=$(docker exec -i ch clickhouse-client --database "$db" --log_comment "$label" \
               "$@" --multiquery < "$file" 2>&1); rc=$?
  return $rc
}
err_line()  { printf '%s' "$LAST_ERR" | tr '\n' ' ' | cut -c1-300; }
err_short() { printf '%s' "$LAST_ERR" | tr '\n' ' ' | sed 's/.*DB::Exception: //' | cut -c1-96; }

stage_stats() {  # stage_stats <label> -> ms | peak bytes | read rows | written rows | spilled | os read
  qd default "SYSTEM FLUSH LOGS" >/dev/null
  qd default "
    SELECT query_duration_ms, memory_usage, read_rows, written_rows,
           ProfileEvents['ExternalAggregationCompressedBytes'],
           ProfileEvents['OSReadBytes']
    FROM system.query_log
    WHERE type='QueryFinish' AND log_comment='$1' AND positionCaseInsensitive(query,'INSERT INTO')>0
    ORDER BY query_duration_ms DESC LIMIT 1 FORMAT TSV"
}
spill_note() {
  local ext os
  ext=$(printf '%s' "$1" | cut -f5); os=$(printf '%s' "$1" | cut -f6)
  [ -z "$ext" ] || [ "$ext" = 0 ] && return 0
  printf '  ·  SPILLED %s of aggregation state to disk (%s read back)' "$(fmt "$ext")" "$(fmt "$os")"
}

summary() {  # summary <db> <sql> -> "read_rows read_bytes elapsed_ns result" (X-ClickHouse-Summary)
  local db="$1" sql="$2" hdr body
  hdr=$(mktemp); body=$(mktemp)
  curl -sS -D "$hdr" -o "$body" \
    "${CH_LOCAL_URL}/?user=app&password=${CH_PASSWORD_LOCAL}&database=${db}&wait_end_of_query=1" \
    --data-binary "$sql" >/dev/null 2>&1
  local s; s=$(grep -i '^x-clickhouse-summary' "$hdr" | tail -1 | cut -d: -f2-)
  python3 - "$s" "$(head -c 200 "$body" | tr -d '\n')" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1].strip())
except Exception:
    d = {}
print("%s\t%s\t%s\t%s" % (d.get("read_rows", "?"), d.get("read_bytes", "?"),
                          d.get("elapsed_ns", "?"), sys.argv[2].strip()))
PY
  rm -f "$hdr" "$body"
}
probe_ms() {  # probe_ms <db> <sql> -> ms (one shot, no median: we WANT the contention)
  local r; r=$(summary "$1" "$2")
  python3 -c "
import sys
try: print(round(float(sys.argv[1])/1e6,1))
except Exception: print('?')" "$(printf '%s' "$r" | cut -f3)"
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
now_ms() { python3 -c 'import time; print(int(time.time()*1000))'; }

BUILD_STAGES=("30_build_intervals:intervals" "45_user_concurrency:users" "40_deltas:deltas" "50_hour_agg:houragg")
stage_table() {
  case "$1" in
    intervals) echo session_intervals ;;
    users)     echo cc_user_minute ;;
    deltas)    echo cc_minute_delta ;;
    houragg)   echo cc_hour_agg ;;
  esac
}
truncate_stage() { qd "$1" "TRUNCATE TABLE IF EXISTS $(stage_table "$2")" >/dev/null 2>&1; }

# Build all four stages with the scale-test rescue ladder. Sets BUILD_FAILED.
build_model() {  # build_model <db> <tag>
  local db="$1" tag="$2" stage f lbl st
  BUILD_FAILED=""
  for stage in "${BUILD_STAGES[@]}"; do
    f="sql/${stage%%:*}.sql"; lbl="${stage##*:}"
    truncate_stage "$db" "$lbl"
    if run_stage "$db" "${tag}_${lbl}" "$f"; then
      st=$(stage_stats "${tag}_${lbl}")
      say "  [$lbl]  $(printf '%s' "$st" | cut -f1) ms  ·  peak mem $(fmt "$(printf '%s' "$st" | cut -f2)")  ·  read $(comma "$(printf '%s' "$st" | cut -f3)") rows  ·  wrote $(comma "$(printf '%s' "$st" | cut -f4)") rows$(spill_note "$st")"
      REBUILD+=("$tag|$lbl|$(printf '%s' "$st" | cut -f1)|$(printf '%s' "$st" | cut -f2)")
    else
      say "  [$lbl]  *** FAILED at default settings ***"
      say "         $(err_line)"
      REBUILD+=("$tag|$lbl|FAILED|-")
      local RESCUED="" tier tname targs
      for tier in "spill:--max_bytes_before_external_group_by=1073741824" \
                  "spill+2threads:--max_bytes_before_external_group_by=1073741824 --max_threads=2"; do
        tname="${tier%%:*}"; targs="${tier#*:}"
        say "  [$lbl]  retrying with $tname"
        truncate_stage "$db" "$lbl"
        # shellcheck disable=SC2086
        if run_stage "$db" "${tag}_${lbl}_${tname}" "$f" $targs; then
          st=$(stage_stats "${tag}_${lbl}_${tname}")
          say "  [$lbl]  $tname OK  $(printf '%s' "$st" | cut -f1) ms  ·  peak mem $(fmt "$(printf '%s' "$st" | cut -f2)")  ·  wrote $(comma "$(printf '%s' "$st" | cut -f4)") rows$(spill_note "$st")"
          REBUILD+=("$tag|$lbl+$tname|$(printf '%s' "$st" | cut -f1)|$(printf '%s' "$st" | cut -f2)")
          RESCUED="$tname"; break
        fi
        say "  [$lbl]  $tname did NOT rescue it:"
        say "         $(err_line)"
        REBUILD+=("$tag|$lbl+$tname|FAILED|-")
      done
      [ -z "$RESCUED" ] && { BUILD_FAILED="$lbl"; return 1; }
    fi
  done
  return 0
}

# The committed gate, verbatim from tools/scale-test.sh: serving delta layer vs
# the interval expansion, every minute, dense-filled.
reconcile_deltas() {  # reconcile_deltas <db> -> prints PASS/FAIL line
  qd "$1" "
    WITH dense AS (
      SELECT minute, concurrent FROM v_concurrency_minute_delta_total
      ORDER BY minute WITH FILL STEP toIntervalSecond(60) INTERPOLATE (concurrent AS concurrent)
    )
    SELECT if(countIf(dense.concurrent != i.concurrent) = 0,
              concat('PASS  ', toString(count()), ' minutes compared, peak ', toString(max(i.concurrent))),
              concat('FAIL  ', toString(countIf(dense.concurrent != i.concurrent)), ' of ', toString(count()),
                     ' minutes disagree, worst diff ', toString(max(abs(dense.concurrent - i.concurrent)))))
    FROM dense INNER JOIN v_concurrency_minute_intervals i USING (minute) FORMAT TSVRaw" | head -1
}
user_gate() {  # user_gate <db> -> prints PASS/FAIL line
  qd "$1" "
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
              concat('PASS  ', toString(count()), ' minutes compared, user peak ', toString(max(truth.u))),
              concat('FAIL  ', toString(countIf(served.u != truth.u)), ' of ', toString(count()),
                     ' minutes disagree, served peak ', toString(max(served.u)),
                     ' vs true ', toString(max(truth.u))))
    FROM served FULL OUTER JOIN truth USING (minute)
    SETTINGS max_bytes_before_external_group_by = 1073741824, max_threads = 4 FORMAT TSVRaw" | head -1
}

# ============================================================================
# 0 — preamble
# ============================================================================
: > "$OUT"
say "SPIKE EVIDENCE — the cricketer spike: N viewers arriving in ONE minute"
say "generated $(date -u +%Y-%m-%dT%H:%M:%SZ)   commit $(git rev-parse --short HEAD)$(git diff --quiet HEAD -- sql tools || echo ' (sql+tools DIRTY)')"
say "host: $(qd default "SELECT concat(version(),'  cores ',toString(getSetting('max_threads')))" | head -1)  \
mem $(fmt "$(qd default "SELECT value FROM system.asynchronous_metrics WHERE metric='OSMemoryTotal'" | head -1 | cut -d. -f1)")"
MAXMEM_RAW=$(fmt "$(qd default "SELECT value FROM system.server_settings WHERE name='max_server_memory_usage'" | head -1)")
say "magnitudes: ${MAGS[*]} spike sessions   seed $SEED   chunk pace ${CHUNK_PACE_S}s   server memory budget $MAXMEM_RAW"
hr
say "THE SHAPE UNDER TEST — same load, different shape (what scale.txt cannot see)"
say "  Baseline: the REAL provided file (905,558 events, peak 2,917 @ 10:56)."
say "  Spike:    N sessions ALL starting inside $ARRIVE..+60s, all on ONE"
say "            content_id (the match), heartbeats every ~40s with the real"
say "            burst shape (mean 3.4 events/beat), sentinel-then-resolved"
say "            audio/subtitle on the first beat (the ADR 0008 behaviour),"
say "            NO mid-session gaps — a cricket audience is foreground."
say "  Wicket:   $WICKET — every spike session ends inside 120 s."
say "  Boundary: the plateau crosses 11:00, so every spike interval is"
say "            hour-clipped in two (ADR 0003) — the doubling is measured."
say "  Streaming: minute-chunks of the spike are inserted ${CHUNK_PACE_S}s apart while"
say "  tools/publish.sh loops beside them (settle 2s) — a time-compressed"
say "  replay. Stability verdicts are read at the REAL 60s heartbeat cadence:"
say "  the publisher keeps up with a live spike iff one run absorbs one"
say "  minute's markings in under 60 s."
hr

declare -a INGEST_SUM=() PUBLISH_SUM=() GATE_SUM=() REBUILD=()

# ============================================================================
# per-magnitude run
# ============================================================================
for N in "${MAGS[@]}"; do
  DBN="spike_x${N}"
  PUBLOG="$OUTDIR/publish-${N}.log"
  : > "$PUBLOG"
  TMPD=$(mktemp -d)

  hr
  say "SPIKE ${N} — $(comma "$N") sessions arriving in one minute, on the real day"
  hr

  qd default "DROP DATABASE IF EXISTS $DBN" >/dev/null
  qd default "CREATE DATABASE $DBN" >/dev/null
  for f in sql/00_schema.sql sql/01_policy.sql sql/10_intervals.sql sql/15_normalise.sql sql/20_views.sql; do
    docker exec -i ch clickhouse-client --database "$DBN" --multiquery < "$f" >/dev/null 2>&1
  done

  # ---- the normal day: the provided file, plus vocabularies fitted from it --
  RAW_COLS='content_id Int64, video_session_id String, user_id String, event_type String, event String, event_timestamp UInt64, platform String, app_version String, country String, audio_language String, subtitle_language String, player_version String, session_start_epoch UInt64'
  CONTENT_COLS='content_id Int64, title String, video_type String, category String'
  docker exec -i ch clickhouse-client --database "$DBN" --query \
    "INSERT INTO content_dim (content_id,title,video_type,category) SELECT content_id,title,video_type,category FROM input('$CONTENT_COLS') FORMAT CSVWithNames" < "$CONTENT_CSV"
  docker exec -i ch clickhouse-client --database "$DBN" --query \
    "INSERT INTO ev_raw (content_id, video_session_id, user_id, event_type, event, event_timestamp, platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch) SELECT content_id, video_session_id, user_id, event_type, event, toDateTime64(event_timestamp/1000,3), platform, app_version, country, audio_language, subtitle_language, player_version, toDateTime64(session_start_epoch/1000,3) FROM input('$RAW_COLS') FORMAT CSVWithNames" < "$RAW_CSV"
  say "  [base]  $(comma "$(qd "$DBN" 'SELECT count() FROM ev_raw')") real events loaded from $RAW_CSV"
  docker exec -i ch clickhouse-client --database "$DBN" --multiquery < tools/scale-gen.sql >/dev/null 2>&1 \
    || { say "  FAILED to fit vocabularies (tools/scale-gen.sql)"; continue; }

  say "  [base]  building the four tiers on the normal day (the published state a spike hits)"
  build_model "$DBN" "spike_${N}_base" || { say "  baseline build failed — magnitude skipped"; continue; }
  BASE_PEAK=$(qd "$DBN" 'SELECT max(concurrent) FROM v_concurrency_minute_delta_total' | head -1)
  say "  [base]  baseline peak $BASE_PEAK  (repo number 2917 — must match or this is not the same model)"
  IDLE_Q1=$(probe_ms "$DBN" "SELECT max(concurrent) FROM v_concurrency_minute_delta_total")
  IDLE_Q7=$(probe_ms "$DBN" "SELECT count() FROM (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS c FROM cc_minute_delta WHERE minute >= toDateTime('$ARRIVE') AND minute < toDateTime('$ARRIVE') + INTERVAL 1 HOUR GROUP BY minute)")
  say "  [base]  idle serving probes: peak query ${IDLE_Q1} ms · dashboard hour curve ${IDLE_Q7} ms"

  # ---- publisher state, applied AFTER the bulk load so the dirty queue is
  # ---- empty and the spike's markings are the only work it will ever see ----
  docker exec -i ch clickhouse-client --database "$DBN" --multiquery < sql/12_publish.sql >/dev/null 2>&1 \
    || { say "  sql/12_publish.sql failed to apply — magnitude skipped"; continue; }

  # ---- generate the spike into a staging table (never counted as ingest) ----
  GT0=$(now_ms)
  GENOK=1
  LAST_ERR=$(docker exec -i ch clickhouse-client --database "$DBN" --log_comment "spike_${N}_gen" \
      --param_N="$N" --param_SEED="$SEED" --param_ARRIVE="$ARRIVE" --param_WICKET="$WICKET" \
      --multiquery <<'SQL' 2>&1
DROP TABLE IF EXISTS spike_stage;
CREATE TABLE spike_stage
(
    content_id          Int64,
    video_session_id    String,
    user_id             String,
    event_type          LowCardinality(String),
    event               LowCardinality(String),
    event_timestamp     DateTime64(3),
    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),
    audio_language      LowCardinality(String),
    subtitle_language   LowCardinality(String),
    player_version      LowCardinality(String),
    session_start_epoch DateTime64(3)
)
ENGINE = MergeTree ORDER BY event_timestamp;

-- One spike session: arrive in [ARRIVE, ARRIVE+60), beat every ~40s (real
-- burst shape, mean 3.4 events/beat), NO gaps, explicit VideoSessionEnd in
-- [WICKET, WICKET+120). Deterministic: every draw is cityHash64(sid, salt).
-- Dimension vocabularies are the ones tools/scale-gen.sql fitted from the
-- REAL file; content is ONE id — the top-ranked real title. The first beat
-- carries the sentinel-then-resolved audio/subtitle behaviour (ADR 0008), so
-- the dominant-value attribution vote does real work with N sessions sharing
-- the arrival minute.
INSERT INTO spike_stage
    (content_id, video_session_id, user_id, event_type, event, event_timestamp,
     platform, app_version, country, audio_language, subtitle_language,
     player_version, session_start_epoch)
WITH
    (a, k) -> bitShiftRight(cityHash64(a, k, {SEED:UInt64}), 11) * pow(2, -53) AS U,
    (u, cdf) -> greatest(1, arrayFirstIndex(x -> x >= u, cdf)) AS PICK,
    toUInt32(toDateTime({ARRIVE:String})) AS ARRIVE_E,
    toUInt32(toDateTime({WICKET:String})) AS WICKET_E,
    3.4  AS BURST_MEAN,
    0.18 AS P_BLANK_SENTINEL,
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
    (SELECT min(content_id) FROM gen_content WHERE rank = 1) AS THE_MATCH,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, event))))      FROM gen_ev) AS ev_lut,
    (SELECT arrayMap(x -> x.2, arraySort(x -> x.1, groupArray((slot, event_type)))) FROM gen_ev) AS et_lut
SELECT
    THE_MATCH AS content_id,
    video_session_id,
    user_id,
    multiIf(is_first, 'VideoSessionStart', is_last, 'VideoSessionEnd', et_lut[lut_slot]) AS event_type,
    multiIf(is_first, 'VideoSessionStart', is_last, 'VideoSessionEnd', ev_lut[lut_slot]) AS event,
    toDateTime64(bt + ((cityHash64(sid, bi, k, {SEED:UInt64}) % 1000) / 1000.0), 3) AS event_timestamp,
    platform,
    app_version,
    country,
    if(bi = 1, if(U(sid, 11) < P_BLANK_SENTINEL, '', 'unk'), audio_resolved)  AS audio_language,
    if(bi = 1, if(U(sid, 12) < P_BLANK_SENTINEL, '', 'unk'), sub_resolved)    AS subtitle_language,
    player_version,
    toDateTime64(t0, 3) AS session_start_epoch
FROM
(
    SELECT
        sid, bi, bt, nb, bsz, k, t0,
        video_session_id, user_id, platform, app_version, country, player_version,
        audio_resolved, sub_resolved,
        (bi = 1)                       AS is_first,
        (bi = nb) AND (k = (bsz - 1))  AS is_last,
        1 + toUInt32(cityHash64(sid, bi, k, {SEED:UInt64}) % 4096) AS lut_slot
    FROM
    (
        SELECT
            sid, bi, bt, nb, t0,
            video_session_id, user_id, platform, app_version, country, player_version,
            audio_resolved, sub_resolved,
            -- start and end events sit alone on their beat; middle beats carry
            -- the real burst shape
            if((bi = 1) OR (bi = nb), 1,
               least(20, 1 + toUInt32(round(-(BURST_MEAN - 1) * log(greatest(U(sid, 5000000 + bi), 1e-12)))))) AS bsz
        FROM
        (
            SELECT
                number AS sid,
                ARRIVE_E + toUInt32(floor(U(number, 2) * 60))  AS t0,
                WICKET_E + toUInt32(floor(U(number, 3) * 120)) AS tend,
                -- beats every 40-41s from t0, last beat pinned to tend; the
                -- worst-case tail gap is ~65s, far below the 150s cut, so each
                -- session is ONE unbroken run — arrive, watch, leave.
                toUInt32(ceil((tend - t0) / 40.5)) + 1 AS nb,
                arrayMap(j -> if(j = toInt64(nb), tend,
                               if(j = 1, t0,
                                  t0 + toUInt32((j - 1) * 40 + floor(U(number, 1000000 + j) * 2)))),
                         range(1, nb + 1)) AS beat_ts,
                plat_v[PICK(U(number, 21), plat_c)] AS platform,
                ctry_v[PICK(U(number, 22), ctry_c)] AS country,
                app_v[PICK(U(number, 23), app_c)]   AS app_version,
                ply_v[PICK(U(number, 24), ply_c)]   AS player_version,
                aud_v[PICK(U(number, 25), aud_c)]   AS audio_resolved,
                sub_v[PICK(U(number, 26), sub_c)]   AS sub_resolved,
                hex(SHA256(concat('spike-sess:', toString(number), ':', toString({SEED:UInt64})))) AS video_session_id,
                hex(SHA256(concat('spike-user:', toString(number), ':', toString({SEED:UInt64})))) AS user_id
            FROM numbers_mt({N:UInt64})
        )
        ARRAY JOIN
            beat_ts                 AS bt,
            arrayEnumerate(beat_ts) AS bi
    )
    ARRAY JOIN range(bsz) AS k
);
SQL
  ) || GENOK=0
  if [ "$GENOK" = 0 ]; then
    say "  [gen]  *** FAILED ***"
    say "         $(err_line)"
    [ "$KEEP" = 1 ] || qd default "DROP DATABASE $DBN" >/dev/null
    continue
  fi
  GT1=$(now_ms)
  SPIKE_EVENTS=$(qd "$DBN" 'SELECT count() FROM spike_stage')
  SPIKE_SHAPE=$(qd "$DBN" "SELECT concat(toString(uniqExact(video_session_id)), ' sessions · ', toString(uniqExact(user_id)), ' users · span ', toString(min(event_timestamp)), ' .. ', toString(max(event_timestamp))) FROM spike_stage" | head -1)
  say "  [gen]  $(comma "$SPIKE_EVENTS") spike events staged in $((GT1 - GT0)) ms  ·  $SPIKE_SHAPE"

  # ==========================================================================
  # STREAMING REPLAY — minute-chunks + concurrent publisher + serving probes
  # ==========================================================================
  say ""
  say "  STREAMING REPLAY — one spike minute per chunk, publisher looping beside it."
  say "  probes are ONE-SHOT reads taken mid-ingest: contention is the measurement."
  E0=$(qd default "SELECT toUInt32(toDateTime('$ARRIVE'))" | head -1)
  E1=$(qd default "SELECT toUInt32(toDateTime('$SPIKE_END'))" | head -1)

  STOPF="$TMPD/stop"
  (
    fails=0
    while [ ! -f "$STOPF" ]; do
      if TARGET=local PUBLISH_SETTLE_S=2 tools/publish.sh --database "$DBN" >>"$PUBLOG" 2>&1; then
        fails=0
      else
        fails=$((fails + 1))
        echo "== publish FAILED (consecutive $fails)" >>"$PUBLOG"
        if [ "$fails" -ge 3 ]; then
          echo "== giving up after 3 consecutive failures" >>"$PUBLOG"
          touch "$TMPD/pubdead"; break
        fi
      fi
      sleep 1
    done
  ) &
  PUBPID=$!

  say "  $(printf '%-8s %10s %10s %7s %7s %10s %8s %9s %9s' 'minute' 'rows' 'ins ms' 'parts' 'merges' 'pending' 'lag s' 'Q1 ms' 'Q7 ms')"
  ING0=$(now_ms)
  WORST_Q1=0; WORST_Q7=0; WORST_INS=0; MAX_PARTS=0; MAX_MERGES=0; MAX_PENDING=0
  m=$E0
  while [ "$m" -lt "$E1" ]; do
    T0=$(now_ms)
    qd "$DBN" "INSERT INTO ev_raw (content_id, video_session_id, user_id, event_type, event, event_timestamp,
                                   platform, app_version, country, audio_language, subtitle_language,
                                   player_version, session_start_epoch)
               SELECT content_id, video_session_id, user_id, event_type, event, event_timestamp,
                      platform, app_version, country, audio_language, subtitle_language,
                      player_version, session_start_epoch
               FROM spike_stage
               WHERE event_timestamp >= toDateTime64($m,3) AND event_timestamp < toDateTime64($((m + 60)),3)" >/dev/null
    T1=$(now_ms); INS=$((T1 - T0))
    ROWS=$(qd "$DBN" "SELECT count() FROM spike_stage WHERE event_timestamp >= toDateTime64($m,3) AND event_timestamp < toDateTime64($((m + 60)),3)" | head -1)
    PARTS=$(qd default "SELECT count() FROM system.parts WHERE database='$DBN' AND table='ev_raw' AND active" | head -1)
    MERGES=$(qd default "SELECT count() FROM system.merges WHERE database='$DBN'" | head -1)
    LAGROW=$(qd "$DBN" "SELECT if(publish_cursor IS NULL OR publish_cursor < toDateTime64('2000-01-01 00:00:00',3), '-', toString(publish_lag_s)), toString(pending_sessions) FROM v_cc_publish_lag" | head -1)
    LAG=$(printf '%s' "$LAGROW" | cut -f1); PEND=$(printf '%s' "$LAGROW" | cut -f2)
    Q1=$(probe_ms "$DBN" "SELECT max(concurrent) FROM v_concurrency_minute_delta_total")
    Q7=$(probe_ms "$DBN" "SELECT count() FROM (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS c FROM cc_minute_delta WHERE minute >= toDateTime('$ARRIVE') AND minute < toDateTime('$ARRIVE') + INTERVAL 1 HOUR GROUP BY minute)")
    say "  $(printf '%-8s %10s %10s %7s %7s %10s %8s %9s %9s' \
        "$(qd default "SELECT formatDateTime(toDateTime($m),'%H:%i')" | head -1)" \
        "$(comma "$ROWS")" "$INS" "$PARTS" "$MERGES" "$(comma "$PEND")" "$LAG" "$Q1" "$Q7")"
    [ "$INS" -gt "$WORST_INS" ] && WORST_INS=$INS
    [ "${PARTS:-0}" -gt "$MAX_PARTS" ] 2>/dev/null && MAX_PARTS=$PARTS
    [ "${MERGES:-0}" -gt "$MAX_MERGES" ] 2>/dev/null && MAX_MERGES=$MERGES
    [ "${PEND:-0}" -gt "$MAX_PENDING" ] 2>/dev/null && MAX_PENDING=$PEND
    WORST_Q1=$(python3 -c "
a='$WORST_Q1'; b='$Q1'
try: print(max(float(a), float(b)))
except Exception: print(a)")
    WORST_Q7=$(python3 -c "
a='$WORST_Q7'; b='$Q7'
try: print(max(float(a), float(b)))
except Exception: print(a)")
    [ "$CHUNK_PACE_S" != 0 ] && sleep "$CHUNK_PACE_S"
    m=$((m + 60))
  done
  ING1=$(now_ms)
  INGEST_S=$(python3 -c "print(round(($ING1 - $ING0)/1000.0, 1))")
  RATE=$(python3 -c "print(f'{int($SPIKE_EVENTS/(($ING1 - $ING0)/1000.0)):,}')")
  say "  ingest wall $INGEST_S s for $(comma "$SPIKE_EVENTS") events ($RATE ev/s inserted)"

  # ---- drain: how long until the serving layer has absorbed the spike? -----
  DR0=$(now_ms); DRAINED=""; PUBDEAD=""
  while :; do
    [ -f "$TMPD/pubdead" ] && { PUBDEAD=1; break; }
    ROW=$(qd "$DBN" "SELECT toString(pending_sessions), toString(runs_in_flight) FROM v_cc_publish_lag" | head -1)
    P=$(printf '%s' "$ROW" | cut -f1); F=$(printf '%s' "$ROW" | cut -f2)
    if [ "$P" = "0" ] && [ "$F" = "0" ]; then DRAINED=1; break; fi
    [ $(( $(now_ms) - DR0 )) -gt 900000 ] && break
    sleep 2
  done
  DR1=$(now_ms)
  touch "$STOPF"; wait "$PUBPID" 2>/dev/null
  if [ -n "$DRAINED" ]; then
    say "  publisher DRAINED $((DR1 - DR0)) ms after the last insert — the serving layer has absorbed the spike"
  elif [ -n "$PUBDEAD" ]; then
    say "  *** publisher DIED during the spike (3 consecutive failures) — $PUBLOG has the errors ***"
    say "      last error: $(grep -B1 'publish FAILED' "$PUBLOG" | grep -o 'DB::Exception:.*' | tail -1 | cut -c1-200)"
  else
    say "  *** publisher did NOT drain within 900 s of the last insert ***"
  fi

  # ---- the publisher's own story: every run, every phase, from its WAL -----
  say ""
  say "  PUBLISH RUNS through the spike (cc_publish_runs — the finalizer's own log):"
  say "  $(printf '%-4s %10s %9s %9s %9s %9s %9s %9s %10s' run sessions 'negate' 'derive' 'prune' 'emit' 'hours' 'users' 'total ms')"
  say "$(qd "$DBN" "
    SELECT concat('  ', lpad(toString(rn), 4, ' '),
                  lpad(toString(any(sessions)), 10, ' '),
                  lpad(toString(sumIf(elapsed_ms, phase = 'negated')), 9, ' '),
                  lpad(toString(sumIf(elapsed_ms, phase = 'derived')), 9, ' '),
                  lpad(toString(sumIf(elapsed_ms, phase = 'pruned')), 9, ' '),
                  lpad(toString(sumIf(elapsed_ms, phase = 'emitted')), 9, ' '),
                  lpad(toString(sumIf(elapsed_ms, phase = 'hours')), 9, ' '),
                  lpad(toString(sumIf(elapsed_ms, phase = 'users')), 9, ' '),
                  lpad(toString(sum(elapsed_ms)), 10, ' '),
                  if(countIf(phase = 'committed') = 0, '  IN FLIGHT/DIED', ''))
    FROM (SELECT *, dense_rank() OVER (ORDER BY run_id) AS rn FROM cc_publish_runs)
    GROUP BY rn ORDER BY rn FORMAT TSVRaw")"
  RUNS_N=$(qd "$DBN" "SELECT uniqExact(run_id) FROM cc_publish_runs" | head -1)
  MAX_RUN_MS=$(qd "$DBN" "SELECT max(t) FROM (SELECT sum(elapsed_ms) AS t FROM cc_publish_runs GROUP BY run_id)" | head -1)
  MAX_CLAIM=$(qd "$DBN" "SELECT max(sessions) FROM cc_publish_runs WHERE phase = 'claimed'" | head -1)
  say ""
  say "  worst run: $MAX_RUN_MS ms  ·  biggest claim: $(comma "$MAX_CLAIM") sessions  ·  $RUNS_N runs total"
  say "  VERDICT at the real 60s heartbeat cadence: $(python3 -c "
m='$MAX_RUN_MS'
try:
    m=float(m)
    print('STABLE — worst run %.1f s < 60 s: the publisher outruns a live spike of this size' % (m/1000)
          if m < 60000 else
          'UNSTABLE — worst run %.1f s > 60 s: markings arrive faster than a run retires them; lag grows for as long as the spike lasts' % (m/1000))
except Exception: print('publisher died — see above')")"

  # user-tier churn from the spike's repeated re-derivations (ADR 0016 rows-only-grow)
  UM_PHYS=$(qd "$DBN" "SELECT count() FROM cc_user_minute" | head -1)
  UM_KEYS=$(qd "$DBN" "SELECT count() FROM cc_user_minute FINAL" | head -1)
  say "  user-tier churn: $(comma "$UM_PHYS") physical rows over $(comma "$UM_KEYS") logical buckets — every re-publish of a touched minute appends superseding versions"

  # ---- correctness of the INCREMENTAL path, post-drain ---------------------
  say ""
  if [ -n "$DRAINED" ]; then
    RECON_INC=$(reconcile_deltas "$DBN")
    say "  GATE (incremental path — publisher-maintained deltas vs interval expansion): $RECON_INC"
  else
    RECON_INC="NOT RUN (publisher did not drain)"
    say "  GATE (incremental path): $RECON_INC"
  fi
  PEAK_ROW=$(qd "$DBN" "SELECT concat(toString(max(concurrent)), ' @ ', toString(argMax(minute, concurrent))) FROM v_concurrency_minute_delta_total" | head -1)
  say "  peak on the spike day: $PEAK_ROW  (baseline was $BASE_PEAK; spike adds ~$(comma "$N"))"

  # ---- the delta table under a spike: concentration, not bloat -------------
  say ""
  say "  DELTA ACCOUNTING — what a spike actually does to cc_minute_delta."
  say "  The naive fear: '+1 at open, -1 at close means a huge number of rows at"
  say "  one minute key'. Measured: the ADR 0008 grain collapses N sessions into"
  say "  the DIMS fan-out at that minute — the magnitude lands in sum(starts),"
  say "  not in row count."
  SPIKE_DL_ROWS=$(qd "$DBN" "SELECT count() FROM cc_minute_delta WHERE minute >= toDateTime('$ARRIVE') AND minute < toDateTime('$SPIKE_END')" | head -1)
  say "  delta rows in the spike window (10:40..11:16): $(comma "$SPIKE_DL_ROWS")"
  say "  $(printf '%-22s %12s %12s %12s' 'minute' 'opens' 'closes' 'net')"
  say "$(qd "$DBN" "
    SELECT concat('  ', rpad(toString(minute), 22, ' '),
                  lpad(toString(toInt64(sum(starts))), 12, ' '),
                  lpad(toString(toInt64(sum(ends))), 12, ' '),
                  lpad(toString(toInt64(sum(delta))), 12, ' '))
    FROM cc_minute_delta
    WHERE minute IN (toDateTime('$ARRIVE'), toDateTime('$ARRIVE') + INTERVAL 1 MINUTE,
                     toDateTime('2026-07-26 10:59:00'), toDateTime('2026-07-26 11:00:00'),
                     toDateTime('$WICKET'), toDateTime('$WICKET') + INTERVAL 1 MINUTE,
                     toDateTime('$WICKET') + INTERVAL 2 MINUTE)
    GROUP BY minute ORDER BY minute FORMAT TSVRaw")"
  XING=$(qd "$DBN" "SELECT count() FROM session_intervals FINAL WHERE interval_start < toDateTime64('2026-07-26 11:00:00',3) AND interval_end >= toDateTime64('2026-07-26 11:00:00',3)" | head -1)
  say "  intervals crossing 11:00: $(comma "$XING") — each is hour-clipped in two (ADR 0003):"
  say "  the 10:59/11:00 rows above carry a close+reopen for every one of them."

  # ---- post-drain storage & merge pressure ---------------------------------
  say ""
  say "  STORAGE after the spike (active parts; no OPTIMIZE FINAL first):"
  say "  $(printf '%-22s %14s %12s %8s' 'table' 'rows' 'on disk' 'parts')"
  say "$(qd "$DBN" "
    SELECT concat('  ', rpad(table, 22, ' '),
                  lpad(formatReadableQuantity(sum(rows)), 14, ' '),
                  lpad(formatReadableSize(sum(data_compressed_bytes)), 12, ' '),
                  lpad(toString(count()), 8, ' '))
    FROM system.parts WHERE database='$DBN' AND active
      AND table IN ('ev_raw','session_intervals','cc_minute_delta','cc_hour_agg','cc_user_minute','session_dirty')
    GROUP BY table ORDER BY sum(data_compressed_bytes) DESC FORMAT TSVRaw")"
  say "  merge pressure (system.part_log, this database):"
  say "$(qd default "
    SELECT concat('    ', rpad(toString(event_type), 16, ' '),
                  lpad(toString(count()), 8, ' '),
                  lpad(formatReadableSize(sum(size_in_bytes)), 14, ' '),
                  lpad(concat(toString(max(duration_ms)), ' ms slowest'), 18, ' '))
    FROM system.part_log WHERE database='$DBN' AND event_date >= today() - 1
    GROUP BY event_type ORDER BY count() DESC FORMAT TSVRaw")"

  # ==========================================================================
  # BATCH PATH — what a full rebuild costs on a spike day (vs scale.txt shape)
  # ==========================================================================
  say ""
  say "  BATCH REBUILD on the spike day — the scale.txt ladder, spike-shaped."
  build_model "$DBN" "spike_${N}_rebuild" \
    || say "  *** batch rebuild failed at stage '$BUILD_FAILED' — that is the measurement ***"

  if [ -z "$BUILD_FAILED" ]; then
    RECON_BATCH=$(reconcile_deltas "$DBN")
    UGATE=$(user_gate "$DBN")
    case "$UGATE" in PASS*|FAIL*) : ;; *) UGATE="DID NOT COMPLETE — $(printf '%s' "$UGATE" | tr '\n' ' ' | cut -c1-160)" ;; esac
    say "  GATE (batch path — rebuilt deltas vs interval expansion): $RECON_BATCH"
    say "  GATE (user tier vs interval expansion): $UGATE"
  else
    RECON_BATCH="NOT RUN (rebuild failed: $BUILD_FAILED)"; UGATE="NOT RUN"
  fi

  # settled serving latency, post-everything
  SET_Q1=$(probe_ms "$DBN" "SELECT max(concurrent) FROM v_concurrency_minute_delta_total")
  SET_Q7=$(probe_ms "$DBN" "SELECT count() FROM (SELECT minute, toInt64(sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)) AS c FROM cc_minute_delta WHERE minute >= toDateTime('$ARRIVE') AND minute < toDateTime('$ARRIVE') + INTERVAL 1 HOUR GROUP BY minute)")
  say "  settled serving probes: peak ${SET_Q1} ms · dashboard hour curve ${SET_Q7} ms  (idle baseline: ${IDLE_Q1} / ${IDLE_Q7} ms)"

  INGEST_SUM+=("$N|$SPIKE_EVENTS|$INGEST_S|$RATE|$MAX_PARTS|$MAX_MERGES|$WORST_INS|$IDLE_Q1|$WORST_Q1|$WORST_Q7")
  PUBLISH_SUM+=("$N|$RUNS_N|$MAX_CLAIM|$MAX_RUN_MS|$([ -n "$DRAINED" ] && echo $((DR1 - DR0)) || echo "-")|$([ -n "$PUBDEAD" ] && echo DIED || { [ -n "$DRAINED" ] && echo drained || echo stuck; })")
  GATE_SUM+=("$N|$RECON_INC|$RECON_BATCH|$UGATE|$PEAK_ROW")

  rm -rf "$TMPD"
  [ "$KEEP" = 1 ] || qd default "DROP DATABASE $DBN" >/dev/null
done

# ============================================================================
# summary tables
# ============================================================================
hr
say "SUMMARY — INGESTION under the spike"
hr
say "$(printf '%-8s %12s %10s %10s %7s %7s %10s %9s %10s %10s' N events 'wall s' 'ev/s' parts merges 'worst ins' 'idle Q1' 'worst Q1' 'worst Q7')"
for r in "${INGEST_SUM[@]}"; do
  IFS='|' read -r a b c d e f g h i j <<< "$r"
  say "$(printf '%-8s %12s %10s %10s %7s %7s %10s %9s %10s %10s' "$a" "$(comma "$b")" "$c" "$d" "$e" "$f" "${g} ms" "${h} ms" "${i} ms" "${j} ms")"
done
hr
say "SUMMARY — the PUBLISHER through the spike (the part scale.txt said would hurt)"
hr
say "$(printf '%-8s %6s %14s %12s %12s %10s' N runs 'max claim' 'worst run' 'drain ms' outcome)"
for r in "${PUBLISH_SUM[@]}"; do
  IFS='|' read -r a b c d e f <<< "$r"
  say "$(printf '%-8s %6s %14s %12s %12s %10s' "$a" "$b" "$(comma "$c")" "${d} ms" "$e" "$f")"
done
say ""
say "  Read 'worst run' against the REAL 60s heartbeat cadence: during a live"
say "  spike every open session re-marks itself dirty every minute, so each"
say "  run's claim is the WHOLE spike audience and the publisher is stable"
say "  only while one run finishes inside one minute."
hr
say "SUMMARY — the GATES on a spike day (correctness under skew is not implied"
say "by correctness under uniform load; here it is measured)"
hr
for r in "${GATE_SUM[@]}"; do
  IFS='|' read -r a b c d e <<< "$r"
  say "  N=$a"
  say "    incremental path : $b"
  say "    batch path       : $c"
  say "    user tier        : $d"
  say "    peak             : $e"
done
hr
say "BATCH REBUILD COST — per stage (compare shapes against evidence/scale.txt)"
hr
say "$(printf '%-22s %-24s %12s %14s' run stage ms 'peak memory')"
for r in "${REBUILD[@]}"; do
  IFS='|' read -r a b c d <<< "$r"
  say "$(printf '%-22s %-24s %12s %14s' "$a" "$b" "$c" "$(fmt "$d")")"
done
hr
say "scratch databases $( [ "$KEEP" = 1 ] && echo 'KEPT (KEEP=1)' || echo 'dropped' ) · sonyliv never written"
say "regenerate: tools/spike-test.sh ${MAGS[*]}"
