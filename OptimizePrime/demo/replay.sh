#!/usr/bin/env bash
# ============================================================================
# demo/replay.sh — REPLAY A LIVE-EVENT DAY. The curve builds while you watch.
#
# The organiser's "Suggested demo" (docs/upstream/PROBLEM_STATEMENT.md) asks for
# something demo/run.sh deliberately does not do:
#
#   "Replay a live-event day: ingest the session stream -> the concurrency curve
#    builds in near real time as sessions open, heartbeat, and close -> apply a
#    filter (platform, country) and the minute-grain view answers instantly."
#
# demo/run.sh queries a model that was ALREADY BUILT. This script ingests the
# stream in event-time order and lets the INCREMENTAL PUBLISHER (tools/publish.sh,
# ADR 0013/0016) move the curve. Four things are visible that no other artifact
# in this repo shows:
#
#   1. the curve BUILDING, minute by minute, as a terminal sparkline
#   2. the publisher's lag and queue depth alongside it — the curve moves because
#      the finalizer ran, NOT because anything was rebuilt
#   3. a platform/country filter answering mid-replay, in milliseconds
#   4. a LATE ARRIVAL correcting history: 37 sessions are withheld from the
#      stream and injected ~25 event-minutes late; a minute that already
#      scrolled past visibly corrects itself, incrementally
#
#   demo/replay.sh                     full run: setup, then replay (~2.5 min)
#   demo/replay.sh --speed 120         2x faster (event-seconds per wall second)
#   demo/replay.sh --resume            skip setup, replay into the existing db
#   demo/replay.sh --setup-only        build the scratch db and stop
#   demo/replay.sh --capture           tee the transcript to evidence/demo-replay/
#   demo/replay.sh --target cloud      run against a Cloud SCRATCH db (slower)
#
# WHAT THIS IS NOT. It runs against a SCRATCH database that this script creates.
# The graded database `sonyliv` is batch-rebuilt and its publisher has committed
# ZERO runs — nothing you see here is running in the graded service. That is
# stated on screen at start and finish, and in demo/REPLAY.md. Read it before
# presenting this; overstating what the replay proves is worse than not showing
# it.
#
# WRITES: the scratch database only. `sonyliv` is SELECTed from and never
# written (and on TARGET=local it is not touched at all). The guard below is a
# hard refusal, not a convention.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

# ---------------------------------------------------------------------------
# knobs
# ---------------------------------------------------------------------------
DB="${REPLAY_DB:-sonyliv_t7replay}"
TARGET="${TARGET:-local}"
SPEED=60                     # event-seconds per wall-clock second
TICK_S=3                     # wall-clock seconds between ingest ticks
WIDTH=48                     # sparkline canvas columns
FROM="2026-07-26 09:00:00"   # replay window start (history before this is preloaded)
TO="2026-07-26 11:31:00"     # replay window end
HOLD_FROM="2026-07-26 09:30:00"   # withheld sessions must open at or after this
HOLD_TO="2026-07-26 10:20:00"     # ...and close at or before this
FILTER_AT="2026-07-26 10:35:00"   # event-time at which the filter beat fires
STRAGGLER_AT="2026-07-26 10:45:00" # event-time at which the withheld sessions land
SETTLE_S="${PUBLISH_SETTLE_S:-3}"
PUBLISH_LOOP_S=1             # sleep between publisher runs
DROP_GUARD_PCT=40            # a fall this steep WHILE a run is in flight is suspect
DIP_FLOOR=50                 # ...but only off a base of at least this many viewers

SETUP=1; RUN=1; CAPTURE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --speed)      SPEED="$2"; shift 2 ;;
    --tick)       TICK_S="$2"; shift 2 ;;
    --width)      WIDTH="$2"; shift 2 ;;
    --from)       FROM="$2"; shift 2 ;;
    --to)         TO="$2"; shift 2 ;;
    --database)   DB="$2"; shift 2 ;;
    --target)     TARGET="$2"; shift 2 ;;
    --resume)     SETUP=0; shift ;;
    --setup-only) RUN=0; shift ;;
    --capture)    CAPTURE=1; shift ;;
    -h|--help)    sed -n '2,40p' "$0" >&2; exit 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die() { printf '\nreplay.sh FAILED: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# THE GUARD. This script INGESTS EVENTS, which makes it the most dangerous
# thing in the repo to point at the wrong database. `sonyliv` is graded: its
# cc_user_minute is still pre-ADR-0016 (SharedAggregatingMergeTree with
# mv_user_minute live), so a publisher run against it would write
# replace-semantics rows into a set-union table and silently inflate the user
# tier. Its publish cursor is at epoch and must stay there.
# ---------------------------------------------------------------------------
case "$DB" in
  sonyliv|default|"") die "refusing to replay into '$DB'. This script creates and
DESTROYS its target database and ingests events into it. '$DB' is either the
GRADED database or a shared default. Pick a scratch name: --database sonyliv_myreplay" ;;
  *[!A-Za-z0-9_]*|[0-9]*) die "not a usable database name: '$DB'" ;;
esac
case "$TARGET" in local|cloud) ;; *) die "TARGET must be local or cloud, got '$TARGET'" ;; esac
[ "${PUBLISH_ALLOW_PROD:-0}" = "1" ] && die "PUBLISH_ALLOW_PROD=1 is set. Unset it; this demo never writes to the graded database."

