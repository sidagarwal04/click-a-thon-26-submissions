package investigation

import (
	"context"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
)

type actionGenerator struct {
	actions []AgentAction
	index   int
}

func (g *actionGenerator) GenerateJSON(_ context.Context, _, _, _, _ string, _ map[string]any, output any) (string, error) {
	*(output.(*AgentAction)) = g.actions[g.index]
	g.index++
	return "resp-test", nil
}

type fakeQueryExecutor struct{}

func (fakeQueryExecutor) Execute(_ context.Context, _ int, validated ValidatedQuery, _, _ time.Time) (QueryResult, error) {
	return QueryResult{Purpose: validated.Purpose, Rows: []map[string]any{{"segment": "banner", "impact": -42.0}}}, nil
}

type fakeVerifier struct{ evidence Evidence }

func (v fakeVerifier) Localize(_ context.Context, _ Subject) ([]Evidence, error) {
	return []Evidence{v.evidence}, nil
}

func (v fakeVerifier) Verify(_ context.Context, _ Subject, _, _ string) (Evidence, error) {
	return v.evidence, nil
}

type fakeStore struct{}

func (fakeStore) SaveStep(context.Context, Subject, Step) error { return nil }
func (fakeStore) SaveEvidence(context.Context, Evidence) error  { return nil }

func TestAgentCompletesOnlyAfterCanonicalVerification(t *testing.T) {
	queryAction := func(state string) AgentAction {
		return AgentAction{State: state, Action: "query", Purpose: "gather " + state,
			SQL: validAgentSQL, ExpectedColumns: []string{"segment", "impact"}, Decision: "evidence gathered"}
	}
	generator := &actionGenerator{actions: []AgentAction{
		queryAction("DISCOVER"), queryAction("CONFIRM"), queryAction("LOCALIZE"),
		queryAction("RULE_OUT"), queryAction("VERIFY"),
		{State: "FINISH", Action: "finish", Decision: "Banner traffic caused the verified revenue drop.", RootCauseDimension: "ad_format", RootCauseSegment: "banner", Confidence: .91},
	}}
	cfg := config.LLMConfig{InvestigationEnabled: true, InvestigatorModel: "test-model", MaxSteps: 8, MaxQueries: 6}
	detectionCfg := config.DetectionConfig{AgentQueryTimeout: time.Second, AgentMaxRowsRead: 1000, AgentMaxBytesRead: 1000, AgentMaxResultRows: 100}
	evidence := Evidence{ID: uuid.New(), Verified: true, Metric: anomalydetector.MetricRevenue, Dimension: "ad_format", Segment: "banner"}
	agent := NewAgent(generator, NewValidator(detectionCfg), fakeQueryExecutor{}, fakeVerifier{evidence: evidence}, fakeStore{}, cfg, slog.New(slog.NewTextHandler(io.Discard, nil)))
	result, err := agent.Investigate(context.Background(), Subject{
		EpisodeID: uuid.New(), Metric: anomalydetector.MetricRevenue, Mode: anomalydetector.ModeHistorical,
		Start: time.Now().Add(-time.Hour), End: time.Now(),
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != "verified" || result.RootCauseSegment != "banner" || len(result.Evidence) != 1 {
		t.Fatalf("unexpected result: %+v", result)
	}
	if generator.index != 6 {
		t.Fatalf("model calls = %d, want 6", generator.index)
	}
}

func TestAgentFallsBackToCanonicalDimensionSweep(t *testing.T) {
	generator := &actionGenerator{actions: []AgentAction{{
		State: "LOCALIZE", Action: "query", Purpose: "check strongest canonical candidate",
		SQL: validAgentSQL, ExpectedColumns: []string{"segment", "impact"}, Decision: "candidate confirmed",
	}}}
	cfg := config.LLMConfig{InvestigationEnabled: true, InvestigatorModel: "test-model", MaxSteps: 1, MaxQueries: 1}
	detectionCfg := config.DetectionConfig{AgentQueryTimeout: time.Second, AgentMaxRowsRead: 1000, AgentMaxBytesRead: 1000, AgentMaxResultRows: 100}
	evidence := Evidence{
		ID: uuid.New(), Verified: true, Metric: anomalydetector.MetricFillRate,
		Dimension: "os_version", Segment: "Android 15", ContributionPct: .9,
	}
	agent := NewAgent(generator, NewValidator(detectionCfg), fakeQueryExecutor{}, fakeVerifier{evidence: evidence}, fakeStore{}, cfg, slog.New(slog.NewTextHandler(io.Discard, nil)))
	result, err := agent.Investigate(context.Background(), Subject{
		EpisodeID: uuid.New(), Metric: anomalydetector.MetricFillRate,
		Direction: anomalydetector.DirectionDown, Mode: anomalydetector.ModeHistorical,
		Start: time.Now().Add(-time.Hour), End: time.Now(),
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != "verified" || result.RootCauseDimension != "os_version" || result.RootCauseSegment != "Android 15" {
		t.Fatalf("unexpected fallback result: %+v", result)
	}
}
