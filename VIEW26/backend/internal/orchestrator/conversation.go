package orchestrator

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

type conversationResult struct {
	run    domain.FeatureRun
	answer domain.QuestionResponse
}

func (o *Orchestrator) Converse(ctx context.Context, request domain.ConversationRequest) (domain.ConversationResponse, error) {
	request.Question = strings.TrimSpace(request.Question)
	if request.Question == "" {
		return domain.ConversationResponse{}, fmt.Errorf("question is required")
	}
	if strings.TrimSpace(request.Role) == "" {
		request.Role = "product_manager"
	}

	ctx, span := o.tracer.Start(ctx, "analytics.portfolio_conversation", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "agent"),
		attribute.String("langfuse.trace.name", "analytics.portfolio_conversation"),
		attribute.StringSlice("langfuse.trace.tags", []string{"featurelens", "portfolio-conversation"}),
		attribute.String("langfuse.observation.input", langfuseJSON(map[string]any{
			"question": request.Question, "role": request.Role, "requested_features": request.Features,
			"active_features": request.ActiveFeatures, "history_turns": len(request.History),
		})),
		attribute.String("agent.name", "Analytics Agent"),
		attribute.String("analytics.user_input", request.Question),
		attribute.String("analytics.role", request.Role),
		attribute.Int("analytics.history_turns", len(request.History)),
	))
	defer span.End()
	traceID := span.SpanContext().TraceID().String()
	if traceID == "00000000000000000000000000000000" {
		traceID = newID("trace")
	}

	graph := o.store.LatestContext()
	latestVersion := graph.Version
	staleContext := false
	if request.ContextVersion != nil && *request.ContextVersion != latestVersion {
		if !request.AllowStale {
			return domain.ConversationResponse{}, fmt.Errorf("context v%d is not latest (v%d); set allow_stale to pin a historical version", *request.ContextVersion, latestVersion)
		}
		versioned, ok := o.store.Context(*request.ContextVersion)
		if !ok {
			return domain.ConversationResponse{}, fmt.Errorf("context v%d not found", *request.ContextVersion)
		}
		graph = versioned
		staleContext = true
	}

	available := publishedConversationRuns(o.store.ListRuns(), graph)
	if len(available) == 0 {
		return domain.ConversationResponse{}, fmt.Errorf("no published feature context is available yet")
	}
	selected := resolveConversationRuns(request, available)
	if len(selected) == 0 {
		return domain.ConversationResponse{}, fmt.Errorf("no published feature matches the requested conversation scope")
	}
	featureScope := featureNames(selected)
	resolvedQuestion := resolveFollowUpQuestion(request, featureScope)
	span.SetAttributes(
		attribute.StringSlice("analytics.feature_scope", featureScope),
		attribute.Int("analytics.context_version", graph.Version),
	)

	started := time.Now().UTC()
	results := make([]conversationResult, 0, len(selected))
	portfolioQuestion := perFeatureQuestion(request.Question, len(selected))
	for _, run := range selected {
		contract, insight := o.analytics.Analyze(ctx, request.Role, portfolioQuestion, run.Input, *run.Profile, *run.Schema, graph, traceID)
		results = append(results, conversationResult{run: run, answer: domain.QuestionResponse{Contract: contract, Insight: insight}})
	}

	contract := conversationContract(request.Role, resolvedQuestion, graph, results)
	evidence := conversationEvidence(request, graph, results)
	if staleContext {
		staleness := fmt.Sprintf("pinned context v%d; latest is v%d", graph.Version, latestVersion)
		contract.Limitations = append(contract.Limitations, "Answer uses a pinned historical context version: "+staleness)
		evidence["context_staleness"] = staleness
		span.SetAttributes(attribute.Bool("analytics.context_stale", true), attribute.Int("analytics.latest_context_version", latestVersion))
	}
	draft := deterministicConversationInsight(contract, results, evidence, traceID)
	draft, synthesisStep := o.analytics.SynthesizeConversation(ctx, contract, graph, draft)
	mode := conversationMode(request.Question, results)
	charts := buildConversationCharts(request.Question, mode, results, traceID)
	kpis := conversationKPIs(mode, results)
	analysisTrace := &domain.AnalysisTrace{
		TraceID: traceID, Role: request.Role, Feature: contract.Feature, Question: resolvedQuestion,
		ContextVersion: graph.Version, SchemaVersion: strings.Join(contract.SchemaVersions, ", "), DatasetRows: conversationDatasetRows(results),
		StartedAt: started, CompletedAt: time.Now().UTC(),
		Steps: []domain.AnalysisTraceStep{
			{ID: "user.input", Kind: "input", Status: "completed", Input: map[string]any{"question": request.Question, "role": request.Role, "history": compactHistory(request.History)}, Output: map[string]any{"resolved_question": resolvedQuestion}},
			{ID: "context.resolve", Kind: "context", Status: "completed", Input: map[string]any{"context_version": graph.Version, "requested_features": request.Features, "active_features": request.ActiveFeatures}, Output: map[string]any{"feature_scope": featureScope, "schema_versions": contract.SchemaVersions}},
			{ID: "agent.route", Kind: "planner", Status: "completed", Input: map[string]any{"question": request.Question}, Output: conversationRoutingOutput(results)},
			{ID: "sources.execute", Kind: "tool", Status: "completed", Output: conversationSourceTrace(results)},
			{ID: "charts.compose", Kind: "output", Status: "completed", Output: map[string]any{"mode": mode, "chart_count": len(charts), "chart_keys": chartKeys(charts), "kpi_count": len(kpis)}},
			synthesisStep,
			{ID: "answer.compose", ObservationID: span.SpanContext().SpanID().String(), Kind: "output", Status: "completed", Output: map[string]any{"headline": draft.Headline, "summary": draft.Summary, "why": draft.Why, "confidence": draft.Confidence, "recommended_action": draft.RecommendedAction, "provenance": draft.Provenance}},
		},
	}
	draft.Trace = analysisTrace
	draft.ContextVersion = graph.Version
	draft.SchemaVersion = strings.Join(contract.SchemaVersions, ", ")
	draft.TraceID = traceID

	sources := make([]domain.QuestionResponse, 0, len(results))
	for _, result := range results {
		sources = append(sources, result.answer)
	}
	span.SetAttributes(
		attribute.String("analytics.answerability", contract.Answerability),
		attribute.Int("analytics.source_answers", len(sources)),
		attribute.Int("analytics.generated_charts", len(charts)),
		attribute.String("analytics.mode", mode),
		attribute.Int("analytics.generated_kpis", len(kpis)),
		attribute.String("analytics.output", draft.Summary),
		attribute.String("langfuse.observation.output", langfuseJSON(map[string]any{
			"headline": draft.Headline, "summary": draft.Summary, "why": draft.Why,
			"confidence": draft.Confidence, "recommended_action": draft.RecommendedAction,
			"feature_scope": featureScope, "context_version": graph.Version,
		})),
	)
	return domain.ConversationResponse{
		ResolvedQuestion: resolvedQuestion,
		FeatureScope:     featureScope,
		ContextVersion:   graph.Version,
		Mode:             mode,
		Contract:         contract,
		Insight:          draft,
		KPIs:             kpis,
		Charts:           charts,
		Sources:          sources,
		FollowUpPrompts:  conversationFollowUps(request.Question, featureScope, results),
	}, nil
}

