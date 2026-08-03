package detector

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"math"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/anomalydetector/baseline"
)

// RobustZScoreDetector — Detector A.
// Monitors revenue, fill_rate, eCPM, and CTR using median/IQR robust z-score.
type RobustZScoreDetector struct {
	bp     baseline.Provider
	cfg    config.DetectionConfig
	logger *slog.Logger
}

func NewRobustZScoreDetector(bp baseline.Provider, cfg config.DetectionConfig, logger *slog.Logger) *RobustZScoreDetector {
	return &RobustZScoreDetector{bp: bp, cfg: cfg, logger: logger}
}

func (d *RobustZScoreDetector) Name() string { return "zscore" }
func (d *RobustZScoreDetector) Metrics() []string {
	return []string{
		anomalydetector.MetricRevenue,
		anomalydetector.MetricFillRate,
		anomalydetector.MetricECPM,
		anomalydetector.MetricCTR,
	}
}

func (d *RobustZScoreDetector) Detect(ctx context.Context, w anomalydetector.Window) ([]anomalydetector.AnomalySignal, error) {
	result, err := d.bp.Compute(ctx, w.Grain(), w.Start)
	if err != nil {
		if errors.Is(err, baseline.ErrInsufficientBaseline) {
			return insufficientSignals(d.Name(), d.Metrics(), w), nil
		}
		return nil, fmt.Errorf("zscore detector: %w", err)
	}

	var signals []anomalydetector.AnomalySignal
	for _, metric := range d.Metrics() {
		currentVal := result.CurrentVals[metric]
		minN := d.cfg.MinBaselineN
		if metric == anomalydetector.MetricRevenue && minN > 2 {
			minN = 2
		}
		bl := baseline.BaselineFor(result, metric, minN)

		z := bl.ZScore(currentVal, w.Target().Unix())
		threshold := d.cfg.ZScoreThreshold
		floor := d.cfg.MinDeviationPct
		if metric == anomalydetector.MetricRevenue {
			// Match the established browser-side V1 revenue detector: commercial
			// movement must be at least 8%, in addition to being statistically rare.
			floor = math.Max(floor, 0.08)
		}
		if metric == anomalydetector.MetricCTR {
			threshold = d.cfg.ZScoreCTRThreshold
			floor = d.cfg.MinDeviationPctCTR
		}

		devPct := bl.DeviationPct(currentVal, w.Target().Unix())
		// Significance (z) alone is unreliable at this N — sigma is tiny enough
		// that ordinary noise (e.g. ~2-3% eCPM softness) can register z > 150.
		// Require both the z-test AND a minimum real-world magnitude.
		isAnomaly := math.Abs(z) > threshold && math.Abs(devPct) > floor

		signals = append(signals, anomalydetector.AnomalySignal{
			Metric:       metric,
			Window:       w,
			DetectorID:   d.Name(),
			CurrentVal:   currentVal,
			BaselineVal:  bl.AdjustedMedian(w.Target().Unix(), bl.BaselineMidpointUnix),
			ZScore:       z,
			DeviationPct: devPct,
			Severity:     severityFromZ(math.Abs(z), threshold),
			IsAnomaly:    isAnomaly,
			BaselineN:    bl.N,
		})
	}
	return signals, nil
}
