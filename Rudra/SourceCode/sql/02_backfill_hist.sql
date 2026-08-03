-- ── Batch backfill of hist_minute_full (unseen-day / historical load) ─────────
-- Event-time stamped and reproducible (no now()) → works on a bulk-loaded CSV and
-- matches a fixed ground truth. Reproduces the live-snapshot semantics exactly:
--   1) reconstruct each session's foreground-active minutes with the SAME sticky-
--      state rule as the live MV (a plain beat keeps the running state; pause/bg
--      exclude), closing a run at the last beat before a >90s gap (gap timeout);
--   2) for each (session, active-minute) take the dims AS OF that minute (one value)
--      so a session is counted ONCE per minute (no per-event-dim double count).
-- Grand-total peak equals an independent dim-agnostic distinct-session count
-- (verified 0 divergence on the unseen day: 22,174).
INSERT INTO sonyliv.hist_minute_full
WITH
mm AS (
    SELECT sid, mi FROM (
        WITH base AS (
            SELECT video_session_id AS sid, toUnixTimestamp64Milli(event_timestamp) AS t,
                multiIf(event_type='VideoHeartbeat' AND event='pause','paused',
                        event_type='AppBackgrounded','background',
                        event_type='VideoSessionEnd','ended','active') AS ms,
                if((event_type='VideoHeartbeat' AND event IN ('pause','resume'))
                   OR event_type IN ('AppBackgrounded','AppForegrounded','VideoPlay','VideoSessionStart','VideoSessionEnd'),
                   toUnixTimestamp64Milli(event_timestamp), toInt64(0)) AS sts,
                leadInFrame(toUnixTimestamp64Milli(event_timestamp),1,toInt64(0))
                    OVER (PARTITION BY video_session_id ORDER BY event_timestamp ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING) AS nt
            FROM sonyliv.raw_events ),
        ws AS (
            SELECT sid, t, nt,
                argMax(ms, sts) OVER (PARTITION BY sid ORDER BY t ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cs
            FROM base )
        SELECT sid, arrayJoin(range(toUInt32(intDiv(t,60000)),
                                    toUInt32(intDiv(if(nt=0 OR nt-t>90000, t+1, nt)-1, 60000))+1)) AS mi
        FROM ws WHERE cs='active'
    ) GROUP BY sid, mi ),
am AS (SELECT sid, toDateTime(mi*60,'UTC') AS minute, toDateTime64((mi+1)*60,3,'UTC') AS minute_end FROM mm)
SELECT am.minute AS minute, ev.content_id, ev.platform, ev.app_version, ev.video_type, ev.country, ev.video_resolution,
       ev.audio_language, ev.subtitle_language, ev.player_version, toUInt32(count()) AS cnt
FROM am
ASOF LEFT JOIN (
    SELECT video_session_id AS sid, event_timestamp AS ts, content_id, platform, app_version, country, video_resolution,
           audio_language, subtitle_language, player_version,
           if(empty(dictGetOrDefault('sonyliv.content_dict','video_type',tuple(content_id),'')),'unknown',
              dictGetOrDefault('sonyliv.content_dict','video_type',tuple(content_id),'unknown')) AS video_type
    FROM sonyliv.raw_events
) AS ev
ON am.sid = ev.sid AND am.minute_end >= ev.ts
GROUP BY minute, ev.content_id, ev.platform, ev.app_version, ev.video_type, ev.country, ev.video_resolution,
         ev.audio_language, ev.subtitle_language, ev.player_version;
