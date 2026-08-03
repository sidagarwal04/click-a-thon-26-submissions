#!/usr/bin/env bash
# What does the choice between the FIRST and the LAST VideoSessionEnd actually cost?
#
#   ./scripts/end_rule_measurement.sh              # phoenix_next
#   CH_DATABASE=phoenix ./scripts/end_rule_measurement.sh
#
# D8 bounds every interval at the session's LAST VideoSessionEnd. The insights plan's Phase 0.2
# proposes that the FIRST end is terminal and later events with the same video_session_id are
# ignored. Those are different rules and the difference was never ruled on, because the
# measurement that settled D8 answered a different question: it showed that the 14 multi-end
# sessions accounted for zero of the 385 intervals that overshot their session end. Zero
# overshoots is not the same as zero difference between the two rules.
#
# This script measures the actual difference, on the frozen slice, and writes it so D13 cites a
# number rather than an intuition.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix_next}"
export CH_DATABASE="$DB" EVIDENCE_STAMP_DB="$DB"
ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

MULTI="SELECT video_session_id AS sid,
              toDateTime(min(event_timestamp)) AS first_end,
              toDateTime(max(event_timestamp)) AS last_end
       FROM raw_events
       WHERE event_type = 'VideoSessionEnd' AND event_timestamp < {frozen_before:String}
       GROUP BY video_session_id HAVING count() > 1"

multi=$(val "SELECT count() FROM ($MULTI)")
maxgap=$(val "SELECT max(dateDiff('second', first_end, last_end)) FROM ($MULTI)")
# Events that a first-end-terminal rule would discard. Their TYPES are the argument: heartbeats
# alone would be noise, but Play and AppForegrounded are a session demonstrably still watching.
discarded=$(val "
  WITH ends AS ($MULTI)
  SELECT count() FROM raw_events r INNER JOIN ends e ON r.video_session_id = e.sid
  WHERE r.event_timestamp > e.first_end AND r.event_timestamp <= e.last_end
    AND r.event_timestamp < {frozen_before:String}")
play=$(val "
  WITH ends AS ($MULTI)
  SELECT count() FROM raw_events r INNER JOIN ends e ON r.video_session_id = e.sid
  WHERE r.event_timestamp > e.first_end AND r.event_timestamp <= e.last_end
    AND r.event_type IN ('VideoPlay', 'AppForegrounded')
    AND r.event_timestamp < {frozen_before:String}")
sessions=$(val "
  WITH ends AS ($MULTI)
  SELECT uniqExact(i.video_session_id) FROM foreground_intervals i
  INNER JOIN ends e ON i.video_session_id = e.sid WHERE i.interval_end > e.first_end")
seconds=$(val "
  WITH ends AS ($MULTI)
  SELECT sum(dateDiff('second', greatest(i.interval_start, e.first_end), least(i.interval_end, e.last_end)))
  FROM foreground_intervals i INNER JOIN ends e ON i.video_session_id = e.sid
  WHERE i.interval_end > e.first_end")
total=$(val "SELECT sum(dateDiff('second', interval_start, interval_end)) FROM foreground_intervals
             WHERE interval_start < {frozen_before:String}")

# The headline. A rule that moves a graded number by one is a rule that needs a decision, not a
# preference. Counted as: sessions live at the peak minute whose FIRST end precedes it, which
# are exactly the sessions a first-end-terminal rule would remove from that minute.
PEAK_MIN="${PEAK_MINUTE:-2026-07-26 10:56:00}"
lost_at_peak=$(val "
  WITH ends AS ($MULTI)
  SELECT uniqExact(r.video_session_id)
  FROM session_minute_runs r INNER JOIN ends e ON r.video_session_id = e.sid
  WHERE r.sign = 1
    AND r.run_start <= toDateTime('$PEAK_MIN') AND r.run_end >= toDateTime('$PEAK_MIN')
    AND e.first_end < toDateTime('$PEAK_MIN')")

{
  printf 'metric\tvalue\n'
  printf 'database\t%s\n'                              "$DB"
  printf 'multi_end_sessions\t%s\t(frozen slice)\n'    "$multi"
  printf 'max_gap_first_to_last_end_seconds\t%s\n'     "$maxgap"
  printf 'events_after_first_end\t%s\t(a first-end-terminal rule discards these)\n' "$discarded"
  printf 'of_which_play_or_foreground\t%s\t(not heartbeat noise: a session still watching)\n' "$play"
  printf 'sessions_with_foreground_past_first_end\t%s\n' "$sessions"
  printf 'foreground_seconds_at_stake\t%s\n'           "$seconds"
  printf 'total_foreground_seconds\t%s\n'              "$total"
  printf 'share_of_foreground_at_stake_pct\t%s\n'      "$(awk -v a="$seconds" -v b="$total" 'BEGIN{printf "%.4f", 100*a/b}')"
  printf 'peak_minute\t%s\n'                           "$PEAK_MIN"
  printf 'sessions_removed_from_peak_minute\t%s\t(peak would restate by this much)\n' "$lost_at_peak"
} | evidence "end_rule_first_vs_last" "cost of treating the FIRST VideoSessionEnd as terminal instead of the last, frozen slice" \
  | xargs cat
