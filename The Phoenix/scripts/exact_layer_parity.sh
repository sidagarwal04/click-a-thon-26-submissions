#!/usr/bin/env bash
# The exact layer's admission gate. Four assertions and two recorded readings, one artifact.
#
# The exact layer answers a DIFFERENT question from the minute layer (instantaneous vs
# touched-the-minute), so parity here is not equality. What must hold instead:
#   1. net delta is zero: every opened interval closes
#   2. instantaneous concurrency never goes negative anywhere in the series
#   3. no session overlaps itself in the source intervals (the design precondition)
#   4. the exact max inside every minute never exceeds that minute's touch count:
#      an instantaneous reading above the minute layer would mean double counting
# Recorded, not asserted: the exact peak/average against the minute layer's, because the
# definitions legitimately differ and the gap IS the finding.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

day_from="${1:-2026-07-26 00:00:00}"
day_to="${2:-2026-07-27 00:00:00}"

{
./scripts/ch.sh --format TSV --query "
SELECT 'net_delta', toString(sum(delta)), if(sum(delta) = 0, 'PASS', 'FAIL')
FROM concurrency_boundary_deltas WHERE ts < {frozen_before:String}"

./scripts/ch.sh --format TSV --query "
WITH curve AS (
  SELECT ts, sum(delta) AS d FROM concurrency_boundary_deltas
  WHERE ts < {frozen_before:String} GROUP BY ts)
SELECT 'min_instantaneous',
       toString(min(c)),
       if(min(c) >= 0, 'PASS', 'FAIL')
FROM (SELECT sum(d) OVER (ORDER BY ts ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c FROM curve)"

./scripts/ch.sh --format TSV --query "
WITH ordered AS (
  SELECT interval_start,
         max(interval_end) OVER (PARTITION BY video_session_id ORDER BY interval_start, interval_end
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_max_end
  FROM foreground_intervals WHERE interval_start < {frozen_before:String})
SELECT 'sessions_overlapping_self', toString(countIf(prev_max_end > interval_start)),
       if(countIf(prev_max_end > interval_start) = 0, 'PASS', 'FAIL')
FROM ordered"

# 4: per-minute comparison across the whole frozen span. The minute layer's value for a
# minute counts every session touching it; the exact layer's max inside the minute is the
# most that coexisted. exact > minute anywhere is a double count.
./scripts/ch.sh --format TSV --query "
WITH exact_curve AS (
  SELECT ts, toInt64(sum(sum(delta)) OVER (ORDER BY ts ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS c
  FROM concurrency_boundary_deltas WHERE ts < {frozen_before:String} GROUP BY ts),
exact_per_minute AS (
  SELECT toStartOfMinute(ts) AS minute, max(c) AS exact_max FROM exact_curve GROUP BY minute),
minute_curve AS (
  SELECT minute, toInt64(sum(sum(delta)) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS touch
  FROM concurrency_deltas WHERE minute < {frozen_before:String} GROUP BY minute)
SELECT 'minutes_exact_exceeds_touch', toString(countIf(e.exact_max > m.touch)),
       if(countIf(e.exact_max > m.touch) = 0, 'PASS', 'FAIL')
FROM exact_per_minute e
INNER JOIN minute_curve m USING (minute)"

# Recorded readings for the headline day, both layers side by side.
./scripts/ch.sh --format TSV \
  --param_platform '' --param_country '' --param_video_type '' --param_app_version '' \
  --param_content_id 0 --param_from_ts "$day_from" --param_to_ts "$day_to" \
  --queries-file sql/queries/serving/peak_average_exact.sql \
  | awk -v OFS='\t' '{print "exact_day", $0}'

./scripts/ch.sh --format TSV \
  --param_platform '' --param_country '' --param_video_type '' --param_app_version '' \
  --param_content_id 0 --param_from_ts "$day_from" --param_to_ts "$day_to" --param_grain_s 86400 \
  --queries-file sql/queries/serving/peak_average.sql 2>/dev/null \
  | awk -v OFS='\t' '{print "minute_day", $0}' || true
} | evidence exact_layer_parity "exact boundary layer: invariants asserted, minute-layer comparison recorded ($day_from -> $day_to)"