func langfuseJSON(value any) string {
	encoded, err := json.Marshal(value)
	if err != nil {
		return "{}"
	}
	return string(encoded)
}

func publishedConversationRuns(runs []domain.FeatureRun, graph domain.ContextVersion) []domain.FeatureRun {
	known := map[string]bool{}
	for _, node := range graph.Nodes {
		if node.Type == "feature" {
			known[node.Key] = true
		}
	}
	seen := map[string]bool{}
	available := make([]domain.FeatureRun, 0, len(runs))
	for _, run := range runs {
		if run.Profile == nil || run.Schema == nil || run.Context == nil || run.Stage != domain.StageCompleted {
			continue
		}
		slug := agent.Slug(run.Input.Name)
		if seen[slug] || !known["feature:"+slug] {
			continue
		}
		seen[slug] = true
		available = append(available, run)
	}
	sort.SliceStable(available, func(i, j int) bool {
		left, right := available[i].Context.Version, available[j].Context.Version
		if left == right {
			return available[i].Input.Name < available[j].Input.Name
		}
		return left < right
	})
	return available
}

func resolveConversationRuns(request domain.ConversationRequest, available []domain.FeatureRun) []domain.FeatureRun {
	if asksForPortfolio(request.Question) {
		return available
	}
	explicit := mentionedConversationRuns(request.Question, available)
	if len(explicit) > 0 {
		if referencesPriorScope(request.Question) {
			explicit = mergeConversationRuns(explicit, runsByNames(request.ActiveFeatures, available))
		}
		return explicit
	}
	if scoped := runsByNames(request.Features, available); len(scoped) > 0 {
		return scoped
	}
	active := request.ActiveFeatures
	if len(active) == 0 {
		for index := len(request.History) - 1; index >= 0; index-- {
			if len(request.History[index].FeatureScope) > 0 {
				active = request.History[index].FeatureScope
				break
			}
		}
	}
	if scoped := runsByNames(active, available); len(scoped) > 0 {
		return scoped
	}
	return available
}

func mentionedConversationRuns(question string, available []domain.FeatureRun) []domain.FeatureRun {
	lower := normalizeConversationText(question)
	selected := []domain.FeatureRun{}
	for _, run := range available {
		name := normalizeConversationText(run.Input.Name)
		slug := strings.ReplaceAll(agent.Slug(run.Input.Name), "_", " ")
		mentioned := strings.Contains(lower, name) || strings.Contains(lower, slug)
		if !mentioned {
			for _, alias := range featureAliases(run.Input.Name) {
				if strings.Contains(lower, alias) {
					mentioned = true
					break
				}
			}
		}
		if mentioned {
			selected = append(selected, run)
		}
	}
	return selected
}

func featureAliases(name string) []string {
	slug := agent.Slug(name)
	switch {
	case strings.Contains(slug, "express_checkout"):
		return []string{"express checkout", "express flow"}
	case strings.Contains(slug, "group") || strings.Contains(slug, "family"):
		return []string{"group family", "group applications", "family applications"}
	case strings.Contains(slug, "status_sharing"):
		return []string{"status sharing", "sharing feature"}
	case strings.Contains(slug, "recovery"):
		return []string{"checkout recovery", "abandoned checkout", "recovery feature", "recovery"}
	case strings.Contains(slug, "forex"):
		return []string{"instant forex", "forex feature", "currency feature"}
	default:
		return []string{strings.ReplaceAll(slug, "_", " ")}
	}
}

func runsByNames(names []string, available []domain.FeatureRun) []domain.FeatureRun {
	if len(names) == 0 {
		return nil
	}
	wanted := map[string]bool{}
	for _, name := range names {
		wanted[agent.Slug(name)] = true
	}
	selected := []domain.FeatureRun{}
	for _, run := range available {
		if wanted[agent.Slug(run.Input.Name)] {
			selected = append(selected, run)
		}
	}
	return selected
}

func mergeConversationRuns(left, right []domain.FeatureRun) []domain.FeatureRun {
	seen := map[string]bool{}
	merged := make([]domain.FeatureRun, 0, len(left)+len(right))
	for _, collection := range [][]domain.FeatureRun{right, left} {
		for _, run := range collection {
			slug := agent.Slug(run.Input.Name)
			if !seen[slug] {
				seen[slug] = true
				merged = append(merged, run)
			}
		}
	}
	return merged
}

func asksForPortfolio(question string) bool {
	lower := strings.ToLower(question)
	for _, token := range []string{"all features", "all other features", "across features", "across all", "every feature", "feature portfolio", "which feature", "compare features", "best feature", "worst feature"} {
		if strings.Contains(lower, token) {
			return true
		}
	}
	return false
}

func referencesPriorScope(question string) bool {
	lower := " " + strings.ToLower(question) + " "
	for _, token := range []string{" it ", " that ", " those ", " them ", " previous ", " compare with ", " versus ", " vs "} {
		if strings.Contains(lower, token) {
			return true
		}
	}
	return false
}

func resolveFollowUpQuestion(request domain.ConversationRequest, scope []string) string {
	if !referencesPriorScope(request.Question) && !looksLikeFollowUp(request.Question) {
		return request.Question
	}
	for index := len(request.History) - 1; index >= 0; index-- {
		message := request.History[index]
		if message.Role == "user" && strings.TrimSpace(message.Content) != "" {
			return fmt.Sprintf("%s — follow-up to: %s", request.Question, message.Content)
		}
	}
	if len(scope) > 0 {
		return fmt.Sprintf("%s — continuing the %s scope", request.Question, strings.Join(scope, ", "))
	}
	return request.Question
}

