-- Convert normalized interval-map changes into signed point corrections.
--
-- Initial backfill and incremental corrections deliberately use the same path:
--   1. Drain append-only dirty operation IDs not present in applied_dirty_operations.
--   2. Recompute only those sessions using the state query from step 10.
--   3. Run steps 12-13 to persist previous and replacement interval maps in
--      entity_interval_changes with change_sign -1 and +1 respectively and to
--      install the versioned session/entity state needed by future corrections.
--   4. When a session changes, recompute every affected canonical user across
--      all that user's current sessions before producing the user's -1/+1 maps.
--   5. Run this file once with deterministic insert tokens, then checkpoint the
--      dirty operations with step 14. There is no state-bypassing bootstrap path.

SELECT throwIf(
    count() > 0,
    'adjustment_batch_id is already published; never reuse a published batch ID'
)
FROM sonyliv.published_adjustment_batches
WHERE adjustment_batch_id = {adjustment_batch_id:UUID};

SELECT throwIf(
    count() = 0
    OR countIf(
        lease_owner != {lease_owner:String}
        OR lease_epoch != {lease_epoch:UInt64}
        OR lease_expires_at <= now64(3, 'UTC')
    ) > 0,
    'compactor lease missing, expired, or fenced before boundary commit'
)
FROM sonyliv.compaction_worksets
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND adjustment_batch_id = {adjustment_batch_id:UUID};

SELECT throwIf(
    countIf(state_revision >= {state_revision:UInt64}) > 0,
    'state_revision must be strictly greater than every committed revision in the lineage'
)
FROM sonyliv.published_adjustment_batches
WHERE pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};

-- ---- Interval-map differences -> exact boundary adjustments --------------
INSERT INTO sonyliv.boundary_adjustments
(
    adjustment_operation_id,
    adjustment_batch_id,
    state_revision,
    source_entity_id,
    entity,
    rollup_mask,
    service_date,
    boundary_time,
    platform,
    country,
    video_type,
    content_id,
    delta
)
WITH
    deduplicated_change_rows AS
    (
        SELECT DISTINCT
            adjustment_batch_id,
            state_revision,
            source_entity_id,
            entity,
            rollup_mask,
            platform,
            country,
            video_type,
            content_id,
            change_sign,
            intervals
        FROM sonyliv.entity_interval_changes
        WHERE adjustment_batch_id = {adjustment_batch_id:UUID}
    ),

    changed_intervals AS
    (
        SELECT
            *,
            arrayJoin(intervals) AS interval
        FROM deduplicated_change_rows
        WHERE interval.2 > interval.1
    ),

    day_slices AS
    (
        SELECT
            *,
            addDays(toDate(interval.1, 'UTC'), day_offset) AS service_date,
            greatest(interval.1, toDateTime64(service_date, 3, 'UTC')) AS slice_start,
            least(interval.2, toDateTime64(addDays(service_date, 1), 3, 'UTC')) AS slice_end
        FROM changed_intervals
        ARRAY JOIN range(
            toUInt32(
                dateDiff(
                    'day',
                    toDate(interval.1, 'UTC'),
                    toDate(interval.2 - toIntervalMillisecond(1), 'UTC')
                ) + 1
            )
        ) AS day_offset
    ),

    endpoints AS
    (
        SELECT
            *,
            arrayJoin([
                (slice_start, toInt8(1)),
                (slice_end, toInt8(-1))
            ]) AS endpoint
        FROM day_slices
        WHERE slice_end > slice_start
    )

SELECT
    reinterpretAsUInt128(
        sipHash128(
            adjustment_batch_id,
            state_revision,
            source_entity_id,
            entity,
            rollup_mask,
            service_date,
            endpoint.1,
            platform,
            country,
            video_type,
            content_id,
            change_sign,
            endpoint.2
        )
    ) AS adjustment_operation_id,
    adjustment_batch_id,
    state_revision,
    source_entity_id,
    entity,
    rollup_mask,
    service_date,
    endpoint.1 AS boundary_time,
    platform,
    country,
    video_type,
    content_id,
    toInt8(change_sign * endpoint.2) AS delta
FROM endpoints
SETTINGS insert_deduplication_token = {boundary_adjustments_dedup_token:String};

-- Stable-token insert deduplication is the crash-retry mechanism on replicated
-- ClickHouse/ClickHouse Cloud. The logical operation-ID gate detects any failure
-- of that contract before a serving generation is published.
SELECT throwIf(
    count() != uniqExact(adjustment_operation_id),
    'duplicate boundary operation IDs detected; do not publish a serving generation'
)
FROM sonyliv.boundary_adjustments
WHERE adjustment_batch_id = {adjustment_batch_id:UUID};

INSERT INTO sonyliv.published_adjustment_batches
SELECT
    {adjustment_batch_id:UUID},
    {policy_version:String},
    {pipeline_run_id:UUID},
    {source_snapshot_hash:String},
    hex(
        SHA256(
            arrayStringConcat(
                arraySort(groupArray(toString(adjustment_operation_id))),
                '\n'
            )
        )
    ) AS adjustment_block_hash,
    count() AS adjustment_rows,
    {state_revision:UInt64},
    {lease_epoch:UInt64},
    now64(3, 'UTC') AS published_at
FROM sonyliv.boundary_adjustments
WHERE adjustment_batch_id = {adjustment_batch_id:UUID}
SETTINGS insert_deduplication_token = {adjustment_ledger_dedup_token:String};
