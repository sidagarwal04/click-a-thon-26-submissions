ATTACH TABLE _ UUID '9db14bb6-21c4-4233-a86b-a4e86b6814dd'
(
    `id` UInt32,
    `section` String,
    `key` String,
    `definition` String,
    `version` UInt16,
    `valid_from` DateTime,
    `source` String,
    `status` String
)
ENGINE = MergeTree
ORDER BY (section, key, version)
SETTINGS index_granularity = 8192
