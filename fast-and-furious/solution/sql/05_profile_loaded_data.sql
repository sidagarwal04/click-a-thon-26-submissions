-- Reproducible evidence profile after ingestion. These are read-only and have
-- explicit limits; capture the result with query_id/log_comment in the run bundle.

-- Population and range.
SELECT
    count() AS raw_rows,
    uniqExact(video_session_id) AS sessions,
    uniqExact(user_id) AS event_user_ids,
    uniqExact(content_id) AS used_content_ids,
    min(event_time) AS min_event_time,
    max(event_time) AS max_event_time
FROM sonyliv.raw_events
SETTINGS max_execution_time = 30, max_rows_to_read = 2000000;

-- Calendar-date sensitivity is evidence for keeping service dates explicitly
-- UTC. Asia/Kolkata is a query-time projection only; it is never persisted.
SELECT
    countIf(toDate(event_time, 'UTC') != toDate(event_time, 'Asia/Kolkata'))
        AS event_rows_with_different_ist_date,
    uniqExactIf(
        video_session_id,
        toDate(event_time, 'UTC') != toDate(event_time, 'Asia/Kolkata')
    ) AS sessions_with_different_ist_event_date,
    uniqExactIf(
        video_session_id,
        event_type = 'VideoSessionStart'
        AND toDate(event_time, 'UTC') != toDate(event_time, 'Asia/Kolkata')
    ) AS session_starts_with_different_ist_date
FROM sonyliv.raw_events
SETTINGS max_execution_time = 30, max_rows_to_read = 2000000;

SELECT event_type, count() AS rows
FROM sonyliv.raw_events
GROUP BY event_type
ORDER BY rows DESC
LIMIT 100;

-- Duplicate excess. Exact full-payload fingerprints and semantic event keys are
-- deliberately different checks.
SELECT
    sum(greatest(c - 1, 0)) AS exact_duplicate_excess,
    countIf(c > 1) AS exact_duplicate_groups,
    max(c) AS maximum_multiplicity
FROM
(
    SELECT source_row_hash, count() AS c
    FROM sonyliv.raw_events
    GROUP BY source_row_hash
);

SELECT sum(greatest(c - 1, 0)) AS semantic_key_duplicate_excess
FROM
(
    SELECT
        video_session_id,
        event_time,
        event_type,
        event,
        count() AS c
    FROM sonyliv.raw_events
    GROUP BY video_session_id, event_time, event_type, event
);

-- Rows/session and lifecycle duration prove touched-session recomputation is
-- bounded while cross-day handling is required.
WITH per_session AS
(
    SELECT
        video_session_id,
        count() AS rows,
        minIf(event_time, event_type = 'VideoSessionStart') AS start_time,
        minIf(event_time, event_type = 'VideoSessionEnd') AS first_end_time,
        countIf(event_type = 'VideoSessionEnd') AS end_rows
    FROM sonyliv.raw_events
    GROUP BY video_session_id
)
SELECT
    quantilesExact(0.5, 0.9, 0.99)(rows) AS rows_per_session_p50_p90_p99,
    max(rows) AS max_rows_per_session,
    quantilesExact(0.5, 0.9, 0.99)(dateDiff('millisecond', start_time, first_end_time) / 1000.0)
        AS duration_seconds_p50_p90_p99,
    max(dateDiff('millisecond', start_time, first_end_time) / 1000.0) AS max_duration_seconds,
    countIf(end_rows = 0) AS no_end_sessions,
    countIf(end_rows > 1) AS multiple_end_row_sessions
FROM per_session;

