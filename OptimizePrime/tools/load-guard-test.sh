#!/usr/bin/env bash
# ============================================================================
# tools/load-guard-test.sh — NEGATIVE TESTS for tools/load.sh and
# tools/apply-sql.sh: the double-load guard (bug 8) and database resolution
# (bug 11), docs/SESSION-2026-08-01.md §4.
#
#   tools/load-guard-test.sh
#
# A guard that has never been seen to refuse is not a guard. Every case below
# either makes the scripts FAIL in the way they now claim to fail, or proves a
# load landed in the database that was asked for and nowhere else.
#
# ISOLATION — the same shape sql/70_truncation_test.sql uses.
#   Cloud:  sonyliv_lgtest_a, sonyliv_lgtest_b   (created here, DROPped on exit)
#   Local:  scratch_lgtest                        (created here, DROPped on exit)
# The graded database `sonyliv` is READ ONLY here: its ev_raw count is recorded
# before and after and the run fails if it moved by one row. No test writes it.
#
# DATA — a synthetic 200-row CSV generated below, so the test does not depend on
# the 233 MB delivered file being present in this worktree. It only has to parse
# and count; nothing here reads concurrency out of it.
# ============================================================================
set -uo pipefail       # NOT -e: this script expects commands to fail, and checks
cd "$(dirname "$0")/.."
REPO="$PWD"

PROD=sonyliv
CDB_A=sonyliv_lgtest_a
CDB_B=sonyliv_lgtest_b
LDB=scratch_lgtest
ROWS=200

# Read .env only for connection details. The database name is never taken from
# here — every case states its own, which is the whole subject of the test.
[ -f .env ] || { echo "no .env — cannot reach ClickHouse" >&2; exit 2; }
set -a; . ./.env; set +a
# ...and then drop the database names it carries. Leaving CH_DATABASE exported
# would make every child invocation below inherit `sonyliv` from the environment,
# which is precisely the input each case is supposed to control.
unset CH_DATABASE CH_DATABASE_LOCAL
HOST="${CH_HOST#https://}"; HOST="${HOST#http://}"; HOST="${HOST%/}"

for db in "$CDB_A" "$CDB_B" "$LDB"; do
  [ "$db" != "$PROD" ] || { echo "refusing: a scratch name equals $PROD" >&2; exit 2; }
done

TMP="$(mktemp -d)"; chmod 700 "$TMP"
PASS=0
FAIL=0

cloud() {  # cloud <sql> — one statement, connected to `default`, never to a test db
  curl -sS --fail-with-body "https://${HOST}:${CH_PORT}/?database=default" \
    --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"
}
cloud1() { cloud "$1 FORMAT TSVRaw" | tr -d '\r\n'; }
local1() { docker exec -i ch clickhouse-client --query "$1 FORMAT TSVRaw" < /dev/null | tr -d '\r\n'; }