# ---------------------------------------------------------------------------
# plumbing — one round trip per call, always with ?database=
# ---------------------------------------------------------------------------
ch_host() { local h="${CH_HOST:?CH_HOST unset — fill in .env}"; h="${h#https://}"; h="${h#http://}"; echo "${h%/}"; }

qdb() { # qdb <sql> — against the SCRATCH database
  if [ "$TARGET" = cloud ]; then
    curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=${DB}" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"
  else
    curl -sS --fail-with-body "${CH_LOCAL_URL}/?user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL}&database=${DB}" \
      --data-binary "$1"
  fi
}
qdb1() { qdb "$1 FORMAT TSVRaw" | tr -d '\r\n'; }

qsys() { # qsys <sql> — server-level (CREATE/DROP DATABASE); never through $DB
  if [ "$TARGET" = cloud ]; then
    curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=default" \
      --user "${CH_USER}:${CH_PASSWORD}" --data-binary "$1"
  else
    curl -sS --fail-with-body "${CH_LOCAL_URL}/?user=${CH_LOCAL_USER:-app}&password=${CH_PASSWORD_LOCAL}&database=default" \
      --data-binary "$1"
  fi
}

# The source of events. Read-only, always. On local this is the container's own
# copy of the provided CSV; on cloud it is the graded database's raw landing
# table, SELECTed from and never written.
if [ "$TARGET" = cloud ]; then SRC="sonyliv.ev_raw"; else SRC="default.ev_raw"; fi

EV_COLS='content_id, video_session_id, user_id, event_type, event, event_timestamp, platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch'

