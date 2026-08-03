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

// TrendVolumeDetector — Detector B.
// Monitors requests with linear trend correction applied to the baseline.
type TrendVolumeDetector struct {
	bp     baseline.Provider
	cfg    config.DetectionConfig
	logger *slog.Logger
}

func NewTrendVolumeDetector(bp baseline.Provider, cfg config.DetectionConfig, logger *slog.Logger) *TrendVolumeDetector {
	return &TrendVolumeDetector{bp: bp, cfg: cfg, logger: logger}
}

func (d *TrendVolumeDetector) Name() string { return "volume" }
func (d *TrendVolumeDetector) Metrics() []string {
	return []string{anomalydetector.MetricRequests}
}

func (d *TrendVolumeDetector) Detect(ctx context.Context, w anomalydetector.Window) ([]anomalydetector.AnomalySignal, error) {
	result, err := d.bp.Compute(ctx, w.Grain(), w.Start)
	if err != nil {
		if errors.Is(err, baseline.ErrInsufficientBaseline) {
			return insufficientSignals(d.Name(), d.Metrics(), w), nil
		}
		return nil, fmt.Errorf("volume detector: %w", err)
	}

	currentVal := result.CurrentVals[anomalydetector.MetricRequests]
	bl := baseline.BaselineFor(result, anomalydetector.MetricRequests, d.cfg.MinBaselineN)

	z := bl.ZScore(currentVal, w.Target().Unix())
	devPct := bl.DeviationPct(currentVal, w.Target().Unix())
	isAnomaly := math.Abs(z) > d.cfg.ZScoreThreshold && math.Abs(devPct) > d.cfg.MinDeviationPct

	return []anomalydetector.AnomalySignal{{
		Metric:       anomalydetector.MetricRequests,
		Window:       w,
		DetectorID:   d.Name(),
		CurrentVal:   currentVal,
		BaselineVal:  bl.AdjustedMedian(w.Target().Unix(), bl.BaselineMidpointUnix),
		ZScore:       z,
		DeviationPct: devPct,
		Severity:     severityFromZ(math.Abs(z), d.cfg.ZScoreThreshold),
		IsAnomaly:    isAnomaly,
		BaselineN:    bl.N,
	}}, nil
}
