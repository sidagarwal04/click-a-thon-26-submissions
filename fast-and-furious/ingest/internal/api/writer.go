package api

import (
	"context"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
)

// LoaderWriter inserts through chx.Loader — the same write path the CSV command
// uses, with its retries, deduplication token and per-batch audit row.
type LoaderWriter struct {
	client  *chx.Client
	runID   uuid.UUID
	audit   *chx.AuditWriter
	workers int
	retries int
	batch   int
}

// NewLoaderWriter binds a client and the per-process run id.
//
// RunID is allocated ONCE, at process start, matching its documented meaning —
// "groups every batch of one invocation" — so ingest_batches groups everything one
// API process wrote. Per-request run ids would make that grouping useless.
func NewLoaderWriter(c *chx.Client, audit *chx.AuditWriter, workers, retries, batchSize int) *LoaderWriter {
	return &LoaderWriter{
		client:  c,
		runID:   newRunID(),
		audit:   audit,
		workers: workers,
		retries: retries,
		batch:   batchSize,
	}
}

// RunID exposes the process run id for logging.
func (lw *LoaderWriter) RunID() uuid.UUID { return lw.runID }

// Write pushes chunks through a per-request loader.
//
// A loader per request, rather than one long-lived loader, because Fingerprint
// lives in LoaderOptions and MUST vary per request. The dedup token is
//
//	source | fingerprint | bs=N | n=rows | ordinal
//
// so with a constant fingerprint two DIFFERENT requests carrying the same row
// count at the same ordinal would produce the SAME token, and ClickHouse would
// silently drop the second as a duplicate. That is data loss with no error
// anywhere, and it is the single easiest way to get this endpoint wrong.
//
// Deriving the fingerprint from the request instead turns the same mechanism into
// the feature you want: replaying an identical payload is exactly-once, and
// distinct payloads never collide.
//
// The cost is one Loader per request. Workers are capped at the chunk count, so a
// small request spawns a single goroutine rather than the configured fan-out.
func (lw *LoaderWriter) Write(ctx context.Context, fingerprint string, async bool, chunks []*chx.Chunk) (chx.Stats, error) {
	workers := lw.workers
	if workers > len(chunks) {
		workers = len(chunks)
	}
	if workers < 1 {
		workers = 1
	}

	loader := chx.NewLoader(lw.client, chx.LoaderOptions{
		Source:      SourceLabel,
		RunID:       lw.runID,
		Fingerprint: fingerprint,
		BatchSize:   lw.batch,
		Workers:     workers,
		MaxRetries:  lw.retries,
		AsyncInsert: async,
		Audit:       lw.audit,
	})

	ch := make(chan *chx.Chunk, len(chunks))
	for _, c := range chunks {
		ch <- c
	}
	close(ch)

	return loader.Run(ctx, ch)
}
