// Package api serves HTTP event ingest into events_raw.
//
// It is a thin front end over the existing write path: a request body becomes
// chx.Chunks and goes through chx.Loader, the same loader the CSV command uses.
// There is deliberately no second insert path and no second normalization rule —
// see model.RawEvent's contract, and NormalizeHexID's, for why duplicating either
// is the failure this package is shaped to avoid.
package api

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"strconv"
	"sync/atomic"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Defaults chosen so the zero-config service is safe rather than fast.
const (
	DefaultBatchSize     = 50_000
	DefaultMaxRows       = 500_000
	DefaultMaxBodyBytes  = 64 << 20 // 64 MiB
	DefaultMaxInFlight   = 32
	DefaultSyncThreshold = 10_000
	DefaultDrainTimeout  = 15 * time.Second
)

// Writer inserts prepared chunks. The interface exists so the handler is
// testable without a ClickHouse: ingest_test.go substitutes a recorder.
type Writer interface {
	// Write inserts chunks under a per-request dedup fingerprint. async selects
	// server-side buffering; see Options.SyncThreshold.
	Write(ctx context.Context, fingerprint string, async bool, chunks []*chx.Chunk) (chx.Stats, error)
}

// Rejecter quarantines rows that failed validation. Satisfied by chx.AuditWriter,
// so API rejects land in ingest_rejects alongside the CSV path's.
type Rejecter interface {
	AddReject(r model.Reject)
}

// Options configures the server.
type Options struct {
	// Token is the bearer credential. Server refuses to start if empty unless
	// AllowUnauthenticated is set.
	Token string
	// AllowUnauthenticated permits an empty Token, serving open writes. Only
	// defensible where the network is the boundary -- a host with no public
	// address, reachable over a private path. It is a flag rather than an
	// inferred default so the decision is visible wherever the service is
	// launched.
	AllowUnauthenticated bool

	// BatchSize caps rows per chunk. It also keeps _batch_row_seq inside the 20
	// bits row_version allots it — see chunk() in ingest.go.
	BatchSize int
	// MaxRows rejects an oversized request outright rather than truncating it.
	MaxRows int
	// MaxBodyBytes bounds memory before any parsing happens.
	MaxBodyBytes int64
	// MaxInFlight bounds concurrent inserts. Over the limit is 503, not a queue.
	MaxInFlight int
	// SyncThreshold is the row count at or above which a request bypasses the
	// async buffer. Bulk data through a small-write buffer only adds latency;
	// this is the same reasoning that makes chx.Open force async_insert to 0.
	SyncThreshold int

	Log *slog.Logger
}

func (o *Options) withDefaults() {
	if o.BatchSize <= 0 {
		o.BatchSize = DefaultBatchSize
	}
	if o.MaxRows <= 0 {
		o.MaxRows = DefaultMaxRows
	}
	if o.MaxBodyBytes <= 0 {
		o.MaxBodyBytes = DefaultMaxBodyBytes
	}
	if o.MaxInFlight <= 0 {
		o.MaxInFlight = DefaultMaxInFlight
	}
	if o.SyncThreshold <= 0 {
		o.SyncThreshold = DefaultSyncThreshold
	}
	if o.Log == nil {
		o.Log = slog.Default()
	}
}

// Server holds the ingest handler's dependencies.
type Server struct {
	opts     Options
	writer   Writer
	rejecter Rejecter
	pinger   func(context.Context) error

	inflight chan struct{}
	started  time.Time

	acceptedRows atomic.Uint64
	rejectedRows atomic.Uint64
	requests     atomic.Uint64
	inFlightNow  atomic.Int64
}

// ErrNoToken is returned rather than defaulting to an open endpoint.
//
// Fail-closed at construction: this endpoint writes into the landing zone of a
// production ClickHouse, so "the operator forgot the flag" must not be a way to
// end up serving unauthenticated writes.
var ErrNoToken = errors.New("api: auth token is required (set SONYLIV_API_TOKEN), or pass --allow-unauthenticated")

