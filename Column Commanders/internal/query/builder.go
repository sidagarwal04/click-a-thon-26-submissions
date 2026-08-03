package query

import (
	"fmt"
	"strings"
)

// dateListSQL renders a []string of "YYYY-MM-DD" dates as a SQL literal list
// suitable for `day IN (...)` / `toDate(e.event_time) IN (...)`, e.g.
// "toDate('2026-06-21'), toDate('2026-06-14')".
func dateListSQL(dates []string) string {
	parts := make([]string, len(dates))
	for i, d := range dates {
		parts[i] = "toDate('" + escapeSingleQuote(d) + "')"
	}
	return strings.Join(parts, ", ")
}

// All SQL constants used by the detection and drilldown pipeline.
// Detectors and engines import from here — never build SQL inline.

// ── Watermark / anchor ────────────────────────────────────────────────────────

const GetDataAnchorSQL = `
SELECT toString(toDate(last_event_time)) AS anchor
FROM watermark FINAL
WHERE table_name = 'ad_events'
LIMIT 1
`

const GetDataAnchorFallbackSQL = `
SELECT toString(max(toDate(event_time))) AS anchor
FROM ad_events
`

// ── Daily Z-Score baseline ────────────────────────────────────────────────────
// Parameters: target_date String, lookback_weeks Int32, min_n Int32

const DailyZScoreBaselineSQL = `
WITH
daily AS (
    SELECT
        day,
        toDayOfWeek(day)                                              AS dow,
        countMerge(requests_s)                                        AS requests,
        sumMerge(revenue_s)                                           AS revenue,
        sumMerge(fills_s)  / countMerge(requests_s)                  AS fill_rate,
        sumMerge(clicks_s) / nullIf(sumMerge(imps_s), 0)            AS ctr,
        sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000    AS ecpm
    FROM daily_global_agg
    GROUP BY day
),
target AS (
    SELECT day, dow, requests, revenue, fill_rate, ctr, ecpm
    FROM daily
    WHERE day = toDate({target_date:String})
),
baseline_set AS (
    SELECT b.requests, b.revenue, b.fill_rate, b.ctr, b.ecpm,
           toUnixTimestamp(b.day) AS day_unix
    FROM daily b
    CROSS JOIN target t
    WHERE b.dow = t.dow
      AND b.day < t.day
      AND b.day >= t.day - INTERVAL {lookback_weeks:Int64} WEEK
)
SELECT
    t.day,
    t.requests      AS curr_requests,
    t.revenue       AS curr_revenue,
    t.fill_rate     AS curr_fill_rate,
    t.ctr           AS curr_ctr,
    t.ecpm          AS curr_ecpm,
    quantile(0.5)(b.revenue)                                                AS med_revenue,
    (quantile(0.75)(b.revenue)   - quantile(0.25)(b.revenue))   / 1.35    AS sigma_revenue,
    quantile(0.5)(b.fill_rate)                                              AS med_fill_rate,
    (quantile(0.75)(b.fill_rate) - quantile(0.25)(b.fill_rate)) / 1.35    AS sigma_fill_rate,
    quantile(0.5)(b.ctr)                                                    AS med_ctr,
    (quantile(0.75)(b.ctr)      - quantile(0.25)(b.ctr))      / 1.35      AS sigma_ctr,
    quantile(0.5)(b.ecpm)                                                   AS med_ecpm,
    (quantile(0.75)(b.ecpm)     - quantile(0.25)(b.ecpm))     / 1.35      AS sigma_ecpm,
    quantile(0.5)(b.requests)                                               AS med_requests,
    (quantile(0.75)(b.requests) - quantile(0.25)(b.requests)) / 1.35      AS sigma_requests,
    simpleLinearRegression(b.day_unix, b.requests).1                        AS trend_slope,
    avg(b.day_unix)                                                         AS baseline_midpoint_unix,
    count() AS n
FROM target t, baseline_set b
GROUP BY t.day, t.requests, t.revenue, t.fill_rate, t.ctr, t.ecpm
HAVING count() >= {min_n:Int64}
`

// ── Hourly Z-Score baseline ───────────────────────────────────────────────────
// Parameters: target_hour String, lookback_weeks Int32, min_n Int32