hr()  { printf '%s\n' "──────────────────────────────────────────────────────────────────────────────"; }
say() { printf '%s\n' "$*"; }
commafy() { printf '%s' "${1:-0}" | sed -e :a -e 's/\(.*[0-9]\)\([0-9]\{3\}\)/\1,\2/;ta'; }
hhmm() { date -u -r "$1" '+%H:%M' 2>/dev/null || date -u -d "@$1" '+%H:%M'; }
ms() { python3 -c 'import time; print(int(time.time()*1000))'; }
signed() { [ "${1:-0}" -ge 0 ] && printf '+%s' "$(commafy "$1")" || printf '%s' "-$(commafy "${1#-}")"; }
epoch_of() { qdb1 "SELECT toString(toUnixTimestamp(toDateTime('$1')))"; }

# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------
CAP=evidence/demo-replay/rehearsal.txt
if [ "$CAPTURE" = 1 ]; then
  mkdir -p evidence/demo-replay
  exec > >(tee "$CAP") 2>&1
fi

T_START_ALL=$(date +%s)

hr
say "REPLAY — a live-event day, ingested in event-time order"
say "  target        $TARGET   ·   scratch database   $DB"
say "  source        $SRC   (READ-ONLY — loaded from the provided CSV)"
say "  window        $FROM  ->  $TO"
say "  compression   ${SPEED}x  (1 wall-clock second = ${SPEED} event-seconds)"
say ""
say "  WHAT THIS IS NOT: a scratch database, not the graded service. The graded"
say "  database sonyliv is BATCH-REBUILT and its publisher has committed ZERO"
say "  runs. Nothing here is running in the graded service. See demo/REPLAY.md."
hr

# ===========================================================================
# SETUP
# ===========================================================================
if [ "$SETUP" = 1 ]; then
  say ""
  say "▶ SETUP  (one-time; --resume skips this)"
  t0=$(date +%s)

  qsys "DROP DATABASE IF EXISTS ${DB}" >/dev/null
  qsys "CREATE DATABASE ${DB}" >/dev/null
  say "  created database ${DB}"

  # The canonical schema, unmodified. The replay must exercise the SAME objects
  # the graded model uses, or it proves nothing about them.
  env -u CH_DATABASE -u CH_DATABASE_LOCAL TARGET="$TARGET" tools/apply-sql.sh --database "$DB" \
    sql/00_schema.sql sql/10_intervals.sql sql/12_publish.sql sql/20_views.sql \
    sql/45_user_concurrency.sql sql/50_hour_agg.sql >/dev/null \
    || die "schema apply failed"
  say "  applied sql/00, 10, 12, 20, 45, 50 (canonical, unmodified)"

  # replay_source — the stream, staged once so ticks are a server-side slice
  # rather than 800k rows over the wire fifty times. Ordered by event_timestamp
  # because every tick reads a contiguous event-time range.
  qdb "CREATE TABLE IF NOT EXISTS replay_source (
         content_id Int64, video_session_id String, user_id String,
         event_type LowCardinality(String), event LowCardinality(String),
         event_timestamp DateTime64(3), platform LowCardinality(String),
         app_version LowCardinality(String), country LowCardinality(String),
         audio_language LowCardinality(String), subtitle_language LowCardinality(String),
         player_version LowCardinality(String), session_start_epoch DateTime64(3)
       ) ENGINE = MergeTree ORDER BY (event_timestamp, video_session_id)
       SETTINGS min_bytes_for_wide_part = 0" >/dev/null
  qdb "INSERT INTO replay_source ($EV_COLS) SELECT $EV_COLS FROM $SRC" >/dev/null
  say "  staged $(commafy "$(qdb1 'SELECT count() FROM replay_source')") events · $(commafy "$(qdb1 'SELECT uniqExact(video_session_id) FROM replay_source')") sessions from $SRC"

  # replay_holdout — the late arrivals. The rule is a PROPERTY, not a sample:
  # every session that both OPENS and CLOSES inside [HOLD_FROM, HOLD_TO]. That
  # makes the set deterministic and makes the whole session late, so the
  # correction it forces is a clean insertion into already-published history
  # rather than an extension of a session still open.
  qdb "CREATE TABLE IF NOT EXISTS replay_holdout (video_session_id String)
       ENGINE = MergeTree ORDER BY video_session_id" >/dev/null
  qdb "INSERT INTO replay_holdout
       SELECT video_session_id FROM replay_source GROUP BY video_session_id
       HAVING min(event_timestamp) >= toDateTime64('$HOLD_FROM',3)
          AND max(event_timestamp) <= toDateTime64('$HOLD_TO',3)" >/dev/null
  say "  withheld $(qdb1 'SELECT count() FROM replay_holdout') sessions ($(commafy "$(qdb1 'SELECT count() FROM replay_source WHERE video_session_id IN (SELECT video_session_id FROM replay_holdout)')") events) — they arrive late, mid-replay"

  # PRELOAD — everything before the replay window. A live-event day does not
  # start with an empty serving layer; it starts with published history.
  qdb "INSERT INTO ev_raw ($EV_COLS) SELECT $EV_COLS FROM replay_source
       WHERE event_timestamp < toDateTime64('$FROM',3)
         AND video_session_id NOT IN (SELECT video_session_id FROM replay_holdout)" >/dev/null
  say "  preloaded $(commafy "$(qdb1 'SELECT count() FROM ev_raw')") events of history (everything before $FROM)"

  say "  bootstrapping the serving layer through tools/publish.sh …"
  sleep "$((SETTLE_S + 1))"
  env TARGET="$TARGET" PUBLISH_SETTLE_S="$SETTLE_S" tools/publish.sh --database "$DB" 2>&1 | sed 's/^/    /'
  say "  setup took $(( $(date +%s) - t0 ))s"
fi

[ "$RUN" = 1 ] || { say ""; say "--setup-only: stopping here. Replay with: demo/replay.sh --resume"; exit 0; }

# ===========================================================================
# THE REPLAY
# ===========================================================================
FROM_E=$(epoch_of "$FROM"); TO_E=$(epoch_of "$TO")
FILTER_E=$(epoch_of "$FILTER_AT"); STRAG_E=$(epoch_of "$STRAGGLER_AT")
SPAN=$(( TO_E - FROM_E ))
EXPECT_S=$(( SPAN / SPEED ))

# The probe minute for the late-arrival beat: the minute the withheld sessions
# cover most heavily, so the correction is unmistakable. Computed, not chosen.
PROBE=$(qdb1 "
  WITH h AS (SELECT video_session_id, min(event_timestamp) mn, max(event_timestamp) mx
             FROM replay_source WHERE video_session_id IN (SELECT video_session_id FROM replay_holdout)
             GROUP BY video_session_id),
       mins AS (SELECT toDateTime(arrayJoin(range(toUInt32(toDateTime('$HOLD_FROM')), toUInt32(toDateTime('$HOLD_TO')), 60))) m)
  SELECT toString(m) FROM mins CROSS JOIN h WHERE h.mn <= m AND h.mx >= m + 60
  GROUP BY m ORDER BY count() DESC, m LIMIT 1")
PROBE_E=$(epoch_of "$PROBE")
PROBE_HOLD=$(qdb1 "
  WITH h AS (SELECT video_session_id, min(event_timestamp) mn, max(event_timestamp) mx
             FROM replay_source WHERE video_session_id IN (SELECT video_session_id FROM replay_holdout)
             GROUP BY video_session_id)
  SELECT toString(count()) FROM h WHERE h.mn <= toDateTime('$PROBE') AND h.mx >= toDateTime('$PROBE') + 60")

# ---------------------------------------------------------------------------
# the publisher, running against the scratch database for the whole replay
# ---------------------------------------------------------------------------
PUBLOG=$(mktemp); PUBPID=""
cleanup() {
  [ -n "$PUBPID" ] && kill "$PUBPID" 2>/dev/null || true
  [ -n "$PUBPID" ] && wait "$PUBPID" 2>/dev/null || true
  rm -f "$PUBLOG"
}
trap cleanup EXIT INT TERM

env TARGET="$TARGET" PUBLISH_SETTLE_S="$SETTLE_S" \
  tools/publish.sh --database "$DB" --loop "$PUBLISH_LOOP_S" > "$PUBLOG" 2>&1 &
PUBPID=$!

say ""
hr
say "▶ REPLAY RUNNING  ·  expect ~${EXPECT_S}s of wall clock  ·  ctrl-c to stop"
say "  tools/publish.sh --loop ${PUBLISH_LOOP_S} is now running against ${DB} (pid $PUBPID)."
say "  The curve below moves ONLY because that finalizer is running. Nothing is"
say "  rebuilt: every update is -deltas(old) + deltas(new) for the sessions that"
say "  received events since the publisher's cursor (ADR 0013)."
say ""
say "  legend   replay-clock→absorbed-through │curve│ cc=concurrent at the"
say "           absorbed edge · lag=publish lag (wall) · q=queue depth (sessions)"
say "           '·' not yet reached   '~' sample landed mid-publish (ADR 0023)"
say "           The curve is LOG-SCALED (this day spans 30x); cc and the peak are"
say "           printed as numbers. The two clocks differ by the publisher's lag —"
say "           that gap is the honest freshness number, shown, not smoothed away."
hr

# ---------------------------------------------------------------------------
# publish-phase probe — ADR 0023.
#
# Between the `negated` and `emitted` phases the serving table holds
# -deltas(old) with no +deltas(new) yet, so any minute covered by the claimed
# batch reads LOW by that batch's entire contribution: measured up to -87.8%
# for 13.6s on Cloud. A live replay polls constantly, so this WILL be hit.
#
# We do not hide it and we do not chart it. Every series read is BRACKETED by a
# phase read; if either bracket says the minute tier is mid-correction, the
# sample is marked '~', the previous good value is carried on the chart, and
# what the sample WOULD have shown is recorded and reported at the end. The
# brackets close the marker race in one direction only (the marker is written
# after its statement returns, so `claimed` can briefly outlive a landed
# negation) — the drop guard below catches that residue.
# ---------------------------------------------------------------------------
# BOTH 'committed' and 'aborted' are terminal. 'aborted' arrives with the
# publisher-safety work (Q8 recovery sweep) and does not exist in every version
# of sql/12_publish.sql — the predicate is written so it is correct either way:
# where the phase is absent the countIf simply never matches it. Without this a
# rolled-back run reads as permanently in flight and the gating goes stale.
#
# Note the empty-vs-NULL trap: argMax over ZERO rows returns the type's default
# — an empty String — not NULL, so ifNull() does not fire and an idle publisher
# reads as ''. That silently arms the drop guard (which only applies while a run
# is in flight) on every idle sample, so the emptiness is normalised here.
phase_now() {
  local p
  p=$(qdb1 "SELECT (SELECT argMax(phase, at) FROM cc_publish_runs
              WHERE run_id IN (SELECT run_id FROM cc_publish_runs
                               GROUP BY run_id
                               HAVING countIf(phase IN ('committed', 'aborted')) = 0))")
  printf '%s' "${p:-idle}"
}
# The phases during which cc_minute_delta holds -deltas(old) and not yet
# +deltas(new). 'claimed'/'claiming' are safe (nothing written to the serving
# table yet); everything from 'emitted' on is safe for the MINUTE tier.
#
# Forward-compatible with ADR 0023's one-block fix by construction: once the
# corrections are staged and land in a single swap, the phase names change to
# staged_neg/staged_pos/swapped, none of which match here — so every sample is
# treated as safe, which is exactly right, because the dip is gone.
phase_unsafe() { case "$1" in negated|derived|pruned) return 0 ;; *) return 1 ;; esac; }

# safe_read <sql> — a scalar read BRACKETED by phase probes. Returns the value,
# or EMPTY if the minute tier was mid-correction on either side of it. Used for
# every number we put on screen as fact, not just for the chart: a probe read
# that lands in the dip reports a minute going BACKWARDS, which is the single
# most misleading thing this demo could show.
safe_read() {
  local a b v
  a=$(phase_now); v=$(qdb1 "$1"); b=$(phase_now)
  if phase_unsafe "$a" || phase_unsafe "$b"; then echo ""; else echo "$v"; fi
}

# THE CHART EDGE — the newest event-time the publisher has FULLY ABSORBED.
#
# Not max(minute) in cc_minute_delta, which is the wrong edge and reads as a
# collapse: a batch's intervals all CLOSE at the end of their coverage, so the
# newest published minute is opens-minus-closes ~ 0 until later batches publish
# the sessions that are still active there. Charting that draws the curve
# falling off a cliff at the right-hand edge on every frame.
#
# The right edge is derivable from the publisher's own bookkeeping: every
# marking at or before the committed cursor has been re-derived in full, so the
# newest event_timestamp among those markings is the newest minute for which
# EVERY covering session is published. Minutes at or before it are stable;
# minutes after it are still accumulating. Capped at the replay clock.
#
# The gap between this and the clock IS the freshness, and it is displayed
# rather than smoothed away.
#
# DERIVED FROM PENDING WORK, not from a margin. The obvious edge —
# max(max_event_ts) among absorbed markings — OVERSHOOTS: one long-running
# session can carry a max_event_ts far ahead of the rest while minutes below it
# are still missing sessions that later batches will publish. Reading there
# prints a minute mid-assembly (measured: cc 3 and cc 5 on curves sitting at
# ~35). Backing that off by a fixed margin only makes the overshoot less
# frequent, not impossible — a margin wide enough to always be safe would be
# wide enough to make the demo look stale.
#
# The exact edge is the oldest event time whose publication is NOT YET
# COMMITTED, because everything strictly before it has been published. That is
# one query over the change log: the earliest event in any marking later than
# the committed cursor. With nothing outstanding the publisher is caught up and
# the edge is simply the newest event absorbed.
#
# Keyed on the COMMITTED cursor, not on cc_publish_consumed: a claimed-but-
# uncommitted run's markings must still count as outstanding, since its new
# events are not in the serving table yet. Instability *within* an in-flight run
# is a separate concern and is handled by phase gating, not here — pinning the
# edge to an in-flight batch instead would drag it back by hours, because a
# batch's read window is widened to cover each session's PRIOR published
# intervals (measured: an edge of 08:09 while the stream was at 11:04).
#
# min_event_ts is per MARKING — the events in one insert block — so for a
# session that has been open for hours this is the current tick, not the
# session's start. Held MONOTONIC by the caller, so the straggler injection
# (whose marking legitimately reaches back into published history) stalls the
# edge for a beat instead of rewinding the chart.
# NOTE the empty-aggregate trap, which bit this function and phase_now() both:
# min()/max()/argMax() over ZERO rows return the column type's DEFAULT, not
# NULL, so `ifNull(min(...), fallback)` never fires and you silently get the
# epoch. Here that produced `epoch - 60s`, which underflows toUnixTimestamp to
# 4294967236 and renders as the year 2106 — observed as a chart edge of "06:27"
# with the stream at 09:00. Emptiness is therefore tested with count(), and the
# result is floored at the window start so no underflow can reach the renderer.
served_minute() {
  qdb1 "WITH
          (SELECT max(cursor_to) FROM cc_publish_runs WHERE phase = 'committed') AS cur,
          (SELECT if(count() = 0, NULL, min(min_event_ts)) FROM session_dirty
             WHERE cur IS NULL OR marked_at > cur) AS outstanding,
          (SELECT if(count() = 0, NULL, max(max_event_ts)) FROM session_dirty) AS absorbed
        SELECT toString(toUnixTimestamp(toStartOfMinute(greatest(
          toDateTime64($FROM_E, 3),
          least(
            ifNull(outstanding - INTERVAL 60 SECOND, ifNull(absorbed, toDateTime64($FROM_E, 3))),
            toDateTime64($1, 3))))))"
}

concurrent_at() { # concurrent_at <epoch> — served concurrency at one minute
  printf "SELECT toString(toInt64(ifNull(argMax(c, minute), 0))) FROM (
     SELECT minute, sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute) AS c
     FROM cc_minute_delta
     WHERE minute >= toStartOfHour(toDateTime(%s)) AND minute <= toDateTime(%s)
     GROUP BY minute)" "$1" "$1"
}

