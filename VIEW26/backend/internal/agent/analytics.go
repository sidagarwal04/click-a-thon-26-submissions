package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/domain"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

type AggregateReader interface {
	QueryJSON(context.Context, string) ([]map[string]any, error)
	SourceDatabase() string
	Enabled() bool
}

type AnalyticsAgent struct {
	Reader      AggregateReader
	Synthesizer InsightSynthesizer
	Tracer      trace.Tracer
}

func (a AnalyticsAgent) Analyze(ctx context.Context, role, question string, input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, graph domain.ContextVersion, traceID string) (domain.AnalysisContract, domain.Insight) {
	started := time.Now().UTC()
	if strings.TrimSpace(role) == "" {
		role = "product_manager"
	}
	if strings.TrimSpace(question) == "" {
		question = defaultQuestion(input, profile)
	}
	schemaVersion := fmt.Sprintf("%s:v%d", Slug(input.Name), schema.Version)
	analysisTrace := &domain.AnalysisTrace{
		TraceID: traceID, Role: role, Feature: input.Name, Question: question,
		ContextVersion: graph.Version, SchemaVersion: schemaVersion, DatasetRows: profile.Rows,
		StartedAt: started,
		Steps: []domain.AnalysisTraceStep{{
			ID: "user.input", Kind: "input", Status: "completed",
			Input:  map[string]any{"role": role, "feature": input.Name, "question": question},
			Output: map[string]any{"selected_dataset_rows": profile.Rows, "selected_schema": schema.Database + "." + schema.Table},
		}},
	}
	sourceDatabase := "atlys"
	if a.Reader != nil {
		sourceDatabase = a.Reader.SourceDatabase()
	}
	intentSource := "keyword_classifier"
	var plan analysisPlan
	classifiedIntent := classifyFeatureIntent(input, question)
	if graphIntent, ok := resolveIntentFromGraph(graph, Slug(input.Name), question); ok {
		// Older published contexts can contain a generic feature_completion
		// binding for a question whose wording now resolves to a more specific
		// governed intent. Prefer the specific classifier in that one direction;
		// explicit non-generic graph bindings remain authoritative.
		if graphIntent == "feature_completion" && classifiedIntent != "feature_completion" {
			intentSource = "semantic_classifier_override"
			plan = buildAnalysisPlanForIntent(classifiedIntent, question, input, profile, schema, sourceDatabase)
		} else {
			intentSource = "context_graph"
			plan = buildAnalysisPlanForIntent(graphIntent, question, input, profile, schema, sourceDatabase)
		}
	} else {
		plan = buildAnalysisPlanForIntent(classifiedIntent, question, input, profile, schema, sourceDatabase)
	}
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{Role: role, Question: question, Feature: input.Name, Playbook: plan.ID, Intent: plan.Intent, AllowedTables: plan.AllowedTables})
	quarantinedCount := 0
	if quarantined, ok := contextSlice["quarantined_definitions"].([]map[string]any); ok {
		quarantinedCount = len(quarantined)
	}
	analysisTrace.Steps = append(analysisTrace.Steps,
		domain.AnalysisTraceStep{
			ID: "context.resolve", Kind: "context", Status: "completed",
			Input:  map[string]any{"requested_context_version": graph.Version, "role": role, "feature": input.Name, "quarantined_definitions": quarantinedCount},
			Output: contextSlice,
		},
		domain.AnalysisTraceStep{
			ID: "plan.compile", Kind: "planner", Status: "completed",
			Input: map[string]any{"question": question, "available_dimensions": availableDimensions(profile), "event_order": profile.EventOrder, "intent_source": intentSource},
			Output: map[string]any{
				"intent": plan.Intent, "playbook": plan.ID, "answerability": plan.Answerability,
				"grain": plan.Grain, "metrics": plan.Metrics, "dimensions": plan.Dimensions,
				"allowed_tables": plan.AllowedTables, "required_evidence": plan.RequiredEvidence,
				"limitations": plan.Limitations, "requested_segment": plan.RequestedSegment, "requested_dimensions": plan.RequestedDimensions, "sql": plan.SQL,
			},
		},
	)
	contract := domain.AnalysisContract{
		Role:             role,
		Intent:           plan.Intent,
		Playbook:         plan.ID,
		Answerability:    plan.Answerability,
		Feature:          input.Name,
		Question:         question,
		ContextVersion:   graph.Version,
		SchemaVersions:   []string{schemaVersion},
		Grain:            "unique " + plan.Grain + " within the selected period",
		Metrics:          plan.Metrics,
		Guardrails:       []string{"Do not compare incomplete ingestion windows", "Separate session and application conversion", "Treat declared known issues as hypotheses until segmented evidence supports them"},
		Dimensions:       plan.Dimensions,
		KnownIssues:      relevantIssues(graph, input, question),
		AllowedTables:    plan.AllowedTables,
		OperatingRules:   []string{"Aggregate in ClickHouse", "Return the why, confidence, evidence, and a PM action", "Cite context and schema versions"},
		RequiredEvidence: plan.RequiredEvidence,
		Limitations:      plan.Limitations,
		RequestedOutputs: []string{"headline", "why", "confidence", "recommended action", "evidence"},
	}

	insight := domain.Insight{
		Headline:          fmt.Sprintf("%s has a governed %s analysis plan", input.Name, strings.ReplaceAll(plan.Intent, "_", " ")),
		Summary:           "The context layer selected a question-specific playbook and bound it to verified events, fields, tables, grain, and guardrails.",
		Why:               "Execution is in simulation mode, so the plan is visible but no production aggregate was claimed.",
		Confidence:        .6,
		RecommendedAction: "Configure the ClickHouse runtime and execute the bound analysis plan.",
		Evidence: map[string]any{
			"execution_mode": "simulation",
			"playbook":       plan.ID,
			"required":       plan.RequiredEvidence,
		},
		SQL:            plan.SQL,
		ContextVersion: graph.Version,
		SchemaVersion:  schemaVersion,
		TraceID:        traceID,
		Provenance: domain.InsightProvenance{
			Generator: "deterministic", Status: "disabled", PromptVersion: AnalyticsPromptVersion,
		},
	}
	if a.Synthesizer != nil && a.Synthesizer.Enabled() {
		insight.Provenance = a.Synthesizer.Metadata()
		insight.Provenance.Generator = "deterministic"
		insight.Provenance.Status = "not_attempted"
		insight.Provenance.Reason = "LLM synthesis requires a successfully executed aggregate query."
	}
	if plan.Answerability == "not_answerable" {
		insight.Headline = fmt.Sprintf("This %s question is not answerable from the selected feature context", strings.ReplaceAll(plan.Intent, "_", " "))
		insight.Summary = fmt.Sprintf("The selected %s table contains %d profiled rows, but the analysis contract is missing required verified evidence.", schema.Table, profile.Rows)
		insight.Why = strings.Join(plan.Limitations, " ")
		insight.Confidence = .99
		insight.RecommendedAction = "Clarify the intended business definition and instrument the missing governed dimension before querying or synthesizing an answer."
		if plan.Intent == "customer_geography" {
			insight.Headline = "This customer-geography question is not answerable from the selected feature context"
			insight.Summary = fmt.Sprintf("The selected %s table contains %d profiled rows, but no verified city-level customer-origin field.", schema.Table, profile.Rows)
			insight.Why = "The context distinguishes customer origin from travel destination. The destination field is a visa or travel destination, and a country-level GeoIP field cannot establish a requested city. Returning a funnel count would answer a different question."
			insight.RecommendedAction = "Clarify whether 'from' means residence city, current location, country-level GeoIP, or a travel destination, then instrument the corresponding governed dimension."
		}
		reason := strings.Join(plan.Limitations, " ")
		if reason == "" {
			reason = "required governed evidence is unavailable"
		}
		insight.Evidence = map[string]any{"execution_mode": "not_executed", "playbook": plan.ID, "dataset_rows": profile.Rows, "reason": reason}
		insight.SQL = ""
		insight.Provenance.Generator = "deterministic"
		insight.Provenance.Status = "not_attempted"
		insight.Provenance.Reason = "The context contract rejected the question before ClickHouse or LLM execution."
		analysisTrace.Steps = append(analysisTrace.Steps,
			domain.AnalysisTraceStep{ID: "tool.clickhouse.query", Kind: "tool", Status: "skipped", Input: map[string]any{"allowed_tables": plan.AllowedTables}, Output: map[string]any{"reason": "analysis contract is not_answerable"}},
			domain.AnalysisTraceStep{ID: "llm.synthesize", Kind: "generation", Status: "skipped", Output: map[string]any{"reason": "no verified aggregate evidence was produced"}},
		)
		finishAnalysisTrace(&insight, analysisTrace)
		return contract, insight
	}
	if a.Reader == nil || !a.Reader.Enabled() || plan.SQL == "" {
		analysisTrace.Steps = append(analysisTrace.Steps,
			domain.AnalysisTraceStep{ID: "tool.clickhouse.query", Kind: "tool", Status: "skipped", Input: map[string]any{"sql": plan.SQL, "allowed_tables": plan.AllowedTables}, Output: map[string]any{"reason": "ClickHouse reader is disabled or SQL is unavailable"}},
			domain.AnalysisTraceStep{ID: "llm.synthesize", Kind: "generation", Status: "skipped", Output: map[string]any{"reason": "no aggregate evidence was produced"}},
		)
		finishAnalysisTrace(&insight, analysisTrace)
		return contract, insight
	}

	queryStarted := time.Now()
	tracer := a.Tracer
	if tracer == nil {
		tracer = otel.Tracer("featurelens/analytics")
	}
	queryCtx, querySpan := tracer.Start(ctx, "analytics.clickhouse_query", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "tool"),
		attribute.String("langfuse.observation.input", traceJSON(map[string]any{"sql": plan.SQL, "allowed_tables": plan.AllowedTables, "playbook": plan.ID})),
		attribute.String("db.system", "clickhouse"),
		attribute.String("db.statement", plan.SQL),
		attribute.StringSlice("analytics.allowed_tables", plan.AllowedTables),
		attribute.String("analytics.playbook", plan.ID),
		attribute.Int("analytics.context_version", graph.Version),
	))
	rows, err := a.Reader.QueryJSON(queryCtx, plan.SQL)
	queryDuration := time.Since(queryStarted).Milliseconds()
	if err != nil {
		querySpan.RecordError(err)
		querySpan.SetStatus(codes.Error, "ClickHouse query failed")
		querySpan.End()
		analysisTrace.Steps = append(analysisTrace.Steps,
			domain.AnalysisTraceStep{ID: "tool.clickhouse.query", ObservationID: querySpan.SpanContext().SpanID().String(), Kind: "tool", Status: "failed", DurationMS: queryDuration, Input: map[string]any{"sql": plan.SQL, "allowed_tables": plan.AllowedTables}, Error: err.Error()},
			domain.AnalysisTraceStep{ID: "llm.synthesize", Kind: "generation", Status: "skipped", Output: map[string]any{"reason": "ClickHouse query failed"}},
		)
		insight.Evidence["query_error"] = err.Error()
		insight.Confidence = .25
		insight.Summary = "The semantic plan was compiled, but ClickHouse could not execute it."
		insight.RecommendedAction = "Inspect the bound fields and tables before trusting an answer."
		finishAnalysisTrace(&insight, analysisTrace)
		return contract, insight
	}
	encodedRows, _ := json.Marshal(rows)
	querySpan.SetAttributes(
		attribute.String("analytics.aggregate_output", truncateTraceValue(string(encodedRows), 16000)),
		attribute.String("langfuse.observation.output", traceJSON(map[string]any{"aggregate_rows": rows, "row_count": len(rows)})),
	)
	querySpan.End()
	analysisTrace.Steps = append(analysisTrace.Steps, domain.AnalysisTraceStep{
		ID: "tool.clickhouse.query", ObservationID: querySpan.SpanContext().SpanID().String(), Kind: "tool", Status: "completed", DurationMS: queryDuration,
		Input:  map[string]any{"sql": plan.SQL, "allowed_tables": plan.AllowedTables},
		Output: map[string]any{"aggregate_rows": rows, "row_count": len(rows)},
	})
	insight = interpretPlan(plan, input.Name, rows, insight)
	missingEvidence := validateRequiredEvidence(plan, insight.Evidence)
	_, validationSpan := tracer.Start(ctx, "analytics.evidence_validate", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "evaluator"),
		attribute.String("langfuse.observation.input", traceJSON(map[string]any{"required_evidence": plan.RequiredEvidence, "requested_dimensions": plan.RequestedDimensions})),
		attribute.String("evaluator.name", "Governed evidence completeness"),
		attribute.StringSlice("analytics.required_evidence", plan.RequiredEvidence),
		attribute.StringSlice("analytics.missing_evidence", missingEvidence),
		attribute.StringSlice("analytics.requested_dimensions", plan.RequestedDimensions),
		attribute.Int("analytics.context_version", graph.Version),
	))
	if len(missingEvidence) > 0 {
		validationSpan.SetAttributes(attribute.String("langfuse.observation.output", traceJSON(map[string]any{"complete": false, "missing_evidence": missingEvidence})))
		validationSpan.SetStatus(codes.Error, "required aggregate evidence is incomplete")
		validationSpan.End()
		contract.Answerability = "not_answerable"
		insight.Headline = "The requested analysis did not produce complete governed evidence"
		if len(plan.RequestedDimensions) > 0 {
			insight.Headline = fmt.Sprintf("%s completion could not be verified", strings.ReplaceAll(strings.Join(plan.RequestedDimensions, " and "), "_", " "))
		}
		insight.Summary = fmt.Sprintf("ClickHouse executed the governed plan, but the result was missing required evidence: %s.", strings.Join(missingEvidence, ", "))
		insight.Why = "FeatureLens stopped before LLM synthesis because an answer without the requested aggregate cut would describe a different question."
		insight.Confidence = .99
		insight.RecommendedAction = "Inspect the requested dimension binding and event coverage, then rerun the governed query."
		insight.Evidence["missing_evidence"] = missingEvidence
		insight.Provenance.Generator = "deterministic"
		insight.Provenance.Status = "not_attempted"
		insight.Provenance.Reason = "Required aggregate evidence was incomplete; LLM synthesis was blocked."
		analysisTrace.Steps = append(analysisTrace.Steps,
			domain.AnalysisTraceStep{ID: "evidence.validate", ObservationID: validationSpan.SpanContext().SpanID().String(), Kind: "evaluator", Status: "failed", Input: map[string]any{"required_evidence": plan.RequiredEvidence, "requested_dimensions": plan.RequestedDimensions}, Output: map[string]any{"missing_evidence": missingEvidence}},
			domain.AnalysisTraceStep{ID: "llm.synthesize", Kind: "generation", Status: "skipped", Output: map[string]any{"reason": "required aggregate evidence is incomplete"}},
		)
		finishAnalysisTrace(&insight, analysisTrace)
		return contract, insight
	}
	validationSpan.SetAttributes(attribute.String("langfuse.observation.output", traceJSON(map[string]any{"complete": true})))
	validationSpan.End()
	analysisTrace.Steps = append(analysisTrace.Steps, domain.AnalysisTraceStep{
		ID: "evidence.validate", ObservationID: validationSpan.SpanContext().SpanID().String(), Kind: "evaluator", Status: "completed",
		Input:  map[string]any{"required_evidence": plan.RequiredEvidence, "requested_dimensions": plan.RequestedDimensions},
		Output: map[string]any{"complete": true},
	})
	insight, synthesisStep := a.synthesize(ctx, contract, graph, insight)
	analysisTrace.Steps = append(analysisTrace.Steps, synthesisStep)
	finishAnalysisTrace(&insight, analysisTrace)
	return contract, insight
}

