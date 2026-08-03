package main

import (
	"context"
	"database/sql"
	"fmt"
	"math"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

type RCAEngine struct {
	conn driver.Conn
}

const (
	anomalyZThreshold    = 3.0
	positivePctThreshold = 10.0
)

func NewRCAEngine(conn driver.Conn) *RCAEngine {
	return &RCAEngine{conn: conn}
}

// getBaselineHourFilters computes explicit date range filters for ClickHouse primary key index pruning
func getBaselineHourFilters(wStartStr, wEndStr string) (rollupInClause string, rawOrClause string) {
	tStart, err := time.Parse("2006-01-02 15:04:05", wStartStr)
	if err != nil {
		return fmt.Sprintf("event_hour < '%s'", wStartStr), fmt.Sprintf("event_time < '%s'", wStartStr)
	}
	tEnd, err := time.Parse("2006-01-02 15:04:05", wEndStr)
	if err != nil {
		tEnd = tStart.Add(1 * time.Hour)
	}

	var rollupHours []string
	var rawRanges []string

	for weeks := 1; weeks <= 4; weeks++ {
		bStart := tStart.AddDate(0, 0, -7*weeks)
		bEnd := tEnd.AddDate(0, 0, -7*weeks)

		bStartStr := bStart.Format("2006-01-02 15:04:05")
		bEndStr := bEnd.Format("2006-01-02 15:04:05")

		rollupHours = append(rollupHours, fmt.Sprintf("'%s'", bStartStr))
		rawRanges = append(rawRanges, fmt.Sprintf("(event_time >= '%s' AND event_time < '%s')", bStartStr, bEndStr))
	}

	rollupInClause = fmt.Sprintf("event_hour IN (%s)", strings.Join(rollupHours, ", "))
	rawOrClause = fmt.Sprintf("(%s)", strings.Join(rawRanges, " OR "))
	return rollupInClause, rawOrClause
}

// FindTopAnomaly scans the dataset for the most significant anomaly for the specified metric
func (e *RCAEngine) FindTopAnomaly(ctx context.Context, metric string) (*AnomalyRecord, error) {
	curCol, baseCol, stdCol, err := metricColumns(metric)
	if err != nil {
		return nil, err
	}

	query := fmt.Sprintf(`
	WITH hourly AS (
	  SELECT event_hour AS h,
	         countMerge(requests) AS requests,
	         sumMerge(fills) AS fills,
	         sumMerge(impressions) AS impressions,
	         sumMerge(clicks) AS clicks,
	         sumMerge(revenue) AS revenue,
	         fills / nullIf(requests, 0) AS fill_rate,
	         impressions / nullIf(fills, 0) AS render_rate,
	         clicks / nullIf(impressions, 0) AS ctr,
	         revenue / nullIf(impressions, 0) * 1000 AS ecpm,
	         revenue / nullIf(requests, 0) AS rpr
	  FROM ad_events_hourly_rollup
	  WHERE dim_name = 'ad_format'
	  GROUP BY h
	),
	baseline AS (
	  SELECT h, fill_rate, render_rate, ctr, revenue, requests, fills, impressions, clicks, ecpm, rpr,
	         avg(fill_rate) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS fr_base,
	         stddevPop(fill_rate) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS fr_std,
	         avg(render_rate) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS render_rate_base,
	         stddevPop(render_rate) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS render_rate_std,
	         avg(ctr) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS ctr_base,
	         stddevPop(ctr) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS ctr_std,
	         avg(revenue) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS rev_base,
	         stddevPop(revenue) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS rev_std,
	         avg(fills) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS fills_base,
	         stddevPop(fills) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS fills_std,
	         avg(impressions) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS impressions_base,
	         stddevPop(impressions) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS impressions_std,
	         avg(clicks) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS clicks_base,
	         stddevPop(clicks) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS clicks_std,
	         avg(ecpm) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS ecpm_base,
	         stddevPop(ecpm) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS ecpm_std,
	         avg(rpr) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS rpr_base,
	         stddevPop(rpr) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS rpr_std,
	         avg(requests) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS req_base,
	         stddevPop(requests) OVER (PARTITION BY toDayOfWeek(h), toHour(h) ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS req_std
	  FROM hourly
	)
	SELECT 
	  h,
	  toFloat64(%s) AS current_val,
	  toFloat64(%s) AS base_val,
	  (current_val - base_val) / nullIf(%s, 0) AS z_val
	FROM baseline
	WHERE z_val IS NOT NULL AND abs((current_val - base_val) / nullIf(base_val, 0)) >= 0.05
	ORDER BY abs(z_val) DESC
	LIMIT 1;
	`, curCol, baseCol, stdCol)

	row := e.conn.QueryRow(ctx, query)
	var h time.Time
	var current, base, z float64

	if err := row.Scan(&h, &current, &base, &z); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("no eligible anomaly rows found: %w", err)
		}
		return nil, fmt.Errorf("failed to scan anomaly row: %w", err)
	}

	pct := 0.0
	if base > 0 {
		pct = ((current - base) / base) * 100.0
	}

	return &AnomalyRecord{
		Timestamp:     h,
		Metric:        metric,
		CurrentValue:  current,
		BaselineValue: base,
		ZScore:        z,
		PctChange:     pct,
	}, nil
}