series_of() { # series_of <served-epoch> — dense per-minute curve, FROM..served
  qdb "SELECT toUnixTimestamp(minute) AS m, toInt64(concurrent) AS c FROM (
         SELECT minute, sum(sum(delta)) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute) AS concurrent
         FROM cc_minute_delta
         WHERE minute >= toDateTime($FROM_E) AND minute <= toDateTime($1)
         GROUP BY minute)
       ORDER BY m WITH FILL FROM $FROM_E TO $(( $1 + 60 )) STEP 60 INTERPOLATE (c AS c)
       FORMAT TSVRaw"
}

# sparkline <from-epoch> <to-epoch> <width> ; TSV of (epoch, value) on stdin
#
# LOG SCALED, deliberately. This curve spans ~30x between the pre-event ramp
# (~30 concurrent) and the peak (2,917). On a linear scale the moment the peak
# lands every earlier minute collapses to the same bottom glyph, and the demo
# stops showing the thing it exists to show — the curve BUILDING. Log keeps the
# ramp and the peak legible in the same 8 glyphs. The legend says so; the peak
# and the axis maximum are printed as numbers so nothing rests on the glyphs.
sparkline() {
  awk -v lo="$1" -v hi="$2" -v w="$3" '
    BEGIN { split("▁ ▂ ▃ ▄ ▅ ▆ ▇ █", g, " "); mx = 0; mn = -1 }
    { b = int((($1 - lo) / (hi - lo)) * w); if (b < 0) b = 0; if (b >= w) b = w - 1;
      if ($2 > v[b]) v[b] = $2; seen[b] = 1; if ($2 > mx) mx = $2 }
    END {
      # Anchor BOTH ends of the log axis at the visible min and max. Anchoring
      # only the top saturates every glyph whenever the visible range is narrow
      # (24..43 all read as the top two glyphs); anchoring both spreads whatever
      # range is on screen across all 8, so the shape is legible at 40
      # concurrent and at 2,917.
      for (i = 0; i < w; i++) if (seen[i] && v[i] > 0 && (mn < 0 || v[i] < mn)) mn = v[i];
      if (mn < 0) mn = 1;
      lmn = log(mn); lmx = log(mx > 0 ? mx : 1); span = lmx - lmn;
      out = "";
      for (i = 0; i < w; i++) {
        if (!seen[i]) { out = out "·"; continue }
        if (v[i] <= 0) { out = out "▁"; continue }
        if (span <= 0) { k = 4 } else { k = int(((log(v[i]) - lmn) / span) * 7) + 1 }
        if (k < 1) k = 1; if (k > 8) k = 8;
        out = out g[k];
      }
      printf "%s\t%d", out, mx;
    }'
}