func (a AnalyticsAgent) SynthesisStatus() map[string]any {
	if a.Synthesizer == nil || !a.Synthesizer.Enabled() {
		return map[string]any{"enabled": false, "mode": "deterministic", "prompt_version": AnalyticsPromptVersion}
	}
	metadata := a.Synthesizer.Metadata()
	return map[string]any{"enabled": true, "mode": "llm", "provider": metadata.Provider, "model": metadata.Model, "prompt_version": metadata.PromptVersion}
}

func (a AnalyticsAgent) synthesize(ctx context.Context, contract domain.AnalysisContract, graph domain.ContextVersion, insight domain.Insight) (domain.Insight, domain.AnalysisTraceStep) {
	if contract.Answerability == "not_answerable" {
		return insight, domain.AnalysisTraceStep{ID: "llm.synthesize", Kind: "generation", Status: "skipped", Output: map[string]any{"reason": "analysis contract is not_answerable"}}
	}
	if a.Synthesizer == nil || !a.Synthesizer.Enabled() {
		return insight, domain.AnalysisTraceStep{ID: "llm.synthesize", Kind: "generation", Status: "skipped", Output: map[string]any{"reason": "LLM synthesis is disabled"}}
	}
	metadata := a.Synthesizer.Metadata()
	draft := insight
	draft.Trace = nil
	request := InsightSynthesisRequest{
		Contract: contract,
		Context:  compactSynthesisContext(graph, contract),
		Evidence: insight.Evidence,
		Draft:    draft,
	}
	step := domain.AnalysisTraceStep{
		ID: "llm.synthesize", Kind: "generation", Status: "completed",
		Input: map[string]any{"provider": metadata.Provider, "model": metadata.Model, "prompt_version": metadata.PromptVersion, "system_prompt": AnalyticsSystemPrompt, "governed_request": request},
	}
	started := time.Now()
	synthesis, err := a.Synthesizer.Synthesize(ctx, request)
	step.DurationMS = time.Since(started).Milliseconds()
	if err != nil {
		step.Status = "failed"
		step.Error = err.Error()
		metadata.Generator = "deterministic"
		metadata.Status = "fallback"
		metadata.Reason = "LLM synthesis was unavailable or invalid; the governed deterministic insight was retained."
		insight.Provenance = metadata
		step.Output = map[string]any{"fallback": "governed deterministic insight retained"}
		return insight, step
	}
	insight.Headline = synthesis.Headline
	insight.Summary = synthesis.Summary
	insight.Why = synthesis.Why
	insight.Confidence = math.Min(insight.Confidence, synthesis.Confidence)
	insight.RecommendedAction = synthesis.RecommendedAction
	if len(synthesis.KeyFindings) > 0 {
		insight.KeyFindings = synthesis.KeyFindings
	}
	metadata.Generator = "llm"
	metadata.Status = "generated"
	insight.Provenance = metadata
	step.Output = synthesis
	step.ObservationID = synthesis.ObservationID
	return insight, step
}

