package detectionv2

import (
	"testing"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/services/anomalydetector"
)

func TestDecodeCandidates(t *testing.T) {
	candidateID := uuid.New()
	runID := uuid.New()
	now := time.Now().UTC().Truncate(time.Millisecond)
	candidates, err := decodeCandidates([]map[string]any{{
		"candidate_id": candidateID.String(), "run_id": runID,
		"mode": "historical", "resolution": "1h", "metric": "fill_rate", "direction": int8(-1),
		"window_start": now, "window_end": now.Add(time.Hour), "current_value": 0.4,
		"baseline_value": 0.8, "deviation_pct": -0.5, "score": 9.2,
		"revenue_impact": "-2.5", "baseline_n": uint16(3), "severity": uint8(4),
		"status": "candidate", "detected_at": now, "version": uint64(42),
	}})
	if err != nil {
		t.Fatal(err)
	}
	if len(candidates) != 1 {
		t.Fatalf("decoded %d candidates, want 1", len(candidates))
	}
	candidate := candidates[0]
	if candidate.ID != candidateID || candidate.RunID != runID || candidate.Mode != anomalydetector.ModeHistorical {
		t.Fatalf("unexpected candidate identity: %+v", candidate)
	}
	if candidate.Resolution != anomalydetector.Resolution1h || candidate.Metric != "fill_rate" || candidate.Direction != anomalydetector.DirectionDown {
		t.Fatalf("unexpected candidate classification: %+v", candidate)
	}
}
