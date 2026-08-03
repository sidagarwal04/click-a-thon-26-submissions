package anomalydetector

import (
	"testing"
	"time"
)

func TestCandidateIDIsStableAndResolutionSpecific(t *testing.T) {
	start := time.Date(2026, 6, 18, 10, 0, 0, 0, time.UTC)
	first := CandidateID(ModeHistorical, Resolution10m, MetricRevenue, DirectionDown, start)
	second := CandidateID(ModeHistorical, Resolution10m, MetricRevenue, DirectionDown, start)
	if first != second {
		t.Fatalf("candidate id is not stable: %s != %s", first, second)
	}
	hourly := CandidateID(ModeHistorical, Resolution1h, MetricRevenue, DirectionDown, start)
	if first == hourly {
		t.Fatal("different resolutions must have different candidate ids")
	}
}

func TestDirectionFromSignal(t *testing.T) {
	if got := DirectionFromSignal(AnomalySignal{DeviationPct: 0.2}); got != DirectionUp {
		t.Fatalf("positive deviation direction = %d", got)
	}
	if got := DirectionFromSignal(AnomalySignal{DeviationPct: -0.2}); got != DirectionDown {
		t.Fatalf("negative deviation direction = %d", got)
	}
}
