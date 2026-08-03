CREATE TABLE default.open_session_intervals (
    `video_session_id` String,
    `content_id` Int64,
    `platform` String,
    `country` String,
    `interval_start` Int64,
    `last_seen_ts` Int64,
    `version` UInt64
) ENGINE = SharedReplacingMergeTree(
    '/clickhouse/tables/{uuid}/{shard}',
    '{replica}',
    version
)
ORDER BY
    video_session_id SETTINGS index_granularity = 8192