const HourlyZScoreBaselineSQL = `
WITH
hourly AS (
    SELECT
        hour,
        toDayOfWeek(hour)                                              AS dow,
        toHour(hour)                                                   AS hod,
        countMerge(requests_s)                                         AS requests,
        sumMerge(revenue_s)                                            AS revenue,
        sumMerge(fills_s)  / countMerge(requests_s)                   AS fill_rate,
        sumMerge(clicks_s) / nullIf(sumMerge(imps_s), 0)             AS ctr,
        sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000     AS ecpm
    FROM hourly_global_agg
    WHERE hour <= toStartOfHour(toDateTime({target_hour:String}))
    GROUP BY hour
),
target AS (
    SELECT hour, dow, hod, requests, revenue, fill_rate, ctr, ecpm
    FROM hourly
    WHERE hour = toStartOfHour(toDateTime({target_hour:String}))
),
baseline_set AS (
    SELECT b.requests, b.revenue, b.fill_rate, b.ctr, b.ecpm,
           toUnixTimestamp(b.hour) AS hour_unix
    FROM hourly b
    CROSS JOIN target t
    WHERE b.dow = t.dow
      AND b.hod = t.hod
      AND b.hour < t.hour
      AND b.hour >= t.hour - INTERVAL {lookback_weeks:Int64} WEEK
)
SELECT
    t.hour,
    t.requests      AS curr_requests,
    t.revenue       AS curr_revenue,
    t.fill_rate     AS curr_fill_rate,
    t.ctr           AS curr_ctr,
    t.ecpm          AS curr_ecpm,
    quantile(0.5)(b.revenue)                                                AS med_revenue,
    (quantile(0.75)(b.revenue)   - quantile(0.25)(b.revenue))   / 1.35    AS sigma_revenue,
    quantile(0.5)(b.fill_rate)                                              AS med_fill_rate,
    (quantile(0.75)(b.fill_rate) - quantile(0.25)(b.fill_rate)) / 1.35    AS sigma_fill_rate,
    quantile(0.5)(b.ctr)                                                    AS med_ctr,
    (quantile(0.75)(b.ctr)      - quantile(0.25)(b.ctr))      / 1.35      AS sigma_ctr,
    quantile(0.5)(b.ecpm)                                                   AS med_ecpm,
    (quantile(0.75)(b.ecpm)     - quantile(0.25)(b.ecpm))     / 1.35      AS sigma_ecpm,
    quantile(0.5)(b.requests)                                               AS med_requests,
    (quantile(0.75)(b.requests) - quantile(0.25)(b.requests)) / 1.35      AS sigma_requests,
    simpleLinearRegression(b.hour_unix, b.requests).1                       AS trend_slope,
    avg(b.hour_unix)                                                        AS baseline_midpoint_unix,
    count() AS n
FROM target t, baseline_set b
GROUP BY t.hour, t.requests, t.revenue, t.fill_rate, t.ctr, t.ecpm
HAVING count() >= {min_n:Int64}
`

// ── Segment (broad-dimension) baseline — Detect scans this every cycle ───────
// Backing table: hourly_by_dimension (dimension-pivoted rollup, built by
// MigrateDimensionRollup). This is what lets Detect check every value of a
// broad dimension (os_version, region, ...) on every cycle instead of only
// after a platform-level detector has already fired — both real fill-rate
// incidents in the validated dataset are invisible at the platform aggregate
// (see docs/ARCHITECTURE_VALIDATED.md §4.2), so a cascade-only design can miss
// a segment that's badly broken while the platform average stays quiet.
// One query returns every segment value's own median/IQR baseline + current
// value for the given dimension_name — not one query per value.
// Parameters: dimension_name String, target_date String, lookback_weeks Int32, min_n Int32

