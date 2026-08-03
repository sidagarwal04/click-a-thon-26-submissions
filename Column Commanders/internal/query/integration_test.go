package query

import (
	"context"
	"io"
	"log/slog"
	"os"
	"testing"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
)

func TestConfiguredDataAnchorIntegration(t *testing.T) {
	if os.Getenv("CLICKHOUSE_INTEGRATION_TEST") != "1" {
		t.Skip("set CLICKHOUSE_INTEGRATION_TEST=1 to query the configured ClickHouse service")
	}

	client, err := db.NewClient(config.Load())
	if err != nil {
		t.Fatalf("connect to ClickHouse: %v", err)
	}
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	executor := NewExecutor(client, slog.New(slog.NewTextHandler(io.Discard, nil)))
	row, err := executor.Row(ctx, "data_anchor_integration", GetDataAnchorSQL)
	if err != nil {
		t.Fatalf("query configured watermark: %v", err)
	}
	if anchor, ok := row["anchor"].(string); !ok || anchor == "" {
		t.Fatalf("unexpected anchor value: %#v", row["anchor"])
	}
}
