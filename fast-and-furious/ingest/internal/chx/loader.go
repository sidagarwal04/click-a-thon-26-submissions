package chx

import (
	"context"
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// batchNamespace seeds the deterministic batch UUIDs. A fixed namespace means
// the same (source, fingerprint, ordinal) always yields the same batch id, on
// any machine, in any run — which is what makes a replay idempotent rather than
// merely repeatable.
var batchNamespace = uuid.MustParse("6f1b0a2e-6a9f-4f1a-9a2b-3c4d5e6f7a80")

// AsyncInsertRowThreshold is the chunk size below which a write is routed
// through ClickHouse's server-side async buffer instead of becoming its own
// part. It matches the 1,000-row floor that --batch-size already refuses to go
// below; the difference is that a timer flush cannot bypass this one.
const AsyncInsertRowThreshold = 1000

// Chunk is one INSERT's worth of rows.
//
// Chunks are cut by the *reader*, at fixed row counts and in source order, not
// by whichever worker happens to be free. That is the whole idempotency story:
// chunk N contains the same rows no matter how many workers are running, so its
// deduplication token identifies the same bytes on every replay.
type Chunk struct {
	Ordinal uint32
	Rows    []model.RawEvent
}

// LoaderOptions configures a raw-event load.
type LoaderOptions struct {
	// Source labels the origin, e.g. "csv:ch-hackathon-raw-data.csv".
	Source string
	// RunID groups every batch of one invocation.
	RunID uuid.UUID
	// Fingerprint is the SHA-256 of the source file, or the generator seed.
	// It participates in the dedup token so re-loading *different* data under
	// the same source name is not silently swallowed as a duplicate.
	Fingerprint string

	// BatchSize is the row count the producer cuts chunks at. It participates
	// in the deduplication token because the token must identify the *bytes of
	// this batch*: the same source re-loaded at a different batch size produces
	// the same rows in different chunks, and without this, chunk N of the second
	// run would be deduplicated against the differently-populated chunk N of the
	// first and its rows would be silently lost.
	BatchSize int

	// Workers is the number of concurrent INSERT streams.
	Workers int
	// MaxRetries is the number of additional attempts after a failed send.
	MaxRetries int
	// AsyncInsert routes batches through the server-side async buffer. Correct
	// only when batches are small; see Loader.Run.
	AsyncInsert bool

	// Audit receives one row per acknowledged batch. May be nil.
	Audit *AuditWriter
	// Progress is called periodically with a snapshot. May be nil.
	Progress func(Stats)
}

// Stats is a point-in-time view of loader progress.
type Stats struct {
	Rows       uint64
	Batches    uint64
	Retries    uint64
	Elapsed    time.Duration
	RowsPerSec float64
	InsertP50  time.Duration
	InsertP99  time.Duration
	InsertMax  time.Duration
}

func (s Stats) String() string {
	return fmt.Sprintf(
		"%d rows in %d batches | %.0f rows/s | insert p50=%s p99=%s max=%s | retries=%d | %s",
		s.Rows, s.Batches, s.RowsPerSec,
		s.InsertP50.Round(time.Millisecond),
		s.InsertP99.Round(time.Millisecond),
		s.InsertMax.Round(time.Millisecond),
		s.Retries, s.Elapsed.Round(time.Millisecond),
	)
}

// Loader fans chunks out across concurrent INSERT streams.
type Loader struct {
	client *Client
	opts   LoaderOptions

	rows    atomic.Uint64
	batches atomic.Uint64
	retries atomic.Uint64

	mu        sync.Mutex
	durations []time.Duration
	started   time.Time
}

// ValidateWritePath rejects flag values the write path cannot survive.
//
// NewLoader normalizes non-positive worker counts, but it never gets the
// chance: both commands size the chunk channel from the same flag first, and
// make(chan T, n) with a negative n is a runtime panic, not an error. Checked
// at the flag boundary so the user gets a message instead of a stack trace.
func ValidateWritePath(workers, retries int) error {
	if workers < 1 {
		return fmt.Errorf("--workers must be at least 1, got %d", workers)
	}
	if retries < 0 {
		return fmt.Errorf("--retries cannot be negative, got %d", retries)
	}
	return nil
}

// NewLoader builds a loader with sane defaults filled in.
func NewLoader(client *Client, opts LoaderOptions) *Loader {
	if opts.Workers <= 0 {
		opts.Workers = 4
	}
	if opts.MaxRetries < 0 {
		opts.MaxRetries = 0
	}
	if opts.RunID == uuid.Nil {
		opts.RunID = uuid.New()
	}
	return &Loader{client: client, opts: opts, started: time.Now()}
}

// Run consumes chunks until the channel closes or the context is cancelled.
//
// Insert strategy, and why:
//
//   - Each chunk becomes exactly one INSERT over the native protocol, carrying
//     a columnar block. Native is the cheapest format to parse server-side, and
//     the producer here can batch naturally, which is precisely the condition
//     under which direct batched inserts beat every alternative.
//     [official: insert-batch-size, insert-format-native,
//     decision-ingestion-strategy — "producers can batch -> direct inserts"]
//
//   - Buffer tables are deliberately NOT used. They hold rows in RAM and lose
//     them on restart, they sit outside insert deduplication so a retry
//     duplicates, and a materialized view attached to a Buffer table does not
//     fire on insert. Client-side batching already produces well-sized parts,
//     so a Buffer table would add a failure mode and buy nothing.
//
//   - AsyncInsert is offered for the case the rule actually covers: a producer
//     that cannot batch. It always waits for the flush; fire-and-forget trades
//     away error visibility for throughput this pipeline does not need.
//     [official: insert-async-small-batches]
//
//   - Every attempt reuses the same insert_deduplication_token. A send that
//     fails after the server committed the block is therefore a no-op on retry
//     rather than a duplicate — the one case where "just retry" is otherwise
//     silently wrong.
func (l *Loader) Run(ctx context.Context, chunks <-chan *Chunk) (Stats, error) {
	l.started = time.Now()

	var (
		wg      sync.WaitGroup
		errOnce sync.Once
		runErr  error
	)
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	fail := func(err error) {
		errOnce.Do(func() {
			runErr = err
			cancel()
		})
	}

	// Progress reporting is a side channel; it must never gate ingestion.
	if l.opts.Progress != nil {
		done := make(chan struct{})
		defer close(done)
		go func() {
			t := time.NewTicker(2 * time.Second)
			defer t.Stop()
			for {
				select {
				case <-done:
					return
				case <-ctx.Done():
					return
				case <-t.C:
					l.opts.Progress(l.Stats())
				}
			}
		}()
	}

	for w := 0; w < l.opts.Workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for chunk := range chunks {
				if ctx.Err() != nil {
					return
				}
				if err := l.sendChunk(ctx, chunk); err != nil {
					fail(err)
					return
				}
			}
		}()
	}

	wg.Wait()

	// Drain anything the reader is still trying to hand over, so a failed run
	// does not deadlock the producer goroutine.
	if runErr != nil {
		go func() {
			for range chunks {
			}
		}()
	}
	return l.Stats(), runErr
}

