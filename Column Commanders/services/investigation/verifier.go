package investigation

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
)

type dimensionSpec struct {
	expression string
}

var dimensions = map[string]dimensionSpec{
	"ad_format":      {expression: "e.ad_format"},
	"app":            {expression: "e.app_id"},
	"advertiser":     {expression: "e.advertiser_id"},
	"app_category":   {expression: "a.category"},
	"publisher_tier": {expression: "a.publisher_tier"},
	"adv_vertical":   {expression: "adv.vertical"},
	"campaign_type":  {expression: "adv.campaign_type"},
	"region":         {expression: "g.region"},
	"country":        {expression: "g.country"},
	"device_model":   {expression: "g.device_model"},
	"os_version":     {expression: "g.os_version"},
}

type Verifier struct {
	qe       *query.Executor
	registry *anomalydetector.MetricRegistry
	cfg      config.DetectionConfig
}

func NewVerifier(qe *query.Executor, registry *anomalydetector.MetricRegistry, cfg config.DetectionConfig) *Verifier {
	return &Verifier{qe: qe, registry: registry, cfg: cfg}
}

// Localize performs one deterministic, lossless dimension sweep before the
// LLM starts reasoning. Every segment is measured against prior same-period
// windows with metric-specific contribution math.
func (v *Verifier) Localize(ctx context.Context, subject Subject) ([]Evidence, error) {
	definition, ok := v.registry.Get(subject.Metric)
	if !ok {
		return nil, fmt.Errorf("unknown metric %q", subject.Metric)
	}
	dimensionNames := attributionDimensions(definition)
	limit := max(20, v.cfg.MaxCulpritSegments*4)
	sql, err := buildAttributionSQL(dimensionNames, definition, v.cfg.LookbackWeeks, false, limit)
	if err != nil {
		return nil, err
	}
	direction := int8(subject.Direction)
	if direction == 0 {
		direction = 1
	}
	rows, err := v.qe.Rows(ctx, "canonical_dimension_sweep", sql,
		"window_start", subject.Start.UTC().Format("2006-01-02 15:04:05.000"),
		"window_end", subject.End.UTC().Format("2006-01-02 15:04:05.000"),
		"direction", direction,
	)
	if err != nil {
		return nil, err
	}
	evidence := make([]Evidence, 0, len(rows))
	for _, row := range rows {
		evidence = append(evidence, v.evidenceFromRow(subject, definition, row, sql))
	}
	return evidence, nil
}

func (v *Verifier) Verify(ctx context.Context, subject Subject, dimension, segment string) (Evidence, error) {
	_, ok := dimensions[dimension]
	if !ok {
		return Evidence{}, fmt.Errorf("unsupported root-cause dimension %q", dimension)
	}
	if strings.TrimSpace(segment) == "" {
		return Evidence{}, fmt.Errorf("root-cause segment is empty")
	}
	definition, ok := v.registry.Get(subject.Metric)
	if !ok {
		return Evidence{}, fmt.Errorf("unknown metric %q", subject.Metric)
	}
	if !containsString(attributionDimensions(definition), dimension) {
		return Evidence{}, fmt.Errorf("dimension %q is not valid for metric %q because its coverage is structurally incomplete", dimension, subject.Metric)
	}
	sql, err := buildAttributionSQL([]string{dimension}, definition, v.cfg.LookbackWeeks, true, 1)
	if err != nil {
		return Evidence{}, err
	}
	row, err := v.qe.Row(ctx, "canonical_episode_verification", sql,
		"window_start", subject.Start.UTC().Format("2006-01-02 15:04:05.000"),
		"window_end", subject.End.UTC().Format("2006-01-02 15:04:05.000"),
		"segment", segment,
		"direction", int8(subject.Direction),
	)
	if err != nil {
		return Evidence{}, err
	}
	return v.evidenceFromRow(subject, definition, row, sql), nil
}

