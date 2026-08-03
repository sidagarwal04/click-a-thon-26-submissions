-- Content metadata. 33,464 titles, 3,357 of them referenced by the sample events.
--
-- No dictionary. We tried DICTIONARY + dictGet first, the obvious choice for a table this
-- small, and on Cloud it returned '' for keys that provably exist: dictHas said 0 while an
-- INNER JOIN matched all 3,357 ids, and the same literal answered correctly one query
-- earlier. Dictionaries load per replica, so the answer depended on which node served the
-- query. A JOIN against 33K rows costs nothing and is deterministic.

CREATE TABLE IF NOT EXISTS content
(
    content_id Int64,
    title      String,
    video_type LowCardinality(String),
    category   LowCardinality(String),
    -- Added for the unseen day (docs/problem/spec.md), tagged "Used as a filter dimension".
    -- Sits BEFORE ingested_at on purpose: ingested_at is the ReplacingMergeTree version column and
    -- must stay last, or a positional insert writes a title string into the version and silently
    -- decides which duplicate row wins.
    show_name  LowCardinality(String),
    ingested_at DateTime DEFAULT now()
)
-- VERSIONED ON ingested_at, not bare. Without a version argument ReplacingMergeTree keeps whichever
-- row a merge happened to see last, which is part insertion order rather than anything meaningful,
-- so re-ingesting a title with a corrected category could lose the correction on any later merge.
-- Safe to use as the version here, unlike on raw_events: this column is in the original CREATE, so
-- every row has a materialised value (verified: one distinct timestamp across all 33,464 rows in
-- phoenix), rather than a DEFAULT now() added by ALTER and evaluated at read time.
ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY content_id;
