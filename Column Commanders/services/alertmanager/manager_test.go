package alertmanager

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"

	"go.opentelemetry.io/otel/trace"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/narrator"
)

type fakeDrillDownRunner struct {
	result *drilldown.DrillDownResult
}

func (f fakeDrillDownRunner) Investigate(context.Context, anomalydetector.AnomalySignal) (*drilldown.DrillDownResult, error) {
	return f.result, nil
}

type fakeVerdictNarrator struct {
	narrative narrator.DetectionV1Narrative
	err       error
}

func (f fakeVerdictNarrator) NarrateDetectionV1(context.Context, anomalydetector.AnomalySignal, *drilldown.DrillDownResult) (narrator.DetectionV1Narrative, error) {
	return f.narrative, f.err
}

func TestRunDrillDownAttachesNarrationAtEnd(t *testing.T) {
	result := &drilldown.DrillDownResult{Classification: "single-segment"}
	store := testStoreWithIncident("incident-1")
	manager := NewManager(
		store,
		fakeDrillDownRunner{result: result},
		fakeVerdictNarrator{narrative: narrator.DetectionV1Narrative{Narrative: narrator.Narrative{Headline: "Final verdict"}, Classification: "single-segment", Verdict: "single-segment attribution"}},
		configForTest(),
		slog.New(slog.NewTextHandler(io.Discard, nil)),
	)

	ctx := context.Background()
	manager.runDrillDown("incident-1", anomalydetector.AnomalySignal{Metric: "fill_rate"}, ctx, trace.SpanFromContext(ctx))
	incident := store.GetByID("incident-1")
	if incident.DrillDown != result {
		t.Fatal("completed drilldown was not attached")
	}
	if incident.Narration == nil || incident.Narration.Headline != "Final verdict" || incident.Narration.Classification != "single-segment" || incident.Narration.Verdict != "single-segment attribution" {
		t.Fatalf("unexpected narration: %+v", incident.Narration)
	}
}

func TestRunDrillDownKeepsResultWhenNarrationFails(t *testing.T) {
	result := &drilldown.DrillDownResult{Classification: "global"}
	store := testStoreWithIncident("incident-2")
	manager := NewManager(
		store,
		fakeDrillDownRunner{result: result},
		fakeVerdictNarrator{err: errors.New("LLM unavailable")},
		configForTest(),
		slog.New(slog.NewTextHandler(io.Discard, nil)),
	)

	ctx := context.Background()
	manager.runDrillDown("incident-2", anomalydetector.AnomalySignal{Metric: "revenue"}, ctx, trace.SpanFromContext(ctx))
	incident := store.GetByID("incident-2")
	if incident.DrillDown != result {
		t.Fatal("deterministic drilldown should remain available after narration failure")
	}
	if incident.Narration != nil {
		t.Fatalf("expected nil narration, got %+v", incident.Narration)
	}
}

func testStoreWithIncident(id string) *Store {
	incident := &Incident{ID: id}
	return &Store{
		active: map[incidentKey]*Incident{},
		byID:   map[string]*Incident{id: incident},
	}
}

func configForTest() config.DetectionConfig { return config.DetectionConfig{} }
