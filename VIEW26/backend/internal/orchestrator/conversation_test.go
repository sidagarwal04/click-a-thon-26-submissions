package orchestrator

import (
	"context"
	"strings"
	"testing"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/clickhouse"
	"github.com/view26/featurelens/internal/domain"
	"github.com/view26/featurelens/internal/store"
	"go.opentelemetry.io/otel"
)

func TestConversationRoutingUsesPortfolioMentionsAndFollowUpScope(t *testing.T) {
	available := []domain.FeatureRun{
		{Input: domain.FeatureInput{Name: "Express Checkout"}},
		{Input: domain.FeatureInput{Name: "Group / Family"}},
		{Input: domain.FeatureInput{Name: "Abandoned Checkout Recovery"}},
		{Input: domain.FeatureInput{Name: "Instant Forex"}},
	}

	portfolio := resolveConversationRuns(domain.ConversationRequest{Question: "Which feature has the highest completion rate?"}, available)
	if len(portfolio) != len(available) {
		t.Fatalf("portfolio question should route across all features, got %v", featureNames(portfolio))
	}

	express := resolveConversationRuns(domain.ConversationRequest{Question: "How is Express Checkout doing?"}, available)
	if len(express) != 1 || express[0].Input.Name != "Express Checkout" {
		t.Fatalf("explicit feature mention was not isolated: %v", featureNames(express))
	}

	followUp := resolveConversationRuns(domain.ConversationRequest{
		Question:       "Compare it with recovery",
		ActiveFeatures: []string{"Express Checkout"},
	}, available)
	if len(followUp) != 2 || followUp[0].Input.Name != "Express Checkout" || followUp[1].Input.Name != "Abandoned Checkout Recovery" {
		t.Fatalf("follow-up did not preserve the prior scope and add the named feature: %v", featureNames(followUp))
	}
}

func TestConversationFollowUpResolutionCarriesPriorQuestion(t *testing.T) {
	request := domain.ConversationRequest{
		Question: "What about by device?",
		History:  []domain.ConversationMessage{{Role: "user", Content: "How is Express Checkout doing?", FeatureScope: []string{"Express Checkout"}}},
	}
	resolved := resolveFollowUpQuestion(request, []string{"Express Checkout"})
	if resolved == request.Question {
		t.Fatalf("expected prior conversational context in resolved question, got %q", resolved)
	}
}

func TestConverseBuildsPortfolioAnswerChartsAndTrace(t *testing.T) {
	baseline := agent.BaselineContext()
	graph := baseline
	graph.Version = 1
	graph.ParentVersion = baseline.Version
	graph.Nodes = append(graph.Nodes,
		domain.ContextNode{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout"},
		domain.ContextNode{Key: "feature:instant_forex", Type: "feature", Name: "Instant Forex"},
	)
	memory := store.NewMemory(baseline)
	if err := memory.PublishContext(graph); err != nil {
		t.Fatal(err)
	}
	for index, fixture := range []struct {
		name string
		rate float64
	}{
		{name: "Express Checkout", rate: .62},
		{name: "Instant Forex", rate: .31},
	} {
		profile := domain.EventProfile{Rows: 100 + index, EventOrder: []string{"shown", "completed"}, Fields: []domain.FieldProfile{{ColumnName: "application_id"}}}
		schema := domain.SchemaProposal{Database: "featurelens", Table: agent.Slug(fixture.name) + "_events_v1", Version: 1}
		bundle := domain.FeatureAnalyticsBundle{KPIs: []domain.AnalyticsKPI{{Key: "completion_rate", Value: fixture.rate, SampleSize: 100}}}
		memory.CreateRun(domain.FeatureRun{
			ID: fixture.name, Input: domain.FeatureInput{Name: fixture.name}, Stage: domain.StageCompleted,
			Profile: &profile, Schema: &schema, Context: &graph, AnalyticsBundle: &bundle,
		})
	}
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("conversation-test"), "featurelens")
	response, err := engine.Converse(context.Background(), domain.ConversationRequest{Role: "product_manager", Question: "Which feature has the highest completion rate?"})
	if err != nil {
		t.Fatal(err)
	}
	if len(response.FeatureScope) != 2 || len(response.Sources) != 2 || len(response.Charts) == 0 {
		t.Fatalf("portfolio answer is incomplete: scope=%v sources=%d charts=%d", response.FeatureScope, len(response.Sources), len(response.Charts))
	}
	if response.Insight.Trace == nil || response.Contract.Playbook != "playbook:cross-feature-conversation:v1" || len(response.FollowUpPrompts) != 3 {
		t.Fatalf("conversation provenance or follow-ups are missing: %#v", response)
	}
}

