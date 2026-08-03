package detectionv2

import (
	"context"
	"fmt"
	"math"
	"reflect"
	"sort"
	"strings"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
)

type Scanner struct {
	qe       *query.Executor
	registry *anomalydetector.MetricRegistry
	cfg      config.DetectionConfig
}

func NewScanner(qe *query.Executor, registry *anomalydetector.MetricRegistry, cfg config.DetectionConfig) *Scanner {
	return &Scanner{qe: qe, registry: registry, cfg: cfg}
}

func (s *Scanner) Scan(ctx context.Context, runID uuid.UUID, mode anomalydetector.DetectionMode, resolution anomalydetector.Resolution, start, end time.Time) ([]anomalydetector.Candidate, error) {
	sql, err := s.BuildSQL(mode, resolution)
	if err != nil {
		return nil, err
	}
	zThreshold := s.cfg.ZScoreThreshold
	ctrZThreshold := s.cfg.ZScoreCTRThreshold
	if ctrZThreshold <= 0 {
		ctrZThreshold = math.Max(8, zThreshold)
	}
	thresholdMultiplier := 1.0
	if mode == anomalydetector.ModeRealTime && resolution == anomalydetector.Resolution5m {
		zThreshold = math.Max(8, zThreshold*1.5)
		ctrZThreshold = math.Max(8, ctrZThreshold*1.5)
		thresholdMultiplier = 2
	}
	rows, err := s.qe.Rows(ctx, "detection_v2_"+string(mode)+"_"+string(resolution), sql,
		"scan_start", start.UTC().Format("2006-01-02 15:04:05.000"),
		"scan_end", end.UTC().Format("2006-01-02 15:04:05.000"),
		"min_n", int64(s.cfg.MinBaselineN),
		"z_threshold", zThreshold,
		"ctr_z_threshold", ctrZThreshold,
		"threshold_multiplier", thresholdMultiplier,
	)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	candidates := make([]anomalydetector.Candidate, 0, len(rows))
	for _, row := range rows {
		windowStart, ok := asTime(row["window_start"])
		if !ok {
			return nil, fmt.Errorf("scanner: invalid window_start %T", row["window_start"])
		}
		metric := fmt.Sprint(row["metric"])
		deviation := asFloat(row["deviation_pct"])
		direction := anomalydetector.DirectionDown
		if deviation > 0 {
			direction = anomalydetector.DirectionUp
		}
		severity := severityForScore(math.Abs(asFloat(row["z_score"])), math.Abs(deviation))
		candidate := anomalydetector.Candidate{
			ID:            anomalydetector.CandidateID(mode, resolution, metric, direction, windowStart),
			RunID:         runID,
			Mode:          mode,
			Resolution:    resolution,
			Metric:        metric,
			Direction:     direction,
			WindowStart:   windowStart,
			WindowEnd:     windowStart.Add(resolutionDuration(resolution)),
			CurrentValue:  asFloat(row["current_value"]),
			BaselineValue: asFloat(row["baseline_value"]),
			DeviationPct:  deviation,
			Score:         math.Abs(asFloat(row["z_score"])),
			RevenueImpact: fmt.Sprintf("%.9f", asFloat(row["revenue_impact"])),
			BaselineN:     uint16(asFloat(row["baseline_n"])),
			Severity:      severity,
			Status:        "candidate",
			DetectedAt:    now,
			Version:       uint64(now.UnixMilli()),
		}
		candidates = append(candidates, candidate)
	}
	return candidates, nil
}

