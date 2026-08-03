-- Freeze the complete initial dirty-operation set for one serving lineage.
-- The membership insert and final header are deliberately single-attempt: if a
-- process dies before the header, abandon this pipeline_run_id and allocate a
-- new one rather than guessing whether a plain MergeTree insert was duplicated.

SELECT throwIf(
    count() > 0,
    'pipeline_run_id already has a committed seed; never reseed a lineage'
)
FROM sonyliv.pipeline_lineage_seeds
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};

SELECT throwIf(
    count() > 0,
    'orphan seed membership exists; abandon this pipeline_run_id'
)
FROM sonyliv.pipeline_seed_operations
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};

INSERT INTO sonyliv.pipeline_seed_operations
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    {source_snapshot_hash:String},
    dirty_operation_id,
    any(video_session_id) AS video_session_id
FROM sonyliv.dirty_session_events
GROUP BY dirty_operation_id
ORDER BY dirty_operation_id
SETTINGS insert_deduplication_token = {seed_membership_dedup_token:String};

INSERT INTO sonyliv.pipeline_lineage_seeds
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    {source_snapshot_hash:String},
    count() AS seed_operations,
    uniqExact(video_session_id) AS seed_sessions,
    hex(
        SHA256(
            arrayStringConcat(
                arraySort(groupArray(concat(
                    toString(dirty_operation_id), ':', video_session_id
                ))),
                '\n'
            )
        )
    ) AS seed_membership_hash,
    now64(3, 'UTC')
FROM sonyliv.pipeline_seed_operations
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND source_snapshot_hash = {source_snapshot_hash:String}
SETTINGS insert_deduplication_token = {seed_header_dedup_token:String};

SELECT
    pipeline_run_id,
    policy_version,
    source_snapshot_hash,
    seed_operations,
    seed_sessions,
    seed_membership_hash
FROM sonyliv.pipeline_lineage_seeds
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};
