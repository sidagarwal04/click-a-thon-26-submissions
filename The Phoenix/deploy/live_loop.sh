#!/usr/bin/env bash
# THE DERIVE LOOP for the deployed demo.
#
# The producer writes raw events continuously; nothing serves raw events. This loop is what turns
# them into the deltas v1 reads and the ten insight tables v2 reads, so without it the demo host
# ingests forever and both consoles stay frozen at whatever the last manual derive produced.
#
# WHY A LOOP AND NOT CRON. The container has no cron and adding one means a second process
# supervisor inside a container that already has exactly one job. A sleep loop is the whole
# feature. derive_tick.sh already serialises itself on a flock, so a slow tick delays the next one
# rather than overlapping it.
#
# WHY THE INSIGHT REFRESH IS WINDOWED. refresh_insights.sh over the full history would re-derive
# every session on every pass. The window is anchored on the RAW WATERMARK and not the wall clock,
# because the insight layer lags ingest and a wall-clock window would ask for minutes that have not
# been derived yet and quietly return nothing.
set -uo pipefail
cd "$(dirname "$0")/.."

DB="${DERIVE_DB:-phoenix_next}"
PERIOD="${DERIVE_PERIOD:-60}"
# How far back each insight refresh reaches. Wide enough to absorb a late arrival, narrow enough
# that a pass stays cheap. Sessions older than this are already final.
LOOKBACK_MIN="${INSIGHT_LOOKBACK_MIN:-30}"

echo "derive loop: db=$DB period=${PERIOD}s lookback=${LOOKBACK_MIN}m"

while true; do
  pass_start=$(date +%s)
  # Concurrency first: this is what v1 and the curve read, so it is the one that must not fall
  # behind. A failure here is logged and retried next pass rather than killing the container,
  # because a demo host that exits on one transient network error is worse than one that lags.
  # NO `| tail -3`. It used to be there and it hid a real, permanent failure: the tick errored on
  # every single pass for twenty minutes while the three surviving lines were echoed SQL, and the
  # actual message -- "Database phoenix_live_v2 does not exist" -- was truncated away. A pipe also
  # masks the exit status behind tail's, so `if !` never fired.
  #
  # Capture in full, print the ERROR lines on failure, and stay silent on success so the log is
  # readable.
  tick_out="$(CH_DATABASE="$DB" ./scripts/derive_tick.sh "$DB" 2>&1)" && tick_rc=0 || tick_rc=$?
  if [ "$tick_rc" -ne 0 ]; then
    echo "=== DERIVE_TICK FAILED (exit $tick_rc) at $(date -u +%FT%TZ) ==="
    echo "$tick_out" | grep -iE "exception|code: [0-9]+|error" | head -5
    echo "$tick_out" | tail -20
    echo "=== end derive_tick failure ==="
  fi

  # Then the insight layer, windowed on the raw watermark.
  WATERMARK="$(CH_DATABASE="$DB" ./scripts/ch.sh --format TSVRaw --query \
    "SELECT toString(max(event_timestamp)) FROM raw_events" 2>/dev/null | head -1)"

  if [ -n "$WATERMARK" ]; then
    FROM_TS="$(CH_DATABASE="$DB" ./scripts/ch.sh --format TSVRaw --query \
      "SELECT toString(toDateTime('$WATERMARK') - INTERVAL $LOOKBACK_MIN MINUTE)" 2>/dev/null | head -1)"
    # Same treatment, and deliberately NOT echoing this stage's own "verdict PASS" line. The
    # insight refresh printing PASS directly after a failed derive made the whole loop read as
    # healthy to anyone skimming `docker compose logs ticker`. A subordinate component's verdict
    # must not be printed at the same level as the pipeline's.
    ins_out="$(FROM_TS="$FROM_TS" TO_TS="$WATERMARK" CH_DATABASE="$DB" \
      ./scripts/refresh_insights.sh 2>&1)" && ins_rc=0 || ins_rc=$?
    if [ "$ins_rc" -ne 0 ]; then
      echo "=== REFRESH_INSIGHTS FAILED (exit $ins_rc) at $(date -u +%FT%TZ) ==="
      echo "$ins_out" | grep -iE "exception|code: [0-9]+|error" | head -5
      echo "=== end refresh_insights failure ==="
    fi
  else
    echo "no watermark yet, skipping insight refresh"
  fi

  # Drift-corrected: sleep the REMAINDER of the period, not a fixed period after the work. With a
  # fixed sleep the effective cadence is work+PERIOD, so a slow tick silently widens the next
  # window, which makes it slower again. That spiral converges on permanent timeout.
  elapsed=$(( $(date +%s) - pass_start ))
  remaining=$(( PERIOD - elapsed ))
  [ "$remaining" -lt 5 ] && remaining=5
  sleep "$remaining"
done
