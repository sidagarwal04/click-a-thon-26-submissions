#!/usr/bin/env bash
# Does the lateness classifier put each kind of event in the class the policy names?
#
#   ./scripts/test_lateness_classifier.sh
#
# Four events go in through raw_events_landing, which is the only path that stamps a real
# arrival_timestamp, and each one is engineered to land in a different class. The point is not
# that multiIf works. It is that the boundaries in sql/insights/schema/09_late_event_audit.sql
# and the boundaries in docs/LATENESS.md are the same boundaries, and that on_time events are
# absent rather than merely uncounted.
#
# Runs in a scratch database. phoenix_next is durable and its raw_events row count is asserted
# by scripts/replica_parity.sh, so four test rows there would break a gate for no reason.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${LATENESS_TEST_DB:-phoenix_lateness_test}"
export EVIDENCE_STAMP_DB="$DB"
ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { CH_DATABASE="$DB" ch --format TSVRaw --query "$1" | head -1; }

echo "== scratch database $DB" >&2
ch --query "DROP DATABASE IF EXISTS $DB"
./scripts/init_db.sh "$DB" >/dev/null
./scripts/init_insights.sh "$DB" >/dev/null

# Offsets in seconds BEFORE now. A negative offset dates the event in the future, which is the
# only way an arrival can precede the event it carries.
#   -3600 future        ->  lateness -3600  -> invalid_future_event
#      10 fresh         ->  lateness 10     -> on_time, and therefore NOT stored
#     600 ten minutes   ->  lateness 600    -> late_acceptable
#    7200 two hours     ->  lateness 7200   -> late_after_finalization
echo "== four events through the landing table, which is what stamps arrival_timestamp" >&2
for spec in "future:-3600" "fresh:10" "acceptable:600" "stale:7200"; do
  name="${spec%%:*}"; off="${spec##*:}"
  CH_DATABASE="$DB" ch --query "
    INSERT INTO raw_events_landing
    SELECT 101, 'sess_$name', 'user_$name', 'VideoHeartbeat', 'heartbeat',
           toUnixTimestamp64Milli(now64(3) - toIntervalSecond($off)),
           'ANDROID_PHONE', '1.0.0', 'IN', 'hi', 'none', 'exo',
           toUnixTimestamp64Milli(now64(3) - toIntervalSecond($off))"
done

got_rows="$(val "SELECT count() FROM late_event_audit")"
got_ontime="$(val "SELECT countIf(lateness_class = 'on_time') FROM late_event_audit")"
raw_rows="$(val "SELECT count() FROM raw_events")"
observed="$(val "SELECT countIf(arrival_timestamp > toDateTime64(0, 3)) FROM raw_events")"

cls() { val "SELECT lateness_class FROM late_event_audit WHERE video_session_id = 'sess_$1'"; }
c_future="$(cls future)"; c_fresh="$(cls fresh)"; c_accept="$(cls acceptable)"; c_stale="$(cls stale)"

verdict=PASS
chk() { [ "$2" = "$3" ] && echo PASS || { verdict=FAIL; echo FAIL; }; }

{
  printf 'check\texpected\tgot\tverdict\n'
  printf 'raw_events_ingested\t4\t%s\t%s\n'          "$raw_rows"  "$(chk _ 4 "$raw_rows")"
  printf 'rows_with_observed_arrival\t4\t%s\t%s\n'   "$observed"  "$(chk _ 4 "$observed")"
  printf 'audit_rows\t3\t%s\t%s\n'                   "$got_rows"  "$(chk _ 3 "$got_rows")"
  printf 'on_time_rows_stored\t0\t%s\t%s\n'          "$got_ontime" "$(chk _ 0 "$got_ontime")"
  printf 'event_dated_in_future\tinvalid_future_event\t%s\t%s\n'   "$c_future" "$(chk _ invalid_future_event "$c_future")"
  printf 'event_10s_old\t<absent>\t%s\t%s\n'                       "${c_fresh:-<absent>}" "$(chk _ '' "$c_fresh")"
  printf 'event_600s_old\tlate_acceptable\t%s\t%s\n'               "$c_accept" "$(chk _ late_acceptable "$c_accept")"
  printf 'event_7200s_old\tlate_after_finalization\t%s\t%s\n'      "$c_stale"  "$(chk _ late_after_finalization "$c_stale")"
  printf '#\tboundaries\tallowed_lateness_seconds=90 finalization_delay_seconds=3600 (PROVISIONAL, see docs/LATENESS.md)\n'
  printf 'verdict\t%s\t%s\t%s\n' "$verdict" "$verdict" "$verdict"
} | evidence "lateness_classifier" "each lateness class produced by a real arrival through the landing table" \
  | xargs cat

[ "${KEEP_LATENESS_TEST:-0}" = "1" ] || ch --query "DROP DATABASE IF EXISTS $DB"
[ "$verdict" = PASS ] || { echo "LATENESS CLASSIFIER FAILED" >&2; exit 1; }
