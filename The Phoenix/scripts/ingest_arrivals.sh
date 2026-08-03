#!/usr/bin/env bash
# Sustained arrival/departure ingest: 5 users arrive for every 1 that leaves, held at a target.
#
#   ./scripts/ingest_arrivals.sh                       # phoenix, ramp to 3000 and hold
#   TARGET=3000 CYCLES=20 ./scripts/ingest_arrivals.sh
#   ARRIVE=500 ./scripts/ingest_arrivals.sh            # bigger steps, faster ramp
#   DB=phoenix_next ./scripts/ingest_arrivals.sh       # somewhere safer to rehearse
#   RESET=1 ./scripts/ingest_arrivals.sh               # forget the alive population, start over
#
# THE 90-SECOND RULE IS THE WHOLE DESIGN. Concurrency here is foreground-only and an event's
# state holds for tolerance_s = 90 seconds and no longer, so a session that stops emitting stops
# being concurrent whether or not it ever ended. A script that inserts 3,000 VideoPlay rows and
# waits produces a spike that collapses 90 seconds later, which looks like a load test and is
# actually a decay curve. So every cycle re-heartbeats the ENTIRE alive population. That, not the
# arrivals, is what holds the number up.
#
# WHY 5:1 CANNOT HOLD A TARGET, stated because the ratio was the requirement. Five in and one out
# is net plus four per cycle, forever: it is a growth rate, not a level. So the ramp runs at 5:1
# until concurrency reaches TARGET and the hold runs at 1:1 after that. Both ratios are printed
# each cycle, so which regime it is in is never a guess.
#
# ONE INSERT PER CYCLE, not three. Heartbeats, arrivals and departures are UNION ALLed into a
# single INSERT so a cycle costs one part rather than three (rule insert-batch-size: parts, not
# rows, are what overwhelm the merge process). Everything is generated server-side from
# numbers(), so no rows cross the wire.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${DB:-${CH_DATABASE:-phoenix}}"
export CH_DATABASE="$DB"
TARGET="${TARGET:-3000}"
ARRIVE="${ARRIVE:-1000}"       # arrivals per ramp cycle; departures are a fifth of this
PERIOD="${PERIOD:-45}"         # seconds between cycles. MUST stay under tolerance_s = 90.
CYCLES="${CYCLES:-0}"          # 0 = run until interrupted
TICK="${TICK:-1}"              # run a derive tick each cycle so the serving layer keeps up
STATE=".ingest_arrivals.$DB"

TOLERANCE_S=90
if [ "$PERIOD" -ge "$TOLERANCE_S" ]; then
  echo "REFUSING: PERIOD=$PERIOD is at or past the ${TOLERANCE_S}s gap tolerance." >&2
  echo "  Every alive session would fall out of the foreground before its next heartbeat," >&2
  echo "  and concurrency would sawtooth instead of holding. Use PERIOD under 90." >&2
  exit 1
fi

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

[ "${RESET:-0}" = "1" ] && rm -f "$STATE"
# lo = first session id still alive, hi = next id to hand out. Alive population is [lo, hi).
if [ -s "$STATE" ]; then read -r LO HI < "$STATE"; else LO=0; HI=0; fi
RUN="$(date -u +%Y%m%d%H%M%S)"

# event_id exists in phoenix and not in phoenix_next: it was ALTERed onto phoenix out of band on
# 2026-08-01 and generation 2 never got it. Detected rather than assumed, so one script rehearses
# in phoenix_next and runs in phoenix without a second copy drifting away from the first.
HAS_EVID="$(val "SELECT count() FROM system.columns
                 WHERE database = currentDatabase() AND table = 'raw_events_landing'
                   AND name = 'event_id'")"
if [ "${HAS_EVID:-0}" = "1" ]; then
  EVID_COL=", event_id"
  evid() { printf ", concat('ev_%s_%s_%s_', toString(n))" "$RUN" "$1" "$2"; }
else
  EVID_COL=""
  evid() { :; }
fi

echo "== $DB: target $TARGET, arrive $ARRIVE per cycle, period ${PERIOD}s, alive $(( HI - LO ))" >&2

# WHY A NEUTRAL HEARTBEAT AND NOT A `resume`. Concurrency here is not
# driven by pause and resume alone. Two separate things decide whether a
# session counts: WHICH state it is in, set by the decisive events (play,
# pause, resume, background, foreground, end), and WHETHER it still counts
# at all, which is the 90-second tolerance measured from its last event of
# ANY kind, neutral ones included. A session that played once and never
# paused still goes dark 90 seconds later, because nothing refreshed the
# second clock.
#
# So the keepalive has to refresh liveness WITHOUT changing state. That is
# exactly what a neutral heartbeat does, per decision D2: it carries the
# last decisive state forward and is forbidden from flipping it. Sending
# `resume` would also keep the session alive, and would lie: `resume` is
# REACTIVATING, so it claims the session had been paused. That inflates
# resume_count in session_insight_facts, manufactures paused-to-playing
# transitions that never happened, and corrupts the pause and resume
# analytics this data exists to support.
#
# The five values rotated through below are the most common real neutral
# heartbeats in the corpus, so vocabulary_check.sh sees nothing new and the
# heartbeat mix resembles the real one.

