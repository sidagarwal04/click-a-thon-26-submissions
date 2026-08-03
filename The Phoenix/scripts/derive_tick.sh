#!/usr/bin/env bash
# One incremental-derive tick, for a scheduler to call every few minutes.
#
#   ./scripts/derive_tick.sh                # tick phoenix
#   ./scripts/derive_tick.sh phoenix_next   # tick a named database
#
# Window logic: [watermark - overlap, max(event_timestamp)]. The watermark is the upper
# bound of the last successful tick, kept in .derive_watermark.<db> (gitignored, local
# state). The overlap re-derives sessions near the boundary; that is SAFE by construction,
# not by luck: 03_derive_incremental retracts everything a touched session currently
# asserts before re-asserting it from its full history, so re-touching a session is
# idempotent. The only cost of overlap is work, never correctness.
#
# ponytail: single flock per db so overlapping scheduler firings queue rather than race.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${1:-${CH_DATABASE:-phoenix}}"
export CH_DATABASE="$DB"
OVERLAP_S="${OVERLAP_S:-120}"
# DERIVE_STATE_DIR points at a mounted volume in the deployed stack, so the watermark survives a
# container restart. Without it the file lived in the container's ephemeral /app and every tick
# took the first-tick branch, replaying a 3600s window every 60 seconds. Defaults to the repo root
# so a host-side run behaves exactly as before.
WM_DIR="${DERIVE_STATE_DIR:-.}"
mkdir -p "$WM_DIR"
WM_FILE="$WM_DIR/.derive_watermark.$DB"
LOG="derive_tick.$DB.log"

exec 9>"$WM_FILE.lock"
flock 9

# select_sequential_consistency=1 everywhere in this script: on Cloud SharedMergeTree a
# SELECT can land on a replica that has not yet seen the last insert, so a retract that
# reads stale state MISSES freshly asserted runs and the next assert duplicates them.
# Measured live 2026-08-01 18:51: two byte-identical +1 rows from consecutive passes.
CHT() { ./scripts/ch.sh --select_sequential_consistency=1 "$@"; }
val() { CHT --format TSVRaw --query "$1" 2>/dev/null | head -1; }

# CLAMPED TO now(). A watermark driven by max(event_timestamp) trusts the data to be honest about
# time, and one future-dated row poisons it permanently: the watermark jumps ahead, every
# subsequent tick computes from_ts >= max_ts, logs "nothing new", and the served curve freezes
# while ingest looks perfectly healthy.
#
# Not hypothetical. phoenix_next holds the spike-sustainability fixtures, which the spec pins at
# 2026-08-02 06:00 and 07:00 UTC -- roughly eight hours ahead of wall clock when they were loaded.
# Measured immediately after: the console reported LAG_S = -31195 (negative lag: the newest event
# is in the future) and CONCURRENT = 0 while the producer was inserting ~54,000 rows per cycle.
# Live traffic was landing and nothing was deriving it.
#
# Clock skew on a real client does exactly the same thing, so this is a production guard and not a
# workaround for a fixture. Future-dated rows are not lost: they are derived by an EXPLICIT window
# (scripts/spike_scenarios.sh passes its own from_ts/to_ts) or by the tick that runs once wall
# clock catches up.
max_ts="$(val "SELECT toString(least(max(event_timestamp), now64(3))) FROM raw_events")"
[ -n "$max_ts" ] || { echo "$(date -u +%FT%TZ) $DB no data reachable, skipping" >>"$LOG"; exit 0; }

# A watermark already past the clamp means a previous tick recorded a future instant. Roll it back
# rather than idling forever waiting for wall clock to catch up.
if [ -s "$WM_FILE" ] && [ "$(val "SELECT parseDateTime64BestEffort('$(cat "$WM_FILE")', 3) > now64(3)")" = "1" ]; then
  echo "$(date -u +%FT%TZ) $DB watermark $(cat "$WM_FILE") is in the FUTURE, resetting to $max_ts" >>"$LOG"
  echo "$max_ts" > "$WM_FILE"
fi

if [ -s "$WM_FILE" ]; then
  from_ts="$(val "SELECT toString(parseDateTimeBestEffort('$(cat "$WM_FILE")') - INTERVAL $OVERLAP_S SECOND)")"
else
  # First tick: cover the last hour rather than all history; a fuller catch-up is a
  # deliberate REBUILD or a wider FIRST_WINDOW_S, not an accident.
  from_ts="$(val "SELECT toString(parseDateTimeBestEffort('$max_ts') - INTERVAL ${FIRST_WINDOW_S:-3600} SECOND)")"
fi

if [ "$(val "SELECT parseDateTimeBestEffort('$from_ts') >= parseDateTimeBestEffort('$max_ts')")" = "1" ]; then
  echo "$(date -u +%FT%TZ) $DB nothing new (watermark $from_ts, max $max_ts)" >>"$LOG"
  exit 0
fi