const SegmentDailyBaselineSQL = `
WITH
daily AS (
    SELECT
        toDate(hour_ts)                                              AS day,
        dimension_value                                              AS seg,
        toDayOfWeek(day)                                             AS dow,
        countMerge(requests_s)                                       AS requests,
        sumMerge(fills_s) / countMerge(requests_s)                  AS fill_rate,
        sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000    AS ecpm
    FROM hourly_by_dimension
    WHERE dimension_name = {dimension_name:String}
    GROUP BY day, seg
),
target AS (
    SELECT seg, dow, requests, fill_rate, ecpm
    FROM daily
    WHERE day = toDate({target_date:String})
),
baseline_set AS (
    SELECT b.seg, b.requests, b.fill_rate, b.ecpm
    FROM daily b
    INNER JOIN target t ON b.seg = t.seg AND b.dow = t.dow
    WHERE b.day < toDate({target_date:String})
      AND b.day >= toDate({target_date:String}) - INTERVAL {lookback_weeks:Int32} WEEK
)
SELECT
    t.seg,
    t.requests  AS curr_requests,
    t.fill_rate AS curr_fill_rate,
    t.ecpm      AS curr_ecpm,
    quantile(0.5)(b.fill_rate)                                           AS med_fill_rate,
    (quantile(0.75)(b.fill_rate) - quantile(0.25)(b.fill_rate)) / 1.35 AS sigma_fill_rate,
    quantile(0.5)(b.ecpm)                                                AS med_ecpm,
    (quantile(0.75)(b.ecpm) - quantile(0.25)(b.ecpm)) / 1.35           AS sigma_ecpm,
    count() AS n
FROM target t
INNER JOIN baseline_set b ON t.seg = b.seg
GROUP BY t.seg, t.requests, t.fill_rate, t.ecpm
HAVING count() >= {min_n:Int32}
`

// SegmentHourlyBaselineSQL — same as SegmentDailyBaselineSQL but same-hour-of-day
// matching for hourly-grain windows.
// Parameters: dimension_name String, target_hour String, lookback_weeks Int32, min_n Int32

const SegmentHourlyBaselineSQL = `
WITH
hourly AS (
    SELECT
        hour_ts                                                      AS hour,
        dimension_value                                              AS seg,
        toDayOfWeek(hour)                                            AS dow,
        toHour(hour)                                                 AS hod,
        countMerge(requests_s)                                       AS requests,
        sumMerge(fills_s) / countMerge(requests_s)                  AS fill_rate,
        sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000    AS ecpm
    FROM hourly_by_dimension
    WHERE dimension_name = {dimension_name:String}
      AND hour_ts <= toStartOfHour(toDateTime({target_hour:String}))
    GROUP BY hour, seg
),
target AS (
    SELECT seg, dow, hod, requests, fill_rate, ecpm
    FROM hourly
    WHERE hour = toStartOfHour(toDateTime({target_hour:String}))
),
baseline_set AS (
    SELECT b.seg, b.requests, b.fill_rate, b.ecpm
    FROM hourly b
    INNER JOIN target t ON b.seg = t.seg AND b.dow = t.dow AND b.hod = t.hod
    WHERE b.hour < toStartOfHour(toDateTime({target_hour:String}))
      AND b.hour >= toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {lookback_weeks:Int32} WEEK
)
SELECT
    t.seg,
    t.requests  AS curr_requests,
    t.fill_rate AS curr_fill_rate,
    t.ecpm      AS curr_ecpm,
    quantile(0.5)(b.fill_rate)                                           AS med_fill_rate,
    (quantile(0.75)(b.fill_rate) - quantile(0.25)(b.fill_rate)) / 1.35 AS sigma_fill_rate,
    quantile(0.5)(b.ecpm)                                                AS med_ecpm,
    (quantile(0.75)(b.ecpm) - quantile(0.25)(b.ecpm)) / 1.35           AS sigma_ecpm,
    count() AS n
FROM target t
INNER JOIN baseline_set b ON t.seg = b.seg
GROUP BY t.seg, t.requests, t.fill_rate, t.ecpm
HAVING count() >= {min_n:Int32}
`

// ── Rolling CUSUM (fill_rate) ─────────────────────────────────────────────────
// Parameters: target_hour String, rolling_window Int32, lookback_weeks Int32