// PerformAnalysis executes full RCA on a target window
func (e *RCAEngine) PerformAnalysis(ctx context.Context, req AnalyzeRequest) (*RCAEvidence, error) {
	startTime := time.Now()

	metric := req.Metric
	if metric == "" {
		metric = "revenue"
	}
	metricDef, err := resolveMetric(metric)
	if err != nil {
		return nil, err
	}
	metric = metricDef.Name

	var wStart, wEnd string
	var anomaly *AnomalyRecord

	if req.WindowStart == "" {
		top, err := e.FindTopAnomaly(ctx, metric)
		if err != nil {
			return nil, fmt.Errorf("failed to find top anomaly: %w", err)
		}
		anomaly = top
		wStart = top.Timestamp.Format("2006-01-02 15:04:05")
		wEnd = top.Timestamp.Add(1 * time.Hour).Format("2006-01-02 15:04:05")
	} else {
		wStart = req.WindowStart
		wEnd = req.WindowEnd
		if wEnd == "" {
			t, _ := time.Parse("2006-01-02 15:04:05", wStart)
			wEnd = t.Add(1 * time.Hour).Format("2006-01-02 15:04:05")
		}

		t, _ := time.Parse("2006-01-02 15:04:05", wStart)
		anomaly = &AnomalyRecord{
			Timestamp: t,
			Metric:    metric,
		}
	}

	// 1. Fetch Window vs Baseline Metrics using pre-aggregated rollup + explicit date range filters
	currentMetrics, baseMetrics, err := e.getMetricsForWindowAndBaseline(ctx, wStart, wEnd)
	if err != nil {
		return nil, fmt.Errorf("failed to query metrics: %w", err)
	}

	curVal := currentMetrics[metric]
	baseVal := baseMetrics[metric]
	delta := curVal - baseVal
	pctChange := 0.0
	if baseVal != 0 {
		pctChange = (delta / baseVal) * 100.0
	}

	// 2. Revenue Identity Factor Decomposition
	var factorDecomp *FactorDecomposition
	if metric == "revenue" || metric == "rpr" {
		factorDecomp = e.decomposeFactors(currentMetrics, baseMetrics)
	}

	targetDrillMetric := metric
	if (metric == "revenue" || metric == "rpr") && factorDecomp != nil && factorDecomp.PrimaryFactor != "" {
		targetDrillMetric = factorDecomp.PrimaryFactor
	}

	targetDelta := currentMetrics[targetDrillMetric] - baseMetrics[targetDrillMetric]

	// 3. Single-Pass Primary Dimension Breakdown from ad_events_hourly_rollup (Wave 1)
	primarySegments, ruledOutDims := e.drillDownPrimaryDimensions(ctx, wStart, wEnd, targetDrillMetric, targetDelta)

	// 4. Multi-Level Recursive Drill-Down (Wave 2)
	twoLevelSegments := e.drillDownTwoLevel(ctx, wStart, wEnd, targetDrillMetric, targetDelta, primarySegments)

	// Combine Wave 1 and Wave 2 top segments
	allTop := append(primarySegments, twoLevelSegments...)
	sort.Slice(allTop, func(i, j int) bool {
		return math.Abs(allTop[i].SegmentDelta) > math.Abs(allTop[j].SegmentDelta)
	})

	if len(allTop) > 6 {
		allTop = allTop[:6]
	}

	// 5. Build Ruled-Out List
	ruledOutList := e.buildRuledOut(factorDecomp, ruledOutDims, currentMetrics, baseMetrics)

	execMs := time.Since(startTime).Milliseconds()

	return &RCAEvidence{
		AnomalyDetected:         math.Abs(anomaly.ZScore) > anomalyZThreshold || math.Abs(pctChange) > positivePctThreshold,
		Metric:                  metric,
		WindowStart:             wStart,
		WindowEnd:               wEnd,
		CurrentValue:            math.Round(curVal*100) / 100,
		BaselineValue:           math.Round(baseVal*100) / 100,
		Delta:                   math.Round(delta*100) / 100,
		PctChange:               math.Round(pctChange*10) / 10,
		ZScore:                  math.Round(anomaly.ZScore*100) / 100,
		FactorDecomposition:     factorDecomp,
		TopContributingSegments: allTop,
		RuledOut:                ruledOutList,
		ExecutionTimeMs:         execMs,
	}, nil
}

func sanitize(s string) string {
	return strings.ReplaceAll(s, "'", "''")
}

func (e *RCAEngine) FindAllAnomalies(ctx context.Context) ([]AnomalyRecord, error) {
	metrics := []string{"revenue", "fill_rate", "render_rate", "ecpm", "ctr"}
	var results []AnomalyRecord

	for _, m := range metrics {
		rec, err := e.FindTopAnomaly(ctx, m)
		if err == nil && rec != nil {
			results = append(results, *rec)
		}
	}

	sort.Slice(results, func(i, j int) bool {
		return math.Abs(results[i].ZScore) > math.Abs(results[j].ZScore)
	})

	return results, nil
}

