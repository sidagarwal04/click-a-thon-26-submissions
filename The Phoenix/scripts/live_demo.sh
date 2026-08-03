#!/usr/bin/env bash
# The live demo: produce, derive, query and observe, all at the same time, for an hour.
#
#   ./scripts/live_demo.sh                       # phoenix, 1 hour, ~12,000 concurrent
#   TARGET=12000 CYCLES=120 WORKERS=3 ./scripts/live_demo.sh
#   ./scripts/live_demo.sh --stop                # kill a run started earlier
#
# WHAT RUNS CONCURRENTLY, AND WHY EACH ONE EARNS ITS PROCESS.
#
#   producer   one batched INSERT per cycle. NOT parallelised: generation is server-side, so a
#              second producer would add no throughput and would split one well-sized part into
#              two half-sized ones, doubling merge work for nothing.
#   deriver    derive_tick.sh in a loop. Deriving WHILE ingesting is the update-friendliness
#              claim the problem statement grades; running it after the fact would prove nothing.
#   queryload  serving queries against the live window. This is the "how does it perform against
#              live data" question, and it only means something measured under concurrent write.
#   observer   ingest lag, active parts, invariants. Catches a stalled curve while there is still
#              time to react.
#
# THE DERIVE EXIT CODE IS SURFACED, NOT SWALLOWED. scripts/ingest_arrivals.sh calls
# `derive_tick.sh >/dev/null 2>&1 || true`, which hides an invariant failure completely: the tick
# stops advancing the watermark, the curve silently freezes, and the console keeps printing
# happily. Here a failing tick is counted, printed, and aborts the run after three in a row.
set -euo pipefail
cd "$(dirname "$0")/.."

# DEFAULTS TO phoenix_next, NOT phoenix. phoenix is the graded database: it holds the validated
# 905,558-row corpus the benchmark answers come from, and its frozen slice must stay still.
# phoenix_next is generation two and is where live ingest and the insight layer live, which is
# also what the frontend reads. Pass DB=phoenix explicitly to aim at the graded one.
DB="${DB:-${CH_DATABASE:-phoenix_next}}"
export CH_DATABASE="$DB"
TARGET="${TARGET:-12000}"
PERIOD="${PERIOD:-30}"
CYCLES="${CYCLES:-120}"
WORKERS="${WORKERS:-3}"
PIDFILE=".live_demo.$DB.pids"
# The boundary that separates demo rows from the validated corpus. Same value reset_live.sh
# uses, so "live rows" on the console means exactly the rows the cleanup will remove.
LIVE_FROM="${LIVE_FROM:-2026-08-01}"
# Serving queries carry `AND minute < {frozen_before}`, which hides the live slice. Move it
# forward for every child process or the demo shows an empty curve.
export FROZEN_BEFORE="${FROZEN_BEFORE:-$(date -u -d '+2 days' +%F)}"

if [ "${1:-}" = "--stop" ]; then
  [ -f "$PIDFILE" ] || { echo "no run recorded in $PIDFILE" >&2; exit 0; }
  while read -r p; do kill "$p" 2>/dev/null || true; done < "$PIDFILE"
  rm -f "$PIDFILE"; echo "stopped" >&2; exit 0
fi