func validateRequiredEvidence(plan analysisPlan, evidence map[string]any) []string {
	missing := make([]string, 0)
	seen := map[string]bool{}
	add := func(key string) {
		if key != "" && !seen[key] {
			seen[key] = true
			missing = append(missing, key)
		}
	}
	for _, key := range plan.RequiredEvidence {
		value, ok := evidence[key]
		if !ok || !evidenceValuePresent(value) {
			add(key)
		}
	}
	if plan.Intent == "segment_comparison" && len(plan.RequestedDimensions) > 0 {
		rows, ok := evidence["segments"].([]map[string]any)
		if !ok || len(rows) == 0 {
			for _, dimension := range plan.RequestedDimensions {
				add("segments." + dimension)
			}
		} else {
			for _, dimension := range plan.RequestedDimensions {
				matched := 0
				for _, row := range rows {
					if textValue(row["dimension"]) != dimension {
						continue
					}
					matched++
					for _, field := range []string{"segment", "entrants", "completions", "completion_rate"} {
						if value, exists := row[field]; !exists || value == nil {
							add("segments." + dimension + "." + field)
						}
					}
				}
				if matched == 0 {
					add("segments." + dimension)
				}
			}
		}
	}
	return missing
}

func evidenceValuePresent(value any) bool {
	if value == nil {
		return false
	}
	switch typed := value.(type) {
	case string:
		return strings.TrimSpace(typed) != ""
	case []map[string]any:
		return len(typed) > 0
	case []any:
		return len(typed) > 0
	case map[string]any:
		return len(typed) > 0
	default:
		return true
	}
}