func looksLikeFollowUp(question string) bool {
	lower := strings.ToLower(strings.TrimSpace(question))
	return strings.HasPrefix(lower, "what about") || strings.HasPrefix(lower, "and ") || strings.HasPrefix(lower, "now ") || strings.HasPrefix(lower, "show me") || strings.HasPrefix(lower, "break it")
}

func perFeatureQuestion(question string, scopeSize int) string {
	if scopeSize < 2 {
		return question
	}
	lower := strings.ToLower(question)
	if strings.Contains(lower, "trend") || strings.Contains(lower, "over time") || strings.Contains(lower, "drop") || strings.Contains(lower, "funnel") || strings.Contains(lower, "device") || strings.Contains(lower, "mobile") || strings.Contains(lower, " os ") || strings.Contains(lower, "segment") || strings.Contains(lower, "city") || strings.Contains(lower, "cities") || strings.Contains(lower, "country") || strings.Contains(lower, "countries") || strings.Contains(lower, "geograph") || strings.Contains(lower, "destination") {
		return question
	}
	for _, token := range []string{"completion", "conversion", "best", "highest", "lowest", "performance", "focus", "priority"} {
		if strings.Contains(lower, token) {
			return "What is the verified feature completion rate?"
		}
	}
	return question
}

func conversationContract(role, question string, graph domain.ContextVersion, results []conversationResult) domain.AnalysisContract {
	feature := results[0].run.Input.Name
	if len(results) > 1 {
		feature = "All published features"
	}
	answerability := "answerable"
	answered := 0
	for _, result := range results {
		if result.answer.Contract.Answerability != "not_answerable" {
			answered++
		}
	}
	if answered == 0 {
		answerability = "not_answerable"
	} else if answered < len(results) {
		answerability = "partially_answerable"
	}
	return domain.AnalysisContract{
		Role: role, Intent: "portfolio_conversation", Playbook: "playbook:cross-feature-conversation:v1", Answerability: answerability,
		Feature: feature, Question: question, ContextVersion: graph.Version,
		SchemaVersions:   uniqueStrings(results, func(result conversationResult) []string { return result.answer.Contract.SchemaVersions }),
		Grain:            "per-feature governed entity grain; entity identifiers are never merged across incompatible features",
		Metrics:          uniqueStrings(results, func(result conversationResult) []string { return result.answer.Contract.Metrics }),
		Guardrails:       []string{"Route only to published feature context", "Aggregate in ClickHouse before synthesis", "Never merge incompatible entity grains", "Fail closed when a required metric or dimension is not governed"},
		Dimensions:       uniqueStrings(results, func(result conversationResult) []string { return result.answer.Contract.Dimensions }),
		KnownIssues:      uniqueStrings(results, func(result conversationResult) []string { return result.answer.Contract.KnownIssues }),
		AllowedTables:    uniqueStrings(results, func(result conversationResult) []string { return result.answer.Contract.AllowedTables }),
		OperatingRules:   []string{"Resolve conversational scope before planning", "Execute one governed plan per feature", "Synthesize only aggregate evidence", "Cite source feature, context, schema, and trace"},
		RequiredEvidence: []string{"published context version", "per-feature analysis contracts", "ClickHouse aggregate evidence", "source trace IDs"},
		Limitations:      []string{"Cross-feature comparisons use each feature's governed entry, completion event, and entity grain; they do not imply a shared eligible population.", "Observed associations and completion differences do not establish causality."},
		RequestedOutputs: []string{"direct answer", "reasoning", "confidence", "recommended action", "supporting charts", "follow-up prompts", "source evidence"},
	}
}

func uniqueStrings(results []conversationResult, values func(conversationResult) []string) []string {
	seen := map[string]bool{}
	output := []string{}
	for _, result := range results {
		for _, value := range values(result) {
			if value != "" && !seen[value] {
				seen[value] = true
				output = append(output, value)
			}
		}
	}
	return output
}

func conversationEvidence(request domain.ConversationRequest, graph domain.ContextVersion, results []conversationResult) map[string]any {
	features := make([]map[string]any, 0, len(results))
	for _, result := range results {
		features = append(features, map[string]any{
			"feature": result.run.Input.Name, "schema_versions": result.answer.Contract.SchemaVersions,
			"intent": result.answer.Contract.Intent, "playbook": result.answer.Contract.Playbook,
			"answerability": result.answer.Contract.Answerability, "headline": result.answer.Insight.Headline,
			"summary": result.answer.Insight.Summary, "why": result.answer.Insight.Why,
			"confidence": result.answer.Insight.Confidence, "aggregates": compactAggregateEvidence(result.answer.Insight.Evidence),
		})
	}
	return map[string]any{
		"context_version":      graph.Version,
		"question":             request.Question,
		"conversation_history": compactHistory(request.History),
		"feature_results":      features,
	}
}

func compactAggregateEvidence(evidence map[string]any) map[string]any {
	compact := map[string]any{}
	for key, value := range evidence {
		switch rows := value.(type) {
		case []map[string]any:
			if len(rows) > 8 {
				compact[key] = rows[:8]
			} else {
				compact[key] = rows
			}
		default:
			compact[key] = value
		}
	}
	return compact
}

