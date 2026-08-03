-- Select a deterministic batch of unapplied dirty operations. This is an
-- append-only queue: no run-local max(version) can hide a later ingestion batch.
-- The orchestrator MUST hold one exclusive compactor lock per pipeline_run_id
-- (ClickHouse Keeper/queue partition/advisory lock). The expiring rows below
-- make abandoned claims recoverable and make lock violations fail visibly.

INSERT INTO sonyliv.compaction_worksets
SELECT
    {pipeline_run_id:UUID} AS pipeline_run_id,
    {policy_version:String} AS policy_version,
    {adjustment_batch_id:UUID} AS adjustment_batch_id,
    d.video_session_id,
    arraySort(groupUniqArray(d.dirty_operation_id)) AS dirty_operation_ids,
    now64(3, 'UTC') AS selected_at,
    {lease_owner:String} AS lease_owner,
    {lease_epoch:UInt64} AS lease_epoch,
    now64(3, 'UTC') + toIntervalMillisecond({claim_lease_ms:UInt64}) AS lease_expires_at
FROM sonyliv.dirty_session_events AS d
LEFT ANTI JOIN
(
    SELECT dirty_operation_id
    FROM sonyliv.applied_dirty_operations
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
) AS a USING (dirty_operation_id)
LEFT ANTI JOIN
(
    SELECT arrayJoin(dirty_operation_ids) AS dirty_operation_id
    FROM sonyliv.compaction_worksets
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id != {adjustment_batch_id:UUID}
      AND lease_expires_at > now64(3, 'UTC')
) AS claimed USING (dirty_operation_id)
LEFT ANTI JOIN
(
    SELECT video_session_id
    FROM sonyliv.compaction_worksets
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
) AS existing USING (video_session_id)
GROUP BY d.video_session_id
ORDER BY min(d.last_ingested_at), d.video_session_id
LIMIT {max_touched_sessions:UInt64}
SETTINGS insert_deduplication_token = {workset_dedup_token:String};

SELECT throwIf(
    count() > 0,
    'exclusive compactor lease violated: a dirty operation is actively claimed by multiple batches'
)
FROM
(
    SELECT arrayJoin(dirty_operation_ids) AS dirty_operation_id
    FROM sonyliv.compaction_worksets
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND lease_expires_at > now64(3, 'UTC')
    GROUP BY dirty_operation_id
    HAVING uniqExact(adjustment_batch_id) > 1
);

SELECT
    count() AS touched_sessions,
    arraySum(groupArray(length(dirty_operation_ids))) AS dirty_operations
FROM sonyliv.compaction_worksets
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID};
