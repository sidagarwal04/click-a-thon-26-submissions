-- Session-independent comparison path, intentionally not the benchmark answer.
--
-- For each minute boundary M, estimate sessions with any qualifying heartbeat
-- signal in (M-timeout, M]. This ignores the ordered pause/background state that
-- the true model applies, and uniqCombined64 is approximate. The difference from
-- exact session concurrency is a useful overcount/telemetry drift monitor.

INSERT INTO sonyliv.heartbeat_lease_minute_states
WITH
    {service_date:Date} AS selected_date,
    toDateTime64(selected_date, 3, 'UTC') AS day_start,
    toDateTime64(addDays(selected_date, 1), 3, 'UTC') AS day_end,
    toUnixTimestamp64Milli(day_start) AS day_start_ms,
    toUnixTimestamp64Milli(day_end) AS day_end_ms,
    {heartbeat_timeout_ms:UInt64} AS timeout_ms,

    liveness_events AS
    (
        SELECT
            video_session_id,
            event_time,
            toUnixTimestamp64Milli(event_time) AS event_ms,
            platform,
            country,
            content_id,
            if(
                empty(dictGetOrDefault('sonyliv.content_dictionary', 'video_type', content_id, '__unknown__')),
                '__unknown__',
                dictGetOrDefault('sonyliv.content_dictionary', 'video_type', content_id, '__unknown__')
            ) AS video_type
        FROM sonyliv.raw_events
        WHERE event_time < day_end
          AND event_time + toIntervalMillisecond(timeout_ms) > day_start
          AND
          (
              event_type = 'VideoPlay'
              OR (event_type = 'VideoHeartbeat' AND event != 'pause')
          )
    ),

    boundary_coverage AS
    (
        SELECT
            video_session_id,
            platform,
            country,
            content_id,
            video_type,
            boundary_number,
            boundary_number * 60000 AS boundary_ms
        FROM liveness_events
        ARRAY JOIN range(
            toUInt64(intDiv(event_ms + 59999, 60000)),
            toUInt64(intDiv(event_ms + toInt64(timeout_ms) - 1, 60000) + 1)
        ) AS boundary_number
        WHERE boundary_ms >= day_start_ms
          AND boundary_ms < day_end_ms
    )

SELECT
    {generation:UInt64} AS generation,
    selected_date AS service_date,
    fromUnixTimestamp64Milli(toInt64(boundary_ms), 'UTC') AS minute_start,
    platform,
    country,
    video_type,
    content_id,
    uniqCombined64State(video_session_id) AS active_sessions
FROM boundary_coverage
GROUP BY
    minute_start,
    platform,
    country,
    video_type,
    content_id;

-- Global minute-boundary comparison against exact signed deltas.
WITH
    {service_date:Date} AS selected_date,
    toDateTime64(selected_date, 3, 'UTC') AS day_start,
    toDateTime64(addDays(selected_date, 1), 3, 'UTC') AS day_end,

    minute_spine AS
    (
        SELECT day_start + toIntervalMinute(number) AS minute_start
        FROM numbers(1440)
    ),

    baseline AS
    (
        SELECT
            minute_start,
            uniqCombined64Merge(active_sessions) AS heartbeat_lease_sessions
        FROM sonyliv.heartbeat_lease_minute_states
        WHERE generation = {generation:UInt64}
          AND service_date = selected_date
        GROUP BY minute_start
    ),

    exact_points AS
    (
        SELECT boundary_time, sum(delta) AS d
        FROM sonyliv.concurrency_delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND entity = 'session'
          AND rollup_mask = 0
          AND service_date = selected_date
          AND boundary_time < day_end
        GROUP BY boundary_time
    ),

    exact_at_boundary AS
    (
        SELECT
            m.minute_start,
            sumIf(p.d, p.boundary_time <= m.minute_start) AS exact_sessions
        FROM minute_spine AS m
        CROSS JOIN exact_points AS p
        GROUP BY m.minute_start
    )

SELECT
    e.minute_start,
    e.exact_sessions,
    coalesce(b.heartbeat_lease_sessions, toUInt64(0)) AS heartbeat_lease_sessions,
    toInt64(heartbeat_lease_sessions) - e.exact_sessions AS overcount
FROM exact_at_boundary AS e
LEFT ANY JOIN baseline AS b USING (minute_start)
WHERE e.exact_sessions != 0 OR heartbeat_lease_sessions != 0
ORDER BY e.minute_start
SETTINGS
    join_use_nulls = 0,
    max_execution_time = 30,
    max_rows_to_read = 100000000,
    max_result_rows = 2000;
