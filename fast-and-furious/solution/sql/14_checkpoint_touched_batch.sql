-- Run only after step 20 wrote exactly one published_adjustment_batches row.
-- Unanchored sessions are deliberately not checkpointed and remain dirty.

SELECT throwIf(
    count() != 1,
    'cannot checkpoint: adjustment batch is not published exactly once'
)
FROM sonyliv.published_adjustment_batches
WHERE adjustment_batch_id = {adjustment_batch_id:UUID}
  AND policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND state_revision = {state_revision:UInt64}
  AND lease_epoch = {lease_epoch:UInt64};

INSERT INTO sonyliv.applied_dirty_operations
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    dirty_operation_id,
    {adjustment_batch_id:UUID},
    now64(3, 'UTC'),
    {state_revision:UInt64}
FROM
(
    SELECT
        video_session_id,
        arrayJoin(dirty_operation_ids) AS dirty_operation_id
    FROM sonyliv.compaction_worksets
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
)
WHERE video_session_id IN
(
    SELECT video_session_id
    FROM sonyliv.session_recompute_candidates
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
)
SETTINGS insert_deduplication_token = {dirty_checkpoint_dedup_token:String};

INSERT INTO sonyliv.processing_batches
SELECT
    {adjustment_batch_id:UUID},
    {input_manifest_hash:String},
    {policy_version:String},
    min(selected_at),
    now64(3, 'UTC'),
    CAST('published', 'Enum8(\'started\' = 1, \'published\' = 2, \'validated\' = 3, \'failed\' = 4)'),
    count(),
    (
        SELECT count()
        FROM sonyliv.boundary_adjustments
        WHERE adjustment_batch_id = {adjustment_batch_id:UUID}
    ),
    ''
FROM sonyliv.compaction_worksets
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {processing_checkpoint_dedup_token:String};

SELECT
    count() AS applied_dirty_operations,
    uniqExact(video_session_id) AS checkpointed_sessions
FROM sonyliv.applied_dirty_operations AS a
INNER JOIN
(
    SELECT video_session_id, arrayJoin(dirty_operation_ids) AS dirty_operation_id
    FROM sonyliv.compaction_worksets
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
) AS w USING (dirty_operation_id)
WHERE a.pipeline_run_id = {pipeline_run_id:UUID}
  AND a.policy_version = {policy_version:String}
  AND a.adjustment_batch_id = {adjustment_batch_id:UUID};