const RollingCUSUMFillRateSQL = `
WITH
recent AS (
    SELECT
        hour,
        sumMerge(fills_s) / countMerge(requests_s) AS metric_val
    FROM hourly_global_agg
    WHERE hour <= toStartOfHour(toDateTime({target_hour:String}))
      AND hour >  toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {rolling_window:Int64} HOUR
    GROUP BY hour
    ORDER BY hour
),
baseline AS (
    SELECT
        quantile(0.5)(metric_val)                                   AS mu,
        (quantile(0.75)(metric_val) - quantile(0.25)(metric_val)) / 1.35 AS sigma
    FROM (
        SELECT hour,
               sumMerge(fills_s) / countMerge(requests_s) AS metric_val
        FROM hourly_global_agg
        WHERE toDayOfWeek(hour) = toDayOfWeek(toDateTime({target_hour:String}))
          AND toHour(hour)      = toHour(toDateTime({target_hour:String}))
          AND hour < toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {rolling_window:Int64} HOUR
          AND hour >= toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {lookback_weeks:Int64} WEEK
        GROUP BY hour
    )
),
with_deviation AS (
    SELECT r.hour, r.metric_val,
           (SELECT mu FROM baseline)    AS mu,
           (SELECT sigma FROM baseline) AS sigma,
           r.metric_val - (SELECT mu FROM baseline) AS deviation
    FROM recent r
)
SELECT
    hour,
    metric_val,
    mu,
    sigma,
    deviation,
    sum(least(0, deviation + sigma * {slack_k:Float64}))
        OVER (ORDER BY hour ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_down,
    sum(greatest(0, deviation - sigma * {slack_k:Float64}))
        OVER (ORDER BY hour ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_up
FROM with_deviation
ORDER BY hour
`

// ── Rolling CUSUM (ecpm) ──────────────────────────────────────────────────────

const RollingCUSUMECPMSQL = `
WITH
recent AS (
    SELECT
        hour,
        sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000 AS metric_val
    FROM hourly_global_agg
    WHERE hour <= toStartOfHour(toDateTime({target_hour:String}))
      AND hour >  toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {rolling_window:Int64} HOUR
    GROUP BY hour
    ORDER BY hour
),
baseline AS (
    SELECT
        quantile(0.5)(metric_val)                                   AS mu,
        (quantile(0.75)(metric_val) - quantile(0.25)(metric_val)) / 1.35 AS sigma
    FROM (
        SELECT hour,
               sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000 AS metric_val
        FROM hourly_global_agg
        WHERE toDayOfWeek(hour) = toDayOfWeek(toDateTime({target_hour:String}))
          AND toHour(hour)      = toHour(toDateTime({target_hour:String}))
          AND hour < toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {rolling_window:Int64} HOUR
          AND hour >= toStartOfHour(toDateTime({target_hour:String})) - INTERVAL {lookback_weeks:Int64} WEEK
        GROUP BY hour
    )
),
with_deviation AS (
    SELECT r.hour, r.metric_val,
           (SELECT mu FROM baseline)    AS mu,
           (SELECT sigma FROM baseline) AS sigma,
           r.metric_val - (SELECT mu FROM baseline) AS deviation
    FROM recent r
)
SELECT
    hour,
    metric_val,
    mu,
    sigma,
    deviation,
    sum(least(0, deviation + sigma * {slack_k:Float64}))
        OVER (ORDER BY hour ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_down,
    sum(greatest(0, deviation - sigma * {slack_k:Float64}))
        OVER (ORDER BY hour ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_up
FROM with_deviation
ORDER BY hour
`

// ── Rolling CUSUM on daily data (for daily-grain detection) ──────────────────
// Used by CUSUM detector when grain = "daily".
// Parameters: target_date String, rolling_window_days (rendered), lookback_weeks (rendered), slack_k (rendered)

const RollingCUSUMDailyFillRateSQL = `
WITH
recent AS (
    SELECT day,
           sumMerge(fills_s) / countMerge(requests_s) AS metric_val
    FROM daily_global_agg
    WHERE day <= toDate({target_date:String})
      AND day > toDate({target_date:String}) - INTERVAL 7 DAY
    GROUP BY day ORDER BY day
),
baseline AS (
    SELECT
        quantile(0.5)(metric_val)                                      AS mu,
        (quantile(0.75)(metric_val) - quantile(0.25)(metric_val))/1.35 AS sigma
    FROM (
        SELECT day, sumMerge(fills_s)/countMerge(requests_s) AS metric_val
        FROM daily_global_agg
        WHERE toDayOfWeek(day) = toDayOfWeek(toDate({target_date:String}))
          AND day < toDate({target_date:String}) - INTERVAL 7 DAY
          AND day >= toDate({target_date:String}) - INTERVAL 4 WEEK
        GROUP BY day
    )
),
with_dev AS (
    SELECT day, metric_val,
           (SELECT mu FROM baseline) AS mu,
           (SELECT sigma FROM baseline) AS sigma,
           metric_val - (SELECT mu FROM baseline) AS deviation
    FROM recent
)
SELECT day, metric_val, mu, sigma, deviation,
    sum(least(0, deviation + sigma * 0.5))
        OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_down,
    sum(greatest(0, deviation - sigma * 0.5))
        OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_up
FROM with_dev ORDER BY day
`

