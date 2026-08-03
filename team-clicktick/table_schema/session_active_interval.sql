CREATE TABLE default.session_active_intervals (
    `video_session_id` String,
    `content_id` Int64,
    `platform` String,
    `country` String,
    `interval_start` Int64,
    `interval_end` Int64,
    `is_open` UInt8
) ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY
    (video_session_id, interval_start) SETTINGS index_granularity = 8192