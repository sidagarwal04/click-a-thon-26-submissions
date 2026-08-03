-- Run 10_reference_intervals.sql first with full_scan=0, workset_batch_id equal
-- to this adjustment batch, and oracle_run_id stable across retries.

INSERT INTO sonyliv.session_recompute_candidates
WITH
    deduplicated_events AS
    (
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
        WHERE event_time <= toDateTime64({evaluation_as_of:String}, 3, 'UTC')
          AND video_session_id IN
          (
              SELECT video_session_id
              FROM sonyliv.compaction_worksets
              WHERE pipeline_run_id = {pipeline_run_id:UUID}
                AND policy_version = {policy_version:String}
                AND adjustment_batch_id = {adjustment_batch_id:UUID}
          )
        GROUP BY video_session_id, event_time, event_type, event
    ),

    anchors AS
    (
        SELECT
            video_session_id,
            minIf(event_time, event_type = 'VideoSessionStart') AS lifecycle_start_time,
            minIf(event_time, event_type = 'VideoSessionEnd') AS terminal_end_time,
            countIf(event_type = 'VideoSessionEnd') > 0 AS has_terminal_end,
            argMinIf(user_id, tuple(event_time, selected_source_row_hash), event_type = 'VideoSessionStart')
                AS canonical_user_id,
            argMinIf(content_id, tuple(event_time, selected_source_row_hash), event_type = 'VideoSessionStart')
                AS content_id,
            argMinIf(platform, tuple(event_time, selected_source_row_hash), event_type = 'VideoSessionStart')
                AS platform,
            argMinIf(app_version, tuple(event_time, selected_source_row_hash), event_type = 'VideoSessionStart')
                AS app_version,
            argMinIf(country, tuple(event_time, selected_source_row_hash), event_type = 'VideoSessionStart')
                AS country,
            count() AS source_event_count
        FROM deduplicated_events
        GROUP BY video_session_id
        HAVING countIf(event_type = 'VideoSessionStart') > 0
    ),

    interval_arrays AS
    (
        SELECT
            video_session_id,
            arraySort(arrayDistinct(groupArray((start_time, end_time)))) AS intervals,
            count() AS interval_count
        FROM sonyliv.active_intervals_reference
        WHERE oracle_run_id = {oracle_run_id:UUID}
          AND policy_version = {policy_version:String}
        GROUP BY video_session_id
    ),

    joined AS
    (
        SELECT
            a.*,
            if(
                i.interval_count = 0,
                CAST([], 'Array(Tuple(DateTime64(3, \'UTC\'), DateTime64(3, \'UTC\')))'),
                i.intervals
            ) AS intervals
        FROM anchors AS a
        LEFT ANY JOIN interval_arrays AS i USING (video_session_id)
    )

SELECT
    {pipeline_run_id:UUID},
    {adjustment_batch_id:UUID},
    {state_revision:UInt64},
    {oracle_run_id:UUID},
    {policy_version:String},
    toDate(lifecycle_start_time, 'UTC') AS session_start_date,
    video_session_id,
    canonical_user_id,
    content_id,
    platform,
    app_version,
    country,
    if(
        empty(dictGetOrDefault('sonyliv.content_dictionary', 'video_type', content_id, '__unknown__')),
        '__unknown__',
        dictGetOrDefault('sonyliv.content_dictionary', 'video_type', content_id, '__unknown__')
    ) AS video_type,
    has_terminal_end,
    terminal_end_time,
    intervals,
    reinterpretAsUInt128(sipHash128(intervals)) AS boundary_hash,
    toUInt32(source_event_count),
    now64(3, 'UTC')
FROM joined
SETTINGS insert_deduplication_token = {candidate_dedup_token:String};

SELECT
    (SELECT count() FROM sonyliv.compaction_worksets
     WHERE pipeline_run_id = {pipeline_run_id:UUID}
       AND policy_version = {policy_version:String}
       AND adjustment_batch_id = {adjustment_batch_id:UUID}) AS workset_sessions,
    count() AS anchored_candidate_sessions,
    countIf(empty(intervals)) AS candidates_without_active_intervals
FROM sonyliv.session_recompute_candidates
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND adjustment_batch_id = {adjustment_batch_id:UUID};
