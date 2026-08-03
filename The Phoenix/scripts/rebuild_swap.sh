#!/usr/bin/env bash
# Full rebuild into a shadow database, verified, then swapped in atomically.
#
#   ./scripts/rebuild_swap.sh              # rebuild and swap
#   VERIFY_ONLY=1 ./scripts/rebuild_swap.sh   # build and verify, do NOT swap
#
# WHY THIS EXISTS. derive.sh refuses to derive into a non-empty database, which makes the
# doubling bug UNREACHABLE but leaves recovery manual: truncate, then re-derive, under time
# pressure, which is exactly the condition that reintroduces the doubling by hand. TASK.md 3.2
# asks for derive-to-shadow-and-swap so that recovery is a single command with a verified
# result. derive.sh keeps its refusal on the live path as the second layer.
#
# THE MATERIALIZED VIEW TRAP, and why this uses a shadow DATABASE and not shadow TABLES.
# concurrency_deltas_mv is attached FROM session_minute_runs. Building into
# session_minute_runs_next in the same database fires NOTHING, so concurrency_deltas_next comes
# out EMPTY and a row-count check on the runs table alone passes on garbage. A shadow database
# gets its own copy of the whole schema, MVs included, so the delta tables populate exactly as
# they do in production. Verified this session before relying on it: EXCHANGE TABLES works
# across databases on this Cloud service (a=2/b=1 on a throwaway pair), and closure is asserted
# on the shadow DELTAS, not just the shadow runs.
#
# The shadow reads phoenix.raw_events through a VIEW rather than copying 1M rows. Cheaper, and
# it removes a whole failure mode: a copy is a second snapshot that can silently differ.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

LIVE="${LIVE_DB:-phoenix}"
# The shadow is DROPped at the start and again at the end of every run, so its name must not
# collide with anything durable. It used to default to phoenix_next, which is now the
# next-generation database holding the insight layer: one rebuild would have wiped it.
SHADOW="${SHADOW_DB:-phoenix_rebuild}"
DERIVED=(foreground_intervals session_minute_runs concurrency_deltas user_minute_runs user_concurrency_deltas)

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

echo "== 1. shadow database $SHADOW" >&2
ch --query "DROP DATABASE IF EXISTS $SHADOW"
ch --query "CREATE DATABASE $SHADOW"

# Source tables as views onto the live database. event_state is itself a view over raw_events,
# so it resolves to these without knowing they are not tables.
ch --query "CREATE VIEW $SHADOW.raw_events AS SELECT * FROM $LIVE.raw_events"
ch --query "CREATE VIEW $SHADOW.content    AS SELECT * FROM $LIVE.content"
for f in sql/schema/03_event_state.sql sql/schema/04_concurrency.sql sql/schema/05_user_concurrency.sql; do
  CH_DATABASE="$SHADOW" ch --queries-file "$f"
done

echo "== 2. derive into $SHADOW (derive.sh, unmodified, including its own post-conditions)" >&2
CH_DATABASE="$SHADOW" ./scripts/derive.sh "$SHADOW" >&2