// sendChunk writes one chunk, retrying with the same deduplication token.
func (l *Loader) sendChunk(ctx context.Context, chunk *Chunk) error {
	if len(chunk.Rows) == 0 {
		return nil
	}

	token := l.dedupToken(chunk.Ordinal, len(chunk.Rows))
	batchID := uuid.NewSHA1(batchNamespace, []byte(token))

	firstEvent, lastEvent := chunk.Rows[0].EventTimestamp, chunk.Rows[0].EventTimestamp
	for i := range chunk.Rows {
		chunk.Rows[i].IngestBatchID = batchID
		chunk.Rows[i].BatchRowSeq = uint32(i)
		// Stamped here rather than by the reader: the batch address and the
		// origin label are properties of the write, not of the parsed row.
		chunk.Rows[i].SourceFile = l.opts.Source
		if t := chunk.Rows[i].EventTimestamp; t.Before(firstEvent) {
			firstEvent = t
		} else if t.After(lastEvent) {
			lastEvent = t
		}
	}

	settings := insertSettings(token, len(chunk.Rows), l.opts.AsyncInsert)

	stmt := insertStatement(l.client.Database, "events_raw", model.InsertColumns)

	var lastErr error
	started := time.Now()

	for attempt := 1; attempt <= l.opts.MaxRetries+1; attempt++ {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if attempt > 1 {
			l.retries.Add(1)
			backoff := time.Duration(attempt-1) * 500 * time.Millisecond
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
		}

		attemptStart := time.Now()
		err := l.sendOnce(ctx, stmt, settings, chunk.Rows)
		if err == nil {
			dur := time.Since(attemptStart)
			l.record(uint64(len(chunk.Rows)), dur)
			l.writeAudit(chunk, batchID, token, uint8(attempt), firstEvent, lastEvent, started, "ok", "")
			return nil
		}
		lastErr = err
		// A cancelled Send is NOT a failed write, and must not be audited as
		// one. clickhouse-go's contextWatchdog closes the socket on cancel and
		// returns ctx.Err(), discarding whatever the server replied — so the
		// block may well have committed. Measured on all three occurrences of
		// the 2026-08-01 run: every row of every batch recorded 'failed' was
		// present in events_raw (3/3, 24/24, 51/51). Calling that 'failed'
		// makes the audit ledger under-report, which is precisely the
		// silent-wrong-answer class this repo exists to avoid.
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			l.writeAudit(chunk, batchID, token, uint8(attempt), firstEvent, lastEvent, started,
				"unknown", err.Error())
			return fmt.Errorf("batch %d (%d rows) interrupted, commit state unknown "+
				"(reconcile _ingest_batch_id %s against events_raw): %w",
				chunk.Ordinal, len(chunk.Rows), batchID, err)
		}
		if !IsRetryable(err) {
			l.writeAudit(chunk, batchID, token, uint8(attempt), firstEvent, lastEvent, started,
				"failed", err.Error())
			return fmt.Errorf("batch %d (%d rows) failed permanently: %w",
				chunk.Ordinal, len(chunk.Rows), err)
		}
	}

	l.writeAudit(chunk, batchID, token, uint8(l.opts.MaxRetries+1), firstEvent, lastEvent, started,
		"failed", lastErr.Error())
	return fmt.Errorf("batch %d (%d rows) after %d attempts: %w",
		chunk.Ordinal, len(chunk.Rows), l.opts.MaxRetries+1, lastErr)
}