func TestCityQuestionBuildsDimensionChart(t *testing.T) {
	results := []conversationResult{{
		run: domain.FeatureRun{Input: domain.FeatureInput{Name: "Express Checkout"}},
		answer: domain.QuestionResponse{
			Contract: domain.AnalysisContract{Intent: "segment_comparison", Dimensions: []string{"city"}},
			Insight: domain.Insight{Evidence: map[string]any{"segments": []map[string]any{
				{"dimension": "city", "segment": "Sydney", "entrants": 81.0, "completions": 50.0, "completion_rate": .6173},
				{"dimension": "city", "segment": "Dubai", "entrants": 153.0, "completions": 70.0, "completion_rate": .4575},
			}}},
		},
	}}
	question := "Which Cities have most express checkout rate?"
	charts := buildConversationCharts(question, conversationMode(question, results), results, "trace-city")
	if len(charts) != 1 || charts[0].Key != "conversation_segments" || len(charts[0].Series) != 1 || charts[0].Series[0].Label != "Express Checkout · city" {
		t.Fatalf("city question did not produce its governed segment chart: %#v", charts)
	}
}

func TestConversationModeSelectsDashboardOrSingle(t *testing.T) {
	single := []conversationResult{{run: domain.FeatureRun{Input: domain.FeatureInput{Name: "Express Checkout"}}}}
	portfolio := []conversationResult{
		{run: domain.FeatureRun{Input: domain.FeatureInput{Name: "Express Checkout"}}},
		{run: domain.FeatureRun{Input: domain.FeatureInput{Name: "Instant Forex"}}},
	}
	cases := []struct {
		question string
		results  []conversationResult
		want     string
	}{
		{"Show me the Express Checkout dashboard", single, "dashboard"},
		{"How is Express Checkout doing?", single, "dashboard"},
		{"Give me an overview of every feature", portfolio, "dashboard"},
		{"Which cities have the strongest completion?", single, "single"},
		{"Where is the largest funnel loss?", single, "single"},
	}
	for _, tc := range cases {
		if got := conversationMode(tc.question, tc.results); got != tc.want {
			t.Errorf("conversationMode(%q) = %q, want %q", tc.question, got, tc.want)
		}
	}
}

