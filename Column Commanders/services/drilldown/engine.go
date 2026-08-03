package drilldown

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"sort"
	"sync"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/internal/telemetry"
	"clickhouse-go-service/services/anomalydetector"
)

// Engine runs the full drilldown investigation for an anomaly signal.
type Engine struct {
	qe     *query.Executor
	cfg    config.DetectionConfig
	logger *slog.Logger
}

// NewEngine creates a DrillDown Engine.
func NewEngine(qe *query.Executor, cfg config.DetectionConfig, logger *slog.Logger) *Engine {
	return &Engine{qe: qe, cfg: cfg, logger: logger}
}

// Investigate runs factor decomposition + contribution analysis for a signal.
// Implements alertmanager.DrillDownRunner.
func (e *Engine) Investigate(ctx context.Context, signal anomalydetector.AnomalySignal) (*DrillDownResult, error) {
	result, err := e.investigate(ctx, signal)
	return result, err
}

func (e *Engine) investigate(ctx context.Context, signal anomalydetector.AnomalySignal) (*DrillDownResult, error) {
	start := time.Now()
	allQueries := make([]string, 0, 20)

	currentDate := signal.Window.Target().Format("2006-01-02")
	// Same-weekday median over trailing weeks, not a single fixed "N days back"
	// day — a single baseline day can itself be anomalous (observed live: a
	// later incident's baseline landed exactly on the platform-wide volume-drop
	// day, making "requests" look ~84% up and wrongly win the guilty-factor
	// vote). Mirrors Detect's own same-weekday-median baseline for this reason.
	baselineDates := baselineDatesFor(signal.Window.Target(), e.cfg.LookbackWeeks)
	baselineDate := baselineDates[0] // most recent, for display/logging only

	e.logger.Info("drilldown started",
		slog.String("metric", signal.Metric),
		slog.String("current_date", currentDate),
		slog.Any("baseline_dates", baselineDates),
	)

	// Step 1: Factor decomposition
	{
		stepCtx, stepSpan := telemetry.StartSpan(ctx, "drilldown.factor_decomposition")
		decomp, factorSQL, err := e.decomposeFactors(stepCtx, currentDate, baselineDates)
		if err != nil {
			telemetry.RecordSpanError(stepSpan, err)
			stepSpan.End()
			return nil, fmt.Errorf("drilldown: factor decomp: %w", err)
		}
		allQueries = append(allQueries, factorSQL)
		telemetry.SetSpanInput(stepSpan, map[string]any{
			"current_date":   currentDate,
			"baseline_dates": baselineDates,
			"sql":            factorSQL,
		})
		telemetry.SetSpanOutput(stepSpan, map[string]any{
			"guilty_factor":     decomp.GuiltyFactor,
			"requests_delta":    decomp.Requests.DeltaPct,
			"fill_rate_delta":   decomp.FillRate.DeltaPct,
			"render_rate_delta": decomp.RenderRate.DeltaPct,
			"ecpm_delta":        decomp.ECPM.DeltaPct,
			"revenue_delta":     decomp.Revenue.DeltaPct,
			"ruled_out":         decomp.RuledOut,
		})
		stepSpan.End()

		// Step 2: Contribution analysis (all dimensions, parallel)
		skip := DimsToSkip(decomp.GuiltyFactor)
		stepCtx2, stepSpan2 := telemetry.StartSpan(ctx, "drilldown.contributions")
		culpritsByDim, dimSQLs, ruledOut, err := e.runContributions(stepCtx2, decomp.GuiltyFactor, currentDate, baselineDates, skip)
		if err != nil {
			telemetry.RecordSpanError(stepSpan2, err)
			stepSpan2.End()
			return nil, fmt.Errorf("drilldown: contribution: %w", err)
		}
		allQueries = append(allQueries, dimSQLs...)
		totalCulprits := 0
		for _, segs := range culpritsByDim {
			totalCulprits += len(segs)
		}
		telemetry.SetSpanInput(stepSpan2, map[string]any{
			"guilty_factor": decomp.GuiltyFactor,
			"skip_dims":     skip,
			"query_count":   len(dimSQLs),
		})
		telemetry.SetSpanOutput(stepSpan2, map[string]any{
			"culprit_count":  totalCulprits,
			"ruled_out_dims": ruledOut,
		})
		stepSpan2.End()

		// Step 3: Flatten and sort culprits
		var allCulprits []SegmentFinding
		for _, segs := range culpritsByDim {
			allCulprits = append(allCulprits, segs...)
		}
		sort.Slice(allCulprits, func(i, j int) bool {
			return math.Abs(allCulprits[i].ContributionPct) > math.Abs(allCulprits[j].ContributionPct)
		})

		// Step 4: Bottom-up segment z-score for top culprit dimension
		if len(allCulprits) > 0 {
			topDim := FindDimConfig(allCulprits[0].Dimension)
			if topDim != nil {
				segSQL := query.BuildSegmentZScoreSQL(topDim.DimCol, topDim.FromClause, currentDate, e.cfg.LookbackWeeks)
				allQueries = append(allQueries, segSQL)
				stepCtx3, stepSpan3 := telemetry.StartSpan(ctx, "drilldown.segment_zscore")
				telemetry.SetSpanInput(stepSpan3, map[string]any{
					"dimension": topDim.Key,
					"sql":       segSQL,
				})
				segRows, segErr := e.qe.Rows(stepCtx3, "segment_zscore_"+topDim.Key, segSQL)
				if segErr != nil {
					e.logger.Warn("segment z-score scan failed", slog.String("dim", topDim.Key), slog.Any("err", segErr))
					telemetry.RecordSpanError(stepSpan3, segErr)
				} else {
					enrichWithZScores(allCulprits, segRows, topDim.Key)
					telemetry.SetSpanOutput(stepSpan3, map[string]any{
						"enriched_segments": len(allCulprits),
						"top_segment":       allCulprits[0].Segment,
						"top_zscore":        allCulprits[0].ZScore,
					})
				}
				stepSpan3.End()
			}
		}

		// Step 5: Pairwise/intersection precision.
		var pairwise *PairwiseFinding
		if len(allCulprits) >= 2 {
			c1, c2 := allCulprits[0], allCulprits[1]
			if c1.Dimension != c2.Dimension && !c1.ColdStart && !c2.ColdStart &&
				math.Abs(c1.ContributionPct) >= e.cfg.PairwiseTriggerPct &&
				math.Abs(c2.ContributionPct) >= e.cfg.PairwiseTriggerPct {
				dim1 := FindDimConfig(c1.Dimension)
				dim2 := FindDimConfig(c2.Dimension)
				if dim1 != nil && dim2 != nil {
					fromClause, filledOnlyFilter := CombinedFromClause(*dim1, *dim2)
					pwSQL := query.BuildPairwiseSQL(
						dim1.DimCol, dim2.DimCol, fromClause, filledOnlyFilter,
						c1.Segment, c2.Segment, decomp.GuiltyFactor, currentDate, baselineDates,
					)
					allQueries = append(allQueries, pwSQL)
					stepCtx4, stepSpan4 := telemetry.StartSpan(ctx, "drilldown.pairwise")
					telemetry.SetSpanInput(stepSpan4, map[string]any{
						"dim1": c1.Dimension, "segment1": c1.Segment,
						"dim2": c2.Dimension, "segment2": c2.Segment,
						"sql": pwSQL,
					})
					pwRows, pwErr := e.qe.Rows(stepCtx4, "pairwise_"+dim1.Key+"_"+dim2.Key, pwSQL)
					if pwErr != nil {
						e.logger.Warn("pairwise precision scan failed",
							slog.String("dim1", dim1.Key), slog.String("dim2", dim2.Key), slog.Any("err", pwErr))
						telemetry.RecordSpanError(stepSpan4, pwErr)
					} else {
						pairwise = buildPairwiseFinding(dim1.Key, c1.Segment, dim2.Key, c2.Segment, pwRows, pwSQL)
						telemetry.SetSpanOutput(stepSpan4, pairwise)
					}
					stepSpan4.End()
				}
			}
		}

		// Step 6: Hold-out verification for the top culprit.
		var holdOut *HoldOutResult
		if len(allCulprits) > 0 && !allCulprits[0].ColdStart {
			top := allCulprits[0]
			if topDim := FindDimConfig(top.Dimension); topDim != nil {
				holdOutSQL := query.BuildHoldOutSQL(
					topDim.DimCol, topDim.FromClause, topDim.FilledOnlyFilter,
					decomp.GuiltyFactor, top.Segment, currentDate, baselineDates,
				)
				allQueries = append(allQueries, holdOutSQL)
				stepCtx5, stepSpan5 := telemetry.StartSpan(ctx, "drilldown.holdout")
				telemetry.SetSpanInput(stepSpan5, map[string]any{
					"dimension": top.Dimension,
					"segment":   top.Segment,
					"metric":    decomp.GuiltyFactor,
					"sql":       holdOutSQL,
				})
				holdOutRows, hoErr := e.qe.Rows(stepCtx5, "hold_out_"+topDim.Key, holdOutSQL)
				if hoErr != nil {
					e.logger.Warn("hold-out verification failed", slog.String("dim", topDim.Key), slog.Any("err", hoErr))
					telemetry.RecordSpanError(stepSpan5, hoErr)
				} else {
					holdOut = buildHoldOutResult(topDim.Key, top.Segment, holdOutRows, e.cfg.HoldOutRevertPct)
					telemetry.SetSpanOutput(stepSpan5, map[string]any{
						"reverted":            holdOut.Reverted,
						"deviation_with_excl": holdOut.DeviationPct,
						"excluded_segment":    holdOut.ExcludedSegment,
					})
				}
				stepSpan5.End()
			}
		}

		// Classification + completeness.
		classification := "global"
		completeness := 0.0
		if len(allCulprits) > 0 && !allCulprits[0].ColdStart {
			completeness = math.Abs(allCulprits[0].ContributionPct)
			if pairwise != nil {
				classification = "intersection"
			} else {
				classification = "single-segment"
			}
		}

		cap := e.cfg.MaxCulpritSegments
		if len(allCulprits) > cap {
			allCulprits = allCulprits[:cap]
		}

		return &DrillDownResult{
			AnomalyDate:       currentDate,
			BaselineDate:      baselineDate,
			Decomposition:     decomp,
			CulpritSegments:   allCulprits,
			RuledOutDims:      ruledOut,
			HoldOut:           holdOut,
			Pairwise:          pairwise,
			Classification:    classification,
			CompletenessScore: completeness,
			AllQueries:        allQueries,
			ExecutionTime:     time.Since(start),
		}, nil
	}
}