func finishAnalysisTrace(insight *domain.Insight, analysisTrace *domain.AnalysisTrace) {
	analysisTrace.CompletedAt = time.Now().UTC()
	analysisTrace.Steps = append(analysisTrace.Steps, domain.AnalysisTraceStep{
		ID: "answer.compose", Kind: "output", Status: "completed",
		Output: map[string]any{
			"headline": insight.Headline, "summary": insight.Summary, "why": insight.Why,
			"confidence": insight.Confidence, "recommended_action": insight.RecommendedAction,
			"provenance": insight.Provenance,
		},
	})
	insight.Trace = analysisTrace
}

func truncateTraceValue(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	return value[:limit] + "…"
}

func traceJSON(value any) string {
	encoded, err := json.Marshal(value)
	if err != nil {
		return "{}"
	}
	return string(encoded)
}

func defaultQuestion(input domain.FeatureInput, profile domain.EventProfile) string {
	questions := ExtractQuestions(input.SpecMarkdown)
	if len(questions) > 0 {
		return questions[0]
	}
	if len(profile.EventOrder) >= 2 {
		return fmt.Sprintf("How does %s progress from %s to %s?", input.Name, profile.EventOrder[0], profile.EventOrder[len(profile.EventOrder)-1])
	}
	return "What did this feature add and how should a Product Manager evaluate it?"
}

