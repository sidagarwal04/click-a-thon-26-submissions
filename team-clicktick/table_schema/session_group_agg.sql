CREATE TABLE default.session_groups_agg (
    `video_session_id` String,
    `content_id` Int64,
    `platform` String,
    `country` String,
    `group_id` UInt64,
    `is_active` UInt8,
    `group_start_ts` Int64,
    `group_end_ts` Int64,
    `started_by_timeout` UInt8
) ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY
    (video_session_id, group_id) SETTINGS index_granularity = 8192