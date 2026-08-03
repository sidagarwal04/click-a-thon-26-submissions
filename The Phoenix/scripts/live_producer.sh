#!/usr/bin/env bash
# Live event producer: 15 concurrent Sony LIV live streams, ~12,000 concurrent sessions, held
# for an hour, written straight through the real ingest path.
#
#   ./scripts/live_producer.sh                          # phoenix_next, 120 cycles of 30s
#   TARGET=12000 CYCLES=120 PERIOD=30 ./scripts/live_producer.sh
#   DB=phoenix ./scripts/live_producer.sh                # aim at the graded database instead
#   RESET=1 ./scripts/live_producer.sh                   # forget the alive population, start over
#
# ---------------------------------------------------------------------------------------------
# THE 90-SECOND RULE IS THE WHOLE DESIGN. Concurrency here is foreground-only, and an event's
# state holds for tolerance_s = 90 seconds and no longer. A session that stops emitting stops
# being concurrent whether or not it ever ended. So every cycle re-heartbeats the ENTIRE alive
# population; that, and not the arrivals, is what holds the curve up. PERIOD must stay under 90.
#
# WHY ONE INSERT PER CYCLE AND NOT ONE PER STREAM. Parts, not rows, are what overwhelm the merge
# process (ClickHouse rule insert-batch-size: 10K-100K rows per INSERT). All 15 streams and all
# five event classes are UNION ALLed into a single statement measuring 40,536 rows at p50 in a
# live run, which is inside that band. Everything is generated server-side from numbers(), so no rows cross the wire
# and a bigger demo costs no more network than a smaller one.
#
# WHY NOT PARALLEL PRODUCER PROCESSES. Because generation is server-side, a second producer adds
# no throughput. It only splits one well-sized part into two half-sized ones and doubles the merge
# work. The concurrency that is worth having is between DIFFERENT jobs (produce, derive, query),
# which is what live_demo.sh runs.
#
# WHY BACKGROUNDING IS THE DIP MECHANIC AND NOT AN EARLY END. An ad break modelled as
# VideoSessionEnd is indistinguishable from the match finishing. Modelled as AppBackgrounded the
# session stays open, stops counting, and counts again when it foregrounds, which is the exact
# behaviour this whole problem exists to measure. 100% of sessions in the real corpus background at
# least once; the previous generator emitted none, so it could not demonstrate the thesis at all.
#
# WHY THE VOCABULARY IS SAMPLED AS JOINT TUPLES. Picking each dimension independently manufactures
# devices that do not exist: an IPHONE with player_version 1.8.2, a TV app_version on a phone. The
# corpus pairs them (IPHONE always with 1.1/HIN/UND, ANDROID_PHONE with 1.8.2/hin/UNK), so whole
# tuples are lifted from the frozen slice and used as units.
#
# COUNTRY IS A DECLARED SYNTHESIS, NOT CORPUS. The frozen corpus is india-only. The diaspora mix
# below is invented so the country filter is demonstrable, and it is stated here and in
# docs/DEMO_LIVE.md rather than quietly injected. The usa/uk/uae/canada rows previously in the live
# slice came from the old generator the same way, undeclared, which is the practice being replaced.
# ---------------------------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

# DEFAULTS TO phoenix_next, NOT phoenix. phoenix is the graded database: it holds the validated
# 905,558-row corpus the benchmark answers come from, and its frozen slice must stay still.
# phoenix_next is generation two and is where live ingest and the insight layer live, which is
# also what the frontend reads. Pass DB=phoenix explicitly to aim at the graded one.
DB="${DB:-${CH_DATABASE:-phoenix_next}}"
export CH_DATABASE="$DB"
TARGET="${TARGET:-12000}"      # peak concurrent sessions across all streams
PERIOD="${PERIOD:-30}"         # seconds between cycles. MUST stay under tolerance_s = 90.
CYCLES="${CYCLES:-120}"        # 120 x 30s = one hour. 0 = until interrupted.
HEARTBEATS="${HEARTBEATS:-2}"  # keepalives per session per cycle (~15s cadence at PERIOD=30)
LIFETIME_CYCLES="${LIFETIME_CYCLES:-12}"  # mean session life; 12 x 30s = 6 min, corpus median 11.9
STATE=".live_producer.$DB"
SQLFILE="$(mktemp -t phoenix-live-producer.XXXXXX.sql)"
trap 'rm -f "$SQLFILE"' EXIT