func (v *Verifier) evidenceFromRow(subject Subject, definition anomalydetector.MetricDefinition, row map[string]any, sql string) Evidence {
	dimension := fmt.Sprint(row["dimension"])
	segment := fmt.Sprint(row["segment"])
	current := floatValue(row["current_value"])
	baseline := floatValue(row["baseline_value"])
	deviation := floatValue(row["deviation_pct"])
	contribution := floatValue(row["contribution_pct"])
	metricImpact := floatValue(row["metric_impact"])
	segmentRevenueDelta := floatValue(row["segment_revenue_delta"])
	baselineN := uint16(floatValue(row["baseline_n"]))
	minimumSample := definition.MinimumDenominator
	if definition.Kind == anomalydetector.MetricAdditive {
		minimumSample = definition.MinimumRequests
	}
	directionMatches := subject.Direction == 0 || metricImpact*float64(subject.Direction) > 0
	verified := baselineN >= uint16(v.cfg.MinBaselineN) &&
		floatValue(row["current_sample"]) >= float64(minimumSample) &&
		math.Abs(deviation) >= definition.Threshold &&
		contribution >= v.cfg.ContributionThreshold &&
		directionMatches

	return Evidence{
		ID:        uuid.NewSHA1(uuid.NameSpaceOID, []byte(fmt.Sprintf("%s|%s|%s|%s|%s|%s", subject.EpisodeID, subject.Metric, dimension, segment, subject.Start.UTC().Format(time.RFC3339Nano), subject.End.UTC().Format(time.RFC3339Nano)))),
		EpisodeID: subject.EpisodeID, Metric: subject.Metric,
		Dimension: dimension, Segment: segment, WindowStart: subject.Start, WindowEnd: subject.End,
		CurrentValue: current, BaselineValue: baseline, DeviationPct: deviation,
		ContributionPct: contribution, RevenueImpact: segmentRevenueDelta,
		BaselineN: baselineN, Verified: verified, VerificationSQL: sql,
	}
}

