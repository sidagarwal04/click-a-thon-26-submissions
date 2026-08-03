#!/usr/bin/env bash
# ============================================================================
# tools/landing-test.sh — the proof for ADR 0030: the all-String landing table.
#
#   tools/landing-test.sh
#
# Six things, in order, all against the LOCAL container only:
#
#   1 IDENTITY   the real 905,558-row file loaded through the landing table is
#                BYTE-IDENTICAL in ev_raw and content_dim to the same file
#                loaded by the pre-landing typed-input() statement. The
#                reference statement is written out here in full rather than
#                fetched from git, so this test keeps meaning something after
#                the old loader has scrolled out of history.
#   1b GATE      and a model built on that database still reconciles against raw
#                at 17,028 minutes / 0 mismatched / peak 2,917.
#   2 BLAST      the measured defect: the real file with exactly ONE corrupted
#                event_timestamp. The old statement loses all 905,558 rows and
#                leaves content_dim populated; the loader must lose ONE.
#   3 SWEEP      one file per malformation class, so each is measured alone.
#                Mirrors the table in docs/codex-validation/004-triage.md §D1.
#   4 ROLLBACK   a phase-B failure (an INSERT-time fault, not a data one) must
#                leave the typed tables exactly as it found them — and a
#                REFUSED load must not even create the landing tables.
#   5 COST       load time and storage, landing vs not. The point is to state
#                the price, not to pretend there isn't one.
#
# SAFETY: local container only, never CH_HOST / Cloud, and only into databases
# named landtest_*. The graded database `sonyliv` and the local real-data
# database `default` are unreachable from here — every query names its database
# and the name is asserted below.
# ============================================================================
set -uo pipefail        # NOT -e: several cases below are SUPPOSED to fail
cd "$(dirname "$0")/.."

RAW="${1:-data/ch-hackathon-raw-data.csv}"
CONTENT="${2:-data/ch-hackathon-content-data.csv}"
OUT=evidence/landing/identity.txt
PREFIX=landtest
PASS=0; FAIL=0

[ -f "$RAW" ]     || { echo "missing $RAW — run tools/fetch_data.sh"     >&2; exit 2; }
[ -f "$CONTENT" ] || { echo "missing $CONTENT — run tools/fetch_data.sh" >&2; exit 2; }
docker inspect ch >/dev/null 2>&1 || { echo "the 'ch' container is not running" >&2; exit 2; }

mkdir -p evidence/landing
TMP="$(mktemp -d)"; chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT

q()  { docker exec -i ch clickhouse-client --database "$1" --query "$2" < /dev/null; }
q1() { q "$1" "$2 FORMAT TSVRaw" | tr -d '\r\n'; }
sys(){ docker exec -i ch clickhouse-client --query "$1" < /dev/null; }

db() {  # db <suffix> — a fresh scratch database with the ingest schema applied
  local d="${PREFIX}_$1"
  case "$d" in "$PREFIX"_*) ;; *) echo "refusing database name $d" >&2; exit 2 ;; esac
  sys "DROP DATABASE IF EXISTS $d" > /dev/null
  sys "CREATE DATABASE $d" > /dev/null
  docker exec -i ch clickhouse-client --database "$d" --multiquery < sql/00_schema.sql   > /dev/null
  docker exec -i ch clickhouse-client --database "$d" --multiquery < sql/01_policy.sql   > /dev/null
  docker exec -i ch clickhouse-client --database "$d" --multiquery < sql/10_intervals.sql > /dev/null
  echo "$d"
}

