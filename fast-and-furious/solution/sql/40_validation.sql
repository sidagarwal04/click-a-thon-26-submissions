-- Publication gates. Every query below must return zero bad rows (or the stated
-- equality) before a minute generation is added to the serving manifest.

SELECT throwIf(count() != 1, 'validation snapshot is missing or duplicated')
FROM sonyliv.delta_snapshots
WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
  AND pipeline_run_id = {pipeline_run_id:UUID}
  AND policy_version = {policy_version:String};

-- 1. Interval shape.
SELECT throwIf(count() > 0, 'invalid or empty reference intervals') AS invalid_or_empty_intervals
FROM sonyliv.active_intervals_reference
WHERE oracle_run_id = {oracle_run_id:UUID}
  AND policy_version = {policy_version:String}
  AND end_time <= start_time;

-- 2. No overlap inside a session after normalization.
WITH ordered AS
(
    SELECT
        video_session_id,
        start_time,
        end_time,
        lagInFrame(end_time, 1, toDateTime64(0, 3, 'UTC')) OVER
        (
            PARTITION BY video_session_id
            ORDER BY start_time, end_time
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS previous_end
    FROM sonyliv.active_intervals_reference
    WHERE oracle_run_id = {oracle_run_id:UUID}
      AND policy_version = {policy_version:String}
)
SELECT throwIf(count() > 0, 'overlapping normalized intervals') AS overlapping_intervals
FROM ordered
WHERE start_time < previous_end;

-- 3. First VideoSessionEnd is terminal.
WITH first_ends AS
(
    SELECT video_session_id, min(event_time) AS first_end
    FROM sonyliv.raw_events
    WHERE event_type = 'VideoSessionEnd'
    GROUP BY video_session_id
)
SELECT throwIf(count() > 0, 'active interval extends after first terminal End') AS intervals_after_terminal_end
FROM sonyliv.active_intervals_reference AS i
INNER JOIN first_ends AS e USING (video_session_id)
WHERE i.policy_version = {policy_version:String}
  AND i.oracle_run_id = {oracle_run_id:UUID}
  AND i.end_time > e.first_end;

-- 4. Every per-day/dimension boundary map balances to zero. Daily splitting
-- emits -1 at midnight under the prior service_date and +1 under the next.
SELECT throwIf(count() > 0, 'unbalanced daily dimension boundary map') AS unbalanced_dimension_days
FROM
(
    SELECT
        entity,
        rollup_mask,
        service_date,
        platform,
        country,
        video_type,
        content_id,
        sum(delta) AS balance
    FROM sonyliv.concurrency_delta_snapshots
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
    GROUP BY
        entity,
        rollup_mask,
        service_date,
        platform,
        country,
        video_type,
        content_id
    HAVING balance != 0
);

-- 5. Prefix concurrency never becomes negative.
WITH points AS
(
    SELECT
        entity,
        rollup_mask,
        service_date,
        platform,
        country,
        video_type,
        content_id,
        boundary_time,
        sum(delta) AS d
    FROM sonyliv.concurrency_delta_snapshots
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
    GROUP BY
        entity,
        rollup_mask,
        service_date,
        platform,
        country,
        video_type,
        content_id,
        boundary_time
), curve AS
(
    SELECT
        *,
        sum(d) OVER
        (
            PARTITION BY entity, rollup_mask, service_date,
                         platform, country, video_type, content_id
            ORDER BY boundary_time
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS concurrency
    FROM points
)
SELECT throwIf(count() > 0, 'negative concurrency prefix') AS negative_curve_points
FROM curve
WHERE concurrency < 0;

-- 6. Mask-0 global session deltas equal the sum of platform-mask deltas at every
-- timestamp. This catches dropped or multiply-attributed sessions.
WITH global_points AS
(
    SELECT service_date, boundary_time, sum(delta) AS d
    FROM sonyliv.concurrency_delta_snapshots
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND entity = 'session' AND rollup_mask = 0
    GROUP BY service_date, boundary_time
), platform_points AS
(
    SELECT service_date, boundary_time, sum(delta) AS d
    FROM sonyliv.concurrency_delta_snapshots
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
      AND entity = 'session' AND rollup_mask = 1
    GROUP BY service_date, boundary_time
)
SELECT throwIf(count() > 0, 'global and platform delta points disagree') AS global_platform_point_mismatches
FROM global_points AS g
FULL OUTER JOIN platform_points AS p USING (service_date, boundary_time)
WHERE coalesce(g.d, toInt64(0)) != coalesce(p.d, toInt64(0));

-- 7. Content enrichment coverage. Supplied data must return zero misses; unseen
-- misses remain explicit __unknown__ values and alert, never silently drop rows.
SELECT throwIf(count() > 0, 'content dictionary misses') AS content_dictionary_misses
FROM
(
    SELECT DISTINCT content_id
    FROM sonyliv.raw_events
) AS r
WHERE NOT dictHas('sonyliv.content_dictionary', r.content_id);

-- 8. Session-static dimension drift is visible. These are metrics, not a gate:
-- supplied counts are user=120, content=1, platform=95, app_version=0, country=0.
WITH anchors AS
(
    SELECT
        video_session_id,
        argMinIf(user_id, event_time, event_type = 'VideoSessionStart') AS start_user,
        argMinIf(content_id, event_time, event_type = 'VideoSessionStart') AS start_content,
        argMinIf(platform, event_time, event_type = 'VideoSessionStart') AS start_platform,
        argMinIf(app_version, event_time, event_type = 'VideoSessionStart') AS start_app_version,
        argMinIf(country, event_time, event_type = 'VideoSessionStart') AS start_country
    FROM sonyliv.raw_events
    GROUP BY video_session_id
)
SELECT
    uniqExactIf(r.video_session_id, r.user_id != a.start_user) AS user_drift_sessions,
    uniqExactIf(r.video_session_id, r.content_id != a.start_content) AS content_drift_sessions,
    uniqExactIf(r.video_session_id, r.platform != a.start_platform) AS platform_drift_sessions,
    uniqExactIf(r.video_session_id, r.app_version != a.start_app_version) AS app_version_drift_sessions,
    uniqExactIf(r.video_session_id, r.country != a.start_country) AS country_drift_sessions
FROM sonyliv.raw_events AS r
INNER JOIN anchors AS a USING (video_session_id);

-- 9. Idempotence/control-plane checks.
WITH current_batches AS
(
    SELECT
        adjustment_batch_id,
        argMax(status, tuple(completed_at, started_at)) AS current_status
    FROM sonyliv.processing_batches
    GROUP BY adjustment_batch_id
)
SELECT
    (
        SELECT throwIf(
            count() != uniqExact(adjustment_batch_id),
            'duplicate published adjustment batch IDs'
        )
        FROM sonyliv.published_adjustment_batches
        WHERE pipeline_run_id = {pipeline_run_id:UUID}
          AND policy_version = {policy_version:String}
    ) AS duplicate_published_batch_rows,
    countIf(current_status = 'failed') AS currently_failed_batches
FROM current_batches;

SELECT throwIf(
    count() != uniqExact(adjustment_operation_id),
    'duplicate boundary operation IDs'
) AS duplicate_boundary_operations
FROM sonyliv.boundary_adjustments AS a
INNER JOIN
(
    SELECT adjustment_batch_id
    FROM sonyliv.delta_snapshot_batches
    WHERE source_delta_snapshot = {source_delta_snapshot:UInt128}
      AND pipeline_run_id = {pipeline_run_id:UUID}
      AND policy_version = {policy_version:String}
) AS m USING (adjustment_batch_id);

-- 10. Cache conservation for the global session mask. These two totals must be
-- equal for the selected policy/date/generation.
WITH
    (
        SELECT sum(
            dateDiff(
                'millisecond',
                greatest(start_time, toDateTime64({service_date:Date}, 3, 'UTC')),
                least(end_time, toDateTime64(addDays({service_date:Date}, 1), 3, 'UTC'))
            )
        )
        FROM sonyliv.active_intervals_reference
        WHERE oracle_run_id = {oracle_run_id:UUID}
          AND policy_version = {policy_version:String}
          AND start_time < toDateTime64(addDays({service_date:Date}, 1), 3, 'UTC')
          AND end_time > toDateTime64({service_date:Date}, 3, 'UTC')
    ) AS clipped_interval_ms_before_day_split,
    (
        SELECT sum(active_entity_ms)
        FROM sonyliv.concurrency_minute_versions
        WHERE generation = {generation:UInt64}
          AND policy_version = {policy_version:String}
          AND pipeline_run_id = {pipeline_run_id:UUID}
          AND source_delta_snapshot = {source_delta_snapshot:UInt128}
          AND service_date = {service_date:Date}
          AND entity = 'session'
          AND rollup_mask = 0
    ) AS cached_active_session_ms
SELECT throwIf(
    coalesce(clipped_interval_ms_before_day_split, toUInt64(0))
        != coalesce(cached_active_session_ms, toUInt64(0)),
    'cached active milliseconds do not equal clipped reference intervals'
) AS active_millisecond_conservation;
