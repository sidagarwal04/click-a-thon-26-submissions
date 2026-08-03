package agent

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/domain"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

type bundleQuery struct {
	ID  string
	SQL string
}

type featureDashboardPlan struct {
	Playbook string
	Grain    string
	Stages   []string
}

func (a AnalyticsAgent) BuildFeatureBundle(ctx context.Context, role string, input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, graph domain.ContextVersion, answers []domain.QuestionResponse, traceID string) domain.FeatureAnalyticsBundle {
	if strings.TrimSpace(role) == "" {
		role = "product_manager"
	}
	plan := dashboardPlanFor(input, profile)
	bundle := domain.FeatureAnalyticsBundle{
		Feature: input.Name, Role: role, Status: "simulation",
		ContextVersion: graph.Version,
		SchemaVersion:  fmt.Sprintf("%s:v%d", Slug(input.Name), schema.Version),
		GeneratedAt:    time.Now().UTC(),
		Playbooks:      bundlePlaybooks(answers, plan.Playbook),
		Insights:       rankBundleInsights(role, answers),
	}
	if a.Reader == nil || !a.Reader.Enabled() {
		bundle.Charts = simulationFunnel(profile, plan, traceID)
		bundle.KPIs = []domain.AnalyticsKPI{{
			Key: "observed_events", Label: "Observed events", Value: float64(profile.Rows), FormattedValue: formatCount(float64(profile.Rows)),
			Unit: "events", Confidence: .7, SampleSize: float64(profile.Rows), TraceID: traceID,
		}}
		bundle.Limitations = []string{"ClickHouse is disabled, so the dashboard shows profiled event volume rather than unique-entity business metrics."}
		return bundle
	}

	queries := []bundleQuery{
		{ID: "funnel", SQL: featureFunnelSQL(plan, schema)},
		{ID: "trend", SQL: featureTrendSQL(plan, schema)},
	}
	if sql := featureSegmentsSQL(profile, plan, schema); sql != "" {
		queries = append(queries, bundleQuery{ID: "segments", SQL: sql})
	}

	results := map[string][]map[string]any{}
	failed := 0
	for _, query := range queries {
		rows, evidence := a.runBundleQuery(ctx, graph.Version, traceID, query)
		bundle.Evidence = append(bundle.Evidence, evidence)
		if evidence.Status != "completed" {
			failed++
			bundle.Limitations = append(bundle.Limitations, fmt.Sprintf("The %s dashboard query was unavailable: %s", query.ID, evidence.Error))
			continue
		}
		results[query.ID] = rows
	}

	bundle.Charts = buildBundleCharts(results, queries, traceID)
	bundle.KPIs = buildBundleKPIs(results, answers, plan.Playbook, traceID)
	bundle.Status = "ready"
	if failed > 0 {
		bundle.Status = "partial"
	}
	if len(bundle.KPIs) == 0 && len(bundle.Charts) == 0 {
		bundle.Status = "unavailable"
	}
	return bundle
}

func (a AnalyticsAgent) runBundleQuery(ctx context.Context, contextVersion int, traceID string, query bundleQuery) ([]map[string]any, domain.AnalyticsEvidence) {
	started := time.Now()
	tracer := a.Tracer
	if tracer == nil {
		tracer = otel.Tracer("featurelens/analytics")
	}
	queryCtx, span := tracer.Start(ctx, "analytics.bundle."+query.ID, trace.WithAttributes(
		attribute.String("langfuse.observation.type", "tool"),
		attribute.String("tool.name", "clickhouse.analytics_bundle."+query.ID),
		attribute.String("db.system", "clickhouse"),
		attribute.String("db.statement", query.SQL),
		attribute.String("analytics.trace_id", traceID),
		attribute.Int("analytics.context_version", contextVersion),
	))
	rows, err := a.Reader.QueryJSON(queryCtx, query.SQL)
	evidence := domain.AnalyticsEvidence{ID: query.ID, Status: "completed", SQL: query.SQL, Rows: rows, DurationMS: time.Since(started).Milliseconds()}
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "ClickHouse dashboard query failed")
		evidence.Status = "failed"
		evidence.Error = err.Error()
		evidence.Rows = nil
	} else {
		span.SetAttributes(attribute.Int("analytics.aggregate_rows", len(rows)))
	}
	span.End()
	return rows, evidence
}

