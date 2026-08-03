-- Build one immutable, exact minute generation for a service day/entity/mask.
-- Publish the matching serving_generation_manifest row only after step 40 passes.

SELECT throwIf(
    count() > 0,
    'generation already has minute rows; validate/publish it or allocate a new generation'
)
FROM sonyliv.concurrency_minute_versions
WHERE generation = {generation:UInt64}
  AND service_date = {service_date:Date}
  AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
  AND rollup_mask = {rollup_mask:UInt16};

SELECT throwIf(
    count() != 1,
    'source delta snapshot is missing or duplicated'
)
FROM sonyliv.delta_snapshots
WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
  AND policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID};

INSERT INTO sonyliv.concurrency_minute_versions
(
    generation,
    policy_version,
    pipeline_run_id,
    source_delta_snapshot,
    entity,
    rollup_mask,
    service_date,
    minute_start,
    platform,
    country,
    video_type,
    content_id,
    minute_peak,
    active_entity_ms,
    ending_concurrency,
    source_boundary_points
)
WITH
    {service_date:Date} AS selected_date,
    toDateTime64(selected_date, 3, 'UTC') AS day_start,
    toDateTime64(addDays(selected_date, 1), 3, 'UTC') AS day_end,
    toUnixTimestamp64Milli(day_start) AS day_start_ms,
    toUInt64(60000) AS minute_ms,

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
        GROUP BY
            platform,
            country,
            video_type,
            content_id,
            boundary_time
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
            least(toUnixTimestamp64Milli(next_boundary_time), day_start_ms + toInt64((minute_number + 1) * minute_ms))
                - greatest(toUnixTimestamp64Milli(boundary_time), day_start_ms + toInt64(minute_number * minute_ms)) AS overlap_ms,
            least(toUnixTimestamp64Milli(next_boundary_time), day_start_ms + toInt64((minute_number + 1) * minute_ms)) AS overlap_end_ms
        FROM curve
        ARRAY JOIN range(
            toUInt64(intDiv(toUnixTimestamp64Milli(boundary_time) - day_start_ms, toInt64(minute_ms))),
            toUInt64(intDiv(toUnixTimestamp64Milli(next_boundary_time) - day_start_ms - 1, toInt64(minute_ms)) + 1)
        ) AS minute_number
        WHERE next_boundary_time > boundary_time
          AND boundary_time < day_end
    )

SELECT
    {generation:UInt64} AS generation,
    {policy_version:String} AS policy_version,
    {pipeline_run_id:UUID} AS pipeline_run_id,
    {source_delta_snapshot:UInt128} AS source_delta_snapshot,
    CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)') AS entity,
    {rollup_mask:UInt16} AS rollup_mask,
    selected_date AS service_date,
    fromUnixTimestamp64Milli(day_start_ms + toInt64(minute_number * minute_ms), 'UTC') AS minute_start,
    platform,
    country,
    video_type,
    content_id,
    toUInt64(max(concurrency)) AS minute_peak,
    toUInt64(sum(toInt128(concurrency) * toInt128(overlap_ms))) AS active_entity_ms,
    toUInt64(argMax(concurrency, overlap_end_ms)) AS ending_concurrency,
    count() AS source_boundary_points
FROM minute_overlaps
WHERE overlap_ms > 0
GROUP BY
    platform,
    country,
    video_type,
    content_id,
    minute_number
HAVING minute_peak > 0 OR active_entity_ms > 0 OR ending_concurrency > 0
SETTINGS
    insert_deduplication_token = {generation_dedup_token:String},
    max_execution_time = 60,
    max_rows_to_read = 100000000,
    max_bytes_to_read = 20000000000;
