package fleet

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Sink is where generated events go.
//
// The fleet knows nothing about ClickHouse, HTTP or JSON — it hands over batches of
// rows and that is the entire contract. internal/mock implements this over the
// existing chx.Loader and APISink, so the fleet inherits their retry, deduplication
// -token and batch-audit behaviour rather than opening a third insert path.
type Sink interface {
	Send(ctx context.Context, rows []model.RawEvent) error
}

// Tuning for the run loop.
const (
	// sweepInterval is how often lease expiries are noticed and due heartbeats
	// emitted. Well below the 5s minimum cadence, so a tick is never missed, and
	// far cheaper than it looks: a sweep of 10,000 sessions is a map walk.
	sweepInterval = 250 * time.Millisecond

	// flushInterval and flushRows bound insert batching. One insert per second
	// beats one per event by three orders of magnitude at fleet scale — the
	// stepper's habit of building a fresh loader per event is exactly what this
	// avoids.
	flushInterval = time.Second
	flushRows     = 5000

	enqueueTimeout = 5 * time.Second

	// saveInterval is how often changed sessions are written to the Store. Five
	// seconds bounds what a crash can lose to five seconds of state, while keeping
	// the write rate far below the heartbeat rate — and only dirty sessions go, so
	// an idle fleet writes nothing at all.
	saveInterval = 5 * time.Second
)

// ErrQueueFull is returned when the write queue cannot accept a batch in time.
var ErrQueueFull = errors.New("event write queue is full; ClickHouse may be unreachable")

// WriteStats is the health of the write path, surfaced so the UI can explain a
// fleet line that has no ClickHouse line under it.
type WriteStats struct {
	Rows      uint64 `json:"rows"`
	Batches   uint64 `json:"batches"`
	Errors    uint64 `json:"errors"`
	LastError string `json:"last_error,omitempty"`
	Queued    int    `json:"queued"`
}

// Fleet is the registry plus the goroutine that drives it.
type Fleet struct {
	*Registry

	sink  Sink
	store Store
	out   chan []model.RawEvent

	mu    sync.Mutex
	stats WriteStats
}

// New builds a fleet. timeout is the liveness lease; it must match the pipeline's.
//
// store may be nil, in which case the fleet is memory-only and a restart loses its
// sessions. That is a supported mode, not a degraded one: the stepper and the load
// simulator have always worked that way, and a fleet driven for a five-minute demo
// does not need a table.
func New(sink Sink, store Store, timeout time.Duration, seed int64) *Fleet {
	return &Fleet{
		Registry: NewRegistry(timeout, seed),
		sink:     sink,
		store:    store,
		out:      make(chan []model.RawEvent, 1024),
	}
}

// Reconcile restores persisted sessions and catches them up to now.
//
// Called once at startup, before Run. Any events the catch-up produces — the
// VideoSessionEnd of a session whose TTL elapsed while the process was down — are
// written immediately rather than queued, because they are the reason the restored
// state is consistent and losing them would leave sessions ClickHouse still
// believes are open.
func (f *Fleet) Reconcile(ctx context.Context) (int, error) {
	if f.store == nil {
		return 0, nil
	}
	rows, err := f.store.Load(ctx)
	if err != nil {
		return 0, fmt.Errorf("load fleet state: %w", err)
	}
	events := f.Restore(rows, time.Now().UTC().Truncate(time.Millisecond))
	if len(events) > 0 {
		if err := f.sink.Send(ctx, events); err != nil {
			return len(rows), fmt.Errorf("write catch-up events: %w", err)
		}
	}
	// Persist whatever the catch-up changed, so a crash loop does not replay the
	// same expiries into events_raw on every restart.
	f.persist(ctx)
	return len(rows), nil
}

// ClearEnded drops ended sessions and tombstones them in the store.
//
// Overrides the Registry method of the same name so the store cannot keep handing
// back rows the operator already cleared — without the tombstone, the next restart
// would resurrect every session the list was emptied of.
// Returns the count cleared and any tombstone-write error.
//
// The error is returned rather than only logged, because a tombstone that did not
// land is not a logging concern: the sessions are gone from memory but still live
// in the store, so the next restart resurrects every one of them. Reporting
// "removed 103,470" while the durable state disagrees is the failure mode that
// hid this for two restarts.
func (f *Fleet) ClearEnded(ctx context.Context) (int, error) {
	ids := f.Registry.RemoveEnded()
	if len(ids) == 0 || f.store == nil {
		return len(ids), nil
	}
	if err := f.store.Save(ctx, removedRows(ids, time.Now().UTC())); err != nil {
		log.Printf("fleet: tombstone %d cleared sessions: %v", len(ids), err)
		return len(ids), fmt.Errorf("cleared %d sessions in memory but the tombstones did not land, "+
			"so they will return on restart: %w", len(ids), err)
	}
	return len(ids), nil
}