TOLERANCE_S=90
if [ "$PERIOD" -ge "$TOLERANCE_S" ]; then
  echo "REFUSING: PERIOD=$PERIOD is at or past the ${TOLERANCE_S}s gap tolerance." >&2
  echo "  Every alive session would fall out of the foreground before its next heartbeat and" >&2
  echo "  the curve would sawtooth instead of holding. Use PERIOD under 90." >&2
  exit 1
fi

# Reads keep stderr quiet; the INSERT deliberately does NOT. A producer whose insert fails
# silently under `set -e` dies with an empty log and looks like a hang, which cost a debugging
# round the first time this ran.
ch()  { ./scripts/ch.sh "$@" 2>/dev/null; }
chw() { ./scripts/ch.sh "$@"; }
val() { ch --format TSVRaw --query "$1" | head -1; }

# THE CORPUS BOUNDARY IS PINNED HERE AND IS NOT $FROZEN_BEFORE.
#
# live_demo.sh exports FROZEN_BEFORE two days out so the serving queries can SEE the live slice --
# that is correct for reading a live curve, and poison for choosing what to generate. ch.sh
# injects $FROZEN_BEFORE into every {frozen_before} placeholder, so the stream-ranking and
# vocabulary queries below silently widened to include synthetic rows and started sampling the
# generator's own past output as though it were the real corpus.
#
# Measured: with FROZEN_BEFORE=2026-08-03 the producer announced
# `head stream 990001 carries 60%` -- content_id 990001 is the synthetic spike-test fixture, which
# has zero real viewers and dimension values that exist nowhere in the corpus. One more run and
# the vocabulary would have been sampled from it too, and the "corpus-only" guarantee would have
# been quietly false while every check still passed.
#
# So the corpus reads bind frozen_before EXPLICITLY, at the graded boundary, whatever the ambient
# environment says.
CORPUS_BEFORE="${CORPUS_BEFORE:-2026-08-01}"
cval() { ch --format TSVRaw --param_frozen_before "$CORPUS_BEFORE" --query "$1" | head -1; }

