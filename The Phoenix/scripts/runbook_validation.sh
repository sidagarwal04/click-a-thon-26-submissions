#!/usr/bin/env bash
# Every number quoted in docs/review/validation_runbook_filled.md that was not already
# covered by an existing artifact. Written because the repo's own rule is "no pipeline
# evidence, no credit", and a filled review that measures 20 numbers ad hoc and tags none of
# them breaks that rule in the one document whose whole point is being checkable.
#
#   ./scripts/runbook_validation.sh          -> evidence/runbook_validation__<ts>__<sha>.tsv
#
# Test numbers refer to sonyliv_30_minute_manual_sql_validation_runbook.md.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/evidence.sh

q() { ./scripts/ch.sh --format TSVRaw --query "$1" 2>/dev/null | head -1; }

{
  printf 'test\tmetric\tvalue\n'

  # T8/T9. content is Replacing, so a bare count() can exceed uniqExact from unmerged parts.
  # FINAL is reported alongside precisely so a reviewer can see it does not.
  printf '8\tcontent_rows_bare\t%s\n'   "$(q "SELECT count() FROM content")"
  printf '8\tcontent_rows_final\t%s\n'  "$(q "SELECT count() FROM content FINAL")"
  printf '8\tcontent_uniq_ids\t%s\n'    "$(q "SELECT uniqExact(content_id) FROM content")"
  printf '9\tcontent_dup_groups\t%s\n'  "$(q "SELECT count() FROM (SELECT content_id FROM content GROUP BY content_id HAVING count()>1)")"

  # T10. LEFT ANTI, so a zero means every event's content_id resolves in the metadata.
  printf '10\tunmatched_event_rows\t%s\n' "$(q "
    SELECT count() FROM raw_events r LEFT ANTI JOIN content c ON r.content_id=c.content_id
    WHERE r.event_timestamp < {frozen_before:String}")"

  # T11.
  q "SELECT countIf(video_session_id='')||'\n'||countIf(user_id='')||'\n'||countIf(event_type='')
     FROM raw_events WHERE event_timestamp < {frozen_before:String}" >/dev/null
  printf '11\tmissing_required_fields\t%s\n' "$(q "
    SELECT countIf(video_session_id='') + countIf(user_id='') + countIf(event_type='')
         + countIf(content_id=0) + countIf(event_timestamp < session_start_epoch)
    FROM raw_events WHERE event_timestamp < {frozen_before:String}")"

  # T12.
  printf '12\tduplicate_groups\t%s\n' "$(q "
    SELECT count() FROM (SELECT video_session_id, event_timestamp, event_type, event, count() c
    FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY 1,2,3,4 HAVING c>1)")"
  printf '12\texcess_rows\t%s\n' "$(q "
    SELECT sum(c-1) FROM (SELECT video_session_id, event_timestamp, event_type, event, count() c
    FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY 1,2,3,4 HAVING c>1)")"

  # T13/T14. Dimension pinning is argMin(dim, event_timestamp) in 01_derive_intervals.sql, so
  # the dirty sessions counted here resolve deterministically to their first event.
  for m in "multiple_starts:countIf(s>1)" "multiple_ends:countIf(e>1)" "missing_start:countIf(s=0)" "missing_end:countIf(e=0)"; do
    printf '13\t%s\t%s\n' "${m%%:*}" "$(q "
      SELECT ${m##*:} FROM (SELECT video_session_id, countIf(event_type='VideoSessionStart') s,
      countIf(event_type='VideoSessionEnd') e FROM raw_events
      WHERE event_timestamp < {frozen_before:String} GROUP BY video_session_id)")"
  done
  for m in "multi_platform_sessions:countIf(p>1)" "multi_user_sessions:countIf(u>1)" "multi_content_sessions:countIf(c>1)"; do
    printf '14\t%s\t%s\n' "${m%%:*}" "$(q "
      SELECT ${m##*:} FROM (SELECT video_session_id, uniqExact(platform) p, uniqExact(user_id) u,
      uniqExact(content_id) c FROM raw_events WHERE event_timestamp < {frozen_before:String}
      GROUP BY video_session_id)")"
  done

  # T17. THE ONE THAT IS NOT ZERO. 385 intervals extend past the session's last
  # VideoSessionEnd, in 21 sessions, and 336 of them exceed the 90s tolerance so the
  # tolerance tail does not explain it. Cause is dirty data: 14 sessions emit more than one
  # end (T13) and events continue after the last one, and the state machine reopens on a
  # later VideoPlay.
  _se="WITH se AS (SELECT video_session_id, maxIf(event_timestamp, event_type='VideoSessionEnd') AS session_end
       FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY video_session_id)"
  printf '17\tinvalid_intervals\t%s\n' "$(q "$_se
    SELECT countIf(i.interval_end > e.session_end) FROM foreground_intervals i
    INNER JOIN se e USING (video_session_id) WHERE e.session_end > 0 AND i.interval_start < {frozen_before:String}")"
  printf '17\tbeyond_90s_tolerance\t%s\n' "$(q "$_se
    SELECT countIf(i.interval_end > e.session_end + INTERVAL 90 SECOND) FROM foreground_intervals i
    INNER JOIN se e USING (video_session_id) WHERE e.session_end > 0 AND i.interval_start < {frozen_before:String}")"
  printf '17\toffending_sessions\t%s\n' "$(q "$_se
    SELECT uniqExact(i.video_session_id) FROM foreground_intervals i
    INNER JOIN se e USING (video_session_id) WHERE e.session_end > 0 AND i.interval_end > e.session_end")"
  # Median as well as max: the median is what says the effect on the AVERAGE will not be
  # exactly zero, and that claim should not rest on an untagged number.
  printf '17\tovershoot_median_s\t%s\n' "$(q "$_se
    SELECT toUInt32(quantile(0.5)(dateDiff('second', e.session_end, i.interval_end))) FROM foreground_intervals i
    INNER JOIN se e USING (video_session_id) WHERE e.session_end > 0 AND i.interval_end > e.session_end")"
  printf '17\tovershoot_max_s\t%s\n' "$(q "$_se
    SELECT max(dateDiff('second', e.session_end, i.interval_end)) FROM foreground_intervals i
    INNER JOIN se e USING (video_session_id) WHERE e.session_end > 0 AND i.interval_end > e.session_end")"
  # One GROUP BY, not a correlated subquery per session: this service throws NOT_IMPLEMENTED
  # on correlated expressions in a sorting step, and a form that silently returned something
  # different would be worse than one that errors.
  printf '17\tsessions_with_events_after_last_end\t%s\n' "$(q "
    SELECT countIf(last_any > session_end) FROM (
      SELECT video_session_id, maxIf(event_timestamp, event_type='VideoSessionEnd') AS session_end,
             max(event_timestamp) AS last_any
      FROM raw_events WHERE event_timestamp < {frozen_before:String} GROUP BY video_session_id)
    WHERE session_end > 0")"

  # T17 impact. UPPER BOUND, not a measurement: excluding these 21 sessions removes their
  # legitimate pre-end viewing too, so the true damage is at most this difference.
  _bad="$_se, bad AS (SELECT DISTINCT i.video_session_id AS sid FROM foreground_intervals i
        INNER JOIN se e USING (video_session_id) WHERE e.session_end > 0 AND i.interval_end > e.session_end),
        d AS (SELECT arrayJoin([(run_start,1),(run_end + INTERVAL 1 MINUTE,-1)]) AS p, video_session_id, sign
              FROM session_minute_runs WHERE run_start < {frozen_before:String})"
  printf '17\tpeak_all_sessions\t%s\n' "$(q "$_bad
    SELECT max(c) FROM (SELECT sum(dl) OVER (ORDER BY m) c FROM
      (SELECT p.1 m, sum(p.2*sign) dl FROM d GROUP BY m))")"
  printf '17\tpeak_excluding_offenders_UPPER_BOUND\t%s\n' "$(q "$_bad
    SELECT max(c) FROM (SELECT sum(dl) OVER (ORDER BY m) c FROM
      (SELECT p.1 m, sum(p.2*sign) dl FROM d WHERE video_session_id NOT IN (SELECT sid FROM bad) GROUP BY m))")"

  # T19/T20.
  printf '19\toverlapping_runs\t%s\n' "$(q "
    WITH o AS (SELECT run_start, lagInFrame(run_end) OVER (PARTITION BY video_session_id ORDER BY run_start) prev
    FROM session_minute_runs FINAL WHERE run_start < {frozen_before:String})
    SELECT countIf(run_start < prev) FROM o")"
  printf '20\tmax_runs_per_session_minute\t%s\n' "$(q "
    SELECT max(c) FROM (SELECT video_session_id,
      arrayJoin(timeSlots(run_start, toUInt32(dateDiff('second',run_start,run_end)),60)) m, count() c
    FROM session_minute_runs FINAL WHERE run_start < {frozen_before:String} GROUP BY video_session_id, m)")"

  # T21-T25.
  printf '21\tsession_net_delta\t%s\n' "$(q "SELECT sum(delta) FROM concurrency_deltas WHERE minute < {frozen_before:String}")"
  printf '22\tuser_net_delta\t%s\n'    "$(q "SELECT sum(delta) FROM user_concurrency_deltas WHERE minute < {frozen_before:String}")"
  _curve="SELECT min(c), max(c) FROM (SELECT sum(d) OVER (ORDER BY minute) c FROM
          (SELECT minute, sum(delta) d FROM %s WHERE minute < {frozen_before:String} GROUP BY minute))"
  printf '23\tsession_min_peak\t%s\n' "$(q "$(printf "$_curve" concurrency_deltas)" | tr '\t' '/')"
  printf '24\tuser_min_peak\t%s\n'    "$(q "$(printf "$_curve" user_concurrency_deltas)" | tr '\t' '/')"

  # T28. THE AVERAGE. The runbook's own reference query returns 87.82, and it is biased LOW:
  # 928 of the 1440 minutes have no delta row, so its LEFT JOIN scores them 0 instead of
  # carrying the standing concurrency forward. The ASOF variant below is an independent
  # last-observation-carried-forward reference sharing no code with sql/queries/serving/.
  _day="toDateTime('2026-07-26 00:00:00') AS f, toDateTime('2026-07-27 00:00:00') AS t"
  printf '28\tminutes_lacking_a_delta_row\t%s\n' "$(q "
    WITH $_day SELECT countIf(d.minute IS NULL)
    FROM (SELECT arrayJoin(timeSlots(f, toUInt32(dateDiff('second',f,t)-60),60)) AS minute) m
    LEFT JOIN (SELECT DISTINCT minute FROM concurrency_deltas WHERE minute >= f AND minute < t) d
    USING (minute) SETTINGS join_use_nulls=1")"
  printf '28\treference_query_average_BIASED_LOW\t%s\n' "$(q "
    WITH $_day, deltas AS (SELECT minute, sum(delta) AS delta FROM concurrency_deltas WHERE minute < t GROUP BY minute),
      curve AS (SELECT minute, sum(delta) OVER (ORDER BY minute) AS concurrency FROM deltas),
      req AS (SELECT arrayJoin(timeSlots(f, toUInt32(dateDiff('second',f,t)-60),60)) AS minute)
    SELECT round(avg(ifNull(c.concurrency,0)),2) FROM req m LEFT JOIN curve c USING (minute)")"
  printf '28\tindependent_locf_average\t%s\n' "$(q "
    WITH $_day, deltas AS (SELECT minute, sum(delta) AS d FROM concurrency_deltas WHERE minute < t GROUP BY minute),
      curve AS (SELECT 1 AS k, minute, toInt64(sum(d) OVER (ORDER BY minute)) AS concurrency FROM deltas),
      req AS (SELECT 1 AS k, arrayJoin(timeSlots(f, toUInt32(dateDiff('second',f,t)-60),60)) AS minute)
    SELECT round(avg(c.concurrency),2) FROM req m ASOF LEFT JOIN curve c ON m.k=c.k AND m.minute >= c.minute")"
  printf '28\tindependent_locf_denominator\t%s\n' "$(q "
    WITH $_day, deltas AS (SELECT minute, sum(delta) AS d FROM concurrency_deltas WHERE minute < t GROUP BY minute),
      curve AS (SELECT 1 AS k, minute, toInt64(sum(d) OVER (ORDER BY minute)) AS concurrency FROM deltas),
      req AS (SELECT 1 AS k, arrayJoin(timeSlots(f, toUInt32(dateDiff('second',f,t)-60),60)) AS minute)
    SELECT count() FROM req m ASOF LEFT JOIN curve c ON m.k=c.k AND m.minute >= c.minute")"

  # T29/T30. The retired dashboard path (a retired dashboard loaded the unbounded-fill query) against the
  # corrected serving/ path, same window. Both averages, one query each.
  _p=(--param_from_ts '2026-07-26 00:00:00' --param_to_ts '2026-07-27 00:00:00'
      --param_platform '' --param_country '' --param_video_type '' --param_app_version ''
      --param_content_id 0 --param_grain_s 86400)
  _bench="$(./scripts/ch.sh --format TSVRaw "${_p[@]}" --queries-file sql/queries/known-wrong/peak_average_no_densification.sql 2>/dev/null | head -1)"
  _serve="$(./scripts/ch.sh --format TSVRaw "${_p[@]}" --queries-file sql/queries/serving/peak_average.sql 2>/dev/null | head -1)"
  printf '30\tbenchmark_peak_average_sql_average\t%s\n' "$(echo "$_bench" | cut -f4)"
  printf '30\tserving_peak_average_sql_average\t%s\n'   "$(echo "$_serve" | cut -f4)"
  printf '30\tserving_denominator\t%s\n'                "$(echo "$_serve" | cut -f7)"
  _curve_out="$(./scripts/ch.sh --format TSVRaw --param_from_ts '2026-07-26 00:00:00' \
    --param_to_ts '2026-07-27 00:00:00' --param_platform '' --param_country '' --param_video_type '' \
    --param_app_version '' --param_content_id 0 --queries-file sql/queries/known-wrong/concurrency_unbounded_fill.sql 2>/dev/null)"
  printf '29\tbenchmark_concurrency_sql_first_minute\t%s\n' "$(echo "$_curve_out" | head -1 | cut -f1)"
  printf '29\tbenchmark_concurrency_sql_last_minute\t%s\n'  "$(echo "$_curve_out" | tail -1 | cut -f1)"
  printf '29\tbenchmark_concurrency_sql_rows\t%s\n'         "$(echo "$_curve_out" | wc -l | tr -d ' ')"
  printf '29\tbenchmark_concurrency_sql_average\t%s\n'      "$(echo "$_curve_out" | head -1 | cut -f5)"

  # T30b. All three candidate denominators, recorded every run so "all three measured, primary
  # labelled" (TASK.md 3.1) is a fact in evidence/ rather than a sentence in a document. Emitted as
  # definition=value:denominator so a reader cannot see an average without seeing what it divided by,
  # which is the entire failure mode this project has paid for twice.
  ./scripts/ch.sh --format TSVRaw --param_from_ts '2026-07-26 00:00:00' \
    --param_to_ts '2026-07-27 00:00:00' --param_platform '' --param_country '' --param_video_type '' \
    --param_app_version '' --param_content_id 0 \
    --queries-file sql/queries/serving/average_definitions.sql 2>/dev/null \
  | while IFS=$'\t' read -r _def _role _avg _den _; do
      printf '30b\taverage.%s\t%s over %s minutes (%s)\n' "$_def" "$_avg" "$_den" "$_role"
    done

  # T33. No platform/country aliasing exists. video_type carries an empty string, from the
  # deliberate LEFT JOIN that keeps playback whose content metadata is missing.
  printf '33\tvideo_types\t%s\n' "$(q "SELECT arrayStringConcat(arraySort(groupUniqArray(video_type)),'|') FROM concurrency_deltas WHERE minute < {frozen_before:String}")"
  printf '33\tcountries\t%s\n'   "$(q "SELECT arrayStringConcat(arraySort(groupUniqArray(country)),'|') FROM concurrency_deltas WHERE minute < {frozen_before:String}")"

  # T37. The serving query's own read budget, read back by query text across all replicas
  # because a --query_id lookup on one replica misses it. Confirms [V:filter_shapes]: only
  # concurrency_deltas, 26,904 rows. raw_events appears in no serving plan.
  printf '37\tserving_query_tables\t%s\n' "$(q "
    SELECT arrayStringConcat(arraySort(tables),',') FROM clusterAllReplicas(default, system.query_log)
    WHERE type='QueryFinish' AND has(tables,'phoenix.concurrency_deltas')
      AND query ILIKE '%ifNotFinite%' AND query NOT ILIKE '%clusterAllReplicas%'
    ORDER BY event_time DESC LIMIT 1")"
  printf '37\tserving_query_read_rows\t%s\n' "$(q "
    SELECT read_rows FROM clusterAllReplicas(default, system.query_log)
    WHERE type='QueryFinish' AND has(tables,'phoenix.concurrency_deltas')
      AND query ILIKE '%ifNotFinite%' AND query NOT ILIKE '%clusterAllReplicas%'
    ORDER BY event_time DESC LIMIT 1")"

  # T40. Both signs present: retractions are stored, not applied. Never count() this table.
  printf '40\tsign_negative_rows\t%s\n' "$(q "SELECT count() FROM session_minute_runs WHERE sign=-1")"
  printf '40\tsign_positive_rows\t%s\n' "$(q "SELECT count() FROM session_minute_runs WHERE sign=1")"

  # T47.
  printf '47\ttables_with_ttl\t%s\n' "$(q "
    SELECT countIf(position(create_table_query,'TTL')>0) FROM system.tables WHERE database=currentDatabase()
    AND name IN ('raw_events','foreground_intervals','session_minute_runs','concurrency_deltas')")"
} | evidence runbook_validation "every number in docs/review/validation_runbook_filled.md not already covered by an existing artifact"