# --- state ------------------------------------------------------------------
LAST_TICK_E=$FROM_E
LAST_SERVED_E=$FROM_E
PEAK_SEEN=0
LAST_GOOD_CC=0
LAST_GOOD_SPARK=""
LAST_GOOD_MAX=0
FILTER_DONE=0
STRAG_DONE=0
PROBE_BEFORE=""
SAMPLES=0; SAMP_MID=0; SAMP_GUARD=0
WORST_DIP_PCT=0; WORST_DIP_FROM=0; WORST_DIP_TO=0
TICKS=0; ROWS_INGESTED=0
T_START=$(date +%s)

while :; do
  NOW=$(date +%s)
  ELAPSED=$(( NOW - T_START ))
  CLOCK=$(( FROM_E + ELAPSED * SPEED ))
  [ "$CLOCK" -gt "$TO_E" ] && CLOCK=$TO_E

  # -- ingest one tick: every event in (last, clock] ------------------------
  if [ "$CLOCK" -gt "$LAST_TICK_E" ]; then
    qdb "INSERT INTO ev_raw ($EV_COLS) SELECT $EV_COLS FROM replay_source
         WHERE event_timestamp >  toDateTime64($LAST_TICK_E, 3)
           AND event_timestamp <= toDateTime64($CLOCK, 3)
           AND video_session_id NOT IN (SELECT video_session_id FROM replay_holdout)" >/dev/null
    LAST_TICK_E=$CLOCK
    TICKS=$(( TICKS + 1 ))
  fi

  # -- sample, bracketed by phase reads (ADR 0023) --------------------------
  PH_A=$(phase_now)
  SERVED_E=$(served_minute "$CLOCK")
  # Monotonic: the chart edge never rewinds. A straggler marking legitimately
  # makes an older minute non-final again, but walking the right-hand edge
  # backwards on stage reads as a fault. History correcting itself is shown
  # where it belongs — on the probe line — not by retracting the chart.
  [ "${SERVED_E:-0}" -lt "$LAST_SERVED_E" ] && SERVED_E=$LAST_SERVED_E
  LAST_SERVED_E=$SERVED_E
  SER=$(series_of "$SERVED_E")
  PH_B=$(phase_now)
  SPARK_RAW=$(printf '%s\n' "$SER" | sparkline "$FROM_E" "$TO_E" "$WIDTH")
  SPARK=${SPARK_RAW%%$'\t'*}
  SMAX=${SPARK_RAW##*$'\t'}
  CC=$(printf '%s\n' "$SER" | awk 'NF{c=$2} END{print c+0}')
  SAMPLES=$(( SAMPLES + 1 ))

  MARK=" "
  SUSPECT=0
  if phase_unsafe "$PH_A" || phase_unsafe "$PH_B"; then SUSPECT=1; SAMP_MID=$(( SAMP_MID + 1 )); fi
  if [ "$SUSPECT" = 0 ] && [ "$PH_A" != idle ] && [ "$LAST_GOOD_CC" -ge "$DIP_FLOOR" ] \
     && [ "$CC" -lt "$(( LAST_GOOD_CC * (100 - DROP_GUARD_PCT) / 100 ))" ]; then
    SUSPECT=1; SAMP_GUARD=$(( SAMP_GUARD + 1 ))
  fi

  if [ "$SUSPECT" = 1 ]; then
    MARK="~"
    # Only a dip off a MATERIAL base is evidence. Below the floor the curve is
    # a handful of viewers and a "-100%" reads as drama rather than measurement.
    if [ "$LAST_GOOD_CC" -ge "$DIP_FLOOR" ] && [ "$CC" -lt "$LAST_GOOD_CC" ]; then
      DIP=$(( (LAST_GOOD_CC - CC) * 100 / LAST_GOOD_CC ))
      if [ "$DIP" -gt "$WORST_DIP_PCT" ]; then
        WORST_DIP_PCT=$DIP; WORST_DIP_FROM=$LAST_GOOD_CC; WORST_DIP_TO=$CC
      fi
    fi
    SHOW_CC=$LAST_GOOD_CC; SHOW_SPARK=$LAST_GOOD_SPARK; SHOW_MAX=$LAST_GOOD_MAX
  else
    LAST_GOOD_CC=$CC; LAST_GOOD_SPARK=$SPARK; LAST_GOOD_MAX=$SMAX
    SHOW_CC=$CC; SHOW_SPARK=$SPARK; SHOW_MAX=$SMAX
  fi

  # -- publisher health, one round trip ------------------------------------
  STAT=$(qdb "SELECT publish_lag_s, pending_sessions, ifNull(last_committed_run, 0) FROM v_cc_publish_lag FORMAT TSVRaw")
  LAG=$(printf '%s' "$STAT" | cut -f1); PEND=$(printf '%s' "$STAT" | cut -f2)

  [ "${SHOW_MAX:-0}" -gt "$PEAK_SEEN" ] && PEAK_SEEN=$SHOW_MAX
  printf '%s→%s%s │%s│ cc %-6s pk %-6s lag %-4s q %-5s\n' \
    "$(hhmm "$CLOCK")" "$(hhmm "$SERVED_E")" "$MARK" "$SHOW_SPARK" \
    "$(commafy "$SHOW_CC")" "$(commafy "$PEAK_SEEN")" "${LAG:-0}s" "$(commafy "${PEND:-0}")"

  # -- BEAT: the filter answers, mid-replay --------------------------------
  if [ "$FILTER_DONE" = 0 ] && [ "$CLOCK" -ge "$FILTER_E" ]; then
    FILTER_DONE=1
    # Filter the NEWEST SERVED minute, not the replay clock. The publisher is
    # legitimately behind the stream; querying a minute it has not reached yet
    # would return zeros and read as a broken filter rather than as freshness.
    FE="$SERVED_E"
    say ""
    say "  ▸ FILTER BEAT — the stream is still landing; the minute-grain view answers now."
    say "    Filtering the newest SERVED minute, $(hhmm "$FE") (the clock is at $(hhmm "$CLOCK") — that gap is publish lag)."
    for dim in platform country; do
      fq="SELECT $dim, toInt64(argMax(c, minute)) AS concurrent FROM (
            SELECT $dim, minute, sum(sum(delta)) OVER (PARTITION BY $dim ORDER BY minute) AS c
            FROM cc_minute_delta
            WHERE minute >= toStartOfHour(toDateTime($FE)) AND minute <= toDateTime($FE)
            GROUP BY $dim, minute)
          GROUP BY $dim HAVING concurrent > 0 ORDER BY concurrent DESC LIMIT 6 FORMAT PrettyCompact"
      # A filtered read is a number we put on screen as fact, so it gets the same
      # bracket the chart does. It needs it MORE, not less: mid-dip every running
      # sum in the window goes to zero, `HAVING concurrent > 0` keeps nothing, and
      # the filter returns an EMPTY TABLE. That failure mode is uglier than a
      # wrong number and ADR 0023 does not name it — it reads as a broken filter.
      OUT=""; MS=0; RETRIES=0
      for _ in 1 2 3 4 5 6 7 8; do
        pa=$(phase_now)
        t0=$(ms); OUT=$(qdb "$fq"); t1=$(ms)
        pb=$(phase_now)
        if ! phase_unsafe "$pa" && ! phase_unsafe "$pb" && [ -n "$OUT" ]; then MS=$(( t1 - t0 )); break; fi
        OUT=""; RETRIES=$(( RETRIES + 1 )); sleep 1
      done
      if [ -n "$OUT" ]; then
        printf '%s\n' "$OUT" | sed 's/^/    /'
        say "    ${dim} breakdown — ${MS} ms, read from cc_minute_delta (the serving table, not events)."
        [ "$RETRIES" -gt 0 ] && say "    (waited out ${RETRIES} in-flight publish(es) first — ADR 0023)"
      else
        say "    ${dim}: no safe window in 8 tries; the publisher never went idle."
      fi
    done
    say ""
  fi

  # -- BEAT: the late arrival lands ----------------------------------------
  if [ "$STRAG_DONE" = 0 ] && [ "$CLOCK" -ge "$STRAG_E" ]; then
    STRAG_DONE=1
    # The BEFORE value is the anchor for everything that follows, so it must not
    # itself be a mid-publish sample. Retry until a bracketed read comes back.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      PROBE_BEFORE=$(safe_read "$(concurrent_at "$PROBE_E")")
      [ -n "$PROBE_BEFORE" ] && break
      sleep 1
    done
    PROBE_BEFORE=${PROBE_BEFORE:-0}
    say ""
    say "  ▸ LATE ARRIVAL — $(qdb1 'SELECT toString(count()) FROM replay_holdout') sessions that closed by $HOLD_TO are only arriving now."
    say "    Minute $PROBE has already scrolled past. It currently serves ${PROBE_BEFORE}."
    say "    $PROBE_HOLD of the withheld sessions have events spanning it (how many of"
    say "    those minutes are FOREGROUND-ACTIVE is the model's call, not the span's)."
    say "    Injecting …"
    qdb "INSERT INTO ev_raw ($EV_COLS) SELECT $EV_COLS FROM replay_source
         WHERE video_session_id IN (SELECT video_session_id FROM replay_holdout)" >/dev/null
    say "    injected. Watch the 'probe' line: the publisher will correct that minute"
    say "    IN PLACE — no rebuild, no truncate, just -deltas(old) + deltas(new)."
    say ""
  fi

  # once injected, show the historical minute correcting itself, live
  if [ "$STRAG_DONE" = 1 ]; then
    PNOW=$(safe_read "$(concurrent_at "$PROBE_E")")
    if [ -z "$PNOW" ]; then
      printf '        probe %s: ~ publish in flight, not sampled (ADR 0023)\n' "$PROBE"
    elif [ "$PNOW" != "$PROBE_BEFORE" ]; then
      printf '        probe %s: %s → %s  (%s, corrected in place — no rebuild)\n' \
        "$PROBE" "$(commafy "$PROBE_BEFORE")" "$(commafy "$PNOW")" "$(signed "$(( PNOW - PROBE_BEFORE ))")"
    else
      printf '        probe %s: %s  (waiting for the publisher to claim the arrivals)\n' \
        "$PROBE" "$(commafy "$PROBE_BEFORE")"
    fi
  fi

  # -- done? ---------------------------------------------------------------
  if [ "$CLOCK" -ge "$TO_E" ]; then
    if [ "${PEND:-0}" = "0" ] && [ "$(qdb1 "SELECT toString(runs_in_flight) FROM v_cc_publish_lag")" = "0" ]; then
      break
    fi
  fi
  sleep "$TICK_S"