func TestDashboardModeSurfacesBundleChartsAndKPIs(t *testing.T) {
	bundle := &domain.FeatureAnalyticsBundle{
		Charts: []domain.AnalyticsChart{
			{Key: "feature_funnel", Type: "funnel", Series: []domain.AnalyticsSeries{{Key: "s", Points: []domain.AnalyticsPoint{{Label: "entry", Value: 100}}}}},
			{Key: "completion_trend", Type: "trend", Series: []domain.AnalyticsSeries{{Key: "s", Points: []domain.AnalyticsPoint{{Label: "2026-01-01", Value: 50}}}}},
			{Key: "segment_completion", Type: "segments", Series: []domain.AnalyticsSeries{{Key: "s", Points: []domain.AnalyticsPoint{{Label: "ios", Value: 60}}}}},
		},
		KPIs: []domain.AnalyticsKPI{
			{Key: "completion_rate", Label: "Completion", FormattedValue: "48%", Confidence: 1},
			{Key: "otp_success", Label: "OTP success", FormattedValue: "92%", Confidence: .9},
		},
	}
	results := []conversationResult{{run: domain.FeatureRun{Input: domain.FeatureInput{Name: "Express Checkout"}, AnalyticsBundle: bundle}}}

	charts := buildConversationCharts("Show me the Express Checkout dashboard", "dashboard", results, "trace-dash")
	if len(charts) != 3 {
		t.Fatalf("dashboard mode should surface all bundle charts, got %d", len(charts))
	}
	kpis := conversationKPIs("dashboard", results)
	if len(kpis) == 0 {
		t.Fatalf("dashboard mode should surface KPI widgets")
	}

	// Single mode leads with the intent-matched chart (the funnel, for a
	// drop-off question) then appends the feature's other curated charts as
	// supporting context so the answer tells a coherent story.
	single := buildConversationCharts("Where is the largest funnel loss?", "single", results, "trace-single")
	if len(single) == 0 || single[0].Type != "funnel" {
		t.Fatalf("single mode should lead with the funnel chart, got %#v", single)
	}
	if len(single) != 3 {
		t.Fatalf("single mode should append supporting context charts, got %d", len(single))
	}
	if kpis := conversationKPIs("single", results); kpis != nil {
		t.Fatalf("single mode should not surface KPI widgets, got %#v", kpis)
	}
}

func TestDeriveKeyFindingsGroundsInEvidence(t *testing.T) {
	evidence := map[string]any{
		"completion_rate": .48,
		"entrants":        1000.0,
		"stages": []map[string]any{
			{"stage": "shown", "entities": 1000.0},
			{"stage": "otp_sent", "entities": 900.0},
			{"stage": "completed", "entities": 480.0},
		},
		"segments": []map[string]any{
			{"dimension": "device", "segment": "ios", "completion_rate": .62},
			{"dimension": "device", "segment": "android", "completion_rate": .34},
		},
	}
	findings := deriveKeyFindings("Express Checkout", evidence)
	if len(findings) != 3 {
		t.Fatalf("expected funnel, segment, and completion findings, got %d: %#v", len(findings), findings)
	}
	// Largest drop is otp_sent -> completed (900 -> 480, ~47%), ranked first and high severity.
	if !strings.Contains(findings[0].Point, "completed") || findings[0].Severity != "high" {
		t.Fatalf("first finding should be the largest funnel drop at high severity: %#v", findings[0])
	}
	// The device gap (62% vs 34% = 28pp) should be flagged high and name both cohorts.
	if !strings.Contains(findings[1].Point, "android") || !strings.Contains(findings[1].Point, "ios") || findings[1].Severity != "high" {
		t.Fatalf("second finding should be the device segment gap: %#v", findings[1])
	}
	for _, finding := range findings {
		if strings.TrimSpace(finding.Why) == "" || strings.TrimSpace(finding.Evidence) == "" {
			t.Fatalf("every finding must carry a why and an evidence anchor: %#v", finding)
		}
	}
}

func TestConversationFollowUpsUseReturnedEvidence(t *testing.T) {
	results := []conversationResult{{
		run: domain.FeatureRun{Input: domain.FeatureInput{Name: "Express Checkout"}},
		answer: domain.QuestionResponse{
			Contract: domain.AnalysisContract{Intent: "segment_comparison", Dimensions: []string{"city"}},
			Insight: domain.Insight{Evidence: map[string]any{"segments": []map[string]any{
				{"dimension": "city", "segment": "Sydney", "completion_rate": .6173},
				{"dimension": "city", "segment": "Dubai", "completion_rate": .4575},
			}}},
		},
	}}
	prompts := conversationFollowUps("Which cities perform best?", []string{"Express Checkout"}, results)
	if len(prompts) != 3 || !strings.Contains(prompts[0], "Dubai") || !strings.Contains(prompts[0], "Sydney") || !strings.Contains(prompts[0], "city") {
		t.Fatalf("follow-ups were not grounded in returned segment evidence: %#v", prompts)
	}
}