# THE FOURTH INVARIANT: do the stored deltas actually equal what the runs imply?
#
# The three checks above are all grouped by the SORT KEY, which for session_minute_runs is
# (video_session_id, run_start, run_end) and EXCLUDES every dimension column. That blind spot is
# not hypothetical: on 2026-08-02 a positional INSERT shifted video_resolution to hold
# player_version values, and closure, dupes and negatives all passed on the misaligned data,
# because none of them looks at which column a value landed in.
#
# Worse, a `+1 @ dimsA` / `-1 @ dimsB` pair sums to zero globally AND nets zero per sort key, so
# it passes all three, and then CollapsingMergeTree physically cancels the pair on merge --
# destroying the very evidence 03b's retract branch needs to heal it. After that the stranded
# delta pair in concurrency_deltas is unreachable forever.
#
# This check recomputes the expected deltas from the runs table grouped by ALL NINE DIMENSIONS
# plus the boundary minute, and full-outer-joins them against what is stored. Any disagreement is
# a real divergence between the runs and the curve served from them.
# Measured cost against the live corpus: 106-111 ms. Cheap enough to run every tick.
_recon_sql() {  # $1 = runs table, $2 = deltas table, $3 = the runs table's identity column
  cat <<RECON
SELECT ifNull(sum(abs(ifNull(a.d, 0) - ifNull(b.d, 0))), 0)
FROM (
    SELECT platform, country, video_type, content_id, app_version,
           audio_language, subtitle_language, player_version, video_resolution,
           bound.1 AS minute, sum(bound.2 * s) AS d
    FROM (
        SELECT platform, country, video_type, content_id, app_version,
               audio_language, subtitle_language, player_version, video_resolution,
               run_start, run_end, sum(sign) AS s
        FROM $1
        GROUP BY platform, country, video_type, content_id, app_version,
                 audio_language, subtitle_language, player_version, video_resolution,
                 run_start, run_end
        HAVING s != 0
    )
    ARRAY JOIN [(run_start, 1), (run_end + INTERVAL 1 MINUTE, -1)] AS bound
    GROUP BY platform, country, video_type, content_id, app_version,
             audio_language, subtitle_language, player_version, video_resolution, minute
) AS a
FULL OUTER JOIN (
    SELECT platform, country, video_type, content_id, app_version,
           audio_language, subtitle_language, player_version, video_resolution,
           minute, sum(delta) AS d
    FROM $2
    GROUP BY platform, country, video_type, content_id, app_version,
             audio_language, subtitle_language, player_version, video_resolution, minute
    HAVING d != 0
) AS b
USING (platform, country, video_type, content_id, app_version,
       audio_language, subtitle_language, player_version, video_resolution, minute)
RECON
}

t0=$(date +%s)
# Up to two passes. A session whose first in-window event arrives BETWEEN the retract and
# the assert gets asserted without being retracted; if a late content row also flipped its
# dims, two variants of the same run are briefly live and the dupes invariant trips.
# Measured live 2026-08-01 18:45: exactly this signature, healed by one retry, because the
# retract emits sum(sign) retractions per group and zeroes any accumulated state. So one
# in-tick retry absorbs the known-transient race; a failure that survives it is real.
for attempt in 1 2; do
  CHT --param_tolerance_s="${TOLERANCE_S:-90}" --param_pause_inactive="${PAUSE_INACTIVE:-1}" \
    --param_from_ts="$from_ts" --param_to_ts="$max_ts" \
    --queries-file sql/pipeline/03b_derive_incremental_atomic.sql
  closure="$(val "SELECT sum(delta) FROM concurrency_deltas")"
  dupes="$(val "SELECT ifNull(max(s), 1) FROM (SELECT sum(sign) AS s FROM session_minute_runs GROUP BY video_session_id, run_start, run_end HAVING s > 0)")"
  negs="$(val "SELECT countIf(s < 0) FROM (SELECT sum(sign) AS s FROM session_minute_runs GROUP BY video_session_id, run_start, run_end)")"
  recon="$(val "$(_recon_sql session_minute_runs concurrency_deltas)")"
  [ "$closure" = "0" ] && [ "$dupes" = "1" ] && [ "$negs" = "0" ] && [ "$recon" = "0" ] && break
  echo "$(date -u +%FT%TZ) $DB attempt $attempt tripped invariants: closure=$closure dupes=$dupes recon=$recon, retrying same window" >>"$LOG"
