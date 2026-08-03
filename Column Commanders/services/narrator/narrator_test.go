package narrator

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/investigation"
)

type narrativeGenerator struct {
	calls        int
	instructions string
	input        string
	schema       map[string]any
	v1Class      string
}

func (g *narrativeGenerator) GenerateJSON(_ context.Context, _, _, instructions, input string, schema map[string]any, output any) (string, error) {
	g.calls++
	g.instructions = instructions
	g.input = input
	g.schema = schema
	switch target := output.(type) {
	case *Narrative:
		*target = Narrative{Headline: "Revenue dropped", Summary: "Verified segment impact", Confidence: .9}
	case *DetectionV1Narrative:
		classification := g.v1Class
		if classification == "" {
			classification = "single-segment"
		}
		*target = DetectionV1Narrative{Narrative: Narrative{Headline: "Revenue dropped", Summary: "Verified segment impact", Confidence: .9}, Classification: classification, Verdict: "Verified segment attribution"}
	}
	return "resp-narrative", nil
}

func TestNarratorRequiresVerifiedEvidence(t *testing.T) {
	generator := &narrativeGenerator{}
	n := New(generator, config.LLMConfig{NarrationEnabled: true, NarratorModel: "test-model"})
	if _, err := n.Narrate(context.Background(), investigation.Subject{}, investigation.Result{Status: "insufficient_evidence"}); err == nil {
		t.Fatal("expected unverified narration to be rejected")
	}
	evidence := investigation.Evidence{ID: uuid.New(), Verified: true}
	narrative, err := n.Narrate(context.Background(), investigation.Subject{EpisodeID: uuid.New()}, investigation.Result{Status: "verified", Evidence: []investigation.Evidence{evidence}})
	if err != nil {
		t.Fatal(err)
	}
	if narrative.Headline != "Revenue dropped" || generator.calls != 1 {
		t.Fatalf("unexpected narrative: %+v calls=%d", narrative, generator.calls)
	}
}

func TestNarrateDetectionV1UsesDeterministicVerdictWithoutSQL(t *testing.T) {
	generator := &narrativeGenerator{}
	n := New(generator, config.LLMConfig{NarrationEnabled: true, NarratorModel: "test-model"})
	signal := anomalydetector.AnomalySignal{
		Metric: "fill_rate", DetectorID: "zscore", CurrentVal: .42, BaselineVal: .91,
		DeviationPct: -.538, ZScore: -8.4, Severity: anomalydetector.SeverityCrit,
		Window: anomalydetector.Window{Start: time.Date(2026, 7, 5, 13, 0, 0, 0, time.UTC), End: time.Date(2026, 7, 5, 14, 0, 0, 0, time.UTC)},
	}
	result := &drilldown.DrillDownResult{
		Classification: "single-segment", CompletenessScore: .91,
		Decomposition: drilldown.FactorDecomposition{GuiltyFactor: "fill_rate", RuledOut: []string{"ecpm"}},
		CulpritSegments: []drilldown.SegmentFinding{{
			Dimension: "os_version", Segment: "Android 15", Metric: "fill_rate",
			ContributionPct: .91, QuerySQL: "SECRET_SEGMENT_SQL",
		}},
		Pairwise: &drilldown.PairwiseFinding{Dim1: "os_version", Value1: "Android 15", Dim2: "region", Value2: "APAC", QuerySQL: "SECRET_PAIRWISE_SQL"},
	}

	narrative, err := n.NarrateDetectionV1(context.Background(), signal, result)
	if err != nil {
		t.Fatal(err)
	}
	if narrative.Headline != "Revenue dropped" || narrative.Classification != "single-segment" || generator.calls != 1 {
		t.Fatalf("unexpected narrative: %+v calls=%d", narrative, generator.calls)
	}
	for _, want := range []string{`"classification":"single-segment"`, `"guilty_factor":"fill_rate"`, `"dimension":"os_version"`, `"segment":"Android 15"`} {
		if !strings.Contains(generator.input, want) {
			t.Errorf("narrator input does not contain %s: %s", want, generator.input)
		}
	}
	if strings.Contains(generator.input, "SECRET_") {
		t.Fatalf("narrator input leaked query SQL: %s", generator.input)
	}
	properties := generator.schema["properties"].(map[string]any)
	classificationSchema := properties["classification"].(map[string]any)
	if got := classificationSchema["enum"].([]string); len(got) != 1 || got[0] != "single-segment" {
		t.Fatalf("classification schema is not pinned to deterministic verdict: %+v", got)
	}
}

func TestNarrateDetectionV1RejectsClassificationMismatch(t *testing.T) {
	generator := &narrativeGenerator{v1Class: "global"}
	n := New(generator, config.LLMConfig{NarrationEnabled: true, NarratorModel: "test-model"})
	_, err := n.NarrateDetectionV1(context.Background(), anomalydetector.AnomalySignal{}, &drilldown.DrillDownResult{Classification: "single-segment"})
	if err == nil {
		t.Fatal("expected narrator classification mismatch to be rejected")
	}
}
