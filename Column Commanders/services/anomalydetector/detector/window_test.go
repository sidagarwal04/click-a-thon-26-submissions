package detector

import (
	"context"
	"io"
	"log/slog"
	"testing"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/anomalydetector/baseline"
)

type recordingBaselineProvider struct {
	target time.Time
}

func (p *recordingBaselineProvider) Compute(_ context.Context, _ string, target time.Time) (baseline.ComputeResult, error) {
	p.target = target
	return baseline.ComputeResult{}, baseline.ErrInsufficientBaseline
}

type fixedBaselineProvider struct {
	result baseline.ComputeResult
}

func (p fixedBaselineProvider) Compute(context.Context, string, time.Time) (baseline.ComputeResult, error) {
	return p.result, nil
}

func TestDetectorsQueryWindowStart(t *testing.T) {
	start := time.Date(2026, 7, 5, 22, 0, 0, 0, time.UTC)
	window := anomalydetector.Window{Start: start, End: start.Add(time.Hour), Duration: time.Hour}
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	cfg := config.DetectionConfig{MinBaselineN: 3}

	tests := []struct {
		name string
		run  func(*recordingBaselineProvider) error
	}{
		{
			name: "zscore",
			run: func(provider *recordingBaselineProvider) error {
				_, err := NewRobustZScoreDetector(provider, cfg, logger).Detect(context.Background(), window)
				return err
			},
		},
		{
			name: "volume",
			run: func(provider *recordingBaselineProvider) error {
				_, err := NewTrendVolumeDetector(provider, cfg, logger).Detect(context.Background(), window)
				return err
			},
		},
		{
			name: "cusum",
			run: func(provider *recordingBaselineProvider) error {
				_, err := NewDirectionalCUSUMDetector(nil, provider, cfg, logger).Detect(context.Background(), window)
				return err
			},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			provider := &recordingBaselineProvider{}
			if err := test.run(provider); err != nil {
				t.Fatalf("detect: %v", err)
			}
			if !provider.target.Equal(start) {
				t.Fatalf("baseline target = %s, want window start %s", provider.target, start)
			}
		})
	}
}

func TestRobustZScoreDetectorIncludesRevenue(t *testing.T) {
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	detector := NewRobustZScoreDetector(&recordingBaselineProvider{}, config.DetectionConfig{}, logger)
	for _, metric := range detector.Metrics() {
		if metric == anomalydetector.MetricRevenue {
			return
		}
	}
	t.Fatal("robust z-score detector must monitor revenue")
}

func TestRevenueDetectionAcceptsTwoSamePeriodObservations(t *testing.T) {
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	provider := fixedBaselineProvider{result: baseline.ComputeResult{CurrentVals: map[string]float64{
		anomalydetector.MetricRevenue:               50,
		"bl:med:" + anomalydetector.MetricRevenue:   100,
		"bl:sigma:" + anomalydetector.MetricRevenue: 5,
		"bl:n": 2,
	}}}
	detector := NewRobustZScoreDetector(provider, config.DetectionConfig{
		MinBaselineN: 3, ZScoreThreshold: 5, MinDeviationPct: 0.03,
	}, logger)
	window := anomalydetector.Window{Start: time.Unix(1_700_000_000, 0), End: time.Unix(1_700_086_400, 0)}

	signals, err := detector.Detect(context.Background(), window)
	if err != nil {
		t.Fatalf("detect: %v", err)
	}
	for _, signal := range signals {
		if signal.Metric == anomalydetector.MetricRevenue {
			if !signal.IsAnomaly || signal.BaselineN != 2 {
				t.Fatalf("revenue signal = %+v, want anomaly with baseline N=2", signal)
			}
			return
		}
	}
	t.Fatal("revenue signal missing")
}