func funnelBounds(profile domain.EventProfile) (string, string) {
	if len(profile.EventOrder) == 0 {
		return "", ""
	}
	return profile.EventOrder[0], profile.EventOrder[len(profile.EventOrder)-1]
}

func analysisGrain(profile domain.EventProfile) string {
	for _, candidate := range []string{"application_id", "user_id", "id"} {
		if hasField(profile, candidate) {
			return candidate
		}
	}
	return "id"
}

func availableDimensions(profile domain.EventProfile) []string {
	return governedDimensionNames(profile)
}

func relevantIssues(graph domain.ContextVersion, input domain.FeatureInput, question string) []string {
	featureKey := "feature:" + Slug(input.Name)
	linked := map[string]bool{}
	for _, edge := range graph.Edges {
		if edge.To == featureKey && (edge.Relation == "MAY_AFFECT" || edge.Relation == "AFFECTS") {
			linked[edge.From] = true
		}
	}
	// Every issue linked to the feature through the graph is attached as a
	// hypothesis, regardless of how the question is worded. Contract guardrails
	// keep over-inclusion safe; question-text keyword matching silently dropped
	// caveats for reworded questions.
	issues := []string{}
	for _, node := range graph.Nodes {
		if node.Type != "known_issue" || !linked[node.Key] {
			continue
		}
		issues = append(issues, node.Name)
	}
	return issues
}

func ClassifyIntent(question string) string {
	lower := strings.ToLower(question)
	switch {
	case (strings.Contains(lower, "customer") || strings.Contains(lower, "user") || strings.Contains(lower, "applicant")) &&
		(strings.Contains(lower, " from ") || strings.Contains(lower, "city") || strings.Contains(lower, "location") || strings.Contains(lower, "geograph")):
		return "customer_geography"
	case strings.Contains(lower, "group size") && (strings.Contains(lower, "complete") || strings.Contains(lower, "completion") || strings.Contains(lower, "fall off") || strings.Contains(lower, "drop")):
		return "group_size_completion"
	case strings.Contains(lower, "traveller") && (strings.Contains(lower, "removed") || strings.Contains(lower, "remove") || strings.Contains(lower, "churn")):
		return "group_traveller_churn"
	case (strings.Contains(lower, "docs_complete") || strings.Contains(lower, "document completion")) && strings.Contains(lower, "bottleneck"):
		return "group_document_bottleneck"
	case strings.Contains(lower, "destination") && (strings.Contains(lower, "segment") || strings.Contains(lower, "drive group")):
		return "group_segments"
	case strings.Contains(lower, "otp") || strings.Contains(lower, "fail") || strings.Contains(lower, "platform"):
		return "platform_failure"
	case strings.Contains(lower, "trend") || strings.Contains(lower, "over time") || strings.Contains(lower, "daily") || strings.Contains(lower, "week over week"):
		return "completion_trend"
	case strings.Contains(lower, "by device") || strings.Contains(lower, "by os") || strings.Contains(lower, "mobile") || strings.Contains(lower, "segment breakdown") || strings.Contains(lower, "segment comparison") ||
		((strings.Contains(lower, "city") || strings.Contains(lower, "cities") || strings.Contains(lower, "country") || strings.Contains(lower, "countries") || strings.Contains(lower, "geograph")) &&
			(strings.Contains(lower, "rate") || strings.Contains(lower, "completion") || strings.Contains(lower, "highest") || strings.Contains(lower, "lowest") || strings.Contains(lower, "best") || strings.Contains(lower, "most") || strings.Contains(lower, "performance"))):
		return "segment_comparison"
	case strings.Contains(lower, "faster") || strings.Contains(lower, "latency") || strings.Contains(lower, "time"):
		return "latency_performance"
	case strings.Contains(lower, "adopt") || strings.Contains(lower, "which segment") || strings.Contains(lower, "use most"):
		return "feature_adoption"
	case strings.Contains(lower, "lift") || strings.Contains(lower, "vs standard") || strings.Contains(lower, "impact") || strings.Contains(lower, "conversion") || strings.Contains(lower, "convert"):
		return "conversion_comparison"
	case strings.Contains(lower, "drop") || strings.Contains(lower, "abandon"):
		return "funnel_diagnosis"
	default:
		return "feature_completion"
	}
}