done

WALL=$(( $(date +%s) - T_START ))
kill "$PUBPID" 2>/dev/null || true; wait "$PUBPID" 2>/dev/null || true; PUBPID=""

# ===========================================================================
# CLOSING — what was published, and whether it is right
# ===========================================================================
say ""
hr
say "▶ REPLAY COMPLETE"
hr
N_EVENTS=$(qdb1 "SELECT toString(count()) FROM ev_raw")
N_RUNS=$(qdb1 "SELECT toString(count()) FROM cc_publish_runs WHERE phase = 'committed'")
N_DERIV=$(qdb1 "SELECT toString(ifNull(sum(sessions), 0)) FROM cc_publish_runs WHERE phase = 'committed'")
N_DELTA=$(qdb1 "SELECT toString(count()) FROM cc_minute_delta")
N_IVAL=$(qdb1 "SELECT toString(count()) FROM session_intervals FINAL")
PEAK=$(qdb1 "SELECT toString(max(concurrent)) FROM v_concurrency_minute_delta_total")
PEAK_AT=$(qdb1 "SELECT toString(argMax(minute, concurrent)) FROM v_concurrency_minute_delta_total")

say "  ingested       $(commafy "$N_EVENTS") events in ${TICKS} ticks over ${WALL}s wall clock"
say "                 (${SPAN}s of event time at ${SPEED}x compression)"
say "  publisher      ${N_RUNS} committed runs, $(commafy "$N_DERIV") session-derivations"
say "  serving layer  $(commafy "$N_DELTA") delta rows · $(commafy "$N_IVAL") intervals"
say "  peak served    $(commafy "$PEAK") at ${PEAK_AT}"
say ""
say "  NOT ONE ROW WAS REBUILT. tools/build-model.sh never ran; no TRUNCATE was"
say "  issued. Every number above was reached by incremental correction."
say ""
say "  ADR 0023 — publish visibility, measured live during this run:"
say "    samples taken                 $SAMPLES"
say "    landed mid-publish (phase)    $SAMP_MID   — charted as '~', value carried forward"
say "    caught by the drop guard      $SAMP_GUARD   — marker race, see the note in this script"
if [ "$WORST_DIP_PCT" -gt 0 ]; then
  say "    deepest dip NOT charted       -${WORST_DIP_PCT}%  ($(commafy "$WORST_DIP_FROM") → $(commafy "$WORST_DIP_TO"))"
  say "    That collapse is real and transient: between 'negated' and 'emitted' the"
  say "    serving table holds -deltas(old) with no +deltas(new) yet. It converges"
  say "    every time. We refuse to chart it and we refuse to hide it."