// insertSettings decides, per chunk, whether this write goes straight to a part
// or through ClickHouse's server-side async buffer.
//
// Why per chunk and not once per run. Measured on the 2026-08-01 load test:
// 22,314 batches averaging 55 rows (generator) and 144 rows (api), against a
// configured --batch-size of 50,000. The generator's one-wall-second timer
// flush emits whatever is buffered, which routes around the 1,000-row floor
// that --batch-size validation exists to enforce. Every one of those became its
// own part, plus one more per dependent materialized view.
//
// Client-side batching cannot fix that without giving up live streaming, so
// sub-floor writes go through the server-side buffer and let ClickHouse
// coalesce them into properly sized parts. Large chunks still go straight
// through: pushing an already-correct 50K-row native block through the buffer
// only adds a copy and a flush delay.
// [official: insert-async-small-batches, insert-batch-size]
func insertSettings(token string, rows int, forceAsync bool) clickhouse.Settings {
	settings := clickhouse.Settings{"insert_deduplication_token": token}

	if forceAsync || rows < AsyncInsertRowThreshold {
		settings["async_insert"] = 1
		settings["wait_for_async_insert"] = 1
		// Without this the token above is INERT on the async path and a retry
		// duplicates silently. Measured on the service 2026-08-02:
		// async_insert_deduplicate value=0 default=0 changed=0.
		settings["async_insert_deduplicate"] = 1
		// deduplicate_blocks_in_dependent_materialized_views is deliberately
		// NOT set here: the async-inserts guide says it should not be enabled
		// where dependent materialized views exist, and events_raw has two. The
		// setting that used to make the pairing throw is obsolete in 26.2, so
		// it would now proceed silently rather than warn.
		return settings
	}

	// Cloud defaults async_insert to 1 in 26.2 (measured: value=1, default=1,
	// changed=0), so a large block must opt out explicitly.
	settings["async_insert"] = 0
	// A retry must not double-append to the dirty-session queue either. The MV
	// output is set-like (its identity is derived from session + batch + row
	// sequence), so deduplicating dependent views is safe here and closes the
	// retry hole end to end.
	settings["deduplicate_blocks_in_dependent_materialized_views"] = 1
	return settings
}

// sendOnce performs a single PrepareBatch/Append/Send cycle.
func (l *Loader) sendOnce(ctx context.Context, stmt string, settings clickhouse.Settings, rows []model.RawEvent) error {
	bctx := clickhouse.Context(ctx, clickhouse.WithSettings(settings))

	batch, err := l.client.Conn.PrepareBatch(bctx, stmt)
	if err != nil {
		return fmt.Errorf("prepare batch: %w", err)
	}
	for i := range rows {
		if err := batch.Append(rows[i].Values()...); err != nil {
			_ = batch.Abort()
			return fmt.Errorf("append row %d: %w", i, err)
		}
	}
	if err := batch.Send(); err != nil {
		return fmt.Errorf("send: %w", err)
	}
	return nil
}

