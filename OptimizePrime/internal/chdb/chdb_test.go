package chdb_test

import (
	"context"
	"errors"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/d-cryptic/clickathon/internal/chdb"
	"github.com/d-cryptic/clickathon/internal/config"
)

// fakeConn embeds driver.Conn and implements only what chdb calls; an
// unexpected call panics, which is what a test wants.
type fakeConn struct {
	driver.Conn
	query    func(query string, args ...any) (driver.Rows, error)
	queryRow func(query string) driver.Row
}

func (c *fakeConn) Query(_ context.Context, query string, args ...any) (driver.Rows, error) {
	return c.query(query, args...)
}

func (c *fakeConn) QueryRow(_ context.Context, query string, _ ...any) driver.Row {
	return c.queryRow(query)
}

type fakeRow struct {
	scan func(dest ...any) error
}

func (r *fakeRow) Err() error                { return nil }
func (r *fakeRow) Scan(dest ...any) error    { return r.scan(dest...) }
func (r *fakeRow) ScanStruct(dest any) error { _ = dest; return errors.New("ScanStruct not modeled") }

// fakeRows serves a fixed set of table rows, with injectable scan and
// iteration errors.
type fakeRows struct {
	driver.Rows
	rows    [][3]any // name, engine, rows
	i       int
	scanErr error
	iterErr error
	closed  bool
}

func (r *fakeRows) Next() bool {
	if r.i >= len(r.rows) {
		return false
	}
	r.i++
	return true
}

func (r *fakeRows) Scan(dest ...any) error {
	if r.scanErr != nil {
		return r.scanErr
	}
	row := r.rows[r.i-1]
	*(dest[0].(*string)) = row[0].(string)
	*(dest[1].(*string)) = row[1].(string)
	*(dest[2].(*uint64)) = row[2].(uint64)
	return nil
}

func (r *fakeRows) Err() error   { return r.iterErr }
func (r *fakeRows) Close() error { r.closed = true; return nil }

func TestTables(t *testing.T) {
	t.Parallel()
	rows := &fakeRows{rows: [][3]any{
		{"cc_minute_delta", "MergeTree", uint64(34056)},
		{"ev_raw", "MergeTree", uint64(896400)},
		{"session_intervals", "MergeTree", uint64(121492)},
	}}
	conn := &fakeConn{query: func(query string, args ...any) (driver.Rows, error) {
		if !strings.Contains(query, "system.tables") {
			t.Errorf("Tables queried %q, want system.tables (not count(*) per table)", query)
		}
		if !strings.Contains(query, "ORDER BY name") {
			t.Errorf("Tables query %q lost its ORDER BY name — output order is part of the contract (deterministic verify output)", query)
		}
		if len(args) != 1 || args[0] != "sonyliv" {
			t.Errorf("Tables args = %v, want the database name as the single bound parameter", args)
		}
		return rows, nil
	}}

	got, err := chdb.Tables(context.Background(), conn, "sonyliv")
	if err != nil {
		t.Fatalf("Tables() error = %v, want nil", err)
	}
	want := []chdb.TableStat{
		{Name: "cc_minute_delta", Engine: "MergeTree", Rows: 34056},
		{Name: "ev_raw", Engine: "MergeTree", Rows: 896400},
		{Name: "session_intervals", Engine: "MergeTree", Rows: 121492},
	}
	if len(got) != len(want) {
		t.Fatalf("len(Tables()) = %d, want %d", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("Tables()[%d] = %+v, want %+v", i, got[i], want[i])
		}
	}
	if !rows.closed {
		t.Error("Tables() did not Close the rows — that leaks the HTTP response")
	}
}

func TestTablesErrors(t *testing.T) {
	t.Parallel()
	boom := errors.New("code: 81, database does not exist")
	cases := []struct {
		name    string
		conn    *fakeConn
		wantSub string
	}{
		{
			"query error",
			&fakeConn{query: func(string, ...any) (driver.Rows, error) { return nil, boom }},
			`query tables in "nope"`,
		},
		{
			"scan error",
			&fakeConn{query: func(string, ...any) (driver.Rows, error) {
				return &fakeRows{rows: [][3]any{{"t", "MergeTree", uint64(1)}}, scanErr: boom}, nil
			}},
			"scan table row",
		},
		{
			"iteration error",
			&fakeConn{query: func(string, ...any) (driver.Rows, error) {
				return &fakeRows{iterErr: boom}, nil
			}},
			"iterate tables",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			_, err := chdb.Tables(context.Background(), tc.conn, "nope")
			if err == nil {
				t.Fatal("Tables() error = nil, want failure")
			}
			if !errors.Is(err, boom) {
				t.Errorf("error %v does not wrap the driver error", err)
			}
			if !strings.Contains(err.Error(), tc.wantSub) {
				t.Errorf("error %q does not say which of the three calls failed (want %q)", err, tc.wantSub)
			}
		})
	}
}

func TestServerVersion(t *testing.T) {
	t.Parallel()
	conn := &fakeConn{queryRow: func(query string) driver.Row {
		if !strings.Contains(query, "version()") {
			t.Errorf("ServerVersion queried %q, want SELECT version()", query)
		}
		return &fakeRow{scan: func(dest ...any) error {
			*(dest[0].(*string)) = "25.8.1.1"
			return nil
		}}
	}}

	v, err := chdb.ServerVersion(context.Background(), conn)
	if err != nil {
		t.Fatalf("ServerVersion() error = %v, want nil", err)
	}
	if v != "25.8.1.1" {
		t.Errorf("ServerVersion() = %q, want 25.8.1.1", v)
	}
}

func TestServerVersionError(t *testing.T) {
	t.Parallel()
	boom := errors.New("connection reset")
	conn := &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(...any) error { return boom }}
	}}

	_, err := chdb.ServerVersion(context.Background(), conn)
	if !errors.Is(err, boom) {
		t.Errorf("ServerVersion() error = %v, want it to wrap the driver error", err)
	}
}

// closedPort returns a 127.0.0.1 port that was just listening and now is not —
// the closest thing to a guaranteed connection-refused endpoint.
func closedPort(t *testing.T) int {
	t.Helper()
	var lc net.ListenConfig
	l, err := lc.Listen(context.Background(), "tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("reserve port: %v", err)
	}
	port := l.Addr().(*net.TCPAddr).Port
	_ = l.Close()
	return port
}

// TestOpenUnreachable pins Open's contract that a dead endpoint fails AT OPEN
// (via the ping) with an error naming the address and user — not at the first
// query with something opaque. It never touches a real ClickHouse: the target
// is a loopback port nothing is listening on.
func TestOpenUnreachable(t *testing.T) {
	t.Parallel()
	for _, secure := range []bool{false, true} {
		cfg := config.ClickHouse{
			Host:     "127.0.0.1",
			Port:     closedPort(t),
			User:     "nobody",
			Password: "irrelevant",
			Database: "default",
			Secure:   secure,
			Target:   config.TargetLocal,
		}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		conn, err := chdb.Open(ctx, &cfg)
		cancel()
		if err == nil {
			_ = conn.Close()
			t.Fatalf("Open(secure=%t) to a closed port succeeded, want ping failure", secure)
		}
		if !strings.Contains(err.Error(), cfg.Addr()) || !strings.Contains(err.Error(), `"nobody"`) {
			t.Errorf("Open(secure=%t) error %q should name the address and user for diagnosis", secure, err)
		}
	}
}
