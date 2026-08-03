CREATE TABLE default.clickathon_apps
(
    `app_id` String,
    `category` String,
    `publisher_tier` String,
    `_peerdb_synced_at` DateTime64(9) DEFAULT now64(),
    `_peerdb_is_deleted` UInt8,
    `_peerdb_version` UInt64
)
ENGINE = SharedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', _peerdb_version)
PRIMARY KEY app_id
ORDER BY app_id
SETTINGS index_granularity = 8192
