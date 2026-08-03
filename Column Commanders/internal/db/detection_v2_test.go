package db

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"clickhouse-go-service/internal/config"
)

func TestDetectionV2StatementsContainDualResolutionRollups(t *testing.T) {
	joined := strings.Join(DetectionV2Statements(), "\n")
	for _, required := range []string{
		"metrics_global_1m",
		"metrics_global_1h",
		"toStartOfMinute",
		"toStartOfHour",
		"SummingMergeTree",
		"PARTITION BY toYYYYMM(window_start)",
	} {
		if !strings.Contains(joined, required) {
			t.Errorf("detection schema is missing %q", required)
		}
	}
}

func TestDetectionV2StatementsContainOperationalTables(t *testing.T) {
	joined := strings.Join(DetectionV2Statements(), "\n")
	for _, table := range []string{
		"anomaly_candidates",
		"anomaly_episodes",
		"investigation_steps",
		"evidence_records",
		"query_templates",
	} {
		if !strings.Contains(joined, "CREATE TABLE IF NOT EXISTS "+table) {
			t.Errorf("detection schema is missing table %q", table)
		}
	}
}

func TestDetectionV2StatementsDoNotHardCodeDatabase(t *testing.T) {
	joined := strings.Join(DetectionV2Statements(), "\n")
	if strings.Contains(joined, "inmobi.") || strings.Contains(joined, "inmobi-analytics.") {
		t.Fatal("v2 migrations must use the configured connection database")
	}
}

func TestDetectionV2RevenueUsesDecimalAggregate(t *testing.T) {
	joined := strings.Join(DetectionV2Statements(), "\n")
	if !strings.Contains(joined, "revenue Decimal128(9)") {
		t.Fatal("rollup revenue must use Decimal128(9)")
	}
	if !strings.Contains(joined, "sum(toDecimal64(revenue, 9))") {
		t.Fatal("float raw revenue must be converted before aggregation")
	}
}

func TestDetectionV2StatementsParseInClickHouse(t *testing.T) {
	if os.Getenv("CLICKHOUSE_INTEGRATION_TEST") != "1" {
		t.Skip("set CLICKHOUSE_INTEGRATION_TEST=1 to validate DDL against ClickHouse")
	}

	client, err := NewClient(config.Load())
	if err != nil {
		t.Fatalf("connect to ClickHouse: %v", err)
	}
	defer client.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	for i, statement := range DetectionV2Statements() {
		// ClickHouse does not support EXPLAIN SYNTAX for ALTER TABLE. These
		// additive statements use the standard ADD COLUMN IF NOT EXISTS form
		// and are exercised by the migration itself at service startup.
		if strings.HasPrefix(statement, "ALTER TABLE") {
			continue
		}
		explainable := statement
		if strings.HasPrefix(statement, "CREATE MATERIALIZED VIEW") {
			separator := "\nAS\n"
			selectAt := strings.Index(statement, separator)
			if selectAt < 0 {
				t.Fatalf("statement %d has no materialized-view SELECT body", i+1)
			}
			explainable = statement[selectAt+len(separator):]
		}
		rows, err := client.conn.Query(ctx, "EXPLAIN SYNTAX "+explainable)
		if err != nil {
			t.Fatalf("statement %d failed syntax validation: %v", i+1, err)
		}
		if err := rows.Close(); err != nil {
			t.Fatalf("close syntax result for statement %d: %v", i+1, err)
		}
	}
	for i, statement := range DetectionV2BackfillStatements() {
		rows, err := client.conn.Query(ctx, "EXPLAIN SYNTAX "+statement)
		if err != nil {
			t.Fatalf("backfill statement %d failed syntax validation: %v", i+1, err)
		}
		if err := rows.Close(); err != nil {
			t.Fatalf("close syntax result for backfill statement %d: %v", i+1, err)
		}
	}
}
