#!/usr/bin/env bash
# Oracle parity gate. Proves the serving layer answers what brute force answers, on both
# derivation paths, and writes the result to evidence/ instead of a terminal nobody kept.
#
#   ./scripts/parity.sh [csv]
#
# Two comparisons, both against the SAME oracle run:
#   batch        phoenix.concurrency_deltas, derived by 01 + 02
#   incremental  a scratch database derived only by 03, over the whole span
#
# The oracle runs in `clickhouse local` over the CSV; the serving layer runs on Cloud. That
# is deliberate: two engines, two independent implementations of the state machine, same
# parameters. Both wrappers pin session_timezone=UTC.
#
# Nothing here writes to `phoenix`. 02_merge_runs.sql asserts sign=+1 unconditionally, so
# re-running the batch path against the validated database would append duplicate runs that
# SummingMergeTree absorbs silently. Batch parity therefore reads phoenix as it stands.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

CSV="${1:-data/ch-hackathon-raw-data.csv}"
TOL="${TOLERANCE_S:-90}"
PI="${PAUSE_INACTIVE:-1}"
INCR_DB=phoenix_parity_incr
# Which database the BATCH comparison reads. Parameterised so a shadow rebuild can be proven
# against the oracle BEFORE it is swapped into place, which is the only order that lets a
# failure cost nothing.
BATCH_DB="${BATCH_DB:-phoenix}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }

# The window is the CORPUS, not 2000-2100, and that is a requirement of comparing the queries
# we actually ship. The serving queries bound their WITH FILL with FROM/TO, which is the fix
# for the sparse-average bug; handing them a 2000-2100 window would ask them to materialise
# roughly 52 million minutes. The old benchmark queries had an UNBOUNDED WITH FILL, so a
# 2000-2100 window was harmless to them and the wide bound went unnoticed.
#
# Widened by a day on each side of the measured span so the bound is not mistaken for a
# hand-fitted range. Densification does not affect the comparison either way: served() keeps
# only minutes with concurrency > 0, because the oracle emits only minutes that had an
# audience.
CORPUS_FROM="${PARITY_FROM:-2026-07-13 00:00:00}"
CORPUS_TO="${PARITY_TO:-2026-07-28 00:00:00}"
FULL=(--param_platform='' --param_country='' --param_video_type='' --param_app_version=''
      --param_content_id=0 --param_from_ts="$CORPUS_FROM" --param_to_ts="$CORPUS_TO")

echo "== 1. oracle over $CSV (tolerance_s=$TOL pause_inactive=$PI)"
FORMAT=TSV TOLERANCE_S="$TOL" PAUSE_INACTIVE="$PI" \
  ./scripts/oracle.sh "$CSV" sql/queries/validation/oracle_concurrency.sql 2>/dev/null \
  | sort > "$TMP/oracle.tsv"
cut -f1,2 "$TMP/oracle.tsv" > "$TMP/oracle_sessions.tsv"
cut -f1,3 "$TMP/oracle.tsv" > "$TMP/oracle_users.tsv"
echo "   oracle minutes: $(wc -l < "$TMP/oracle.tsv")"

# The oracle emits only minutes that had an audience. The serving queries densify with a
# bounded WITH FILL, so their zero rows have no oracle counterpart by construction; comparing
# them would manufacture diffs that are an artifact of densification, not a disagreement.
#
# These are the files the dashboard serves. Before this they were the retired benchmark copies,
# which meant the parity gate proved a query nobody shipped: the two directories had already
# diverged by the seeded window, the bounded fill, and the read budget.
served() { CH_DATABASE="$1" ch --format TSV "${FULL[@]}" --queries-file "$2" \
             | awk -F'\t' '$2 > 0 {print $1 "\t" $2}' | sort; }

echo "== 2. batch path: $BATCH_DB serving layer vs oracle"
served "$BATCH_DB" sql/queries/serving/concurrency_curve.sql      > "$TMP/batch_sessions.tsv"
served "$BATCH_DB" sql/queries/serving/user_concurrency_curve.sql > "$TMP/batch_users.tsv"

echo "== 3. incremental path: $INCR_DB, derived only by 03 over the whole span"
ch --query "DROP DATABASE IF EXISTS $INCR_DB"
ch --query "CREATE DATABASE $INCR_DB"
for f in sql/schema/*.sql; do CH_DATABASE="$INCR_DB" ch --queries-file "$f"; done
# Seed from BATCH_DB, not from a hardcoded phoenix. Comparing an incremental derivation of
# phoenix's raw data against a batch derivation of some OTHER database's raw data is a green
# result that means nothing, and it would have gone green the first time it was pointed at a
# replica.
#
# Explicit column list rather than SELECT *: raw_events carries arrival_timestamp from
# generation 2 onward and phoenix does not, so the shapes differ by source. These thirteen are
# the columns every generation shares, and the scratch database's arrival_timestamp correctly
# defaults to the not-observed sentinel because these rows did not arrive, they were copied.
RAW_COLS='video_session_id, user_id, content_id, event_type, event, event_timestamp,
          platform, app_version, country, audio_language, subtitle_language, player_version,
          session_start_epoch'
CH_DATABASE="$INCR_DB" ch --query "INSERT INTO content SELECT * FROM ${BATCH_DB}.content"
CH_DATABASE="$INCR_DB" ch --query \
  "INSERT INTO raw_events ($RAW_COLS) SELECT $RAW_COLS FROM ${BATCH_DB}.raw_events"
CH_DATABASE="$INCR_DB" ch --param_tolerance_s="$TOL" --param_pause_inactive="$PI" \
  --param_from_ts='2000-01-01 00:00:00' --param_to_ts='2100-01-01 00:00:00' \
  --queries-file sql/pipeline/03_derive_incremental.sql
CH_DATABASE="$INCR_DB" ch --queries-file sql/pipeline/04_merge_user_runs.sql
served "$INCR_DB" sql/queries/serving/concurrency_curve.sql      > "$TMP/incr_sessions.tsv"
served "$INCR_DB" sql/queries/serving/user_concurrency_curve.sql > "$TMP/incr_users.tsv"

echo "== 4. diffs"
{
  printf 'comparison\tpath\toracle_minutes\tserved_minutes\tdiff_rows\tverdict\n'
  fail=0
  for c in "sessions batch $TMP/oracle_sessions.tsv $TMP/batch_sessions.tsv" \
           "users batch $TMP/oracle_users.tsv $TMP/batch_users.tsv" \
           "sessions incremental $TMP/oracle_sessions.tsv $TMP/incr_sessions.tsv" \
           "users incremental $TMP/oracle_users.tsv $TMP/incr_users.tsv"; do
    set -- $c
    d=$(diff "$3" "$4" | grep -c '^[<>]' || true)
    [ "$d" = 0 ] || fail=1
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$(wc -l < "$3")" "$(wc -l < "$4")" "$d" \
      "$([ "$d" = 0 ] && echo PASS || echo FAIL)"
    [ "$d" = 0 ] || diff "$3" "$4" | head -10 | sed 's/^/# diff: /' >&2
  done
  printf '#\tcsv\t%s\n#\ttolerance_s\t%s\n#\tpause_inactive\t%s\n' "$CSV" "$TOL" "$PI"
  echo "$fail" > "$TMP/fail"
} | evidence oracle_parity "oracle (clickhouse local, CSV) vs serving layer, batch and incremental" | xargs cat

[ "$(cat "$TMP/fail")" = 0 ] || { echo "PARITY FAILED" >&2; exit 1; }
echo "PARITY PASS"