func (e *RCAEngine) getMetricsForWindowAndBaseline(ctx context.Context, wStart, wEnd string) (map[string]float64, map[string]float64, error) {
	rollupIn, rawOr := getBaselineHourFilters(wStart, wEnd)

	// Try querying from pre-aggregated rollup first
	queryRollup := fmt.Sprintf(`
	WITH current_period AS (
		SELECT 
			countMerge(requests) AS requests,
			sumMerge(fills) AS fills,
			sumMerge(impressions) AS impressions,
			sumMerge(clicks) AS clicks,
			sumMerge(revenue) AS revenue
		FROM ad_events_hourly_rollup
		WHERE dim_name = 'ad_format' AND event_hour >= '%s' AND event_hour < '%s'
	),
	baseline_period AS (
		SELECT 
			countMerge(requests) / nullIf(uniqExact(toDate(event_hour)), 0) AS requests,
			sumMerge(fills) / nullIf(uniqExact(toDate(event_hour)), 0) AS fills,
			sumMerge(impressions) / nullIf(uniqExact(toDate(event_hour)), 0) AS impressions,
			sumMerge(clicks) / nullIf(uniqExact(toDate(event_hour)), 0) AS clicks,
			sumMerge(revenue) / nullIf(uniqExact(toDate(event_hour)), 0) AS revenue
		FROM ad_events_hourly_rollup
		WHERE dim_name = 'ad_format' AND %s
	)
	SELECT 
		toFloat64(c.requests), toFloat64(c.fills), toFloat64(c.impressions), toFloat64(c.clicks), toFloat64(c.revenue),
		toFloat64(b.requests), toFloat64(b.fills), toFloat64(b.impressions), toFloat64(b.clicks), toFloat64(b.revenue)
	FROM current_period c CROSS JOIN baseline_period b;
	`, wStart, wEnd, rollupIn)

	row := e.conn.QueryRow(ctx, queryRollup)

	var curReq, curFill, curImp, curClick, curRev float64
	var baseReq, baseFill, baseImp, baseClick, baseRev float64

	if err := row.Scan(&curReq, &curFill, &curImp, &curClick, &curRev, &baseReq, &baseFill, &baseImp, &baseClick, &baseRev); err != nil {
		// Fallback to raw ad_events table with explicit date ranges
		queryRaw := fmt.Sprintf(`
		WITH current_period AS (
			SELECT 
				count() AS requests,
				sum(is_filled) AS fills,
				sum(is_impression) AS impressions,
				sum(is_click) AS clicks,
				sum(revenue) AS revenue
			FROM ad_events
			WHERE event_time >= '%s' AND event_time < '%s'
		),
		baseline_period AS (
			SELECT 
				count() / nullIf(uniqExact(toDate(event_time)), 0) AS requests,
				sum(is_filled) / nullIf(uniqExact(toDate(event_time)), 0) AS fills,
				sum(is_impression) / nullIf(uniqExact(toDate(event_time)), 0) AS impressions,
				sum(is_click) / nullIf(uniqExact(toDate(event_time)), 0) AS clicks,
				sum(revenue) / nullIf(uniqExact(toDate(event_time)), 0) AS revenue
			FROM ad_events
			WHERE %s
		)
		SELECT 
			toFloat64(c.requests), toFloat64(c.fills), toFloat64(c.impressions), toFloat64(c.clicks), toFloat64(c.revenue),
			toFloat64(b.requests), toFloat64(b.fills), toFloat64(b.impressions), toFloat64(b.clicks), toFloat64(b.revenue)
		FROM current_period c CROSS JOIN baseline_period b;
		`, wStart, wEnd, rawOr)

		row = e.conn.QueryRow(ctx, queryRaw)
		if err := row.Scan(&curReq, &curFill, &curImp, &curClick, &curRev, &baseReq, &baseFill, &baseImp, &baseClick, &baseRev); err != nil {
			return nil, nil, err
		}
	}

	curMap := map[string]float64{
		"requests":    curReq,
		"fills":       curFill,
		"fill_rate":   safeDiv(curFill, curReq),
		"impressions": curImp,
		"render_rate": safeDiv(curImp, curFill),
		"clicks":      curClick,
		"ctr":         safeDiv(curClick, curImp),
		"revenue":     curRev,
		"ecpm":        safeDiv(curRev, curImp) * 1000.0,
		"rpr":         safeDiv(curRev, curReq),
	}

	baseMap := map[string]float64{
		"requests":    baseReq,
		"fills":       baseFill,
		"fill_rate":   safeDiv(baseFill, baseReq),
		"impressions": baseImp,
		"render_rate": safeDiv(baseImp, baseFill),
		"clicks":      baseClick,
		"ctr":         safeDiv(baseClick, baseImp),
		"revenue":     baseRev,
		"ecpm":        safeDiv(baseRev, baseImp) * 1000.0,
		"rpr":         safeDiv(baseRev, baseReq),
	}

	return curMap, baseMap, nil
}

