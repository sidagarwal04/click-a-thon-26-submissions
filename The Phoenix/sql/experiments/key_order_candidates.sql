-- EXPERIMENT: candidate ORDER BY keys for concurrency_deltas, measured side by side.
--
-- Applied by scripts/key_order_experiment.sh into a scratch database. Nothing here is ever
-- applied to phoenix: TASK.md says do not reorder the existing key, and changing a sort key
-- is a modelling decision that belongs to the team, not to a measurement script.
--
-- It lives in a versioned file rather than being typed at a prompt because the rule in this
-- repo is zero ad-hoc DDL, and an experiment is not an exception to that.
--
-- Measured cardinalities on the frozen slice, which are what the candidates are built from:
--   country 1, video_type 3, platform 10, app_version 65, minute 1532, content_id 3357
--
-- Candidate A is the shipped key, reproduced here so all three are measured under identical
-- conditions rather than compared against a number captured on a different day.

CREATE TABLE IF NOT EXISTS deltas_a_shipped
(
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  Int64,
    app_version LowCardinality(String),
    minute      DateTime,
    delta       Int32
)
ENGINE = SummingMergeTree(delta)
ORDER BY (platform, country, video_type, content_id, app_version, minute);

-- Candidate B: strict low-to-high cardinality, per schema-pk-cardinality-order.
CREATE TABLE IF NOT EXISTS deltas_b_cardinality
(
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  Int64,
    app_version LowCardinality(String),
    minute      DateTime,
    delta       Int32
)
ENGINE = SummingMergeTree(delta)
ORDER BY (country, video_type, platform, app_version, minute, content_id);

-- Candidate C: the dead single-valued column dropped from the key entirely, otherwise
-- cardinality-ordered, with content_id promoted above minute so a content filter has a
-- shorter unbound prefix to cross.
CREATE TABLE IF NOT EXISTS deltas_c_no_dead_column
(
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  Int64,
    app_version LowCardinality(String),
    minute      DateTime,
    delta       Int32
)
ENGINE = SummingMergeTree(delta)
ORDER BY (video_type, platform, app_version, content_id, minute);
