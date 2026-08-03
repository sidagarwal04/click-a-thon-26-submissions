-- Expected baseline via ClickHouse simpleLinearRegression(T-7 -> actual).
-- Residual z-score = how abnormal today is vs the learned T-7 relationship.

TRUNCATE TABLE rca_ml_expected;

INSERT INTO rca_ml_expected
WITH
models AS
(
    SELECT
        simpleLinearRegression(base_revenue, revenue) AS rev_model,
        simpleLinearRegression(ifNull(base_fill_rate, 0), ifNull(fill_rate, 0)) AS fill_model,
        simpleLinearRegression(toFloat64(base_requests), toFloat64(requests)) AS req_model
    FROM rca_daily_wow
    WHERE base_revenue > 0 AND base_requests > 0
),
scored AS
(
    SELECT
        w.event_date AS event_date,
        w.revenue AS rev_actual,
        w.base_revenue AS rev_t7,
        m.rev_model.1 * w.base_revenue + m.rev_model.2 AS rev_expected,
        w.revenue - (m.rev_model.1 * w.base_revenue + m.rev_model.2) AS rev_residual,
        m.rev_model.1 AS rev_slope,
        m.rev_model.2 AS rev_intercept,
        ifNull(w.fill_rate, 0) AS fill_actual,
        ifNull(w.base_fill_rate, 0) AS fill_t7,
        m.fill_model.1 * ifNull(w.base_fill_rate, 0) + m.fill_model.2 AS fill_expected,
        ifNull(w.fill_rate, 0)
            - (m.fill_model.1 * ifNull(w.base_fill_rate, 0) + m.fill_model.2) AS fill_residual,
        m.fill_model.1 AS fill_slope,
        m.fill_model.2 AS fill_intercept,
        toFloat64(w.requests) AS req_actual,
        toFloat64(w.base_requests) AS req_t7,
        m.req_model.1 * toFloat64(w.base_requests) + m.req_model.2 AS req_expected,
        toFloat64(w.requests)
            - (m.req_model.1 * toFloat64(w.base_requests) + m.req_model.2) AS req_residual,
        m.req_model.1 AS req_slope,
        m.req_model.2 AS req_intercept
    FROM rca_daily_wow AS w
    CROSS JOIN models AS m
),
with_z AS
(
    SELECT
        *,
        ifNull(
            rev_residual / nullIf(stddevPop(rev_residual) OVER (), 0),
            0
        ) AS rev_residual_z,
        ifNull(
            fill_residual / nullIf(stddevPop(fill_residual) OVER (), 0),
            0
        ) AS fill_residual_z,
        ifNull(
            req_residual / nullIf(stddevPop(req_residual) OVER (), 0),
            0
        ) AS req_residual_z
    FROM scored
)
SELECT
    event_date,
    rev_actual,
    rev_t7,
    rev_expected,
    rev_residual,
    rev_residual_z,
    rev_slope,
    rev_intercept,
    fill_actual,
    fill_t7,
    fill_expected,
    fill_residual,
    fill_residual_z,
    fill_slope,
    fill_intercept,
    req_actual,
    req_t7,
    req_expected,
    req_residual,
    req_residual_z,
    req_slope,
    req_intercept,
    toUInt8(
        abs(rev_residual_z) >= 2
        OR abs(fill_residual_z) >= 2
        OR abs(req_residual_z) >= 2
    ) AS ml_outlier,
    now() AS built_at
FROM with_z;
