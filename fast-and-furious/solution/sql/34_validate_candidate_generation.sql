-- Full per-minute parity gate for one candidate generation. This independently
-- recomputes exact minute rows from the sealed signed-point snapshot and rejects
-- any missing, duplicate, shifted, or numerically different cache row.

WITH
    {service_date:Date} AS selected_date,
    toDateTime64(selected_date, 3, 'UTC') AS day_start,
    toDateTime64(addDays(selected_date, 1), 3, 'UTC') AS day_end,
    toUnixTimestamp64Milli(day_start) AS day_start_ms,
    toUInt64(60000) AS minute_ms,

    snapshot_guard AS
    (
        SELECT throwIf(
            count() != 1,
            'candidate source_delta_snapshot is missing or duplicated'
        ) AS ok
        FROM sonyliv.delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
    ),

    snapshot_metadata AS
    (
        SELECT any(adjustment_ledger_hash) AS adjustment_ledger_hash
        FROM sonyliv.delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
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
        FROM sonyliv.concurrency_delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND service_date = selected_date
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
          AND boundary_time < day_end
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
                toInt64(throwIf(1, 'negative concurrency invariant breach')),
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
          AND boundary_time < day_end
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

    expected_fingerprint AS
    (
        SELECT
            count() AS minute_rows,
            hex(
                SHA256(
                    arrayStringConcat(
                        arrayMap(item -> item.2, arraySort(groupArray((
                            tuple(minute_start, platform, country, video_type, content_id),
                            concat(
                                toString(toUnixTimestamp64Milli(minute_start)), ';',
                                toString(length(platform)), ':', platform,
                                toString(length(country)), ':', country,
                                toString(length(video_type)), ':', video_type,
                                toString(content_id), ';', toString(minute_peak), ';',
                                toString(active_entity_ms), ';', toString(ending_concurrency), ';'
                            )
                        )))),
                        ''
                    )
                )
            ) AS answer_hash
        FROM expected
    ),

    candidate_fingerprint AS
    (
        SELECT
            count() AS minute_rows,
            hex(
                SHA256(
                    arrayStringConcat(
                        arrayMap(item -> item.2, arraySort(groupArray((
                            tuple(minute_start, platform, country, video_type, content_id),
                            concat(
                                toString(toUnixTimestamp64Milli(minute_start)), ';',
                                toString(length(platform)), ':', platform,
                                toString(length(country)), ':', country,
                                toString(length(video_type)), ':', video_type,
                                toString(content_id), ';', toString(minute_peak), ';',
                                toString(active_entity_ms), ';', toString(ending_concurrency), ';'
                            )
                        )))),
                        ''
                    )
                )
            ) AS answer_hash
        FROM actual
    ),

    differences AS
    (
        SELECT
            coalesce(e.minute_start, a.minute_start) AS minute_start,
            coalesce(e.platform, a.platform) AS platform,
            coalesce(e.country, a.country) AS country,
            coalesce(e.video_type, a.video_type) AS video_type,
            coalesce(e.content_id, a.content_id) AS content_id
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

    result AS
    (
        SELECT
            (SELECT count() FROM differences) AS mismatch_rows,
            e.answer_hash AS expected_hash,
            e.minute_rows AS expected_rows,
            c.answer_hash AS candidate_hash,
            c.minute_rows AS candidate_rows,
            m.adjustment_ledger_hash AS ledger_hash
        FROM expected_fingerprint AS e
        CROSS JOIN candidate_fingerprint AS c
        CROSS JOIN snapshot_metadata AS m
        CROSS JOIN snapshot_guard
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
    CAST('sealed_points', 'Enum8(\'sealed_points\' = 1, \'raw_interval_oracle\' = 2)'),
    toUUID('00000000-0000-0000-0000-000000000000'),
    ledger_hash,
    if(
        mismatch_rows > 0 OR candidate_hash != expected_hash OR candidate_rows != expected_rows,
        toString(throwIf(1, 'candidate minute generation differs from exact sealed-point recomputation')),
        candidate_hash
    ),
    candidate_rows,
    expected_hash,
    expected_rows,
    repeat('0', 64),
    'sealed-point-v2',
    hex(SHA256(concat(
        toString(selected_date), ';', {entity:String}, ';', toString({rollup_mask:UInt16}), ';',
        toString({generation:UInt64}), ';',
        toString(length({policy_version:String})), ':', {policy_version:String},
        toString({pipeline_run_id:UUID}), ';', toString({source_delta_snapshot:UInt128}), ';',
        'sealed_points;',
        '00000000-0000-0000-0000-000000000000;',
        ledger_hash, candidate_hash, ';', toString(candidate_rows), ';',
        expected_hash, ';', toString(expected_rows), ';',
        repeat('0', 64), 'sealed-point-v2'
    ))),
    now64(3, 'UTC')
FROM result
SETTINGS
    insert_deduplication_token = {sealed_attestation_dedup_token:String},
    join_use_nulls = 0,
    max_execution_time = 60,
    max_rows_to_read = 100000000,
    max_bytes_to_read = 20000000000;

SELECT throwIf(
    count() != 1,
    'sealed-point validation attestation missing or duplicated'
) AS candidate_generation_parity
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
      AND validation_source = 'sealed_points'
    GROUP BY attestation_id
);
