package chx

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// AuditWriter buffers control-plane rows (batch audit, rejects) and flushes
// them on a timer.
//
// These rows arrive one at a time and are worth a few hundred bytes each — the
// exact shape client-side batching cannot fix, because there is nothing to
// batch with. Two mechanisms are stacked:
//
//   - a small in-process buffer, so a run producing thousands of batches does
//     not issue thousands of single-row INSERTs; and
//   - async_insert=1 with wait_for_async_insert=1 on the flush, so ClickHouse
//     coalesces what still arrives in dribs into properly sized parts and still
//     confirms durability before returning.
//
// wait_for_async_insert stays at 1 on purpose. Fire-and-forget would hide
// exactly the failures this table exists to record.
// [official: insert-async-small-batches]
type AuditWriter struct {
	client        *Client
	flushInterval time.Duration
	maxBuffered   int

	mu      sync.Mutex
	batches []model.BatchAudit
	rejects []model.Reject
	// retryAfter suppresses the size-triggered flush for one interval after a
	// failure. Without it, an outage turns every Add past the high-water mark
	// into its own doomed round trip and the load crawls.
	retryAfter time.Time
	// Rows discarded because retention filled up. Reported by Close: an
	// incomplete audit trail must be stated, not inferred from a short table.
	droppedBatches int
	droppedRejects int

	stop chan struct{}
	done chan struct{}

	errMu   sync.Mutex
	lastErr error
}

// maxRetained bounds what a failing flush may hold. Rows are kept across
// failures so the audit and quarantine trail survives a transient outage —
// which is precisely when it is worth having — but a permanent one must not
// grow the buffer without limit.
const maxRetained = 10000

// NewAuditWriter starts the background flusher. Call Close to drain it.
func NewAuditWriter(ctx context.Context, client *Client) *AuditWriter {
	w := &AuditWriter{
		client:        client,
		flushInterval: 2 * time.Second,
		maxBuffered:   1000,
		stop:          make(chan struct{}),
		done:          make(chan struct{}),
	}
	go w.loop(ctx)
	return w
}

// Add queues one batch-audit row.
func (w *AuditWriter) Add(b model.BatchAudit) {
	w.mu.Lock()
	w.batches = append(w.batches, b)
	over := len(w.batches) >= w.maxBuffered && time.Now().After(w.retryAfter)
	w.mu.Unlock()
	if over {
		if err := w.Flush(context.Background()); err != nil {
			w.setErr(err)
		}
	}
}

// AddReject queues one quarantined source row.
func (w *AuditWriter) AddReject(r model.Reject) {
	w.mu.Lock()
	w.rejects = append(w.rejects, r)
	over := len(w.rejects) >= w.maxBuffered && time.Now().After(w.retryAfter)
	w.mu.Unlock()
	if over {
		if err := w.Flush(context.Background()); err != nil {
			w.setErr(err)
		}
	}
}

func (w *AuditWriter) loop(ctx context.Context) {
	defer close(w.done)
	t := time.NewTicker(w.flushInterval)
	defer t.Stop()
	for {
		select {
		case <-w.stop:
			return
		case <-ctx.Done():
			return
		case <-t.C:
			if err := w.Flush(ctx); err != nil {
				w.setErr(err)
			}
		}
	}
}

// Flush writes everything currently buffered.
//
// Rows that fail to send go back into the buffer rather than being dropped.
// This table is the record of what went wrong during a load, so discarding it
// on the first ClickHouse hiccup would delete the evidence at exactly the
// moment it becomes interesting. The two tables are sent independently: a
// failure on one must not lose the other.
func (w *AuditWriter) Flush(ctx context.Context) error {
	w.mu.Lock()
	batches, rejects := w.batches, w.rejects
	w.batches, w.rejects = nil, nil
	w.mu.Unlock()

	if len(batches) == 0 && len(rejects) == 0 {
		return nil
	}

	bctx := clickhouse.Context(ctx, clickhouse.WithSettings(clickhouse.Settings{
		"async_insert":          1,
		"wait_for_async_insert": 1,
	}))

	batchErr := sendRows(bctx, w.client, "ingest_batches", model.BatchAuditInsertColumns, batches)
	rejectErr := sendRows(bctx, w.client, "ingest_rejects", model.RejectInsertColumns, rejects)
	if batchErr == nil && rejectErr == nil {
		return nil
	}

	w.mu.Lock()
	if batchErr != nil {
		w.batches, w.droppedBatches = requeue(batches, w.batches, w.droppedBatches)
	}
	if rejectErr != nil {
		w.rejects, w.droppedRejects = requeue(rejects, w.rejects, w.droppedRejects)
	}
	w.retryAfter = time.Now().Add(w.flushInterval)
	w.mu.Unlock()

	return errors.Join(batchErr, rejectErr)
}

// requeue puts unsent rows back ahead of whatever arrived while the flush was
// in flight, keeping the trail in order, and trims the oldest past the
// retention bound.
func requeue[T any](unsent, queued []T, dropped int) ([]T, int) {
	out := append(unsent, queued...)
	if over := len(out) - maxRetained; over > 0 {
		out = out[over:]
		dropped += over
	}
	return out, dropped
}

// rowValues is satisfied by the control-plane row types, whose Values method
// has a pointer receiver.
type rowValues[T any] interface {
	*T
	Values() []any
}

// sendRows writes one control-plane table. An empty slice is not an error.
func sendRows[T any, P rowValues[T]](ctx context.Context, c *Client, table string, cols []string, rows []T) error {
	if len(rows) == 0 {
		return nil
	}
	b, err := c.Conn.PrepareBatch(ctx, insertStatement(c.Database, table, cols))
	if err != nil {
		return fmt.Errorf("prepare %s batch: %w", table, err)
	}
	for i := range rows {
		if err := b.Append(P(&rows[i]).Values()...); err != nil {
			_ = b.Abort()
			return fmt.Errorf("append %s row: %w", table, err)
		}
	}
	if err := b.Send(); err != nil {
		return fmt.Errorf("send %s batch: %w", table, err)
	}
	return nil
}

// Close stops the flusher and drains the buffer.
//
// Anything still unsent, or dropped past the retention bound, is reported: a
// caller that is told the audit trail is complete when it is not would draw
// the wrong conclusion from a short table.
func (w *AuditWriter) Close(ctx context.Context) error {
	close(w.stop)
	<-w.done

	flushErr := w.Flush(ctx)

	w.mu.Lock()
	unsent := len(w.batches) + len(w.rejects)
	dropped := w.droppedBatches + w.droppedRejects
	w.mu.Unlock()

	var incomplete error
	if unsent > 0 || dropped > 0 {
		incomplete = fmt.Errorf("audit trail incomplete: %d row(s) never sent, %d dropped past the %d-row retention bound",
			unsent, dropped, maxRetained)
	}

	w.errMu.Lock()
	lastErr := w.lastErr
	w.errMu.Unlock()

	return errors.Join(flushErr, incomplete, lastErr)
}

func (w *AuditWriter) setErr(err error) {
	w.errMu.Lock()
	w.lastErr = err
	w.errMu.Unlock()
}