const RollingCUSUMDailyECPMSQL = `
WITH
recent AS (
    SELECT day,
           sumMerge(revenue_s)/nullIf(sumMerge(imps_s),0)*1000 AS metric_val
    FROM daily_global_agg
    WHERE day <= toDate({target_date:String})
      AND day > toDate({target_date:String}) - INTERVAL 7 DAY
    GROUP BY day ORDER BY day
),
baseline AS (
    SELECT
        quantile(0.5)(metric_val)                                      AS mu,
        (quantile(0.75)(metric_val) - quantile(0.25)(metric_val))/1.35 AS sigma
    FROM (
        SELECT day, sumMerge(revenue_s)/nullIf(sumMerge(imps_s),0)*1000 AS metric_val
        FROM daily_global_agg
        WHERE toDayOfWeek(day) = toDayOfWeek(toDate({target_date:String}))
          AND day < toDate({target_date:String}) - INTERVAL 7 DAY
          AND day >= toDate({target_date:String}) - INTERVAL 4 WEEK
        GROUP BY day
    )
),
with_dev AS (
    SELECT day, metric_val,
           (SELECT mu FROM baseline) AS mu,
           (SELECT sigma FROM baseline) AS sigma,
           metric_val - (SELECT mu FROM baseline) AS deviation
    FROM recent
)
SELECT day, metric_val, mu, sigma, deviation,
    sum(least(0, deviation + sigma * 0.5))
        OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_down,
    sum(greatest(0, deviation - sigma * 0.5))
        OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cusum_up
FROM with_dev ORDER BY day
`

// ── Factor decomposition ──────────────────────────────────────────────────────
// Use BuildFactorDecompositionSQL() to render.

// render_rate = impressions / fills is kept as its own factor (not folded into
// fill_rate or ecpm) — a render-failure incident (fills succeed, ad doesn't
// render) would otherwise be invisible to guilty-factor classification and get
// silently misattributed. See docs/ARCHITECTURE.md's 4-factor revenue identity.
//
// The baseline is the median across several same-weekday prior days, not a
// single fixed "N days back" comparison. A single baseline day can itself be
// anomalous — e.g. it can land squarely on a real, unrelated incident — which
// silently corrupts every factor delta computed against it (observed live:
// comparing a later incident's day against a baseline day that happened to be
// the platform-wide volume-drop day made "requests" look ~84% up and wrongly
// won the guilty-factor vote). Mirrors the same same-weekday-median approach
// Detect already uses for exactly this reason.
// toFloat64() around countMerge(requests_s): the baseline branch's
// quantile(0.5)(requests) is always Float64, and UNION ALL-ing that against
// this branch's plain UInt64 count makes ClickHouse produce a Variant(UInt64,
// Float64) column instead of a plain number — the Go driver hands that back
// as a chcol.Variant struct that toF() doesn't know how to unwrap, silently
// reading as 0. Casting both branches to the same type avoids the Variant
// entirely. (Found live: this exact mismatch is what broke "requests" here.)
const factorDecompositionSQLTemplate = `
SELECT 'current' AS period,
    toFloat64(countMerge(requests_s))                               AS requests,
    sumMerge(fills_s) / countMerge(requests_s)                     AS fill_rate,
    sumMerge(imps_s) / nullIf(sumMerge(fills_s), 0)                AS render_rate,
    sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000      AS ecpm,
    sumMerge(revenue_s)                                             AS revenue
FROM daily_global_agg
WHERE day = toDate('%[1]s')
GROUP BY period
UNION ALL
SELECT 'baseline' AS period,
    quantile(0.5)(requests)    AS requests,
    quantile(0.5)(fill_rate)   AS fill_rate,
    quantile(0.5)(render_rate) AS render_rate,
    quantile(0.5)(ecpm)        AS ecpm,
    quantile(0.5)(revenue)     AS revenue
FROM (
    SELECT day,
        countMerge(requests_s)                                     AS requests,
        sumMerge(fills_s) / countMerge(requests_s)                AS fill_rate,
        sumMerge(imps_s) / nullIf(sumMerge(fills_s), 0)           AS render_rate,
        sumMerge(revenue_s) / nullIf(sumMerge(imps_s), 0) * 1000 AS ecpm,
        sumMerge(revenue_s)                                        AS revenue
    FROM daily_global_agg
    WHERE day IN (%[2]s)
    GROUP BY day
)
`

