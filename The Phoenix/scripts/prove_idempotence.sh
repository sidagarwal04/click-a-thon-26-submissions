#!/usr/bin/env bash
# Runs the full rebuild TWICE into two separate shadow databases and diffs the result.
#
#   ./scripts/prove_idempotence.sh
#
# TASK.md 3.2 and the Definition of Done ask for "full rebuild idempotent, proven by running
# twice and diffing". derive.sh's refusal proves the corruption is unreachable, which is a
# different claim: refusing to run twice is not the same as running twice and getting the same
# answer.
#
# WHY THE COMPARISON IS SCOPED TO THE FROZEN SLICE. Live ingest is writing to raw_events
# continuously, so the two rebuilds genuinely read different inputs and a raw diff would fail
# for a reason that has nothing to do with idempotence. Restricting to minute < frozen_before
# compares the two runs over the input they DID share. That is the honest comparison, and it is
# the same isolation predicate the frozen gate proves holds under concurrent writes.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

A="${A_DB:-phoenix_idem_a}"
B="${B_DB:-phoenix_idem_b}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }

echo "== rebuild 1 -> $A" >&2
SHADOW_DB="$A" VERIFY_ONLY=1 ./scripts/rebuild_swap.sh >/dev/null 2>&1
echo "== rebuild 2 -> $B" >&2
SHADOW_DB="$B" VERIFY_ONLY=1 ./scripts/rebuild_swap.sh >/dev/null 2>&1

# Full row dumps of the derived tables over the shared input, sorted so the comparison is of
# CONTENT and not of insert order. Not a checksum of the whole table: a checksum tells you
# something differs, a diff tells you what, and on a failure that difference is the finding.
dump() {  # db table -> sorted TSV on stdout
  case "$2" in
    foreground_intervals)
      CH_DATABASE="$1" ch --format TSV --query "
        SELECT video_session_id, user_id, content_id, platform, country, app_version, video_type,
               interval_start, interval_end
        FROM foreground_intervals WHERE interval_start < {frozen_before:String}
        ORDER BY video_session_id, interval_start, interval_end" ;;
    session_minute_runs|user_minute_runs)
      CH_DATABASE="$1" ch --format TSV --query "
        SELECT * EXCEPT sign FROM $2 WHERE run_start < {frozen_before:String}
        GROUP BY * EXCEPT sign HAVING sum(sign) > 0 ORDER BY 1, 2, 3" ;;
    concurrency_deltas|user_concurrency_deltas)
      CH_DATABASE="$1" ch --format TSV --query "
        SELECT platform, country, video_type, content_id, app_version, minute, sum(delta) AS d
        FROM $2 WHERE minute < {frozen_before:String}
        GROUP BY platform, country, video_type, content_id, app_version, minute
        HAVING d != 0 ORDER BY 1, 2, 3, 4, 5, 6" ;;
  esac
}

{
  printf 'table\trows_run1\trows_run2\tdiff_lines\tverdict\n'
  fail=0
  for t in foreground_intervals session_minute_runs concurrency_deltas user_minute_runs user_concurrency_deltas; do
    dump "$A" "$t" | sort > "$TMP/a"
    dump "$B" "$t" | sort > "$TMP/b"
    d=$(diff "$TMP/a" "$TMP/b" | grep -c '^[<>]' || true)
    [ "$d" = 0 ] || fail=1
    printf '%s\t%s\t%s\t%s\t%s\n' "$t" "$(wc -l < "$TMP/a")" "$(wc -l < "$TMP/b")" "$d" \
      "$([ "$d" = 0 ] && echo PASS || echo FAIL)"
    [ "$d" = 0 ] || diff "$TMP/a" "$TMP/b" | head -5 | sed 's/^/# diff: /' >&2
  done
  printf '#\tcompared_on\tminute < frozen_before, the input both runs shared\n'
  printf '#\trun1_db\t%s\n#\trun2_db\t%s\n' "$A" "$B"
  printf 'verdict\t%s\n' "$([ "$fail" = 0 ] && echo PASS || echo FAIL)"
  echo "$fail" > "$TMP/fail"
} | evidence rebuild_idempotence "full rebuild run twice into separate shadow databases, derived tables diffed row by row over the shared frozen input" | xargs cat

for d in "$A" "$B"; do ch --query "DROP DATABASE IF EXISTS $d"; done

[ "$(cat "$TMP/fail")" = 0 ] || { echo "IDEMPOTENCE FAILED" >&2; exit 1; }
echo "IDEMPOTENCE PASS" >&2
