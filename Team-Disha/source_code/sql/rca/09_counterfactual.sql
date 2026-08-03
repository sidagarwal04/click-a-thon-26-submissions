-- Glossary-faithful counterfactuals per incident (ClickHouse-computed).
-- Revenue ≈ Requests × Fill × eCPM / 1000

TRUNCATE TABLE rca_counterfactual;

INSERT INTO rca_counterfactual
WITH base AS
(
    SELECT
        i.id AS incident_id,
        i.probe_day AS probe_day,
        i.baseline_day AS baseline_day,
        i.primary_factor AS primary_factor,
        i.segment AS segment,
        w.requests AS requests_t,
        ifNull(w.fill_rate, 0) AS fill_t,
        ifNull(w.ecpm, 0) AS ecpm_t,
        w.revenue AS revenue_actual,
        w.base_requests AS base_requests,
        ifNull(w.base_fill_rate, 0) AS base_fill,
        ifNull(w.base_ecpm, 0) AS base_ecpm,
        w.base_revenue AS base_revenue,
        -- Counterfactual revenues holding one factor at baseline
        w.requests * ifNull(w.base_fill_rate, 0) * ifNull(w.ecpm, 0) / 1000
            AS revenue_if_fill_at_baseline,
        w.requests * ifNull(w.fill_rate, 0) * ifNull(w.base_ecpm, 0) / 1000
            AS revenue_if_ecpm_at_baseline,
        w.base_requests * ifNull(w.fill_rate, 0) * ifNull(w.ecpm, 0) / 1000
            AS revenue_if_requests_at_baseline
    FROM rca_incidents AS i
    INNER JOIN rca_daily_wow AS w ON w.event_date = i.probe_day
),
scored AS
(
    SELECT
        *,
        revenue_actual - revenue_if_fill_at_baseline AS delta_if_fill_fixed,
        revenue_actual - revenue_if_ecpm_at_baseline AS delta_if_ecpm_fixed,
        revenue_actual - revenue_if_requests_at_baseline AS delta_if_requests_fixed,
        multiIf(
            primary_factor = 'fill_rate', revenue_actual - revenue_if_fill_at_baseline,
            primary_factor = 'ecpm', revenue_actual - revenue_if_ecpm_at_baseline,
            primary_factor = 'requests', revenue_actual - revenue_if_requests_at_baseline,
            0
        ) AS delta_explained_by_primary
    FROM base
)
SELECT
    incident_id,
    probe_day,
    baseline_day,
    primary_factor,
    segment,
    requests_t,
    fill_t,
    ecpm_t,
    revenue_actual,
    base_requests,
    base_fill,
    base_ecpm,
    base_revenue,
    revenue_if_fill_at_baseline,
    revenue_if_ecpm_at_baseline,
    revenue_if_requests_at_baseline,
    delta_if_fill_fixed,
    delta_if_ecpm_fixed,
    delta_if_requests_fixed,
    delta_explained_by_primary,
    arrayFilter(
        x -> x != '',
        [
            if(abs(delta_if_fill_fixed) < abs(delta_explained_by_primary) * 0.25
               AND primary_factor != 'fill_rate', 'fill_rate', ''),
            if(abs(delta_if_ecpm_fixed) < abs(delta_explained_by_primary) * 0.25
               AND primary_factor != 'ecpm', 'ecpm', ''),
            if(abs(delta_if_requests_fixed) < abs(delta_explained_by_primary) * 0.25
               AND primary_factor != 'requests', 'requests', '')
        ]
    ) AS ruled_out_factors,
    now() AS built_at
FROM scored;
