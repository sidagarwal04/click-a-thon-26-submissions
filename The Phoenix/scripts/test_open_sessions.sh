#!/usr/bin/env bash
# Open-session proof.
#
# The sample dataset has zero open sessions: every one carries a VideoSessionEnd. The unseen
# day is stated to contain sessions still open when the day cuts off, and update handling is
# a named judging criterion, so this path would otherwise ship unvalidated.
#
# The test manufactures the missing condition and checks the one thing that matters: that
# feeding the continuation through the incremental path lands on exactly the same answer as
# deriving the complete session in one pass.
#
#   phoenix_open_test    truncated sessions ("day 1"), then their tails ("day 2 arrivals")
#   phoenix_open_truth   the same sessions, complete, derived once
#
# Verdict is a diff of the two concurrency curves. Anything but zero is a failure.
#
#   ./scripts/test_open_sessions.sh [session_count]
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

# Assertions, retraction counts and diff counts accumulate here and are flushed to evidence/
# at the verdict, before the cleanup trap fires. Without this the proof of the open-session
# path lived only in a terminal scrollback, and open sessions are the DEFAULT state in a
# live replay: this is the one path that cannot stay unwitnessed.
METRICS=""
metric() { METRICS="${METRICS}${1}	${2}
"; }
# TSVRaw single value, for arithmetic rather than display
val() { CH_DATABASE="$1" ./scripts/ch.sh --format TSVRaw --query "$2" 2>/dev/null | head -1; }

N="${1:-30}"
TEST=phoenix_open_test
TRUTH=phoenix_open_truth
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

q() { CH_DATABASE="$1" ./scripts/ch.sh "${@:2}" 2>&1 | grep -v "Unknown settings" || true; }
pipeline() { CH_DATABASE="$1" ./scripts/ch.sh --param_tolerance_s="${TOLERANCE_S:-90}" \
    --param_pause_inactive="${PAUSE_INACTIVE:-1}" --param_from_ts="$2" --param_to_ts="$3" \
    --queries-file sql/pipeline/03_derive_incremental.sql 2>&1 | grep -v "Unknown settings" || true; }

echo "== 1. building isolated databases"
for db in "$TEST" "$TRUTH"; do
  q default --query "DROP DATABASE IF EXISTS $db"
  q default --query "CREATE DATABASE $db"
  for f in sql/schema/*.sql; do q "$db" --queries-file "$f"; done
  q "$db" --query "INSERT INTO content SELECT * FROM phoenix.content"
done

echo "== 2. selecting $N real sessions with backgrounding and pauses"
# A session qualifies only if it has enough events to cut in half, a clean end, and both an
# AppBackgrounded and a pause, so the truncation exercises the interesting branches.
q phoenix --query "
CREATE OR REPLACE TABLE phoenix.open_test_sessions ENGINE = MergeTree ORDER BY video_session_id AS
SELECT
    video_session_id,
    -- cut at the 60th percentile event: far enough in to have real intervals behind it,
    -- early enough to leave a meaningful tail
    quantileExact(0.6)(toUnixTimestamp(event_timestamp)) AS cutoff
FROM phoenix.raw_events
GROUP BY video_session_id
HAVING count() BETWEEN 20 AND 400
   AND countIf(event_type = 'VideoSessionEnd') = 1
   AND countIf(event_type = 'AppBackgrounded') > 0
   AND countIf(event = 'pause') > 0
ORDER BY cityHash64(video_session_id)
LIMIT $N"
q phoenix --format PrettyCompact --query "SELECT count() AS sessions_selected FROM phoenix.open_test_sessions"
metric sessions_selected "$(val phoenix "SELECT count() FROM phoenix.open_test_sessions")"

echo "== 3. truth: the same sessions, complete, derived in one pass by the BATCH path"
# Deliberately the batch scripts (01 + 02), not the incremental one under test: comparing the
# incremental path against itself would only prove it is self-consistent.
q "$TRUTH" --query "
INSERT INTO raw_events SELECT r.* FROM phoenix.raw_events r
INNER JOIN phoenix.open_test_sessions s ON r.video_session_id = s.video_session_id"
CH_DATABASE="$TRUTH" ./scripts/ch.sh --param_tolerance_s="${TOLERANCE_S:-90}" \
  --param_pause_inactive="${PAUSE_INACTIVE:-1}" --queries-file sql/pipeline/01_derive_intervals.sql 2>&1 | grep -v "Unknown settings" || true
CH_DATABASE="$TRUTH" ./scripts/ch.sh --queries-file sql/pipeline/02_merge_runs.sql 2>&1 | grep -v "Unknown settings" || true

echo "== 4. day 1: the same sessions, truncated mid-playback (no VideoSessionEnd)"
q "$TEST" --query "
INSERT INTO raw_events SELECT r.* FROM phoenix.raw_events r
INNER JOIN phoenix.open_test_sessions s ON r.video_session_id = s.video_session_id
WHERE toUnixTimestamp(r.event_timestamp) < s.cutoff"
q "$TEST" --format PrettyCompact --query "
SELECT count() AS events_day1, countIf(event_type = 'VideoSessionEnd') AS ends_present FROM raw_events"
metric events_day1 "$(val "$TEST" "SELECT count() FROM raw_events")"
metric ends_present_day1 "$(val "$TEST" "SELECT countIf(event_type = 'VideoSessionEnd') FROM raw_events")"
pipeline "$TEST" '2000-01-01 00:00:00' '2100-01-01 00:00:00'

echo "== 4b. bystanders: 200 unrelated complete sessions that must never be re-derived"
# Without these the test database holds only the sessions under test, so 'incremental' would
# be indistinguishable from 'rebuild everything'.
q phoenix --query "
CREATE OR REPLACE TABLE phoenix.open_test_bystanders ENGINE = MergeTree ORDER BY video_session_id AS
SELECT video_session_id FROM phoenix.raw_events
WHERE video_session_id NOT IN (SELECT video_session_id FROM phoenix.open_test_sessions)
GROUP BY video_session_id
ORDER BY cityHash64(video_session_id) LIMIT 200"
q "$TEST" --query "
INSERT INTO raw_events SELECT r.* FROM phoenix.raw_events r
INNER JOIN phoenix.open_test_bystanders b ON r.video_session_id = b.video_session_id"
pipeline "$TEST" '2000-01-01 00:00:00' '2100-01-01 00:00:00'
q "$TRUTH" --query "
INSERT INTO raw_events SELECT r.* FROM phoenix.raw_events r
INNER JOIN phoenix.open_test_bystanders b ON r.video_session_id = b.video_session_id"
CH_DATABASE="$TRUTH" ./scripts/ch.sh --param_tolerance_s="${TOLERANCE_S:-90}" \
  --param_pause_inactive="${PAUSE_INACTIVE:-1}" --param_from_ts='2000-01-01 00:00:00' \
  --param_to_ts='2100-01-01 00:00:00' --queries-file sql/pipeline/03_derive_incremental.sql 2>&1 | grep -v "Unknown settings" || true

echo "== 5. state after day 1: are they carried as open?"
q "$TEST" --format PrettyCompact --query "
SELECT
    sum(sign)                                   AS asserted_runs,
    max(run_end)                                AS latest_run_end,
    (SELECT max(toDateTime(event_timestamp)) FROM raw_events) AS latest_event,
    dateDiff('second', latest_event, latest_run_end) AS provisional_tail_s
FROM session_minute_runs"
metric day1_asserted_runs "$(val "$TEST" "SELECT sum(sign) FROM session_minute_runs")"
metric day1_provisional_tail_s "$(val "$TEST" "SELECT dateDiff('second', (SELECT max(toDateTime(event_timestamp)) FROM raw_events), max(run_end)) FROM session_minute_runs")"

echo "== 5b. open sessions must be counted as watching at the cutoff, not dropped"
q "$TEST" --format PrettyCompact --query "
SELECT
    max(c)                       AS peak_while_open,
    -- MINUTES with an audience, not ROWS. concurrency_deltas is sparse: a row is a change, and
    -- its value holds until the next row. countIf(c > 0) over the raw rows counts boundaries and
    -- undercounts badly (measured elsewhere in this repo: 1,413 rows against 3,664 minutes). The
    -- gap-weighted form below is the one proven in scripts/ground_state.sh.
    toInt64(sumIf(held, c > 0))  AS minutes_with_audience
FROM (
    SELECT c,
           greatest(dateDiff('minute', minute, leadInFrame(minute) OVER
               (ORDER BY minute ASC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)), 0) AS held
    FROM (SELECT minute,
                 sum(delta) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c
          FROM (SELECT minute, sum(delta) AS delta FROM concurrency_deltas GROUP BY minute))
)"
metric day1_peak_while_open "$(val "$TEST" "SELECT max(c) FROM (SELECT sum(delta) OVER (ORDER BY minute ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c FROM (SELECT minute, sum(delta) AS delta FROM concurrency_deltas GROUP BY minute))")"
metric day1_minutes_with_audience "$(val "$TEST" "SELECT sum(held) FROM (SELECT c, greatest(dateDiff('minute', minute, leadInFrame(minute) OVER (ORDER BY minute ASC ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)), 0) AS held FROM (SELECT minute, sum(delta) OVER (ORDER BY minute ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS c FROM (SELECT minute, sum(delta) AS delta FROM concurrency_deltas GROUP BY minute))) WHERE c > 0")"

# Baseline before the arrival. Step 4b re-derives over an unbounded window on purpose, so
# the cumulative retraction count includes bystander rows that pass legitimately wrote. Only
# the DELTA across step 6 answers "did the tail arrival touch a session it should not have".
PRE_TEST=$(val "$TEST" "SELECT countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_sessions)) FROM session_minute_runs")
PRE_BY=$(val "$TEST" "SELECT countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_bystanders)) FROM session_minute_runs")

echo "== 6. day 2 arrivals: the previously dropped tails, including the real ends"
q "$TEST" --query "
INSERT INTO raw_events SELECT r.* FROM phoenix.raw_events r
INNER JOIN phoenix.open_test_sessions s ON r.video_session_id = s.video_session_id
WHERE toUnixTimestamp(r.event_timestamp) >= s.cutoff"
# Window bounded to the arrival period only. An unbounded window would re-derive everything
# and quietly prove nothing about incrementality.
TAIL_FROM=$(q "$TEST" --format TSVRaw --query "
SELECT toString(min(toDateTime(r.event_timestamp))) FROM phoenix.raw_events r
INNER JOIN phoenix.open_test_sessions s ON r.video_session_id = s.video_session_id
WHERE toUnixTimestamp(r.event_timestamp) >= s.cutoff")
echo "  arrival window: $TAIL_FROM -> 2100-01-01 00:00:00"
pipeline "$TEST" "$TAIL_FROM" '2100-01-01 00:00:00'
q "$TEST" --format PrettyCompact --query "
SELECT sum(sign) AS asserted_runs, count() AS rows_written, countIf(sign = -1) AS retractions
FROM session_minute_runs"
metric day2_asserted_runs "$(val "$TEST" "SELECT sum(sign) FROM session_minute_runs")"
metric day2_rows_written "$(val "$TEST" "SELECT count() FROM session_minute_runs")"
metric day2_retractions "$(val "$TEST" "SELECT countIf(sign = -1) FROM session_minute_runs")"

echo "== 6b. did the arrival touch anything it should not have?"
q "$TEST" --format PrettyCompact --query "
SELECT
    countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_sessions))    AS retracted_under_test,
    countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_bystanders)) AS retracted_bystanders
FROM session_minute_runs"
metric retracted_under_test "$(val "$TEST" "SELECT countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_sessions)) FROM session_minute_runs")"
metric retracted_bystanders "$(val "$TEST" "SELECT countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_bystanders)) FROM session_minute_runs")"
metric bystanders_total "$(val phoenix "SELECT count() FROM phoenix.open_test_bystanders")"
# The claim under test: the tail arrival retracted runs for sessions under test and for no
# one else. Cumulative counts above cannot show this; these deltas can.
POST_TEST=$(val "$TEST" "SELECT countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_sessions)) FROM session_minute_runs")
POST_BY=$(val "$TEST" "SELECT countIf(sign = -1 AND video_session_id IN (SELECT video_session_id FROM phoenix.open_test_bystanders)) FROM session_minute_runs")
metric arrival_retracted_under_test "$(( POST_TEST - PRE_TEST ))"
metric arrival_retracted_bystanders "$(( POST_BY - PRE_BY ))"
metric arrival_sessions_rederived "$(val "$TEST" "SELECT uniqExact(video_session_id) FROM raw_events WHERE event_timestamp >= parseDateTimeBestEffort('$TAIL_FROM')")"

echo "== 7. verdict: incremental result vs one-pass truth"
curve() { CH_DATABASE="$1" ./scripts/ch.sh --format TSV \
    --param_platform='' --param_country='' --param_video_type='' --param_app_version='' \
    --param_content_id=0 --param_from_ts='2000-01-01 00:00:00' --param_to_ts='2100-01-01 00:00:00' \
    --queries-file sql/queries/serving/concurrency_curve.sql 2>&1 | grep -v "Unknown settings"; }
curve "$TEST"  > "$TMP/test.tsv"
curve "$TRUTH" > "$TMP/truth.tsv"
DIFFS=$(diff "$TMP/truth.tsv" "$TMP/test.tsv" | grep -c '^[<>]' || true)
echo "  truth minutes:       $(wc -l < "$TMP/truth.tsv")"
echo "  incremental minutes: $(wc -l < "$TMP/test.tsv")"
echo "  differing rows:      $DIFFS"
metric truth_minutes "$(wc -l < "$TMP/truth.tsv")"
metric incremental_minutes "$(wc -l < "$TMP/test.tsv")"
metric differing_rows "$DIFFS"
metric verdict "$([ "$DIFFS" = "0" ] && echo PASS || echo FAIL)"
metric tolerance_s "${TOLERANCE_S:-90}"
metric pause_inactive "${PAUSE_INACTIVE:-1}"

# Flushed here, before the EXIT trap removes $TMP and before the non-zero exit below.
printf 'metric\tvalue\n%s' "$METRICS" \
  | evidence open_sessions "incremental absorption of open sessions vs one-pass batch truth" >/dev/null

[ "$DIFFS" = "0" ] && echo "  PASS: open sessions absorbed incrementally, no rebuild" \
                   || { echo "  FAIL"; diff "$TMP/truth.tsv" "$TMP/test.tsv" | head -20; exit 1; }