func deterministicConversationInsight(contract domain.AnalysisContract, results []conversationResult, evidence map[string]any, traceID string) domain.Insight {
	confidence := 1.0
	for _, result := range results {
		confidence = math.Min(confidence, result.answer.Insight.Confidence)
	}
	if len(results) == 1 {
		source := results[0].answer.Insight
		findings := source.KeyFindings
		if len(findings) == 0 {
			findings = deriveKeyFindings(results[0].run.Input.Name, source.Evidence)
		}
		return domain.Insight{
			Headline: source.Headline, Summary: source.Summary, Why: source.Why, Confidence: source.Confidence,
			RecommendedAction: source.RecommendedAction, KeyFindings: findings, Evidence: evidence, SQL: source.SQL,
			ContextVersion: contract.ContextVersion, SchemaVersion: strings.Join(contract.SchemaVersions, ", "), TraceID: traceID,
			Provenance: domain.InsightProvenance{Generator: "deterministic", Status: "ready", PromptVersion: agent.AnalyticsPromptVersion},
		}
	}

	type rateResult struct {
		feature string
		rate    float64
		entrant float64
	}
	rates := []rateResult{}
	for _, result := range results {
		if rate, entrants, ok := conversationCompletionMetric(result); ok {
			rates = append(rates, rateResult{feature: result.run.Input.Name, rate: rate, entrant: entrants})
		}
	}
	sort.SliceStable(rates, func(i, j int) bool { return rates[i].rate > rates[j].rate })
	headline := fmt.Sprintf("The Analytics Agent compiled governed evidence across %d published features", len(results))
	summary := "Each feature was routed to its own verified schema, entity grain, ClickHouse aggregate, and analysis playbook before portfolio synthesis."
	why := "The context layer prevents a single generic SQL query from mixing incompatible events or entity IDs across features."
	action := results[0].answer.Insight.RecommendedAction
	findings := make([]domain.KeyFinding, 0, 3)
	if len(rates) > 0 {
		headline = fmt.Sprintf("%s leads observed feature completion at %.1f%%", rates[0].feature, rates[0].rate*100)
		parts := make([]string, 0, len(rates))
		for _, item := range rates {
			parts = append(parts, fmt.Sprintf("%s %.1f%%", item.feature, item.rate*100))
		}
		summary = "Governed completion comparison: " + strings.Join(parts, "; ") + "."
		why = "Every percentage uses that feature's published entry event, completion event, and semantic grain. The rates are comparable as product health signals, but not as a shared eligible-user experiment."
		action = "Start with the largest high-volume completion gap, then use its funnel and segment follow-ups before prioritizing a product change."

		// Rank the portfolio into findings: the leader, the laggard with the most
		// room to move, and the spread that frames where to focus.
		best, worst := rates[0], rates[len(rates)-1]
		findings = append(findings, domain.KeyFinding{
			Point:    fmt.Sprintf("%s leads at %.1f%% completion (%.0f entrants).", best.feature, best.rate*100, best.entrant),
			Why:      "It sets the achievable bar in this portfolio; its funnel and segment structure is the reference pattern to compare weaker features against.",
			Evidence: "feature completion comparison",
			Severity: "low",
		})
		if len(rates) > 1 && best.rate-worst.rate > 0.05 {
			severity := "medium"
			if (best.rate-worst.rate) >= 0.2 && worst.entrant >= best.entrant*0.5 {
				severity = "high"
			}
			findings = append(findings, domain.KeyFinding{
				Point:    fmt.Sprintf("%s trails at %.1f%% — %.1f pp below the leader — on %.0f entrants.", worst.feature, worst.rate*100, (best.rate-worst.rate)*100, worst.entrant),
				Why:      fmt.Sprintf("This is the largest completion gap in the portfolio; with real entrant volume behind it, closing %s returns more incremental conversions than polishing the leader.", worst.feature),
				Evidence: "feature completion comparison",
				Severity: severity,
			})
		}
	}
	return domain.Insight{
		Headline: headline, Summary: summary, Why: why, Confidence: confidence, RecommendedAction: action,
		KeyFindings: findings, Evidence: evidence, SQL: joinedSourceSQL(results), ContextVersion: contract.ContextVersion,
		SchemaVersion: strings.Join(contract.SchemaVersions, ", "), TraceID: traceID,
		Provenance: domain.InsightProvenance{Generator: "deterministic", Status: "ready", PromptVersion: agent.AnalyticsPromptVersion},
	}
}

func conversationCompletionMetric(result conversationResult) (float64, float64, bool) {
	evidence := result.answer.Insight.Evidence
	for _, key := range []string{"completion_rate", "feature_completion_rate", "recovery_rate"} {
		if value, ok := finiteConversationNumber(evidence[key]); ok {
			entrants, _ := finiteConversationNumber(evidence["entrants"])
			if entrants == 0 {
				entrants, _ = finiteConversationNumber(evidence["feature_entrants"])
			}
			return value, entrants, true
		}
	}
	if result.run.AnalyticsBundle != nil {
		for _, kpi := range result.run.AnalyticsBundle.KPIs {
			if kpi.Key == "completion_rate" {
				return kpi.Value, kpi.SampleSize, true
			}
		}
	}
	return 0, 0, false
}

// conversationMode decides whether the answer should render as a full feature
// dashboard (many charts + KPI widgets) or a single focused chart with a
// description. A dashboard is requested explicitly ("dashboard", "overview"),
// implied by a broad portfolio question, or by a general "how is X doing" ask
// that does not target one specific metric.
func conversationMode(question string, results []conversationResult) string {
	lower := strings.ToLower(question)
	for _, token := range []string{"dashboard", "overview", "summary", "summarize", "full picture", "everything", "deep dive", "deep-dive", "health", "how is", "how are", "how's", "how does", "report", "at a glance", "break it down", "breakdown"} {
		if strings.Contains(lower, token) {
			return "dashboard"
		}
	}
	// A portfolio question that spans multiple features reads better as a dashboard.
	if len(results) > 1 && asksForPortfolio(question) {
		return "dashboard"
	}
	return "single"
}

func buildConversationCharts(question, mode string, results []conversationResult, traceID string) []domain.AnalyticsChart {
	if mode == "dashboard" {
		return buildDashboardCharts(results, traceID)
	}
	return buildSingleChart(question, results, traceID)
}

// buildSingleChart returns a focused set of charts for a non-dashboard answer:
// the chart that best matches the question's intent leads, followed by the rest
// of the feature's curated charts as supporting context. A PM asking about
// drop-off still sees the trend and segments that explain it, so the analysis
// reads as a coherent story rather than one isolated number. Charts are
// deduplicated and capped so the answer stays scannable.
func buildSingleChart(question string, results []conversationResult, traceID string) []domain.AnalyticsChart {
	lower := strings.ToLower(question)
	var primary *domain.AnalyticsChart
	switch {
	case strings.Contains(lower, "trend") || strings.Contains(lower, "over time") || strings.Contains(lower, "daily"):
		primary = conversationTrendChart(results, traceID)
	case strings.Contains(lower, "funnel") || strings.Contains(lower, "drop") || strings.Contains(lower, "stage"):
		primary = conversationFunnelChart(results, traceID)
	case strings.Contains(lower, "segment") || strings.Contains(lower, "device") || strings.Contains(lower, "mobile") || strings.Contains(lower, " os ") || strings.Contains(lower, "destination") || strings.Contains(lower, "city") || strings.Contains(lower, "cities") || strings.Contains(lower, "country") || strings.Contains(lower, "countries") || strings.Contains(lower, "geograph"):
		primary = conversationSegmentChart(results, traceID)
	}

	// Portfolio comparison question → lead with the cross-feature comparison.
	if primary == nil && len(results) > 1 {
		primary = portfolioCompletionChart(results, traceID)
	}

	charts := []domain.AnalyticsChart{}
	if primary != nil {
		charts = appendUniqueChart(charts, *primary)
	}
	// Add the rest of the feature's curated charts as supporting context so the
	// PM can see the surrounding story, not just the single matched chart.
	if len(results) == 1 && results[0].run.AnalyticsBundle != nil {
		for _, chart := range results[0].run.AnalyticsBundle.Charts {
			charts = appendUniqueChart(charts, chart)
		}
	}
	if len(charts) > 3 {
		charts = charts[:3]
	}
	return charts
}

