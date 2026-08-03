-- Exact, event-time reference interval builder.
--
-- Run with query parameters, for example:
--   clickhouse-client \
--     --param_policy_version=sonyliv-active-v1 \
--     --param_oracle_run_id=... \
--     --param_full_scan=1 \
--     --param_heartbeat_timeout_ms=120000 \
--     --param_evaluation_as_of='2026-07-26 11:32:04.847' \
--     --multiquery < solution/sql/10_reference_intervals.sql
--
-- This is both the initial backfill and the independent correctness oracle. The
-- production hot path runs the same state derivation only for touched session
-- IDs, compares its new boundary map with argMax(previous map, revision), and
-- publishes the difference. Do not attach this query directly to raw_events as
-- an incremental MV: an incremental MV sees only its inserted block.

SELECT throwIf(
    {full_scan:UInt8} = 1
    AND
    (
        (
            SELECT count()
            FROM sonyliv.oracle_run_manifests
            WHERE oracle_run_id = {oracle_run_id:UUID}
              AND pipeline_run_id = {pipeline_run_id:UUID}
              AND policy_version = {policy_version:String}
        ) > 0
        OR
        (
            SELECT count()
            FROM sonyliv.active_intervals_reference
            WHERE oracle_run_id = {oracle_run_id:UUID}
              AND policy_version = {policy_version:String}
        ) > 0
    ),
    'full-scan oracle ID is committed or has orphan rows; allocate a new run ID'
);

