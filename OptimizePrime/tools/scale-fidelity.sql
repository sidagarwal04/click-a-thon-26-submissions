-- ============================================================================
-- tools/scale-fidelity.sql — real file vs synthetic stream, side by side.
--
-- > Summary: one row per shape metric the model actually reads, with the
-- > PROVIDED file in one column and the SYNTHETIC 1x stream in the other.
-- > `__R__` and `__S__` are substituted with the two database names by
-- > tools/scale-test.sh. Without this table the scale timings are
-- > unfalsifiable — a uniform random stream would measure nothing and would
-- > still produce a perfectly plausible table of milliseconds.
--
-- The metrics are chosen to be the ones the derivation reads, not decoration:
-- gaps >150 s (run splitting), pause/resume counts (pause windows), the
-- two-hour concentration (peak concurrency), events per session (per-session
-- array size), multi-valued audio (dominant-value attribution), and finally the
-- four numbers the model produces from them.
-- ============================================================================

-- The UNION ALL gets its own nesting level. `ORDER BY o` written directly
-- against a UNION binds to the LAST branch only, and the analyzer rejects it
-- outright (Code: 47, unknown identifier `o`).
SELECT concat('  ', rpad(metric, 40, ' '), lpad(real_v, 22, ' '), lpad(synth_v, 22, ' '))
FROM
(
  SELECT * FROM
  (
  SELECT 1 AS o, 'events'                          AS metric, toString((SELECT count() FROM __R__.ev_raw)) AS real_v, toString((SELECT count() FROM __S__.ev_raw)) AS synth_v
  UNION ALL SELECT 2, 'sessions',                  toString((SELECT uniqExact(video_session_id) FROM __R__.ev_raw)), toString((SELECT uniqExact(video_session_id) FROM __S__.ev_raw))
  UNION ALL SELECT 3, 'users',                     toString((SELECT uniqExact(user_id) FROM __R__.ev_raw)), toString((SELECT uniqExact(user_id) FROM __S__.ev_raw))
  UNION ALL SELECT 4, 'distinct content_id',       toString((SELECT uniqExact(content_id) FROM __R__.ev_raw)), toString((SELECT uniqExact(content_id) FROM __S__.ev_raw))
  UNION ALL SELECT 5, 'events/session  p50',       toString((SELECT quantileExact(0.5)(c) FROM (SELECT count() c FROM __R__.ev_raw GROUP BY video_session_id))), toString((SELECT quantileExact(0.5)(c) FROM (SELECT count() c FROM __S__.ev_raw GROUP BY video_session_id)))
  UNION ALL SELECT 6, 'events/session  mean',      toString(round((SELECT avg(c) FROM (SELECT count() c FROM __R__.ev_raw GROUP BY video_session_id)),1)), toString(round((SELECT avg(c) FROM (SELECT count() c FROM __S__.ev_raw GROUP BY video_session_id)),1))
  UNION ALL SELECT 7, 'events in the top 2 hours %', toString(round(100*(SELECT sum(c) FROM (SELECT count() c FROM __R__.ev_raw GROUP BY toStartOfHour(event_timestamp) ORDER BY c DESC LIMIT 2))/(SELECT count() FROM __R__.ev_raw),2)), toString(round(100*(SELECT sum(c) FROM (SELECT count() c FROM __S__.ev_raw GROUP BY toStartOfHour(event_timestamp) ORDER BY c DESC LIMIT 2))/(SELECT count() FROM __S__.ev_raw),2))
  UNION ALL SELECT 8, 'distinct hour buckets',     toString((SELECT uniqExact(toStartOfHour(event_timestamp)) FROM __R__.ev_raw)), toString((SELECT uniqExact(toStartOfHour(event_timestamp)) FROM __S__.ev_raw))
  UNION ALL SELECT 9, 'top content share of events %', toString(round(100*(SELECT max(c) FROM (SELECT count() c FROM __R__.ev_raw GROUP BY content_id))/(SELECT count() FROM __R__.ev_raw),2)), toString(round(100*(SELECT max(c) FROM (SELECT count() c FROM __S__.ev_raw GROUP BY content_id))/(SELECT count() FROM __S__.ev_raw),2))
  UNION ALL SELECT 10,'inter-arrival p50/p90/p99 s', (SELECT toString(quantilesExact(0.5,0.9,0.99)(x)) FROM (SELECT arrayJoin(arrayDifference(arraySort(groupArray(toUnixTimestamp(event_timestamp))))) x FROM __R__.ev_raw GROUP BY video_session_id)), (SELECT toString(quantilesExact(0.5,0.9,0.99)(x)) FROM (SELECT arrayJoin(arrayDifference(arraySort(groupArray(toUnixTimestamp(event_timestamp))))) x FROM __S__.ev_raw GROUP BY video_session_id))
  UNION ALL SELECT 11,'gaps > 150 s per session',  toString(round((SELECT avg(g) FROM (SELECT countIf(x>150) g FROM (SELECT video_session_id, arrayJoin(arrayDifference(arraySort(groupArray(toUnixTimestamp(event_timestamp))))) x FROM __R__.ev_raw GROUP BY video_session_id) GROUP BY video_session_id)),4)), toString(round((SELECT avg(g) FROM (SELECT countIf(x>150) g FROM (SELECT video_session_id, arrayJoin(arrayDifference(arraySort(groupArray(toUnixTimestamp(event_timestamp))))) x FROM __S__.ev_raw GROUP BY video_session_id) GROUP BY video_session_id)),4))
  UNION ALL SELECT 12,'pause events per session',  toString(round((SELECT countIf(event='pause')/uniqExact(video_session_id) FROM __R__.ev_raw),3)), toString(round((SELECT countIf(event='pause')/uniqExact(video_session_id) FROM __S__.ev_raw),3))
  UNION ALL SELECT 13,'resume events per session', toString(round((SELECT countIf(event='resume')/uniqExact(video_session_id) FROM __R__.ev_raw),3)), toString(round((SELECT countIf(event='resume')/uniqExact(video_session_id) FROM __S__.ev_raw),3))
  UNION ALL SELECT 14,'sessions with >1 audio value', toString((SELECT countIf(a>1) FROM (SELECT uniqExact(audio_language) a FROM __R__.ev_raw GROUP BY video_session_id))), toString((SELECT countIf(a>1) FROM (SELECT uniqExact(audio_language) a FROM __S__.ev_raw GROUP BY video_session_id)))
  UNION ALL SELECT 15,'distinct app_version',      toString((SELECT uniqExact(app_version) FROM __R__.ev_raw)), toString((SELECT uniqExact(app_version) FROM __S__.ev_raw))
  UNION ALL SELECT 16,'session span p50 / mean s', (SELECT concat(toString(quantileExact(0.5)(s)),' / ',toString(round(avg(s)))) FROM (SELECT dateDiff('second',min(event_timestamp),max(event_timestamp)) s FROM __R__.ev_raw GROUP BY video_session_id)), (SELECT concat(toString(quantileExact(0.5)(s)),' / ',toString(round(avg(s)))) FROM (SELECT dateDiff('second',min(event_timestamp),max(event_timestamp)) s FROM __S__.ev_raw GROUP BY video_session_id))
  UNION ALL SELECT 17,'--- derived by the MODEL ---','','' 
  UNION ALL SELECT 18,'session_intervals rows',    toString((SELECT count() FROM __R__.session_intervals FINAL)), toString((SELECT count() FROM __S__.session_intervals FINAL))
  UNION ALL SELECT 19,'counted watch hours',       toString(round((SELECT sum(dateDiff('second',interval_start,interval_end))/3600 FROM __R__.session_intervals FINAL),1)), toString(round((SELECT sum(dateDiff('second',interval_start,interval_end))/3600 FROM __S__.session_intervals FINAL),1))
  UNION ALL SELECT 20,'PEAK concurrency',          toString((SELECT max(concurrent) FROM __R__.v_concurrency_minute_delta_total)), toString((SELECT max(concurrent) FROM __S__.v_concurrency_minute_delta_total))
  UNION ALL SELECT 21,'cc_minute_delta rows',      toString((SELECT count() FROM __R__.cc_minute_delta)), toString((SELECT count() FROM __S__.cc_minute_delta))
  UNION ALL SELECT 22,'  ... as % of the ADR 0008 ceiling', toString(round(100*(SELECT count() FROM __R__.cc_minute_delta)/(SELECT sum(starts)+sum(ends) FROM __R__.cc_minute_delta),1)), toString(round(100*(SELECT count() FROM __S__.cc_minute_delta)/(SELECT sum(starts)+sum(ends) FROM __S__.cc_minute_delta),1))
  )
  ORDER BY o
)
FORMAT TSVRaw