// buildPairwiseFinding parses the two-row (current/baseline) pairwise query result.
func buildPairwiseFinding(dim1, val1, dim2, val2 string, rows []map[string]any, sql string) *PairwiseFinding {
	pf := &PairwiseFinding{Dim1: dim1, Value1: val1, Dim2: dim2, Value2: val2, QuerySQL: sql}
	for _, row := range rows {
		period, _ := row["period"].(string)
		switch period {
		case "current":
			pf.CurrentValue = toF(row["val"])
			pf.CurrentN = int64(toF(row["n"]))
		case "baseline":
			pf.BaselineValue = toF(row["val"])
		}
	}
	return pf
}

// buildHoldOutResult parses the two-row (current/baseline) hold-out query result.
func buildHoldOutResult(dimKey, excludedSegment string, rows []map[string]any, revertThreshold float64) *HoldOutResult {
	var curVal, basVal float64
	for _, row := range rows {
		period, _ := row["period"].(string)
		val := toF(row["val"])
		switch period {
		case "current":
			curVal = val
		case "baseline":
			basVal = val
		}
	}
	dp := float64(0)
	if basVal != 0 {
		dp = (curVal - basVal) / basVal
	}
	return &HoldOutResult{
		Dimension:       dimKey,
		ExcludedSegment: excludedSegment,
		ExcludingValue:  curVal,
		ExcludingBase:   basVal,
		DeviationPct:    dp,
		Reverted:        abs64(dp) < revertThreshold,
	}
}

