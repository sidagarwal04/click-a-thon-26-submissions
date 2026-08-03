// Package chdb opens ClickHouse connections from a config.ClickHouse.
//
// It speaks the HTTP protocol on CH_PORT rather than the native protocol on
// 9440. That is deliberate: the bash tools already use HTTP on CH_PORT, and a
// single port in .env means there is no way for the Go and shell paths to end
// up pointing at different endpoints.
package chdb

import (
	"context"
	"crypto/tls"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/d-cryptic/clickathon/internal/config"
)

// Open connects and verifies the connection with a ping, so a bad host or
// password fails here rather than at the first query.
func Open(ctx context.Context, cfg *config.ClickHouse) (driver.Conn, error) {
	opts := &clickhouse.Options{
		Addr:     []string{cfg.Addr()},
		Protocol: clickhouse.HTTP,
		Auth: clickhouse.Auth{
			Database: cfg.Database,
			Username: cfg.User,
			Password: cfg.Password,
		},
		DialTimeout: 10 * time.Second,
		// Compression is worth it here: the benchmark shapes pull minute-grain
		// rows over the public internet from a Cloud service.
		Compression: &clickhouse.Compression{Method: clickhouse.CompressionLZ4},
		ClientInfo: clickhouse.ClientInfo{
			Products: []struct {
				Name    string
				Version string
			}{{Name: "sonyliv-concurrency", Version: "0.1.0"}},
		},
	}
	if cfg.Secure {
		opts.TLS = &tls.Config{MinVersion: tls.VersionTLS12}
	}

	conn, err := clickhouse.Open(opts)
	if err != nil {
		return nil, fmt.Errorf("open clickhouse at %s: %w", cfg.Addr(), err)
	}
	if err := conn.Ping(ctx); err != nil {
		_ = conn.Close()
		return nil, fmt.Errorf("ping clickhouse at %s as %q: %w", cfg.Addr(), cfg.User, err)
	}
	return conn, nil
}

// TableStat is one row of the table inventory shown by `sonyliv verify`.
type TableStat struct {
	Name   string
	Engine string
	Rows   uint64
}

// Tables lists the tables in the configured database with their live row counts.
//
// Row counts come from system.tables.total_rows, not count(), so this stays
// cheap on a table with a billion rows.
func Tables(ctx context.Context, conn driver.Conn, database string) ([]TableStat, error) {
	const q = `
		SELECT name, engine, ifNull(total_rows, 0) AS rows
		FROM system.tables
		WHERE database = ?
		ORDER BY name`

	rows, err := conn.Query(ctx, q, database)
	if err != nil {
		return nil, fmt.Errorf("query tables in %q: %w", database, err)
	}
	defer func() { _ = rows.Close() }()

	var out []TableStat
	for rows.Next() {
		var t TableStat
		if err := rows.Scan(&t.Name, &t.Engine, &t.Rows); err != nil {
			return nil, fmt.Errorf("scan table row: %w", err)
		}
		out = append(out, t)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate tables: %w", err)
	}
	return out, nil
}

// ServerVersion returns the server version string, for the evidence trail.
func ServerVersion(ctx context.Context, conn driver.Conn) (string, error) {
	var v string
	if err := conn.QueryRow(ctx, "SELECT version()").Scan(&v); err != nil {
		return "", fmt.Errorf("select version(): %w", err)
	}
	return v, nil
}