func (s *Scanner) BuildSQL(mode anomalydetector.DetectionMode, resolution anomalydetector.Resolution) (string, error) {
	source, bucket, season, err := scanShape(resolution)
	if err != nil {
		return "", err
	}
	metricTuples, err := s.metricTuples()
	if err != nil {
		return "", err
	}
	lookback := s.cfg.LookbackWeeks
	if lookback <= 0 {
		lookback = 5
	}

	peerPredicate := fmt.Sprintf(`b.window_start != t.window_start
		AND b.window_start >= t.window_start - INTERVAL %d WEEK
		AND b.window_start <= t.window_start + INTERVAL %d WEEK`, lookback, lookback)
	baseEnd := fmt.Sprintf("target_end + INTERVAL %d WEEK", lookback)
	if mode == anomalydetector.ModeRealTime {
		peerPredicate = fmt.Sprintf(`b.window_start < t.window_start
			AND b.window_start >= t.window_start - INTERVAL %d WEEK`, lookback)
		baseEnd = "target_end"
	} else if mode != anomalydetector.ModeHistorical {
		return "", fmt.Errorf("unsupported detection mode %q", mode)
	}

	return fmt.Sprintf(`WITH
	toDateTime64({scan_start:String}, 3, 'UTC') AS target_start,
	toDateTime64({scan_end:String}, 3, 'UTC') AS target_end,
	rolled AS
	(
		SELECT
			%s AS window_start,
			sum(requests) AS requests,
			sum(fills) AS fills,
			sum(impressions) AS impressions,
			sum(clicks) AS clicks,
			sum(revenue) AS revenue
		FROM %s
		WHERE window_start >= target_start - INTERVAL %d WEEK
		  AND window_start < %s
		GROUP BY window_start
	),
	metric_rows AS
	(
		SELECT
			window_start,
			requests,
			toFloat64(revenue) AS revenue_value,
			metric_tuple.1 AS metric,
			metric_tuple.2 AS value,
			metric_tuple.3 AS sample_size,
			metric_tuple.4 AS minimum_sample,
			metric_tuple.5 AS commercial_threshold
		FROM rolled
		ARRAY JOIN [%s] AS metric_tuple
	),
	stats AS
	(
		SELECT
			t.window_start AS window_start,
			t.metric AS metric,
			any(t.value) AS current_value,
			quantileExact(0.5)(b.value) AS baseline_value,
			any(t.revenue_value) AS current_revenue,
			quantileExact(0.5)(b.revenue_value) AS baseline_revenue,
			(quantileExact(0.75)(b.value) - quantileExact(0.25)(b.value)) / 1.35 AS sigma,
			any(t.commercial_threshold) AS commercial_threshold,
			count() AS baseline_n
		FROM metric_rows AS t
		INNER JOIN metric_rows AS b ON b.metric = t.metric AND %s AND %s
		WHERE t.window_start >= target_start
		  AND t.window_start < target_end
		  AND t.sample_size >= t.minimum_sample
		GROUP BY t.window_start, t.metric
		HAVING baseline_n >= {min_n:Int64}
	),
	scored AS
	(
		SELECT
			window_start,
			metric,
			current_value,
			baseline_value,
			if(baseline_value = 0, 0, (current_value - baseline_value) / abs(baseline_value)) AS deviation_pct,
			if(sigma > 0, (current_value - baseline_value) / sigma,
				if(current_value = baseline_value, 0, if(current_value > baseline_value, 999, -999))) AS z_score,
			current_revenue - baseline_revenue AS revenue_impact,
			baseline_n,
			commercial_threshold
		FROM stats
	)
	SELECT window_start, metric, current_value, baseline_value, deviation_pct,
		z_score, revenue_impact, baseline_n
	FROM scored
	WHERE abs(z_score) >= if(metric = 'ctr', {ctr_z_threshold:Float64}, {z_threshold:Float64})
	  AND abs(deviation_pct) >= commercial_threshold * {threshold_multiplier:Float64}
	ORDER BY window_start, metric
	SETTINGS max_execution_time = 30, max_rows_to_read = 10000000,
		max_bytes_to_read = 1000000000, timeout_before_checking_execution_speed = 0`,
		bucket, source, lookback, baseEnd, metricTuples, season, peerPredicate), nil
}

func (s *Scanner) metricTuples() (string, error) {
	items := make([]string, 0, len(s.registry.Definitions()))
	for _, definition := range s.registry.Definitions() {
		expression, sample, err := rolledMetricExpression(definition)
		if err != nil {
			return "", err
		}
		minimumSample := definition.MinimumDenominator
		if definition.Kind == anomalydetector.MetricAdditive {
			minimumSample = definition.MinimumRequests
		}
		commercialThreshold := definition.Threshold
		switch {
		case definition.Kind == anomalydetector.MetricAdditive:
			commercialThreshold = math.Max(commercialThreshold, s.cfg.V2AdditiveMinDeviationPct)
		case definition.Name == anomalydetector.MetricCTR:
			commercialThreshold = math.Max(commercialThreshold, s.cfg.MinDeviationPctCTR)
		default:
			commercialThreshold = math.Max(commercialThreshold, s.cfg.MinDeviationPct)
		}
		items = append(items, fmt.Sprintf("tuple('%s', toFloat64(%s), toFloat64(%s), toFloat64(%d), toFloat64(%s))",
			definition.Name, expression, sample, minimumSample, formatFloat(commercialThreshold)))
	}
	return strings.Join(items, ",\n\t\t\t"), nil
}