INSERT INTO sonyliv.active_intervals_reference
(
    oracle_run_id,
    policy_version,
    session_start_date,
    video_session_id,
    canonical_user_id,
    interval_index,
    start_time,
    end_time,
    content_id,
    platform,
    country,
    video_type
)
WITH
    {heartbeat_timeout_ms:UInt64} AS heartbeat_timeout_ms,
    toDateTime64({evaluation_as_of:String}, 3, 'UTC') AS evaluation_as_of,

    deduplicated_events AS
    (
        -- The supplied file has 4,209 excess exact rows. The semantic key below
        -- removes one additional conflicting payload row while retaining every
        -- legitimate same-millisecond event combination.
        SELECT
            video_session_id,
            event_time,
            event_type,
            event,
            argMax(user_id, tuple(ingested_at, ingest_batch_id, ingest_version, source_row_hash)) AS user_id,
            argMax(content_id, tuple(ingested_at, ingest_batch_id, ingest_version, source_row_hash)) AS content_id,
            argMax(platform, tuple(ingested_at, ingest_batch_id, ingest_version, source_row_hash)) AS platform,
            argMax(app_version, tuple(ingested_at, ingest_batch_id, ingest_version, source_row_hash)) AS app_version,
            argMax(country, tuple(ingested_at, ingest_batch_id, ingest_version, source_row_hash)) AS country,
            argMax(source_row_hash, tuple(ingested_at, ingest_batch_id, ingest_version, source_row_hash))
                AS selected_source_row_hash
        FROM sonyliv.raw_events
        WHERE event_time <= evaluation_as_of
          AND
          (
              {full_scan:UInt8} = 1
              OR video_session_id IN
              (
                  SELECT video_session_id
                  FROM sonyliv.compaction_worksets
                  WHERE pipeline_run_id = {pipeline_run_id:UUID}
                    AND policy_version = {policy_version:String}
                    AND adjustment_batch_id = {workset_batch_id:UUID}
              )
          )
        GROUP BY
            video_session_id,
            event_time,
            event_type,
            event
    ),

    session_anchors AS
    (
        SELECT
            video_session_id,
            minIf(event_time, event_type = 'VideoSessionStart') AS lifecycle_start_time,
            minIf(event_time, event_type = 'VideoSessionEnd') AS terminal_end_time,
            countIf(event_type = 'VideoSessionEnd') > 0 AS has_terminal_end,

            argMinIf(
                user_id,
                tuple(event_time, selected_source_row_hash),
                event_type = 'VideoSessionStart'
            ) AS canonical_user_id,
            argMinIf(
                content_id,
                tuple(event_time, selected_source_row_hash),
                event_type = 'VideoSessionStart'
            ) AS content_id,
            argMinIf(
                platform,
                tuple(event_time, selected_source_row_hash),
                event_type = 'VideoSessionStart'
            ) AS platform,
            argMinIf(
                app_version,
                tuple(event_time, selected_source_row_hash),
                event_type = 'VideoSessionStart'
            ) AS app_version,
            argMinIf(
                country,
                tuple(event_time, selected_source_row_hash),
                event_type = 'VideoSessionStart'
            ) AS country
        FROM deduplicated_events
        GROUP BY video_session_id
        HAVING countIf(event_type = 'VideoSessionStart') > 0
    ),

    events_through_first_end AS
    (
        SELECT
            e.*,
            a.lifecycle_start_time,
            a.terminal_end_time,
            a.has_terminal_end,
            a.canonical_user_id,
            a.content_id AS canonical_content_id,
            a.platform AS canonical_platform,
            a.app_version AS canonical_app_version,
            a.country AS canonical_country
        FROM deduplicated_events AS e
        INNER JOIN session_anchors AS a USING (video_session_id)
        WHERE e.event_time >= a.lifecycle_start_time
          AND (NOT a.has_terminal_end OR e.event_time <= a.terminal_end_time)
          -- `start_choice: first`: a later distinct SessionStart is retained in
          -- raw storage but cannot reset either lifecycle state axis.
          AND
          (
              e.event_type != 'VideoSessionStart'
              OR e.event_time = a.lifecycle_start_time
          )
    ),

    same_timestamp_assignments AS
    (
        -- There is no source sequence within a millisecond. Collapse all events
        -- at a timestamp and apply deterministic stop-wins precedence.
        SELECT
            video_session_id,
            event_time,
            any(lifecycle_start_time) AS lifecycle_start_time,
            any(terminal_end_time) AS terminal_end_time,
            any(has_terminal_end) AS has_terminal_end,
            any(canonical_user_id) AS canonical_user_id,
            any(canonical_content_id) AS content_id,
            any(canonical_platform) AS platform,
            any(canonical_app_version) AS app_version,
            any(canonical_country) AS country,

            max(event_type = 'VideoSessionStart') AS has_start,
            max(event_type = 'VideoSessionEnd') AS has_end,
            max(event_type = 'AppBackgrounded') AS has_background,
            max(event_type = 'AppForegrounded') AS has_foreground,
            max(event_type = 'VideoError' OR (event_type = 'VideoHeartbeat' AND event = 'pause')) AS has_play_stop,
            max(event_type = 'VideoPlay' OR (event_type = 'VideoHeartbeat' AND event = 'resume')) AS has_play_start,
            max(
                event_type = 'VideoPlay'
                OR (event_type = 'VideoHeartbeat' AND event != 'pause')
            ) AS has_liveness_signal
        FROM events_through_first_end
        GROUP BY video_session_id, event_time
    ),

    setters AS
    (
        SELECT
            *,
            multiIf(
                has_end OR has_background, toInt8(-1),
                has_start OR has_foreground, toInt8(1),
                toInt8(0)
            ) AS foreground_setter,
            multiIf(
                has_end OR has_play_stop, toInt8(-1),
                has_play_start, toInt8(1),
                toInt8(0)
            ) AS playing_setter
        FROM same_timestamp_assignments
    ),

    state_after_assignment AS
    (
        SELECT
            *,
            max(has_start) OVER state_window AS lifecycle_started,
            max(has_end) OVER state_window AS terminal_end_seen,
            argMaxIf(foreground_setter, event_time, foreground_setter != 0)
                OVER state_window AS foreground_state,
            argMaxIf(playing_setter, event_time, playing_setter != 0)
                OVER state_window AS playing_state
        FROM setters
        WINDOW state_window AS
        (
            PARTITION BY video_session_id
            ORDER BY event_time
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
    ),

    eligible_signals AS
    (
        SELECT
            *,
            has_liveness_signal
                AND lifecycle_started = 1
                AND terminal_end_seen = 0
                AND foreground_state = 1
                AND playing_state = 1 AS is_eligible_signal
        FROM state_after_assignment
    ),

    leased_state AS
    (
        SELECT
            *,
            maxIf(event_time, is_eligible_signal) OVER state_window AS last_eligible_signal,
            leadInFrame(
                event_time,
                1,
                evaluation_as_of + toIntervalMillisecond(heartbeat_timeout_ms)
            ) OVER full_window AS next_event_time
        FROM eligible_signals
        WINDOW
            state_window AS
            (
                PARTITION BY video_session_id
                ORDER BY event_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ),
            full_window AS
            (
                PARTITION BY video_session_id
                ORDER BY event_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
    ),

    candidate_segments AS
    (
        SELECT
            video_session_id,
            canonical_user_id,
            lifecycle_start_time,
            content_id,
            platform,
            country,
            event_time AS start_time,
            least(
                next_event_time,
                last_eligible_signal + toIntervalMillisecond(heartbeat_timeout_ms)
            ) AS end_time
        FROM leased_state
        WHERE lifecycle_started = 1
          AND terminal_end_seen = 0
          AND foreground_state = 1
          AND playing_state = 1
          AND last_eligible_signal > toDateTime64(0, 3, 'UTC')
          AND event_time < last_eligible_signal + toIntervalMillisecond(heartbeat_timeout_ms)
    ),

    nonempty_segments AS
    (
        SELECT *
        FROM candidate_segments
        WHERE end_time > start_time
    ),

    marked_islands AS
    (
        SELECT
            *,
            start_time > max(end_time) OVER
            (
                PARTITION BY video_session_id
                ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS starts_new_island
        FROM nonempty_segments
    ),

    numbered_islands AS
    (
        SELECT
            *,
            sum(starts_new_island) OVER
            (
                PARTITION BY video_session_id
                ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS island_number
        FROM marked_islands
    ),

    normalized_intervals AS
    (
        SELECT
            video_session_id,
            any(canonical_user_id) AS canonical_user_id,
            any(lifecycle_start_time) AS lifecycle_start_time,
            any(content_id) AS content_id,
            any(platform) AS platform,
            any(country) AS country,
            island_number,
            min(start_time) AS start_time,
            max(end_time) AS end_time
        FROM numbered_islands
        GROUP BY video_session_id, island_number
    )

SELECT
    {oracle_run_id:UUID} AS oracle_run_id,
    {policy_version:String} AS policy_version,
    toDate(lifecycle_start_time, 'UTC') AS session_start_date,
    video_session_id,
    canonical_user_id,
    toUInt32(row_number() OVER (PARTITION BY video_session_id ORDER BY start_time, end_time)) AS interval_index,
    start_time,
    end_time,
    content_id,
    platform,
    country,
    if(
        empty(dictGetOrDefault('sonyliv.content_dictionary', 'video_type', content_id, '__unknown__')),
        '__unknown__',
        dictGetOrDefault('sonyliv.content_dictionary', 'video_type', content_id, '__unknown__')
    ) AS video_type
FROM normalized_intervals
WHERE end_time > start_time
SETTINGS insert_deduplication_token = {oracle_insert_dedup_token:String};

-- The completion marker is intentionally in this same multiquery and uses the
-- same full_scan parameter as the interval INSERT above. A scoped hot-path run
-- cannot be relabelled later as an independent publication oracle.
INSERT INTO sonyliv.oracle_run_manifests
WITH
    deduplicated_events AS
    (
        SELECT
            video_session_id,
            event_time,
            event_type,
            event
        FROM sonyliv.raw_events
        WHERE event_time <= toDateTime64({evaluation_as_of:String}, 3, 'UTC')
        GROUP BY video_session_id, event_time, event_type, event
    ),
    expected AS
    (
        SELECT count() AS expected_anchored_sessions
        FROM
        (
            SELECT video_session_id
            FROM deduplicated_events
            GROUP BY video_session_id
            HAVING countIf(event_type = 'VideoSessionStart') > 0
        )
    ),
    oracle_rows AS
    (
        SELECT
            video_session_id,
            interval_index,
            start_time,
            end_time,
            concat(
                video_session_id, canonical_user_id, ';',
                toString(interval_index), ';',
                toString(toUnixTimestamp64Milli(start_time)), ';',
                toString(toUnixTimestamp64Milli(end_time)), ';',
                toString(content_id), ';',
                toString(length(platform)), ':', platform,
                toString(length(country)), ':', country,
                toString(length(video_type)), ':', video_type
            ) AS canonical_row
        FROM sonyliv.active_intervals_reference
        WHERE oracle_run_id = {oracle_run_id:UUID}
          AND policy_version = {policy_version:String}
    ),
    oracle_summary AS
    (
        SELECT
            uniqExact(video_session_id) AS active_sessions,
            count() AS interval_rows,
            hex(
                SHA256(
                    arrayStringConcat(
                        arrayMap(
                            item -> item.2,
                            arraySort(groupArray((
                                tuple(video_session_id, start_time, end_time, interval_index),
                                canonical_row
                            )))
                        ),
                        ''
                    )
                )
            ) AS interval_hash
        FROM oracle_rows
    ),
    payload AS
    (
        SELECT
            {oracle_run_id:UUID} AS oracle_run_id,
            {pipeline_run_id:UUID} AS pipeline_run_id,
            {policy_version:String} AS policy_version,
            {source_snapshot_hash:String} AS source_snapshot_hash,
            toBool({full_scan:UInt8}) AS is_full_scan,
            toDateTime64({evaluation_as_of:String}, 3, 'UTC') AS evaluation_as_of,
            {heartbeat_timeout_ms:UInt64} AS heartbeat_timeout_ms,
            expected.expected_anchored_sessions,
            oracle_summary.active_sessions,
            oracle_summary.interval_rows,
            oracle_summary.interval_hash
        FROM expected
        CROSS JOIN oracle_summary
        WHERE {full_scan:UInt8} = 1
    )
SELECT
    *,
    hex(SHA256(concat(
        toString(oracle_run_id), ';', toString(pipeline_run_id), ';',
        toString(length(policy_version)), ':', policy_version,
        source_snapshot_hash, toString(is_full_scan), ';',
        toString(toUnixTimestamp64Milli(evaluation_as_of)), ';',
        toString(heartbeat_timeout_ms), ';',
        toString(expected_anchored_sessions), ';', toString(active_sessions), ';',
        toString(interval_rows), ';', interval_hash
    ))) AS manifest_hash,
    now64(3, 'UTC')
FROM payload
SETTINGS insert_deduplication_token = {oracle_manifest_dedup_token:String};