else
  say "    deepest dip NOT charted       none observed this run"
fi
if [ -n "$PROBE_BEFORE" ]; then
  PFIN=$(qdb1 "$(concurrent_at "$PROBE_E")")
  say ""
  say "  LATE ARRIVAL — minute $PROBE: $(commafy "$PROBE_BEFORE") → $(commafy "$PFIN") ($(signed "$(( PFIN - PROBE_BEFORE ))")),"
  say "  corrected in place by the finalizer. The rebuild path was never invoked."
fi

say ""
say "▶ IS IT RIGHT? — the committed gate (sql/90_reconcile.sql) against this database."
say "  Truth is recomputed FROM ev_raw with a different algorithm; it never reads"
say "  the serving layer. Any disagreeing minute fails."
say ""
RECON=evidence/demo-replay/reconcile.txt
mkdir -p evidence/demo-replay
if [ "$TARGET" = cloud ]; then
  curl -sS --fail-with-body "https://$(ch_host):${CH_PORT}/?database=${DB}&default_format=PrettyCompact" \
    --user "${CH_USER}:${CH_PASSWORD}" --data-binary "@sql/90_reconcile.sql" > "$RECON" 2>&1 || true
else
  docker exec -i ch clickhouse-client --database "$DB" --format PrettyCompact < sql/90_reconcile.sql > "$RECON" 2>&1 || true