func rolledMetricExpression(d anomalydetector.MetricDefinition) (string, string, error) {
	if err := d.Validate(); err != nil {
		return "", "", err
	}
	numerator := string(d.Numerator)
	if d.Kind == anomalydetector.MetricAdditive {
		return numerator, "requests", nil
	}
	if d.Kind == anomalydetector.MetricScaledRatio {
		numerator = fmt.Sprintf("%s * %s", numerator, formatFloat(d.Scale))
	}
	return fmt.Sprintf("%s / nullIf(%s, 0)", numerator, d.Denominator), string(d.Denominator), nil
}

func scanShape(resolution anomalydetector.Resolution) (source, bucket, season string, err error) {
	switch resolution {
	case anomalydetector.Resolution5m:
		return "metrics_global_1m", "toStartOfInterval(window_start, INTERVAL 5 MINUTE)",
			"toDayOfWeek(b.window_start) = toDayOfWeek(t.window_start) AND toHour(b.window_start) = toHour(t.window_start) AND intDiv(toMinute(b.window_start), 5) = intDiv(toMinute(t.window_start), 5)", nil
	case anomalydetector.Resolution10m:
		return "metrics_global_1m", "toStartOfInterval(window_start, INTERVAL 10 MINUTE)",
			"toDayOfWeek(b.window_start) = toDayOfWeek(t.window_start) AND toHour(b.window_start) = toHour(t.window_start) AND intDiv(toMinute(b.window_start), 10) = intDiv(toMinute(t.window_start), 10)", nil
	case anomalydetector.Resolution1h:
		return "metrics_global_1h", "toStartOfHour(window_start)",
			"toDayOfWeek(b.window_start) = toDayOfWeek(t.window_start) AND toHour(b.window_start) = toHour(t.window_start)", nil
	default:
		return "", "", "", fmt.Errorf("unsupported resolution %q", resolution)
	}
}

func resolutionDuration(resolution anomalydetector.Resolution) time.Duration {
	switch resolution {
	case anomalydetector.Resolution5m:
		return 5 * time.Minute
	case anomalydetector.Resolution10m:
		return 10 * time.Minute
	default:
		return time.Hour
	}
}

func severityForScore(score, deviation float64) anomalydetector.Severity {
	switch {
	case score >= 12 || deviation >= .30:
		return anomalydetector.SeverityCrit
	case score >= 8 || deviation >= .20:
		return anomalydetector.SeverityHigh
	case score >= 5 || deviation >= .10:
		return anomalydetector.SeverityMedium
	default:
		return anomalydetector.SeverityLow
	}
}

func asFloat(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case float32:
		return float64(n)
	case int:
		return float64(n)
	case int8:
		return float64(n)
	case int16:
		return float64(n)
	case int32:
		return float64(n)
	case int64:
		return float64(n)
	case uint:
		return float64(n)
	case uint8:
		return float64(n)
	case uint16:
		return float64(n)
	case uint32:
		return float64(n)
	case uint64:
		return float64(n)
	}
	value := reflect.ValueOf(v)
	if value.IsValid() && value.Kind() == reflect.String {
		var f float64
		_, _ = fmt.Sscan(value.String(), &f)
		return f
	}
	var f float64
	_, _ = fmt.Sscan(fmt.Sprint(v), &f)
	return f
}

func asTime(v any) (time.Time, bool) {
	switch value := v.(type) {
	case time.Time:
		return value.UTC(), true
	case string:
		for _, layout := range []string{"2006-01-02 15:04:05.999999999", "2006-01-02 15:04:05", time.RFC3339Nano} {
			if parsed, err := time.ParseInLocation(layout, value, time.UTC); err == nil {
				return parsed.UTC(), true
			}
		}
	}
	return time.Time{}, false
}

func formatFloat(value float64) string {
	return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.9f", value), "0"), ".")
}

func sortCandidates(candidates []anomalydetector.Candidate) {
	sort.Slice(candidates, func(i, j int) bool {
		if !candidates[i].WindowStart.Equal(candidates[j].WindowStart) {
			return candidates[i].WindowStart.Before(candidates[j].WindowStart)
		}
		return candidates[i].Metric < candidates[j].Metric
	})
}
