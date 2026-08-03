package agent

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

type synthesisTestReader struct{}

func (synthesisTestReader) Enabled() bool          { return true }
func (synthesisTestReader) SourceDatabase() string { return "atlys" }
func (synthesisTestReader) QueryJSON(context.Context, string) ([]map[string]any, error) {
	return []map[string]any{{"entrants": 100.0, "completions": 60.0, "completion_rate": .6}}, nil
}

type synthesisTestClient struct{ fail bool }

func (s synthesisTestClient) Enabled() bool { return true }
func (s synthesisTestClient) Metadata() domain.InsightProvenance {
	return domain.InsightProvenance{Provider: "test", Model: "test-model", PromptVersion: AnalyticsPromptVersion}
}
func (s synthesisTestClient) Synthesize(_ context.Context, input InsightSynthesisRequest) (InsightSynthesis, error) {
	if s.fail {
		return InsightSynthesis{}, errors.New("provider unavailable")
	}
	if input.Contract.ContextVersion != 1 || input.Evidence["completion_rate"] != .6 {
		return InsightSynthesis{}, errors.New("missing governed input")
	}
	return InsightSynthesis{
		Headline: "LLM headline", Summary: "LLM summary", Why: "Evidence-backed why",
		Confidence: .99, RecommendedAction: "Run the next product test.",
	}, nil
}

func TestAnalyticsAgentUsesLLMButPreservesGovernedEvidence(t *testing.T) {
	agent := AnalyticsAgent{Reader: synthesisTestReader{}, Synthesizer: synthesisTestClient{}}
	contract, insight := agent.Analyze(context.Background(), "product_manager", "How is completion?", synthesisFixtureInput(), synthesisFixtureProfile(), synthesisFixtureSchema(), synthesisFixtureContext(), "trace-test")
	if contract.Playbook != "playbook:feature-completion:v1" {
		t.Fatalf("unexpected playbook %s", contract.Playbook)
	}
	if insight.Headline != "LLM headline" || insight.Provenance.Generator != "llm" {
		t.Fatalf("LLM synthesis not applied: %#v", insight)
	}
	if insight.Evidence["completion_rate"] != .6 || insight.SQL == "" {
		t.Fatal("governed evidence or SQL was replaced")
	}
	if insight.Confidence != .9 {
		t.Fatalf("LLM confidence should be capped at deterministic confidence, got %v", insight.Confidence)
	}
	if insight.Trace == nil || traceStepStatus(insight.Trace, "tool.clickhouse.query") != "completed" || traceStepStatus(insight.Trace, "llm.synthesize") != "completed" {
		t.Fatalf("expected completed ClickHouse and LLM trace steps, got %#v", insight.Trace)
	}
	if _, err := json.Marshal(insight); err != nil {
		t.Fatalf("analysis trace must remain serializable: %v", err)
	}
}

type countingReader struct{ calls int }

func (reader *countingReader) Enabled() bool          { return true }
func (reader *countingReader) SourceDatabase() string { return "atlys" }
func (reader *countingReader) QueryJSON(context.Context, string) ([]map[string]any, error) {
	reader.calls++
	return []map[string]any{{"entrants": 999.0}}, nil
}

type countingSynthesizer struct{ calls int }

func (synthesizer *countingSynthesizer) Enabled() bool { return true }
func (synthesizer *countingSynthesizer) Metadata() domain.InsightProvenance {
	return domain.InsightProvenance{Provider: "test", Model: "test-model", PromptVersion: AnalyticsPromptVersion}
}
func (synthesizer *countingSynthesizer) Synthesize(context.Context, InsightSynthesisRequest) (InsightSynthesis, error) {
	synthesizer.calls++
	return InsightSynthesis{}, errors.New("must not be called")
}

func TestCustomerGeographyFailsClosedBeforeQueryOrSynthesis(t *testing.T) {
	reader := &countingReader{}
	synthesizer := &countingSynthesizer{}
	analytics := AnalyticsAgent{Reader: reader, Synthesizer: synthesizer}
	contract, insight := analytics.Analyze(context.Background(), "product_manager", "How many customers do we have from Dubai?", synthesisFixtureInput(), synthesisFixtureProfile(), synthesisFixtureSchema(), synthesisFixtureContext(), "trace-dubai")

	if contract.Intent != "customer_geography" || contract.Answerability != "not_answerable" {
		t.Fatalf("expected a rejected customer-geography contract, got %#v", contract)
	}
	if reader.calls != 0 || synthesizer.calls != 0 {
		t.Fatalf("rejected question executed downstream systems: reader=%d synthesizer=%d", reader.calls, synthesizer.calls)
	}
	if insight.SQL != "" || insight.Evidence["execution_mode"] != "not_executed" {
		t.Fatalf("rejected answer claimed execution: %#v", insight)
	}
	if insight.Trace == nil || traceStepStatus(insight.Trace, "tool.clickhouse.query") != "skipped" || traceStepStatus(insight.Trace, "llm.synthesize") != "skipped" {
		t.Fatalf("expected skipped tool and LLM trace steps, got %#v", insight.Trace)
	}
}