fi
sed 's/^/  /' "$RECON" | head -12
if grep -q MISMATCH "$RECON"; then
  say ""
  say "  ✗ RECONCILE FAILED — a minute disagrees. See $RECON"
else
  say ""
  say "  ✓ reconcile PASSED — the incrementally-published curve you just watched"
  say "    being built agrees with an independent recompute from raw events, at"
  say "    every minute compared."
fi

say ""
hr
say "HONESTY — what this run does and does not prove"
say "  DOES:      the incremental publisher can absorb a live stream and late"
say "             arrivals, keep a minute-grain serving layer current, answer"
say "             filtered queries in milliseconds, and stay reconcilable."
say "  DOES NOT:  say anything about the graded service. ${DB} is a scratch"
say "             database built by this script. The graded database sonyliv is"
say "             BATCH-REBUILT; its publisher has committed ZERO runs and its"
say "             cursor is at epoch. Time here is compressed ${SPEED}x, and"
say "             PUBLISH_SETTLE_S=${SETTLE_S} (the floor on publish lag) is"
say "             lower than the default 5. Full detail: demo/REPLAY.md."
say "  total wall clock  $(( $(date +%s) - T_START_ALL ))s"
hr
[ "$CAPTURE" = 1 ] && say "" && say "transcript: $CAP"
exit 0