-- Physical CSV/replay order is not event-time order. ingest_version preserves
-- the streamed file order for this deterministic backfill. It is not a real
-- arrival timestamp and must not be used to pick a production watermark.
WITH ordered AS
(
    SELECT
        video_session_id,
        event_time,
        max(event_time) OVER
        (
            PARTITION BY video_session_id
            ORDER BY ingested_at, ingest_batch_id, ingest_version
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS prior_event_time_max
    FROM sonyliv.raw_events
), late AS
(
    SELECT dateDiff('millisecond', event_time, prior_event_time_max) AS lag_ms
    FROM ordered
    WHERE event_time < prior_event_time_max
)
SELECT
    count() AS behind_prior_session_max_rows,
    quantilesExact(0.5, 0.9, 0.95, 0.99, 0.999)(lag_ms / 1000.0) AS lag_seconds,
    max(lag_ms / 1000.0) AS max_lag_seconds
FROM late;

-- Recurring liveness signal cadence.
WITH periodic AS
(
    SELECT
        video_session_id,
        event_time,
        lagInFrame(event_time, 1, event_time) OVER
        (
            PARTITION BY video_session_id
            ORDER BY event_time
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS previous_time
    FROM sonyliv.raw_events
    WHERE event_type = 'VideoHeartbeat'
      AND event = 'network-activity'
)
SELECT
    countIf(event_time > previous_time) AS measured_gaps,
    quantilesExactIf(0.5, 0.9, 0.95, 0.99)(
        dateDiff('millisecond', previous_time, event_time) / 1000.0,
        event_time > previous_time
    ) AS gap_seconds_p50_p90_p95_p99
FROM periodic;

-- Dimension cardinality and content coverage.
SELECT
    uniqExact(platform) AS platforms,
    uniqExact(app_version) AS app_versions,
    uniqExact(country) AS countries,
    uniqExact(audio_language) AS audio_languages,
    uniqExact(subtitle_language) AS subtitle_languages,
    uniqExact(player_version) AS player_versions,
    uniqExact(event) AS event_values
FROM sonyliv.raw_events;

SELECT
    count() AS content_rows,
    uniqExact(content_id) AS unique_content_ids,
    min(content_id) AS min_content_id,
    max(content_id) AS max_content_id,
    countIf(empty(video_type) OR video_type = '__unknown__') AS unknown_video_type_rows
FROM sonyliv.content_dim;

SELECT count() AS missing_content_ids
FROM
(
    SELECT DISTINCT content_id FROM sonyliv.raw_events
) AS r
LEFT ANTI JOIN sonyliv.content_dim AS c USING (content_id);

-- Static dimension drift versus the first SessionStart anchor.
WITH anchors AS
(
    SELECT
        video_session_id,
        argMinIf(user_id, event_time, event_type = 'VideoSessionStart') AS start_user,
        argMinIf(content_id, event_time, event_type = 'VideoSessionStart') AS start_content,
        argMinIf(platform, event_time, event_type = 'VideoSessionStart') AS start_platform,
        argMinIf(app_version, event_time, event_type = 'VideoSessionStart') AS start_app_version,
        argMinIf(country, event_time, event_type = 'VideoSessionStart') AS start_country
    FROM sonyliv.raw_events
    GROUP BY video_session_id
)
SELECT
    uniqExactIf(r.video_session_id, r.user_id != a.start_user) AS user_drift_sessions,
    uniqExactIf(r.video_session_id, r.content_id != a.start_content) AS content_drift_sessions,
    uniqExactIf(r.video_session_id, r.platform != a.start_platform) AS platform_drift_sessions,
    uniqExactIf(r.video_session_id, r.app_version != a.start_app_version) AS app_version_drift_sessions,
    uniqExactIf(r.video_session_id, r.country != a.start_country) AS country_drift_sessions
FROM sonyliv.raw_events AS r
INNER JOIN anchors AS a USING (video_session_id);

-- Canonical session users versus user concurrency risk.
WITH session_users AS
(
    SELECT
        video_session_id,
        argMinIf(user_id, event_time, event_type = 'VideoSessionStart') AS canonical_user_id,
        minIf(event_time, event_type = 'VideoSessionStart') AS start_time,
        minIf(event_time, event_type = 'VideoSessionEnd') AS end_time
    FROM sonyliv.raw_events
    GROUP BY video_session_id
    HAVING countIf(event_type = 'VideoSessionStart') > 0
)
SELECT
    uniqExact(canonical_user_id) AS canonical_users,
    countIf(session_count > 1) AS users_with_multiple_sessions
FROM
(
    SELECT canonical_user_id, count() AS session_count
    FROM session_users
    GROUP BY canonical_user_id
);
