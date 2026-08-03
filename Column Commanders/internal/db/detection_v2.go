package db

import (
	"context"
	"fmt"
)

// DetectionV2Statements creates the dual-resolution rollups and durable
// workflow tables. Statements intentionally use the connection's configured
// database instead of hard-coding a deployment-specific database name.
func DetectionV2Statements() []string {
	return []string{
		`CREATE TABLE IF NOT EXISTS metrics_global_1m
(
	window_start DateTime64(3, 'UTC'),
	requests UInt64,
	fills UInt64,
	impressions UInt64,
	clicks UInt64,
	revenue Decimal128(9)
)
ENGINE = SummingMergeTree((requests, fills, impressions, clicks, revenue))
PARTITION BY toYYYYMM(window_start)
ORDER BY window_start`,

		`CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_global_1m_mv
TO metrics_global_1m
AS
SELECT
	toStartOfMinute(toTimeZone(event_time, 'UTC')) AS window_start,
	count() AS requests,
	sum(is_filled) AS fills,
	sum(is_impression) AS impressions,
	sum(is_click) AS clicks,
	sum(toDecimal64(revenue, 9)) AS revenue
FROM ad_events
GROUP BY window_start`,

		`CREATE TABLE IF NOT EXISTS metrics_global_1h
(
	window_start DateTime64(3, 'UTC'),
	requests UInt64,
	fills UInt64,
	impressions UInt64,
	clicks UInt64,
	revenue Decimal128(9)
)
ENGINE = SummingMergeTree((requests, fills, impressions, clicks, revenue))
PARTITION BY toYYYYMM(window_start)
ORDER BY window_start`,

		`CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_global_1h_mv
TO metrics_global_1h
AS
SELECT
	toStartOfHour(toTimeZone(event_time, 'UTC')) AS window_start,
	count() AS requests,
	sum(is_filled) AS fills,
	sum(is_impression) AS impressions,
	sum(is_click) AS clicks,
	sum(toDecimal64(revenue, 9)) AS revenue
FROM ad_events
GROUP BY window_start`,

		`CREATE TABLE IF NOT EXISTS anomaly_candidates
(
	candidate_id UUID,
	run_id UUID,
	mode LowCardinality(String),
	resolution LowCardinality(String),
	metric LowCardinality(String),
	direction Int8,
	window_start DateTime64(3, 'UTC'),
	window_end DateTime64(3, 'UTC'),
	current_value Float64,
	baseline_value Float64,
	deviation_pct Float64,
	score Float64,
	revenue_impact Decimal128(9) DEFAULT 0,
	baseline_n UInt16,
	severity UInt8,
	status LowCardinality(String) DEFAULT 'candidate',
	detected_at DateTime64(3, 'UTC') DEFAULT now64(3),
	version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3))
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(window_start)
ORDER BY candidate_id`,

		`CREATE TABLE IF NOT EXISTS anomaly_episodes
(
	episode_id UUID,
	primary_metric LowCardinality(String),
	direction Int8,
	start_time DateTime64(3, 'UTC'),
	end_time DateTime64(3, 'UTC'),
	detected_resolutions Array(String),
	candidate_ids Array(UUID),
	severity UInt8,
	status LowCardinality(String),
	verification_status LowCardinality(String) DEFAULT 'pending',
	created_at DateTime64(3, 'UTC') DEFAULT now64(3),
	updated_at DateTime64(3, 'UTC') DEFAULT now64(3),
	version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3))
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(start_time)
ORDER BY episode_id`,

		`CREATE TABLE IF NOT EXISTS investigation_steps
(
	episode_id UUID,
	step_index UInt16,
	state LowCardinality(String),
	purpose String,
	query_template_id UUID DEFAULT toUUID('00000000-0000-0000-0000-000000000000'),
	query_sql String DEFAULT '',
	validation_status LowCardinality(String),
	decision String DEFAULT '',
	created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (episode_id, step_index, created_at)`,

		`CREATE TABLE IF NOT EXISTS evidence_records
(
	evidence_id UUID,
	episode_id UUID,
	metric LowCardinality(String),
	dimension LowCardinality(String) DEFAULT '',
	segment String DEFAULT '',
	window_start DateTime64(3, 'UTC'),
	window_end DateTime64(3, 'UTC'),
	current_value Float64,
	baseline_value Float64,
	deviation_pct Float64,
	contribution_pct Float64,
	revenue_impact Decimal128(9) DEFAULT 0,
	baseline_n UInt16,
	verified UInt8,
	verification_query String,
	created_at DateTime64(3, 'UTC') DEFAULT now64(3),
	version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3))
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(created_at)
ORDER BY evidence_id`,

		`CREATE TABLE IF NOT EXISTS query_templates
(
	template_id UUID,
	purpose LowCardinality(String),
	mode LowCardinality(String),
	resolution LowCardinality(String),
	sql String,
	expected_columns Array(String),
	metric_registry_checksum FixedString(64),
	schema_fingerprint String,
	status LowCardinality(String),
	created_at DateTime64(3, 'UTC') DEFAULT now64(3),
	updated_at DateTime64(3, 'UTC') DEFAULT now64(3),
	version UInt64 DEFAULT toUnixTimestamp64Milli(now64(3))
)
ENGINE = ReplacingMergeTree(version)
ORDER BY template_id`,

		`ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS diagnosis String DEFAULT ''`,
		`ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS root_cause_dimension LowCardinality(String) DEFAULT ''`,
		`ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS root_cause_segment String DEFAULT ''`,
		`ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS narration String DEFAULT ''`,
		`ALTER TABLE anomaly_episodes ADD COLUMN IF NOT EXISTS confidence Float32 DEFAULT 0`,
		`ALTER TABLE investigation_steps ADD COLUMN IF NOT EXISTS result_rows UInt32 DEFAULT 0`,
		`ALTER TABLE investigation_steps ADD COLUMN IF NOT EXISTS result_json String DEFAULT ''`,
		`ALTER TABLE investigation_steps ADD COLUMN IF NOT EXISTS error String DEFAULT ''`,
	}
}

