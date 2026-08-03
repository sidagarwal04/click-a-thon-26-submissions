-- Day signals assembled entirely in ClickHouse from rca_* layers.
-- Mirrors former Python _day_signals_from_tables (recovery gates + hidden scans).

TRUNCATE TABLE rca_day_signals;

INSERT INTO rca_day_signals
WITH
thresh AS
(
    SELECT
        maxIf(value, name = 'thresh_req_chg') AS thresh_req_chg,
        maxIf(value, name = 'thresh_fill_chg') AS thresh_fill_chg,
        maxIf(value, name = 'thresh_ecpm_chg') AS thresh_ecpm_chg,
        maxIf(value, name = 'seg_fill_chg') AS seg_fill_chg,
        maxIf(value, name = 'seg_fill_impact') AS seg_fill_impact,
        maxIf(value, name = 'seg_ecpm_abs') AS seg_ecpm_abs,
        maxIf(value, name = 'seg_ecpm_rev') AS seg_ecpm_rev,
        maxIf(value, name = 'min_seg_req') AS min_seg_req
    FROM rca_thresholds
),
fill_cands AS
(
    SELECT
        s.event_date AS event_date,
        concat('os_version=', s.dim_value) AS segment,
        'os_version' AS source,
        s.fill_impact AS severity,
        s.fill_chg AS fill_chg,
        toJSONString(map(
            'dimension', s.dimension,
            'dim_value', s.dim_value,
            'fill_t', toString(s.fill_t),
            'fill_b', toString(s.fill_b),
            'fill_chg', toString(s.fill_chg),
            'fill_impact', toString(s.fill_impact),
            'req_t', toString(s.req_t),
            'req_b', toString(s.req_b)
        )) AS evidence_json
    FROM rca_segment_day AS s
    CROSS JOIN thresh AS t
    WHERE s.dimension = 'os_version'
      AND s.fill_chg <= -t.seg_fill_chg
      AND s.fill_impact >= t.seg_fill_impact
      AND s.req_t >= t.min_seg_req

    UNION ALL

    SELECT
        c.event_date,
        c.segment,
        'os_region' AS source,
        c.fill_impact * 1.1 AS severity,
        c.fill_chg,
        toJSONString(map(
            'combo_kind', c.combo_kind,
            'segment', c.segment,
            'fill_t', toString(c.fill_t),
            'fill_b', toString(c.fill_b),
            'fill_chg', toString(c.fill_chg),
            'fill_impact', toString(c.fill_impact),
            'req_t', toString(c.req_t),
            'req_b', toString(c.req_b)
        ))
    FROM rca_combo_day AS c
    CROSS JOIN thresh AS t
    WHERE c.combo_kind = 'os_region'
      AND c.fill_chg <= -t.seg_fill_chg
      AND c.fill_impact >= t.seg_fill_impact
      AND c.req_t >= 1000
),
fill_top AS
(
    SELECT *
    FROM
    (
        SELECT
            *,
            row_number() OVER (PARTITION BY event_date ORDER BY severity DESC) AS rn
        FROM fill_cands
    )
    WHERE rn = 1
),
ecpm_cands AS
(
    SELECT
        c.event_date AS event_date,
        c.segment AS segment,
        'format_region' AS source,
        abs(c.d_rev) * abs(c.ecpm_chg) * 100 AS severity,
        c.ecpm_chg AS ecpm_chg,
        toJSONString(map(
            'combo_kind', c.combo_kind,
            'segment', c.segment,
            'ecpm_t', toString(c.ecpm_t),
            'ecpm_b', toString(c.ecpm_b),
            'ecpm_chg', toString(c.ecpm_chg),
            'd_rev', toString(c.d_rev),
            'imp_t', toString(c.imp_t)
        )) AS evidence_json
    FROM rca_combo_day AS c
    CROSS JOIN thresh AS t
    WHERE c.combo_kind = 'format_region'
      AND c.ecpm_chg <= -t.seg_ecpm_abs
      AND c.d_rev <= -t.seg_ecpm_rev

    UNION ALL

    SELECT
        s.event_date,
        concat('category=', s.dim_value),
        'category',
        abs(s.d_rev) * abs(s.ecpm_chg) * 80,
        s.ecpm_chg,
        toJSONString(map(
            'dimension', s.dimension,
            'dim_value', s.dim_value,
            'ecpm_t', toString(s.ecpm_t),
            'ecpm_b', toString(s.ecpm_b),
            'ecpm_chg', toString(s.ecpm_chg),
            'd_rev', toString(s.d_rev)
        ))
    FROM rca_segment_day AS s
    CROSS JOIN thresh AS t
    WHERE s.dimension = 'category'
      AND s.ecpm_chg <= -t.seg_ecpm_abs
      AND s.d_rev <= -t.seg_ecpm_rev
),
ecpm_top AS
(
    SELECT *
    FROM
    (
        SELECT
            *,
            row_number() OVER (PARTITION BY event_date ORDER BY severity DESC) AS rn
        FROM ecpm_cands
    )
    WHERE rn = 1
),
day_base AS
(
    SELECT
        w.event_date AS event_date,
        w.baseline_day AS baseline_day,
        ifNull(w.req_chg, 0) AS req_chg,
        ifNull(w.rev_chg, 0) AS rev_chg,
        ifNull(w.fill_chg, 0) AS fill_chg,
        ifNull(w.ecpm_chg, 0) AS ecpm_chg,
        w.flag_volume AS flag_volume,
        w.flag_fill AS flag_fill,
        w.flag_ecpm AS flag_ecpm,
        w.seasonal_ok AS seasonal_ok,
        w.is_anomaly_gated AS is_anomaly_gated,
        f.primary_factor AS factor_primary,
        f.share_requests AS share_requests,
        f.share_fill_rate AS share_fill_rate,
        f.share_ecpm AS share_ecpm,
        -- Resolve primary (match Python _resolve_primary)
        multiIf(
            ifNull(w.req_chg, 0) <= -t.thresh_req_chg, 'requests',
            f.primary_factor = 'fill_rate'
                AND ifNull(w.fill_chg, 0) <= -t.thresh_fill_chg
                AND ifNull(w.fill_chg, 0) < t.thresh_fill_chg,
                'fill_rate',
            f.primary_factor = 'ecpm'
                AND ifNull(w.ecpm_chg, 0) <= -t.thresh_ecpm_chg
                AND ifNull(w.ecpm_chg, 0) < t.thresh_ecpm_chg,
                'ecpm',
            ifNull(w.fill_chg, 0) <= -t.thresh_fill_chg, 'fill_rate',
            ifNull(w.ecpm_chg, 0) <= -t.thresh_ecpm_chg, 'ecpm',
            f.primary_factor
        ) AS primary_factor,
        ifNull(ft.segment, '') AS fill_segment,
        ifNull(ft.source, '') AS fill_source,
        ifNull(ft.severity, 0) AS fill_severity,
        ifNull(ft.fill_chg, 0) AS fill_seg_chg,
        ifNull(ft.evidence_json, '{}') AS fill_evidence,
        ifNull(et.segment, '') AS ecpm_segment,
        ifNull(et.source, '') AS ecpm_source,
        ifNull(et.severity, 0) AS ecpm_severity,
        ifNull(et.evidence_json, '{}') AS ecpm_evidence
    FROM rca_daily_wow AS w
    INNER JOIN rca_factor_day AS f ON f.event_date = w.event_date
    CROSS JOIN thresh AS t
    LEFT JOIN fill_top AS ft ON ft.event_date = w.event_date
    LEFT JOIN ecpm_top AS et ON et.event_date = w.event_date
),
primary_signals AS
(
    -- Global volume
    SELECT
        event_date,
        'requests' AS primary_factor,
        'global_uniform' AS shape,
        'ALL' AS segment_key,
        'ALL (global volume)' AS segment,
        'global' AS source,
        abs(rev_chg) * abs(req_chg) * 1000 AS severity,
        toUInt8(0) AS hidden_globally,
        '{}' AS evidence_json
    FROM day_base
    CROSS JOIN thresh AS t
    WHERE primary_factor = 'requests'
      AND req_chg <= -t.thresh_req_chg
      AND (seasonal_ok = 1 OR is_anomaly_gated = 1)

    UNION ALL

    -- Localized / combo fill (global primary)
    SELECT
        event_date,
        'fill_rate',
        if(fill_source = 'os_region', 'hidden_combo', 'localized'),
        fill_segment,
        fill_segment,
        fill_source,
        fill_severity,
        0,
        fill_evidence
    FROM day_base
    CROSS JOIN thresh AS t
    WHERE primary_factor = 'fill_rate'
      AND fill_chg <= -t.thresh_fill_chg
      AND fill_segment != ''
      AND (seasonal_ok = 1 OR is_anomaly_gated = 1)

    UNION ALL

    -- Global fill fallback
    SELECT
        event_date,
        'fill_rate',
        'global_fill',
        'GLOBAL_FILL',
        'global fill',
        'global',
        abs(fill_chg) * 1e5,
        0,
        '{}'
    FROM day_base
    CROSS JOIN thresh AS t
    WHERE primary_factor = 'fill_rate'
      AND fill_chg <= -t.thresh_fill_chg
      AND fill_segment = ''
      AND (seasonal_ok = 1 OR is_anomaly_gated = 1)

    UNION ALL

    -- eCPM primary
    SELECT
        event_date,
        'ecpm',
        if(ecpm_segment != '', 'layered', 'global_ecpm'),
        if(ecpm_segment != '', ecpm_segment, 'GLOBAL_ECPM'),
        if(ecpm_segment != '', ecpm_segment, 'global eCPM'),
        if(ecpm_segment != '', ecpm_source, 'global'),
        if(ecpm_segment != '', ecpm_severity, abs(ecpm_chg) * 1e4),
        0,
        if(ecpm_segment != '', ecpm_evidence, '{}')
    FROM day_base
    CROSS JOIN thresh AS t
    WHERE primary_factor = 'ecpm'
      AND ecpm_chg <= -t.thresh_ecpm_chg
      AND (seasonal_ok = 1 OR is_anomaly_gated = 1)
),
hidden_fill AS
(
    SELECT
        d.event_date AS event_date,
        'fill_rate' AS primary_factor,
        'hidden_combo' AS shape,
        d.fill_segment AS segment_key,
        d.fill_segment AS segment,
        d.fill_source AS source,
        d.fill_severity AS severity,
        toUInt8(abs(d.fill_chg) < t.thresh_fill_chg) AS hidden_globally,
        d.fill_evidence AS evidence_json
    FROM day_base AS d
    CROSS JOIN thresh AS t
    WHERE d.fill_segment != ''
      AND d.fill_seg_chg <= -t.seg_fill_chg
      AND d.primary_factor != 'requests'
      AND NOT (
          d.primary_factor = 'fill_rate'
          AND d.fill_chg <= -t.thresh_fill_chg
          AND d.fill_segment != ''
      )
),
hidden_ecpm AS
(
    SELECT
        d.event_date,
        'ecpm',
        'layered_hidden',
        d.ecpm_segment,
        d.ecpm_segment,
        d.ecpm_source,
        d.ecpm_severity,
        toUInt8(d.ecpm_chg > -t.thresh_ecpm_chg) AS hidden_globally,
        d.ecpm_evidence
    FROM day_base AS d
    CROSS JOIN thresh AS t
    WHERE d.ecpm_segment != ''
      AND d.ecpm_chg < t.thresh_ecpm_chg
      AND d.primary_factor != 'requests'
      AND d.primary_factor != 'fill_rate'
      AND NOT (
          d.primary_factor = 'ecpm' AND d.ecpm_chg <= -t.thresh_ecpm_chg
      )
      -- skip if any fill signal already exists for the day (Python early-return)
      AND d.event_date NOT IN (SELECT event_date FROM primary_signals WHERE primary_factor = 'fill_rate')
      AND d.event_date NOT IN (SELECT event_date FROM hidden_fill)
),
-- Suppress hidden fill when day already has requests primary
filtered_hidden_fill AS
(
    SELECT h.*
    FROM hidden_fill AS h
    WHERE h.event_date NOT IN (
        SELECT event_date FROM primary_signals WHERE primary_factor = 'requests'
    )
),
all_signals AS
(
    SELECT * FROM primary_signals
    UNION ALL
    SELECT * FROM filtered_hidden_fill
    UNION ALL
    SELECT * FROM hidden_ecpm
)
SELECT
    event_date,
    primary_factor,
    shape,
    segment_key,
    segment,
    source,
    severity,
    hidden_globally,
    evidence_json,
    now() AS built_at
FROM all_signals
WHERE segment_key != '' AND segment_key IS NOT NULL;