func TestCustomerGeographyQualifiesPhysicalCityColumn(t *testing.T) {
	profile := synthesisFixtureProfile()
	profile.Fields = append(profile.Fields,
		domain.FieldProfile{ColumnName: "user_id"},
		domain.FieldProfile{ColumnName: "city"},
	)
	plan := buildAnalysisPlan("How many customers do we have from Dubai?", synthesisFixtureInput(), profile, synthesisFixtureSchema(), "atlys")
	if plan.Answerability != "partially_answerable" || plan.RequestedSegment != "Dubai" {
		t.Fatalf("expected observed-city plan, got %#v", plan)
	}
	if !strings.Contains(plan.SQL, "'Dubai' AS requested_city") || !strings.Contains(plan.SQL, "events.city") || strings.Contains(plan.SQL, " AS city") {
		t.Fatalf("city query can shadow its physical column: %s", plan.SQL)
	}
}

type cityCompletionReader struct{}

func (cityCompletionReader) Enabled() bool          { return true }
func (cityCompletionReader) SourceDatabase() string { return "atlys" }
func (cityCompletionReader) QueryJSON(_ context.Context, query string) ([]map[string]any, error) {
	if !strings.Contains(query, "'city' AS dimension") || !strings.Contains(query, "toString(`city`)") || strings.Contains(query, "'device_type' AS dimension") {
		return nil, errors.New("query was not restricted to the governed city dimension")
	}
	return []map[string]any{
		{"dimension": "city", "segment": "Sydney", "entrants": 81.0, "completions": 50.0, "completion_rate": .6173},
		{"dimension": "city", "segment": "Dubai", "entrants": 153.0, "completions": 70.0, "completion_rate": .4575},
	}, nil
}

type cityCaptureSynthesizer struct {
	calls int
	input InsightSynthesisRequest
}

func (synthesizer *cityCaptureSynthesizer) Enabled() bool { return true }
func (synthesizer *cityCaptureSynthesizer) Metadata() domain.InsightProvenance {
	return domain.InsightProvenance{Provider: "test", Model: "test-model", PromptVersion: AnalyticsPromptVersion}
}
func (synthesizer *cityCaptureSynthesizer) Synthesize(_ context.Context, input InsightSynthesisRequest) (InsightSynthesis, error) {
	synthesizer.calls++
	synthesizer.input = input
	return InsightSynthesis{Headline: "Sydney leads Express Checkout completion", Summary: "Sydney is 61.73%.", Why: "City was bound at the entrant event.", Confidence: .9, RecommendedAction: "Inspect the Sydney cohort."}, nil
}

func TestCityCompletionQuestionUsesGovernedDimensionEvidence(t *testing.T) {
	profile := synthesisFixtureProfile()
	profile.Fields = append(profile.Fields, domain.FieldProfile{ColumnName: "city"})
	synthesizer := &cityCaptureSynthesizer{}
	analytics := AnalyticsAgent{Reader: cityCompletionReader{}, Synthesizer: synthesizer}

	contract, insight := analytics.Analyze(context.Background(), "product_manager", "Which Cities have most express checkout rate?", domain.FeatureInput{Name: "Express Checkout"}, profile, synthesisFixtureSchema(), synthesisFixtureContext(), "trace-city-ranking")
	if contract.Intent != "segment_comparison" || contract.Playbook != "playbook:segment-completion:v1" || strings.Join(contract.Dimensions, ",") != "city" {
		t.Fatalf("city ranking did not compile to the requested governed dimension: %#v", contract)
	}
	best, ok := insight.Evidence["best_segment"].(map[string]any)
	if !ok || best["segment"] != "Sydney" || insight.Provenance.Generator != "llm" {
		t.Fatalf("city evidence was not preserved through synthesis: %#v", insight)
	}
	if synthesizer.calls != 1 || traceStepStatus(insight.Trace, "evidence.validate") != "completed" {
		t.Fatalf("valid city evidence did not reach synthesis: calls=%d trace=%#v", synthesizer.calls, insight.Trace)
	}
	rows, ok := synthesizer.input.Evidence["segments"].([]map[string]any)
	if !ok || len(rows) != 2 || rows[0]["dimension"] != "city" {
		t.Fatalf("LLM input did not contain city aggregates: %#v", synthesizer.input.Evidence)
	}
}

