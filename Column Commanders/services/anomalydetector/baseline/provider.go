package baseline

import (
	"context"
	"errors"
	"time"
)

// ErrInsufficientBaseline is returned when fewer than MinBaselineN prior
// same-period observations are available.
var ErrInsufficientBaseline = errors.New("baseline: insufficient prior same-period observations")

// Provider computes statistical baselines for detection windows.
// All implementations must be safe for concurrent use.
type Provider interface {
	// Compute returns baseline statistics and current window metric values.
	// grain: "daily" or "hourly"
	// targetTime: the start timestamp/date of the aggregate row being evaluated
	// Returns ErrInsufficientBaseline if fewer than MinBaselineN observations exist.
	Compute(ctx context.Context, grain string, targetTime time.Time) (ComputeResult, error)
}
