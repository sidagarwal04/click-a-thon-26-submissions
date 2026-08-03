-- The application first resolves the published generation for each requested
-- (service_date, entity, rollup_mask), then passes it as {generation:UInt64}.
-- The manifest is tiny; it can also be exposed as a dictionary.

-- Resolve current validated generation.
SELECT
    argMax(generation, published_at) AS generation
FROM sonyliv.serving_generation_manifest
WHERE service_date = {service_date:Date}
  AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
  AND rollup_mask = {rollup_mask:UInt16}
  AND policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND source_delta_snapshot = {source_delta_snapshot:UInt128};

-- Cached minute rows are exact only for positive, minute-aligned ranges inside
-- one UTC service day. Partial minutes or cross-day requests must use step 30.
WITH
    toDateTime64({range_start:String}, 3, 'UTC') AS range_start,
    toDateTime64({range_end:String}, 3, 'UTC') AS range_end
SELECT throwIf(
    range_start >= range_end
    OR range_start != toStartOfMinute(range_start)
    OR range_end != toStartOfMinute(range_end)
    OR toDate(range_start, 'UTC') != toDate(range_end - toIntervalMillisecond(1), 'UTC'),
    'minute cache requires a positive minute-aligned range within one UTC service day; route to 30_exact_metrics.sql'
);

-- Exact minute series. Missing rows are zero; the UI may fill its requested
-- time spine. No raw/session table is read.
SELECT
    minute_start,
    platform,
    country,
    video_type,
    content_id,
    minute_peak,
    active_entity_ms / 60000.0 AS minute_average
FROM sonyliv.concurrency_minute_versions
WHERE generation = {generation:UInt64}
  AND policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND source_delta_snapshot = {source_delta_snapshot:UInt128}
  AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
  AND rollup_mask = {rollup_mask:UInt16}
  AND service_date = {service_date:Date}
  AND minute_start >= toDateTime64({range_start:String}, 3, 'UTC')
  AND minute_start < toDateTime64({range_end:String}, 3, 'UTC')
  AND ({platform_filter:String} = '*' OR platform = {platform_filter:String})
  AND ({country_filter:String} = '*' OR country = {country_filter:String})
  AND ({video_type_filter:String} = '*' OR video_type = {video_type_filter:String})
  AND ({content_id_filter:Int64} = -2147483648 OR content_id = {content_id_filter:Int64})
ORDER BY minute_start, platform, country, video_type, content_id
LIMIT 1000000;

-- Exact range peak and time-weighted average for minute-aligned ranges.
SELECT
    platform,
    country,
    video_type,
    content_id,
    max(minute_peak) AS peak_concurrency,
    sum(active_entity_ms) /
        dateDiff(
            'millisecond',
            toDateTime64({range_start:String}, 3, 'UTC'),
            toDateTime64({range_end:String}, 3, 'UTC')
        ) AS average_concurrency
FROM sonyliv.concurrency_minute_versions
WHERE generation = {generation:UInt64}
  AND policy_version = {policy_version:String}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND source_delta_snapshot = {source_delta_snapshot:UInt128}
  AND entity = CAST({entity:String}, 'Enum8(\'session\' = 1, \'user\' = 2)')
  AND rollup_mask = {rollup_mask:UInt16}
  AND service_date = {service_date:Date}
  AND minute_start >= toDateTime64({range_start:String}, 3, 'UTC')
  AND minute_start < toDateTime64({range_end:String}, 3, 'UTC')
  AND ({platform_filter:String} = '*' OR platform = {platform_filter:String})
  AND ({country_filter:String} = '*' OR country = {country_filter:String})
  AND ({video_type_filter:String} = '*' OR video_type = {video_type_filter:String})
  AND ({content_id_filter:Int64} = -2147483648 OR content_id = {content_id_filter:Int64})
GROUP BY platform, country, video_type, content_id
ORDER BY peak_concurrency DESC
LIMIT 10000;

-- For partial-minute ranges, use 30_exact_metrics.sql so the denominator and
-- edge overlap remain exact rather than clipping whole minute snapshots.
-- Keep filtering, service dates, and range parameters in UTC. If a consumer
-- needs India wall-clock labels, project only the returned timestamp:
--   toTimeZone(minute_start, 'Asia/Kolkata') AS minute_start_ist
