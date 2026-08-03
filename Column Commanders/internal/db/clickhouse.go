package db

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"reflect"
	"strings"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/model"
)

// ErrNoRows is returned by QueryRow when the result set is empty.
var ErrNoRows = errors.New("clickhouse: no rows returned")

// Client wraps a ClickHouse native-protocol connection.
type Client struct {
	conn driver.Conn
}

// NewClient opens and pings a ClickHouse connection using the native protocol.
func NewClient(cfg *config.Config) (*Client, error) {
	opts := &clickhouse.Options{
		Addr: []string{cfg.ClickHouseHost + ":" + cfg.ClickHousePort},
		Auth: clickhouse.Auth{
			Database: cfg.ClickHouseDB,
			Username: cfg.ClickHouseUser,
			Password: cfg.ClickHousePassword,
		},
		DialTimeout:     5 * time.Second,
		MaxOpenConns:    10,
		MaxIdleConns:    5,
		ConnMaxLifetime: time.Hour,
		Compression: &clickhouse.Compression{
			Method: clickhouse.CompressionLZ4,
		},
	}
	if cfg.ClickHouseSecure {
		opts.TLS = &tls.Config{MinVersion: tls.VersionTLS12}
	}
	conn, err := clickhouse.Open(opts)
	if err != nil {
		return nil, fmt.Errorf("open clickhouse connection: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := conn.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping clickhouse: %w", err)
	}

	return &Client{conn: conn}, nil
}

// Ping checks connectivity.
func (c *Client) Ping(ctx context.Context) error {
	return c.conn.Ping(ctx)
}

// Migrate creates the events table if it does not already exist.
func (c *Client) Migrate(ctx context.Context) error {
	return c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS events (
			id          UUID    DEFAULT generateUUIDv4(),
			source      String,
			event_type  String,
			payload     String,
			timestamp   DateTime64(3) DEFAULT now64()
		) ENGINE = MergeTree()
		ORDER BY (timestamp, event_type)
	`)
}

// MigrateGlobalRollups creates the platform-wide hourly/daily rollups and the
// watermark table that every platform-level detector (zscore, volume, cusum)
// and the drilldown factor decomposition depend on. Documented in
// plans/02_clickhouse_schema_and_mvs.md as scripts/create_mvs.sh, but that
// script was never actually committed or run — this is the real, idempotent
// equivalent, wired into startup like every other migration here.
func (c *Client) MigrateGlobalRollups(ctx context.Context) error {
	if err := c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS hourly_global_agg (
			hour       DateTime,
			requests_s AggregateFunction(count),
			fills_s    AggregateFunction(sum, UInt8),
			imps_s     AggregateFunction(sum, UInt8),
			clicks_s   AggregateFunction(sum, UInt8),
			revenue_s  AggregateFunction(sum, Float64)
		) ENGINE = AggregatingMergeTree
		PARTITION BY toYYYYMM(hour)
		ORDER BY hour
	`); err != nil {
		return fmt.Errorf("create hourly_global_agg: %w", err)
	}
	if err := c.conn.Exec(ctx, `
		CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_global_mv
		TO hourly_global_agg AS
		SELECT
			toStartOfHour(event_time) AS hour,
			countState()              AS requests_s,
			sumState(is_filled)       AS fills_s,
			sumState(is_impression)   AS imps_s,
			sumState(is_click)        AS clicks_s,
			sumState(revenue)         AS revenue_s
		FROM ad_events
		GROUP BY hour
	`); err != nil {
		return fmt.Errorf("create hourly_global_mv: %w", err)
	}

	if err := c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS daily_global_agg (
			day        Date,
			requests_s AggregateFunction(count),
			fills_s    AggregateFunction(sum, UInt8),
			imps_s     AggregateFunction(sum, UInt8),
			clicks_s   AggregateFunction(sum, UInt8),
			revenue_s  AggregateFunction(sum, Float64)
		) ENGINE = AggregatingMergeTree
		ORDER BY day
	`); err != nil {
		return fmt.Errorf("create daily_global_agg: %w", err)
	}
	if err := c.conn.Exec(ctx, `
		CREATE MATERIALIZED VIEW IF NOT EXISTS daily_global_mv
		TO daily_global_agg AS
		SELECT
			toDate(event_time)      AS day,
			countState()            AS requests_s,
			sumState(is_filled)     AS fills_s,
			sumState(is_impression) AS imps_s,
			sumState(is_click)      AS clicks_s,
			sumState(revenue)       AS revenue_s
		FROM ad_events
		GROUP BY day
	`); err != nil {
		return fmt.Errorf("create daily_global_mv: %w", err)
	}

	if err := c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS watermark (
			table_name      String,
			last_event_time DateTime,
			updated_at      DateTime DEFAULT now()
		) ENGINE = ReplacingMergeTree(updated_at)
		ORDER BY table_name
	`); err != nil {
		return fmt.Errorf("create watermark: %w", err)
	}

	return nil
}