func featureFunnelSQL(plan featureDashboardPlan, schema domain.SchemaProposal) string {
	parts := make([]string, 0, len(plan.Stages))
	for index, event := range plan.Stages {
		parts = append(parts, fmt.Sprintf("SELECT %d AS step, '%s' AS stage, uniqExactIf(%s, event_name = '%s') AS entities FROM %s", index+1, escapeSQL(event), identifier(plan.Grain), escapeSQL(event), qualified(schema.Database, schema.Table)))
	}
	return "SELECT * FROM (\n" + strings.Join(parts, "\nUNION ALL\n") + "\n) ORDER BY step\nFORMAT JSONEachRow"
}

func featureTrendSQL(plan featureDashboardPlan, schema domain.SchemaProposal) string {
	first, last := plan.Stages[0], plan.Stages[len(plan.Stages)-1]
	return fmt.Sprintf(`SELECT
    if(observed_days >= 120, 'month', 'week') AS granularity,
    toString(if(granularity = 'month', toStartOfMonth(toDate(timestamp)), toStartOfWeek(toDate(timestamp), 1))) AS date,
    uniqExactIf(%s, event_name = '%s') AS entrants,
    uniqExactIf(%s, event_name = '%s') AS completions,
    round(completions / nullIf(entrants, 0), 4) AS completion_rate
FROM %s
CROSS JOIN
(
    SELECT dateDiff('day', min(toDate(timestamp)), max(toDate(timestamp))) + 1 AS observed_days
    FROM %s
) AS bounds
GROUP BY granularity, date
HAVING entrants > 0
ORDER BY date
FORMAT JSONEachRow`, identifier(plan.Grain), escapeSQL(first), identifier(plan.Grain), escapeSQL(last), qualified(schema.Database, schema.Table), qualified(schema.Database, schema.Table))
}

func featureSegmentsSQL(profile domain.EventProfile, plan featureDashboardPlan, schema domain.SchemaProposal) string {
	dimensions := governedDimensionNames(profile)
	if len(dimensions) > 5 {
		dimensions = dimensions[:5]
	}
	return featureSegmentsSQLForDimensions(profile, plan, schema, dimensions)
}

func featureSegmentsSQLForDimensions(profile domain.EventProfile, plan featureDashboardPlan, schema domain.SchemaProposal, requested []string) string {
	first, last := plan.Stages[0], plan.Stages[len(plan.Stages)-1]
	dimensions := make([]string, 0, len(requested))
	seen := map[string]bool{}
	for _, dimension := range requested {
		if _, governed := dimensionDefinitionFor(dimension); governed && hasField(profile, dimension) && !seen[dimension] {
			dimensions = append(dimensions, dimension)
			seen[dimension] = true
		}
	}
	if len(dimensions) == 0 {
		return ""
	}
	parts := make([]string, 0, len(dimensions))
	for _, dimension := range dimensions {
		parts = append(parts, fmt.Sprintf(`SELECT
    '%s' AS dimension,
    if(segment_value = '', 'unknown', segment_value) AS segment,
    count() AS entrants,
    sum(completed) AS completions,
    round(completions / nullIf(entrants, 0), 4) AS completion_rate
FROM
(
    SELECT
        %s AS entity_id,
        anyIf(ifNull(toString(%s), 'unknown'), event_name = '%s') AS segment_value,
        max(event_name = '%s') AS entered,
        max(event_name = '%s') AS completed
    FROM %s
    WHERE %s IS NOT NULL
    GROUP BY entity_id
)
WHERE entered = 1
GROUP BY segment
HAVING entrants >= 20`, escapeSQL(dimension), identifier(plan.Grain), identifier(dimension), escapeSQL(first), escapeSQL(first), escapeSQL(last), qualified(schema.Database, schema.Table), identifier(plan.Grain)))
	}
	return "SELECT * FROM (\n" + strings.Join(parts, "\nUNION ALL\n") + "\n) ORDER BY dimension, completion_rate DESC, entrants DESC\nFORMAT JSONEachRow"
}