func interpretPlan(plan analysisPlan, featureName string, rows []map[string]any, insight domain.Insight) domain.Insight {
	insight.Evidence = map[string]any{"execution_mode": "clickhouse", "playbook": plan.ID}
	if len(rows) == 0 {
		insight.Headline = "No rows matched the governed analysis window"
		insight.Summary = "ClickHouse executed the plan but returned no aggregate evidence."
		insight.Why = "The feature may not have a complete observation window for the selected events."
		insight.Confidence = .3
		insight.RecommendedAction = "Check ingestion completeness and the event-window contract."
		return insight
	}

	switch plan.Intent {
	case "customer_geography":
		copyEvidence(insight.Evidence, rows[0])
		city := textValue(rows[0]["requested_city"])
		customers := number(rows[0]["customers"])
		total := number(rows[0]["total_customers"])
		share := number(rows[0]["customer_share"])
		insight.Headline = fmt.Sprintf("%.0f unique customers in the selected feature dataset were observed from %s", customers, city)
		insight.Summary = fmt.Sprintf("ClickHouse found %.0f unique users for observed city %s out of %.0f unique users in this feature dataset (%.2f%%).", customers, city, total, share*100)
		insight.Why = "The query uses the observed city field and unique user_id. The context treats city as event geo-city, not proof of residence or hometown, and excludes visa destination from the origin definition."
		insight.Confidence = .88
		insight.RecommendedAction = "Confirm the city field's collection semantics before using this count for CRM, residence, or market-sizing decisions."
	case "group_size_completion":
		insight.Evidence["segments"] = rows
		worst := lowestMetricRow(rows, "completion_rate")
		insight.Evidence["lowest_completion_segment"] = worst
		insight.Headline = fmt.Sprintf("Group size %s has the lowest observed completion at %.2f%%", textValue(worst["group_size"]), number(worst["completion_rate"])*100)
		insight.Summary = fmt.Sprintf("ClickHouse compared %d group-size cohorts using unique applications from group_started to group_submitted.", len(rows))
		insight.Why = "The result is segmented by the verified group_size field, so differences across large and small groups are measured rather than inferred from an overall funnel rate."
		insight.Confidence = .92
		insight.RecommendedAction = "Inspect the lowest-completion group-size cohort by document completeness and platform before changing the group flow."
	case "group_traveller_churn":
		copyEvidence(insight.Evidence, rows[0])
		insight.Headline = fmt.Sprintf("%.0f travellers were removed after %.0f additions", number(rows[0]["travellers_removed"]), number(rows[0]["travellers_added"]))
		insight.Summary = fmt.Sprintf("Across %.0f started groups, the observed averages were %.2f additions and %.2f removals per group.", number(rows[0]["groups_started"]), number(rows[0]["additions_per_group"]), number(rows[0]["removals_per_group"]))
		insight.Why = "The calculation counts the verified traveller_added and traveller_removed events and normalizes them by unique started groups."
		insight.Confidence = .94
		insight.RecommendedAction = "Segment groups with removals by relation, group size, and document state to locate avoidable edit churn."
	case "group_document_bottleneck":
		insight.Evidence["segments"] = rows
		worst := lowestMetricRow(rows, "submission_rate")
		insight.Evidence["lowest_submission_segment"] = worst
		insight.Headline = "Document-completion cohorts are now measurable by group size"
		insight.Summary = fmt.Sprintf("ClickHouse produced %d group-size × document-completion cohorts with group submission counts and rates.", len(rows))
		insight.Why = "The analysis reduces traveller-level docs_complete events to a group-level all-documents-complete flag, then compares observed submission rates. This is an association, not proof of causation."
		insight.Confidence = .87
		insight.RecommendedAction = "Prioritize the group sizes where incomplete-document cohorts have the largest submission-rate gap, then test targeted completion guidance."
	case "group_segments":
		insight.Evidence["segments"] = rows
		insight.Evidence["largest_segment"] = rows[0]
		insight.Headline = fmt.Sprintf("%s %s is the largest observed group-application segment", textValue(rows[0]["dimension"]), textValue(rows[0]["segment"]))
		insight.Summary = fmt.Sprintf("The leading segment has %.0f group starts; ClickHouse also reports its submissions and completion rate alongside device and GeoIP cohorts.", number(rows[0]["groups_started"]))
		insight.Why = "The ranking uses unique group application starts by verified dimensions. It measures observed feature volume, not exposure-adjusted market demand."
		insight.Confidence = .91
		insight.RecommendedAction = "Compare high-volume segments with low completion and prioritize the largest evidence-backed opportunity."
	case "recovery_drop_step":
		insight.Evidence["segments"] = rows
		best := highestMetricRow(rows, "recovery_rate")
		insight.Evidence["most_recoverable_step"] = best
		insight.Headline = fmt.Sprintf("%s is the most recoverable observed drop step at %.2f%%", textValue(best["drop_step"]), number(best["recovery_rate"])*100)
		insight.Summary = fmt.Sprintf("ClickHouse compared %d drop-step cohorts using unique abandoned applications and observed reconversions.", len(rows))
		insight.Why = "The playbook carries each application's detected drop_step through to reconversion and keeps the result separate from causal or incremental-lift claims."
		insight.Confidence = .91
		insight.RecommendedAction = "Prioritize the highest-volume recoverable step, then validate reminder incrementality with an untreated holdout."
	case "recovery_channel":
		insight.Evidence["segments"] = rows
		best := highestMetricRow(rows, "recovery_rate")
		insight.Evidence["best_channel"] = best
		insight.Headline = fmt.Sprintf("%s has the highest observed recovery rate at %.2f%%", textValue(best["channel"]), number(best["recovery_rate"])*100)
		insight.Summary = fmt.Sprintf("ClickHouse compared %d channels from reminder sent through open, click, and reconversion.", len(rows))
		insight.Why = "Open, click, and reconversion are calculated on the same application-level reminder cohort so channel-stage denominators stay explicit."
		insight.Confidence = .9
		insight.RecommendedAction = "Check targeting mix and cost per recovered application before moving more traffic to the leading channel."
	case "recovery_timing":
		insight.Evidence["segments"] = rows
		best := highestMetricRow(rows, "recovery_rate")
		insight.Evidence["best_timing"] = best
		insight.Headline = fmt.Sprintf("The %.0f-hour cohort has the highest observed recovery at %.2f%%", number(best["hours_since_drop"]), number(best["recovery_rate"])*100)
		insight.Summary = fmt.Sprintf("ClickHouse compared %d reminder-timing cohorts using open and reconversion rates.", len(rows))
		insight.Why = "The timing value comes from reminder_sent and is joined to later outcomes at application grain; the context flags that timing was not randomized."
		insight.Confidence = .87
		insight.RecommendedAction = "Randomize eligible abandoners across timing windows before adopting the leading cohort as a sending policy."
	case "recovery_segments":
		insight.Evidence["segments"] = rows
		insight.Evidence["largest_recovery_segment"] = rows[0]
		insight.Headline = fmt.Sprintf("%s %s contributes the most observed reconversions", textValue(rows[0]["dimension"]), textValue(rows[0]["segment"]))
		insight.Summary = fmt.Sprintf("ClickHouse produced %d device, GeoIP, and destination cuts ranked by reconverted applications and recovery rate.", len(rows))
		insight.Why = "The playbook preserves both abandonment volume and reconversion count, preventing a small high-rate cohort from automatically becoming the largest opportunity."
		insight.Confidence = .9
		insight.RecommendedAction = "Prioritize high-volume segments with below-baseline recovery and inspect their drop-step and channel mix."
	case "conversion_comparison":
		copyEvidence(insight.Evidence, rows[0])
		featureRate := number(rows[0]["feature_completion_rate"])
		standardRate := number(rows[0]["standard_conversion_rate"])
		lift := number(rows[0]["percentage_point_lift"])
		direction := "above"
		if lift < 0 {
			direction = "below"
		}
		comparisonLabel := "the comparable standard checkout cohort"
		if plan.ID == "playbook:nullable-cohort-conversion:v1" {
			comparisonLabel = "the null-marker baseline cohort"
			insight.Summary = fmt.Sprintf("The marked cohort completes at %.2f%% versus %.2f%% for entities where the governed cohort marker is null.", featureRate*100, standardRate*100)
			insight.Why = "ClickHouse assigned each entity to a marked or null-marker cohort from the verified nullable field, then compared completion on the same semantic funnel. The marker is user-selected rather than randomized, so the comparison is observational rather than causal."
		} else {
			insight.Summary = fmt.Sprintf("Feature completion is %.2f%% versus %.2f%% for standard checkout in the aligned observation window.", featureRate*100, standardRate*100)
			insight.Why = "ClickHouse compared unique application cohorts over aligned calendar dates and allowed one additional day for standard purchase completion. Date-level alignment avoids false precision while source timestamp timezone provenance remains unresolved; the comparison is observational rather than causal."
		}
		insight.Headline = fmt.Sprintf("%s is %.2f percentage points %s %s", featureName, math.Abs(lift*100), direction, comparisonLabel)
		insight.Confidence = .86
		insight.RecommendedAction = "Validate the difference with an experiment or matched cohort before treating it as incremental lift."
	case "platform_failure":
		insight.Evidence["segments"] = rows
		insight.Evidence["worst_segment"] = rows[0]
		device := textValue(rows[0]["device_type"])
		osName := textValue(rows[0]["os"])
		rate := number(rows[0]["otp_success_rate"])
		insight.Headline = fmt.Sprintf("%s / %s has the weakest OTP success at %.2f%%", device, osName, rate*100)
		insight.Summary = "The platform diagnostic separates OTP success from downstream payment confirmation for every observed device/OS segment."
		insight.Why = "The worst segment is ranked from ClickHouse aggregates and is consistent with the context graph's linked iOS OTP regression hypothesis."
		insight.Confidence = .96
		insight.RecommendedAction = "Prioritize the weakest platform, validate the OTP autofill path, and monitor OTP success and confirmation-from-OTP together."
	case "latency_performance":
		copyEvidence(insight.Evidence, rows[0])
		average := number(rows[0]["avg_latency_ms"])
		insight.Headline = fmt.Sprintf("%s confirms in %.2fs on average; faster-vs-standard is not yet measurable", featureName, average/1000)
		insight.Summary = fmt.Sprintf("The observed p50 is %.2fs and p95 is %.2fs across %.0f confirmed payments.", number(rows[0]["p50_latency_ms"])/1000, number(rows[0]["p95_latency_ms"])/1000, number(rows[0]["payments"]))
		insight.Why = "The feature emits payment latency, but the standard checkout instrumentation has no equivalent latency metric in the published context."
		insight.Confidence = .82
		insight.RecommendedAction = "Instrument the same latency definition on standard checkout before claiming a speed improvement."
	case "feature_adoption":
		insight.Evidence["segments"] = rows
		top := firstMetric(rows, "adoption_rate")
		insight.Evidence["top_adoption_segment"] = top
		insight.Headline = fmt.Sprintf("%s leads adoption at %.2f%%", textValue(top["segment"]), number(top["rate"])*100)
		insight.Summary = "ClickHouse ranks adoption by device and geography and reports saved-method mix separately where eligibility denominators are unavailable."
		insight.Why = "Adoption uses unique applications selected divided by unique applications shown within the same segment."
		insight.Confidence = .91
		insight.RecommendedAction = "Investigate the lowest-adoption eligible segments and keep saved-method mix separate from eligibility-adjusted adoption."
	case "completion_trend":
		insight.Evidence["trend_series"] = rows
		first, latest := rows[0], rows[len(rows)-1]
		firstRate, latestRate := number(first["completion_rate"]), number(latest["completion_rate"])
		granularity := textValue(first["granularity"])
		if granularity == "" {
			granularity = "week"
		}
		insight.Evidence["latest_completion_rate"] = latestRate
		insight.Evidence["percentage_point_change"] = latestRate - firstRate
		insight.Headline = fmt.Sprintf("%s completion is %.2f%% in the latest observed %s", featureName, latestRate*100, granularity)
		insight.Summary = fmt.Sprintf("%sly completion moved from %.2f%% on %s to %.2f%% on %s across %d observed %ss.", strings.ToUpper(granularity[:1])+granularity[1:], firstRate*100, textValue(first["date"]), latestRate*100, textValue(latest["date"]), len(rows), granularity)
		insight.Why = fmt.Sprintf("The trend uses the same governed entry event, completion event, and entity grain in every %s so changes are comparable within this feature.", granularity)
		insight.Confidence = .9
		insight.RecommendedAction = fmt.Sprintf("Inspect the largest %sly movement by device and traffic mix before attributing it to a product change.", granularity)
	case "segment_comparison":
		insight.Evidence["segments"] = rows
		best := highestMetricRow(rows, "completion_rate")
		worst := lowestMetricRow(rows, "completion_rate")
		insight.Evidence["best_segment"] = best
		insight.Evidence["weakest_segment"] = worst
		insight.Headline = fmt.Sprintf("%s %s leads %s completion at %.2f%%", textValue(best["dimension"]), textValue(best["segment"]), featureName, number(best["completion_rate"])*100)
		insight.Summary = fmt.Sprintf("The weakest verified cohort is %s %s at %.2f%%; ClickHouse compared %d qualified cohorts with explicit entrant denominators.", textValue(worst["dimension"]), textValue(worst["segment"]), number(worst["completion_rate"])*100, len(rows))
		insight.Why = "Each segment is assigned from the governed entrant event at entity grain, preventing later-event dimension sparsity from inflating completion above 100%."
		insight.Confidence = .91
		insight.RecommendedAction = "Prioritize the largest low-performing cohort, then validate whether eligibility or traffic mix explains the gap."
	case "funnel_diagnosis":
		insight.Evidence["stages"] = rows
		largest := map[string]any{"from_stage": textValue(rows[0]["stage"]), "to_stage": textValue(rows[0]["stage"]), "drop": float64(0), "retention_rate": float64(1)}
		for index := 1; index < len(rows); index++ {
			previous, current := number(rows[index-1]["entities"]), number(rows[index]["entities"])
			drop := previous - current
			if drop > number(largest["drop"]) {
				retention := float64(0)
				if previous > 0 {
					retention = current / previous
				}
				largest = map[string]any{"from_stage": textValue(rows[index-1]["stage"]), "to_stage": textValue(rows[index]["stage"]), "drop": drop, "retention_rate": retention}
			}
		}
		insight.Evidence["largest_drop"] = largest
		insight.Headline = fmt.Sprintf("%s has its largest observed drop from %s to %s", featureName, textValue(largest["from_stage"]), textValue(largest["to_stage"]))
		insight.Summary = fmt.Sprintf("The governed funnel loses %.0f unique entities at that transition, retaining %.2f%% of the prior stage.", number(largest["drop"]), number(largest["retention_rate"])*100)
		insight.Why = "ClickHouse counted unique entities at each verified stage using the feature-specific funnel and semantic grain."
		insight.Confidence = .93
		insight.RecommendedAction = "Segment this transition by device, OS, and destination, then inspect the product change nearest the drop."
	default:
		copyEvidence(insight.Evidence, rows[0])
		insight.Headline = fmt.Sprintf("%s completion is measurable from the verified feature table", featureName)
		insight.Summary = "ClickHouse computed entrance, completion, and completion rate from the published event sequence."
		insight.Why = "The calculation counts unique entities at the verified first and last feature events."
		insight.Confidence = .9
		insight.RecommendedAction = "Review the result across a complete window and relevant segments."
	}
	return insight
}

