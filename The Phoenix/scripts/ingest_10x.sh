#!/usr/bin/env bash
# Stage 5 ingestion: ten times the corpus into phoenix_next, in rules-compliant batches.
#
#   ./scripts/ingest_10x.sh                  # 10 generations, ~9.06M rows
#   GENERATIONS=3 ./scripts/ingest_10x.sh    # smaller rehearsal
#   PROBES_ONLY=1 ./scripts/ingest_10x.sh    # lateness probes without the bulk
#
# Audited against clickhouse-best-practices v0.1.0. Rule compliance is asserted in the evidence
# artifact, not claimed here; see docs/INSIGHT_BENCHMARKS.md for the review.
#
# WHY INSERT ... SELECT AND NOT A CLIENT-SIDE FORMAT. Rule 3.6 ranks Native above RowBinary above
# JSONEachRow for insert performance. All three describe data crossing the wire. This generates
# from raw_events that is ALREADY on the server, so the rows never leave it: no serialisation, no
# parsing, no wire transfer. The fastest format is the one you do not use. Rule 3.6 is satisfied
# by being inapplicable, which is worth saying out loud rather than quietly skipping.
#
# WHY NOT ASYNC INSERTS. Rule 3.5 recommends async_insert when client-side batching is not
# practical. Here it is practical: batches are sized deliberately below, so server-side buffering
# would add a flush timer and a durability question for no benefit. Rule 3.5 does not apply.
#
# WHY BATCHING BY HASH BUCKET AND NOT LIMIT/OFFSET. OFFSET re-scans and re-sorts the prefix on
# every batch, so 180 batches over 905K rows is quadratic. cityHash64(video_session_id) % N
# partitions the source once, deterministically, and keeps every event of a session in the same
# batch, which matters because a session split across batches with different arrival times is a
# different test from the one intended.
#
# THE BULK IS A BACKFILL AND WILL CLASSIFY AS LATE. Do not read that as a defect. Its events are
# timestamped in the replayed window and arrive now, so lateness is real and large, and
# late_event_audit is correct to say so. It demonstrates the policy on a genuine operational
# event. What it is NOT is a producer's lateness distribution, so it does NOT size
# allowed_lateness_seconds. docs/LATENESS.md stays provisional after this runs. The PROBES below
# are what exercise the on-time, acceptable and future classes.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix_next}"
GENERATIONS="${GENERATIONS:-10}"
# Rule 3.4: ideal 10,000 to 100,000 rows per INSERT. The corpus is 905,558 rows, so 18 buckets
# puts each batch at roughly 50,300: mid-band, and far from the 1,000-row minimum.
BUCKETS="${BUCKETS:-18}"
export CH_DATABASE="$DB" EVIDENCE_STAMP_DB="$DB"

[ "$DB" = "phoenix" ] && { echo "REFUSING: phoenix is generation 1 and read-only to this work." >&2; exit 1; }

