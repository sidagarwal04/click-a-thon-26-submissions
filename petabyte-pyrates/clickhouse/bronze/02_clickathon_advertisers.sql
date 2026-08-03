CREATE TABLE default.clickathon_advertisers
(
    `advertiser_id` String,
    `vertical` String,
    `campaign_type` String,
    `_peerdb_synced_at` DateTime64(9) DEFAULT now64(),
    `_peerdb_is_deleted` UInt8,
    `_peerdb_version` UInt64
)
ENGINE = SharedReplacingMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}', _peerdb_version)
PRIMARY KEY advertiser_id
ORDER BY advertiser_id
SETTINGS index_granularity = 8192