echo "== 3. verify the shadow before it is allowed anywhere near $LIVE" >&2
s_runs="$(CH_DATABASE=$SHADOW val "SELECT sum(sign) FROM session_minute_runs")"
s_urun="$(CH_DATABASE=$SHADOW val "SELECT sum(sign) FROM user_minute_runs")"
s_clos="$(CH_DATABASE=$SHADOW val "SELECT sum(delta) FROM concurrency_deltas")"
s_uclo="$(CH_DATABASE=$SHADOW val "SELECT sum(delta) FROM user_concurrency_deltas")"
s_delt="$(CH_DATABASE=$SHADOW val "SELECT count() FROM concurrency_deltas")"
s_peak="$(CH_DATABASE=$SHADOW val "SELECT max(c) FROM (SELECT sum(delta) OVER (ORDER BY minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c FROM (SELECT minute, sum(delta) AS delta FROM concurrency_deltas WHERE minute < {frozen_before:String} GROUP BY minute))")"
l_peak="$(CH_DATABASE=$LIVE   val "SELECT max(c) FROM (SELECT sum(delta) OVER (ORDER BY minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c FROM (SELECT minute, sum(delta) AS delta FROM concurrency_deltas WHERE minute < {frozen_before:String} GROUP BY minute))")"
# Overshoot is the thing this rebuild is for: it must be ZERO afterwards.
s_over="$(CH_DATABASE=$SHADOW val "
  WITH ends AS (SELECT video_session_id AS sid, toDateTime(max(event_timestamp)) AS le
                FROM raw_events WHERE event_type = 'VideoSessionEnd' GROUP BY video_session_id)
  SELECT count() FROM foreground_intervals AS i INNER JOIN ends AS e ON i.video_session_id = e.sid
  WHERE i.interval_end > e.le")"

verdict=PASS
[ "$s_clos" = "0" ]        || verdict=FAIL
[ "$s_uclo" = "0" ]        || verdict=FAIL
[ "$s_over" = "0" ]        || verdict=FAIL
[ "${s_runs:-0}" -gt 0 ]   || verdict=FAIL
[ "${s_delt:-0}" -gt 0 ]   || verdict=FAIL

{
  printf 'metric\tvalue\n'
  printf 'live_db\t%s\n'                     "$LIVE"
  printf 'shadow_db\t%s\n'                   "$SHADOW"
  printf 'shadow.asserted_session_runs\t%s\n' "$s_runs"
  printf 'shadow.asserted_user_runs\t%s\n'    "$s_urun"
  printf 'shadow.delta_rows\t%s\n'            "$s_delt"
  printf 'shadow.invariant.closure_session\t%s\t(required 0)\n' "$s_clos"
  printf 'shadow.invariant.closure_user\t%s\t(required 0)\n'    "$s_uclo"
  printf 'shadow.intervals_past_last_session_end\t%s\t(required 0, the defect this rebuild fixes)\n' "$s_over"
  printf 'live.peak_frozen_slice\t%s\n'   "$l_peak"
  printf 'shadow.peak_frozen_slice\t%s\n' "$s_peak"
  printf 'verdict\t%s\n' "$verdict"
} | evidence "rebuild_swap_${SHADOW}" "full rebuild into a shadow database with the end-bound rule, verified on the shadow deltas before any swap" | xargs cat

[ "$verdict" = PASS ] || { echo "SHADOW VERIFY FAILED, nothing swapped" >&2; exit 1; }

if [ "${VERIFY_ONLY:-0}" = "1" ]; then
  echo "== VERIFY_ONLY=1: shadow built and verified, $LIVE untouched. Shadow left at $SHADOW." >&2
  exit 0
fi

echo "== 4. EXCHANGE the derived tables into $LIVE" >&2
# One statement per table. ClickHouse has no multi-table atomic exchange, so the window between
# the five is real; it is milliseconds and every table is individually consistent, which is a
# strictly better position than TRUNCATE-then-reinsert where the window is the whole derive.
for t in "${DERIVED[@]}"; do
  ch --query "EXCHANGE TABLES $LIVE.$t AND $SHADOW.$t"
  echo "   exchanged $t" >&2
done

echo "== 5. confirm $LIVE now carries the rebuild" >&2
l_over="$(CH_DATABASE=$LIVE val "
  WITH ends AS (SELECT video_session_id AS sid, toDateTime(max(event_timestamp)) AS le
                FROM raw_events WHERE event_type = 'VideoSessionEnd' GROUP BY video_session_id)
  SELECT count() FROM foreground_intervals AS i INNER JOIN ends AS e ON i.video_session_id = e.sid
  WHERE i.interval_end > e.le")"
l_clos="$(CH_DATABASE=$LIVE val "SELECT sum(delta) FROM concurrency_deltas")"
echo "   $LIVE intervals past last session end: $l_over (required 0)" >&2
echo "   $LIVE closure: $l_clos (required 0)" >&2
[ "$l_over" = "0" ] && [ "$l_clos" = "0" ] || { echo "POST-SWAP CHECK FAILED" >&2; exit 1; }

# After the EXCHANGE, $SHADOW holds the OLD tables. That makes it the rollback: re-running the
# same five EXCHANGE statements puts them back. Keep it when the rebuild changes semantics rather
# than merely refreshing data, which is precisely when you want the previous state reachable.
if [ "${KEEP_SHADOW:-0}" = "1" ]; then
  echo "== 6. KEEP_SHADOW=1: $SHADOW retained, holding the PREVIOUS tables." >&2
  echo "   rollback: for t in ${DERIVED[*]}; do ./scripts/ch.sh --query \"EXCHANGE TABLES $LIVE.\$t AND $SHADOW.\$t\"; done" >&2
else
  echo "== 6. drop $SHADOW (now holding the OLD tables)" >&2
  ch --query "DROP DATABASE $SHADOW"
fi
echo "REBUILD AND SWAP COMPLETE" >&2