// BackfillGlobalRollupsIfEmpty runs the one-time backfill for
// hourly_global_agg/daily_global_agg and populates the watermark row. Guarded
// against AggregatingMergeTree double-counting the same way as
// BackfillDimensionRollupIfEmpty — only backfills a rollup that's still empty.
func (c *Client) BackfillGlobalRollupsIfEmpty(ctx context.Context) error {
	if empty, err := c.tableIsEmpty(ctx, "hourly_global_agg"); err != nil {
		return fmt.Errorf("check hourly_global_agg emptiness: %w", err)
	} else if empty {
		if err := c.conn.Exec(ctx, `
			INSERT INTO hourly_global_agg
			SELECT toStartOfHour(event_time) AS hour,
			       countState(), sumState(is_filled), sumState(is_impression),
			       sumState(is_click), sumState(revenue)
			FROM ad_events GROUP BY hour
		`); err != nil {
			return fmt.Errorf("backfill hourly_global_agg: %w", err)
		}
	}

	if empty, err := c.tableIsEmpty(ctx, "daily_global_agg"); err != nil {
		return fmt.Errorf("check daily_global_agg emptiness: %w", err)
	} else if empty {
		if err := c.conn.Exec(ctx, `
			INSERT INTO daily_global_agg
			SELECT toDate(event_time) AS day,
			       countState(), sumState(is_filled), sumState(is_impression),
			       sumState(is_click), sumState(revenue)
			FROM ad_events GROUP BY day
		`); err != nil {
			return fmt.Errorf("backfill daily_global_agg: %w", err)
		}
	}

	if err := c.conn.Exec(ctx, `
		INSERT INTO watermark (table_name, last_event_time)
		SELECT 'ad_events', max(event_time) FROM ad_events
	`); err != nil {
		return fmt.Errorf("populate watermark: %w", err)
	}
	return nil
}

// tableIsEmpty reports whether the given table currently has zero rows.
func (c *Client) tableIsEmpty(ctx context.Context, table string) (bool, error) {
	row, err := c.QueryRow(ctx, fmt.Sprintf("SELECT count() AS n FROM %s SETTINGS max_execution_time = 30", table))
	if err != nil && !errors.Is(err, ErrNoRows) {
		return false, err
	}
	switch v := row["n"].(type) {
	case uint64:
		return v == 0, nil
	case int64:
		return v == 0, nil
	}
	return true, nil
}

// MigrateDetection creates operational tables for the anomaly detection service.
func (c *Client) MigrateDetection(ctx context.Context) error {
	if err := c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS cusum_state (
			metric        String,
			direction     String,
			window_end    DateTime,
			cusum_val     Float64,
			updated_at    DateTime DEFAULT now()
		) ENGINE = ReplacingMergeTree(updated_at)
		ORDER BY (metric, direction, window_end)
	`); err != nil {
		return fmt.Errorf("create cusum_state: %w", err)
	}

	if err := c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS incidents (
			id            String,
			metric        String,
			detector_id   String,
			dimension     String DEFAULT '',
			segment       String DEFAULT '',
			window_start  DateTime,
			window_end    DateTime,
			severity      UInt8,
			status        String,
			z_score       Float64,
			cusum_val     Float64,
			deviation_pct Float64,
			created_at    DateTime DEFAULT now(),
			updated_at    DateTime DEFAULT now()
		) ENGINE = ReplacingMergeTree(updated_at)
		ORDER BY (id)
		PARTITION BY toYYYYMM(window_start)
	`); err != nil {
		return fmt.Errorf("create incidents: %w", err)
	}

	// Additive, idempotent — covers a table created before dimension/segment existed.
	if err := c.conn.Exec(ctx, `ALTER TABLE incidents ADD COLUMN IF NOT EXISTS dimension String DEFAULT ''`); err != nil {
		return fmt.Errorf("alter incidents add dimension: %w", err)
	}
	if err := c.conn.Exec(ctx, `ALTER TABLE incidents ADD COLUMN IF NOT EXISTS segment String DEFAULT ''`); err != nil {
		return fmt.Errorf("alter incidents add segment: %w", err)
	}

	return nil
}

