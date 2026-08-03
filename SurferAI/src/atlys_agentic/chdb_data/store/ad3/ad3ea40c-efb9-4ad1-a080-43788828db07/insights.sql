ATTACH TABLE _ UUID '1783b6a4-66ab-4c18-a30c-1bbfbeceda92'
(
    `finding_key` String,
    `spec_id` String,
    `question` String,
    `answer_md` String,
    `confidence` Float32,
    `cuts_json` String,
    `trace_id` String,
    `created_at` DateTime
)
ENGINE = MergeTree
ORDER BY (finding_key, spec_id, created_at)
SETTINGS index_granularity = 8192
