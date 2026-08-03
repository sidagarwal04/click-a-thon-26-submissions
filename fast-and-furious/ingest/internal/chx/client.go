// Package chx wraps the ClickHouse native client with the insert strategy this
// pipeline commits to: large client-side batches over the native protocol for
// bulk event data, server-side async buffering only for the small control rows
// that genuinely cannot be batched.
package chx

import (
	"context"
	"crypto/tls"
	"fmt"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/sonyliv-clickathon/ingest/internal/config"
)

// Version is reported to ClickHouse so this pipeline's queries are identifiable
// in system.query_log — which is where the latency evidence comes from.
const Version = "1.0.0"

// Client is a connected ClickHouse handle.
type Client struct {
	Conn     driver.Conn
	Database string

	// user/password are retained only to substitute into the content
	// dictionary's SOURCE clause, which authenticates even against a table on
	// the same server. They are never logged.
	user     string
	password string
}

// Open dials ClickHouse over the native protocol.
//
// Two settings choices worth stating explicitly:
//
//   - Compression is LZ4. The event payload is highly repetitive (93% heartbeat
//     rows, 10 distinct platforms, one country) so wire compression is close to
//     free CPU for a large bandwidth win, which matters on a Cloud service.
//
//   - async_insert is forced to 0 at the connection level, as a conservative
//     default only. ClickHouse Cloud enables async inserts by default (measured
//     on 26.2: value=1, default=1, changed=0), which is right for small writers
//     and wrong for a 50K-row native block, where the server-side buffer adds a
//     copy and a flush delay for no benefit.
//
//     This is a floor, not a policy. Every insert path states its own choice
//     per write and overrides it: the event loader decides per chunk in
//     insertSettings (loader.go) — sub-floor chunks go async so the server can
//     coalesce them into properly sized parts — and the control-plane writer
//     (ingest_batches, ingest_rejects) is always async because its rows arrive
//     one at a time and cannot be batched client-side.
//     [official: insert-batch-size, insert-async-small-batches]
func Open(ctx context.Context, cfg *config.Config) (*Client, error) {
	opts := &clickhouse.Options{
		Addr: []string{cfg.Addr()},
		Auth: clickhouse.Auth{
			Database: cfg.Database,
			Username: cfg.User,
			Password: cfg.Password,
		},
		Compression:  &clickhouse.Compression{Method: clickhouse.CompressionLZ4},
		DialTimeout:  cfg.DialTimeout,
		ReadTimeout:  cfg.ReadTimeout,
		MaxOpenConns: cfg.MaxOpenConns,
		MaxIdleConns: cfg.MaxOpenConns,
		Settings: clickhouse.Settings{
			"async_insert": 0,
		},
		ClientInfo: clickhouse.ClientInfo{
			Products: []struct {
				Name    string
				Version string
			}{
				{Name: "sonyliv-ingest", Version: Version},
			},
		},
	}
	if cfg.Secure {
		opts.TLS = &tls.Config{MinVersion: tls.VersionTLS12}
	}

	conn, err := clickhouse.Open(opts)
	if err != nil {
		return nil, fmt.Errorf("open clickhouse %s: %w", cfg.Redacted(), err)
	}
	if err := conn.Ping(ctx); err != nil {
		_ = conn.Close()
		return nil, fmt.Errorf("ping clickhouse %s: %w", cfg.Redacted(), err)
	}
	return &Client{
		Conn:     conn,
		Database: cfg.Database,
		user:     cfg.User,
		password: cfg.Password,
	}, nil
}

// Close releases the connection pool.
func (c *Client) Close() error { return c.Conn.Close() }

// ServerVersion reports the server build, recorded in run output so a result
// can be tied to the engine that produced it.
func (c *Client) ServerVersion(ctx context.Context) (string, error) {
	var v string
	if err := c.Conn.QueryRow(ctx, "SELECT version()").Scan(&v); err != nil {
		return "", err
	}
	return v, nil
}

// CountRows returns the row count of a table, or an error if it does not exist.
func (c *Client) CountRows(ctx context.Context, table string) (uint64, error) {
	var n uint64
	q := fmt.Sprintf("SELECT count() FROM %s.%s", c.Database, table)
	if err := c.Conn.QueryRow(ctx, q).Scan(&n); err != nil {
		return 0, fmt.Errorf("count %s: %w", table, err)
	}
	return n, nil
}

// Named binds a value to a {name:Type} query parameter.
//
// Positional ? binding is enough for the short queries in this package, but the
// concurrency rollups are long enough that positional arguments become a counting
// exercise, and they reference the same parameter more than once — which ? cannot
// express at all. Re-exported here so callers bind parameters through chx rather
// than importing the driver directly, which is the boundary the rest of this
// package maintains.
func Named(name string, value any) driver.NamedValue {
	return clickhouse.Named(name, value)
}