# --------------------------------------------------------------------------------------------
# Stream schedule. Fifteen real live-type titles, resolved from the content table at startup so
# the demo names real content and title/category filters resolve.
#
# The head stream carries 60% of the audience, the other fourteen share 40% on a Zipf tail. That
# is a marquee-match shape: the real corpus head is 19%, which is a normal day rather than a final.
#
# PEAK MINUTES ARE DELIBERATELY SPREAD, and tv_share is correlated with peak_min so TV-heavy
# streams peak later than mobile-heavy ones. This is the property the problem statement singles
# out: "a dimension like platform and a content might peak at one minute, while a combination like
# platform + country might reach its peak at an entirely different minute". If every stream shared
# one platform mix and one peak, every dimension combination would peak together and the demo would
# skip the hard part. sql/queries/serving/test_peak_is_not_a_rollup.sql is the assertion.
#
#          share  peak_min  decay_min  end_min  tv_share%
SCHED=(
  "6000  8  40  56  25"
  "1230 20  44  58  35"
  " 615 32  48  58  47"
  " 410 14  42  57  30"
  " 308 26  46  58  41"
  " 246 38  50  59  53"
  " 205 10  40  56  27"
  " 176 22  44  58  37"
  " 154 34  48  58  49"
  " 137 16  42  57  31"
  " 123 28  46  58  43"
  " 112 40  50  59  55"
  " 103 12  40  57  29"
  "  95 24  44  58  39"
  "  88 36  48  59  51"
)
NSTREAMS=${#SCHED[@]}

# --------------------------------------------------------------------------------------------
# Vocabulary, lifted from the frozen slice as whole tuples.
# --------------------------------------------------------------------------------------------
tuples_for() {   # $1 = 'tv' | 'mobile'
  local pred="platform LIKE '%TV%'"
  [ "$1" = mobile ] && pred="NOT (platform LIKE '%TV%')"
  cval "SELECT concat('[', arrayStringConcat(groupArray(t), ','), ']') FROM (
         SELECT concat('(', arrayStringConcat(arrayMap(x -> concat('''', x, ''''),
                  [platform, app_version, audio_language, subtitle_language, player_version]), ','), ')') AS t,
                count() AS c
         FROM raw_events
         WHERE event_timestamp < {frozen_before:String} AND $pred
         GROUP BY platform, app_version, audio_language, subtitle_language, player_version
         ORDER BY c DESC LIMIT 12)"
}

echo "== $DB: resolving live streams and vocabulary from the frozen corpus" >&2
# Ranked by July traffic so the head stream is a title that really was the big one, but NOT
# restricted to titles that had traffic: only 9 of the 193 live titles appear in the frozen slice,
# and a live stream starting tonight has no reason to have been watched last month. The rest are
# filled from the live catalogue by content_id, deterministically.
CONTENT_IDS="$(cval "SELECT arrayStringConcat(groupArray(toString(content_id)), ',') FROM (
  SELECT c.content_id AS content_id, countIf(r.event_timestamp < {frozen_before:String}) AS n
  FROM content c LEFT JOIN raw_events r ON r.content_id = c.content_id
  WHERE c.video_type = 'live'
  GROUP BY c.content_id ORDER BY n DESC, content_id ASC LIMIT $NSTREAMS)")"
IFS=',' read -r -a CIDS <<<"$CONTENT_IDS"
[ "${#CIDS[@]}" = "$NSTREAMS" ] || { echo "REFUSING: resolved ${#CIDS[@]} live content ids, need $NSTREAMS" >&2; exit 1; }

TUP_TV="$(tuples_for tv)"
TUP_MO="$(tuples_for mobile)"
[ -n "$TUP_TV" ] && [ -n "$TUP_MO" ] || { echo "REFUSING: could not sample dimension tuples" >&2; exit 1; }

# Declared synthesis. Cumulative weights out of 1000: india 92%, then the diaspora tail.
CTYS="['india','usa','uae','uk','singapore','australia','canada']"
CTYW="[920,945,965,980,990,996,1000]"
# The five most common neutral heartbeat values in the corpus. Neutral is mandatory: it refreshes
# liveness without flipping state. 'resume' would also keep a session alive and would LIE, since
# resume is REACTIVATING and claims the session had been paused, inflating resume_count and
# manufacturing paused-to-playing transitions in the insight layer.
HB="['network-activity','buffer-health','video-resize','BufferStart','BufferEnd']"

# event_id exists on phoenix.raw_events_landing (added by an out-of-band ALTER) and not on
# generations built from the committed DDL. Detected, never assumed: one script then runs against
# either without a second copy drifting away from the first.
HAS_EVID="$(val "SELECT count() FROM system.columns
                 WHERE database = currentDatabase() AND table = 'raw_events_landing' AND name = 'event_id'")"
if [ "${HAS_EVID:-0}" = "1" ]; then EVID_COL=", event_id"; else EVID_COL=""; fi
evid() { [ "${HAS_EVID:-0}" = "1" ] && printf ", concat('ev_%s_%s_', toString(number))" "$RUN" "$1" || true; }

# --------------------------------------------------------------------------------------------
# State: one line per stream, "lo hi". The alive population of stream i is [lo_i, hi_i).
# Departures retire from the low end, so a session's life is (hi-lo)/departures_per_cycle cycles,
# which is how LIFETIME_CYCLES turns into a real 0-15 minute lifetime distribution.
# --------------------------------------------------------------------------------------------
[ "${RESET:-0}" = "1" ] && rm -f "$STATE"
declare -a LO HI
if [ -s "$STATE" ]; then
  RUN="$(head -1 "$STATE")"
  CYCLE0="$(sed -n 2p "$STATE")"
  i=0; while read -r lo hi; do LO[$i]=$lo; HI[$i]=$hi; i=$((i+1)); done < <(tail -n +3 "$STATE")
else
  RUN="$(date -u +%Y%m%d%H%M%S)"; CYCLE0=0
  for ((i=0; i<NSTREAMS; i++)); do LO[$i]=0; HI[$i]=0; done
fi

save_state() {
  { echo "$RUN"; echo "$cycle_abs"
    for ((i=0; i<NSTREAMS; i++)); do echo "${LO[$i]} ${HI[$i]}"; done; } > "$STATE"
}

# Piecewise curve: ramp from 0 to peak_min, plateau to decay_min, linear decay to end_min.
# Integer arithmetic throughout; bash has no floats and this does not need them.
curve() {   # $1=share $2=peak_min $3=decay_min $4=end_min $5=elapsed_min  -> target concurrency
  local share=$1 pk=$2 dc=$3 en=$4 t=$5
  if   [ "$t" -lt "$pk" ]; then echo $(( share * (t + 1) / (pk + 1) ))
  elif [ "$t" -lt "$dc" ]; then echo "$share"
  elif [ "$t" -lt "$en" ]; then echo $(( share * (en - t) / (en - dc) ))
  else echo 0; fi
}

echo "== $DB: $NSTREAMS live streams, target $TARGET, period ${PERIOD}s, $CYCLES cycles" >&2
echo "   head stream ${CIDS[0]} carries 60%; peaks spread 8-40 min; tv_share rises with peak_min" >&2

cycle_abs="$CYCLE0"
c=0
while :; do
  c=$(( c + 1 )); cycle_abs=$(( cycle_abs + 1 ))
  elapsed_min=$(( cycle_abs * PERIOD / 60 ))

  BRANCHES=""; tot_arr=0; tot_dep=0; tot_alive=0
  for ((i=0; i<NSTREAMS; i++)); do
    read -r share pk dc en tvs <<<"${SCHED[$i]}"
    # Scale the schedule's shares (which sum to ~10,000) to the requested TARGET.
    share=$(( share * TARGET / 10000 ))
    target=$(curve "$share" "$pk" "$dc" "$en" "$elapsed_min")
    alive=$(( HI[i] - LO[i] ))

    # Natural turnover plus whatever the curve demands. Turnover alone gives every session a
    # LIFETIME_CYCLES-long life; the curve term is what moves the level.
    churn=$(( alive / LIFETIME_CYCLES ))
    depart=$(( churn + (alive > target ? alive - target : 0) ))
    arrive=$(( churn + (target > alive ? target - alive : 0) ))
    [ "$depart" -gt "$alive" ] && depart="$alive"

    new_lo=$(( LO[i] + depart )); new_hi=$(( HI[i] + arrive ))
    cid="${CIDS[$i]}"
    sid="concat('ls_${RUN}_${i}_', toString(number))"
    # 1 session in 8 reuses its neighbour's user id, so ~12% of users hold two concurrent
    # sessions. The corpus runs 1.13 sessions per user; without this, user concurrency and
    # session concurrency would be identical and user_minute_runs would prove nothing.
    # USER IDS ARE STREAM-SCOPED, EXCEPT FOR A DELIBERATE CROSS-STREAM POOL.
    #
    # `du_<run>_<stream>_<n>` means a user belongs to exactly one stream, so a user could only
    # ever watch one content. That quietly disabled a whole console view: measured, only 151 of
    # 155,403 live users appeared on more than one content (hash collisions, not switches)
    # against 16,557 on more than one platform, and user_content_transitions therefore sat frozen
    # at 2026-07-26, the last content switch in the REAL corpus. The pipeline was correct the
    # whole time; the generator simply could not produce the event it was meant to demonstrate.
    #
    # So one session in 25 draws its user from a run-wide pool shared by all fifteen streams.
    # Those users land on different content and produce genuine switches. The pool is bounded at
    # 2,000 so collisions are frequent enough to matter across a 15-stream demo rather than being
    # a long-tail curiosity.
    #
    # The 1-in-8 neighbour reuse below stays: it is what makes a user hold two CONCURRENT sessions
    # (corpus ratio 1.13 sessions per user) and is a different phenomenon from switching content.
    uid="if(number % 25 = 0,
             concat('du_${RUN}_x_', toString(cityHash64(number, 'x') % 2000)),
             concat('du_${RUN}_${i}_', toString(if(number % 8 = 0, number - 1, number))))"
    # Reference the hoisted WITH aliases, never the array literals. Inlining them put the two
    # 12-tuple arrays into all 75 branches and the statement reached ~90 KB, which the shell
    # rejected outright with "Argument list too long". Named once, used everywhere.
    tup="if(cityHash64(number, 'p') % 100 < $tvs, tvt[(cityHash64(number,'t') % length(tvt)) + 1],
                                                 mot[(cityHash64(number,'m') % length(mot)) + 1])"
    cty="ctys[arrayFirstIndex(x -> (cityHash64(number, 'c') % 1000) < x, ctyw)]"
    dims="tp.1, tp.2, $cty, tp.3, tp.4, tp.5"
    # Spread every row across the cycle instead of stamping them all with one now64(3).
    #
    # Realism is the smaller half of the reason. The larger half: the incremental derive's window
    # is HALF-OPEN (sql/pipeline/03_derive_incremental.sql:35, `event_timestamp < to_ts`) and
    # derive_tick.sh sets to_ts = max(event_timestamp). Rows sitting exactly at the max are
    # therefore outside every window that ends at them. With all 30,000 rows of a cycle sharing one
    # instant, that is the entire cycle: measured, 2,024 raw rows produced 0 foreground intervals
    # and a flat zero curve. Jitter makes the max a single row rather than the whole batch.
    jit="(cityHash64(number, 'j') % $(( PERIOD * 1000 )))"
    hbjit="(cityHash64(number, 'j') % $(( (PERIOD / HEARTBEATS) * 1000 )))"

    # --- keepalive: every session alive AFTER this cycle's departures ---------------------
    # HEARTBEATS per cycle, spread backwards from now so the cadence resembles the corpus's
    # ~11.8s rather than one lonely row per period.
    if [ $(( new_hi - arrive - new_lo )) -gt 0 ]; then
      BRANCHES="${BRANCHES}${BRANCHES:+ UNION ALL }
      SELECT $cid, $sid, $uid, 'VideoHeartbeat', hb[(number % 5) + 1],
             ts - (hbo * 1000) - $hbjit, $dims, ts - (hbo * 1000) - $hbjit$(evid h)
      FROM (SELECT $new_lo + number AS number, $tup AS tp FROM numbers($(( new_hi - arrive - new_lo ))))
      ARRAY JOIN range(0, $PERIOD, $(( PERIOD / HEARTBEATS ))) AS hbo"
    fi

    # --- arrivals: start and play in the same millisecond ---------------------------------
    if [ "$arrive" -gt 0 ]; then
      BRANCHES="${BRANCHES}${BRANCHES:+ UNION ALL }
      SELECT $cid, $sid, $uid, et, if(et = 'VideoPlay', 'Play', 'Start'), ts - $jit,
             $dims, ts - $jit$(evid a)
      FROM (SELECT ${HI[i]} + number AS number, $tup AS tp FROM numbers($arrive))
      ARRAY JOIN ['VideoSessionStart','VideoPlay'] AS et"
    fi

    # --- departures: one VideoSessionEnd each, never heartbeated again ---------------------
    if [ "$depart" -gt 0 ]; then
      BRANCHES="${BRANCHES}${BRANCHES:+ UNION ALL }
      SELECT $cid, $sid, $uid, 'VideoSessionEnd', 'VideoSessionEnd', ts - $jit,
             $dims, ts - $jit$(evid e)
      FROM (SELECT ${LO[i]} + number AS number, $tup AS tp FROM numbers($depart))"
    fi

    # --- backgrounding: one seventh of the alive population goes background this cycle, and
    #     the seventh that went last cycle comes back. ~14% backgrounded at any instant, and
    #     over a 12-cycle life most sessions background at least once, as the corpus does.
    if [ $(( new_hi - arrive - new_lo )) -gt 6 ]; then
      span=$(( new_hi - arrive - new_lo ))
      BRANCHES="${BRANCHES} UNION ALL
      SELECT $cid, $sid, $uid, 'AppBackgrounded', 'AppBackgrounded', ts - $jit,
             $dims, ts - $jit$(evid b)
      FROM (SELECT $new_lo + (number * 7) + ($c % 7) AS number, $tup AS tp
            FROM numbers($(( span / 7 )))) WHERE number < $(( new_hi - arrive ))
      UNION ALL
      SELECT $cid, $sid, $uid, 'AppForegrounded', 'AppForegrounded', ts - $jit,
             $dims, ts - $jit$(evid f)
      FROM (SELECT $new_lo + (number * 7) + (($c + 6) % 7) AS number, $tup AS tp
            FROM numbers($(( span / 7 )))) WHERE number < $(( new_hi - arrive ))"
    fi

    LO[$i]=$new_lo; HI[$i]=$new_hi
    tot_arr=$(( tot_arr + arrive )); tot_dep=$(( tot_dep + depart ))
    tot_alive=$(( tot_alive + new_hi - new_lo ))
  done

  # ONE statement, all fifteen streams, all five event classes.
  # Written to a file rather than passed as argv. Even hoisted, a 15-stream statement is tens of
  # kilobytes, and --query puts that in the argument list where it competes with the environment
  # for ARG_MAX. A file has no such ceiling, so the demo scales with TARGET instead of dying at it.
  cat > "$SQLFILE" <<SQL
