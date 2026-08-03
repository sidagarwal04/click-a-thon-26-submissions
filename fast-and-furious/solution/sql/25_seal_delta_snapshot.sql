-- Seal one immutable correction-ledger snapshot while the lineage compactor
-- lease is held. Membership and point rows are materialized first; the header
-- row is the final visibility/commit marker and is never updated.

SELECT throwIf(
    count() > 0,
    'source_delta_snapshot already exists; never reuse a committed snapshot ID'
)
FROM sonyliv.delta_snapshots
WHERE source_delta_snapshot = {source_delta_snapshot:UInt128};

SELECT throwIf(
    (
        SELECT count()
        FROM sonyliv.delta_snapshot_batches
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
    ) > 0
    OR
    (
        SELECT count()
        FROM sonyliv.concurrency_delta_snapshots
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
    ) > 0,
    'orphan snapshot staging rows exist; abandon this snapshot ID'
);

-- A fresh lineage cannot expose only its first LIMIT-sized seed batch. Validate
-- the frozen seed membership and require every seed operation/session to have a
-- committed state revision before any snapshot can be sealed.
SELECT throwIf(
    count() != 1,
    'pipeline lineage seed is missing or duplicated'
)
FROM sonyliv.pipeline_lineage_seeds
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};

WITH prior AS
(
    SELECT count() AS snapshots
    FROM sonyliv.delta_snapshots
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
), current_dirty_rows AS
(
    SELECT dirty_operation_id, any(video_session_id) AS selected_session_id
    FROM sonyliv.dirty_session_events
    GROUP BY dirty_operation_id
), current_dirty AS
(
    SELECT
        count() AS dirty_operations,
        hex(
            SHA256(
                arrayStringConcat(
                    arraySort(groupArray(concat(
                        toString(dirty_operation_id), ':', selected_session_id
                    ))),
                    '\n'
                )
            )
        ) AS dirty_membership_hash
    FROM current_dirty_rows
), seed AS
(
    SELECT
        any(seed_operations) AS seed_operations,
        any(seed_membership_hash) AS seed_membership_hash
    FROM sonyliv.pipeline_lineage_seeds
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
)
SELECT throwIf(
    p.snapshots = 0
    AND
    (
        d.dirty_operations != s.seed_operations
        OR d.dirty_membership_hash != s.seed_membership_hash
    ),
    'raw dirty membership changed before the first snapshot; allocate a new lineage'
)
FROM prior AS p
CROSS JOIN current_dirty AS d
CROSS JOIN seed AS s;

WITH current_seed AS
(
    SELECT
        count() AS seed_operations,
        uniqExact(video_session_id) AS seed_sessions,
        count() != uniqExact(dirty_operation_id) AS has_duplicate_operations,
        hex(
            SHA256(
                arrayStringConcat(
                    arraySort(groupArray(concat(
                        toString(dirty_operation_id), ':', video_session_id
                    ))),
                    '\n'
                )
            )
        ) AS seed_membership_hash
    FROM sonyliv.pipeline_seed_operations
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
), committed_seed AS
(
    SELECT
        any(seed_operations) AS expected_operations,
        any(seed_sessions) AS expected_sessions,
        any(seed_membership_hash) AS expected_hash
    FROM sonyliv.pipeline_lineage_seeds
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
)
SELECT throwIf(
    s.has_duplicate_operations
    OR s.seed_operations != c.expected_operations
    OR s.seed_sessions != c.expected_sessions
    OR s.seed_membership_hash != c.expected_hash,
    'pipeline seed membership differs from its committed header'
)
FROM current_seed AS s
CROSS JOIN committed_seed AS c;

SELECT throwIf(
    count() > 0,
    'pipeline seed dirty operations are not fully checkpointed'
)
FROM sonyliv.pipeline_seed_operations AS s
LEFT ANTI JOIN
(
    SELECT dirty_operation_id
    FROM sonyliv.applied_dirty_operations
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
) AS a USING (dirty_operation_id)
WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
  AND s.policy_version = {policy_version:String};

SELECT throwIf(
    count() > 0,
    'pipeline seed sessions do not all have committed state'
)
FROM
(
    SELECT DISTINCT video_session_id
    FROM sonyliv.pipeline_seed_operations
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
) AS seed_sessions
LEFT ANTI JOIN
(
    SELECT DISTINCT s.video_session_id
    FROM sonyliv.session_state_versions AS s
    INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
    WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
      AND s.policy_version = {policy_version:String}
      AND p.pipeline_run_id = {pipeline_run_id:UUID}
      AND p.policy_version = {policy_version:String}
) AS committed_sessions USING (video_session_id);

