package anomalydetector

import (
	"fmt"
	"time"

	"github.com/google/uuid"
)

// Direction is stored numerically in ClickHouse so ordering and filtering are
// unambiguous across detector implementations.
type Direction int8

const (
	DirectionDown Direction = -1
	DirectionUp   Direction = 1
)

// Candidate is the durable anomaly unit emitted by a scanner before adjacent
// windows and resolutions are correlated into an episode.
type Candidate struct {
	ID            uuid.UUID     `json:"candidate_id"`
	RunID         uuid.UUID     `json:"run_id"`
	Mode          DetectionMode `json:"mode"`
	Resolution    Resolution    `json:"resolution"`
	Metric        string        `json:"metric"`
	Direction     Direction     `json:"direction"`
	WindowStart   time.Time     `json:"window_start"`
	WindowEnd     time.Time     `json:"window_end"`
	CurrentValue  float64       `json:"current_value"`
	BaselineValue float64       `json:"baseline_value"`
	DeviationPct  float64       `json:"deviation_pct"`
	Score         float64       `json:"score"`
	RevenueImpact string        `json:"revenue_impact"`
	BaselineN     uint16        `json:"baseline_n"`
	Severity      Severity      `json:"severity"`
	Status        string        `json:"status"`
	DetectedAt    time.Time     `json:"detected_at"`
	Version       uint64        `json:"-"`
}

// CandidateID returns a stable identifier for the candidate's natural key.
// Reprocessing the same scan window therefore replaces the old candidate row
// instead of producing a duplicate.
func CandidateID(mode DetectionMode, resolution Resolution, metric string, direction Direction, windowStart time.Time) uuid.UUID {
	key := fmt.Sprintf("%s|%s|%s|%d|%s",
		mode,
		resolution,
		metric,
		direction,
		windowStart.UTC().Format(time.RFC3339Nano),
	)
	return uuid.NewSHA1(uuid.NameSpaceOID, []byte(key))
}

// DirectionFromSignal derives direction from the detector evidence while
// keeping downward movement as the conservative zero-value fallback.
func DirectionFromSignal(signal AnomalySignal) Direction {
	if signal.ZScore > 0 || signal.CUSUMVal > 0 || signal.DeviationPct > 0 {
		return DirectionUp
	}
	return DirectionDown
}
