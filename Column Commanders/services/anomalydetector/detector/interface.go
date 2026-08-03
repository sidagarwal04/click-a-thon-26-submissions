package detector

import (
	"context"

	"clickhouse-go-service/services/anomalydetector"
)

// Detector inspects a time window and returns AnomalySignals.
// Each implementation encapsulates one detection algorithm.
// All implementations must be safe for concurrent use.
type Detector interface {
	// Name returns a unique identifier (e.g. "zscore", "cusum_down").
	Name() string

	// Metrics returns the metric names this detector monitors.
	Metrics() []string

	// Detect runs the detection algorithm for the given window.
	// Returns one AnomalySignal per monitored metric — including non-anomalous ones.
	// ErrInsufficientBaseline (wrapped) means not enough history yet; not fatal.
	Detect(ctx context.Context, w anomalydetector.Window) ([]anomalydetector.AnomalySignal, error)
}
