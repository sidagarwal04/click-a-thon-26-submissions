-- Independent per-minute oracle parity. Unlike steps 31/34, this derives entity
-- intervals directly from active_intervals_reference and therefore catches a
-- boundary/cache time shift that preserves only the daily active-ms total.

WITH
    {service_date:Date} AS selected_date,
    toDateTime64(selected_date, 3, 'UTC') AS day_start,
    toDateTime64(addDays(selected_date, 1), 3, 'UTC') AS day_end,
    toUnixTimestamp64Milli(day_start) AS day_start_ms,
    toUInt64(60000) AS minute_ms,

    source_intervals AS
    (
        SELECT
            video_session_id,
            canonical_user_id,
            if(bitAnd({rollup_mask:UInt16}, 1) != 0, platform, '__all__') AS platform,
            if(bitAnd({rollup_mask:UInt16}, 2) != 0, country, '__all__') AS country,
            if(bitAnd({rollup_mask:UInt16}, 8) != 0, video_type, '__all__') AS video_type,
            if(bitAnd({rollup_mask:UInt16}, 4) != 0, content_id, toInt32(0)) AS content_id,
            greatest(start_time, day_start) AS start_time,
            least(end_time, day_end) AS end_time
        FROM sonyliv.active_intervals_reference
        WHERE oracle_run_id = {oracle_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND start_time < day_end
          AND end_time > day_start
    ),

    user_marked AS
    (
        SELECT
            *,
            start_time > max(end_time) OVER
            (
                PARTITION BY canonical_user_id, platform, country, video_type, content_id
                ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS starts_new_island
        FROM source_intervals
        WHERE {entity:String} = 'user'
    ),

    user_numbered AS
    (
        SELECT
            *,
            sum(starts_new_island) OVER
            (
                PARTITION BY canonical_user_id, platform, country, video_type, content_id
                ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS island_number
        FROM user_marked
    ),

    user_intervals AS
    (
        SELECT
            canonical_user_id AS source_entity_id,
            platform,
            country,
            video_type,
            content_id,
            min(start_time) AS start_time,
            max(end_time) AS end_time
        FROM user_numbered
        GROUP BY
            canonical_user_id, platform, country, video_type, content_id, island_number
    ),

    entity_intervals AS
    (
        SELECT
            video_session_id AS source_entity_id,
            platform,
            country,
            video_type,
            content_id,
            start_time,
            end_time
        FROM source_intervals
        WHERE {entity:String} = 'session'

        UNION ALL

        SELECT * FROM user_intervals
    ),

    endpoints AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            endpoint.1 AS boundary_time,
            endpoint.2 AS delta
        FROM entity_intervals
        ARRAY JOIN [
            (start_time, toInt64(1)),
            (end_time, toInt64(-1))
        ] AS endpoint
        WHERE end_time > start_time
    ),

    points AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            boundary_time,
            sum(delta) AS point_delta
        FROM endpoints
        GROUP BY platform, country, video_type, content_id, boundary_time
        HAVING point_delta != 0
    ),

    curve AS
    (
        SELECT
            *,
            sum(point_delta) OVER point_window AS concurrency,
            leadInFrame(boundary_time, 1, day_end) OVER full_window AS next_boundary_time
        FROM points
        WINDOW
            point_window AS
            (
                PARTITION BY platform, country, video_type, content_id
                ORDER BY boundary_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ),
            full_window AS
            (
                PARTITION BY platform, country, video_type, content_id
                ORDER BY boundary_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
    ),

    minute_overlaps AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            minute_number,
            if(
                concurrency < 0,
                toInt64(throwIf(1, 'negative independent-oracle concurrency')),
                toInt64(concurrency)
            ) AS concurrency,
            least(
                toUnixTimestamp64Milli(next_boundary_time),
                day_start_ms + toInt64((minute_number + 1) * minute_ms)
            ) - greatest(
                toUnixTimestamp64Milli(boundary_time),
                day_start_ms + toInt64(minute_number * minute_ms)
            ) AS overlap_ms,
            least(
                toUnixTimestamp64Milli(next_boundary_time),
                day_start_ms + toInt64((minute_number + 1) * minute_ms)
            ) AS overlap_end_ms
        FROM curve
        ARRAY JOIN range(
            toUInt64(intDiv(toUnixTimestamp64Milli(boundary_time) - day_start_ms, toInt64(minute_ms))),
            toUInt64(intDiv(toUnixTimestamp64Milli(next_boundary_time) - day_start_ms - 1, toInt64(minute_ms)) + 1)
        ) AS minute_number
        WHERE next_boundary_time > boundary_time
    ),

    expected AS
    (
        SELECT
            fromUnixTimestamp64Milli(
                day_start_ms + toInt64(minute_number * minute_ms),
                'UTC'
            ) AS minute_start,
            platform,
            country,
            video_type,
            content_id,
            toUInt64(max(concurrency)) AS minute_peak,
            toUInt64(sum(toInt128(concurrency) * toInt128(overlap_ms))) AS active_entity_ms,
            toUInt64(argMax(concurrency, overlap_end_ms)) AS ending_concurrency,
            toUInt8(1) AS expected_present
        FROM minute_overlaps
        WHERE overlap_ms > 0
        GROUP BY platform, country, video_type, content_id, minute_number
        HAVING minute_peak > 0 OR active_entity_ms > 0 OR ending_concurrency > 0
    ),

    actual AS
    (
        SELECT
            minute_start,
            platform,
            country,
            video_type,
            content_id,
            any(minute_peak) AS minute_peak,
            any(active_entity_ms) AS active_entity_ms,
            any(ending_concurrency) AS ending_concurrency,
            count() AS physical_rows,
            toUInt8(1) AS actual_present
        FROM sonyliv.concurrency_minute_versions
        WHERE generation = {generation:UInt64}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND service_date = selected_date
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
        GROUP BY minute_start, platform, country, video_type, content_id
    ),

    differences AS
    (
        SELECT coalesce(e.minute_start, a.minute_start) AS minute_start
        FROM expected AS e
        FULL OUTER JOIN actual AS a
            ON e.minute_start = a.minute_start
           AND e.platform = a.platform
           AND e.country = a.country
           AND e.video_type = a.video_type
           AND e.content_id = a.content_id
        WHERE e.expected_present = 0
           OR a.actual_present = 0
           OR a.physical_rows != 1
           OR e.minute_peak != a.minute_peak
           OR e.active_entity_ms != a.active_entity_ms
           OR e.ending_concurrency != a.ending_concurrency
    ),

    expected_fingerprint AS
    (
        SELECT
            count() AS minute_rows,
            hex(SHA256(arrayStringConcat(arrayMap(item -> item.2, arraySort(groupArray((
                tuple(minute_start, platform, country, video_type, content_id),
                concat(
                    toString(toUnixTimestamp64Milli(minute_start)), ';',
                    toString(length(platform)), ':', platform,
                    toString(length(country)), ':', country,
                    toString(length(video_type)), ':', video_type,
                    toString(content_id), ';', toString(minute_peak), ';',
                    toString(active_entity_ms), ';', toString(ending_concurrency), ';'
                )
            )))), ''))) AS answer_hash
        FROM expected
    ),

    candidate_fingerprint AS
    (
        SELECT
            count() AS minute_rows,
            hex(SHA256(arrayStringConcat(arrayMap(item -> item.2, arraySort(groupArray((
                tuple(minute_start, platform, country, video_type, content_id),
                concat(
                    toString(toUnixTimestamp64Milli(minute_start)), ';',
                    toString(length(platform)), ':', platform,
                    toString(length(country)), ':', country,
                    toString(length(video_type)), ':', video_type,
                    toString(content_id), ';', toString(minute_peak), ';',
                    toString(active_entity_ms), ';', toString(ending_concurrency), ';'
                )
            )))), ''))) AS answer_hash
        FROM actual
    ),

    parent AS
    (
        SELECT
            any(attestation_id) AS parent_attestation_id,
            uniqExact(attestation_id) AS logical_attestations
        FROM sonyliv.generation_validation_attestations
        WHERE service_date = selected_date
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
          AND generation = {generation:UInt64}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND validation_source = 'sealed_points'
    ),

    snapshot AS
    (
        SELECT
            any(adjustment_ledger_hash) AS ledger_hash,
            count() AS snapshot_rows
        FROM sonyliv.delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
    ),

    latest_source AS
    (
        SELECT
            argMax(
                p.source_snapshot_hash,
                tuple(p.state_revision, p.published_at, p.adjustment_batch_id)
            ) AS source_snapshot_hash
        FROM sonyliv.delta_snapshot_batches AS m
        INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
        WHERE m.source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND m.pipeline_run_id = {pipeline_run_id:UUID}
          AND m.policy_version = {policy_version:String}
          AND p.pipeline_run_id = {pipeline_run_id:UUID}
          AND p.policy_version = {policy_version:String}
    ),

    oracle_manifest AS
    (
        SELECT
            count() AS manifest_rows,
            countIf(manifest_hash != hex(SHA256(concat(
                toString(oracle_run_id), ';', toString(pipeline_run_id), ';',
                toString(length(toString(policy_version))), ':', toString(policy_version),
                source_snapshot_hash, toString(is_full_scan), ';',
                toString(toUnixTimestamp64Milli(evaluation_as_of)), ';',
                toString(heartbeat_timeout_ms), ';',
                toString(expected_anchored_sessions), ';', toString(active_sessions), ';',
                toString(interval_rows), ';', interval_hash
            )))) AS invalid_manifest_hashes,
            any(source_snapshot_hash) AS selected_source_snapshot_hash,
            any(is_full_scan) AS selected_is_full_scan,
            any(heartbeat_timeout_ms) AS selected_heartbeat_timeout_ms,
            any(expected_anchored_sessions) AS selected_expected_sessions,
            any(active_sessions) AS selected_active_sessions,
            any(interval_rows) AS selected_interval_rows,
            any(interval_hash) AS selected_interval_hash
        FROM sonyliv.oracle_run_manifests
        WHERE oracle_run_id = {oracle_run_id:UUID}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
    ),

    current_oracle_rows AS
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

    current_oracle_summary AS
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
        FROM current_oracle_rows
    ),

    result AS
    (
        SELECT
            (SELECT count() FROM differences) AS mismatch_rows,
            e.answer_hash AS expected_hash,
            e.minute_rows AS expected_rows,
            c.answer_hash AS candidate_hash,
            c.minute_rows AS candidate_rows,
            p.parent_attestation_id AS parent_id,
            p.logical_attestations AS parent_count,
            s.ledger_hash,
            s.snapshot_rows,
            o.manifest_rows AS oracle_manifest_rows,
            o.invalid_manifest_hashes AS invalid_oracle_manifest_hashes,
            o.selected_is_full_scan AS oracle_is_full_scan,
            o.selected_heartbeat_timeout_ms AS oracle_heartbeat_timeout_ms,
            o.selected_source_snapshot_hash AS oracle_source_hash,
            o.selected_expected_sessions AS oracle_expected_sessions,
            o.selected_active_sessions AS sealed_oracle_active_sessions,
            o.selected_interval_rows AS sealed_oracle_interval_rows,
            o.selected_interval_hash AS sealed_oracle_interval_hash,
            co.active_sessions AS current_oracle_active_sessions,
            co.interval_rows AS current_oracle_interval_rows,
            co.interval_hash AS current_oracle_interval_hash,
            ls.source_snapshot_hash AS latest_source_hash
        FROM expected_fingerprint AS e
        CROSS JOIN candidate_fingerprint AS c
        CROSS JOIN parent AS p
        CROSS JOIN snapshot AS s
        CROSS JOIN oracle_manifest AS o
        CROSS JOIN current_oracle_summary AS co
        CROSS JOIN latest_source AS ls
    )

