-- clickhouse-client \
--   --param_source_version=1 \
--   --query "$(cat solution/sql/02_ingest_content_csv.sql)" \
--   < ch-hackathon-content-data.csv

INSERT INTO sonyliv.content_dim
(
    content_id,
    title,
    video_type,
    category,
    source_version
)
SELECT
    toInt32(content_id),
    title,
    if(empty(trim(video_type)), '__unknown__', lower(trim(video_type))),
    if(empty(trim(category)), '__unknown__', trim(category)),
    {source_version:UInt64}
FROM input(
    'content_id Int64,
     title String,
     video_type String,
     category String'
)
FORMAT CSVWithNames;

SYSTEM RELOAD DICTIONARY sonyliv.content_dictionary;
