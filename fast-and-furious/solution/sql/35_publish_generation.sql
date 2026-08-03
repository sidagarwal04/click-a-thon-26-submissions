-- Authoritative control-plane publication. The guarded INSERT recomputes the
-- candidate and sealed snapshot in one query snapshot; prior validation order is
-- not trusted. Any post-validation append therefore changes a checked hash/count
-- and prevents the manifest row from becoming visible.

INSERT INTO sonyliv.serving_generation_manifest
WITH
    {service_date:Date} AS selected_date,

    snapshot_header AS
    (
        SELECT
            count() AS header_rows,
            any(adjustment_batches) AS adjustment_batches,
            any(adjustment_rows) AS adjustment_rows,
            any(adjustment_ledger_hash) AS adjustment_ledger_hash,
            any(point_rows) AS point_rows,
            any(point_hash) AS point_hash
        FROM sonyliv.delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
    ),

    membership_logical AS
    (
        SELECT
            adjustment_batch_id,
            any(adjustment_block_hash) AS selected_block_hash,
            any(adjustment_rows) AS selected_adjustment_rows,
            count() AS physical_rows,
            uniqExact(tuple(adjustment_block_hash, adjustment_rows)) AS physical_versions
        FROM sonyliv.delta_snapshot_batches
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
        GROUP BY adjustment_batch_id
    ),

    membership_summary AS
    (
        SELECT
            count() AS total_adjustment_batches,
            sum(selected_adjustment_rows) AS total_adjustment_rows,
            countIf(physical_rows != 1 OR physical_versions != 1) AS malformed_members,
            hex(
                SHA256(
                    arrayStringConcat(
                        arraySort(groupArray(concat(
                                toString(adjustment_batch_id), ':',
                                toString(selected_block_hash), ':',
                                toString(selected_adjustment_rows)
                        ))),
                        '\n'
                    )
                )
            ) AS adjustment_ledger_hash
        FROM membership_logical
    ),

    actual_batches AS
    (
        SELECT
            adjustment_batch_id,
            count() AS actual_rows,
            hex(
                SHA256(
                    arrayStringConcat(
                        arraySort(groupArray(toString(adjustment_operation_id))),
                        '\n'
                    )
                )
            ) AS actual_hash
        FROM sonyliv.boundary_adjustments
        WHERE adjustment_batch_id IN
        (
            SELECT adjustment_batch_id
            FROM membership_logical
        )
        GROUP BY adjustment_batch_id
    ),

    malformed_batches AS
    (
        SELECT m.adjustment_batch_id
        FROM membership_logical AS m
        LEFT JOIN actual_batches AS a USING (adjustment_batch_id)
        WHERE a.actual_rows != m.selected_adjustment_rows
           OR a.actual_hash != m.selected_block_hash
    ),

    logical_points AS
    (
        SELECT
            entity,
            rollup_mask,
            service_date,
            boundary_time,
            platform,
            country,
            video_type,
            content_id,
            sum(delta) AS delta
        FROM sonyliv.concurrency_delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
        GROUP BY
            entity, rollup_mask, service_date, boundary_time,
            platform, country, video_type, content_id
        HAVING delta != 0
    ),

    point_summary AS
    (
        SELECT
            count() AS point_rows,
            hex(
                SHA256(
                    concat(
                        toString(count()), ':',
                        toString(sum(cityHash64(
                            entity, rollup_mask, service_date, boundary_time,
                            platform, country, video_type, content_id, delta
                        ))), ':',
                        toString(groupBitXor(cityHash64(
                            entity, rollup_mask, service_date, boundary_time,
                            platform, country, video_type, content_id, delta
                        )))
                    )
                )
            ) AS point_hash
        FROM logical_points
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

    candidate_logical AS
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
            count() AS physical_rows
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

    candidate_summary AS
    (
        SELECT
            count() AS minute_rows,
            countIf(physical_rows != 1) AS duplicate_keys,
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
        FROM candidate_logical
    ),

    sealed_logical AS
    (
        SELECT
            service_date,
            entity,
            rollup_mask,
            generation,
            policy_version,
            pipeline_run_id,
            source_delta_snapshot,
            oracle_run_id,
            snapshot_ledger_hash,
            candidate_answer_hash,
            candidate_minute_rows,
            expected_answer_hash,
            expected_minute_rows,
            parent_attestation_id,
            validator_version,
            attestation_id,
            hex(SHA256(concat(
                toString(service_date), ';', toString(entity), ';', toString(rollup_mask), ';',
                toString(generation), ';',
                toString(length(toString(policy_version))), ':', toString(policy_version),
                toString(pipeline_run_id), ';', toString(source_delta_snapshot), ';',
                'sealed_points;', toString(oracle_run_id), ';',
                snapshot_ledger_hash, candidate_answer_hash, ';',
                toString(candidate_minute_rows), ';', expected_answer_hash, ';',
                toString(expected_minute_rows), ';', parent_attestation_id,
                toString(validator_version)
            ))) AS self_hash
        FROM sonyliv.generation_validation_attestations
        WHERE service_date = selected_date
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
          AND generation = {generation:UInt64}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND validation_source = 'sealed_points'
          AND oracle_run_id = toUUID('00000000-0000-0000-0000-000000000000')
        GROUP BY
            service_date, entity, rollup_mask, generation, policy_version,
            pipeline_run_id, source_delta_snapshot, oracle_run_id,
            snapshot_ledger_hash, candidate_answer_hash, candidate_minute_rows,
            expected_answer_hash, expected_minute_rows, parent_attestation_id,
            validator_version, attestation_id
    ),

    sealed_summary AS
    (
        SELECT
            count() AS logical_attestations,
            countIf(attestation_id != self_hash) AS invalid_self_hashes,
            countIf(validator_version != 'sealed-point-v2') AS invalid_versions,
            any(attestation_id) AS selected_attestation_id,
            any(snapshot_ledger_hash) AS selected_snapshot_ledger_hash,
            any(candidate_answer_hash) AS selected_candidate_answer_hash,
            any(candidate_minute_rows) AS selected_candidate_minute_rows,
            any(expected_answer_hash) AS selected_expected_answer_hash,
            any(expected_minute_rows) AS selected_expected_minute_rows,
            any(parent_attestation_id) AS selected_parent_attestation_id
        FROM sealed_logical
    ),

    raw_logical AS
    (
        SELECT
            service_date,
            entity,
            rollup_mask,
            generation,
            policy_version,
            pipeline_run_id,
            source_delta_snapshot,
            oracle_run_id,
            snapshot_ledger_hash,
            candidate_answer_hash,
            candidate_minute_rows,
            expected_answer_hash,
            expected_minute_rows,
            parent_attestation_id,
            validator_version,
            attestation_id,
            hex(SHA256(concat(
                toString(service_date), ';', toString(entity), ';', toString(rollup_mask), ';',
                toString(generation), ';',
                toString(length(toString(policy_version))), ':', toString(policy_version),
                toString(pipeline_run_id), ';', toString(source_delta_snapshot), ';',
                'raw_interval_oracle;', toString(oracle_run_id), ';',
                snapshot_ledger_hash, candidate_answer_hash, ';',
                toString(candidate_minute_rows), ';', expected_answer_hash, ';',
                toString(expected_minute_rows), ';', parent_attestation_id,
                toString(validator_version)
            ))) AS self_hash
        FROM sonyliv.generation_validation_attestations
        WHERE service_date = selected_date
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
          AND generation = {generation:UInt64}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND validation_source = 'raw_interval_oracle'
          AND oracle_run_id = {oracle_run_id:UUID}
        GROUP BY
            service_date, entity, rollup_mask, generation, policy_version,
            pipeline_run_id, source_delta_snapshot, oracle_run_id,
            snapshot_ledger_hash, candidate_answer_hash, candidate_minute_rows,
            expected_answer_hash, expected_minute_rows, parent_attestation_id,
            validator_version, attestation_id
    ),

    raw_summary AS
    (
        SELECT
            count() AS logical_attestations,
            countIf(attestation_id != self_hash) AS invalid_self_hashes,
            countIf(validator_version != 'raw-interval-oracle-v2') AS invalid_versions,
            any(attestation_id) AS selected_attestation_id,
            any(snapshot_ledger_hash) AS selected_snapshot_ledger_hash,
            any(candidate_answer_hash) AS selected_candidate_answer_hash,
            any(candidate_minute_rows) AS selected_candidate_minute_rows,
            any(expected_answer_hash) AS selected_expected_answer_hash,
            any(expected_minute_rows) AS selected_expected_minute_rows,
            any(parent_attestation_id) AS selected_parent_attestation_id
        FROM raw_logical
    ),

    existing_manifest AS
    (
        SELECT count() AS manifest_rows
        FROM sonyliv.serving_generation_manifest
        WHERE service_date = selected_date
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
          AND generation = {generation:UInt64}
    ),

    publication AS
    (
        SELECT
            c.answer_hash,
            c.minute_rows,
            r.selected_attestation_id AS validation_attestation_id,
            if(
                h.header_rows != 1
                OR m.malformed_members != 0
                OR m.total_adjustment_batches != h.adjustment_batches
                OR m.total_adjustment_rows != h.adjustment_rows
                OR m.adjustment_ledger_hash != h.adjustment_ledger_hash
                OR (SELECT count() FROM malformed_batches) != 0
                OR p.point_rows != h.point_rows
                OR p.point_hash != h.point_hash
                OR o.manifest_rows != 1
                OR o.invalid_manifest_hashes != 0
                OR NOT o.selected_is_full_scan
                OR o.selected_heartbeat_timeout_ms = 0
                OR o.selected_expected_sessions < o.selected_active_sessions
                OR o.selected_source_snapshot_hash != ls.source_snapshot_hash
                OR o.selected_active_sessions != co.active_sessions
                OR o.selected_interval_rows != co.interval_rows
                OR o.selected_interval_hash != co.interval_hash
                OR c.duplicate_keys != 0
                OR e.manifest_rows != 0
                OR s.logical_attestations != 1
                OR s.invalid_self_hashes != 0
                OR s.invalid_versions != 0
                OR s.selected_parent_attestation_id != repeat('0', 64)
                OR s.selected_snapshot_ledger_hash != h.adjustment_ledger_hash
                OR s.selected_candidate_answer_hash != s.selected_expected_answer_hash
                OR s.selected_candidate_minute_rows != s.selected_expected_minute_rows
                OR s.selected_candidate_answer_hash != c.answer_hash
                OR s.selected_candidate_minute_rows != c.minute_rows
                OR r.logical_attestations != 1
                OR r.invalid_self_hashes != 0
                OR r.invalid_versions != 0
                OR r.selected_parent_attestation_id != s.selected_attestation_id
                OR r.selected_snapshot_ledger_hash != h.adjustment_ledger_hash
                OR r.selected_candidate_answer_hash != r.selected_expected_answer_hash
                OR r.selected_candidate_minute_rows != r.selected_expected_minute_rows
                OR r.selected_candidate_answer_hash != c.answer_hash
                OR r.selected_candidate_minute_rows != c.minute_rows,
                toString(throwIf(1, 'generation publication integrity gate failed')),
                c.answer_hash
            ) AS guarded_answer_hash
        FROM candidate_summary AS c
        CROSS JOIN snapshot_header AS h
        CROSS JOIN membership_summary AS m
        CROSS JOIN point_summary AS p
        CROSS JOIN latest_source AS ls
        CROSS JOIN oracle_manifest AS o
        CROSS JOIN current_oracle_summary AS co
        CROSS JOIN sealed_summary AS s
        CROSS JOIN raw_summary AS r
        CROSS JOIN existing_manifest AS e
    )

SELECT
    selected_date,
    CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)'),
    {rollup_mask:UInt16},
    {generation:UInt64},
    {policy_version:String},
    {pipeline_run_id:UUID},
    {source_delta_snapshot:UInt128},
    {oracle_run_id:UUID},
    validation_attestation_id,
    now64(3, 'UTC'),
    guarded_answer_hash,
    minute_rows
FROM publication
SETTINGS
    insert_deduplication_token = {generation_manifest_dedup_token:String},
    join_use_nulls = 0,
    max_execution_time = 120,
    max_rows_to_read = 100000000,
    max_bytes_to_read = 20000000000;

SELECT
    generation,
    validation_oracle_run_id,
    validation_attestation_id,
    answer_hash,
    minute_rows,
    source_delta_snapshot,
    published_at
FROM sonyliv.serving_generation_manifest
WHERE service_date = {service_date:Date}
  AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
  AND rollup_mask = {rollup_mask:UInt16}
  AND generation = {generation:UInt64};