ok()   { PASS=$((PASS+1)); printf '  PASS  %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$*"; }
check(){ [ "$2" = "$3" ] && ok "$1 = $2" || bad "$1: got $2, expected $3"; }

# The pre-landing loader's statement, verbatim. This is the reference identity
# 1 compares against — if it is ever edited, it stops being a reference.
OLD_RAW_SQL="INSERT INTO ev_raw (content_id, video_session_id, user_id, event_type, event, event_timestamp, platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch) SELECT content_id, video_session_id, user_id, event_type, event, toDateTime64(event_timestamp/1000, 3), platform, app_version, country, audio_language, subtitle_language, player_version, toDateTime64(session_start_epoch/1000, 3) FROM input('content_id Int64, video_session_id String, user_id String, event_type String, event String, event_timestamp UInt64, platform String, app_version String, country String, audio_language String, subtitle_language String, player_version String, session_start_epoch UInt64') FORMAT CSVWithNames"
OLD_CONTENT_SQL="INSERT INTO content_dim (content_id, title, video_type, category) SELECT content_id, title, video_type, category FROM input('content_id Int64, title String, video_type String, category String') FORMAT CSVWithNames"

old_load() {  # old_load <db> <raw> <content> — the pre-landing path, content FIRST
  docker exec -i ch clickhouse-client --database "$1" --query "$OLD_CONTENT_SQL" < "$3" > /dev/null 2>&1
  docker exec -i ch clickhouse-client --database "$1" --query "$OLD_RAW_SQL"     < "$2" > /dev/null 2>&1
  echo $?
}

# An order-free fingerprint of every column, so the comparison does not depend
# on part layout or insert order. sum and bitXor are both commutative; two
# different functions because either alone can collide.
FP_RAW="SELECT concat(toString(count()), ' ',
       toString(sum(cityHash64(content_id, video_session_id, user_id, event_type, event,
                    toString(event_timestamp), platform, app_version, country, audio_language,
                    subtitle_language, player_version, toString(session_start_epoch), toString(extra)))), ' ',
       toString(groupBitXor(cityHash64(content_id, video_session_id, user_id, event_type, event,
                    toString(event_timestamp), platform, app_version, country, audio_language,
                    subtitle_language, player_version, toString(session_start_epoch), toString(extra)))))
FROM ev_raw"
FP_CONTENT="SELECT concat(toString(count()), ' ',
       toString(sum(cityHash64(content_id, title, video_type, category, toString(extra)))), ' ',
       toString(groupBitXor(cityHash64(content_id, title, video_type, category, toString(extra)))))
FROM content_dim"

