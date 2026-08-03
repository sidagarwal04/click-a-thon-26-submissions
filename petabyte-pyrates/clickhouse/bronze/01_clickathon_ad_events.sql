CREATE TABLE default.clickathon_ad_events
(
    `event_time` DateTime64(6),
    `app_id` String,
    `geo_device_id` String,
    `advertiser_id` Nullable(String),
    `ad_format` String,
    `is_filled` Int16,
    `is_impression` Int16,
    `is_click` Int16,
    `revenue` Float64,
    `id` Int64,
    `_peerdb_synced_at` DateTime64(9) DEFAULT now64(),
    `_peerdb_is_deleted` UInt8,
    `_peerdb_version` UInt64
)
ENGINE = SharedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', _peerdb_version)
PRIMARY KEY id
ORDER BY id
SETTINGS index_granularity = 8192
