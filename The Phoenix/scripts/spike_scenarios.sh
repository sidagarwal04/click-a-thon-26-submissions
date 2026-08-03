#!/usr/bin/env bash
# Generate, load, classify and validate the two spike-sustainability scenarios.
#
#   ./scripts/spike_scenarios.sh                       # phoenix_next, 20,000 sessions each
#   SESSIONS=2000 ./scripts/spike_scenarios.sh          # rehearsal
#   ./scripts/spike_scenarios.sh --cleanup              # remove every synthetic row, then stop
#
# Runs against phoenix_next, never phoenix. phoenix_next is the insight database the frontend
# reads; phoenix stays the graded concurrency database and is not touched here.
#
# THE SYNTHETIC ROWS ARE VISIBLE TO THE FRONTEND, and that is a deliberate, reversible choice
# rather than an oversight. content_id 990001 carries the title 'Synthetic Spike Sustainability
# Test' and dimension values that exist nowhere in the corpus (app_version 'spike-test-1.0.0',
# player_version 'synthetic-player-1'), so a dashboard can exclude it with one predicate and a
# human reading a filter list can tell instantly what it is. `--cleanup` removes it entirely.
# The alternative -- a separate database -- was tried and abandoned: it doubled the schema surface
# and meant the spike demo could not be shown next to the live insights it is meant to explain.
#
# IDEMPOTENT BY CLEANUP, NOT BY LUCK. raw_events is a plain MergeTree and will not deduplicate a
# second load, so re-running without cleaning first would double every count and the retention
# ratios would still look plausible. So the load always cleans first.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${DB:-phoenix_next}"
export CH_DATABASE="$DB"
export EVIDENCE_STAMP_DB="$DB"
SESSIONS="${SESSIONS:-20000}"
SEED="${SEED:-20260802}"
CONTENT_ID=990001
OUT="${OUT:-data/generated}"
H_START="${H_START:-2026-08-02T06:00:00Z}"
W_START="${W_START:-2026-08-02T07:00:00Z}"

[ "$DB" = phoenix ] && { echo "REFUSING: this writes synthetic vocabulary; not into phoenix." >&2; exit 1; }

# Errors are NOT swallowed. A `2>/dev/null` here hid three separate failures during development
# (a wrong column name, a nested aggregate, a masked insert), each of which surfaced only as a
# bare exit code with no message.
# select_sequential_consistency=1 on every read. On Cloud SharedMergeTree a SELECT can land on
# a replica that has not yet seen the last insert. Measured here: the validation query
# reported only the healthy scenario's session count and omitted the weak one entirely,
# moments after loading 31,130 weak rows that were demonstrably present. An evidence artifact
# that silently drops a whole scenario is worse than one that fails loudly.
ch()  { ./scripts/ch.sh --select_sequential_consistency=1 "$@"; }
val() { ch --format TSVRaw --query "$1" 2>/dev/null | head -1; }