cleanup() {
  cloud "DROP DATABASE IF EXISTS $CDB_A" > /dev/null 2>&1 || true
  cloud "DROP DATABASE IF EXISTS $CDB_B" > /dev/null 2>&1 || true
  docker exec -i ch clickhouse-client --query "DROP DATABASE IF EXISTS $LDB" > /dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

ok()  { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$*"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$*"; }
eq()  { # eq <what> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1 = $2"; else bad "$1: expected $2, got $3"; fi
}
case_() { printf '\n%s\n' "-- $* ------------------------------------------------"; }

# --- the synthetic day ------------------------------------------------------
# Every identifier is deliberately impossible in the delivered data — negative
# content ids in the -777xxx range, `lgtest-` prefixed session and user ids. If a
# regression ever lands these rows in a database this test did not create, they
# can be found and deleted by predicate. That is not hypothetical: run this file
# against the PRE-FIX loader and case 11 loads into the local `default` database.
{
  echo 'content_id,video_session_id,user_id,event_type,event,event_timestamp,platform,app_version,country,audio_language,subtitle_language,player_version,session_start_epoch'
  i=0
  while [ $i -lt $ROWS ]; do
    ts=$((1784937600000 + i * 60000))
    echo "$((-777001 - i % 7)),lgtest-vs$((i % 20)),lgtest-u$((i % 11)),Heartbeat,heartbeat,$ts,LGTEST,0.0.0,lgtest,hin,none,0.0,1784937600000"
    i=$((i + 1))
  done
} > "$TMP/raw.csv"
printf 'content_id,title,video_type,category\n-777001,lgtest,lgtest,lgtest\n' > "$TMP/content.csv"

# --- sandboxes: .env copies that name a DIFFERENT database than the caller ---
# tools/load.sh does not cd to the repo root, so ./.env is whatever directory it
# is invoked from. That is how the old precedence bug is exercised: environment
# vs file, disagreeing, in one command.
mk_sandbox() {  # mk_sandbox <dir> <db-or-empty>
  mkdir -p "$1"; chmod 700 "$1"
  if [ -n "$2" ]; then sed "s|^CH_DATABASE=.*|CH_DATABASE=$2|" .env > "$1/.env"
  else                 grep -v '^CH_DATABASE=' .env > "$1/.env"
  fi
  chmod 600 "$1/.env"
}
mk_sandbox "$TMP/sb_a" "$CDB_A"
mk_sandbox "$TMP/sb_none" ""

echo "load-guard test · commit $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
echo "cloud $HOST · scratch $CDB_A, $CDB_B · local $LDB · $ROWS synthetic rows"

PROD_BEFORE=$(cloud1 "SELECT count() FROM $PROD.ev_raw")
echo "graded $PROD.ev_raw before: $PROD_BEFORE (must not move)"

cloud "CREATE DATABASE IF NOT EXISTS $CDB_A" > /dev/null
cloud "CREATE DATABASE IF NOT EXISTS $CDB_B" > /dev/null
docker exec -i ch clickhouse-client --query "CREATE DATABASE IF NOT EXISTS $LDB" > /dev/null

# ===========================================================================
case_ "1  schema into the scratch databases, by --database"
TARGET=cloud tools/apply-sql.sh --database "$CDB_A" sql/00_schema.sql > /dev/null
TARGET=cloud tools/apply-sql.sh --database "$CDB_B" sql/00_schema.sql > /dev/null
eq "$CDB_A tables" 2 "$(cloud1 "SELECT count() FROM system.tables WHERE database='$CDB_A' AND name IN ('ev_raw','content_dim')")"
eq "$CDB_B tables" 2 "$(cloud1 "SELECT count() FROM system.tables WHERE database='$CDB_B' AND name IN ('ev_raw','content_dim')")"

# ===========================================================================
case_ "2  first load into an empty database succeeds"
TARGET=cloud tools/load.sh --database "$CDB_A" "$TMP/raw.csv" "$TMP/content.csv" > /dev/null
eq "$CDB_A.ev_raw" "$ROWS" "$(cloud1 "SELECT count() FROM $CDB_A.ev_raw")"

# ===========================================================================
case_ "3  DEFECT 1 — the same load again, no flag, MUST be refused"
OUT="$(TARGET=cloud tools/load.sh --database "$CDB_A" "$TMP/raw.csv" "$TMP/content.csv" 2>&1)"; RC=$?
eq "exit code" 1 "$RC"
case "$OUT" in *"REFUSING TO LOAD"*) ok "said REFUSING TO LOAD" ;; *) bad "no refusal banner in output" ;; esac
eq "$CDB_A.ev_raw unchanged" "$ROWS" "$(cloud1 "SELECT count() FROM $CDB_A.ev_raw")"

# ===========================================================================
case_ "4  doubling is still reachable, but only via --append, and it announces itself"
OUT="$(TARGET=cloud tools/load.sh --database "$CDB_A" --append "$TMP/raw.csv" "$TMP/content.csv" 2>&1)"
case "$OUT" in *"ADDING TO EXISTING DATA"*) ok "said ADDING TO EXISTING DATA" ;; *) bad "no append banner" ;; esac
eq "$CDB_A.ev_raw doubled on purpose" "$((ROWS * 2))" "$(cloud1 "SELECT count() FROM $CDB_A.ev_raw")"

# ===========================================================================
case_ "5  --replace truncates and reloads, so it is repeatable"
TARGET=cloud tools/load.sh --database "$CDB_A" --replace "$TMP/raw.csv" "$TMP/content.csv" > /dev/null
TARGET=cloud tools/load.sh --database "$CDB_A" --replace "$TMP/raw.csv" "$TMP/content.csv" > /dev/null
eq "$CDB_A.ev_raw after two --replace runs" "$ROWS" "$(cloud1 "SELECT count() FROM $CDB_A.ev_raw")"

# ===========================================================================
case_ "6  DEFECT 2 — CH_DATABASE in the ENVIRONMENT beats the .env beside the loader"
# Sandbox .env says $CDB_A; the environment says $CDB_B. Before the fix the file
# won and the load landed in $CDB_A — the graded database, in the real case.
A_BEFORE=$(cloud1 "SELECT count() FROM $CDB_A.ev_raw")
( cd "$TMP/sb_a" && CH_DATABASE="$CDB_B" TARGET=cloud "$REPO/tools/load.sh" "$TMP/raw.csv" "$TMP/content.csv" ) > /dev/null
eq "$CDB_B.ev_raw (asked for)"      "$ROWS"     "$(cloud1 "SELECT count() FROM $CDB_B.ev_raw")"
eq "$CDB_A.ev_raw (not asked for)"  "$A_BEFORE" "$(cloud1 "SELECT count() FROM $CDB_A.ev_raw")"