// buildDashboardCharts assembles the full set of charts for a feature (or the
// whole portfolio) so the answer can render as a multi-chart dashboard.
func buildDashboardCharts(results []conversationResult, traceID string) []domain.AnalyticsChart {
	charts := []domain.AnalyticsChart{}
	if len(results) > 1 {
		if chart := portfolioCompletionChart(results, traceID); chart != nil {
			charts = appendUniqueChart(charts, *chart)
		}
		if chart := portfolioVolumeChart(results, traceID); chart != nil {
			charts = appendUniqueChart(charts, *chart)
		}
		if chart := conversationTrendChart(results, traceID); chart != nil {
			charts = appendUniqueChart(charts, *chart)
		}
		if chart := conversationFunnelChart(results, traceID); chart != nil {
			charts = appendUniqueChart(charts, *chart)
		}
		if chart := conversationSegmentChart(results, traceID); chart != nil {
			charts = appendUniqueChart(charts, *chart)
		}
	} else if len(results) == 1 && results[0].run.AnalyticsBundle != nil {
		// A single feature already has a curated bundle — surface all of it.
		for _, chart := range results[0].run.AnalyticsBundle.Charts {
			charts = appendUniqueChart(charts, chart)
		}
	}
	if len(charts) > 6 {
		charts = charts[:6]
	}
	return charts
}

// conversationKPIs surfaces headline KPI widgets for dashboard answers. Single
// feature answers reuse the feature's curated bundle KPIs; portfolio answers
// derive a compact comparison-oriented KPI row.
func conversationKPIs(mode string, results []conversationResult) []domain.AnalyticsKPI {
	if mode != "dashboard" {
		return nil
	}
	if len(results) == 1 {
		if bundle := results[0].run.AnalyticsBundle; bundle != nil {
			return decisionKPIs(bundle)
		}
		return nil
	}
	return portfolioKPIs(results)
}

// portfolioKPIs summarizes a multi-feature answer into a small KPI row: how many
// features were compared, the leader, the weakest, and the completion spread.
func portfolioKPIs(results []conversationResult) []domain.AnalyticsKPI {
	type rate struct {
		feature  string
		rate     float64
		entrants float64
	}
	rates := []rate{}
	for _, result := range results {
		if value, entrants, ok := conversationCompletionMetric(result); ok {
			rates = append(rates, rate{feature: result.run.Input.Name, rate: value, entrants: entrants})
		}
	}
	if len(rates) == 0 {
		return nil
	}
	sort.SliceStable(rates, func(i, j int) bool { return rates[i].rate > rates[j].rate })
	best, weakest := rates[0], rates[len(rates)-1]
	kpis := []domain.AnalyticsKPI{
		{Key: "features_compared", Label: "Features compared", Value: float64(len(results)), FormattedValue: fmt.Sprintf("%d", len(results)), Confidence: 1},
		{Key: "leading_feature", Label: "Leading · " + best.feature, Value: best.rate * 100, FormattedValue: fmt.Sprintf("%.1f%%", best.rate*100), Unit: "%", Confidence: 0.9, SampleSize: best.entrants},
	}
	if len(rates) > 1 {
		kpis = append(kpis,
			domain.AnalyticsKPI{Key: "trailing_feature", Label: "Trailing · " + weakest.feature, Value: weakest.rate * 100, FormattedValue: fmt.Sprintf("%.1f%%", weakest.rate*100), Unit: "%", Confidence: 0.9, SampleSize: weakest.entrants},
			domain.AnalyticsKPI{Key: "completion_spread", Label: "Completion spread", Value: (best.rate - weakest.rate) * 100, FormattedValue: fmt.Sprintf("+%.1f pp", (best.rate-weakest.rate)*100), Confidence: 0.88},
		)
	}
	if len(kpis) > 4 {
		kpis = kpis[:4]
	}
	return kpis
}

// decisionKPIs picks the four most decision-relevant KPIs from a feature bundle,
// mirroring the release view's KPI selection so answers stay consistent with it.
func decisionKPIs(bundle *domain.FeatureAnalyticsBundle) []domain.AnalyticsKPI {
	generic := map[string]bool{"entrants": true, "completions": true, "completion_rate": true, "best_segment": true}
	selected := []domain.AnalyticsKPI{}
	for _, kpi := range bundle.KPIs {
		if !generic[kpi.Key] {
			selected = append(selected, kpi)
		}
	}
	has := func(key string) bool {
		for _, kpi := range selected {
			if kpi.Key == key {
				return true
			}
		}
		return false
	}
	for _, kpi := range bundle.KPIs {
		if kpi.Key == "completion_rate" && !has(kpi.Key) {
			end := kpi
			end.Label = "End-to-end completion"
			selected = append([]domain.AnalyticsKPI{end}, selected...)
		}
	}
	if len(selected) > 4 {
		selected = selected[:4]
	}
	return selected
}

func appendUniqueChart(charts []domain.AnalyticsChart, chart domain.AnalyticsChart) []domain.AnalyticsChart {
	for _, existing := range charts {
		if existing.Key == chart.Key {
			return charts
		}
	}
	return append(charts, chart)
}

func portfolioCompletionChart(results []conversationResult, traceID string) *domain.AnalyticsChart {
	points := []domain.AnalyticsPoint{}
	for _, result := range results {
		if rate, entrants, ok := conversationCompletionMetric(result); ok {
			points = append(points, domain.AnalyticsPoint{Label: result.run.Input.Name, Value: rate * 100, SampleSize: entrants})
		}
	}
	if len(points) == 0 {
		return nil
	}
	sort.SliceStable(points, func(i, j int) bool { return points[i].Value > points[j].Value })
	return &domain.AnalyticsChart{Key: "portfolio_completion", Type: "comparison", Title: "Feature completion comparison", Subtitle: "Each feature uses its governed entry, completion event, and entity grain", Unit: "%", Series: []domain.AnalyticsSeries{{Key: "completion_rate", Label: "Completion rate", Points: points}}, SQL: joinedSourceSQL(results), TraceID: traceID}
}