# DROP PARTITION, NOT DELETE, AND THIS COST A DEBUGGING ROUND TO LEARN.
#
# The first version ran `DELETE FROM raw_events WHERE content_id = 990001` before each load. On
# ClickHouse Cloud that is a lightweight delete: a mutation setting _row_exists = 0. The second
# run then loaded 77,391 rows, the INSERT reported written_rows = 77,391, raw_events_mv finished
# with no exception -- and `SELECT count() WHERE content_id = 990001` returned 0. The rows were
# physically in partition 20260802 (108,521 of them, in system.parts) and every one was masked.
# The delete predicate had been applied to rows that did not exist when it was issued.
#
# Silent, and it survives every check that counts rows through a SELECT. So: drop the whole
# partition. The scenarios live entirely on 2026-08-02, raw_events is
# PARTITION BY toYYYYMMDD(event_timestamp), and a partition drop is metadata only -- instant, no
# mutation, and nothing left behind to mask a later insert. This is what
# insert-mutation-avoid-delete means in practice.
#
# NOTHING ELSE NEEDS CLEANING, which is the other half of the fix. The insight tables are
# ReplacingMergeTree keyed on the session or the minute, so a re-run SUPERSEDES rather than
# accumulates (refresh_insights.sh asserts exactly that). session_minute_runs is Collapsing and
# the incremental derive retracts a session's existing runs before re-asserting them, so it is
# idempotent by construction. Deleting from them was never necessary and was how the trap got in.
#
# AND IT REFUSES TO DROP A PARTITION THAT HOLDS ANYONE ELSE'S ROWS. The scenarios are pinned to
# 2026-08-02, so they share partition 20260802 with any live ingest that happens to run on that
# UTC day -- and live ingest into phoenix_next is exactly what the team runs. Dropping the
# partition blind would delete a colleague's stream to make room for a test fixture. So each
# candidate partition is checked first: if it contains any row that is not content_id 990001, the
# script stops and says so rather than guessing which data mattered.
cleanup() {
  for p in $(ch --format TSVRaw --query "
      SELECT DISTINCT partition FROM system.parts
      WHERE database = currentDatabase() AND table = 'raw_events' AND active
        AND partition >= '20260802'"); do
    foreign="$(val "SELECT count() FROM raw_events
                    WHERE toYYYYMMDD(event_timestamp) = toUInt32('$p') AND content_id != $CONTENT_ID")"
    if [ "${foreign:-0}" != "0" ]; then
      echo "REFUSING: partition $p in $DB holds $foreign rows that are not content_id $CONTENT_ID." >&2
      echo "  That is somebody else's data sharing the scenario day. Move the scenario with" >&2
      echo "  H_START/W_START, or clear those rows deliberately, but this script will not." >&2
      exit 1
    fi
    echo "== dropping partition $p from $DB.raw_events (scenario rows only)" >&2
    ./scripts/ch.sh --alter_sync=2 --query "ALTER TABLE raw_events DROP PARTITION '$p'"
  done
}

[ "${1:-}" = "--cleanup" ] && { cleanup; echo "cleaned" >&2; exit 0; }

# ---------------------------------------------------------------------------------------------
echo "== 1. schema" >&2
./scripts/ch.sh --queries-file sql/insights/schema/10_concurrency_spike_events.sql >/dev/null

echo "== 2. synthetic content row" >&2
# `< /dev/null` IS LOAD-BEARING. clickhouse-client keeps reading stdin after an INSERT ... VALUES
# passed via --query, so that more rows can be appended. Run interactively that stdin is already
# at EOF and nothing happens; run detached, with stdin held open by the parent, and the client
# blocks forever. Measured: this exact statement sat for 12 minutes with no query registered
# server-side, which reads as a hung pipeline rather than a hung client.
ch --query "INSERT INTO content (content_id, title, video_type, category) VALUES
            ($CONTENT_ID, 'Synthetic Spike Sustainability Test', 'live', 'test')" < /dev/null

echo "== 3. generate (seed $SEED, $SESSIONS sessions per scenario)" >&2
python3 scripts/generate_spike_scenarios.py --scenario both --sessions "$SESSIONS" \
  --seed "$SEED" --healthy-start "$H_START" --weak-start "$W_START" --output-dir "$OUT" >&2

echo "== 4. clean, then load" >&2
cleanup
# insert_deduplicate=0, AND THIS IS THE SUBTLEST BUG IN THIS SCRIPT.
#
# Replicated tables deduplicate inserted blocks by content hash over a rolling window
# (replicated_deduplication_window, ~100 blocks). The generator is deterministic BY DESIGN -- the
# spec demands a fixed seed so a correctness gate can compare runs -- so re-running produces a
# byte-identical CSV, which produces a byte-identical block, which ClickHouse silently discards
# as a duplicate. The INSERT succeeds, reports its rows, and nothing lands.
#
# Measured: after several runs, phoenix_insights held the weak scenario's 2,000 sessions and none
# of the healthy scenario's, because the healthy block was still inside the dedup window and the
# weak one had aged out. Worse, the classifier still returned healthy_sustained -- from insight
# rows left by an EARLIER run, since those tables are ReplacingMergeTree and nobody had deleted
# them. A green verdict computed from data that was no longer in raw_events.
#
# Deduplication is the wrong protection here: this script drops the partition immediately before
# loading, so a repeat load is intended, not accidental. load.sh is left alone -- its dedup is
# correct for the real corpus, where a re-run IS an accident.
# NATIVE, NOT CSVWithNames, over the wire. The CSV stays as the deliverable artifact the spec
# asks for -- it is the reproducible, diffable input -- but CSV is the slowest thing to hand to
# the server (rule insert-format-native ranks Native > RowBinary > row text formats, purely on
# parsing cost). `clickhouse local` reads the CSV once locally and re-emits it as Native, so the
# cloud service is handed a column-oriented block it barely has to parse.
#
# Measured at rehearsal scale this is worth little (3.88 MiB, 434 ms). It is worth real time at
# the spec's actual scale: 20,000 sessions per scenario is ~774,000 rows and ~120 MB of CSV, and
# parse cost there is a straight line in the load time.
#
# schema_inference_make_columns_nullable=0 is mandatory on the local read: without it every
# inferred column comes back Nullable and the INSERT then fails against non-Nullable targets.
for s in healthy weak; do
  f="$OUT/spike_${s}_events.csv"
  echo "loading $f -> $DB.raw_events_landing (CSV -> Native)" >&2
  clickhouse local --session_timezone UTC --schema_inference_make_columns_nullable=0 \
    --query "SELECT * FROM file('$f', CSVWithNames) FORMAT Native" \
  | ./scripts/ch.sh --insert_deduplicate=0 --query "INSERT INTO raw_events_landing FORMAT Native"
done

echo "== 5. derive concurrency over the scenario range" >&2
./scripts/ch.sh --param_tolerance_s=90 --param_pause_inactive=1 \
  --param_from_ts="2026-08-02 05:00:00" --param_to_ts="2026-08-02 09:00:00" \
  --queries-file sql/pipeline/03b_derive_incremental_atomic.sql >/dev/null

echo "== 6. refresh insights over the scenario range" >&2
FROM_TS='2026-08-02 05:00:00' TO_TS='2026-08-02 09:00:00' \
  CH_DATABASE="$DB" ./scripts/refresh_insights.sh >/dev/null 2>&1

echo "== 7. classify both spikes" >&2
# The previous verdict is SUPERSEDED, not removed first. concurrency_spike_events is
# ReplacingMergeTree(version) keyed on (content_id, window_start), and VERSION is a monotonically
# increasing UTC stamp, so re-classifying replaces the row and reads under FINAL see only the
# newest. Clearing it first would be the same lightweight-delete-then-reinsert pattern that
# silently masked 108,521 rows in raw_events earlier in this script's history -- applied, this
# time, to the table that holds the answer itself.
VERSION="$(date -u +%Y%m%d%H%M%S)"
for w in "06:00:00 06:30:00" "07:00:00 07:30:00"; do
  set -- $w
  ./scripts/ch.sh --param_content_id="$CONTENT_ID" \
    --param_from_ts="2026-08-02 $1" --param_to_ts="2026-08-02 $2" \
    --param_version="$VERSION" --queries-file sql/insights/spike/refresh_spike_events.sql >/dev/null
done

# ---------------------------------------------------------------------------------------------
echo "== 8. validate" >&2
{
  printf 'metric\tvalue\n'
  printf 'database\t%s\n' "$DB"
  printf 'sessions_per_scenario\t%s\n' "$SESSIONS"
  printf 'seed\t%s\n' "$SEED"

  ch --format TSVRaw --query "
    SELECT concat('source.', scenario, '.sessions'), toString(sessions) FROM (
      SELECT multiIf(startsWith(video_session_id,'spike-h-'),'healthy',
                     startsWith(video_session_id,'spike-w-'),'weak','other') AS scenario,
             uniqExact(video_session_id) AS sessions
      FROM raw_events WHERE content_id = $CONTENT_ID GROUP BY scenario ORDER BY scenario)"

  # The verdict, per scenario, plus the numbers behind it.
  ch --format TSVRaw --query "
    SELECT concat(scen, '.', k), v FROM (
      SELECT multiIf(toString(window_start) LIKE '%06:%','healthy','weak') AS scen,
             arrayJoin([
               ('peak_concurrency', toString(peak_concurrency)),
               ('minutes_to_peak', toString(minutes_to_peak)),
               ('minutes_above_80pct_peak', toString(minutes_above_80pct_peak)),
               ('retention_5m_percent', toString(round(retention_5m_percent,1))),
               ('retention_10m_percent', toString(round(retention_10m_percent,1))),
               ('retention_15m_percent', toString(round(retention_15m_percent,1))),
               ('background_rate', toString(round(background_rate_after_peak,3))),
               ('timeout_rate', toString(round(timeout_rate_after_peak,3))),
               ('error_rate', toString(round(error_rate_after_peak,3))),
               ('entered_sessions', toString(entered_sessions)),
               ('spike_type', spike_type)
             ]) AS kv, kv.1 AS k, kv.2 AS v
      FROM concurrency_spike_events FINAL WHERE content_id = $CONTENT_ID
      ORDER BY window_start)"

  # The gate. The two scenarios acquire the SAME audience, so a classifier that keys on peak
  # rather than on sustain would give them the same verdict. Requiring the pair to differ is
  # what makes this a test rather than a demonstration.
  h="$(val "SELECT spike_type FROM concurrency_spike_events FINAL
            WHERE content_id = $CONTENT_ID AND toHour(window_start) = 6 LIMIT 1")"
  w="$(val "SELECT spike_type FROM concurrency_spike_events FINAL
            WHERE content_id = $CONTENT_ID AND toHour(window_start) = 7 LIMIT 1")"
  printf 'classification.healthy\t%s\t(required healthy_sustained)\n' "${h:-none}"
  printf 'classification.weak\t%s\t(required short_lived)\n' "${w:-none}"
  verdict=PASS
  [ "$h" = healthy_sustained ] || verdict=FAIL
  [ "$w" = short_lived ]       || verdict=FAIL
  printf 'verdict\t%s\n' "$verdict"
} | evidence "spike_sustainability_$DB" "healthy vs weak spike, same acquisition, opposite sustain"