func buildBundleCharts(results map[string][]map[string]any, queries []bundleQuery, traceID string) []domain.AnalyticsChart {
	querySQL := map[string]string{}
	for _, query := range queries {
		querySQL[query.ID] = query.SQL
	}
	charts := make([]domain.AnalyticsChart, 0, 3)
	if rows := results["funnel"]; len(rows) > 0 {
		points := make([]domain.AnalyticsPoint, 0, len(rows))
		for _, row := range rows {
			value := finiteNumber(row["entities"])
			points = append(points, domain.AnalyticsPoint{Label: textValue(row["stage"]), Value: value, SampleSize: value})
		}
		charts = append(charts, domain.AnalyticsChart{Key: "feature_funnel", Type: "funnel", Title: "Feature funnel", Subtitle: "Unique entities reaching each observed event", Unit: "entities", Series: []domain.AnalyticsSeries{{Key: "entities", Label: "Unique entities", Points: points}}, SQL: querySQL["funnel"], TraceID: traceID})
	}
	if rows := results["trend"]; len(rows) > 0 {
		points := make([]domain.AnalyticsPoint, 0, len(rows))
		for _, row := range rows {
			points = append(points, domain.AnalyticsPoint{Label: textValue(row["date"]), Value: finiteNumber(row["completion_rate"]) * 100, SampleSize: finiteNumber(row["entrants"])})
		}
		granularity := textValue(rows[0]["granularity"])
		if granularity == "" {
			granularity = "week"
		}
		charts = append(charts, domain.AnalyticsChart{Key: "completion_trend", Type: "trend", Title: "Completion trend", Subtitle: strings.ToUpper(granularity[:1]) + granularity[1:] + "ly completion rate for the selected feature", Unit: "%", Series: []domain.AnalyticsSeries{{Key: "completion_rate", Label: "Completion rate", Points: points}}, SQL: querySQL["trend"], TraceID: traceID})
	}
	if rows := results["segments"]; len(rows) > 0 {
		seriesByDimension := map[string][]domain.AnalyticsPoint{}
		order := []string{}
		for _, row := range rows {
			dimension := textValue(row["dimension"])
			if _, exists := seriesByDimension[dimension]; !exists {
				order = append(order, dimension)
			}
			seriesByDimension[dimension] = append(seriesByDimension[dimension], domain.AnalyticsPoint{Label: textValue(row["segment"]), Value: finiteNumber(row["completion_rate"]) * 100, SampleSize: finiteNumber(row["entrants"])})
		}
		series := make([]domain.AnalyticsSeries, 0, len(order))
		for _, dimension := range order {
			series = append(series, domain.AnalyticsSeries{Key: dimension, Label: strings.ReplaceAll(dimension, "_", " "), Points: seriesByDimension[dimension]})
		}
		charts = append(charts, domain.AnalyticsChart{Key: "segment_completion", Type: "segments", Title: "Segment performance", Subtitle: "Best and weakest completion cohorts across verified dimensions", Unit: "%", Series: series, SQL: querySQL["segments"], TraceID: traceID})
	}
	return charts
}