INSERT INTO sonyliv.generation_validation_attestations
SELECT
    selected_date,
    CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)'),
    {rollup_mask:UInt16},
    {generation:UInt64},
    {policy_version:String},
    {pipeline_run_id:UUID},
    {source_delta_snapshot:UInt128},
    CAST('raw_interval_oracle', 'Enum8(\'sealed_points\' = 1, \'raw_interval_oracle\' = 2)'),
    {oracle_run_id:UUID},
    ledger_hash,
    if(
        mismatch_rows > 0
        OR candidate_hash != expected_hash
        OR candidate_rows != expected_rows
        OR parent_count != 1
        OR snapshot_rows != 1
        OR oracle_manifest_rows != 1
        OR invalid_oracle_manifest_hashes != 0
        OR NOT oracle_is_full_scan
        OR oracle_heartbeat_timeout_ms = 0
        OR oracle_expected_sessions < sealed_oracle_active_sessions
        OR oracle_source_hash != latest_source_hash
        OR sealed_oracle_active_sessions != current_oracle_active_sessions
        OR sealed_oracle_interval_rows != current_oracle_interval_rows
        OR sealed_oracle_interval_hash != current_oracle_interval_hash,
        toString(throwIf(1, 'candidate differs from independent raw-interval minute oracle')),
        candidate_hash
    ),
    candidate_rows,
    expected_hash,
    expected_rows,
    parent_id,
    'raw-interval-oracle-v2',
    hex(SHA256(concat(
        toString(selected_date), ';', {entity:String}, ';', toString({rollup_mask:UInt16}), ';',
        toString({generation:UInt64}), ';',
        toString(length({policy_version:String})), ':', {policy_version:String},
        toString({pipeline_run_id:UUID}), ';', toString({source_delta_snapshot:UInt128}), ';',
        'raw_interval_oracle;', toString({oracle_run_id:UUID}), ';',
        ledger_hash, candidate_hash, ';', toString(candidate_rows), ';',
        expected_hash, ';', toString(expected_rows), ';',
        parent_id, 'raw-interval-oracle-v2'
    ))),
    now64(3, 'UTC')
FROM result
SETTINGS
    insert_deduplication_token = {oracle_attestation_dedup_token:String},
    join_use_nulls = 0,
    max_execution_time = 120,
    max_rows_to_read = 100000000,
    max_bytes_to_read = 20000000000;

SELECT throwIf(
    count() != 1,
    'raw-interval oracle validation attestation missing or duplicated'
) AS raw_oracle_generation_parity
FROM
(
    SELECT attestation_id
    FROM sonyliv.generation_validation_attestations
    WHERE service_date = {service_date:Date}
      AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
      AND rollup_mask = {rollup_mask:UInt16}
      AND generation = {generation:UInt64}
      AND policy_version = {policy_version:String}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND validation_source = 'raw_interval_oracle'
      AND oracle_run_id = {oracle_run_id:UUID}
    GROUP BY attestation_id
);