func portfolioVolumeChart(results []conversationResult, traceID string) *domain.AnalyticsChart {
	points := []domain.AnalyticsPoint{}
	for _, result := range results {
		_, entrants, ok := conversationCompletionMetric(result)
		if ok && entrants > 0 {
			points = append(points, domain.AnalyticsPoint{Label: result.run.Input.Name, Value: entrants, SampleSize: entrants})
		}
	}
	if len(points) == 0 {
		return nil
	}
	sort.SliceStable(points, func(i, j int) bool { return points[i].Value > points[j].Value })
	return &domain.AnalyticsChart{Key: "portfolio_volume", Type: "comparison", Title: "Observed feature entrants", Subtitle: "Unique governed entrants in each feature observation window", Unit: "entities", Series: []domain.AnalyticsSeries{{Key: "entrants", Label: "Entrants", Points: points}}, SQL: joinedSourceSQL(results), TraceID: traceID}
}

func conversationTrendChart(results []conversationResult, traceID string) *domain.AnalyticsChart {
	series := []domain.AnalyticsSeries{}
	for _, result := range results {
		rows := evidenceRows(result.answer.Insight.Evidence["trend_series"])
		if len(rows) == 0 {
			rows = evidenceRows(result.answer.Insight.Evidence["daily_series"])
		}
		if len(rows) == 0 && result.run.AnalyticsBundle != nil {
			if chart := bundleChart(result.run.AnalyticsBundle, "completion_trend"); chart != nil && len(chart.Series) > 0 {
				series = append(series, domain.AnalyticsSeries{Key: agent.Slug(result.run.Input.Name), Label: result.run.Input.Name, Points: chart.Series[0].Points})
				continue
			}
		}
		points := []domain.AnalyticsPoint{}
		for _, row := range rows {
			value, _ := finiteConversationNumber(row["completion_rate"])
			entrants, _ := finiteConversationNumber(row["entrants"])
			points = append(points, domain.AnalyticsPoint{Label: fmt.Sprint(row["date"]), Value: value * 100, SampleSize: entrants})
		}
		if len(points) > 0 {
			series = append(series, domain.AnalyticsSeries{Key: agent.Slug(result.run.Input.Name), Label: result.run.Input.Name, Points: points})
		}
	}
	if len(series) == 0 {
		return nil
	}
	return &domain.AnalyticsChart{Key: "conversation_trend", Type: "trend", Title: "Completion trend", Subtitle: "Governed completion rate by reporting period; switch feature to inspect its series", Unit: "%", Series: series, SQL: joinedSourceSQL(results), TraceID: traceID}
}

func conversationSegmentChart(results []conversationResult, traceID string) *domain.AnalyticsChart {
	series := []domain.AnalyticsSeries{}
	for _, result := range results {
		rows := evidenceRows(result.answer.Insight.Evidence["segments"])
		if len(rows) == 0 && result.run.AnalyticsBundle != nil {
			if chart := bundleChart(result.run.AnalyticsBundle, "segment_completion"); chart != nil {
				for _, item := range chart.Series {
					series = append(series, domain.AnalyticsSeries{Key: agent.Slug(result.run.Input.Name) + "-" + item.Key, Label: result.run.Input.Name + " · " + item.Label, Points: item.Points})
				}
				continue
			}
		}
		grouped := map[string][]domain.AnalyticsPoint{}
		order := []string{}
		for _, row := range rows {
			dimension := fmt.Sprint(row["dimension"])
			if _, ok := grouped[dimension]; !ok {
				order = append(order, dimension)
			}
			rate, ok := finiteConversationNumber(row["completion_rate"])
			if !ok {
				rate, ok = finiteConversationNumber(row["rate"])
			}
			if !ok {
				continue
			}
			entrants, _ := finiteConversationNumber(row["entrants"])
			grouped[dimension] = append(grouped[dimension], domain.AnalyticsPoint{Label: fmt.Sprint(row["segment"]), Value: rate * 100, SampleSize: entrants})
		}
		for _, dimension := range order {
			series = append(series, domain.AnalyticsSeries{Key: agent.Slug(result.run.Input.Name) + "-" + dimension, Label: result.run.Input.Name + " · " + strings.ReplaceAll(dimension, "_", " "), Points: grouped[dimension]})
		}
	}
	if len(series) == 0 {
		return nil
	}
	return &domain.AnalyticsChart{Key: "conversation_segments", Type: "segments", Title: "Segment completion", Subtitle: "Qualified cohorts from the governed entrant dimension", Unit: "%", Series: series, SQL: joinedSourceSQL(results), TraceID: traceID}
}

func conversationFunnelChart(results []conversationResult, traceID string) *domain.AnalyticsChart {
	series := []domain.AnalyticsSeries{}
	for _, result := range results {
		rows := evidenceRows(result.answer.Insight.Evidence["stages"])
		if len(rows) == 0 && result.run.AnalyticsBundle != nil {
			if chart := bundleChart(result.run.AnalyticsBundle, "feature_funnel"); chart != nil && len(chart.Series) > 0 {
				series = append(series, domain.AnalyticsSeries{Key: agent.Slug(result.run.Input.Name), Label: result.run.Input.Name, Points: chart.Series[0].Points})
				continue
			}
		}
		points := []domain.AnalyticsPoint{}
		for _, row := range rows {
			entities, ok := finiteConversationNumber(row["entities"])
			if ok {
				points = append(points, domain.AnalyticsPoint{Label: fmt.Sprint(row["stage"]), Value: entities, SampleSize: entities})
			}
		}
		if len(points) > 0 {
			series = append(series, domain.AnalyticsSeries{Key: agent.Slug(result.run.Input.Name), Label: result.run.Input.Name, Points: points})
		}
	}
	if len(series) == 0 {
		return nil
	}
	return &domain.AnalyticsChart{Key: "conversation_funnel", Type: "funnel", Title: "Governed feature funnel", Subtitle: "Unique entities reaching each verified stage; switch feature to inspect", Unit: "entities", Series: series, SQL: joinedSourceSQL(results), TraceID: traceID}
}

func bundleChart(bundle *domain.FeatureAnalyticsBundle, key string) *domain.AnalyticsChart {
	for index := range bundle.Charts {
		if bundle.Charts[index].Key == key {
			return &bundle.Charts[index]
		}
	}
	return nil
}