func copyEvidence(target map[string]any, source map[string]any) {
	for key, value := range source {
		target[key] = value
	}
}

func firstMetric(rows []map[string]any, metric string) map[string]any {
	for _, row := range rows {
		if textValue(row["metric"]) == metric {
			return row
		}
	}
	return rows[0]
}

func lowestMetricRow(rows []map[string]any, metric string) map[string]any {
	worst := rows[0]
	worstValue := number(worst[metric])
	for _, row := range rows[1:] {
		value := number(row[metric])
		if math.IsNaN(worstValue) || (!math.IsNaN(value) && value < worstValue) {
			worst = row
			worstValue = value
		}
	}
	return worst
}

func highestMetricRow(rows []map[string]any, metric string) map[string]any {
	best := rows[0]
	bestValue := number(best[metric])
	for _, row := range rows[1:] {
		value := number(row[metric])
		if math.IsNaN(bestValue) || (!math.IsNaN(value) && value > bestValue) {
			best = row
			bestValue = value
		}
	}
	return best
}

func number(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case float32:
		return float64(typed)
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case jsonNumber:
		parsed, _ := typed.Float64()
		return parsed
	default:
		return math.NaN()
	}
}

type jsonNumber interface{ Float64() (float64, error) }

func textValue(value any) string {
	if value == nil {
		return "unknown"
	}
	return fmt.Sprint(value)
}

func hasField(profile domain.EventProfile, column string) bool {
	for _, field := range profile.Fields {
		if field.ColumnName == column {
			return true
		}
	}
	return false
}
