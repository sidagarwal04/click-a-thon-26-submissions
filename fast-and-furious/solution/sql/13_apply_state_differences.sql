-- Turn staged touched-session candidates into old/new entity interval maps.
-- Every INSERT uses a stable retry token. Repeated change rows are also
-- logically deduplicated by step 20 before boundary publication.

-- Affected users include both the previous and replacement session owner.
INSERT INTO sonyliv.affected_compaction_users
WITH candidate_ids AS
(
    SELECT video_session_id
    FROM sonyliv.session_recompute_candidates
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
), old_users AS
(
    SELECT
        video_session_id,
        argMax(canonical_user_id, state_revision) AS canonical_user_id
    FROM sonyliv.session_state_versions AS s
    INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
    WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
      AND s.policy_version = {policy_version:String}
      AND p.pipeline_run_id = {pipeline_run_id:UUID}
      AND p.policy_version = {policy_version:String}
      AND video_session_id IN candidate_ids
    GROUP BY video_session_id
)
SELECT DISTINCT
    {pipeline_run_id:UUID},
    {policy_version:String},
    {adjustment_batch_id:UUID},
    canonical_user_id
FROM
(
    SELECT canonical_user_id FROM old_users
    UNION ALL
    SELECT canonical_user_id
    FROM sonyliv.session_recompute_candidates
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
)
SETTINGS insert_deduplication_token = {affected_users_dedup_token:String};