func TestRequestedDimensionFailsClosedWhenAggregateShapeIsWrong(t *testing.T) {
	profile := synthesisFixtureProfile()
	profile.Fields = append(profile.Fields, domain.FieldProfile{ColumnName: "city"})
	reader := &countingReader{}
	synthesizer := &countingSynthesizer{}
	analytics := AnalyticsAgent{Reader: reader, Synthesizer: synthesizer}

	contract, insight := analytics.Analyze(context.Background(), "product_manager", "Which cities have the highest completion rate?", domain.FeatureInput{Name: "Express Checkout"}, profile, synthesisFixtureSchema(), synthesisFixtureContext(), "trace-city-incomplete")
	if reader.calls != 1 || synthesizer.calls != 0 {
		t.Fatalf("invalid requested-dimension evidence crossed the synthesis gate: reader=%d synthesizer=%d", reader.calls, synthesizer.calls)
	}
	if contract.Answerability != "not_answerable" || traceStepStatus(insight.Trace, "evidence.validate") != "failed" || traceStepStatus(insight.Trace, "llm.synthesize") != "skipped" {
		t.Fatalf("incomplete dimension evidence did not fail closed: contract=%#v trace=%#v", contract, insight.Trace)
	}
}

func TestCompactContextExcludesOtherFeatureBindings(t *testing.T) {
	graph := domain.ContextVersion{
		Version: 2,
		Nodes: []domain.ContextNode{
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout"},
			{Key: "feature:instant_forex", Type: "feature", Name: "Instant Forex"},
			{Key: "playbook:segment-completion:v1", Type: "analysis_playbook", Name: "Segment completion"},
			{Key: "table:featurelens_poc.express_checkout_events_v1", Type: "table", Name: "express_checkout_events_v1"},
			{Key: "table:featurelens_poc.instant_forex_events_v1", Type: "table", Name: "instant_forex_events_v1"},
			{Key: "dimension:express_checkout:city", Type: "dimension", Name: "Express Checkout city"},
			{Key: "dimension:instant_forex:city", Type: "dimension", Name: "Instant Forex city"},
		},
		Edges: []domain.ContextEdge{
			{From: "playbook:segment-completion:v1", Relation: "QUERIES", To: "table:featurelens_poc.express_checkout_events_v1"},
			{From: "playbook:segment-completion:v1", Relation: "QUERIES", To: "table:featurelens_poc.instant_forex_events_v1"},
			{From: "playbook:segment-completion:v1", Relation: "GROUPS_BY", To: "dimension:express_checkout:city"},
			{From: "playbook:segment-completion:v1", Relation: "GROUPS_BY", To: "dimension:instant_forex:city"},
		},
	}
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{Feature: "Express Checkout", Playbook: "playbook:segment-completion:v1", AllowedTables: []string{"featurelens_poc.express_checkout_events_v1"}})
	encoded, err := json.Marshal(contextSlice)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "instant_forex") || !strings.Contains(string(encoded), "dimension:express_checkout:city") {
		t.Fatalf("feature-scoped context retrieval leaked another feature binding: %s", encoded)
	}
}

func traceStepStatus(analysisTrace *domain.AnalysisTrace, id string) string {
	for _, step := range analysisTrace.Steps {
		if step.ID == id {
			return step.Status
		}
	}
	return "missing"
}

func TestAnalyticsAgentFallsBackWhenLLMFails(t *testing.T) {
	agent := AnalyticsAgent{Reader: synthesisTestReader{}, Synthesizer: synthesisTestClient{fail: true}}
	_, insight := agent.Analyze(context.Background(), "product_manager", "How is completion?", synthesisFixtureInput(), synthesisFixtureProfile(), synthesisFixtureSchema(), synthesisFixtureContext(), "trace-test")
	if insight.Provenance.Status != "fallback" || insight.Provenance.Generator != "deterministic" {
		t.Fatalf("expected deterministic fallback provenance, got %#v", insight.Provenance)
	}
	if insight.Headline == "LLM headline" || insight.Evidence["completion_rate"] != .6 {
		t.Fatal("fallback did not preserve deterministic insight")
	}
}

func synthesisFixtureInput() domain.FeatureInput {
	return domain.FeatureInput{Name: "Test Feature", SpecMarkdown: "# Test Feature", Role: "product_manager"}
}

func synthesisFixtureProfile() domain.EventProfile {
	return domain.EventProfile{
		Rows: 2, EventOrder: []string{"feature_shown", "feature_completed"},
		Fields: []domain.FieldProfile{{ColumnName: "application_id"}},
	}
}

func synthesisFixtureSchema() domain.SchemaProposal {
	return domain.SchemaProposal{Database: "featurelens", Table: "test_events_v1", Version: 1}
}

func synthesisFixtureContext() domain.ContextVersion {
	return domain.ContextVersion{
		Version: 1, ParentVersion: 0, Feature: "test_feature", State: "published",
		Nodes: []domain.ContextNode{
			{Key: "role:product-manager", Type: "role_profile", Name: "Product Manager"},
			{Key: "playbook:feature-completion:v1", Type: "analysis_playbook", Name: "Feature completion"},
			{Key: "metric:test_feature-completion-rate", Type: "metric", Name: "Test Feature completion rate"},
		},
	}
}
