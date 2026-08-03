#!/usr/bin/env bash
# tools/validate-source-contract.sh — READ-ONLY source-contract gate (ADR 0026).
#
# Asserts and reports what is true about ev_raw / content_dim in one database,
# changing nothing: a verdict plus a table of counts, one screen, BEFORE any
# derived number is trusted. FAIL = the file is not what we think it is — stop.
# WARN = unusual, proceed with eyes open. INFO = context for comparing against
# the committed baseline in evidence/source-contract/.
#
#   tools/validate-source-contract.sh                       # TARGET=local, CH_DATABASE_LOCAL
#   tools/validate-source-contract.sh -c                    # cloud, CH_DATABASE (graded reads are fine: SELECTs only)
#   tools/validate-source-contract.sh -c --database liv_x   # any database on cloud
#
# Exit codes: 0 = CLEAN or WARN-only (the verdict line says which), 1 = FAIL,
# 2 = could not run. The vocabulary contract is evidence/liveness/vocabulary.tsv
# (doubts/11), rendered into the query at run time; this script dies without it.
# Origin: feat/problem-space-research (design-bakeoff cherry-pick #1), adapted.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
die() { printf 'validate-source-contract: %s\n' "$*" >&2; exit 2; }

TARGET_ARG="${TARGET:-local}"
DB_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    -c) TARGET_ARG=cloud; shift ;;
    --target) TARGET_ARG="${2:?--target needs a value}"; shift 2 ;;
    --database) DB_ARG="${2:?--database needs a value}"; shift 2 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) die "unknown argument: $1 (usage: [-c|--target cloud|local] [--database NAME])" ;;
  esac
done
case "$TARGET_ARG" in local|cloud) ;; *) die "TARGET='$TARGET_ARG' is not a target — 'local' or 'cloud' (ADR 0018)" ;; esac

SQL_FILE="$ROOT/queries/validate_source_contract.sql"
VOCAB="$ROOT/evidence/liveness/vocabulary.tsv"
[ -f "$SQL_FILE" ] || die "missing $SQL_FILE"
[ -f "$VOCAB" ] || die "missing $VOCAB — the vocabulary contract is half the gate (doubts/11)"

# The gate is read-only BY DESIGN. Refuse to run if the query file ever grows a
# write, so a future edit cannot quietly turn a report into a mutation.
# Comments are stripped first (R2: prose must not trip a code guard).
if perl -pe 's/--.*$//' "$SQL_FILE" | grep -Eiqw 'insert|alter|drop|truncate|optimize|create|rename|detach|attach|grant|kill'; then
  die "$SQL_FILE contains a write keyword — the gate is read-only (ADR 0026); refusing to run"
fi

# Render the vocabulary contract into the query: TSV -> ('type','event'),...
# perl, not sed — BSD sed burned us before (RUNBOOK R1).
PAIRS=$(perl -ne '
  next if $. == 1; s/\r?\n$//;
  my @f = split /\t/; next unless defined $f[1] && length $f[0];
  for (@f[0,1]) { s/\x27/\x27\x27/g }
  push @p, "(\x27$f[0]\x27,\x27$f[1]\x27)";
  END { print join(",", @p) }' "$VOCAB")
[ -n "$PAIRS" ] || die "$VOCAB rendered an empty pair list"
Q=$(PAIRS="$PAIRS" perl -pe 's/__VOCAB_PAIRS__/$ENV{PAIRS}/' "$SQL_FILE")

# --database maps onto the variable tools/ch honours for the chosen target
# (environment wins over .env there — ADR 0018).
if [ -n "$DB_ARG" ]; then
  if [ "$TARGET_ARG" = cloud ]; then export CH_DATABASE="$DB_ARG"; else export CH_DATABASE_LOCAL="$DB_ARG"; fi
fi

DB_SHOWN=$(TARGET="$TARGET_ARG" "$ROOT/tools/ch" "SELECT currentDatabase()") \
  || die "cannot reach TARGET=$TARGET_ARG — fix connectivity before trusting anything"

# Shape pre-probe. A missing ev_raw column would kill the full report with a
# server error instead of a verdict, so shape is checked FIRST, separately —
# the gate must stay readable exactly when the file is most wrong.
PRE=$(TARGET="$TARGET_ARG" "$ROOT/tools/ch" "WITH
    ['content_id', 'video_session_id', 'user_id', 'event_type', 'event',
     'event_timestamp', 'platform', 'app_version', 'country', 'audio_language',
     'subtitle_language', 'player_version', 'session_start_epoch'] AS expected_cols,
    (SELECT groupArray(name) FROM system.columns
     WHERE database = currentDatabase() AND table = 'ev_raw') AS actual_cols
  SELECT
    arrayStringConcat(arrayFilter(c -> NOT has(actual_cols, c), expected_cols), ', '),
    (SELECT count() FROM system.tables
     WHERE database = currentDatabase() AND name = 'content_dim')
  FORMAT TSV")
MISSING=$(printf '%s' "$PRE" | cut -f1)
HAS_CONTENT=$(printf '%s' "$PRE" | cut -f2)
if [ -n "$MISSING" ]; then
  printf 'source-contract gate (ADR 0026, read-only) — target=%s database=%s\n' "$TARGET_ARG" "$DB_SHOWN"
  printf '  FAIL  expected columns missing from ev_raw: %s\n' "$MISSING"
  echo
  echo 'VERDICT: FAIL — ev_raw does not have the 13-column shape (or does not exist here). This file/database is not what we think it is; STOP.'
  exit 1
fi
CONTENT_REL='content_dim'
CONTENT_NOTE=''
if [ "$HAS_CONTENT" = "0" ]; then
  CONTENT_REL="(SELECT CAST(0, 'Int64') AS content_id, '' AS title, '' AS video_type, '' AS category WHERE 0)"
  CONTENT_NOTE="  note: content_dim is ABSENT here — every event content_id counts as unresolved (A9/R10)"
fi
Q=$(CONTENT_REL="$CONTENT_REL" perl -pe 's/__CONTENT_DIM__/$ENV{CONTENT_REL}/' <<<"$Q")

OUT=$(TARGET="$TARGET_ARG" "$ROOT/tools/ch" "$Q")

printf 'source-contract gate (ADR 0026, read-only) — target=%s database=%s vocabulary=%s pairs\n' \
  "$TARGET_ARG" "$DB_SHOWN" "$(($(grep -c '' "$VOCAB") - 1))"
[ -z "$CONTENT_NOTE" ] || printf '%s\n' "$CONTENT_NOTE"
printf '%s\n' '  sev   probe                                                       count  note'
printf '%s\n' "$OUT" | awk -F'\t' '{ printf "  %-5s %-55s %10s  %s\n", $1, $2, $3, $4 }'

FAILS=$(printf '%s\n' "$OUT" | awk -F'\t' '$1 == "FAIL" && $3 + 0 > 0' | grep -c '' || true)
WARNS=$(printf '%s\n' "$OUT" | awk -F'\t' '$1 == "WARN" && $3 + 0 > 0' | grep -c '' || true)
echo
if [ "$FAILS" -gt 0 ]; then
  echo "VERDICT: FAIL — $FAILS contract violation(s). This file is not what we think it is; STOP before the load costs an hour."
  exit 1
elif [ "$WARNS" -gt 0 ]; then
  echo "VERDICT: WARN — 0 failures, $WARNS warning(s). Proceed with eyes open; diff the WARN rows against evidence/source-contract/."
else
  echo "VERDICT: CLEAN — every FAIL and WARN probe is zero."
fi