// NewServer validates options and wires the handler.
func NewServer(w Writer, r Rejecter, ping func(context.Context) error, opts Options) (*Server, error) {
	opts.withDefaults()
	// Still fail-closed on an EMPTY token: forgetting the credential must not be
	// a way to end up serving open writes. AllowUnauthenticated is the deliberate
	// opt-out, so an open endpoint is always something someone chose in the unit
	// file rather than something that happened.
	if opts.Token == "" && !opts.AllowUnauthenticated {
		return nil, ErrNoToken
	}
	if opts.MaxRows < opts.BatchSize {
		return nil, fmt.Errorf("api: --max-rows %d is below --batch-size %d, so no request could ever fill a chunk",
			opts.MaxRows, opts.BatchSize)
	}
	return &Server{
		opts:     opts,
		writer:   w,
		rejecter: r,
		pinger:   ping,
		inflight: make(chan struct{}, opts.MaxInFlight),
		started:  time.Now(),
	}, nil
}

// Handler returns the routed, middleware-wrapped mux.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()

	// Liveness deliberately does NOT touch ClickHouse. If the database blips,
	// systemd restarting a healthy process makes the outage longer, not shorter.
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
	})

	// Readiness does. This is the one a load balancer should poll.
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		if err := s.pinger(ctx); err != nil {
			writeJSON(w, http.StatusServiceUnavailable, map[string]any{
				"status": "unavailable", "error": err.Error(),
			})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"status": "ready"})
	})

	mux.Handle("GET /v1/stats", s.auth(http.HandlerFunc(s.handleStats)))
	mux.Handle("POST /v1/events", s.auth(s.limit(http.HandlerFunc(s.handleEvents))))

	return s.logRequests(mux)
}

// auth compares the bearer token in constant time.
func (s *Server) auth(next http.Handler) http.Handler {
	if s.opts.Token == "" {
		// Open by explicit request. No wrapper at all rather than a per-request
		// branch, so the fast path carries no cost and the intent is legible.
		return next
	}
	want := []byte("Bearer " + s.opts.Token)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got := []byte(r.Header.Get("Authorization"))
		// ConstantTimeCompare returns 0 on length mismatch, so the length check
		// is implicit; comparing anyway keeps the intent obvious.
		if len(got) != len(want) || subtle.ConstantTimeCompare(got, want) != 1 {
			w.Header().Set("WWW-Authenticate", `Bearer realm="sonyliv-api"`)
			writeJSON(w, http.StatusUnauthorized, errBody("unauthorized", "missing or invalid bearer token"))
			return
		}
		next.ServeHTTP(w, r)
	})
}

// limit bounds concurrent inserts.
//
// Shedding with 503 + Retry-After beats letting requests pile up behind the
// driver's connection pool: the caller learns to back off instead of seeing an
// opaque timeout after the pool starves.
func (s *Server) limit(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case s.inflight <- struct{}{}:
			s.inFlightNow.Add(1)
			defer func() {
				s.inFlightNow.Add(-1)
				<-s.inflight
			}()
			next.ServeHTTP(w, r)
		default:
			w.Header().Set("Retry-After", "1")
			writeJSON(w, http.StatusServiceUnavailable, errBody("busy",
				fmt.Sprintf("at --max-inflight=%d; retry", s.opts.MaxInFlight)))
		}
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

func (s *Server) logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Health checks are high-frequency and uninteresting; logging them
		// buries the requests that matter.
		if r.URL.Path == "/healthz" || r.URL.Path == "/readyz" {
			next.ServeHTTP(w, r)
			return
		}
		rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		start := time.Now()
		next.ServeHTTP(rec, r)
		s.opts.Log.Info("request",
			"method", r.Method, "path", r.URL.Path, "status", rec.status,
			"dur_ms", time.Since(start).Milliseconds(), "remote", r.RemoteAddr)
	})
}

func (s *Server) handleStats(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"uptime_seconds": int64(time.Since(s.started).Seconds()),
		"requests":       s.requests.Load(),
		"accepted_rows":  s.acceptedRows.Load(),
		"rejected_rows":  s.rejectedRows.Load(),
		"in_flight":      s.inFlightNow.Load(),
		"max_in_flight":  s.opts.MaxInFlight,
		"batch_size":     s.opts.BatchSize,
		"sync_threshold": s.opts.SyncThreshold,
	})
}

func writeJSON(w http.ResponseWriter, code int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(body)
}

func errBody(code, detail string) map[string]any {
	return map[string]any{"error": code, "detail": detail}
}

// contentLengthHint reports the declared body size, or -1. Used only to reject
// an obviously-oversized request before reading it.
func contentLengthHint(r *http.Request) int64 {
	if v := r.Header.Get("Content-Length"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			return n
		}
	}
	return -1
}

// newRunID is a seam for tests.
var newRunID = uuid.New
