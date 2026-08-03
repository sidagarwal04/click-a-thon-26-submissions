CREATE TABLE default.session_state_rows (
    `video_session_id` String,
    `content_id` Int64,
    `platform` String,
    `country` String,
    `event_timestamp` Int64,
    `signal` String,
    `play_state` String,
    `app_state` String,
    `is_active` UInt8
) ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY
    (video_session_id, event_timestamp) SETTINGS index_granularity = 8192