ch() { ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

corpus_rows="$(val "SELECT count() FROM raw_events WHERE event_timestamp < {frozen_before:String}")"
[ "${corpus_rows:-0}" -gt 0 ] || { echo "no frozen corpus in $DB to replay" >&2; exit 1; }
per_batch=$(( corpus_rows / BUCKETS ))
echo "== source corpus $corpus_rows rows, $BUCKETS buckets, ~$per_batch rows per INSERT" >&2

# Rule 3.4 is a hard gate, not advice: a batch under 1,000 rows is refused rather than run.
if [ "$per_batch" -lt 1000 ]; then
  echo "REFUSING: $per_batch rows per batch is below the 1,000-row minimum (rule insert-batch-size)." >&2
  echo "  Lower BUCKETS. Tiny batches create tiny parts and overwhelm the merge process." >&2
  exit 1
fi
if [ "$per_batch" -gt 100000 ]; then
  echo "REFUSING: $per_batch rows per batch is above the 100,000-row ideal ceiling." >&2
  echo "  Raise BUCKETS." >&2
  exit 1
fi

# Every generation lands in the SAME replayed window, so they overlap and concurrency scales with
# the generation count, which is the load characteristic worth testing. Spreading them across
# successive windows instead would give ten times the rows at one times the concurrency, and
# would multiply the partition count by ten for no reason (rule 1.4).
#
# Shift = frozen_before minus the corpus start, so no synthetic row can ever land below
# frozen_before and contaminate the graded slice. scripts/frozen_gate.sh checks that afterwards.
SHIFT_S="$(val "
  SELECT toInt64(dateDiff('second',
    (SELECT min(event_timestamp) FROM raw_events WHERE event_timestamp < {frozen_before:String}),
    toDateTime64({frozen_before:String}, 3)))")"
echo "== shifting replayed events forward by $SHIFT_S seconds, to start exactly at frozen_before" >&2

COLS='content_id, video_session_id, user_id, event_type, event, event_timestamp,
      platform, app_version, country, audio_language, subtitle_language, player_version,
      session_start_epoch'

before_rows="$(val "SELECT count() FROM raw_events")"
before_frozen="$(val "SELECT count() FROM raw_events WHERE event_timestamp < {frozen_before:String}")"
t0=$(date +%s)
batches=0

if [ "${PROBES_ONLY:-0}" != "1" ]; then
  for g in $(seq 1 "$GENERATIONS"); do
    for b in $(seq 0 $(( BUCKETS - 1 ))); do
      # Into raw_events_landing, never raw_events: the landing table's MV is what stamps a true
      # arrival_timestamp with now64(3), materialised into the part at insert time.
      ch --query "
        INSERT INTO raw_events_landing ($COLS)
        SELECT
            content_id,
            concat(video_session_id, '_g$g') AS video_session_id,
            concat(user_id, '_g$g')          AS user_id,
            event_type, event,
            toUnixTimestamp64Milli(event_timestamp     + toIntervalSecond($SHIFT_S)) AS event_timestamp,
            platform, app_version, country, audio_language, subtitle_language, player_version,
            toUnixTimestamp64Milli(session_start_epoch + toIntervalSecond($SHIFT_S)) AS session_start_epoch
        FROM raw_events
        WHERE event_timestamp < {frozen_before:String}
          AND cityHash64(video_session_id) % $BUCKETS = $b" \
        --max_insert_block_size="$per_batch"
      batches=$(( batches + 1 ))
    done
    echo "   generation $g of $GENERATIONS complete ($batches batches so far)" >&2
  done
fi

# LATENESS PROBES. Known offsets, one per class, so the classifier is exercised on this database
# and not only in the scratch test. Same four offsets as scripts/test_lateness_classifier.sh.
echo "== lateness probes, one per class" >&2
for spec in "future:-3600:invalid_future_event" "fresh:10:on_time" \
            "acceptable:600:late_acceptable" "stale:7200:late_after_finalization"; do
  name="${spec%%:*}"; rest="${spec#*:}"; off="${rest%%:*}"
  ch --query "
    INSERT INTO raw_events_landing ($COLS)
    SELECT 101, 'probe_${name}_$$', 'probe_user_$$', 'VideoHeartbeat', 'heartbeat',
           toUnixTimestamp64Milli(now64(3) - toIntervalSecond($off)),
           'ANDROID_PHONE', '1.0.0', 'IN', 'hi', 'none', 'exo',
           toUnixTimestamp64Milli(now64(3) - toIntervalSecond($off))"
done
t1=$(date +%s)

after_rows="$(val "SELECT count() FROM raw_events")"
after_frozen="$(val "SELECT count() FROM raw_events WHERE event_timestamp < {frozen_before:String}")"
ingested=$(( after_rows - before_rows ))
observed="$(val "SELECT count() FROM raw_events WHERE arrival_timestamp > toDateTime64(0, 3)")"

# Rule 3.4 validation query, verbatim from the rule: parts per table. Over 3,000 active parts in
# one partition blocks inserts outright, so this is a real ceiling and not a tidiness metric.
max_parts="$(val "
  SELECT max(p) FROM (
    SELECT count() AS p FROM system.parts
    WHERE database = currentDatabase() AND table = 'raw_events' AND active
    GROUP BY partition)")"
partitions="$(val "
  SELECT uniqExact(partition) FROM system.parts
  WHERE database = currentDatabase() AND table = 'raw_events' AND active")"

probe() { val "
  SELECT lateness_class FROM late_event_audit
  WHERE video_session_id = 'probe_$1_$$' LIMIT 1"; }
c_future="$(probe future)"; c_fresh="$(probe fresh)"
c_accept="$(probe acceptable)"; c_stale="$(probe stale)"

verdict=PASS
chk() { [ "$1" = "$2" ] && echo PASS || { verdict=FAIL; echo FAIL; }; }
# The frozen corpus must be untouched. Every synthetic row is at or after frozen_before by
# construction; this is the check that the construction held.
[ "$before_frozen" = "$after_frozen" ] || verdict=FAIL
# Rule 1.4: partition cardinality stays in the low hundreds, nowhere near the 100-1,000 ceiling.
[ "${partitions:-9999}" -lt 100 ] || verdict=FAIL
# Rule 3.4: part count per partition well under the 3,000 that blocks inserts.
[ "${max_parts:-9999}" -lt 300 ] || verdict=FAIL

{
  printf 'metric\tvalue\tnote\n'
  printf 'database\t%s\t\n'                   "$DB"
  printf 'generations\t%s\t\n'                "$GENERATIONS"
  printf 'batches\t%s\t\n'                    "$batches"
  printf 'rows_per_batch\t%s\trule insert-batch-size: ideal 10,000 to 100,000\n' "$per_batch"
  printf 'rows_ingested\t%s\t\n'              "$ingested"
  printf 'ingest_seconds\t%s\t\n'             "$(( t1 - t0 ))"
  printf 'rows_per_second\t%s\t\n'            "$(( ingested / ((t1 - t0) > 0 ? (t1 - t0) : 1) ))"
  printf 'raw_events_total\t%s\t\n'           "$after_rows"
  printf 'rows_with_observed_arrival\t%s\tarrival_timestamp materialised by raw_events_mv\n' "$observed"
  printf 'frozen_slice_before\t%s\t\n'        "$before_frozen"
  printf 'frozen_slice_after\t%s\trequired equal: the graded corpus must be untouched\n' "$after_frozen"
  printf 'partitions\t%s\trule schema-partition-low-cardinality: keep under 1,000\n' "$partitions"
  printf 'max_parts_per_partition\t%s\trule insert-batch-size: 3,000 blocks inserts\n' "$max_parts"
  printf 'probe.invalid_future_event\t%s\t%s\n'   "$c_future" "$(chk invalid_future_event "$c_future")"
  printf 'probe.on_time_absent_from_audit\t%s\t%s\n' "${c_fresh:-<absent>}" "$(chk '' "$c_fresh")"
  printf 'probe.late_acceptable\t%s\t%s\n'        "$c_accept" "$(chk late_acceptable "$c_accept")"
  printf 'probe.late_after_finalization\t%s\t%s\n' "$c_stale" "$(chk late_after_finalization "$c_stale")"
  printf '#\tno OPTIMIZE FINAL is issued anywhere in this script (rule insert-optimize-avoid-final)\n'
  printf '#\tthe bulk is a BACKFILL: its lateness is real and large, and does NOT size allowed_lateness_seconds\n'
  printf 'verdict\t%s\t%s\n' "$verdict" "$verdict"
} | evidence "ingest_10x_${DB}" "ten generations of the corpus into ${DB} in rules-compliant batches, with lateness probes" \
  | xargs cat

[ "$verdict" = PASS ] || { echo "INGEST CHECKS FAILED" >&2; exit 1; }
echo "INGESTED $ingested rows in $batches batches. Next: derive and refresh the new window, then re-run bench_insights.sh." >&2
