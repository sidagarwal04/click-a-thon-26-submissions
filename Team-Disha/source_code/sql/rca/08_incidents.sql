-- Cluster day signals into incidents (gap-and-island) entirely in ClickHouse.
-- Combo-over-single preference + eCPM layer merge; letter ids assigned by window_start.

TRUNCATE TABLE rca_incidents;

INSERT INTO rca_incidents
WITH
ordered AS
(
    SELECT
        *,
        lagInFrame(event_date) OVER (
            PARTITION BY primary_factor, segment_key
            ORDER BY event_date
        ) AS prev_day
    FROM rca_day_signals
),
marked AS
(
    SELECT
        *,
        toUInt8(prev_day IS NULL OR dateDiff('day', prev_day, event_date) > 1) AS is_new
    FROM ordered
),
islands AS
(
    SELECT
        *,
        sum(is_new) OVER (
            PARTITION BY primary_factor, segment_key
            ORDER BY event_date
        ) AS island_id
    FROM marked
),
raw_clusters AS
(
    SELECT
        primary_factor,
        segment_key,
        anyLast(segment) AS segment,
        anyLast(source) AS source,
        anyLast(shape) AS shape,
        min(event_date) AS window_start,
        max(event_date) AS window_end,
        toUInt32(count()) AS n_days,
        -- Alias names must not shadow row-level cols used inside argMax
        sum(severity) AS cluster_severity,
        toUInt8(max(hidden_globally)) AS cluster_hidden,
        multiIf(
            primary_factor = 'fill_rate',
            argMax(event_date, (hidden_globally * 1e12) + severity),
            primary_factor = 'ecpm',
            argMax(event_date, ((1 - hidden_globally) * 1e12) + severity),
            argMax(event_date, severity)
        ) AS probe_day,
        argMax(evidence_json, severity) AS evidence_json,
        island_id
    FROM islands
    GROUP BY primary_factor, segment_key, island_id
),
-- Prefer combo (x) over overlapping single-dim fill clusters
fill_ranked AS
(
    SELECT
        primary_factor,
        segment_key,
        segment,
        source,
        shape,
        window_start,
        window_end,
        n_days,
        cluster_severity AS severity,
        cluster_hidden AS hidden_globally,
        probe_day,
        evidence_json,
        island_id,
        toUInt8(position(segment, ' x ') > 0) AS is_combo
    FROM raw_clusters
    WHERE primary_factor = 'fill_rate'
),
fill_drop AS
(
    SELECT a.primary_factor AS primary_factor, a.segment_key AS segment_key, a.island_id AS island_id
    FROM fill_ranked AS a
    INNER JOIN fill_ranked AS b
        ON a.window_start <= b.window_end AND b.window_start <= a.window_end
    WHERE a.is_combo = 1
      AND b.is_combo = 0
      AND (
          position(a.segment, replaceRegexpOne(b.segment, '^[^=]+=', '')) > 0
          OR position(a.segment, b.segment) > 0
      )
),
fill_kept AS
(
    -- Anti-join: ClickHouse LEFT JOIN defaults String to '' (not NULL)
    SELECT f.*
    FROM fill_ranked AS f
    WHERE (f.primary_factor, f.segment_key, f.island_id) NOT IN
    (
        SELECT primary_factor, segment_key, island_id FROM fill_drop
    )
),
non_fill AS
(
    SELECT
        primary_factor,
        segment_key,
        segment,
        source,
        shape,
        window_start,
        window_end,
        n_days,
        cluster_severity AS severity,
        cluster_hidden AS hidden_globally,
        probe_day,
        evidence_json,
        island_id
    FROM raw_clusters
    WHERE primary_factor != 'fill_rate'
),
after_combo AS
(
    SELECT
        primary_factor, segment_key, segment, source, shape,
        window_start, window_end, n_days, severity, hidden_globally,
        probe_day, evidence_json, island_id
    FROM fill_kept
    UNION ALL
    SELECT
        primary_factor, segment_key, segment, source, shape,
        window_start, window_end, n_days, severity, hidden_globally,
        probe_day, evidence_json, island_id
    FROM non_fill
),
-- eCPM layer merge: chain clusters with gap <= 2 days
ecpm_ord AS
(
    SELECT
        *,
        lagInFrame(window_end) OVER (ORDER BY window_start, severity DESC) AS prev_end
    FROM after_combo
    WHERE primary_factor = 'ecpm'
),
ecpm_marked AS
(
    SELECT
        *,
        toUInt8(prev_end IS NULL OR dateDiff('day', prev_end, window_start) > 2) AS new_grp
    FROM ecpm_ord
),
ecpm_grp AS
(
    SELECT
        *,
        sum(new_grp) OVER (ORDER BY window_start, severity DESC) AS merge_id
    FROM ecpm_marked
),
ecpm_merged AS
(
    SELECT
        'ecpm' AS primary_factor,
        arrayStringConcat(arraySort(groupUniqArray(segment)), ' + ') AS merged_segment,
        argMax(source, severity) AS source,
        'layered' AS shape,
        min(window_start) AS window_start,
        max(window_end) AS window_end,
        toUInt32(sum(n_days)) AS n_days,
        sum(severity) AS cluster_severity,
        toUInt8(min(hidden_globally)) AS cluster_hidden,
        argMax(probe_day, ((1 - hidden_globally) * 1e12) + severity) AS probe_day,
        argMax(evidence_json, severity) AS evidence_json
    FROM ecpm_grp
    GROUP BY merge_id
),
final_clusters AS
(
    SELECT
        primary_factor, segment_key, segment, source, shape,
        window_start, window_end, n_days, severity, hidden_globally,
        probe_day, evidence_json
    FROM after_combo
    WHERE primary_factor != 'ecpm'

    UNION ALL

    SELECT
        primary_factor,
        merged_segment AS segment_key,
        merged_segment AS segment,
        source,
        shape,
        window_start,
        window_end,
        n_days,
        cluster_severity AS severity,
        cluster_hidden AS hidden_globally,
        probe_day,
        evidence_json
    FROM ecpm_merged
),
top_n AS
(
    SELECT *
    FROM final_clusters
    ORDER BY severity DESC
    LIMIT 8
),
enriched AS
(
    SELECT
        c.primary_factor AS primary_factor,
        c.segment_key AS segment_key,
        c.segment AS segment,
        c.source AS source,
        c.shape AS shape,
        c.window_start AS window_start,
        c.window_end AS window_end,
        c.n_days AS n_days,
        c.severity AS severity,
        c.hidden_globally AS hidden_globally,
        c.probe_day AS probe_day,
        c.evidence_json AS evidence_json,
        w.baseline_day AS baseline_day,
        w.req_chg AS req_chg,
        w.rev_chg AS rev_chg,
        w.fill_chg AS fill_chg,
        w.ecpm_chg AS ecpm_chg,
        f.share_requests AS share_requests,
        f.share_fill_rate AS share_fill_rate,
        f.share_ecpm AS share_ecpm,
        multiIf(
            c.primary_factor = 'requests',
            [
                'fill_rate_as_primary',
                'ecpm_as_primary',
                'weekend_seasonality',
                'single_segment',
                'seasonality_residual_gate'
            ],
            c.primary_factor = 'fill_rate',
            [
                'requests_as_primary',
                'ecpm_as_primary',
                'advertiser_dims_for_fill',
                'seasonality_residual_gate'
            ],
            [
                'fill_rate_as_primary',
                'weekend_seasonality',
                'seasonality_residual_gate'
            ]
        ) AS ruled_out,
        concat(
            'SQL-assembled incident: ', c.primary_factor, ' / ', c.segment,
            ' window ', toString(c.window_start), '...', toString(c.window_end),
            ' probe ', toString(c.probe_day),
            '. Evidence from eda.rca_* (ClickHouse-native).'
        ) AS explanation
    FROM top_n AS c
    LEFT JOIN rca_daily_wow AS w ON w.event_date = c.probe_day
    LEFT JOIN rca_factor_day AS f ON f.event_date = c.probe_day
),
numbered AS
(
    SELECT
        *,
        row_number() OVER (ORDER BY window_start, severity DESC) AS rn
    FROM enriched
)
SELECT
    substr('ABCDEFGH', toUInt8(rn), 1) AS id,
    window_start,
    window_end,
    n_days,
    probe_day,
    ifNull(baseline_day, probe_day - 7) AS baseline_day,
    'same_dow_minus_7' AS baseline_rule,
    primary_factor,
    shape,
    segment,
    source,
    hidden_globally,
    severity,
    req_chg,
    rev_chg,
    fill_chg,
    ecpm_chg,
    share_requests,
    share_fill_rate,
    share_ecpm,
    evidence_json,
    ruled_out,
    explanation,
    now() AS built_at
FROM numbered;
