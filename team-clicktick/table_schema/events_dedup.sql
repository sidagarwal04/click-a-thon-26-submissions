CREATE TABLE default.events_dedup (
    `content_id` Int64,
    `video_session_id` String,
    `user_id` String,
    `event_type` String,
    `event` String,
    `event_timestamp` Int64,
    `platform` String,
    `app_version` String,
    `country` String,
    `audio_language` String,
    `subtitle_language` String,
    `player_version` String,
    `session_start_epoch` Int64
) ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY
    (video_session_id, event_timestamp) SETTINGS index_granularity = 8192