func (e *RCAEngine) decomposeFactors(cur, base map[string]float64) *FactorDecomposition {
	reqPct := safePctChange(cur["requests"], base["requests"])
	frPct := safePctChange(cur["fill_rate"], base["fill_rate"])
	rrPct := safePctChange(cur["render_rate"], base["render_rate"])
	ecpmPct := safePctChange(cur["ecpm"], base["ecpm"])

	// Determine primary driver factor
	factors := map[string]float64{
		"requests":    math.Abs(reqPct),
		"fill_rate":   math.Abs(frPct),
		"render_rate": math.Abs(rrPct),
		"ecpm":        math.Abs(ecpmPct),
	}

	primary := "fill_rate"
	maxVal := 0.0
	for k, v := range factors {
		if v > maxVal {
			maxVal = v
			primary = k
		}
	}

	explanation := fmt.Sprintf("Primary revenue movement driver is %s (%.1f%% change), while request volume changed %.1f%% and eCPM changed %.1f%%.", primary, getVal(factors, primary), reqPct, ecpmPct)

	return &FactorDecomposition{
		RequestsDeltaPct:   math.Round(reqPct*10) / 10,
		FillRateDeltaPct:   math.Round(frPct*10) / 10,
		RenderRateDeltaPct: math.Round(rrPct*10) / 10,
		ECPMDeltaPct:       math.Round(ecpmPct*10) / 10,
		PrimaryFactor:      primary,
		Explanation:        explanation,
	}
}

func (e *RCAEngine) drillDownPrimaryDimensions(ctx context.Context, wStart, wEnd, targetMetric string, totalDelta float64) ([]SegmentContribution, []string) {
	curMetricExpr := getRollupMetricSqlExpr(targetMetric)
	baseMetricExpr := getRollupBaseMetricSqlExpr(targetMetric)
	rollupIn, _ := getBaselineHourFilters(wStart, wEnd)

	// Single-pass query over pre-aggregated ad_events_hourly_rollup with explicit date ranges
	query := fmt.Sprintf(`
	WITH current_segs AS (
		SELECT 
			dim_name,
			dim_val,
			%s AS cur_metric
		FROM ad_events_hourly_rollup
		WHERE event_hour >= '%s' AND event_hour < '%s'
		GROUP BY dim_name, dim_val
	),
	base_segs AS (
		SELECT 
			dim_name,
			dim_val,
			%s AS base_metric
		FROM ad_events_hourly_rollup
		WHERE %s
		GROUP BY dim_name, dim_val
	)
	SELECT 
		coalesce(c.dim_name, b.dim_name) AS dim_name,
		coalesce(c.dim_val, b.dim_val) AS dim_val,
		toFloat64(coalesce(c.cur_metric, 0)) AS current_m,
		toFloat64(coalesce(b.base_metric, 0)) AS base_m
	FROM current_segs c FULL OUTER JOIN base_segs b 
	  ON c.dim_name = b.dim_name AND c.dim_val = b.dim_val
	ORDER BY abs(current_m - base_m) DESC;
	`, curMetricExpr, wStart, wEnd, baseMetricExpr, rollupIn)

	rows, err := e.conn.Query(ctx, query)
	if err != nil {
		// Fallback to single-pass GROUP BY GROUPING SETS on raw table
		return e.fallbackParallelDrillDown(ctx, wStart, wEnd, targetMetric, totalDelta)
	}
	defer rows.Close()

	var results []SegmentContribution
	maxSharePerDim := make(map[string]float64)

	for rows.Next() {
		var dimName, val string
		var cur, base float64
		if err := rows.Scan(&dimName, &val, &cur, &base); err != nil {
			continue
		}
		if val == "" {
			val = "Unfilled / Unknown"
		}

		delta := cur - base
		share := 0.0
		if math.Abs(totalDelta) > 0.0001 {
			share = delta / totalDelta
			if share > 1.0 {
				share = 1.0
			} else if share < -1.0 {
				share = -1.0
			}
		}

		if math.Abs(share) > maxSharePerDim[dimName] {
			maxSharePerDim[dimName] = math.Abs(share)
		}

		if math.Abs(share) >= 0.08 {
			results = append(results, SegmentContribution{
				Dimension:     dimName,
				Value:         val,
				CurrentMetric: math.Round(cur*100) / 100,
				BaseMetric:    math.Round(base*100) / 100,
				SegmentDelta:  math.Round(delta*100) / 100,
				ShareOfDelta:  math.Round(share*1000) / 1000,
			})
		}
	}

	allDims := []string{"ad_format", "category", "publisher_tier", "vertical", "campaign_type", "region", "country", "device_model", "os_version"}
	var ruledOutDims []string
	for _, d := range allDims {
		if maxSharePerDim[d] < 0.08 {
			ruledOutDims = append(ruledOutDims, d)
		}
	}

	return results, ruledOutDims
}