// dedupToken identifies the exact bytes of a chunk.
//
// All four components are load-bearing:
//   - source and fingerprint, so two different files do not collide on ordinal;
//   - batch size, so the same file at a different chunking does not collide;
//   - row count, which pins the final (short) chunk of a load.
func (l *Loader) dedupToken(ordinal uint32, rows int) string {
	return fmt.Sprintf("%s|%s|bs=%d|n=%d|%d",
		l.opts.Source, l.opts.Fingerprint, l.opts.BatchSize, rows, ordinal)
}

func (l *Loader) writeAudit(chunk *Chunk, batchID uuid.UUID, token string, attempt uint8,
	firstEvent, lastEvent, started time.Time, status, errMsg string) {
	if l.opts.Audit == nil {
		return
	}
	now := time.Now()
	l.opts.Audit.Add(model.BatchAudit{
		IngestBatchID:     batchID,
		RunID:             l.opts.RunID,
		Source:            l.opts.Source,
		SourceFingerprint: l.opts.Fingerprint,
		BatchOrdinal:      chunk.Ordinal,
		DedupToken:        token,
		RowCount:          uint32(len(chunk.Rows)),
		BytesEstimate:     estimateBytes(chunk.Rows),
		FirstEventTime:    firstEvent,
		LastEventTime:     lastEvent,
		StartedAt:         started,
		CompletedAt:       now,
		DurationMS:        uint32(now.Sub(started).Milliseconds()),
		Attempt:           attempt,
		Status:            status,
		Error:             errMsg,
	})
}

func (l *Loader) record(rows uint64, d time.Duration) {
	l.rows.Add(rows)
	l.batches.Add(1)
	l.mu.Lock()
	l.durations = append(l.durations, d)
	l.mu.Unlock()
}

// Stats snapshots progress. Safe to call concurrently with Run.
func (l *Loader) Stats() Stats {
	l.mu.Lock()
	ds := make([]time.Duration, len(l.durations))
	copy(ds, l.durations)
	l.mu.Unlock()

	sort.Slice(ds, func(i, j int) bool { return ds[i] < ds[j] })

	s := Stats{
		Rows:    l.rows.Load(),
		Batches: l.batches.Load(),
		Retries: l.retries.Load(),
		Elapsed: time.Since(l.started),
	}
	if s.Elapsed > 0 {
		s.RowsPerSec = float64(s.Rows) / s.Elapsed.Seconds()
	}
	if n := len(ds); n > 0 {
		s.InsertP50 = ds[n*50/100]
		s.InsertP99 = ds[min(n*99/100, n-1)]
		s.InsertMax = ds[n-1]
	}
	return s
}

// estimateBytes is a rough uncompressed payload size, used only to make the
// audit log interpretable. Fixed-width fields plus the variable strings.
func estimateBytes(rows []model.RawEvent) uint64 {
	var total uint64
	for i := range rows {
		r := &rows[i]
		total += 16 + 4 + 64 + 64 + 8 + 8 + 8 // lineage, ids, timestamps
		total += uint64(len(r.EventType) + len(r.Event) + len(r.Platform) +
			len(r.AppVersion) + len(r.Country) + len(r.AudioLanguage) +
			len(r.SubtitleLanguage) + len(r.PlayerVersion))
	}
	return total
}

// insertStatement renders "INSERT INTO db.table (col, ...)".
func insertStatement(database, table string, columns []string) string {
	return fmt.Sprintf("INSERT INTO %s.%s (%s)", database, table, strings.Join(columns, ", "))
}

// permanentServerErrors are ClickHouse exception codes that will never succeed
// on retry: the schema, the query, or the credentials are wrong. Retrying these
// only multiplies the time to a clear error message.
//
// Everything not listed is treated as transient — network faults, TOO_MANY_PARTS
// while merges catch up, timeouts — because a retry with the same deduplication
// token is free when it turns out to be unnecessary.
var permanentServerErrors = map[int32]string{
	16:  "NO_SUCH_COLUMN_IN_TABLE",
	43:  "ILLEGAL_TYPE_OF_ARGUMENT",
	47:  "UNKNOWN_IDENTIFIER",
	53:  "TYPE_MISMATCH",
	60:  "UNKNOWN_TABLE",
	62:  "SYNTAX_ERROR",
	81:  "UNKNOWN_DATABASE",
	192: "UNKNOWN_USER",
	193: "WRONG_PASSWORD",
	497: "ACCESS_DENIED",
	516: "AUTHENTICATION_FAILED",
}

// IsRetryable reports whether an error is worth another attempt.
func IsRetryable(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}
	var chErr *clickhouse.Exception
	if errors.As(err, &chErr) {
		_, permanent := permanentServerErrors[chErr.Code]
		return !permanent
	}
	return true
}
