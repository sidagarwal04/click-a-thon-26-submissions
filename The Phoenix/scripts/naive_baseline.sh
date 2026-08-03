#!/usr/bin/env bash
# Build and measure the naive baseline table.
#
#   ./scripts/naive_baseline.sh
#
# concurrency_deltas_naive has the same structure and engine as concurrency_deltas, and is
# populated with the same minute-boundary rule, so the overcount is a table-vs-table
# comparison at identical grain rather than two numbers from two different implementations.
#
# The table is TRUNCATEd before every load. SummingMergeTree absorbs a second insert with no
# error and no complaint, so re-running without the truncate would silently double the naive
# curve and inflate the overcount.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

DB="${CH_DATABASE:-phoenix}"
ch() { CH_DATABASE="$DB" ./scripts/ch.sh "$@" 2>/dev/null; }
val() { ch --format TSVRaw --query "$1" | head -1; }

echo "== 1. creating $DB.concurrency_deltas_naive from concurrency_deltas"
ch --query "CREATE TABLE IF NOT EXISTS concurrency_deltas_naive AS concurrency_deltas"
ch --query "TRUNCATE TABLE concurrency_deltas_naive"

echo "== 2. populating from raw_events (session span, first event to last)"
ch --queries-file sql/queries/validation/naive_deltas.sql

echo "== 3. assertions"
FROZEN="${FROZEN_BEFORE:-2026-08-01}"
BAL=$(val "SELECT sum(delta) FROM concurrency_deltas_naive")
NMIN=$(val "SELECT min(minute) FROM concurrency_deltas_naive")
NMAX=$(val "SELECT max(minute) FROM concurrency_deltas_naive")
FMIN=$(val "SELECT min(minute) FROM concurrency_deltas WHERE minute < '$FROZEN'")
FMAX=$(val "SELECT max(minute) FROM concurrency_deltas WHERE minute < '$FROZEN'")
# The comparison range is the INTERSECTION of the two spans, not their union, and not a
# requirement that they be identical.
#
# Requiring identical spans is what halted this script before, and it was the gate that was
# wrong rather than the data. The corrected table legitimately ends one minute later than the
# naive one: a foreground interval runs to last_event + tolerance, so it can reach into a
# minute that the session's last raw event did not. That tolerance tail is validated design.
# A gate that fails on it is mis-calibrated, and "halt" is the most expensive possible
# response to a known, intended, one-minute difference.
#
# Clipping keeps the comparison honest in the way that actually matters: both curves are
# evaluated over exactly the same minutes, so neither gets credit or blame for a minute the
# other never saw. The minutes dropped by the clip are reported rather than swallowed.
CMIN=$(val "SELECT toString(greatest(toDateTime('$NMIN'), toDateTime('$FMIN')))")
CMAX=$(val "SELECT toString(least(toDateTime('$NMAX'), toDateTime('$FMAX')))")
EXCLUDED=$(val "SELECT toString(dateDiff('minute', toDateTime('$CMIN'), toDateTime('$CMAX')) * -1
                     + dateDiff('minute', least(toDateTime('$NMIN'), toDateTime('$FMIN')),
                                          greatest(toDateTime('$NMAX'), toDateTime('$FMAX'))))")
echo "   sum(delta) naive:     $BAL   (must be 0: every +1 has a matching -1)"
echo "   naive     span: $NMIN .. $NMAX"
echo "   corrected span: $FMIN .. $FMAX"
echo "   compared  span: $CMIN .. $CMAX   ($EXCLUDED minute(s) excluded by the clip)"

# A failed gate is evidence too. Exiting without writing one leaves the same hole this
# whole exercise exists to close: a result that lived only in a terminal.
gate_fail() {
  printf 'metric\tvalue\ngate\tFAIL\nreason\t%s\nnaive_sum_delta\t%s\nnaive_min_minute\t%s\nnaive_max_minute\t%s\ncorrected_min_minute\t%s\ncorrected_max_minute\t%s\n' \
    "$1" "$BAL" "$NMIN" "$NMAX" "$FMIN" "$FMAX" \
    | evidence naive_baseline_gate "range/balance gate before the naive-vs-corrected comparison" >/dev/null
  echo "FAIL: $1" >&2
  exit 1
}

# Balance still halts: a naive curve that does not close to zero is genuinely broken, and
# no amount of clipping makes a comparison against it meaningful.
[ "$BAL" = "0" ] || gate_fail "naive deltas do not balance to zero, the curve is not closed"
# The only range condition that can still invalidate the comparison is an EMPTY overlap.
if [ "$(val "SELECT toDateTime('$CMIN') >= toDateTime('$CMAX')")" = "1" ]; then
  gate_fail "the two tables do not overlap at all, there is nothing to compare"