// BuildFactorDecompositionSQL renders the factor decomposition query, comparing
// currentDate against the median of baselineDates (same weekday, trailing
// weeks — see drilldown.baselineDatesFor).
func BuildFactorDecompositionSQL(currentDate string, baselineDates []string) string {
	return fmt.Sprintf(factorDecompositionSQLTemplate, currentDate, dateListSQL(baselineDates))
}

// ── Contribution SQL template ─────────────────────────────────────────────────
// Use BuildContributionSQL() to render; do not use directly.

// Contribution is volume-weighted Explanatory Power (Adtributor-style), not raw
// rate-delta: impact = segment_n × (current_rate - baseline_rate). Without the
// segment_n weight, a thin segment with a large rate swing can outrank a large
// segment that actually drives most of the real-dollar impact, and the ranking
// has no guaranteed relationship to the platform's actual observed change. For
// "requests" the metric itself is already an additive count, so no extra
// weighting is applied (see BuildContributionSQL).
//
// FULL OUTER JOIN (not JOIN) so a segment value present in only one period —
// a cold-start segment with no baseline history, or one that vanished — is
// surfaced as its own `cold_start` finding instead of silently dropped.
//
// The baseline is the median across several same-weekday prior days (see
// dateListSQL), not a single fixed day — same rationale as
// BuildFactorDecompositionSQL: one contaminated baseline day would corrupt
// every segment's baseline rate computed against it.
const contributionSQLTemplate = `
WITH
cur AS (
    SELECT %[1]s AS seg, %[2]s AS val, count() AS n
    %[3]s
    WHERE toDate(e.event_time) = '%[4]s'
    %[5]s
    GROUP BY seg
),
bas_daily AS (
    SELECT toDate(e.event_time) AS day, %[1]s AS seg, %[2]s AS val, count() AS n
    %[3]s
    WHERE toDate(e.event_time) IN (%[6]s)
    %[5]s
    GROUP BY day, seg
),
bas AS (
    SELECT seg, quantile(0.5)(val) AS val, quantile(0.5)(n) AS n
    FROM bas_daily
    GROUP BY seg
),
joined AS (
    SELECT
        coalesce(c.seg, b.seg) AS seg,
        c.val       AS cur_val,
        b.val       AS bas_val,
        c.n         AS cur_n,
        isNull(c.n) AS missing_cur,
        isNull(b.n) AS missing_bas
    FROM cur c
    FULL OUTER JOIN bas b ON c.seg = b.seg
),
deltas AS (
    SELECT
        seg, cur_val, bas_val,
        (missing_cur OR missing_bas) AS is_cold_start,
        if(missing_cur OR missing_bas, NULL, cur_val - bas_val) AS raw_delta,
        if(missing_cur OR missing_bas, NULL, %[7]s)             AS impact
    FROM joined
),
total AS (SELECT sum(impact) AS tot FROM deltas WHERE NOT is_cold_start)
SELECT
    seg,
    is_cold_start       AS cold_start,
    round(cur_val, 6)   AS current_value,
    round(bas_val, 6)   AS baseline_value,
    round(raw_delta, 6) AS delta,
    round(impact / nullIf(abs((SELECT tot FROM total)), 0), 4) AS contribution_pct
FROM deltas
ORDER BY is_cold_start DESC, abs(contribution_pct) DESC
LIMIT 20
`

// MetricExpressions maps metric name → SQL aggregate expression.
var MetricExpressions = map[string]string{
	"fill_rate":   "sum(e.is_filled) / count()",
	"render_rate": "sum(e.is_impression) / nullIf(sum(e.is_filled), 0)",
	"ecpm":        "sum(e.revenue) / nullIf(sum(e.is_impression), 0) * 1000",
	"ctr":         "sum(e.is_click) / nullIf(sum(e.is_impression), 0)",
	"requests":    "count()",
}