-- Retract current session maps.
INSERT INTO sonyliv.entity_interval_changes
(
    adjustment_batch_id, state_revision, entity, source_entity_id,
    rollup_mask, platform, country, video_type, content_id,
    change_sign, intervals
)
WITH current_old AS
(
    SELECT
        source_entity_id,
        rollup_mask,
        platform,
        country,
        video_type,
        content_id,
        argMax(tuple(is_deleted, intervals), tuple(state_revision, adjustment_batch_id)) AS current
    FROM sonyliv.entity_state_versions AS s
    INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
    WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
      AND s.policy_version = {policy_version:String}
      AND p.pipeline_run_id = {pipeline_run_id:UUID}
      AND p.policy_version = {policy_version:String}
      AND entity = 'session'
      AND source_entity_id IN
      (
          SELECT video_session_id
          FROM sonyliv.session_recompute_candidates
          WHERE pipeline_run_id = {pipeline_run_id:UUID}
            AND policy_version = {policy_version:String}
            AND adjustment_batch_id = {adjustment_batch_id:UUID}
      )
    GROUP BY source_entity_id, rollup_mask, platform, country, video_type, content_id
    HAVING current.1 = 0
)
SELECT
    {adjustment_batch_id:UUID},
    {state_revision:UInt64},
    CAST('session', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    source_entity_id,
    rollup_mask,
    platform,
    country,
    video_type,
    content_id,
    toInt8(-1),
    current.2
FROM current_old
SETTINGS insert_deduplication_token = {old_session_changes_dedup_token:String};

-- Publish replacement session maps for every configured mask.
INSERT INTO sonyliv.entity_interval_changes
(
    adjustment_batch_id, state_revision, entity, source_entity_id,
    rollup_mask, platform, country, video_type, content_id,
    change_sign, intervals
)
WITH [toUInt16(0), 1, 2, 4, 8, 3, 5, 9, 12, 15] AS masks
SELECT
    {adjustment_batch_id:UUID},
    {state_revision:UInt64},
    CAST('session', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    video_session_id,
    mask,
    if(bitAnd(mask, 1) != 0, platform, '__all__'),
    if(bitAnd(mask, 2) != 0, country, '__all__'),
    if(bitAnd(mask, 8) != 0, video_type, '__all__'),
    if(bitAnd(mask, 4) != 0, content_id, toInt32(0)),
    toInt8(1),
    intervals
FROM sonyliv.session_recompute_candidates
ARRAY JOIN masks AS mask
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {new_session_changes_dedup_token:String};

-- Retract current user maps before the session-state replacement is installed.
INSERT INTO sonyliv.entity_interval_changes
(
    adjustment_batch_id, state_revision, entity, source_entity_id,
    rollup_mask, platform, country, video_type, content_id,
    change_sign, intervals
)
WITH current_old AS
(
    SELECT
        source_entity_id,
        rollup_mask,
        platform,
        country,
        video_type,
        content_id,
        argMax(tuple(is_deleted, intervals), tuple(state_revision, adjustment_batch_id)) AS current
    FROM sonyliv.entity_state_versions AS s
    INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
    WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
      AND s.policy_version = {policy_version:String}
      AND p.pipeline_run_id = {pipeline_run_id:UUID}
      AND p.policy_version = {policy_version:String}
      AND entity = 'user'
      AND source_entity_id IN
      (
          SELECT canonical_user_id
          FROM sonyliv.affected_compaction_users
          WHERE pipeline_run_id = {pipeline_run_id:UUID}
            AND policy_version = {policy_version:String}
            AND adjustment_batch_id = {adjustment_batch_id:UUID}
      )
    GROUP BY source_entity_id, rollup_mask, platform, country, video_type, content_id
    HAVING current.1 = 0
)
SELECT
    {adjustment_batch_id:UUID},
    {state_revision:UInt64},
    CAST('user', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    source_entity_id,
    rollup_mask,
    platform,
    country,
    video_type,
    content_id,
    toInt8(-1),
    current.2
FROM current_old
SETTINGS insert_deduplication_token = {old_user_changes_dedup_token:String};

-- Tombstone session dimension keys that disappear in the replacement.
INSERT INTO sonyliv.entity_state_versions
WITH
    [toUInt16(0), 1, 2, 4, 8, 3, 5, 9, 12, 15] AS masks,
    current_old AS
    (
        SELECT
            source_entity_id,
            rollup_mask,
            platform,
            country,
            video_type,
            content_id,
            argMax(is_deleted, tuple(state_revision, adjustment_batch_id)) AS is_deleted
        FROM sonyliv.entity_state_versions AS s
        INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
        WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
          AND s.policy_version = {policy_version:String}
          AND p.pipeline_run_id = {pipeline_run_id:UUID}
          AND p.policy_version = {policy_version:String}
          AND entity = 'session'
          AND source_entity_id IN
          (
              SELECT video_session_id
              FROM sonyliv.session_recompute_candidates
              WHERE pipeline_run_id = {pipeline_run_id:UUID}
                AND policy_version = {policy_version:String}
                AND adjustment_batch_id = {adjustment_batch_id:UUID}
          )
        GROUP BY source_entity_id, rollup_mask, platform, country, video_type, content_id
        HAVING is_deleted = 0
    ),
    new_keys AS
    (
        SELECT DISTINCT
            video_session_id AS source_entity_id,
            mask AS rollup_mask,
            if(bitAnd(mask, 1) != 0, platform, '__all__') AS platform,
            if(bitAnd(mask, 2) != 0, country, '__all__') AS country,
            if(bitAnd(mask, 8) != 0, video_type, '__all__') AS video_type,
            if(bitAnd(mask, 4) != 0, content_id, toInt32(0)) AS content_id
        FROM sonyliv.session_recompute_candidates
        ARRAY JOIN masks AS mask
        WHERE pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND adjustment_batch_id = {adjustment_batch_id:UUID}
    )
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    CAST('session', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    o.source_entity_id,
    o.rollup_mask,
    o.platform,
    o.country,
    o.video_type,
    o.content_id,
    {state_revision:UInt64},
    {adjustment_batch_id:UUID},
    true,
    CAST([], 'Array(Tuple(DateTime64(3, \'UTC\'), DateTime64(3, \'UTC\')))')
FROM current_old AS o
LEFT ANTI JOIN new_keys AS n
    ON o.source_entity_id = n.source_entity_id
   AND o.rollup_mask = n.rollup_mask
   AND o.platform = n.platform
   AND o.country = n.country
   AND o.video_type = n.video_type
   AND o.content_id = n.content_id
SETTINGS insert_deduplication_token = {session_tombstones_dedup_token:String};

-- Install replacement session maps.
INSERT INTO sonyliv.entity_state_versions
WITH [toUInt16(0), 1, 2, 4, 8, 3, 5, 9, 12, 15] AS masks
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    CAST('session', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    video_session_id,
    mask,
    if(bitAnd(mask, 1) != 0, platform, '__all__'),
    if(bitAnd(mask, 2) != 0, country, '__all__'),
    if(bitAnd(mask, 8) != 0, video_type, '__all__'),
    if(bitAnd(mask, 4) != 0, content_id, toInt32(0)),
    {state_revision:UInt64},
    {adjustment_batch_id:UUID},
    false,
    intervals
FROM sonyliv.session_recompute_candidates
ARRAY JOIN masks AS mask
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {session_state_maps_dedup_token:String};

INSERT INTO sonyliv.session_state_versions
SELECT
    {pipeline_run_id:UUID},
    policy_version,
    session_start_date,
    video_session_id,
    state_revision,
    now64(3, 'UTC'),
    adjustment_batch_id,
    canonical_user_id,
    content_id,
    platform,
    app_version,
    country,
    video_type,
    has_terminal_end,
    terminal_end_time,
    intervals,
    boundary_hash,
    source_event_count,
    CAST([], 'Array(LowCardinality(String))')
FROM sonyliv.session_recompute_candidates
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {session_state_versions_dedup_token:String};

-- Rebuild current user maps from all current session states of affected users.
INSERT INTO sonyliv.user_recompute_candidates
WITH
    [toUInt16(0), 1, 2, 4, 8, 3, 5, 9, 12, 15] AS masks,
    candidate_ids AS
    (
        SELECT video_session_id
        FROM sonyliv.session_recompute_candidates
        WHERE pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND adjustment_batch_id = {adjustment_batch_id:UUID}
    ),
    committed_current_sessions AS
    (
        SELECT
            video_session_id,
            argMax(
                tuple(canonical_user_id, content_id, platform, country, video_type, intervals),
                state_revision
            ) AS current
        FROM sonyliv.session_state_versions AS s
        INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
        WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
          AND s.policy_version = {policy_version:String}
          AND p.pipeline_run_id = {pipeline_run_id:UUID}
          AND p.policy_version = {policy_version:String}
        GROUP BY video_session_id
    ),
    session_overlay AS
    (
        SELECT video_session_id, current
        FROM committed_current_sessions
        WHERE video_session_id NOT IN candidate_ids

        UNION ALL

        SELECT
            video_session_id,
            tuple(canonical_user_id, content_id, platform, country, video_type, intervals) AS current
        FROM sonyliv.session_recompute_candidates
        WHERE pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND adjustment_batch_id = {adjustment_batch_id:UUID}
    ),
    current_sessions AS
    (
        SELECT *
        FROM session_overlay
        WHERE current.1 IN
        (
            SELECT canonical_user_id
            FROM sonyliv.affected_compaction_users
            WHERE pipeline_run_id = {pipeline_run_id:UUID}
              AND policy_version = {policy_version:String}
              AND adjustment_batch_id = {adjustment_batch_id:UUID}
        )
    ),
    masked_intervals AS
    (
        SELECT
            current.1 AS canonical_user_id,
            mask AS rollup_mask,
            if(bitAnd(mask, 1) != 0, current.3, '__all__') AS platform,
            if(bitAnd(mask, 2) != 0, current.4, '__all__') AS country,
            if(bitAnd(mask, 8) != 0, current.5, '__all__') AS video_type,
            if(bitAnd(mask, 4) != 0, current.2, toInt32(0)) AS content_id,
            interval.1 AS start_time,
            interval.2 AS end_time
        FROM current_sessions
        ARRAY JOIN current.6 AS interval
        ARRAY JOIN masks AS mask
    ),
    marked AS
    (
        SELECT
            *,
            start_time > max(end_time) OVER
            (
                PARTITION BY canonical_user_id, rollup_mask, platform, country, video_type, content_id
                ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS starts_new_island
        FROM masked_intervals
    ),
    numbered AS
    (
        SELECT
            *,
            sum(starts_new_island) OVER
            (
                PARTITION BY canonical_user_id, rollup_mask, platform, country, video_type, content_id
                ORDER BY start_time, end_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS island_number
        FROM marked
    ),
    merged AS
    (
        SELECT
            canonical_user_id,
            rollup_mask,
            platform,
            country,
            video_type,
            content_id,
            island_number,
            min(start_time) AS start_time,
            max(end_time) AS end_time
        FROM numbered
        GROUP BY canonical_user_id, rollup_mask, platform, country, video_type, content_id, island_number
    )
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    {adjustment_batch_id:UUID},
    {state_revision:UInt64},
    canonical_user_id,
    rollup_mask,
    platform,
    country,
    video_type,
    content_id,
    arraySort(groupArray((start_time, end_time)))
FROM merged
GROUP BY canonical_user_id, rollup_mask, platform, country, video_type, content_id
SETTINGS insert_deduplication_token = {user_candidates_dedup_token:String};

-- Publish replacement user maps.
INSERT INTO sonyliv.entity_interval_changes
(
    adjustment_batch_id, state_revision, entity, source_entity_id,
    rollup_mask, platform, country, video_type, content_id,
    change_sign, intervals
)
SELECT
    adjustment_batch_id,
    state_revision,
    CAST('user', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    canonical_user_id,
    rollup_mask,
    platform,
    country,
    video_type,
    content_id,
    toInt8(1),
    intervals
FROM sonyliv.user_recompute_candidates
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {new_user_changes_dedup_token:String};

-- Tombstone user keys that disappear.
INSERT INTO sonyliv.entity_state_versions
WITH current_old AS
(
    SELECT
        source_entity_id,
        rollup_mask,
        platform,
        country,
        video_type,
        content_id,
        argMax(is_deleted, tuple(state_revision, adjustment_batch_id)) AS is_deleted
    FROM sonyliv.entity_state_versions AS s
    INNER JOIN sonyliv.published_adjustment_batches AS p USING (adjustment_batch_id)
    WHERE s.pipeline_run_id = {pipeline_run_id:UUID}
      AND s.policy_version = {policy_version:String}
      AND p.pipeline_run_id = {pipeline_run_id:UUID}
      AND p.policy_version = {policy_version:String}
      AND entity = 'user'
      AND source_entity_id IN
      (
          SELECT canonical_user_id
          FROM sonyliv.affected_compaction_users
          WHERE pipeline_run_id = {pipeline_run_id:UUID}
            AND policy_version = {policy_version:String}
            AND adjustment_batch_id = {adjustment_batch_id:UUID}
      )
    GROUP BY source_entity_id, rollup_mask, platform, country, video_type, content_id
    HAVING is_deleted = 0
), new_keys AS
(
    SELECT DISTINCT
        canonical_user_id AS source_entity_id,
        rollup_mask,
        platform,
        country,
        video_type,
        content_id
    FROM sonyliv.user_recompute_candidates
    WHERE pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND adjustment_batch_id = {adjustment_batch_id:UUID}
)
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    CAST('user', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    o.source_entity_id,
    o.rollup_mask,
    o.platform,
    o.country,
    o.video_type,
    o.content_id,
    {state_revision:UInt64},
    {adjustment_batch_id:UUID},
    true,
    CAST([], 'Array(Tuple(DateTime64(3, \'UTC\'), DateTime64(3, \'UTC\')))')
FROM current_old AS o
LEFT ANTI JOIN new_keys AS n
    ON o.source_entity_id = n.source_entity_id
   AND o.rollup_mask = n.rollup_mask
   AND o.platform = n.platform
   AND o.country = n.country
   AND o.video_type = n.video_type
   AND o.content_id = n.content_id
SETTINGS insert_deduplication_token = {user_tombstones_dedup_token:String};

INSERT INTO sonyliv.entity_state_versions
SELECT
    {pipeline_run_id:UUID},
    {policy_version:String},
    CAST('user', 'Enum8(\'session\' = 1, \'user\' = 2)'),
    canonical_user_id,
    rollup_mask,
    platform,
    country,
    video_type,
    content_id,
    state_revision,
    adjustment_batch_id,
    false,
    intervals
FROM sonyliv.user_recompute_candidates
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {user_state_maps_dedup_token:String};