fi

# A PASSING gate is evidence too, for the same reason a failing one is: without this row the
# ledger keeps whatever the gate last wrote, so a FAIL from a since-recalibrated gate reads
# as an open failure forever. Replacing the claim_id in place is the ledger's own convention.
printf 'metric\tvalue\ngate\tPASS\nnaive_sum_delta\t%s\nnaive_min_minute\t%s\nnaive_max_minute\t%s\ncorrected_min_minute\t%s\ncorrected_max_minute\t%s\nminutes_excluded_by_clip\t%s\n' \
  "$BAL" "$NMIN" "$NMAX" "$FMIN" "$FMAX" "$EXCLUDED" \
  | evidence naive_baseline_gate "range/balance gate before the naive-vs-corrected comparison" >/dev/null

echo "== 4. measuring"
# Both curves are densified to one row per minute across the shared range BEFORE any
# aggregate is taken. Deltas exist only at run boundaries, so a naive run covering minutes
# 10-20 has rows at 10 and 21 and nothing between. Counting phantom minutes on the sparse
# rows would find 1 where there are 11.
ch --format TSV --query "
WITH both AS
(
    SELECT minute, sum(dn) AS dn, sum(df) AS df
    FROM
    (
        SELECT minute, delta AS dn, 0 AS df FROM concurrency_deltas_naive
        UNION ALL
        SELECT minute, 0 AS dn, delta AS df FROM concurrency_deltas WHERE minute < '$FROZEN'
    )
    GROUP BY minute
),
curves AS
(
    SELECT
        minute,
        toInt64(sum(dn) OVER w) AS naive,
        toInt64(sum(df) OVER w) AS corrected
    FROM both
    WINDOW w AS (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    ORDER BY minute ASC
    WITH FILL FROM toDateTime('$CMIN') TO toDateTime('$CMAX') + toIntervalMinute(1)
        STEP toIntervalMinute(1) INTERPOLATE (naive AS naive, corrected AS corrected)
),
clipped AS
(
    -- Clip AFTER both cumulative sums, never before. Filtering the deltas first would
    -- restart both curves at zero inside the window and understate them identically, which
    -- is the seeding trap wearing a different hat.
    SELECT minute, naive, corrected FROM curves
    WHERE minute >= toDateTime('$CMIN') AND minute <= toDateTime('$CMAX')
)
SELECT 'metric', 'value'
UNION ALL SELECT 'peak_naive',              toString(max(naive))                       FROM clipped
UNION ALL SELECT 'peak_naive_minute',       toString(argMax(minute, naive))            FROM clipped
UNION ALL SELECT 'peak_corrected',          toString(max(corrected))                   FROM clipped
UNION ALL SELECT 'peak_corrected_minute',   toString(argMax(minute, corrected))        FROM clipped
UNION ALL SELECT 'overcount_pct_at_peak',   toString(round((max(naive) - max(corrected)) * 100.0 / max(corrected), 1)) FROM clipped
UNION ALL SELECT 'phantom_minutes',         toString(countIf(naive > 0 AND corrected = 0)) FROM clipped
UNION ALL SELECT 'inverted_minutes',        toString(countIf(corrected > 0 AND naive = 0)) FROM clipped
UNION ALL SELECT 'minutes_naive_gt0',       toString(countIf(naive > 0))               FROM clipped
UNION ALL SELECT 'minutes_corrected_gt0',   toString(countIf(corrected > 0))           FROM clipped
UNION ALL SELECT 'minutes_compared',        toString(count())                          FROM clipped
UNION ALL SELECT 'compare_range_start',     '$CMIN'
UNION ALL SELECT 'compare_range_end',       '$CMAX'
UNION ALL SELECT 'minutes_excluded_by_clip','$EXCLUDED'
UNION ALL SELECT 'naive_span',              '$NMIN .. $NMAX'
UNION ALL SELECT 'corrected_span',          '$FMIN .. $FMAX'
UNION ALL SELECT 'naive_delta_rows',        toString((SELECT count() FROM concurrency_deltas_naive))
UNION ALL SELECT 'naive_sum_delta',         toString((SELECT sum(delta) FROM concurrency_deltas_naive))
UNION ALL SELECT 'gate',                    'PASS'
" | evidence naive_baseline "naive session-span vs foreground-only, same minute rule, densified, clipped to the overlapping range" \
  | xargs cat