ch()  { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

: > "$PIDFILE"
cleanup() {
  echo >&2; echo "== shutting down" >&2
  while read -r p; do kill "$p" 2>/dev/null || true; done < "$PIDFILE"
  rm -f "$PIDFILE"
}
trap cleanup INT TERM EXIT

echo "== live demo on $DB: target $TARGET, ${CYCLES} cycles of ${PERIOD}s, frozen_before=$FROZEN_BEFORE" >&2

# ---- producer ------------------------------------------------------------------------------
TARGET="$TARGET" PERIOD="$PERIOD" CYCLES="$CYCLES" DB="$DB" RESET="${RESET:-1}" \
  ./scripts/live_producer.sh >"live_demo.producer.$DB.log" 2>&1 &
echo $! >> "$PIDFILE"

# ---- deriver -------------------------------------------------------------------------------
(
  fails=0
  while :; do
    if ./scripts/derive_tick.sh "$DB" >/dev/null 2>&1; then
      fails=0
    else
      fails=$(( fails + 1 ))
      echo "$(date -u +%FT%TZ) DERIVE TICK FAILED ($fails in a row) - see derive_tick.$DB.log" >&2
      [ "$fails" -ge 3 ] && { echo "$(date -u +%FT%TZ) three consecutive failures, stopping deriver" >&2; exit 1; }
    fi
    sleep "$PERIOD"
  done
) >"live_demo.deriver.$DB.log" 2>&1 &
echo $! >> "$PIDFILE"

# ---- query load ----------------------------------------------------------------------------
for ((w=1; w<=WORKERS; w++)); do
  DURATION=$(( CYCLES * PERIOD )) DB="$DB" ./scripts/live_queryload.sh \
    >"live_demo.queryload$w.$DB.log" 2>&1 &
  echo $! >> "$PIDFILE"
done

# ---- observer, in the foreground so the console shows the demo ------------------------------
echo >&2
printf '%-9s %-8s %-9s %-9s %-8s %-7s %s\n' \
  ELAPSED LIVE_ROWS CONCURRENT SESSIONS LAG_S PARTS DERIVE >&2

START=$(date +%s)
END=$(( START + CYCLES * PERIOD ))
while [ "$(date +%s)" -lt "$END" ]; do
  sleep 15
  elapsed=$(( $(date +%s) - START ))

  # One round trip for everything the console shows: five separate queries per tick would add
  # load the demo is trying to measure.
  row="$(val "SELECT concat(
      toString((SELECT count() FROM raw_events WHERE event_timestamp >= '$LIVE_FROM')), '|',
      -- CUMULATIVE FROM THE START OF THE LIVE SLICE, and reported at the last COMPLETE minute.
      --
      -- The first version summed deltas only over the last 10 minutes. A running sum that starts
      -- mid-series is not a level, it is a CHANGE: it silently drops every +1 belonging to a
      -- session that arrived before the window. While the demo ramped it looked plausible
      -- (8,270), and once the population went steady and arrivals balanced departures it
      -- collapsed to 2,843 while the producer was holding 10,515 sessions alive. A curve that
      -- decays whenever the system is healthiest is worse than no curve.
      --
      -- The last minute is excluded because it is still being written; including it always
      -- reports a partial number that looks like a crash.
      toString((SELECT ifNull(argMax(c, m), 0) FROM (SELECT minute AS m, sum(d) OVER (ORDER BY minute) AS c FROM (SELECT minute, sum(delta) AS d FROM concurrency_deltas WHERE minute >= '$LIVE_FROM' AND minute < toStartOfMinute(now()) GROUP BY minute)))), '|',
      toString((SELECT uniqExact(video_session_id) FROM raw_events
                WHERE event_timestamp >= now() - INTERVAL 2 MINUTE)), '|',
      -- Lag measured against the newest event that is NOT in the future, for the same reason
      -- derive_tick.sh clamps its watermark. phoenix_next holds spike fixtures pinned eight hours
      -- ahead of wall clock, and an unclamped max() reported LAG_S = -31195: a negative lag, which
      -- reads as a broken clock rather than as healthy ingest.
      toString((SELECT ifNull(toInt32(dateDiff('second', max(event_timestamp), now())), -1)
                FROM raw_events WHERE event_timestamp <= now())), '|',
      toString((SELECT count() FROM system.parts
                WHERE database = currentDatabase() AND table = 'raw_events' AND active)))" 2>/dev/null)"
  IFS='|' read -r rows conc sess lag parts <<<"${row:-0|0|0|-1|0}"

  # A dead producer must be LOUD. The first full run lost its producer to a network blip and the
  # console kept printing a slowly-decaying curve, which reads as a demo winding down rather than
  # as a process that is gone.
  if ! kill -0 "$(head -1 "$PIDFILE")" 2>/dev/null; then
    echo "  PRODUCER IS GONE - see live_demo.producer.$DB.log" >&2
  fi
  derive="$(tail -1 "derive_tick.$DB.log" 2>/dev/null | grep -o 'ok:\|FAILED\|nothing new' | head -1)"
  printf '%-9s %-8s %-9s %-9s %-8s %-7s %s\n' \
    "${elapsed}s" "${rows:-?}" "${conc:-?}" "${sess:-?}" "${lag:-?}" "${parts:-?}" "${derive:-pending}" >&2
done

echo "== demo window complete" >&2