func evidenceRows(value any) []map[string]any {
	rows, _ := value.([]map[string]any)
	return rows
}

// deriveKeyFindings turns the governed aggregate evidence into a small ranked
// list of grounded findings so a deterministic (non-LLM) answer still gives the
// PM more than a single headline. Each finding is anchored to a real number:
// the largest funnel drop, the widest segment gap, and the headline completion
// rate. Findings that cannot be grounded in the evidence are simply not emitted.
func deriveKeyFindings(feature string, evidence map[string]any) []domain.KeyFinding {
	findings := make([]domain.KeyFinding, 0, 3)
	prefix := ""
	if feature != "" {
		prefix = feature + " "
	}

	// Largest funnel drop-off — the stage where the most entities are lost.
	if stages := evidenceRows(evidence["stages"]); len(stages) > 1 {
		worstDrop, worstStage, prevStage := 0.0, "", ""
		var lostAt, enteredAt float64
		for i := 1; i < len(stages); i++ {
			prev, okPrev := finiteConversationNumber(stages[i-1]["entities"])
			cur, okCur := finiteConversationNumber(stages[i]["entities"])
			if !okPrev || !okCur || prev <= 0 {
				continue
			}
			drop := (prev - cur) / prev
			if drop > worstDrop {
				worstDrop, lostAt, enteredAt = drop, prev-cur, prev
				worstStage = humanEvidenceLabel(fmt.Sprint(stages[i]["stage"]))
				prevStage = humanEvidenceLabel(fmt.Sprint(stages[i-1]["stage"]))
			}
		}
		if worstStage != "" && worstDrop > 0 {
			severity := "medium"
			if worstDrop >= 0.4 {
				severity = "high"
			} else if worstDrop < 0.15 {
				severity = "low"
			}
			findings = append(findings, domain.KeyFinding{
				Point:    fmt.Sprintf("The largest drop-off is at %q: %.0f%% of the %.0f entities from %q do not advance (%.0f lost).", worstStage, worstDrop*100, enteredAt, prevStage, lostAt),
				Why:      fmt.Sprintf("This is the single biggest recoverable pool of %sconversion — fixing this step moves the completion rate more than any other change, and every entity lost here has already shown intent by reaching %q.", prefix, prevStage),
				Evidence: fmt.Sprintf("funnel stage transition %s → %s", prevStage, worstStage),
				Severity: severity,
			})
		}
	}

	// Widest segment gap — the cohort that under-converts relative to the best.
	if segments := evidenceRows(evidence["segments"]); len(segments) > 1 {
		best, weakest := metricExtremes(segments, "completion_rate")
		bestRate, okB := finiteConversationNumber(best["completion_rate"])
		weakRate, okW := finiteConversationNumber(weakest["completion_rate"])
		if okB && okW && bestRate-weakRate > 0.05 {
			dimension := humanEvidenceLabel(fmt.Sprint(weakest["dimension"]))
			weakSeg := humanEvidenceLabel(fmt.Sprint(weakest["segment"]))
			bestSeg := humanEvidenceLabel(fmt.Sprint(best["segment"]))
			gap := (bestRate - weakRate) * 100
			severity := "medium"
			if gap >= 20 {
				severity = "high"
			}
			findings = append(findings, domain.KeyFinding{
				Point:    fmt.Sprintf("By %s, %q completes at %.1f%% versus %.1f%% for %q — a %.1f pp gap.", dimension, weakSeg, weakRate*100, bestRate*100, bestSeg, gap),
				Why:      fmt.Sprintf("A gap this size means the %sexperience is not landing evenly; closing %q toward the %q cohort is a targeted lever the PM can own without a full-funnel rebuild.", prefix, weakSeg, bestSeg),
				Evidence: fmt.Sprintf("segment completion by %s", dimension),
				Severity: severity,
			})
		}
	}

	// Headline completion rate — the top-line health signal for the release.
	for _, key := range []string{"completion_rate", "feature_completion_rate", "recovery_rate"} {
		if rate, ok := finiteConversationNumber(evidence[key]); ok {
			entrants, _ := finiteConversationNumber(evidence["entrants"])
			if entrants == 0 {
				entrants, _ = finiteConversationNumber(evidence["feature_entrants"])
			}
			sample := ""
			if entrants > 0 {
				sample = fmt.Sprintf(" across %.0f governed entrants", entrants)
			}
			findings = append(findings, domain.KeyFinding{
				Point:    fmt.Sprintf("Overall completion sits at %.1f%%%s.", rate*100, sample),
				Why:      fmt.Sprintf("This is the top-line signal for whether the %srelease is working; it frames how urgent the drop-off and segment gaps above are and sets the baseline any change is measured against.", prefix),
				Evidence: humanEvidenceLabel(key),
				Severity: "low",
			})
			break
		}
	}

	if len(findings) > 4 {
		findings = findings[:4]
	}
	return findings
}

func finiteConversationNumber(value any) (float64, bool) {
	var number float64
	switch typed := value.(type) {
	case float64:
		number = typed
	case float32:
		number = float64(typed)
	case int:
		number = float64(typed)
	case int64:
		number = float64(typed)
	case json.Number:
		parsed, err := typed.Float64()
		if err != nil {
			return 0, false
		}
		number = parsed
	default:
		return 0, false
	}
	return number, !math.IsNaN(number) && !math.IsInf(number, 0)
}

func joinedSourceSQL(results []conversationResult) string {
	queries := []string{}
	for _, result := range results {
		if strings.TrimSpace(result.answer.Insight.SQL) != "" {
			queries = append(queries, "-- "+result.run.Input.Name+"\n"+result.answer.Insight.SQL)
		}
	}
	return strings.Join(queries, "\n\n")
}

func conversationDatasetRows(results []conversationResult) int {
	total := 0
	for _, result := range results {
		total += result.run.Profile.Rows
	}
	return total
}

func compactHistory(history []domain.ConversationMessage) []domain.ConversationMessage {
	if len(history) > 6 {
		return history[len(history)-6:]
	}
	return history
}

func conversationRoutingOutput(results []conversationResult) []map[string]any {
	output := make([]map[string]any, 0, len(results))
	for _, result := range results {
		output = append(output, map[string]any{"feature": result.run.Input.Name, "playbook": result.answer.Contract.Playbook, "intent": result.answer.Contract.Intent, "answerability": result.answer.Contract.Answerability, "allowed_tables": result.answer.Contract.AllowedTables})
	}
	return output
}