# ===========================================================================
case_ "7  --database contradicting an exported CH_DATABASE is an error"
OUT="$(CH_DATABASE="$CDB_B" TARGET=cloud tools/load.sh --database "$CDB_A" "$TMP/raw.csv" "$TMP/content.csv" 2>&1)"; RC=$?
eq "exit code" 1 "$RC"
case "$OUT" in *contradicts*) ok "named the contradiction" ;; *) bad "did not name the contradiction" ;; esac

# ===========================================================================
case_ "8  no database anywhere is an error, not a guess"
OUT="$(cd "$TMP/sb_none" && TARGET=cloud "$REPO/tools/load.sh" "$TMP/raw.csv" "$TMP/content.csv" 2>&1)"; RC=$?
eq "exit code" 1 "$RC"
case "$OUT" in *"no database"*) ok "said no database" ;; *) bad "did not say no database" ;; esac
# apply-sql.sh cannot be sandboxed the same way — it cds to the repo root and so
# always reads the repo's .env, which does define CH_DATABASE. Exercise its two
# other refusals instead; both fire before a single statement is sent.
OUT="$(CH_DATABASE="$CDB_B" TARGET=cloud "$REPO/tools/apply-sql.sh" --database "$CDB_A" sql/00_schema.sql 2>&1)"; RC=$?
eq "apply-sql.sh contradiction exit code" 1 "$RC"
OUT="$(TARGET=cloud "$REPO/tools/apply-sql.sh" --database "${CDB_A}_nope" sql/00_schema.sql 2>&1)"; RC=$?
eq "apply-sql.sh missing-database exit code" 1 "$RC"
case "$OUT" in *"does not exist"*) ok "apply-sql.sh said the database does not exist" ;; *) bad "wrong message" ;; esac

# ===========================================================================
case_ "9  a database that does not exist is an error before anything is written"
OUT="$(TARGET=cloud tools/load.sh --database ${CDB_A}_nope "$TMP/raw.csv" "$TMP/content.csv" 2>&1)"; RC=$?
eq "exit code" 1 "$RC"
case "$OUT" in *"does not exist"*) ok "said the database does not exist" ;; *) bad "wrong message" ;; esac

# ===========================================================================
case_ "10  DEFECT 2, local — the local path used to ignore the database entirely"
DEFAULT_BEFORE=$(local1 "SELECT count() FROM default.ev_raw")
tools/apply-sql.sh --database "$LDB" sql/00_schema.sql > /dev/null
eq "$LDB tables" 2 "$(local1 "SELECT count() FROM system.tables WHERE database='$LDB' AND name IN ('ev_raw','content_dim')")"
tools/load.sh --database "$LDB" "$TMP/raw.csv" "$TMP/content.csv" > /dev/null
eq "$LDB.ev_raw"        "$ROWS"            "$(local1 "SELECT count() FROM $LDB.ev_raw")"
eq "local default.ev_raw untouched" "$DEFAULT_BEFORE" "$(local1 "SELECT count() FROM default.ev_raw")"

# ===========================================================================
case_ "11  local honours CH_DATABASE_LOCAL with no flag at all"
OUT="$(CH_DATABASE_LOCAL="$LDB" tools/load.sh "$TMP/raw.csv" "$TMP/content.csv" 2>&1)"; RC=$?
eq "exit code (refused: $LDB is not empty)" 1 "$RC"
case "$OUT" in *"$LDB"*) ok "resolved to $LDB, not default" ;; *) bad "did not resolve to $LDB" ;; esac
eq "local default.ev_raw still untouched" "$DEFAULT_BEFORE" "$(local1 "SELECT count() FROM default.ev_raw")"

# ===========================================================================
case_ "12  the graded database was never written"
eq "$PROD.ev_raw" "$PROD_BEFORE" "$(cloud1 "SELECT count() FROM $PROD.ev_raw")"

echo
echo "------------------------------------------------------------"
if [ "$FAIL" -eq 0 ]; then
  echo "load-guard test PASSED · $PASS assertions"
  echo "------------------------------------------------------------"
  exit 0
fi
echo "load-guard test FAILED · $FAIL of $((PASS + FAIL)) assertions"
echo "------------------------------------------------------------"
exit 1