{
echo "LANDING BOUNDARY (ADR 0030) — proof"
echo "commit: $(git rev-parse --short HEAD 2>/dev/null || echo n/a)   server: $(q1 default 'SELECT version()')"
echo "raw: $RAW   content: $CONTENT"
echo

# ---------------------------------------------------------------------------
echo "== 1  IDENTITY — the happy path is unchanged, byte for byte"
echo
D_OLD="$(db ident_old)"; D_NEW="$(db ident_new)"
# Section 5 reads system.query_log for these two loads. The scratch databases are
# dropped and recreated under the SAME NAMES every run, so without a start mark
# the cost section silently sums this run and every previous one.
RUN_START="$(q1 default 'SELECT now()')"
old_load "$D_OLD" "$RAW" "$CONTENT" > /dev/null
tools/load.sh --database "$D_NEW" "$RAW" "$CONTENT" > /dev/null 2>&1
RUN_END="$(q1 default 'SELECT now()')"   # section 1b builds the model into D_NEW
FP_O="$(q1 "$D_OLD" "$FP_RAW")";     FP_N="$(q1 "$D_NEW" "$FP_RAW")"
FC_O="$(q1 "$D_OLD" "$FP_CONTENT")"; FC_N="$(q1 "$D_NEW" "$FP_CONTENT")"
echo "  ev_raw      pre-landing : $FP_O"
echo "  ev_raw      landing     : $FP_N"
echo "  content_dim pre-landing : $FC_O"
echo "  content_dim landing     : $FC_N"
echo "  (count · sum of per-row cityHash64 over every column · bitXor of the same)"
echo
[ "$FP_O" = "$FP_N" ] && ok "ev_raw fingerprint identical"      || bad "ev_raw fingerprint DIFFERS"
[ "$FC_O" = "$FC_N" ] && ok "content_dim fingerprint identical" || bad "content_dim fingerprint DIFFERS"
check "landing produced no cast-ledger rows" "$(q1 "$D_NEW" 'SELECT count() FROM ev_cast_quarantine')" 0

# ---------------------------------------------------------------------------
echo
echo "== 1b THE GATE — a model built through the landing table still reconciles"
echo "   (sql/90_reconcile.sql recomputes from ev_raw with a different implementation"
echo "    of the same spec, so it tests the pipeline instead of agreeing with itself)"
echo
CH_DATABASE_LOCAL="$D_NEW" TARGET=local tools/build-model.sh 2>&1 | sed 's/^/    /'
echo
docker exec -i ch clickhouse-client --database "$D_NEW" --format PrettyCompactNoEscapes \
  < sql/90_reconcile.sql 2>&1 | sed 's/^/  /' | tee "$TMP/gate.txt"
echo
if grep -q MISMATCH "$TMP/gate.txt"; then bad "the gate reported a MISMATCH"; else ok "no MISMATCH"; fi
GATE_SUMMARY="$(grep -o 'minutes_compared=[0-9]*' "$TMP/gate.txt" | head -1 | cut -d= -f2)"
GATE_MISMATCH="$(grep -o 'mismatched=[0-9]*' "$TMP/gate.txt" | head -1 | cut -d= -f2)"
GATE_PEAK="$(grep -o 'peak=[0-9]*' "$TMP/gate.txt" | head -1 | cut -d= -f2)"
check "minutes compared" "$GATE_SUMMARY" 17028
check "mismatched"       "$GATE_MISMATCH" 0
check "peak"             "$GATE_PEAK" 2917

# ---------------------------------------------------------------------------
echo
echo "== 2  BLAST RADIUS — the real file, exactly one corrupted event_timestamp"
echo "   (docs/codex-validation/004-triage.md §D1 corrupted data row 499,999 the same way)"
echo
python3 - "$RAW" "$TMP/corrupt.csv" <<'PY'
import csv, sys
src, out = sys.argv[1], sys.argv[2]
with open(src, newline="") as f, open(out, "w", newline="") as g:
    r = csv.reader(f); w = csv.writer(g)
    hdr = next(r); w.writerow(hdr); ti = hdr.index("event_timestamp")
    for n, row in enumerate(r, 1):
        if n == 499999:
            row[ti] = "NOT_A_TIMESTAMP"
        w.writerow(row)
PY
TOTAL="$(( $(grep -c "" "$TMP/corrupt.csv") - 1 ))"
D_OLD="$(db blast_old)"; D_NEW="$(db blast_new)"
old_load "$D_OLD" "$TMP/corrupt.csv" "$CONTENT" > /dev/null
tools/load.sh --database "$D_NEW" "$TMP/corrupt.csv" "$CONTENT" > /dev/null 2>&1
NEW_RC=$?
printf '  %-14s %12s %12s\n' "" "pre-landing" "landing"
printf '  %-14s %12s %12s\n' "ev_raw"      "$(q1 "$D_OLD" 'SELECT count() FROM ev_raw')"      "$(q1 "$D_NEW" 'SELECT count() FROM ev_raw')"
printf '  %-14s %12s %12s\n' "content_dim" "$(q1 "$D_OLD" 'SELECT count() FROM content_dim')" "$(q1 "$D_NEW" 'SELECT count() FROM content_dim')"
echo
check "one bad row costs one row (of $TOTAL)" "$(q1 "$D_NEW" 'SELECT count() FROM ev_raw')" "$((TOTAL - 1))"
check "the loader still succeeds"             "$NEW_RC" 0
check "content_dim is whole, not half"        "$(q1 "$D_NEW" 'SELECT count() FROM content_dim')" "$(q1 "$D_OLD" 'SELECT count() FROM content_dim')"
check "the row is in the ledger"              "$(q1 "$D_NEW" "SELECT sum(copies) FROM ev_cast_quarantine FINAL WHERE disposition = 'rejected'")" 1
check "its raw text survived"                 "$(q1 "$D_NEW" "SELECT any(raw['event_timestamp']) FROM ev_cast_quarantine FINAL")" NOT_A_TIMESTAMP
echo
echo "  the ledger entry:"
q "$D_NEW" "SELECT source, reason, disposition, detail, copies FROM ev_cast_quarantine FINAL FORMAT PrettyCompactNoEscapes"

# ---------------------------------------------------------------------------
echo
echo "== 3  SWEEP — one malformation per file, each measured alone"
echo
python3 - "$TMP" <<'PY'
import csv, os, sys
tmp = sys.argv[1]
HDR = ["content_id","video_session_id","user_id","event_type","event","event_timestamp",
       "platform","app_version","country","audio_language","subtitle_language",
       "player_version","session_start_epoch"]
GOOD = 1785063241252
CASES = {"clean":"1785063241252", "text":"NOT_A_TIMESTAMP", "negative":"-1",
         "decimal":"1785063241252.7", "empty":"", "seconds":"1785063241",
         "overflow":"999999999999999999999999", "quoted":'"1785063241252"'}
os.makedirs(f"{tmp}/sweep", exist_ok=True)
for name, ts in CASES.items():
    with open(f"{tmp}/sweep/{name}.csv", "w", newline="") as f:
        f.write(",".join(HDR) + "\n")
        f.write(f"31000001,vs_{name},u_{name},VideoSessionStart,VideoSessionStart,{ts},"
                f"ANDROID,1.0,india,hin,UNK,1.0,{GOOD}\n")
        f.write(f"31000001,vs_{name},u_{name},VideoSessionEnd,VideoSessionEnd,{GOOD+60000},"
                f"ANDROID,1.0,india,hin,UNK,1.0,{GOOD}\n")
with open(f"{tmp}/sweep-content.csv", "w", newline="") as f:
    csv.writer(f).writerows([["content_id","title","video_type","category"],
                             [31000001, "Sweep", "movie", "drama"]])
PY
printf '  %-9s | %-3s %-10s | %-3s %-10s %-28s %s\n' case rc "ev/content" rc "ev/content" "ledger" "min(event_timestamp)"
printf '  %s\n' "----------------------------------------------------------------------------------------------------"
for n in clean text negative decimal empty seconds overflow quoted; do
  D_OLD="$(db sw_old)"; D_NEW="$(db sw_new)"
  ORC="$(old_load "$D_OLD" "$TMP/sweep/$n.csv" "$TMP/sweep-content.csv")"
  tools/load.sh --database "$D_NEW" "$TMP/sweep/$n.csv" "$TMP/sweep-content.csv" > /dev/null 2>&1
  NRC=$?
  printf '  %-9s | %-3s %-10s | %-3s %-10s %-28s %s\n' "$n" "$ORC" \
    "$(q1 "$D_OLD" "SELECT concat(toString((SELECT count() FROM ev_raw)),'/',toString((SELECT count() FROM content_dim)))")" \
    "$NRC" \
    "$(q1 "$D_NEW" "SELECT concat(toString((SELECT count() FROM ev_raw)),'/',toString((SELECT count() FROM content_dim)))")" \
    "$(q1 "$D_NEW" "SELECT if(empty(groupArray(concat(reason,':',disposition))), '-', arrayStringConcat(arraySort(groupArray(concat(reason,':',disposition))),' ')) FROM (SELECT reason, disposition FROM ev_cast_quarantine FINAL)")" \
    "$(q1 "$D_NEW" "SELECT ifNull(toString(min(event_timestamp)),'-') FROM ev_raw")"
done
echo
echo "  Read the two rc columns first: 27 and 72 are whole-file losses. The landing"
echo "  column is 0 everywhere — every class costs its own row and nothing else."
echo
echo "  'seconds' is the one the cast cannot catch: 1785063241 IS a valid UInt64, so"
echo "  no cast can object. It lands in 1970 and is caught one stage later, by ADR"
echo "  0025's ts_out_of_range rule — demonstrated here:"
D_SEC="$(db sec)"
tools/load.sh --database "$D_SEC" "$TMP/sweep/seconds.csv" "$TMP/sweep-content.csv" > /dev/null 2>&1
docker exec -i ch clickhouse-client --database "$D_SEC" --multiquery < sql/15_normalise.sql > /dev/null 2>&1
echo "    cast ledger (load time, ADR 0030): $(q1 "$D_SEC" 'SELECT count() FROM ev_cast_quarantine') rows"
q "$D_SEC" "SELECT reason, rows, sessions, first_seen FROM v_quarantine_summary FORMAT PrettyCompactNoEscapes"
check "the castable-but-wrong timestamp is quarantined by rule" \
  "$(q1 "$D_SEC" "SELECT ifNull(any(reason),'-') FROM v_quarantine_summary")" ts_out_of_range

echo
echo "  What landing does NOT cover: a STRUCTURAL CSV fault — a row with the wrong"
echo "  number of fields — still costs the file, because the failure is in the reader"
echo "  before any column has a value to hold. It does now fail in phase A, so"
echo "  content_dim is no longer left populated beside an empty ev_raw:"
head -1 "$TMP/sweep/clean.csv" > "$TMP/structural.csv"
sed -n '2p' "$TMP/sweep/clean.csv" | cut -d, -f1-12 >> "$TMP/structural.csv"
sed -n '3p' "$TMP/sweep/clean.csv" >> "$TMP/structural.csv"
D_ST="$(db struct)"
tools/load.sh --database "$D_ST" "$TMP/structural.csv" "$TMP/sweep-content.csv" > /dev/null 2>&1
STRC=$?
[ "$STRC" -ne 0 ] && ok "structural fault still refuses the file (exit $STRC)" \
                  || bad "structural fault was accepted"
check "and content_dim was NOT half-populated" "$(q1 "$D_ST" 'SELECT count() FROM content_dim')" 0

# ---------------------------------------------------------------------------
echo
echo "== 4  ROLLBACK — a phase-B fault leaves the typed tables as it found them"
echo
# An INSERT-time fault that has nothing to do with the data: mv_stateless's
# target is gone, so INSERT INTO ev_raw fails after content_dim has committed.
D_RB="$(db rollback)"
sys "DROP TABLE ${D_RB}.cc_minute_stateless" > /dev/null
tools/load.sh --database "$D_RB" "$TMP/sweep/clean.csv" "$TMP/sweep-content.csv" > /dev/null 2>&1
RBRC=$?
[ "$RBRC" -ne 0 ] && ok "the load failed loudly (exit $RBRC)" || bad "the load reported success"
check "ev_raw rolled back"                "$(q1 "$D_RB" 'SELECT count() FROM ev_raw')" 0
check "content_dim rolled back"           "$(q1 "$D_RB" 'SELECT count() FROM content_dim')" 0
check "ev_landing kept — the only record" "$(q1 "$D_RB" 'SELECT count() FROM ev_landing')" 2

echo
echo "  and the same property for a REFUSED load: the loader applies sql/05_landing.sql"
echo "  itself, so it must do that AFTER the double-load guard — a refusal that quietly"
echo "  created three tables would not be a refusal."
D_RF="$(db refuse)"
q "$D_RF" "INSERT INTO ev_raw (video_session_id, event_timestamp) VALUES ('x', now64(3))" > /dev/null
BEFORE_T="$(q1 "$D_RF" "SELECT count() FROM system.tables WHERE database = '$D_RF'")"
tools/load.sh --database "$D_RF" "$TMP/sweep/clean.csv" "$TMP/sweep-content.csv" > /dev/null 2>&1
RFRC=$?
[ "$RFRC" -ne 0 ] && ok "the non-empty database was refused (exit $RFRC)" || bad "a non-empty database was loaded into"
check "object count unchanged by the refusal" \
  "$(q1 "$D_RF" "SELECT count() FROM system.tables WHERE database = '$D_RF'")" "$BEFORE_T"
check "no landing objects created"            \
  "$(q1 "$D_RF" "SELECT count() FROM system.tables WHERE database = '$D_RF' AND name LIKE '%landing%'")" 0

# ---------------------------------------------------------------------------
echo
echo "== 5  COST — what the extra materialisation actually costs"
echo
sys "SYSTEM FLUSH LOGS" > /dev/null 2>&1
echo "  storage, after loading the real file (ev_raw + content_dim vs what landing adds):"
q "${PREFIX}_ident_new" "
SELECT formatReadableSize(sumIf(bytes_on_disk, table IN ('ev_raw','content_dim')))    AS typed,
       formatReadableSize(sumIf(bytes_on_disk, table IN ('ev_landing','content_landing','ev_cast_quarantine'))) AS landing_adds,
       round(100.0*sumIf(bytes_on_disk, table IN ('ev_landing','content_landing','ev_cast_quarantine'))
             / sumIf(bytes_on_disk, table IN ('ev_raw','content_dim')), 1)            AS pct_over_typed
FROM system.parts WHERE active AND database = '${PREFIX}_ident_new' FORMAT PrettyCompactNoEscapes"
echo
echo "  server-side INSERT time and bytes read for the two identity loads above."
echo "  Wall clock is not reported: this container is shared with other worktrees"
echo "  and its wall clock swings ~2x run to run. See ADR 0030 for a 14-run series."
q "${PREFIX}_ident_new" "
SELECT if(current_database = '${PREFIX}_ident_old', 'pre-landing', 'landing') AS route,
       sum(query_duration_ms) AS server_ms, formatReadableSize(sum(read_bytes)) AS read, count() AS statements
FROM system.query_log
WHERE type = 'QueryFinish' AND query_kind = 'Insert'
  AND event_time BETWEEN toDateTime('$RUN_START') AND toDateTime('$RUN_END')
  AND current_database IN ('${PREFIX}_ident_old', '${PREFIX}_ident_new')
  -- the six INGEST statements only. Section 1b builds the model into the same
  -- database, and its INSERTs would otherwise be charged to the landing route.
  AND (startsWith(query, 'INSERT INTO ev_raw')      OR startsWith(query, 'INSERT INTO content_dim')
    OR startsWith(query, 'INSERT INTO ev_landing')  OR startsWith(query, 'INSERT INTO content_landing')
    OR startsWith(query, 'INSERT INTO ev_cast_quarantine'))
GROUP BY route ORDER BY route FORMAT PrettyCompactNoEscapes"
echo
echo "  ev_landing is the whole cost and it is reclaimable in one statement once a"
echo "  load is verified — TRUNCATE TABLE ev_landing. What that gives up is the raw"
echo "  text of the rows that DID type; the rows that did not are in the ledger,"
echo "  which is tiny. --replace already truncates it."

echo
echo "------------------------------------------------------------"
if [ "$FAIL" -eq 0 ]; then
  echo "landing test PASSED · $PASS assertions"
else
  echo "landing test FAILED · $FAIL of $((PASS + FAIL)) assertions"
fi
echo "------------------------------------------------------------"
} 2>&1 | tee "$OUT"

for s in ident_old ident_new blast_old blast_new sw_old sw_new sec struct rollback refuse; do
  sys "DROP DATABASE IF EXISTS ${PREFIX}_${s}" > /dev/null 2>&1
done

grep -q "landing test PASSED" "$OUT" || exit 1
echo
echo "evidence written to $OUT"