SELECT throwIf(
    count() != uniqExact(adjustment_batch_id),
    'duplicate adjustment batch IDs in the lineage ledger'
)
FROM sonyliv.published_adjustment_batches
WHERE policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID};

INSERT INTO sonyliv.delta_snapshot_batches
SELECT
    {source_delta_snapshot:UInt128},
    {pipeline_run_id:UUID},
    {policy_version:String},
    adjustment_batch_id,
    adjustment_block_hash,
    adjustment_rows
FROM sonyliv.published_adjustment_batches
WHERE policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID}
ORDER BY adjustment_batch_id
SETTINGS insert_deduplication_token = {snapshot_membership_dedup_token:String};

-- Every member must still match the exact staged boundary block committed by
-- step 20. This is checked before copying it into the immutable point snapshot.
WITH actual AS
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
        FROM sonyliv.delta_snapshot_batches
        WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
    )
    GROUP BY adjustment_batch_id
), differences AS
(
    SELECT m.adjustment_batch_id
    FROM sonyliv.delta_snapshot_batches AS m
    LEFT JOIN actual AS a USING (adjustment_batch_id)
    WHERE m.source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND m.pipeline_run_id = {pipeline_run_id:UUID}
      AND m.policy_version = {policy_version:String}
      AND
      (
          a.actual_rows != m.adjustment_rows
          OR a.actual_hash != m.adjustment_block_hash
      )
)
SELECT throwIf(
    count() > 0,
    'snapshot member boundary rows do not match the committed batch hash/count'
)
FROM differences;

INSERT INTO sonyliv.concurrency_delta_snapshots
SELECT
    {source_delta_snapshot:UInt128},
    {pipeline_run_id:UUID},
    {policy_version:String},
    a.entity,
    a.rollup_mask,
    a.service_date,
    a.boundary_time,
    a.platform,
    a.country,
    a.video_type,
    a.content_id,
    sum(toInt64(a.delta)) AS delta
FROM sonyliv.boundary_adjustments AS a
INNER JOIN
(
    SELECT adjustment_batch_id
    FROM sonyliv.delta_snapshot_batches
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
) AS m USING (adjustment_batch_id)
GROUP BY
    a.entity,
    a.rollup_mask,
    a.service_date,
    a.boundary_time,
    a.platform,
    a.country,
    a.video_type,
    a.content_id
HAVING delta != 0
SETTINGS insert_deduplication_token = {snapshot_points_dedup_token:String};

INSERT INTO sonyliv.delta_snapshots
WITH ledger AS
(
    SELECT
        adjustment_batch_id,
        adjustment_block_hash,
        adjustment_rows AS batch_adjustment_rows
    FROM sonyliv.delta_snapshot_batches
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
), ledger_summary AS
(
    SELECT
        count() AS adjustment_batches,
        sum(batch_adjustment_rows) AS total_adjustment_rows,
        hex(
            SHA256(
                arrayStringConcat(
                    arraySort(
                        groupArray(
                            concat(
                                toString(adjustment_batch_id), ':',
                                toString(adjustment_block_hash), ':',
                                toString(batch_adjustment_rows)
                            )
                        )
                    ),
                    '\n'
                )
            )
        ) AS adjustment_ledger_hash
    FROM ledger
), logical_points AS
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
), point_summary AS
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
)
SELECT
    {source_delta_snapshot:UInt128},
    {policy_version:String},
    {pipeline_run_id:UUID},
    now64(3, 'UTC'),
    ledger_summary.adjustment_batches,
    ledger_summary.total_adjustment_rows,
    ledger_summary.adjustment_ledger_hash,
    point_summary.point_rows,
    point_summary.point_hash,
    now64(3, 'UTC')
FROM ledger_summary
CROSS JOIN point_summary
SETTINGS insert_deduplication_token = {delta_snapshot_dedup_token:String};

SELECT
    source_delta_snapshot,
    policy_version,
    pipeline_run_id,
    cutoff,
    adjustment_batches,
    adjustment_rows,
    adjustment_ledger_hash,
    point_rows,
    point_hash
FROM sonyliv.delta_snapshots
WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};