// PersistNow flushes changed sessions immediately instead of waiting for the tick.
//
// Called right after a create. The comparison query scopes itself from
// fleet_sessions, so a session that exists in memory but not yet in the table is
// invisible to the ClickHouse line while the fleet line already counts it — a gap
// that looks like a pipeline defect and is really a five-second write delay.
// Identity is what the scope needs, and identity is fixed at create, so this is
// the only point that needs forcing.
func (f *Fleet) PersistNow(ctx context.Context) { f.persist(ctx) }

// persist writes changed sessions to the store, if there is one.
func (f *Fleet) persist(ctx context.Context) {
	if f.store == nil {
		return
	}
	rows := f.snapshot()
	if len(rows) == 0 {
		return
	}
	sctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 30*time.Second)
	defer cancel()
	if err := f.store.Save(sctx, rows); err != nil {
		log.Printf("fleet: persist %d sessions: %v", len(rows), err)
	}
}

// Emit queues rows produced by an HTTP handler.
//
// Bounded wait rather than a non-blocking send: silently dropping events would make
// the fleet's own curve disagree with ClickHouse for a reason that is invisible in
// both, which is the one failure this whole design exists to detect. Better to fail
// the request and say so.
func (f *Fleet) Emit(ctx context.Context, rows []model.RawEvent) error {
	if len(rows) == 0 {
		return nil
	}
	select {
	case f.out <- rows:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(enqueueTimeout):
		return ErrQueueFull
	}
}

// Run drives the fleet until ctx is cancelled.
//
// One goroutine owns both the sweep and the write buffer, so the buffer needs no
// lock and there is no ordering question between a sweep's heartbeats and a
// handler's commands. Rows are always appended in the order they were produced.
func (f *Fleet) Run(ctx context.Context) {
	sweep := time.NewTicker(sweepInterval)
	defer sweep.Stop()
	flush := time.NewTicker(flushInterval)
	defer flush.Stop()
	save := time.NewTicker(saveInterval)
	defer save.Stop()

	buf := make([]model.RawEvent, 0, flushRows)

	// Flush with a context that outlives cancellation, so the final partial batch
	// still lands on shutdown instead of being discarded.
	send := func(rows []model.RawEvent) {
		if len(rows) == 0 {
			return
		}
		sctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), 2*time.Minute)
		defer cancel()

		err := f.sink.Send(sctx, rows)
		f.mu.Lock()
		if err != nil {
			f.stats.Errors++
			f.stats.LastError = err.Error()
			log.Printf("fleet: write %d rows: %v", len(rows), err)
		} else {
			f.stats.Rows += uint64(len(rows))
			f.stats.Batches++
		}
		f.mu.Unlock()
	}

	for {
		select {
		case <-ctx.Done():
			send(buf)
			// Final persist on the way out, so a clean shutdown loses nothing.
			f.persist(ctx)
			return

		case <-save.C:
			f.persist(ctx)
			continue

		case <-sweep.C:
			buf = append(buf, f.Sweep(time.Now().UTC().Truncate(time.Millisecond))...)

		case rows := <-f.out:
			buf = append(buf, rows...)

		case <-flush.C:
			if len(buf) > 0 {
				send(buf)
				buf = buf[:0]
			}
			continue
		}

		// Size-triggered flush, in bounded chunks. Without the loop a create of
		// 100,000 sessions would arrive as one 200,000-row slice and go out as a
		// single insert; the chunking keeps every insert the same shape whether it
		// came from a heartbeat tick or a bulk create.
		for len(buf) >= flushRows {
			send(buf[:flushRows])
			buf = append(buf[:0], buf[flushRows:]...)
		}
	}
}

// WriteStats reports the write path's health.
func (f *Fleet) WriteStats() WriteStats {
	f.mu.Lock()
	defer f.mu.Unlock()
	s := f.stats
	s.Queued = len(f.out)
	return s
}