// baselineDatesFor returns the same-weekday dates prior to end, one per prior
// week going back `weeks` occurrences, most recent first, formatted as
// "2006-01-02". Mirrors Detect's own same-weekday trailing-window baseline so
// Attribute isn't fooled by a single contaminated comparison day.
func baselineDatesFor(end time.Time, weeks int) []string {
	if weeks < 1 {
		weeks = 1
	}
	dates := make([]string, weeks)
	for w := 1; w <= weeks; w++ {
		dates[w-1] = end.AddDate(0, 0, -7*w).Format("2006-01-02")
	}
	return dates
}

// decomposeFactors runs the revenue identity decomposition and identifies the guilty factor.
func (e *Engine) decomposeFactors(ctx context.Context, currentDate string, baselineDates []string) (FactorDecomposition, string, error) {
	sql := query.BuildFactorDecompositionSQL(currentDate, baselineDates)
	rows, err := e.qe.Rows(ctx, "factor_decomp", sql)
	if err != nil {
		return FactorDecomposition{}, "", err
	}

	vals := map[string]map[string]float64{} // period → col → val
	for _, row := range rows {
		period, _ := row["period"].(string)
		vals[period] = map[string]float64{
			"requests":    toF(row["requests"]),
			"fill_rate":   toF(row["fill_rate"]),
			"render_rate": toF(row["render_rate"]),
			"ecpm":        toF(row["ecpm"]),
			"revenue":     toF(row["revenue"]),
		}
	}

	cur := vals["current"]
	bas := vals["baseline"]

	mkDelta := func(col string, guiltThreshold float64) FactorDelta {
		c, b := cur[col], bas[col]
		dp := float64(0)
		if b != 0 {
			dp = (c - b) / b
		}
		return FactorDelta{
			Current:  c,
			Baseline: b,
			DeltaPct: dp,
			IsGuilty: abs64(dp) > guiltThreshold,
		}
	}

	decomp := FactorDecomposition{
		Requests:   mkDelta("requests", 0.30),
		FillRate:   mkDelta("fill_rate", 0.20),
		RenderRate: mkDelta("render_rate", 0.20),
		ECPM:       mkDelta("ecpm", 0.20),
		Revenue:    mkDelta("revenue", 0.0),
	}

	// Identify guilty factor (largest mover above threshold)
	type candidate struct {
		name  string
		delta float64
	}
	var guilty []candidate
	var ruledOut []string
	for name, fd := range map[string]FactorDelta{
		"fill_rate":   decomp.FillRate,
		"render_rate": decomp.RenderRate,
		"ecpm":        decomp.ECPM,
		"requests":    decomp.Requests,
	} {
		if fd.IsGuilty {
			guilty = append(guilty, candidate{name, abs64(fd.DeltaPct)})
		} else {
			ruledOut = append(ruledOut, name)
		}
	}

	if len(guilty) == 0 {
		decomp.GuiltyFactor = "mixed"
		decomp.RuledOut = ruledOut
	} else {
		sort.Slice(guilty, func(i, j int) bool { return guilty[i].delta > guilty[j].delta })
		decomp.GuiltyFactor = guilty[0].name
		decomp.RuledOut = ruledOut
	}

	return decomp, sql, nil
}