// MigrateDetectionV2 applies additive, idempotent DDL only. Historical data is
// deliberately not backfilled here because safe backfill requires an explicit
// cutover/reconciliation step and must never happen implicitly at service boot.
func (c *Client) MigrateDetectionV2(ctx context.Context) error {
	for i, statement := range DetectionV2Statements() {
		if err := c.conn.Exec(ctx, statement); err != nil {
			return fmt.Errorf("detection v2 migration statement %d: %w", i+1, err)
		}
	}
	return nil
}

// BackfillDetectionV2 populates each rollup only when it is completely empty.
// This makes the operation safe to retry while avoiding duplicate SummingMergeTree
// rows. It is deliberately opt-in through DETECTION_AUTO_BACKFILL.
func (c *Client) BackfillDetectionV2(ctx context.Context) error {
	for i, statement := range DetectionV2BackfillStatements() {
		if err := c.conn.Exec(ctx, statement); err != nil {
			return fmt.Errorf("detection v2 backfill statement %d: %w", i+1, err)
		}
	}
	return nil
}

// DetectionV2BackfillStatements is exported for read-only syntax validation
// and operational tooling.
func DetectionV2BackfillStatements() []string {
	return []string{
		`INSERT INTO metrics_global_1m
SELECT
	toStartOfMinute(toTimeZone(event_time, 'UTC')) AS window_start,
	count() AS requests,
	sum(is_filled) AS fills,
	sum(is_impression) AS impressions,
	sum(is_click) AS clicks,
	sum(toDecimal64(revenue, 9)) AS revenue
FROM ad_events
WHERE NOT EXISTS (SELECT 1 FROM metrics_global_1m LIMIT 1)
GROUP BY window_start`,
		`INSERT INTO metrics_global_1h
SELECT
	toStartOfHour(toTimeZone(event_time, 'UTC')) AS window_start,
	count() AS requests,
	sum(is_filled) AS fills,
	sum(is_impression) AS impressions,
	sum(is_click) AS clicks,
	sum(toDecimal64(revenue, 9)) AS revenue
FROM ad_events
WHERE NOT EXISTS (SELECT 1 FROM metrics_global_1h LIMIT 1)
GROUP BY window_start`,
	}
}