// BuildContributionSQL renders the contribution SQL for a given dimension and metric.
// dimCol: e.g. "g.region" — the SELECT column for the dimension.
// fromClause: e.g. "FROM ad_events e INNER JOIN geo_device g ON e.geo_device_id = g.geo_device_id"
// filledOnlyFilter: "" or "AND e.advertiser_id != ”" for advertiser dimensions.
// metric: a key of MetricExpressions — selects both the aggregate and the
// impact weighting (volume-weighted for ratio metrics, raw delta for "requests").
// baselineDates: same-weekday prior days (see drilldown.baselineDatesFor) —
// each segment's baseline is the median across them, not a single fixed day.
func BuildContributionSQL(dimCol, fromClause, filledOnlyFilter, metric, currentDate string, baselineDates []string) string {
	metricExpr, ok := MetricExpressions[metric]
	if !ok {
		metricExpr = MetricExpressions["fill_rate"] // safe default
	}
	impactExpr := "cur_n * (cur_val - bas_val)"
	if metric == "requests" {
		impactExpr = "cur_val - bas_val"
	}
	return fmt.Sprintf(contributionSQLTemplate,
		dimCol, metricExpr, fromClause, currentDate, filledOnlyFilter, dateListSQL(baselineDates), impactExpr,
	)
}

// ── Segment Z-Score ───────────────────────────────────────────────────────────
// Use BuildSegmentZScoreSQL() to render.

const segmentZScoreSQLTemplate = `
WITH
seg_daily AS (
    SELECT
        toDate(e.event_time)          AS day,
        toDayOfWeek(e.event_time)     AS dow,
        %s                            AS seg,
        sum(e.is_filled) / count()    AS fill_rate,
        count()                       AS requests
    %s
    WHERE toDate(e.event_time) BETWEEN
        toDate('%s') - INTERVAL %d WEEK AND toDate('%s')
    GROUP BY day, dow, seg
),
target AS (
    SELECT seg, fill_rate, requests
    FROM seg_daily WHERE day = toDate('%s')
),
baseline_agg AS (
    SELECT
        b.seg,
        quantile(0.5)(b.fill_rate)                                        AS med_fill_rate,
        (quantile(0.75)(b.fill_rate) - quantile(0.25)(b.fill_rate)) / 1.35 AS sigma_fill_rate,
        count() AS n
    FROM seg_daily b
    JOIN target t ON b.seg = t.seg
    WHERE b.day < toDate('%s')
    GROUP BY b.seg
    HAVING count() >= 2
)
SELECT
    t.seg,
    t.fill_rate                                                          AS curr_fill_rate,
    ba.med_fill_rate                                                     AS baseline_fill_rate,
    round((t.fill_rate - ba.med_fill_rate) / nullIf(ba.sigma_fill_rate, 0), 2) AS z_score,
    ba.n
FROM target t
JOIN baseline_agg ba ON t.seg = ba.seg
ORDER BY abs(z_score) DESC
LIMIT 20
`

// BuildSegmentZScoreSQL renders the bottom-up segment z-score SQL.
func BuildSegmentZScoreSQL(dimCol, fromClause, targetDate string, lookbackWeeks int) string {
	return fmt.Sprintf(segmentZScoreSQLTemplate,
		dimCol, fromClause,
		targetDate, lookbackWeeks, targetDate,
		targetDate, targetDate,
	)
}

// ── Hold-out verification ─────────────────────────────────────────────────────
// Use BuildHoldOutSQL() to render. Recomputes the guilty metric excluding the
// winning segment/value for both periods — mechanizes the by-hand exclusion
// checks from the data-analysis phase (e.g. "EU-minus-Android-15") into an
// automatic step. If the excluded segment is truly the cause, the result
// should revert to (near) the baseline value.
//
// The baseline is the median across several same-weekday prior days, not a
// single fixed day — same rationale as BuildFactorDecompositionSQL.