// runContributions runs contribution analysis for all dimensions in parallel.
func (e *Engine) runContributions(
	ctx context.Context,
	metric, currentDate string,
	baselineDates []string,
	skip map[string]bool,
) (map[string][]SegmentFinding, []string, []string, error) {
	type dimResult struct {
		key      string
		findings []SegmentFinding
		sql      string
		err      error
	}

	sem := make(chan struct{}, e.cfg.ParallelWorkers)
	resultCh := make(chan dimResult, len(AllDimensions))
	var wg sync.WaitGroup

	for _, dim := range AllDimensions {
		if skip[dim.Key] {
			continue
		}
		wg.Add(1)
		dim := dim
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()

			sql := query.BuildContributionSQL(
				dim.DimCol, dim.FromClause,
				dim.FilledOnlyFilter, metric,
				currentDate, baselineDates,
			)
			rows, err := e.qe.Rows(ctx, "contribution_"+dim.Key, sql)
			if err != nil {
				resultCh <- dimResult{key: dim.Key, err: err, sql: sql}
				return
			}

			var findings []SegmentFinding
			for _, row := range rows {
				coldStart := toBool(row["cold_start"])
				cp := toF(row["contribution_pct"])
				// A cold-start segment (no history in one of the two periods) has
				// no valid contribution_pct — surface it regardless of the
				// threshold rather than let it be silently dropped.
				if !coldStart && abs64(cp) < e.cfg.ContributionThreshold {
					continue
				}
				findings = append(findings, SegmentFinding{
					Dimension:       dim.Key,
					Segment:         toString(row["seg"]),
					Metric:          metric,
					CurrentValue:    toF(row["current_value"]),
					BaselineValue:   toF(row["baseline_value"]),
					Delta:           toF(row["delta"]),
					ContributionPct: cp,
					ColdStart:       coldStart,
					QuerySQL:        sql,
				})
			}
			resultCh <- dimResult{key: dim.Key, findings: findings, sql: sql}
		}()
	}

	go func() {
		wg.Wait()
		close(resultCh)
	}()

	byDim := map[string][]SegmentFinding{}
	var allSQLs []string
	var ruledOut []string

	for r := range resultCh {
		allSQLs = append(allSQLs, r.sql)
		if r.err != nil {
			e.logger.Warn("contribution query failed",
				slog.String("dim", r.key),
				slog.Any("error", r.err),
			)
			ruledOut = append(ruledOut, r.key)
			continue
		}
		if len(r.findings) == 0 {
			ruledOut = append(ruledOut, r.key)
		} else {
			byDim[r.key] = r.findings
		}
	}

	return byDim, allSQLs, ruledOut, nil
}

// enrichWithZScores adds segment-level z-scores from a bottom-up scan to matching findings.
func enrichWithZScores(culprits []SegmentFinding, segRows []map[string]any, dimKey string) {
	zMap := map[string]float64{}
	for _, row := range segRows {
		seg := toString(row["seg"])
		zMap[seg] = toF(row["z_score"])
	}
	for i := range culprits {
		if culprits[i].Dimension == dimKey {
			culprits[i].ZScore = zMap[culprits[i].Segment]
		}
	}
}

func toF(v any) float64 {
	if v == nil {
		return 0
	}
	switch t := v.(type) {
	case float64:
		return t
	case float32:
		return float64(t)
	case int64:
		return float64(t)
	case uint64:
		return float64(t)
	case int32:
		return float64(t)
	case uint32:
		return float64(t)
	case uint8:
		return float64(t)
	case int:
		return float64(t)
	}
	return 0
}

func toBool(v any) bool {
	switch t := v.(type) {
	case bool:
		return t
	case uint8:
		return t != 0
	case int:
		return t != 0
	}
	return false
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprintf("%v", v)
}

func abs64(f float64) float64 {
	if f < 0 {
		return -f
	}
	return f
}
