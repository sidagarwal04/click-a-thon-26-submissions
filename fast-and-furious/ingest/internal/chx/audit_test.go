package chx

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// failingConn fails every PrepareBatch. Only that one method is reachable from
// the code under test, so the embedded nil interface is never dereferenced.
type failingConn struct {
	driver.Conn
	calls int
}

func (f *failingConn) PrepareBatch(context.Context, string, ...driver.PrepareBatchOption) (driver.Batch, error) {
	f.calls++
	return nil, errors.New("connection refused")
}

func newTestWriter(conn driver.Conn) *AuditWriter {
	// Constructed directly rather than via NewAuditWriter: the background
	// flusher would race the assertions.
	return &AuditWriter{
		client:      &Client{Conn: conn, Database: "default"},
		maxBuffered: 1000,
		stop:        make(chan struct{}),
		done:        make(chan struct{}),
	}
}

// TestFlushKeepsRowsWhenTheInsertFails is the reason this buffer exists.
//
// These two tables are the record of what went wrong during a load. Dropping
// them because ClickHouse was briefly unreachable deletes the evidence at
// exactly the moment it becomes worth having, and leaves a short table that
// reads as "nothing went wrong".
func TestFlushKeepsRowsWhenTheInsertFails(t *testing.T) {
	conn := &failingConn{}
	w := newTestWriter(conn)

	w.Add(model.BatchAudit{Source: "csv:raw.csv"})
	w.AddReject(model.Reject{Source: "csv:raw.csv", SourceLine: 42})

	if err := w.Flush(context.Background()); err == nil {
		t.Fatal("Flush reported success while both inserts failed")
	}

	w.mu.Lock()
	nb, nr := len(w.batches), len(w.rejects)
	w.mu.Unlock()
	if nb != 1 || nr != 1 {
		t.Fatalf("after a failed flush: %d batch row(s) and %d reject row(s) retained, want 1 and 1", nb, nr)
	}

	// Both tables must have been attempted — a failure on one must not skip
	// the other, or a working table silently loses rows with a broken one.
	if conn.calls != 2 {
		t.Errorf("PrepareBatch called %d time(s), want 2 (one per table)", conn.calls)
	}
}

// TestFlushOrdersRetriedRowsFirst: rows queued while a flush was in flight must
// not jump ahead of the ones it failed to send.
func TestFlushOrdersRetriedRowsFirst(t *testing.T) {
	w := newTestWriter(&failingConn{})

	w.Add(model.BatchAudit{Source: "first"})
	_ = w.Flush(context.Background())
	w.Add(model.BatchAudit{Source: "second"})

	w.mu.Lock()
	defer w.mu.Unlock()
	if len(w.batches) != 2 {
		t.Fatalf("buffered %d rows, want 2", len(w.batches))
	}
	if w.batches[0].Source != "first" || w.batches[1].Source != "second" {
		t.Errorf("order is %q, %q; want the retried row first",
			w.batches[0].Source, w.batches[1].Source)
	}
}

// TestRetentionIsBounded: keeping rows across failures must not turn a
// permanent outage into unbounded memory growth.
func TestRetentionIsBounded(t *testing.T) {
	unsent := make([]int, maxRetained)
	queued := make([]int, 50)
	for i := range unsent {
		unsent[i] = i
	}
	for i := range queued {
		queued[i] = maxRetained + i
	}

	out, dropped := requeue(unsent, queued, 0)
	if len(out) != maxRetained {
		t.Errorf("retained %d rows, want the %d-row bound", len(out), maxRetained)
	}
	if dropped != 50 {
		t.Errorf("dropped %d rows, want 50", dropped)
	}
	// The oldest go first, and the newest arrival is still there.
	if out[0] != 50 {
		t.Errorf("oldest retained row is %d, want 50", out[0])
	}
	if out[len(out)-1] != maxRetained+49 {
		t.Errorf("newest retained row is %d, want %d", out[len(out)-1], maxRetained+49)
	}
}

// TestCloseReportsAnIncompleteTrail: a caller told the load succeeded while
// audit rows never landed would draw the wrong conclusion from the table.
func TestCloseReportsAnIncompleteTrail(t *testing.T) {
	w := newTestWriter(&failingConn{})
	close(w.done) // stand in for the flusher goroutine

	w.Add(model.BatchAudit{Source: "csv:raw.csv"})

	err := w.Close(context.Background())
	if err == nil {
		t.Fatal("Close reported success with a row still unsent")
	}
	if !strings.Contains(err.Error(), "audit trail incomplete") {
		t.Errorf("error does not say the trail is incomplete: %v", err)
	}
}

// TestCloseIsQuietWhenEverythingLanded guards against the opposite failure: a
// warning on every clean run trains the operator to ignore it.
func TestCloseIsQuietWhenEverythingLanded(t *testing.T) {
	w := newTestWriter(&failingConn{})
	close(w.done)

	if err := w.Close(context.Background()); err != nil {
		t.Errorf("Close on an empty writer returned %v, want nil", err)
	}
}

func TestValidateWritePath(t *testing.T) {
	// A negative worker count reaches make(chan, workers*2) before NewLoader
	// can normalize it, and a negative channel capacity panics.
	if err := ValidateWritePath(-1, 3); err == nil {
		t.Error("--workers -1 was accepted; it panics at channel allocation")
	}
	if err := ValidateWritePath(0, 3); err == nil {
		t.Error("--workers 0 was accepted; it would stall with no writers")
	}
	if err := ValidateWritePath(6, -1); err == nil {
		t.Error("--retries -1 was accepted")
	}
	if err := ValidateWritePath(1, 0); err != nil {
		t.Errorf("the minimum valid write path was rejected: %v", err)
	}
}