# The event vocabulary is the one the state machine actually classifies, from
# sql/schema/03_event_state.sql. VideoSessionStart and VideoPlay open a session,
# VideoSessionEnd closes it, and a bare VideoHeartbeat is NEUTRAL: it carries the previous
# decisive state forward without flipping it, which is exactly what a keepalive must do. Sending
# 'resume' instead would also work but would misrepresent a session that was never paused.
cycle=0
while :; do
  cycle=$(( cycle + 1 ))
  alive=$(( HI - LO ))

  if [ "$alive" -lt "$TARGET" ]; then
    regime="ramp 5:1"; arrive="$ARRIVE"; depart=$(( ARRIVE / 5 ))
  else
    regime="hold 1:1"; arrive=$(( ARRIVE / 5 )); depart=$(( ARRIVE / 5 ))
  fi
  # Never retire more than are alive, and never below zero.
  [ "$depart" -gt "$alive" ] && depart="$alive"

  new_lo=$(( LO + depart ))
  new_hi=$(( HI + arrive ))

  # One statement. `d` is the alive range AFTER departures, so a session cannot both be retired
  # and heartbeated in the same cycle, which would leave it open by carrying a neutral event
  # after its own end and would be silently dropped by the D8 end bound anyway.
  ch --query "
    INSERT INTO raw_events_landing
      (content_id, video_session_id, user_id, event_type, event, event_timestamp,
       platform, app_version, country, audio_language, subtitle_language, player_version,
       session_start_epoch${EVID_COL})
    WITH
      toUnixTimestamp64Milli(now64(3)) AS ts,
      ['ANDROID_PHONE','IPHONE','ANDROID_TV','WEB','FIRETV'] AS plats,
      ['india','usa','uae','uk','canada']                    AS ctys,
      ['6.34.8','6.25.1','8.9.5','3.11.1']                   AS vers,
      [2078157818, 2078157806, 2078158120, 20985523, 21009390] AS contents,
      ['network-activity','buffer-health','video-resize','BufferStart','BufferEnd'] AS hb
    -- KEEPALIVE for everyone still alive. Neutral heartbeat: carries the open state forward.
    SELECT
      contents[(n % 5) + 1],
      concat('ld_', toString(n)), concat('lu_', toString(n)),
      'VideoHeartbeat', hb[(n % 5) + 1], ts,
      plats[(n % 5) + 1], vers[(n % 4) + 1], ctys[(n % 5) + 1], 'hi', 'none', 'exo',
      ts$(evid "$cycle" h)
    FROM (SELECT ${new_lo} + number AS n FROM numbers(${new_hi} - ${arrive} - ${new_lo}))

    UNION ALL
    -- ARRIVALS. Start and play in the same millisecond; min() collapses ties and a close beats
    -- an open, but these are both opens so the session lands open either way.
    SELECT
      contents[(n % 5) + 1],
      concat('ld_', toString(n)), concat('lu_', toString(n)),
      arrayJoin(['VideoSessionStart','VideoPlay']) AS et,
      if(et = 'VideoPlay', 'Play', 'Start'), ts,
      plats[(n % 5) + 1], vers[(n % 4) + 1], ctys[(n % 5) + 1], 'hi', 'none', 'exo',
      ts$(evid "$cycle" a)
    FROM (SELECT ${HI} + number AS n FROM numbers(${arrive}))

    UNION ALL
    -- DEPARTURES. One VideoSessionEnd each. Per D13 the LAST end is terminal, and these sessions
    -- are never heartbeated again, so nothing can reopen them.
    SELECT
      contents[(n % 5) + 1],
      concat('ld_', toString(n)), concat('lu_', toString(n)),
      'VideoSessionEnd', 'VideoSessionEnd', ts,
      plats[(n % 5) + 1], vers[(n % 4) + 1], ctys[(n % 5) + 1], 'hi', 'none', 'exo',
      ts$(evid "$cycle" e)
    FROM (SELECT ${LO} + number AS n FROM numbers(${depart}))"

  LO="$new_lo"; HI="$new_hi"
  printf '%s %s\n' "$LO" "$HI" > "$STATE"

  [ "$TICK" = "1" ] && ./scripts/derive_tick.sh "$DB" >/dev/null 2>&1 || true

  # TWO numbers, because phoenix already carries a teammate's ingest at tens of thousands of
  # concurrent users and a total would not show what THIS script produced.
  #
  # `mine` counts distinct lu_ users whose derived minute-run covers the last completed minute.
  # It comes from user_minute_runs and not from user_concurrency_deltas, because the delta table
  # carries dimensions and not user_id, so a cohort cannot be separated out of it. sum(sign) > 0
  # is mandatory: user_minute_runs is a CollapsingMergeTree and a re-derived user has retraction
  # rows physically present until a merge removes them.
  mine="$(val "
    SELECT uniqExact(user_id) FROM (
      SELECT user_id FROM user_minute_runs
      WHERE user_id LIKE 'lu\\_%'
        AND run_start <= toStartOfMinute(now() - INTERVAL 1 MINUTE)
        AND run_end   >= toStartOfMinute(now() - INTERVAL 1 MINUTE)
      GROUP BY user_id, run_start, run_end HAVING sum(sign) > 0)
    SETTINGS max_execution_time = 30")"
  live="$(val "
    SELECT max(c) FROM (
      SELECT sum(d) OVER (ORDER BY minute) AS c
      FROM (SELECT minute, sum(delta) AS d FROM user_concurrency_deltas
            WHERE minute >= now() - INTERVAL 10 MINUTE GROUP BY minute))
    SETTINGS max_execution_time = 30")"

  printf 'cycle %-3s %-9s arrive %-5s depart %-5s alive %-6s mine_concurrent %-7s db_total %s\n' \
    "$cycle" "$regime" "$arrive" "$depart" "$(( HI - LO ))" "${mine:-pending}" "${live:-pending}" >&2

  [ "$CYCLES" != "0" ] && [ "$cycle" -ge "$CYCLES" ] && break
  sleep "$PERIOD"
done

echo "DONE. Alive population $(( HI - LO )). State in $STATE; RESET=1 to start over." >&2
