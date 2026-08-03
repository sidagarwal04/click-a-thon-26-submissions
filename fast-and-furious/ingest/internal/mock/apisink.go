package mock

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// sink consumes generated chunks. Both implementations share this shape, so the
// runner picks a destination without knowing anything about how it writes.
//
// *chx.Loader already satisfies it, which is why switching the generator between
// the native protocol and HTTP is a one-line change in Start rather than a second
// copy of the run loop.
type sink interface {
	Run(ctx context.Context, chunks <-chan *chx.Chunk) (chx.Stats, error)
	Stats() chx.Stats
}

// APISink POSTs generated events to the ingest endpoint instead of writing to
// ClickHouse over the native protocol.
//
// Why bother, when the loader is right there and faster: this makes the generator
// a genuine client of POST /api/events. The endpoint's decoding, validation,
// chunking, idempotency and async-insert path all get exercised by every load run
// rather than only by hand-written curls. If the API breaks, the load simulator
// breaks — which is the point.
//
// It is slower than the direct path, and deliberately so: JSON serialisation plus
// an HTTP round trip per chunk is the cost a real producer pays, so a rate
// measured through here is a rate a real producer could expect.
type APISink struct {
	url    string
	token  string
	client *http.Client

	mu      sync.Mutex
	stats   chx.Stats
	started time.Time
}

// NewAPISink posts to a full ingest endpoint URL. token may be empty.
//
// The URL is passed whole rather than assembled from a base, because the two
// endpoints this targets have different paths: the mock's own /api/events, and
// sonyliv-api's /v1/events. Appending a fixed path meant the sink could only
// ever talk to itself.
//
// insecure skips certificate verification, which is needed when sonyliv-api is
// reached over loopback HTTPS with a self-signed pair. It is scoped to this
// client so nothing else inherits it.
func NewAPISink(endpointURL, token string, insecure bool) *APISink {
	transport := http.DefaultTransport
	if insecure {
		t := http.DefaultTransport.(*http.Transport).Clone()
		t.TLSClientConfig = &tls.Config{InsecureSkipVerify: true} //nolint:gosec // self-signed loopback, deliberate
		transport = t
	}
	return &APISink{
		url:   endpointURL,
		token: token,
		client: &http.Client{
			Transport: transport,
			// Generous: wait_for_async_insert=1 means the endpoint blocks until
			// ClickHouse has flushed the buffer, so a chunk's round trip includes a
			// server-side flush.
			Timeout: 2 * time.Minute,
		},
		started: time.Now(),
	}
}

// Run drains chunks, POSTing each as NDJSON.
//
// NDJSON rather than a JSON array: the endpoint decodes it row by row with bounded
// memory, and encoding it here is a loop rather than building one giant slice of
// interface values.
func (a *APISink) Run(ctx context.Context, chunks <-chan *chx.Chunk) (chx.Stats, error) {
	a.mu.Lock()
	a.started = time.Now()
	a.mu.Unlock()

	for chunk := range chunks {
		if err := ctx.Err(); err != nil {
			return a.Stats(), err
		}
		took, err := a.post(ctx, chunk.Rows)
		if err != nil {
			return a.Stats(), err
		}
		a.record(uint64(len(chunk.Rows)), took)
	}
	return a.Stats(), nil
}

func (a *APISink) post(ctx context.Context, rows []model.RawEvent) (time.Duration, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	for i := range rows {
		r := &rows[i]
		// Encoded as the source CSV field names, which is what EventIn expects —
		// the same shape any external producer would send.
		if err := enc.Encode(map[string]any{
			"video_session_id":    r.VideoSessionID,
			"user_id":             r.UserID,
			"content_id":          r.ContentID,
			"event_type":          r.EventType,
			"event":               r.Event,
			"event_timestamp":     r.EventTimestamp.UnixMilli(),
			"session_start_epoch": r.SessionStartEpoch.UnixMilli(),
			"platform":            r.Platform,
			"app_version":         r.AppVersion,
			"country":             r.Country,
			"audio_language":      r.AudioLanguage,
			"subtitle_language":   r.SubtitleLanguage,
			"player_version":      r.PlayerVersion,
		}); err != nil {
			return 0, fmt.Errorf("encode event: %w", err)
		}
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.url, &buf)
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/x-ndjson")
	if a.token != "" {
		req.Header.Set("Authorization", "Bearer "+a.token)
	}

	started := time.Now()
	res, err := a.client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("post events: %w", err)
	}
	defer func() { _ = res.Body.Close() }()
	took := time.Since(started)

	var out IngestResult
	if err := json.NewDecoder(res.Body).Decode(&out); err != nil && res.StatusCode == http.StatusOK {
		return took, fmt.Errorf("decode ingest response: %w", err)
	}
	if res.StatusCode != http.StatusOK {
		return took, fmt.Errorf("ingest returned %s: %v", res.Status, out.Errors)
	}
	// A row the endpoint refused is a generator bug, not a transient failure, so
	// surface it rather than quietly shipping fewer events than were generated.
	if out.Rejected > 0 {
		return took, fmt.Errorf("ingest rejected %d of %d rows: %v",
			out.Rejected, out.Rejected+out.Accepted, out.Errors)
	}
	return took, nil
}

func (a *APISink) record(rows uint64, took time.Duration) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.stats.Rows += rows
	a.stats.Batches++
	// p50/p99 would need a reservoir; a single-writer sink reports the extremes it
	// has actually seen and leaves p50 as the mean, which is honest for a counter
	// the dashboard labels "insert p50".
	if took > a.stats.InsertMax {
		a.stats.InsertMax = took
	}
	a.stats.InsertP99 = a.stats.InsertMax
	if a.stats.Batches > 0 {
		a.stats.InsertP50 = time.Duration(int64(a.stats.Elapsed+took) / int64(a.stats.Batches))
	}
	a.stats.Elapsed += took
}

// Stats reports progress in the same shape the loader does.
func (a *APISink) Stats() chx.Stats {
	a.mu.Lock()
	defer a.mu.Unlock()
	s := a.stats
	elapsed := time.Since(a.started)
	s.Elapsed = elapsed
	if elapsed > 0 {
		s.RowsPerSec = float64(s.Rows) / elapsed.Seconds()
	}
	return s
}
