-- Exact bucket metrics from signed millisecond boundaries.
--
-- Required parameters:
--   entity               'session' or 'user'
--   rollup_mask          mask from policy.yaml
--   policy/pipeline/snapshot exactly matching the published manifest
--   range_start          UTC string, inclusive
--   range_end            UTC string, exclusive
--   bucket_ms            60000, 3600000, or 86400000
--   platform_filter      '*' for any, otherwise exact normalized value
--   country_filter       '*'
--   video_type_filter    '*'
--   content_id_filter    -2147483648 for any, otherwise exact Int32
--
-- The query includes every point from UTC midnight so a range beginning in the
-- middle of a minute/day has the correct opening balance. Because intervals are
-- split at UTC midnight, each service_date independently begins at zero.

SELECT throwIf(
    count() != 1,
    'exact query source snapshot is missing or duplicated'
)
FROM sonyliv.delta_snapshots
WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};

WITH
    toDateTime64({range_start:String}, 3, 'UTC') AS range_start,
    toDateTime64({range_end:String}, 3, 'UTC') AS range_end,
    toUnixTimestamp64Milli(range_start) AS range_start_ms,
    toUnixTimestamp64Milli(range_end) AS range_end_ms,
    {bucket_ms:UInt64} AS bucket_ms,

    grouped_points AS
    (
        SELECT
            service_date,
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
          AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
          AND rollup_mask = {rollup_mask:UInt16}
          AND service_date BETWEEN toDate(range_start, 'UTC')
                               AND toDate(range_end - toIntervalMillisecond(1), 'UTC')
          AND boundary_time < range_end
          AND ({platform_filter:String} = '*' OR platform = {platform_filter:String})
          AND ({country_filter:String} = '*' OR country = {country_filter:String})
          AND ({video_type_filter:String} = '*' OR video_type = {video_type_filter:String})
          AND ({content_id_filter:Int64} = -2147483648 OR content_id = {content_id_filter:Int64})
        GROUP BY
            service_date,
            platform,
            country,
            video_type,
            content_id,
            boundary_time
        HAVING point_delta != 0
    ),

    -- Derive the result spine from logically re-summed points, never physical
    -- SummingMergeTree rows. Fully compensated old dimension groups disappear
    -- deterministically before or after background merges.
    selected_groups AS
    (
        SELECT DISTINCT
            platform,
            country,
            video_type,
            content_id
        FROM grouped_points
    ),

    curve AS
    (
        SELECT
            *,
            sum(point_delta) OVER point_window AS concurrency,
            leadInFrame(
                boundary_time,
                1,
                toDateTime64(addDays(service_date, 1), 3, 'UTC')
            ) OVER full_day_window AS next_boundary_time
        FROM grouped_points
        WINDOW
            point_window AS
            (
                PARTITION BY service_date, platform, country, video_type, content_id
                ORDER BY boundary_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ),
            full_day_window AS
            (
                PARTITION BY service_date, platform, country, video_type, content_id
                ORDER BY boundary_time
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
    ),

    clipped_segments AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            greatest(toUnixTimestamp64Milli(boundary_time), range_start_ms) AS segment_start_ms,
            least(
                toUnixTimestamp64Milli(next_boundary_time),
                range_end_ms
            ) AS segment_end_ms,
            if(
                concurrency < 0,
                toInt64(throwIf(1, 'negative concurrency invariant breach')),
                toInt64(concurrency)
            ) AS concurrency
        FROM curve
        WHERE boundary_time < range_end
          AND next_boundary_time > range_start
    ),

    segment_bucket_overlaps AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            bucket_number,
            concurrency,
            least(segment_end_ms, toInt64((bucket_number + 1) * bucket_ms))
                - greatest(segment_start_ms, toInt64(bucket_number * bucket_ms)) AS overlap_ms
        FROM clipped_segments
        ARRAY JOIN range(
            toUInt64(intDiv(segment_start_ms, toInt64(bucket_ms))),
            toUInt64(intDiv(segment_end_ms - 1, toInt64(bucket_ms)) + 1)
        ) AS bucket_number
        WHERE segment_end_ms > segment_start_ms
    ),

    bucket_metrics AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            bucket_number,
            toUInt64(max(concurrency)) AS peak_concurrency,
            toUInt64(sum(toInt128(concurrency) * toInt128(overlap_ms))) AS active_entity_ms,
            count() AS source_segments
        FROM segment_bucket_overlaps
        WHERE overlap_ms > 0
        GROUP BY
            platform,
            country,
            video_type,
            content_id,
            bucket_number
    ),

    result_spine AS
    (
        SELECT
            platform,
            country,
            video_type,
            content_id,
            bucket_number
        FROM selected_groups
        ARRAY JOIN range(
            toUInt64(intDiv(range_start_ms, toInt64(bucket_ms))),
            toUInt64(intDiv(range_end_ms - 1, toInt64(bucket_ms)) + 1)
        ) AS bucket_number
    )

SELECT
    fromUnixTimestamp64Milli(toInt64(s.bucket_number * bucket_ms), 'UTC') AS bucket_start,
    s.platform,
    s.country,
    s.video_type,
    s.content_id,
    coalesce(m.peak_concurrency, toUInt64(0)) AS peak_concurrency,
    coalesce(m.active_entity_ms, toUInt64(0)) AS active_entity_ms,
    coalesce(m.active_entity_ms, toUInt64(0)) /
        (
            least(toInt64((s.bucket_number + 1) * bucket_ms), range_end_ms)
            - greatest(toInt64(s.bucket_number * bucket_ms), range_start_ms)
        ) AS average_concurrency,
    coalesce(m.source_segments, toUInt64(0)) AS source_segments
FROM result_spine AS s
LEFT ANY JOIN bucket_metrics AS m
    ON s.platform = m.platform
   AND s.country = m.country
   AND s.video_type = m.video_type
   AND s.content_id = m.content_id
   AND s.bucket_number = m.bucket_number
ORDER BY
    bucket_start,
    s.platform,
    s.country,
    s.video_type,
    s.content_id
SETTINGS
    join_use_nulls = 0,
    max_execution_time = 30,
    max_rows_to_read = 100000000,
    max_bytes_to_read = 20000000000,
    max_result_rows = 1000000,
    result_overflow_mode = 'throw';