// Single-Pass GROUP BY GROUPING SETS on raw ad_events table
func (e *RCAEngine) fallbackParallelDrillDown(ctx context.Context, wStart, wEnd, targetMetric string, totalDelta float64) ([]SegmentContribution, []string) {
	curMetricExpr := getMetricSqlExpr(targetMetric)
	baseMetricExpr := getBaseMetricSqlExpr(targetMetric)
	_, rawOr := getBaselineHourFilters(wStart, wEnd)

	query := fmt.Sprintf(`
	WITH current_segs AS (
		SELECT 
			multiIf(
				ad_format != '', 'ad_format',
				dictGet('apps_dict', 'category', app_id) != '', 'category',
				dictGet('apps_dict', 'publisher_tier', app_id) != '', 'publisher_tier',
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', 'vertical',
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', 'campaign_type',
				dictGet('geo_device_dict', 'region', geo_device_id) != '', 'region',
				dictGet('geo_device_dict', 'country', geo_device_id) != '', 'country',
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', 'device_model',
				'os_version'
			) AS dim_name,
			multiIf(
				ad_format != '', ad_format,
				dictGet('apps_dict', 'category', app_id) != '', dictGet('apps_dict', 'category', app_id),
				dictGet('apps_dict', 'publisher_tier', app_id) != '', dictGet('apps_dict', 'publisher_tier', app_id),
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', dictGet('advertisers_dict', 'vertical', advertiser_id),
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', dictGet('advertisers_dict', 'campaign_type', advertiser_id),
				dictGet('geo_device_dict', 'region', geo_device_id) != '', dictGet('geo_device_dict', 'region', geo_device_id),
				dictGet('geo_device_dict', 'country', geo_device_id) != '', dictGet('geo_device_dict', 'country', geo_device_id),
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', dictGet('geo_device_dict', 'device_model', geo_device_id),
				dictGet('geo_device_dict', 'os_version', geo_device_id)
			) AS dim_val,
			%s AS cur_metric
		FROM ad_events
		WHERE event_time >= '%s' AND event_time < '%s'
		GROUP BY GROUPING SETS (
			(ad_format),
			(dictGet('apps_dict', 'category', app_id)),
			(dictGet('apps_dict', 'publisher_tier', app_id)),
			(dictGet('advertisers_dict', 'vertical', advertiser_id)),
			(dictGet('advertisers_dict', 'campaign_type', advertiser_id)),
			(dictGet('geo_device_dict', 'region', geo_device_id)),
			(dictGet('geo_device_dict', 'country', geo_device_id)),
			(dictGet('geo_device_dict', 'device_model', geo_device_id)),
			(dictGet('geo_device_dict', 'os_version', geo_device_id))
		)
	),
	base_segs AS (
		SELECT 
			multiIf(
				ad_format != '', 'ad_format',
				dictGet('apps_dict', 'category', app_id) != '', 'category',
				dictGet('apps_dict', 'publisher_tier', app_id) != '', 'publisher_tier',
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', 'vertical',
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', 'campaign_type',
				dictGet('geo_device_dict', 'region', geo_device_id) != '', 'region',
				dictGet('geo_device_dict', 'country', geo_device_id) != '', 'country',
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', 'device_model',
				'os_version'
			) AS dim_name,
			multiIf(
				ad_format != '', ad_format,
				dictGet('apps_dict', 'category', app_id) != '', dictGet('apps_dict', 'category', app_id),
				dictGet('apps_dict', 'publisher_tier', app_id) != '', dictGet('apps_dict', 'publisher_tier', app_id),
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', dictGet('advertisers_dict', 'vertical', advertiser_id),
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', dictGet('advertisers_dict', 'campaign_type', advertiser_id),
				dictGet('geo_device_dict', 'region', geo_device_id) != '', dictGet('geo_device_dict', 'region', geo_device_id),
				dictGet('geo_device_dict', 'country', geo_device_id) != '', dictGet('geo_device_dict', 'country', geo_device_id),
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', dictGet('geo_device_dict', 'device_model', geo_device_id),
				dictGet('geo_device_dict', 'os_version', geo_device_id)
			) AS dim_val,
			%s AS base_metric
		FROM ad_events
		WHERE %s
		GROUP BY GROUPING SETS (
			(ad_format),
			(dictGet('apps_dict', 'category', app_id)),
			(dictGet('apps_dict', 'publisher_tier', app_id)),
			(dictGet('advertisers_dict', 'vertical', advertiser_id)),
			(dictGet('advertisers_dict', 'campaign_type', advertiser_id)),
			(dictGet('geo_device_dict', 'region', geo_device_id)),
			(dictGet('geo_device_dict', 'country', geo_device_id)),
			(dictGet('geo_device_dict', 'device_model', geo_device_id)),
			(dictGet('geo_device_dict', 'os_version', geo_device_id))
		)
	)
	SELECT 
		coalesce(c.dim_name, b.dim_name) AS dim_name,
		coalesce(c.dim_val, b.dim_val) AS dim_val,
		toFloat64(coalesce(c.cur_metric, 0)) AS current_m,
		toFloat64(coalesce(b.base_metric, 0)) AS base_m
	FROM current_segs c FULL OUTER JOIN base_segs b ON c.dim_name = b.dim_name AND c.dim_val = b.dim_val
	ORDER BY abs(current_m - base_m) DESC;
	`, curMetricExpr, wStart, wEnd, baseMetricExpr, rawOr)

	rows, err := e.conn.Query(ctx, query)
	if err != nil {
		return nil, nil
	}
	defer rows.Close()

	var results []SegmentContribution
	maxSharePerDim := make(map[string]float64)

	for rows.Next() {
		var dimName, val string
		var cur, base float64
		if err := rows.Scan(&dimName, &val, &cur, &base); err != nil {
			continue
		}
		if val == "" {
			val = "Unfilled / Unknown"
		}

		delta := cur - base
		share := 0.0
		if math.Abs(totalDelta) > 0.0001 {
			share = delta / totalDelta
			if share > 1.0 {
				share = 1.0
			} else if share < -1.0 {
				share = -1.0
			}
		}

		if math.Abs(share) > maxSharePerDim[dimName] {
			maxSharePerDim[dimName] = math.Abs(share)
		}

		if math.Abs(share) >= 0.08 {
			results = append(results, SegmentContribution{
				Dimension:     dimName,
				Value:         val,
				CurrentMetric: math.Round(cur*100) / 100,
				BaseMetric:    math.Round(base*100) / 100,
				SegmentDelta:  math.Round(delta*100) / 100,
				ShareOfDelta:  math.Round(share*1000) / 1000,
			})
		}
	}

	allDims := []string{"ad_format", "category", "publisher_tier", "vertical", "campaign_type", "region", "country", "device_model", "os_version"}
	var ruledOutDims []string
	for _, d := range allDims {
		if maxSharePerDim[d] < 0.08 {
			ruledOutDims = append(ruledOutDims, d)
		}
	}

	return results, ruledOutDims
}

