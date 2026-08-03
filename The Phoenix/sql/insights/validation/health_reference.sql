-- REFERENCE for playback_health_minute.
--
-- Recomputed from raw_events and foreground_intervals, not from session_insight_facts or
-- audience_minute_snapshot, which is what the pipeline reads. Error sessions come straight from
-- the event stream; timeouts and abandonment are re-derived from the interval table and the
-- presence of a VideoSessionEnd, rather than from the flags the facts table stores.
--
-- active_sessions IS deliberately excluded from this comparison. It is copied verbatim from
-- audience_minute_snapshot, which has its own gate against the authoritative concurrency curve
-- `[V:insight_parity_audience_snapshot]`, and re-deriving it here would only re-test that. The
-- rates are excluded for the same reason they are in the cohorts pair: they are the counts
-- divided by that denominator, so if the counts and the denominator both hold, the rates cannot
-- disagree, and comparing two Float32 renderings invites a formatting failure.
--
-- Composite first column, because the harness diffs on field one.
WITH
    iv AS
    (
        SELECT video_session_id AS sid,
               max(interval_end) AS last_active_at,
               argMax(dateDiff('second', interval_start, interval_end), interval_start) AS last_len
        FROM foreground_intervals
        GROUP BY video_session_id
    ),
    ev AS
    (
        SELECT video_session_id AS sid,
               argMin(content_id, event_timestamp)  AS content_id,
               argMin(platform, event_timestamp)    AS platform,
               argMin(country, event_timestamp)     AS country,
               argMin(app_version, event_timestamp) AS app_version,
               max(if(event_type = 'VideoSessionEnd', event_timestamp, toDateTime64(0, 3))) AS last_end
        FROM raw_events
        GROUP BY video_session_id
    ),
    sess AS
    (
        SELECT iv.sid AS sid, iv.last_active_at AS last_active_at,
               ev.content_id AS content_id, ev.platform AS platform, ev.country AS country,
               ev.app_version AS app_version, ifNull(c.video_type, '') AS video_type,
               toUInt8(iv.last_len = toInt64({tolerance_s:UInt32})) AS timed_out,
               toUInt8(ev.last_end = toDateTime64(0, 3))            AS abandoned
        FROM iv
        INNER JOIN ev ON ev.sid = iv.sid
        -- LEFT ANY JOIN, not LEFT JOIN, per clickhouse-best-practices rule query-join-use-any. This is a
        -- one-row-per-key lookup, and `content` is a ReplacingMergeTree: duplicate content_id rows exist
        -- between a reload and the merge that collapses them, and a plain LEFT JOIN would fan out and
        -- multiply every row that matched. Measured 0 duplicates today, so this closes a latent hazard
        -- rather than a live defect.
        LEFT ANY JOIN content AS c ON c.content_id = ev.content_id
    ),
    errs AS
    (
        SELECT toStartOfMinute(toDateTime(r.event_timestamp)) AS minute,
               s.content_id AS content_id, s.platform AS platform, s.country AS country,
               s.app_version AS app_version, s.video_type AS video_type,
               uniqExact(r.video_session_id) AS video_error_sessions
        FROM raw_events AS r
        INNER JOIN sess AS s ON s.sid = r.video_session_id
        WHERE r.event_type = 'VideoError' AND r.event_timestamp < {frozen_before:String}
        GROUP BY minute, content_id, platform, country, app_version, video_type
    ),
    outs AS
    (
        SELECT toStartOfMinute(last_active_at) AS minute,
               content_id, platform, country, app_version, video_type,
               toUInt32(countIf(timed_out = 1)) AS heartbeat_timeout_sessions,
               toUInt32(countIf(abandoned = 1)) AS abandoned_sessions
        FROM sess
        WHERE last_active_at > toDateTime(0) AND last_active_at < {frozen_before:String}
        GROUP BY minute, content_id, platform, country, app_version, video_type
    ),
    keys AS
    (
        SELECT minute, content_id, platform, country, app_version, video_type FROM errs
        UNION DISTINCT
        SELECT minute, content_id, platform, country, app_version, video_type FROM outs
    )
SELECT
    concat(toString(k.minute), '|', toString(k.content_id), '|', k.platform, '|', k.country,
           '|', k.app_version, '|', k.video_type) AS health_key,
    toUInt32(ifNull(e.video_error_sessions, 0))       AS video_error_sessions,
    toUInt32(ifNull(o.heartbeat_timeout_sessions, 0)) AS heartbeat_timeout_sessions,
    toUInt32(ifNull(o.abandoned_sessions, 0))         AS abandoned_sessions
FROM keys AS k
LEFT JOIN errs AS e USING (minute, content_id, platform, country, app_version, video_type)
LEFT JOIN outs AS o USING (minute, content_id, platform, country, app_version, video_type)
-- The same all-zero filter the optimized side applies, and it has to be here too. `outs` groups
-- every session's last active minute, so it emits a row for each ordinary session ending
-- normally and on time, with all three counts zero. Without this the reference carries 8,543
-- rows against the optimized side's 296 and reports 8,247 missing keys, none of which is a
-- disagreement about a number: both sides say zero, one of them just says it out loud.
WHERE ifNull(e.video_error_sessions, 0) > 0
   OR ifNull(o.heartbeat_timeout_sessions, 0) > 0
   OR ifNull(o.abandoned_sessions, 0) > 0
ORDER BY health_key;
