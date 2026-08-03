package anomalydetector_test

import (
	"context"
	"io"
	"log/slog"
	"os"
	"testing"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/anomalydetector/baseline"
	"clickhouse-go-service/services/anomalydetector/detector"
)

func TestConfiguredLegacyDetectionReadPath(t *testing.T) {
	if os.Getenv("CLICKHOUSE_INTEGRATION_TEST") != "1" {
		t.Skip("set CLICKHOUSE_INTEGRATION_TEST=1 to query the configured ClickHouse service")
	}

	cfg := config.Load()
	client, err := db.NewClient(cfg)
	if err != nil {
		t.Fatalf("connect to ClickHouse: %v", err)
	}
	defer client.Close()

	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	executor := query.NewExecutor(client, logger)
	provider := baseline.NewSamePeriodProvider(executor, cfg.Detection, logger)
	detectors := []anomalydetector.Detector{
		detector.NewRobustZScoreDetector(provider, cfg.Detection, logger),
		detector.NewTrendVolumeDetector(provider, cfg.Detection, logger),
		detector.NewDirectionalCUSUMDetector(executor, provider, cfg.Detection, logger),
	}
	engine := anomalydetector.NewDetectionEngine(detectors, executor, cfg.Detection, logger)

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	window, err := engine.ResolveWindow(ctx, time.Time{})
	if err != nil {
		t.Fatalf("resolve detection window: %v", err)
	}
	result, err := engine.Detect(ctx, window)
	if err != nil {
		t.Fatalf("run detection read path: %v", err)
	}
	if len(result.Signals) == 0 {
		t.Fatal("detection returned no signals")
	}
}