INSERT INTO raw_events_landing
  (content_id, video_session_id, user_id, event_type, event, event_timestamp,
   platform, app_version, country, audio_language, subtitle_language, player_version,
   session_start_epoch${EVID_COL})
WITH toUnixTimestamp64Milli(now64(3)) AS ts,
     ${TUP_TV} AS tvt,
     ${TUP_MO} AS mot,
     ${CTYS} AS ctys,
     ${CTYW} AS ctyw,
     ${HB} AS hb
$BRANCHES
SQL
  # RETRIED, because an hour-long run against a cloud service will meet the network.
  # Measured: cycle 24 of the first full run died on
  #   Code: 209 NetException: Timeout: connect timed out ... (SOCKET_TIMEOUT)
  # at 9,987 of a 12,000 target. Nothing was wrong with the data or the query; a single TCP
  # connect blipped, `set -e` killed the producer, and live_demo.sh's EXIT trap then tore down
  # the deriver and all three query workers. One transient packet loss ended a sixty-minute demo
  # twelve minutes in.
  #
  # A dropped cycle is survivable on its own terms: the population is held in $STATE, not in the
  # database, so the next cycle re-heartbeats everyone and the curve closes the gap. What is NOT
  # survivable is exiting. So failures are retried, and a cycle that fails all three attempts is
  # reported and skipped rather than fatal.
  #
  # NO async_insert HERE, and its absence is deliberate. An earlier version set
  # `--async_insert=1 --wait_for_async_insert=1` on this statement, which reads like diligence and
  # does nothing: async inserts apply to INSERT with FORMAT/VALUES data, never to INSERT ... SELECT.
  # Measured over 40 minutes of live ingest: system.asynchronous_insert_log recorded 0 events for
  # this database while every cycle carried the setting.
  #
  # It would be wrong even if it worked. Per ClickHouse rule insert-async-small-batches, async
  # insert exists for "when client-side batching isn't practical". Ours is practical and already
  # done: measured p50 53,972 rows per statement, inside the 10K-100K band insert-batch-size asks
  # for, at one statement per 30s. Async would buffer an already correctly-sized batch, adding a
  # copy and a flush delay to solve a problem this producer does not have.
  ok=0
  for attempt in 1 2 3; do
    if chw --connect_timeout=30 --receive_timeout=120 --queries-file "$SQLFILE"; then
      ok=1; break
    fi
    echo "  cycle $c insert failed (attempt $attempt/3), retrying in $((attempt * 5))s" >&2
    sleep $(( attempt * 5 ))
  done
  if [ "$ok" != "1" ]; then
    echo "  cycle $c SKIPPED after 3 failed attempts; population held, next cycle will catch up" >&2
  fi

  save_state
  printf 'cycle %-4s t+%-3smin  arrive %-6s depart %-6s alive %-7s streams %s\n' \
    "$c" "$elapsed_min" "$tot_arr" "$tot_dep" "$tot_alive" "$NSTREAMS" >&2

  [ "$CYCLES" != "0" ] && [ "$c" -ge "$CYCLES" ] && break
  sleep "$PERIOD"
done

echo "DONE. Alive population $tot_alive. State in $STATE; RESET=1 to start over." >&2