done
# Healing pass. The dupes check is GLOBAL but the retract only reaches sessions with
# events in the current window, so a double whose session has gone quiet is out of every
# future window and would fail every tick forever. When dupes persist, derive the
# offending sessions' own event range: that puts them in the touched-set, the exact
# retract zeroes them, and the assert writes the one correct variant.
if [ "$dupes" != "1" ] || [ "$negs" != "0" ]; then
  heal_range="$(val "SELECT concat(toString(min(event_timestamp)), '|', toString(max(event_timestamp) + INTERVAL 1 SECOND))
    FROM raw_events WHERE video_session_id IN (
      SELECT video_session_id FROM session_minute_runs
      GROUP BY video_session_id, run_start, run_end HAVING sum(sign) > 1 OR sum(sign) < 0)")"
  heal_from="${heal_range%%|*}"; heal_to="${heal_range##*|}"
  echo "$(date -u +%FT%TZ) $DB healing pass over offender range $heal_from -> $heal_to" >>"$LOG"
  CHT --param_tolerance_s="${TOLERANCE_S:-90}" --param_pause_inactive="${PAUSE_INACTIVE:-1}" \
    --param_from_ts="$heal_from" --param_to_ts="$heal_to" \
    --queries-file sql/pipeline/03b_derive_incremental_atomic.sql
  closure="$(val "SELECT sum(delta) FROM concurrency_deltas")"
  dupes="$(val "SELECT ifNull(max(s), 1) FROM (SELECT sum(sign) AS s FROM session_minute_runs GROUP BY video_session_id, run_start, run_end HAVING s > 0)")"
  negs="$(val "SELECT countIf(s < 0) FROM (SELECT sum(sign) AS s FROM session_minute_runs GROUP BY video_session_id, run_start, run_end)")"
  recon="$(val "$(_recon_sql session_minute_runs concurrency_deltas)")"
fi

# USER STAGE. The session stage above only writes session_minute_runs; user_minute_runs is a
# separate rebuild (04) that this tick never ran, so the Users side of the console stayed at
# whatever the last batch derive left and read zero for every live minute. 04c is the windowed,
# self-healing twin of 04, scoped to users touched in this window: see that file for why the
# scope is required and not just an optimisation. Runs only after the session invariants hold,
# since it reads asserted session runs.
if [ "$closure" = "0" ] && [ "$dupes" = "1" ] && [ "$negs" = "0" ]; then
  # foreground_intervals, append-only for SETTLED sessions. Until this line existed the table had
  # no writer in the tick at all -- its only producer, 01_derive_intervals.sql, is whole-corpus
  # with no window and runs solely in scripts/derive.sh's batch path. Under continuous ingest it
  # simply stopped: measured on phoenix_next, runs were current at 2026-08-02 07:02 while
  # intervals sat at 2026-08-01 17:07, and of 120,336 recently active sessions ZERO had an
  # interval row.
  #
  # That did not read as an empty table downstream. 01_refresh_session_facts.sql LEFT JOINs this
  # table, so it read as PLAUSIBLE ZEROS in tables the console marks fresh: 4,003 sessions with
  # active_seconds and every active_after_* at zero, 0 heartbeat timeouts across 52,859 active
  # sessions, and content_entry_cohorts frozen 396 minutes back. Silent zeros, not gaps.
  #
  # 01b is append-only and needs no sign column because it only touches sessions that have gone
  # quiet for longer than tolerance_s AND have no interval rows yet. A settled session's
  # intervals can never change, so nothing is ever rewritten and nothing can be duplicated.
  CHT --param_tolerance_s="${TOLERANCE_S:-90}" --param_pause_inactive="${PAUSE_INACTIVE:-1}" \
    --param_from_ts="$from_ts" --param_to_ts="$max_ts" \
    --queries-file sql/pipeline/01b_derive_intervals_incremental.sql

  CHT --param_from_ts="$from_ts" --param_to_ts="$max_ts" \
    --queries-file sql/pipeline/04c_merge_user_runs_atomic.sql
  uclosure="$(val "SELECT sum(delta) FROM user_concurrency_deltas")"
  # HAVING s != 0, not s > 0. The old form filtered negatives out BEFORE max(), so a stranded
  # negative on the user side could never register no matter how bad it got.
  udupes="$(val "SELECT ifNull(max(s), 1) FROM (SELECT sum(sign) AS s FROM user_minute_runs GROUP BY user_id, run_start, run_end HAVING s != 0)")"
  # The user side had no negatives check at all; the session side has had one since the retract
  # was made self-healing. Same failure, same detection.
  unegs="$(val "SELECT countIf(s < 0) FROM (SELECT sum(sign) AS s FROM user_minute_runs GROUP BY user_id, run_start, run_end)")"
  urecon="$(val "$(_recon_sql user_minute_runs user_concurrency_deltas)")"
  if [ "$uclosure" != "0" ] || [ "$udupes" != "1" ] || [ "$unegs" != "0" ] || [ "$urecon" != "0" ]; then
    echo "$(date -u +%FT%TZ) $DB USER STAGE FAILED: closure=$uclosure dupes=$udupes negatives=$unegs recon=$urecon" >>"$LOG"
    exit 1
  fi
fi
t1=$(date +%s)

if [ "$closure" != "0" ] || [ "$dupes" != "1" ] || [ "$negs" != "0" ] || [ "$recon" != "0" ]; then
  echo "$(date -u +%FT%TZ) $DB TICK FAILED invariants after retry and healing pass: closure=$closure dupes=$dupes negatives=$negs recon=$recon (window $from_ts -> $max_ts)" >>"$LOG"
  exit 1
fi

echo "$max_ts" >"$WM_FILE"
echo "$(date -u +%FT%TZ) $DB ok: window $from_ts -> $max_ts in $((t1 - t0))s, closure 0, dupes 1, negatives 0" >>"$LOG"
