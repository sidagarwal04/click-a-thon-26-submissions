CREATE TABLE default.clickathon_geo_device
(
    `geo_device_id` String,
    `region` String,
    `country` String,
    `device_model` String,
    `os_version` String,
    `_peerdb_synced_at` DateTime64(9) DEFAULT now64(),
    `_peerdb_is_deleted` UInt8,
    `_peerdb_version` UInt64
)
ENGINE = SharedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', _peerdb_version)
PRIMARY KEY geo_device_id
ORDER BY geo_device_id
SETTINGS index_granularity = 8192