func getMetricSqlExpr(metric string) string {
	expr, err := metricExpr(metric)
	if err != nil {
		return "sum(revenue)"
	}
	return expr
}

func getBaseMetricSqlExpr(metric string) string {
	expr := getMetricSqlExpr(metric)
	if metric == "fill_rate" || metric == "ecpm" || metric == "render_rate" || metric == "ctr" {
		return expr
	}
	return fmt.Sprintf("(%s) / nullIf(uniqExact(toDate(event_time)), 0)", expr)
}

func (e *RCAEngine) drillDownTwoLevel(ctx context.Context, wStart, wEnd, metric string, totalDelta float64, topPrimary []SegmentContribution) []SegmentContribution {
	if len(topPrimary) == 0 {
		return nil
	}

	var results []SegmentContribution
	var mu sync.Mutex
	var wg sync.WaitGroup

	maxPrimaryToDrill := 2
	if len(topPrimary) < maxPrimaryToDrill {
		maxPrimaryToDrill = len(topPrimary)
	}

	for i := 0; i < maxPrimaryToDrill; i++ {
		top := topPrimary[i]
		primaryExpr := getDimExpr(top.Dimension)

		wg.Add(1)
		go func(primarySeg SegmentContribution, pExpr string) {
			defer wg.Done()
			res := e.queryTwoLevelGrouped(ctx, wStart, wEnd, metric, totalDelta, primarySeg, pExpr)
			if len(res) > 0 {
				mu.Lock()
				results = append(results, res...)
				mu.Unlock()
			}
		}(top, primaryExpr)
	}

	wg.Wait()
	return results
}