func conversationSourceTrace(results []conversationResult) []map[string]any {
	output := make([]map[string]any, 0, len(results))
	for _, result := range results {
		output = append(output, map[string]any{"feature": result.run.Input.Name, "trace_id": result.answer.Insight.TraceID, "sql": result.answer.Insight.SQL, "aggregate_evidence": compactAggregateEvidence(result.answer.Insight.Evidence), "headline": result.answer.Insight.Headline})
	}
	return output
}

func chartKeys(charts []domain.AnalyticsChart) []string {
	keys := make([]string, 0, len(charts))
	for _, chart := range charts {
		keys = append(keys, chart.Key)
	}
	return keys
}

func featureNames(runs []domain.FeatureRun) []string {
	names := make([]string, 0, len(runs))
	for _, run := range runs {
		names = append(names, run.Input.Name)
	}
	return names
}

func normalizeConversationText(value string) string {
	return strings.Join(strings.Fields(strings.NewReplacer("/", " ", "_", " ", "-", " ").Replace(strings.ToLower(value))), " ")
}

func conversationFollowUps(question string, scope []string, results []conversationResult) []string {
	if len(results) == 1 {
		result := results[0]
		feature := result.run.Input.Name
		evidence := result.answer.Insight.Evidence
		switch result.answer.Contract.Intent {
		case "segment_comparison":
			rows := evidenceRows(evidence["segments"])
			if len(rows) > 0 {
				best, weakest := metricExtremes(rows, "completion_rate")
				dimension := humanEvidenceLabel(fmt.Sprint(best["dimension"]))
				return []string{
					fmt.Sprintf("Compare %s completion by %s; how large is the gap between %s and %s?", feature, dimension, humanEvidenceLabel(fmt.Sprint(weakest["segment"])), humanEvidenceLabel(fmt.Sprint(best["segment"]))),
					fmt.Sprintf("Where is the largest funnel loss for %s?", feature),
					fmt.Sprintf("Show the weekly completion trend for %s.", feature),
				}
			}
		case "platform_failure":
			row := evidenceRow(evidence["worst_segment"])
			segmentParts := []string{}
			for _, value := range []any{row["device_type"], row["os"]} {
				label := fmt.Sprint(value)
				if label != "" && label != "<nil>" {
					segmentParts = append(segmentParts, label)
				}
			}
			segment := strings.Join(segmentParts, " / ")
			return []string{
				fmt.Sprintf("Compare OTP success by device and OS for %s; is %s still the weakest cohort?", feature, segment),
				fmt.Sprintf("Compare confirmation after OTP across device and OS for %s.", feature),
				fmt.Sprintf("Where is the largest end-to-end funnel loss for %s?", feature),
			}
		case "completion_trend":
			rows := evidenceRows(evidence["trend_series"])
			if len(rows) == 0 {
				rows = evidenceRows(evidence["daily_series"])
			}
			period := "latest reporting period"
			if len(rows) > 0 {
				period = fmt.Sprint(rows[len(rows)-1]["date"])
			}
			return []string{
				fmt.Sprintf("Which device or OS cohort is the largest opportunity for %s after %s?", feature, period),
				fmt.Sprintf("Where is the largest funnel loss for %s?", feature),
				fmt.Sprintf("Compare %s completion with every published feature.", feature),
			}
		case "recovery_channel":
			row := evidenceRow(evidence["best_channel"])
			return []string{
				fmt.Sprintf("Compare recovery rates across channels; how far ahead is %s?", humanEvidenceLabel(fmt.Sprint(row["channel"]))),
				"Which reminder timing has the strongest observed recovery?",
				"Which drop step is the largest recoverable opportunity?",
			}
		case "recovery_timing":
			row := evidenceRow(evidence["best_timing"])
			return []string{
				fmt.Sprintf("Compare every recovery timing cohort; does the %.0f-hour window remain strongest?", conversationNumber(row["hours_since_drop"])),
				"Which recovery channel performs best?",
				"Which device or geography segment contributes the most recoveries?",
			}
		case "group_size_completion":
			rows := evidenceRows(evidence["segments"])
			if len(rows) > 0 {
				best, weakest := metricExtremes(rows, "completion_rate")
				return []string{
					fmt.Sprintf("Compare completion by group size; how large is the gap between size %s and size %s?", fmt.Sprint(weakest["group_size"]), fmt.Sprint(best["group_size"])),
					"Which group sizes have the largest document-completion bottleneck?",
					fmt.Sprintf("Where is the largest funnel loss for %s?", feature),
				}
			}
		}
		return []string{
			fmt.Sprintf("Where is the largest funnel loss for %s?", feature),
			fmt.Sprintf("Which device or OS cohort is the largest opportunity for %s?", feature),
			fmt.Sprintf("Show the weekly completion trend for %s.", feature),
		}
	}

	type completionResult struct {
		feature string
		rate    float64
	}
	rates := make([]completionResult, 0, len(results))
	for _, result := range results {
		if rate, _, ok := conversationCompletionMetric(result); ok {
			rates = append(rates, completionResult{feature: result.run.Input.Name, rate: rate})
		}
	}
	sort.SliceStable(rates, func(i, j int) bool { return rates[i].rate > rates[j].rate })
	if len(rates) >= 2 {
		best, weakest := rates[0], rates[len(rates)-1]
		return []string{
			fmt.Sprintf("Compare the funnel stages for %s and %s.", weakest.feature, best.feature),
			fmt.Sprintf("Compare weekly completion trends for %s and %s.", weakest.feature, best.feature),
			fmt.Sprintf("Which device or OS cohorts create the largest gap between %s and %s?", weakest.feature, best.feature),
		}
	}
	return []string{"Which published feature has the largest funnel loss?", "Compare weekly completion trends across published features.", "Which device or OS cohort is the largest opportunity?"}
}

func metricExtremes(rows []map[string]any, metric string) (best, weakest map[string]any) {
	best, weakest = rows[0], rows[0]
	for _, row := range rows[1:] {
		if conversationNumber(row[metric]) > conversationNumber(best[metric]) {
			best = row
		}
		if conversationNumber(row[metric]) < conversationNumber(weakest[metric]) {
			weakest = row
		}
	}
	return best, weakest
}

func evidenceRow(value any) map[string]any {
	row, _ := value.(map[string]any)
	return row
}

func conversationNumber(value any) float64 {
	number, _ := finiteConversationNumber(value)
	return number
}

func humanEvidenceLabel(value string) string {
	return strings.TrimSpace(strings.ReplaceAll(value, "_", " "))
}
