package baseline

// Baseline holds computed reference statistics for a metric over a reference period.
type Baseline struct {
	Metric               string
	Median               float64 // quantile(0.5) — robust centre
	IQR                  float64 // Q3 - Q1
	Sigma                float64 // IQR / 1.35 — normalised IQR ≈ stddev
	TrendSlope           float64 // req/sec slope from simpleLinearRegression; 0 for ratio metrics
	BaselineMidpointUnix int64   // unix timestamp of mean(day) across baseline set
	N                    int     // number of prior same-period observations
	Sufficient           bool    // N >= MinBaselineN
}

// ComputeResult bundles baseline stats with the current window's metric values,
// so a single SQL round-trip serves both needs.
type ComputeResult struct {
	Baseline    Baseline
	CurrentVals map[string]float64 // metric name → current window value
}

// ZScore computes the z-score for an observed value against this baseline.
// For MetricRequests it applies trend correction; for ratio metrics TrendSlope == 0 so no correction.
// Returns 0 if Sigma == 0 or Sufficient == false.
func (b Baseline) ZScore(observed float64, observedUnix int64) float64 {
	if !b.Sufficient || b.Sigma == 0 {
		return 0
	}
	adjusted := b.AdjustedMedian(observedUnix, b.BaselineMidpointUnix)
	return (observed - adjusted) / b.Sigma
}

// AdjustedMedian returns the trend-corrected median at the given Unix timestamp.
func (b Baseline) AdjustedMedian(targetUnix, midpointUnix int64) float64 {
	return b.Median + b.TrendSlope*float64(targetUnix-midpointUnix)
}

// DeviationPct returns (observed - adjustedMedian) / adjustedMedian.
func (b Baseline) DeviationPct(observed float64, targetUnix int64) float64 {
	adj := b.AdjustedMedian(targetUnix, b.BaselineMidpointUnix)
	if adj == 0 {
		return 0
	}
	return (observed - adj) / adj
}