func buildBundleKPIs(results map[string][]map[string]any, answers []domain.QuestionResponse, dashboardPlaybook, traceID string) []domain.AnalyticsKPI {
	kpis := make([]domain.AnalyticsKPI, 0, 6)
	seen := map[string]bool{}
	add := func(kpi domain.AnalyticsKPI) {
		if len(kpis) >= 6 || seen[kpi.Key] || math.IsNaN(kpi.Value) || math.IsInf(kpi.Value, 0) {
			return
		}
		seen[kpi.Key] = true
		kpis = append(kpis, kpi)
	}
	for _, answer := range answers {
		if answer.Contract.Answerability == "not_answerable" {
			continue
		}
		evidence := answer.Insight.Evidence
		confidence := answer.Insight.Confidence
		playbook := answer.Contract.Playbook
		answerTraceID := answer.Insight.TraceID
		switch answer.Contract.Intent {
		case "conversion_comparison":
			lift := finiteNumber(evidence["percentage_point_lift"])
			add(domain.AnalyticsKPI{Key: "lift_vs_standard", Label: "Lift vs standard", Value: lift, FormattedValue: formatPercentagePoints(lift), Unit: "pp", Direction: signedDirection(lift), Confidence: confidence, SampleSize: finiteNumber(evidence["feature_entrants"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "latency_performance":
			latency := finiteNumber(evidence["p95_latency_ms"])
			if latency > 0 {
				add(domain.AnalyticsKPI{Key: "p95_latency", Label: "Slowest 5% time to pay", Value: latency, FormattedValue: fmt.Sprintf("%.2fs", latency/1000), Unit: "seconds", Direction: "lower_is_better", Confidence: confidence, SampleSize: finiteNumber(evidence["payments"]), SourcePlaybook: playbook, TraceID: answerTraceID})
			}
		case "platform_failure":
			row := evidenceMap(evidence["worst_segment"])
			rate := finiteNumber(row["otp_success_rate"])
			segment := uniqueSegmentLabel(textValue(row["device_type"]), textValue(row["os"]))
			add(domain.AnalyticsKPI{Key: "weakest_otp_segment", Label: "Weakest OTP cohort · " + segment, Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["otp_entries"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "feature_adoption":
			row := evidenceMap(evidence["top_adoption_segment"])
			rate := finiteNumber(row["rate"])
			add(domain.AnalyticsKPI{Key: "top_adoption_segment", Label: "Top adoption · " + textValue(row["segment"]), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["denominator"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "group_size_completion":
			row := evidenceMap(evidence["lowest_completion_segment"])
			rate := finiteNumber(row["completion_rate"])
			add(domain.AnalyticsKPI{Key: "weakest_group_size", Label: "At-risk group size · " + textValue(row["group_size"]), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["groups_started"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "group_traveller_churn":
			value := finiteNumber(evidence["removals_per_group"])
			add(domain.AnalyticsKPI{Key: "removals_per_group", Label: "Traveller removals per group", Value: value, FormattedValue: fmt.Sprintf("%.2f", value), Unit: "travellers/group", Direction: "lower_is_better", Confidence: confidence, SampleSize: finiteNumber(evidence["groups_started"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "group_document_bottleneck":
			row := evidenceMap(evidence["lowest_submission_segment"])
			rate := finiteNumber(row["submission_rate"])
			add(domain.AnalyticsKPI{Key: "document_bottleneck", Label: "Document completion · group size " + textValue(row["group_size"]), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["groups"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "group_segments":
			row := evidenceMap(evidence["largest_segment"])
			starts := finiteNumber(row["groups_started"])
			add(domain.AnalyticsKPI{Key: "largest_group_segment", Label: "Largest segment · " + textValue(row["segment"]), Value: starts, FormattedValue: formatCount(starts), Unit: "groups", Confidence: confidence, SampleSize: starts, SourcePlaybook: playbook, TraceID: answerTraceID})
		case "recovery_drop_step":
			row := evidenceMap(evidence["most_recoverable_step"])
			rate := finiteNumber(row["recovery_rate"])
			add(domain.AnalyticsKPI{Key: "recoverable_drop_step", Label: "Best recoverable step · " + strings.ReplaceAll(textValue(row["drop_step"]), "_", " "), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["abandonments"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "recovery_channel":
			row := evidenceMap(evidence["best_channel"])
			rate := finiteNumber(row["recovery_rate"])
			add(domain.AnalyticsKPI{Key: "best_recovery_channel", Label: "Best recovery channel · " + textValue(row["channel"]), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["reminders"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "recovery_timing":
			row := evidenceMap(evidence["best_timing"])
			rate := finiteNumber(row["recovery_rate"])
			add(domain.AnalyticsKPI{Key: "best_recovery_timing", Label: fmt.Sprintf("Best recovery timing · %.0fh", finiteNumber(row["hours_since_drop"])), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["reminders"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		case "recovery_segments":
			row := evidenceMap(evidence["largest_recovery_segment"])
			rate := finiteNumber(row["recovery_rate"])
			add(domain.AnalyticsKPI{Key: "largest_recovery_segment", Label: "Recovery opportunity · " + textValue(row["segment"]), Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: confidence, SampleSize: finiteNumber(row["abandonments"]), SourcePlaybook: playbook, TraceID: answerTraceID})
		}
		if len(kpis) >= 3 {
			break
		}
	}
	if rows := results["funnel"]; len(rows) > 0 {
		entrants := finiteNumber(rows[0]["entities"])
		completions := finiteNumber(rows[len(rows)-1]["entities"])
		rate := 0.0
		if entrants > 0 {
			rate = completions / entrants
		}
		add(domain.AnalyticsKPI{Key: "completion_rate", Label: "End-to-end completion", Value: rate, FormattedValue: formatPercent(rate), Unit: "%", Direction: "higher_is_better", Confidence: .95, SampleSize: entrants, SourcePlaybook: dashboardPlaybook, TraceID: traceID})
		largestLoss := 0.0
		largestFromStage := ""
		largestToStage := ""
		largestSample := 0.0
		for index := 1; index < len(rows); index++ {
			previous := finiteNumber(rows[index-1]["entities"])
			current := finiteNumber(rows[index]["entities"])
			if previous <= 0 {
				continue
			}
			loss := math.Max(0, (previous-current)/previous)
			if loss > largestLoss {
				largestLoss, largestFromStage, largestToStage, largestSample = loss, textValue(rows[index-1]["stage"]), textValue(rows[index]["stage"]), previous
			}
		}
		if largestToStage != "" {
			transition := strings.ReplaceAll(largestFromStage, "_", " ") + " → " + strings.ReplaceAll(largestToStage, "_", " ")
			add(domain.AnalyticsKPI{Key: "largest_funnel_loss", Label: "Largest drop-off · " + transition, Value: largestLoss, FormattedValue: fmt.Sprintf("%.1f%%", largestLoss*100), Unit: "%", Direction: "lower_is_better", Confidence: .95, SampleSize: largestSample, SourcePlaybook: dashboardPlaybook, TraceID: traceID})
		}
	}
	if rows := results["segments"]; len(rows) > 0 {
		weakest := lowestMetricRow(rows, "completion_rate")
		weakestRate := finiteNumber(weakest["completion_rate"])
		add(domain.AnalyticsKPI{Key: "weakest_segment", Label: "Opportunity · " + textValue(weakest["segment"]), Value: weakestRate, FormattedValue: formatPercent(weakestRate), Unit: "%", Direction: "higher_is_better", Confidence: .9, SampleSize: finiteNumber(weakest["entrants"]), SourcePlaybook: "dashboard:feature-segments:v1", TraceID: traceID})
		best := highestMetricRow(rows, "completion_rate")
		gap := finiteNumber(best["completion_rate"]) - weakestRate
		add(domain.AnalyticsKPI{Key: "segment_opportunity_gap", Label: "Segment opportunity gap", Value: gap, FormattedValue: formatPercentagePoints(gap), Unit: "pp", Direction: "lower_is_better", Confidence: .88, SampleSize: finiteNumber(weakest["entrants"]), SourcePlaybook: "dashboard:feature-segments:v1", TraceID: traceID})
	}
	return kpis
}

func evidenceMap(value any) map[string]any {
	row, _ := value.(map[string]any)
	return row
}

func uniqueSegmentLabel(values ...string) string {
	unique := []string{}
	seen := map[string]bool{}
	for _, value := range values {
		value = strings.TrimSpace(value)
		key := strings.ToLower(value)
		if value == "" || seen[key] {
			continue
		}
		seen[key] = true
		unique = append(unique, value)
	}
	if len(unique) == 0 {
		return "unknown"
	}
	return strings.Join(unique, " / ")
}

func rankBundleInsights(role string, answers []domain.QuestionResponse) []domain.RankedInsight {
	type candidate struct {
		response domain.QuestionResponse
		score    float64
	}
	candidates := make([]candidate, 0, len(answers))
	for _, answer := range answers {
		if answer.Contract.Answerability == "not_answerable" {
			continue
		}
		candidates = append(candidates, candidate{response: answer, score: answer.Insight.Confidence + roleIntentWeight(role, answer.Contract.Intent)})
	}
	sort.SliceStable(candidates, func(i, j int) bool { return candidates[i].score > candidates[j].score })
	if len(candidates) > 3 {
		candidates = candidates[:3]
	}
	insights := make([]domain.RankedInsight, 0, len(candidates))
	for index, candidate := range candidates {
		answer := candidate.response
		insights = append(insights, domain.RankedInsight{
			Rank: index + 1, Intent: answer.Contract.Intent, Headline: answer.Insight.Headline, Summary: answer.Insight.Summary,
			Why: answer.Insight.Why, RecommendedAction: answer.Insight.RecommendedAction, Confidence: answer.Insight.Confidence,
			Playbook: answer.Contract.Playbook, TraceID: answer.Insight.TraceID,
		})
	}
	return insights
}

func roleIntentWeight(role, intent string) float64 {
	role = strings.ToLower(role)
	switch role {
	case "growth":
		if intent == "conversion_comparison" || intent == "feature_adoption" || intent == "recovery_channel" || intent == "recovery_segments" {
			return .08
		}
	case "instrumentation":
		if intent == "platform_failure" || intent == "latency_performance" || intent == "feature_completion" {
			return .08
		}
	default:
		if intent == "conversion_comparison" || intent == "funnel_diagnosis" || intent == "group_size_completion" || intent == "recovery_drop_step" {
			return .08
		}
	}
	return 0
}

func bundlePlaybooks(answers []domain.QuestionResponse, dashboardPlaybook string) []string {
	seen := map[string]bool{}
	playbooks := []string{dashboardPlaybook, "dashboard:completion-trend:v1", "dashboard:feature-segments:v1"}
	for _, playbook := range playbooks {
		seen[playbook] = true
	}
	for _, answer := range answers {
		if answer.Contract.Playbook != "" && !seen[answer.Contract.Playbook] {
			seen[answer.Contract.Playbook] = true
			playbooks = append(playbooks, answer.Contract.Playbook)
		}
	}
	return playbooks
}

func simulationFunnel(profile domain.EventProfile, plan featureDashboardPlan, traceID string) []domain.AnalyticsChart {
	points := make([]domain.AnalyticsPoint, 0, len(plan.Stages))
	for _, event := range plan.Stages {
		value := float64(profile.EventCounts[event])
		points = append(points, domain.AnalyticsPoint{Label: event, Value: value, SampleSize: value})
	}
	if len(points) == 0 {
		return nil
	}
	return []domain.AnalyticsChart{{Key: "observed_event_volume", Type: "funnel", Title: "Observed event volume", Subtitle: "Profiled events in simulation mode", Unit: "events", Series: []domain.AnalyticsSeries{{Key: "events", Label: "Events", Points: points}}, TraceID: traceID}}
}

func dashboardPlanFor(input domain.FeatureInput, profile domain.EventProfile) featureDashboardPlan {
	plan := featureDashboardPlan{Playbook: "dashboard:feature-funnel:v1", Grain: analysisGrain(profile), Stages: inferredGenericFunnelStages(profile)}
	slug := Slug(input.Slug)
	if slug == "" {
		slug = Slug(input.Name)
	}
	switch {
	case strings.Contains(slug, "express_checkout"):
		plan.Playbook = "dashboard:express-checkout:v1"
		plan.Stages = presentEvents(profile, "express_checkout_shown", "express_checkout_selected", "otp_entered", "express_payment_confirmed")
	case strings.Contains(slug, "group") || strings.Contains(slug, "family"):
		plan.Playbook = "dashboard:group-family:v1"
		plan.Grain = preferredDashboardGrain(profile, "group_id")
		plan.Stages = presentEvents(profile, "group_started", "traveller_added", "group_submitted")
	case strings.Contains(slug, "status_sharing"):
		plan.Playbook = "dashboard:status-sharing-engagement:v1"
		plan.Grain = preferredDashboardGrain(profile, "share_id")
		plan.Stages = presentEvents(profile, "link_generated", "link_opened", "recipient_cta_clicked")
	case strings.Contains(slug, "abandoned_checkout_recovery"):
		plan.Playbook = "dashboard:checkout-recovery:v1"
		plan.Stages = presentEvents(profile, "abandonment_detected", "reminder_sent", "reminder_opened", "reminder_cta_clicked", "reconverted")
	case strings.Contains(slug, "forex"):
		plan.Playbook = "dashboard:instant-forex:v1"
		plan.Stages = presentEvents(profile, "forex_offer_shown", "currency_selected", "forex_added_to_cart", "forex_purchased")
	}
	if len(plan.Stages) < 2 {
		plan.Stages = inferredGenericFunnelStages(profile)
	}
	if len(plan.Stages) < 2 {
		first, last := funnelBounds(profile)
		plan.Stages = []string{first, last}
	}
	return plan
}

// inferredGenericFunnelStages keeps an unseen feature's main success path from
// treating failure branches such as rejected/cancelled events as completion.
// Known feature plans still override this inference with their explicit
// semantic funnels.
func inferredGenericFunnelStages(profile domain.EventProfile) []string {
	stages := make([]string, 0, len(profile.EventOrder))
	for _, event := range profile.EventOrder {
		lower := strings.ToLower(event)
		branch := false
		for _, token := range []string{"reject", "failed", "failure", "error", "cancel", "declined", "removed"} {
			if strings.Contains(lower, token) {
				branch = true
				break
			}
		}
		if !branch {
			stages = append(stages, event)
		}
	}
	if len(stages) >= 2 {
		return stages
	}
	return append([]string{}, profile.EventOrder...)
}

func presentEvents(profile domain.EventProfile, candidates ...string) []string {
	present := map[string]bool{}
	for _, event := range profile.EventOrder {
		present[event] = true
	}
	selected := make([]string, 0, len(candidates))
	for _, candidate := range candidates {
		if present[candidate] {
			selected = append(selected, candidate)
		}
	}
	return selected
}

func preferredDashboardGrain(profile domain.EventProfile, preferred string) string {
	if hasField(profile, preferred) {
		return preferred
	}
	return analysisGrain(profile)
}

func finiteNumber(value any) float64 {
	parsed := number(value)
	if math.IsNaN(parsed) || math.IsInf(parsed, 0) {
		return 0
	}
	return parsed
}

func formatCount(value float64) string {
	if value >= 1_000_000 {
		return fmt.Sprintf("%.1fM", value/1_000_000)
	}
	if value >= 1_000 {
		return fmt.Sprintf("%.1fK", value/1_000)
	}
	return fmt.Sprintf("%.0f", value)
}

func formatPercent(value float64) string { return fmt.Sprintf("%.1f%%", value*100) }

func formatPercentagePoints(value float64) string {
	points := value * 100
	if points > 0 {
		return fmt.Sprintf("↑ %.1f points", points)
	}
	if points < 0 {
		return fmt.Sprintf("↓ %.1f points", math.Abs(points))
	}
	return "0.0 points"
}

func signedDirection(value float64) string {
	if value > 0 {
		return "positive"
	}
	if value < 0 {
		return "negative"
	}
	return "neutral"
}