// MigrateDimensionRollup creates the dimension-pivoted rollup table + MV that
// lets Detect scan every value of a broad dimension (os_version, region, ...)
// on every cycle instead of only after a platform-level detector has already
// fired. Mirrors the design validated live in the InMobi architecture docs
// (ARRAY JOIN pivot across the 9 categorical dimensions, AggregatingMergeTree
// with -State/-Merge so it can't accidentally be queried as plain columns).
// LEFT JOIN advertisers (not INNER) because advertiser_id is empty on unfilled
// rows — those rows still need to be pivoted into every other dimension.
func (c *Client) MigrateDimensionRollup(ctx context.Context) error {
	if err := c.conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS hourly_by_dimension (
			hour_ts         DateTime,
			dimension_name  LowCardinality(String) COMMENT 'one of: ad_format, app_category, publisher_tier, adv_vertical, campaign_type, region, country, device_model, os_version',
			dimension_value LowCardinality(String),
			requests_s      AggregateFunction(count),
			fills_s         AggregateFunction(sum, UInt8),
			imps_s          AggregateFunction(sum, UInt8),
			clicks_s        AggregateFunction(sum, UInt8),
			revenue_s       AggregateFunction(sum, Float64)
		) ENGINE = AggregatingMergeTree
		ORDER BY (dimension_name, dimension_value, hour_ts)
	`); err != nil {
		return fmt.Errorf("create hourly_by_dimension: %w", err)
	}

	if err := c.conn.Exec(ctx, dimensionRollupMVSelect(true)); err != nil {
		return fmt.Errorf("create mv_hourly_by_dimension: %w", err)
	}

	return nil
}

// BackfillDimensionRollupIfEmpty runs the one-time backfill for
// hourly_by_dimension. AggregatingMergeTree merges/sums state for a matching
// key rather than replacing it, so re-running this against a non-empty table
// would silently double-count — guarded by checking the table is empty first.
func (c *Client) BackfillDimensionRollupIfEmpty(ctx context.Context) error {
	empty, err := c.tableIsEmpty(ctx, "hourly_by_dimension")
	if err != nil {
		return fmt.Errorf("check hourly_by_dimension emptiness: %w", err)
	}
	if !empty {
		return nil // already backfilled
	}
	if err := c.conn.Exec(ctx, dimensionRollupMVSelect(false)); err != nil {
		return fmt.Errorf("backfill hourly_by_dimension: %w", err)
	}
	return nil
}

// dimensionRollupMVSelect returns the shared SELECT (the ARRAY JOIN pivot)
// wrapped either as a MATERIALIZED VIEW definition (asMV=true, fires on every
// future insert) or as a one-time INSERT INTO ... SELECT (asMV=false, backfill).
func dimensionRollupMVSelect(asMV bool) string {
	pivotSelect := `
SELECT
    toStartOfHour(e.event_time) AS hour_ts,
    dim.1 AS dimension_name,
    dim.2 AS dimension_value,
    countState()               AS requests_s,
    sumState(e.is_filled)      AS fills_s,
    sumState(e.is_impression)  AS imps_s,
    sumState(e.is_click)       AS clicks_s,
    sumState(e.revenue)        AS revenue_s
FROM ad_events e
LEFT JOIN apps a ON e.app_id = a.app_id
LEFT JOIN advertisers v ON e.advertiser_id = v.advertiser_id
LEFT JOIN geo_device g ON e.geo_device_id = g.geo_device_id
ARRAY JOIN [
    ('ad_format',      e.ad_format),
    ('app_category',   a.category),
    ('publisher_tier', a.publisher_tier),
    ('adv_vertical',   if(e.advertiser_id = '', 'unfilled', v.vertical)),
    ('campaign_type',  if(e.advertiser_id = '', 'unfilled', v.campaign_type)),
    ('region',         g.region),
    ('country',        g.country),
    ('device_model',   g.device_model),
    ('os_version',     g.os_version)
] AS dim
GROUP BY hour_ts, dimension_name, dimension_value
`
	if asMV {
		return "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_by_dimension TO hourly_by_dimension AS" + pivotSelect
	}
	return "INSERT INTO hourly_by_dimension" + pivotSelect
}

// Named converts alternating key-value pairs into clickhouse.Named args.
// Call: Named("key1", val1, "key2", val2, ...)
// This is required for {param:Type} syntax in SQL with the native protocol driver.
func Named(keysAndVals ...any) []any {
	if len(keysAndVals)%2 != 0 {
		panic("db.Named: must receive an even number of key-value arguments")
	}
	out := make([]any, 0, len(keysAndVals)/2)
	for i := 0; i < len(keysAndVals); i += 2 {
		key, _ := keysAndVals[i].(string)
		out = append(out, clickhouse.Named(key, keysAndVals[i+1]))
	}
	return out
}

// QueryRows executes a SELECT and returns results as a slice of column-name → value maps.
// Uses reflection via ScanType() so Date/DateTime columns are scanned correctly.
func (c *Client) QueryRows(ctx context.Context, sql string, args ...any) ([]map[string]any, error) {
	rows, err := c.conn.Query(ctx, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("query: %w", err)
	}
	defer rows.Close()

	colTypes := rows.ColumnTypes()
	n := len(colTypes)
	colNames := make([]string, n)
	scanTypes := make([]reflect.Type, n)
	for i, ct := range colTypes {
		colNames[i] = ct.Name()
		scanTypes[i] = ct.ScanType()
	}

	var result []map[string]any
	for rows.Next() {
		// Allocate a properly-typed pointer for each column
		ptrs := make([]any, n)
		for i, t := range scanTypes {
			ptrs[i] = reflect.New(t).Interface()
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, fmt.Errorf("scan row: %w", err)
		}
		row := make(map[string]any, n)
		for i, name := range colNames {
			// Dereference the scan pointer to get the actual value.
			// For Nullable(T) columns clickhouse-go scans into *T (a pointer);
			// dereference once more so callers always receive T or nil.
			val := reflect.ValueOf(ptrs[i]).Elem().Interface()
			if v := reflect.ValueOf(val); v.Kind() == reflect.Ptr {
				if v.IsNil() {
					row[name] = nil
				} else {
					row[name] = v.Elem().Interface()
				}
			} else {
				row[name] = val
			}
		}
		result = append(result, row)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows error: %w", err)
	}
	return result, nil
}

// QueryRow executes a SELECT expected to return exactly one row.
// Returns ErrNoRows if the result set is empty.
func (c *Client) QueryRow(ctx context.Context, sql string, args ...any) (map[string]any, error) {
	rows, err := c.QueryRows(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, ErrNoRows
	}
	return rows[0], nil
}

// Exec executes a statement that returns no rows (DDL, INSERT).
func (c *Client) Exec(ctx context.Context, sql string, args ...any) error {
	if err := c.conn.Exec(ctx, sql, args...); err != nil {
		return fmt.Errorf("exec: %w", err)
	}
	return nil
}

// BatchInsert inserts a slice of events in a single ClickHouse batch.
func (c *Client) BatchInsert(ctx context.Context, events []model.Event) error {
	batch, err := c.conn.PrepareBatch(ctx, "INSERT INTO events (source, event_type, payload, timestamp)")
	if err != nil {
		return fmt.Errorf("prepare batch: %w", err)
	}

	for i, e := range events {
		ts := e.Timestamp
		if ts.IsZero() {
			ts = time.Now().UTC()
		}
		if err := batch.Append(e.Source, e.EventType, e.Payload, ts); err != nil {
			return fmt.Errorf("append row %d: %w", i, err)
		}
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("send batch: %w", err)
	}
	return nil
}

// InsertRows inserts a slice of rows (as map[string]any) into the given table.
func (c *Client) InsertRows(ctx context.Context, table string, cols []string, rows []map[string]any) error {
	if len(rows) == 0 {
		return nil
	}

	quotedCols := make([]string, len(cols))
	for i, col := range cols {
		quotedCols[i] = "`" + strings.ReplaceAll(col, "`", "``") + "`"
	}
	query := fmt.Sprintf(
		"INSERT INTO `%s` (%s)",
		strings.ReplaceAll(table, "`", "``"),
		strings.Join(quotedCols, ", "),
	)

	batch, err := c.conn.PrepareBatch(ctx, query)
	if err != nil {
		return fmt.Errorf("prepare batch: %w", err)
	}

	for i, row := range rows {
		vals := make([]any, len(cols))
		for j, col := range cols {
			vals[j] = row[col]
		}
		if err := batch.Append(vals...); err != nil {
			return fmt.Errorf("append row %d: %w", i, err)
		}
	}

	return batch.Send()
}

// Close releases the underlying connection.
func (c *Client) Close() error {
	return c.conn.Close()
}
