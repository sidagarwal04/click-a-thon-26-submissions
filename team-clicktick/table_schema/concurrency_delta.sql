CREATE TABLE default.concurrency_deltas (
    `platform` String,
    `country` String,
    `content_id` Int64,
    `video_type` String,
    `minute_bucket` DateTime,
    `delta` Int64
) ENGINE = SharedSummingMergeTree(
    '/clickhouse/tables/{uuid}/{shard}',
    '{replica}',
    delta
)
ORDER BY
    (
        platform,
        country,
        content_id,
        video_type,
        minute_bucket
    ) SETTINGS index_granularity = 8192