// toFloat64() around the current-branch value: when metric is "requests",
// %[2]s is the bare count() (UInt64), and UNION ALL-ing that against the
// baseline branch's quantile(0.5)(val) (always Float64) would otherwise
// produce a Variant column — same issue as BuildFactorDecompositionSQL. A
// no-op cast for every other metric, which is already a Float64 ratio.
const holdOutSQLTemplate = `
SELECT 'current' AS period, toFloat64(%[2]s) AS val
%[3]s
WHERE toDate(e.event_time) = '%[4]s'
  AND %[1]s != '%[5]s'
  %[6]s
UNION ALL
SELECT 'baseline' AS period, quantile(0.5)(val) AS val
FROM (
    SELECT toDate(e.event_time) AS day, %[2]s AS val
    %[3]s
    WHERE toDate(e.event_time) IN (%[7]s)
      AND %[1]s != '%[5]s'
      %[6]s
    GROUP BY day
)
`

// BuildHoldOutSQL renders the hold-out verification query for `metric`,
// excluding rows where dimCol = segmentValue, for currentDate vs. the median
// of baselineDates.
func BuildHoldOutSQL(dimCol, fromClause, filledOnlyFilter, metric, segmentValue, currentDate string, baselineDates []string) string {
	metricExpr, ok := MetricExpressions[metric]
	if !ok {
		metricExpr = MetricExpressions["fill_rate"]
	}
	return fmt.Sprintf(holdOutSQLTemplate,
		dimCol, metricExpr, fromClause, currentDate, escapeSingleQuote(segmentValue), filledOnlyFilter, dateListSQL(baselineDates),
	)
}

// ── Pairwise / intersection precision ─────────────────────────────────────────
// Use BuildPairwiseSQL() to render. Scoped to the flagged window only — run on
// demand for the top 2 flagged single-dimension culprits, not pre-materialized.
// Narrows an over-broad single-dimension claim (e.g. "iOS 18.1", ~80K requests)
// down to the true intersection responsible (e.g. "iOS 18.1 x APAC", ~20K
// requests) when both dimensions independently score high explanatory power —
// the Simpson's-paradox signature.
//
// The baseline is the median across several same-weekday prior days, not a
// single fixed day — same rationale as BuildFactorDecompositionSQL. The
// current-branch count() is cast to Float64 for the same reason described
// there: UNION ALL-ing a plain UInt64 count() against quantile(0.5)(n)
// (always Float64) otherwise produces a Variant column the Go driver hands
// back as an opaque struct instead of a number.

const pairwiseSQLTemplate = `
SELECT 'current' AS period, %[3]s AS val, toFloat64(count()) AS n
%[1]s
WHERE toDate(e.event_time) = '%[6]s'
  AND %[4]s = '%[7]s'
  AND %[5]s = '%[8]s'
  %[2]s
UNION ALL
SELECT 'baseline' AS period, quantile(0.5)(val) AS val, quantile(0.5)(n) AS n
FROM (
    SELECT toDate(e.event_time) AS day, %[3]s AS val, count() AS n
    %[1]s
    WHERE toDate(e.event_time) IN (%[9]s)
      AND %[4]s = '%[7]s'
      AND %[5]s = '%[8]s'
      %[2]s
    GROUP BY day
)
`

// BuildPairwiseSQL renders the pairwise precision query for the intersection
// dim1Col = value1 AND dim2Col = value2, for currentDate vs. the median of
// baselineDates. fromClause/filledOnlyFilter should come from
// drilldown.CombinedFromClause so both dimensions' joins are present.
func BuildPairwiseSQL(dim1Col, dim2Col, fromClause, filledOnlyFilter, value1, value2, metric, currentDate string, baselineDates []string) string {
	metricExpr, ok := MetricExpressions[metric]
	if !ok {
		metricExpr = MetricExpressions["fill_rate"]
	}
	return fmt.Sprintf(pairwiseSQLTemplate,
		fromClause, filledOnlyFilter, metricExpr,
		dim1Col, dim2Col, currentDate, escapeSingleQuote(value1), escapeSingleQuote(value2), dateListSQL(baselineDates),
	)
}

// ── Incident upsert ───────────────────────────────────────────────────────────

// UpsertIncidentSQL — all non-string params are rendered via RenderSQL before execution.
const UpsertIncidentSQL = `
INSERT INTO incidents
    (id, metric, detector_id, dimension, segment, window_start, window_end,
     severity, status, z_score, cusum_val, deviation_pct, updated_at)
VALUES
    ({id:String}, {metric:String}, {detector_id:String},
     {dimension:String}, {segment:String},
     {window_start:String}, {window_end:String},
     {severity:String}, {status:String},
     {z_score:String}, {cusum_val:String}, {deviation_pct:String},
     now())
`