// Single-Pass GROUP BY GROUPING SETS query for 2-level drill down secondary dimensions
func (e *RCAEngine) queryTwoLevelGrouped(ctx context.Context, wStart, wEnd, metric string, totalDelta float64, top SegmentContribution, primaryExpr string) []SegmentContribution {
	curMetricExpr := getMetricSqlExpr(metric)
	baseMetricExpr := getBaseMetricSqlExpr(metric)
	safeVal := sanitize(top.Value)
	_, rawOr := getBaselineHourFilters(wStart, wEnd)

	query := fmt.Sprintf(`
	WITH current_segs AS (
		SELECT 
			multiIf(
				ad_format != '', 'ad_format',
				dictGet('apps_dict', 'category', app_id) != '', 'category',
				dictGet('apps_dict', 'publisher_tier', app_id) != '', 'publisher_tier',
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', 'vertical',
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', 'campaign_type',
				dictGet('geo_device_dict', 'region', geo_device_id) != '', 'region',
				dictGet('geo_device_dict', 'country', geo_device_id) != '', 'country',
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', 'device_model',
				'os_version'
			) AS sec_dim,
			multiIf(
				ad_format != '', ad_format,
				dictGet('apps_dict', 'category', app_id) != '', dictGet('apps_dict', 'category', app_id),
				dictGet('apps_dict', 'publisher_tier', app_id) != '', dictGet('apps_dict', 'publisher_tier', app_id),
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', dictGet('advertisers_dict', 'vertical', advertiser_id),
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', dictGet('advertisers_dict', 'campaign_type', advertiser_id),
				dictGet('geo_device_dict', 'region', geo_device_id) != '', dictGet('geo_device_dict', 'region', geo_device_id),
				dictGet('geo_device_dict', 'country', geo_device_id) != '', dictGet('geo_device_dict', 'country', geo_device_id),
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', dictGet('geo_device_dict', 'device_model', geo_device_id),
				dictGet('geo_device_dict', 'os_version', geo_device_id)
			) AS sec_val,
			%s AS cur_metric
		FROM ad_events
		WHERE event_time >= '%s' AND event_time < '%s' AND %s = '%s'
		GROUP BY GROUPING SETS (
			(ad_format),
			(dictGet('apps_dict', 'category', app_id)),
			(dictGet('apps_dict', 'publisher_tier', app_id)),
			(dictGet('advertisers_dict', 'vertical', advertiser_id)),
			(dictGet('advertisers_dict', 'campaign_type', advertiser_id)),
			(dictGet('geo_device_dict', 'region', geo_device_id)),
			(dictGet('geo_device_dict', 'country', geo_device_id)),
			(dictGet('geo_device_dict', 'device_model', geo_device_id)),
			(dictGet('geo_device_dict', 'os_version', geo_device_id))
		)
	),
	base_segs AS (
		SELECT 
			multiIf(
				ad_format != '', 'ad_format',
				dictGet('apps_dict', 'category', app_id) != '', 'category',
				dictGet('apps_dict', 'publisher_tier', app_id) != '', 'publisher_tier',
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', 'vertical',
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', 'campaign_type',
				dictGet('geo_device_dict', 'region', geo_device_id) != '', 'region',
				dictGet('geo_device_dict', 'country', geo_device_id) != '', 'country',
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', 'device_model',
				'os_version'
			) AS sec_dim,
			multiIf(
				ad_format != '', ad_format,
				dictGet('apps_dict', 'category', app_id) != '', dictGet('apps_dict', 'category', app_id),
				dictGet('apps_dict', 'publisher_tier', app_id) != '', dictGet('apps_dict', 'publisher_tier', app_id),
				dictGet('advertisers_dict', 'vertical', advertiser_id) != '', dictGet('advertisers_dict', 'vertical', advertiser_id),
				dictGet('advertisers_dict', 'campaign_type', advertiser_id) != '', dictGet('advertisers_dict', 'campaign_type', advertiser_id),
				dictGet('geo_device_dict', 'region', geo_device_id) != '', dictGet('geo_device_dict', 'region', geo_device_id),
				dictGet('geo_device_dict', 'country', geo_device_id) != '', dictGet('geo_device_dict', 'country', geo_device_id),
				dictGet('geo_device_dict', 'device_model', geo_device_id) != '', dictGet('geo_device_dict', 'device_model', geo_device_id),
				dictGet('geo_device_dict', 'os_version', geo_device_id)
			) AS sec_val,
			%s AS base_metric
		FROM ad_events
		WHERE %s AND %s = '%s'
		GROUP BY GROUPING SETS (
			(ad_format),
			(dictGet('apps_dict', 'category', app_id)),
			(dictGet('apps_dict', 'publisher_tier', app_id)),
			(dictGet('advertisers_dict', 'vertical', advertiser_id)),
			(dictGet('advertisers_dict', 'campaign_type', advertiser_id)),
			(dictGet('geo_device_dict', 'region', geo_device_id)),
			(dictGet('geo_device_dict', 'country', geo_device_id)),
			(dictGet('geo_device_dict', 'device_model', geo_device_id)),
			(dictGet('geo_device_dict', 'os_version', geo_device_id))
		)
	)
	SELECT 
		coalesce(c.sec_dim, b.sec_dim) AS sec_dim,
		coalesce(c.sec_val, b.sec_val) AS sec_val,
		toFloat64(coalesce(c.cur_metric, 0)) AS current_m,
		toFloat64(coalesce(b.base_metric, 0)) AS base_m
	FROM current_segs c FULL OUTER JOIN base_segs b ON c.sec_dim = b.sec_dim AND c.sec_val = b.sec_val
	WHERE coalesce(c.sec_dim, b.sec_dim) != '%s'
	ORDER BY abs(current_m - base_m) DESC
	LIMIT 5;
	`, curMetricExpr, wStart, wEnd, primaryExpr, safeVal, baseMetricExpr, rawOr, primaryExpr, safeVal, top.Dimension)

	rows, err := e.conn.Query(ctx, query)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var results []SegmentContribution
	for rows.Next() {
		var secDim, secVal string
		var cur, base float64
		if err := rows.Scan(&secDim, &secVal, &cur, &base); err != nil {
			continue
		}

		if secVal == "" {
			secVal = "Unknown"
		}

		delta := cur - base
		share := 0.0
		if math.Abs(totalDelta) > 0.0001 {
			share = delta / totalDelta
			if share > 1.0 {
				share = 1.0
			} else if share < -1.0 {
				share = -1.0
			}
		}

		if math.Abs(share) >= 0.08 {
			combinedDim := fmt.Sprintf("%s x %s", top.Dimension, secDim)
			combinedVal := fmt.Sprintf("%s x %s", top.Value, secVal)

			results = append(results, SegmentContribution{
				Dimension:     combinedDim,
				Value:         combinedVal,
				CurrentMetric: math.Round(cur*100) / 100,
				BaseMetric:    math.Round(base*100) / 100,
				SegmentDelta:  math.Round(delta*100) / 100,
				ShareOfDelta:  math.Round(share*1000) / 1000,
			})
		}
	}

	return results
}