func attributionDimensions(metric anomalydetector.MetricDefinition) []string {
	names := make([]string, 0, len(dimensions))
	for name := range dimensions {
		// Advertiser fields are absent on unfilled requests. They cannot safely
		// explain request-denominator metrics because missingness is an outcome,
		// not a causal segment.
		if (metric.Name == anomalydetector.MetricRequests || metric.Denominator == anomalydetector.ColumnRequests) &&
			(name == "advertiser" || name == "adv_vertical" || name == "campaign_type") {
			continue
		}
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func containsString(items []string, wanted string) bool {
	for _, item := range items {
		if item == wanted {
			return true
		}
	}
	return false
}

func buildAttributionSQL(dimensionNames []string, metric anomalydetector.MetricDefinition, lookbackWeeks int, filterSegment bool, limit int) (string, error) {
	if err := metric.Validate(); err != nil {
		return "", err
	}
	if lookbackWeeks < 1 {
		lookbackWeeks = 5
	}
	if len(dimensionNames) == 0 {
		return "", fmt.Errorf("at least one attribution dimension is required")
	}
	if limit < 1 || limit > 1000 {
		return "", fmt.Errorf("attribution limit must be between 1 and 1000")
	}

	tuples := make([]string, 0, len(dimensionNames))
	needApps, needAdvertisers, needGeo := false, false, false
	for _, name := range dimensionNames {
		spec, ok := dimensions[name]
		if !ok {
			return "", fmt.Errorf("unsupported attribution dimension %q", name)
		}
		tuples = append(tuples, fmt.Sprintf("tuple('%s', toString(%s))", name, spec.expression))
		needApps = needApps || strings.HasPrefix(spec.expression, "a.")
		needAdvertisers = needAdvertisers || strings.HasPrefix(spec.expression, "adv.")
		needGeo = needGeo || strings.HasPrefix(spec.expression, "g.")
	}
	dimensionTuples := strings.Join(tuples, ", ")
	joins := make([]string, 0, 3)
	if needApps {
		joins = append(joins, "ANY LEFT JOIN apps AS a ON e.app_id = a.app_id")
	}
	if needAdvertisers {
		joins = append(joins, "ANY LEFT JOIN advertisers AS adv ON e.advertiser_id = adv.advertiser_id")
	}
	if needGeo {
		joins = append(joins, "ANY LEFT JOIN geo_device AS g ON e.geo_device_id = g.geo_device_id")
	}
	joinSQL := strings.Join(joins, "\n\t")

	var segmentUnions, globalUnions []string
	for week := 0; week <= lookbackWeeks; week++ {
		shift := ""
		if week > 0 {
			shift = fmt.Sprintf(" - INTERVAL %d WEEK", week)
		}
		filteredFact := fmt.Sprintf(`(SELECT event_time, app_id, geo_device_id, advertiser_id, ad_format,
		is_filled, is_impression, is_click, revenue
	FROM ad_events
	WHERE event_time >= toDateTime64({window_start:String}, 3, 'UTC')%s
	  AND event_time < toDateTime64({window_end:String}, 3, 'UTC')%s) AS e`, shift, shift)
		segmentUnions = append(segmentUnions, fmt.Sprintf(`SELECT %d AS period,
		dimension_tuple.1 AS dimension, dimension_tuple.2 AS segment,
		count() AS requests, sum(e.is_filled) AS fills, sum(e.is_impression) AS impressions,
		sum(e.is_click) AS clicks, sum(e.revenue) AS revenue
	FROM %s
	%s
	ARRAY JOIN [%s] AS dimension_tuple
	WHERE dimension_tuple.2 != ''
	GROUP BY dimension, segment`, week, filteredFact, joinSQL, dimensionTuples))
		globalUnions = append(globalUnions, fmt.Sprintf(`SELECT %d AS period,
		count() AS requests, sum(is_filled) AS fills, sum(is_impression) AS impressions,
		sum(is_click) AS clicks, sum(revenue) AS revenue
	FROM ad_events
	WHERE event_time >= toDateTime64({window_start:String}, 3, 'UTC')%s
	  AND event_time < toDateTime64({window_end:String}, 3, 'UTC')%s`, week, shift, shift))
	}

	metricExpression := aggregateValueExpression(metric)
	sampleExpression := string(metric.Denominator)
	if metric.Kind == anomalydetector.MetricAdditive {
		sampleExpression = "requests"
	}
	segmentImpact := "current_value - baseline_value"
	globalImpact := "global_current_value - global_baseline_value"
	if metric.Kind != anomalydetector.MetricAdditive {
		scale := metric.Scale
		if scale == 0 {
			scale = 1
		}
		segmentImpact = fmt.Sprintf("(current_value - baseline_value) * current_sample / %.9g", scale)
		globalImpact = fmt.Sprintf("(global_current_value - global_baseline_value) * global_current_sample / %.9g", scale)
	}
	segmentPredicate := ""
	if filterSegment {
		segmentPredicate = "AND segment = {segment:String}"
	}

	return fmt.Sprintf(`WITH segment_aggregates AS
(
	%s
), segment_values AS
(
	SELECT period, dimension, segment, toFloat64(%s) AS metric_value,
		toFloat64(%s) AS sample_size, toFloat64(revenue) AS revenue_value
	FROM segment_aggregates
), segment_stats AS
(
	SELECT dimension, segment,
		anyIf(metric_value, period = 0) AS current_value,
		quantileExactIf(0.5)(metric_value, period > 0) AS baseline_value,
		anyIf(sample_size, period = 0) AS current_sample,
		anyIf(revenue_value, period = 0) AS current_revenue,
		quantileExactIf(0.5)(revenue_value, period > 0) AS baseline_revenue,
		countIf(period > 0) AS baseline_n
	FROM segment_values
	GROUP BY dimension, segment
), global_aggregates AS
(
	%s
), global_values AS
(
	SELECT period, toFloat64(%s) AS metric_value,
		toFloat64(%s) AS sample_size
	FROM global_aggregates
), global_stats AS
(
	SELECT anyIf(metric_value, period = 0) AS global_current_value,
		quantileExactIf(0.5)(metric_value, period > 0) AS global_baseline_value,
		anyIf(sample_size, period = 0) AS global_current_sample
	FROM global_values
), scored AS
(
	SELECT dimension, segment, current_value, baseline_value, current_sample, baseline_n,
		if(baseline_value = 0, 0, (current_value - baseline_value) / abs(baseline_value)) AS deviation_pct,
		%s AS metric_impact,
		%s AS global_metric_impact,
		current_revenue - baseline_revenue AS segment_revenue_delta
	FROM segment_stats
	CROSS JOIN global_stats
)
SELECT dimension, segment, current_value, baseline_value, current_sample, baseline_n,
	deviation_pct, metric_impact,
	metric_impact / nullIf(global_metric_impact, 0) AS contribution_pct,
	segment_revenue_delta
FROM scored
WHERE ({direction:Int8} = 0 OR metric_impact * {direction:Int8} > 0)
	%s
ORDER BY abs(contribution_pct) DESC, abs(metric_impact) DESC
LIMIT %d
SETTINGS max_execution_time = 10, max_rows_to_read = 10000000,
	max_bytes_to_read = 1000000000, max_result_rows = 1000,
	timeout_before_checking_execution_speed = 0, join_algorithm = 'auto'`,
		strings.Join(segmentUnions, "\n\tUNION ALL\n\t"), metricExpression, sampleExpression,
		strings.Join(globalUnions, "\n\tUNION ALL\n\t"), metricExpression, sampleExpression,
		segmentImpact, globalImpact, segmentPredicate, limit), nil
}

func aggregateValueExpression(metric anomalydetector.MetricDefinition) string {
	numerator := string(metric.Numerator)
	if metric.Kind == anomalydetector.MetricAdditive {
		return numerator
	}
	if metric.Kind == anomalydetector.MetricScaledRatio {
		numerator = fmt.Sprintf("%s * %.9g", numerator, metric.Scale)
	}
	return fmt.Sprintf("%s / nullIf(%s, 0)", numerator, metric.Denominator)
}

func floatValue(value any) float64 {
	var result float64
	_, _ = fmt.Sscan(fmt.Sprint(value), &result)
	return result
}
