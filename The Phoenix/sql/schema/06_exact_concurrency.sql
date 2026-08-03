-- The exact-resolution serving layer. One table, additive to everything that exists.
--
--   concurrency_boundary_deltas   +1 at interval start, -1 at interval end, per second
--
-- Why this exists: the minute layer answers "how many sessions touched minute M", which is
-- the right reading for a dashboard curve but quantizes both the peak and the average to
-- minute buckets. Instantaneous concurrency only changes when an interval opens or closes,
-- so storing a delta at each boundary makes the exact value at ANY instant a cumulative
-- sum, and the exact peak provably occurs at one of these boundaries. No per-second
-- densification is ever stored or scanned: a day costs boundary-count rows, not 86,400.
--
-- Why the source is foreground_intervals and not a new run table: intervals within one
-- session never overlap (measured: 0 overlapping of 725,157, evidence exact_layer_parity),
-- so a session can never count twice at one instant and no run-merging step is needed.
-- Interval ends are exclusive already, so back-to-back intervals cancel at the shared
-- boundary inside the SummingMergeTree, and a zero-length interval nets to zero, which is
-- the correct instantaneous reading of a sub-second touch.
--
-- Known limitation, stated rather than hidden: the incremental path (03_derive_incremental)
-- re-derives touched sessions into session_minute_runs without rewriting
-- foreground_intervals, so this table reflects the last batch derive, not open-session
-- updates. The upgrade path is a second-resolution twin of session_minute_runs with the
-- same retract/assert protocol; see docs/DECISIONS.md.
CREATE TABLE IF NOT EXISTS concurrency_boundary_deltas
(
    platform    LowCardinality(String),
    country     LowCardinality(String),
    video_type  LowCardinality(String),
    content_id  Int64,
    app_version LowCardinality(String),
    audio_language LowCardinality(String),
    subtitle_language LowCardinality(String),
    player_version LowCardinality(String),
    video_resolution LowCardinality(String),
    ts          DateTime,
    delta       Int32
)
ENGINE = SummingMergeTree(delta)
-- PARTITION BY DAY. Known wart, measured and deliberately not changed under time pressure:
-- the unseen day's dirty tail (2014-12-31 to 2026-08-03) makes 189 daily partitions where one
-- holds 6,936,152 of 7,000,000 rows. A straight INSERT ... SELECT of the corpus fails with
-- TOO_MANY_PARTS. toYYYYMM is the fix and needs a full rebuild of both live databases; it is
-- recorded in docs/FINAL_CHECKLIST.md rather than applied at deploy time.
PARTITION BY toYYYYMMDD(ts)
ORDER BY (platform, country, video_type, content_id, app_version, audio_language, subtitle_language, player_version, video_resolution, ts);

-- Fires on the batch derive's insert into foreground_intervals. Zero-length intervals are
-- skipped at write time; they would collapse to zero anyway, but not writing them halves
-- nothing and costs one predicate.
CREATE MATERIALIZED VIEW IF NOT EXISTS concurrency_boundary_deltas_mv TO concurrency_boundary_deltas AS
SELECT
    platform,
    country,
    video_type,
    content_id,
    app_version,
    audio_language,
    subtitle_language,
    player_version,
    video_resolution,
    b.1 AS ts,
    b.2 AS delta
FROM foreground_intervals
ARRAY JOIN [(interval_start, 1), (interval_end, -1)] AS b
WHERE interval_start < interval_end;