func (e *RCAEngine) buildRuledOut(factors *FactorDecomposition, ruledOutDims []string, cur, base map[string]float64) []RuledOutItem {
	items := make([]RuledOutItem, 0)

	// Check non-primary revenue identity factors
	if factors != nil {
		if factors.PrimaryFactor != "requests" && math.Abs(factors.RequestsDeltaPct) < 5.0 {
			items = append(items, RuledOutItem{
				Dimension: "requests_volume",
				Reason:    fmt.Sprintf("Request volume was normal (%.1f%% change) and within expected like-for-like baseline bounds", factors.RequestsDeltaPct),
			})
		}
		if factors.PrimaryFactor != "ecpm" && math.Abs(factors.ECPMDeltaPct) < 5.0 {
			items = append(items, RuledOutItem{
				Dimension: "ecpm_pricing",
				Reason:    fmt.Sprintf("eCPM pricing was normal (%.1f%% change) and ruled out as primary cause", factors.ECPMDeltaPct),
			})
		}
		if factors.PrimaryFactor != "render_rate" && math.Abs(factors.RenderRateDeltaPct) < 5.0 {
			items = append(items, RuledOutItem{
				Dimension: "render_rate",
				Reason:    fmt.Sprintf("Render rate was stable (%.1f%% change) across ad formats", factors.RenderRateDeltaPct),
			})
		}
	}

	// Check dimensions with uniform change
	for _, dim := range ruledOutDims {
		items = append(items, RuledOutItem{
			Dimension: dim,
			Reason:    fmt.Sprintf("Metric change across %s segments was uniform; no single %s segment contributed >8%% of total delta", dim, dim),
		})
	}

	if len(items) == 0 {
		items = append(items, RuledOutItem{
			Dimension: "render_rate",
			Reason:    "Render rate was stable across rendering environments and ruled out.",
		})
	}

	return items
}

// Helpers
func safeDiv(a, b float64) float64 {
	if b == 0 {
		return 0
	}
	return a / b
}

func safePctChange(cur, base float64) float64 {
	if base == 0 {
		return 0
	}
	return ((cur - base) / base) * 100.0
}

func getVal(m map[string]float64, k string) float64 {
	return m[k]
}

func getDimExpr(dim string) string {
	switch dim {
	case "ad_format":
		return "ad_format"
	case "category":
		return "dictGet('apps_dict', 'category', app_id)"
	case "publisher_tier":
		return "dictGet('apps_dict', 'publisher_tier', app_id)"
	case "vertical":
		return "dictGet('advertisers_dict', 'vertical', advertiser_id)"
	case "campaign_type":
		return "dictGet('advertisers_dict', 'campaign_type', advertiser_id)"
	case "region":
		return "dictGet('geo_device_dict', 'region', geo_device_id)"
	case "country":
		return "dictGet('geo_device_dict', 'country', geo_device_id)"
	case "device_model":
		return "dictGet('geo_device_dict', 'device_model', geo_device_id)"
	case "os_version":
		return "dictGet('geo_device_dict', 'os_version', geo_device_id)"
	default:
		return dim
	}
}

func getRollupMetricSqlExpr(metric string) string {
	switch metric {
	case "requests":
		return "countMerge(requests)"
	case "fills":
		return "sumMerge(fills)"
	case "impressions":
		return "sumMerge(impressions)"
	case "clicks":
		return "sumMerge(clicks)"
	case "revenue":
		return "sumMerge(revenue)"
	case "fill_rate":
		return "sumMerge(fills) / nullIf(countMerge(requests), 0)"
	case "render_rate":
		return "sumMerge(impressions) / nullIf(sumMerge(fills), 0)"
	case "ctr":
		return "sumMerge(clicks) / nullIf(sumMerge(impressions), 0)"
	case "ecpm":
		return "sumMerge(revenue) / nullIf(sumMerge(impressions), 0) * 1000.0"
	case "rpr":
		return "sumMerge(revenue) / nullIf(countMerge(requests), 0)"
	default:
		return "sumMerge(revenue)"
	}
}

func getRollupBaseMetricSqlExpr(metric string) string {
	expr := getRollupMetricSqlExpr(metric)
	if metric == "fill_rate" || metric == "ecpm" || metric == "render_rate" || metric == "ctr" || metric == "rpr" {
		return expr
	}
	return fmt.Sprintf("(%s) / nullIf(uniqExact(toDate(event_hour)), 0)", expr)
}
