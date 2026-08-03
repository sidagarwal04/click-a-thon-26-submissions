#!/usr/bin/env bash
# Probe the live stream: is it running, and what event time is it carrying?
#
#   ./scripts/ingest_probe.sh [samples] [interval_seconds]
#
# Ingest is a teammate's and this script does not touch it. It only reads, because the two
# things we need to know about it are both observable from the outside:
#
#   1. Is it actually moving? Every gate that claims "stable while ingest runs" is worthless
#      if the stream was idle for the run. This samples count() over time so the claim is
#      backed rather than assumed.
#
#   2. What does it put in event_timestamp? If the stream stamps wall-clock arrival time
#      instead of source event time, then its rows are not a continuation of the corpus,
#      they are a separate day sitting in the same table, and every range query has to know
#      that. Compared here against session_start_epoch, which comes from the same producer.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

SAMPLES="${1:-3}"
INTERVAL="${2:-20}"

first_count=""; last_count=""; first_wm=""; last_wm=""
for i in $(seq 1 "$SAMPLES"); do
  row="$(./scripts/ch.sh --format TSVRaw --query \
    "SELECT count(), toString(max(event_timestamp)), toString(now()) FROM raw_events" | head -1)"
  c="$(echo "$row" | cut -f1)"; wm="$(echo "$row" | cut -f2)"
  [ -z "$first_count" ] && { first_count="$c"; first_wm="$wm"; }
  last_count="$c"; last_wm="$wm"
  echo "sample $i/$SAMPLES: rows=$c watermark=$wm" >&2
  [ "$i" -lt "$SAMPLES" ] && sleep "$INTERVAL"
done

arrived=$(( last_count - first_count ))
[ "$arrived" -gt 0 ] && running=RUNNING || running=IDLE

{
  printf 'metric\tvalue\n'
  printf 'samples\t%s\n' "$SAMPLES"
  printf 'interval_seconds\t%s\n' "$INTERVAL"
  printf 'observed_seconds\t%s\n' "$(( (SAMPLES - 1) * INTERVAL ))"
  printf 'rows_first_sample\t%s\n' "$first_count"
  printf 'rows_last_sample\t%s\n' "$last_count"
  printf 'rows_arrived\t%s\n' "$arrived"
  printf 'event_watermark_first\t%s\n' "$first_wm"
  printf 'event_watermark_last\t%s\n' "$last_wm"
  printf 'stream_state\t%s\n' "$running"

  # The live slice, characterised against its own producer's session_start_epoch and
  # against the server clock. If event_timestamp tracks the server clock rather than the
  # corpus, that shows up here as a span that ends at "now" and starts when ingest started.
  ./scripts/ch.sh --format TSV --query "
    SELECT * FROM (
      SELECT 'live.first_event_timestamp' AS metric, toString(min(event_timestamp)) AS value FROM raw_events WHERE event_timestamp >= {frozen_before:String}
      UNION ALL SELECT 'live.last_event_timestamp',  toString(max(event_timestamp)) FROM raw_events WHERE event_timestamp >= {frozen_before:String}
      UNION ALL SELECT 'live.first_session_start_epoch', toString(min(session_start_epoch)) FROM raw_events WHERE event_timestamp >= {frozen_before:String}
      UNION ALL SELECT 'live.last_session_start_epoch',  toString(max(session_start_epoch)) FROM raw_events WHERE event_timestamp >= {frozen_before:String}
      UNION ALL SELECT 'live.rows',     toString(count())                       FROM raw_events WHERE event_timestamp >= {frozen_before:String}
      UNION ALL SELECT 'live.sessions', toString(uniqExact(video_session_id))   FROM raw_events WHERE event_timestamp >= {frozen_before:String}
      UNION ALL SELECT 'frozen.last_event_timestamp', toString(max(event_timestamp)) FROM raw_events WHERE event_timestamp < {frozen_before:String}
      UNION ALL SELECT 'frozen.rows', toString(count()) FROM raw_events WHERE event_timestamp < {frozen_before:String}
      -- Zero overlap here is what makes the frozen predicate a clean cut rather than a
      -- guess: no session has events on both sides of the boundary.
      UNION ALL SELECT 'sessions_spanning_the_boundary', toString(
          uniqExactIf(video_session_id, event_timestamp <  {frozen_before:String})
        + uniqExactIf(video_session_id, event_timestamp >= {frozen_before:String})
        - uniqExact(video_session_id)) FROM raw_events
      UNION ALL SELECT 'last_insert_into_raw_events', toString(max(event_time)) FROM clusterAllReplicas(default, system.query_log)
        WHERE type = 'QueryFinish' AND query_kind = 'Insert' AND event_time > now() - INTERVAL 6 HOUR
          AND (has(tables, 'phoenix.raw_events_landing') OR has(tables, 'phoenix.raw_events'))

      -- Blast radius, per derived table. The live stream does not stop at raw_events: the
      -- MVs fire on it and someone re-ran the batch derive, so live-derived rows are sitting
      -- in every table below. Naming the size of that per table is the difference between
      -- 'the data is contaminated' and knowing the frozen predicate is sufficient.
      UNION ALL SELECT 'blast.foreground_intervals',    toString(countIf(interval_start >= {frozen_before:String})) FROM foreground_intervals
      UNION ALL SELECT 'blast.session_minute_runs',     toString(sumIf(sign, run_start >= {frozen_before:String}))   FROM session_minute_runs
      UNION ALL SELECT 'blast.user_minute_runs',        toString(sumIf(sign, run_start >= {frozen_before:String}))   FROM user_minute_runs
      UNION ALL SELECT 'blast.concurrency_deltas',      toString(uniqExactIf(minute, minute >= {frozen_before:String})) FROM concurrency_deltas
      UNION ALL SELECT 'blast.user_concurrency_deltas', toString(uniqExactIf(minute, minute >= {frozen_before:String})) FROM user_concurrency_deltas
      -- Zero here means the frozen predicate is a clean cut on the DERIVED tables too, not
      -- just on raw_events: no run straddles the boundary and gets half-counted.
      UNION ALL SELECT 'blast.runs_straddling_boundary', toString(countIf(run_start < {frozen_before:String} AND run_end >= {frozen_before:String})) FROM session_minute_runs
    ) ORDER BY metric"
} | evidence ingest_probe "is the live stream moving, and does its event_timestamp carry source event time or wall-clock arrival time" \
  | xargs cat
