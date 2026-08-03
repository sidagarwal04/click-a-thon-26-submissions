package mock

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/generator"
)

// ErrRunInFlight is returned when a second run is started while one is active.
var ErrRunInFlight = errors.New("a run is already in flight; stop it first")

// Params is what the load dashboard posts. Every field maps onto
// generator.Config, which already carries the measured defaults — this struct
// exposes the subset worth turning by hand and lets Defaults() fill the rest.
type Params struct {
	// Concurrency is the steady-state count of simultaneously active sessions.
	// This, not an event count, is the natural dial for the workload.
	Concurrency int `json:"concurrency"`
	// UserPool bounds distinct users. Exposed separately from Concurrency
	// because fewer users than sessions is what produces multi-session users,
	// and session-vs-user concurrency is a judged dimension.
	UserPool int `json:"user_pool"`

	// ContentIDs pins traffic to specific catalogue rows. Empty means "sample
	// ContentPool rows", which is the realistic spread; pinning a handful is how
	// you manufacture a live-event spike on one asset.
	ContentIDs  []int64 `json:"content_ids"`
	ContentPool int     `json:"content_pool"`

	SpeedFactor     float64 `json:"speed_factor"`
	RampUpSeconds   int     `json:"ramp_up_seconds"`
	DurationMinutes int     `json:"duration_minutes"`
	MaxEvents       int64   `json:"max_events"`
	EventsPerSec    int     `json:"events_per_sec"`
	BotShare        float64 `json:"bot_share"`
	Seed            int64   `json:"seed"`

	// Pointers, not plain floats, because Config.Defaults() deliberately does
	// NOT fill these: zero is a meaningful value (a perfectly ordered stream),
	// so it cannot be distinguished from "unset". nil here means "use the
	// measured rates"; an explicit 0 means "generate a clean stream", which is
	// what you want when isolating a bug from the disorder.
	LateFraction *float64 `json:"late_fraction"`
	DupFraction  *float64 `json:"dup_fraction"`

	BatchSize int  `json:"batch_size"`
	Workers   int  `json:"workers"`
	Async     bool `json:"async"`

	// Sink chooses where generated events go:
	//   "direct" (default) — chx.Loader over the native protocol. Fastest.
	//   "api"              — POST to /api/events, so the load run is a real client
	//                        of the ingest endpoint and exercises its decoding,
	//                        validation, chunking and async-insert path.
	// "api" is slower by design: JSON plus an HTTP round trip is what a real
	// producer pays, so a rate measured through it is a rate a producer could
	// expect.
	Sink string `json:"sink"`
}

// Status is the polled view of a run.
type Status struct {
	Running   bool      `json:"running"`
	RunID     string    `json:"run_id,omitempty"`
	StartedAt time.Time `json:"started_at,omitempty"`
	Elapsed   float64   `json:"elapsed_seconds"`
	Params    *Params   `json:"params,omitempty"`

	ContentRequested int `json:"content_requested"`
	ContentResolved  int `json:"content_resolved"`

	Rows       uint64  `json:"rows"`
	Batches    uint64  `json:"batches"`
	Retries    uint64  `json:"retries"`
	RowsPerSec float64 `json:"rows_per_sec"`
	InsertP50  float64 `json:"insert_p50_ms"`
	InsertP99  float64 `json:"insert_p99_ms"`

	Summary  *generator.Summary `json:"summary,omitempty"`
	Finished bool               `json:"finished"`
	Error    string             `json:"error,omitempty"`
}

type run struct {
	id        uuid.UUID
	params    Params
	startedAt time.Time
	cancel    context.CancelFunc
	done      chan struct{}

	contentRequested int
	contentResolved  int

	sink sink

	mu         sync.Mutex
	summary    *generator.Summary
	finished   bool
	finishedAt time.Time
	err        error
}

// Runner supervises at most one load run.
//
// One at a time on purpose. Two concurrent generators writing into one
// events_raw would interleave two unrelated session populations, and the
// resulting curve would not correspond to either set of parameters — which
// defeats the point of a dial you can turn and watch.
type Runner struct {
	mu      sync.Mutex
	client  *chx.Client
	current *run

	// selfURL and token let a run POST back into this same process's ingest
	// endpoint when Params.Sink is "api".
	selfURL string
	token   string

	// When set, "api" runs POST to this full endpoint URL instead of back into
	// this process. That is what makes the dashboard a client of sonyliv-api
	// rather than a second, parallel writer into events_raw.
	apiURL      string
	apiToken    string
	apiInsecure bool
}

// NewRunner builds an idle runner. selfURL is this server's own base URL, used
// only by the "api" sink.
func NewRunner(client *chx.Client, selfURL, token string) *Runner {
	return &Runner{client: client, selfURL: selfURL, token: token}
}

// UseExternalAPI directs "api" runs at a sonyliv-api endpoint. url must be the
// full path, e.g. https://127.0.0.1/v1/events. insecure skips certificate
// verification, for a self-signed loopback pair.
func (r *Runner) UseExternalAPI(url, token string, insecure bool) {
	r.apiURL, r.apiToken, r.apiInsecure = url, token, insecure
}

// apiEndpoint reports the configured sonyliv-api endpoint, if any.
//
// Shared with the fleet so both producers resolve "where do events go" from one
// place. Without this the fleet could be writing directly to ClickHouse while a
// load run goes through the ingest service, and the two populations would be
// subject to different validation.
func (r *Runner) apiEndpoint() (url, token string, insecure, ok bool) {
	if r.apiURL == "" {
		return "", "", false, false
	}
	return r.apiURL, r.apiToken, r.apiInsecure, true
}

// orDefault resolves an optional rate: nil takes the measured value, an explicit
// zero stays zero.
func orDefault(v *float64, def float64) float64 {
	if v == nil {
		return def
	}
	return *v
}

// Start resolves content, builds the generator, and runs it in the background.
func (r *Runner) Start(ctx context.Context, p Params) (*Status, error) {
	r.mu.Lock()
	if r.current != nil && !r.isFinishedLocked() {
		r.mu.Unlock()
		return nil, ErrRunInFlight
	}
	r.mu.Unlock()

	content, requested, err := r.resolveContent(ctx, p)
	if err != nil {
		return nil, err
	}

	cfg := generator.Config{
		Seed:              p.Seed,
		StartTime:         time.Now().UTC().Truncate(time.Minute),
		Duration:          time.Duration(p.DurationMinutes) * time.Minute,
		TargetConcurrency: p.Concurrency,
		RampUp:            time.Duration(p.RampUpSeconds) * time.Second,
		MaxEvents:         p.MaxEvents,
		EventsPerSecond:   p.EventsPerSec,
		SpeedFactor:       p.SpeedFactor,
		UserPoolSize:      p.UserPool,
		BotSessionShare:   p.BotShare,
		// Measured on the supplied extract: 7.0% of rows arrive out of order
		// within their own session, 0.465% are byte-identical duplicates. These
		// are what exercise the dedup token and the commutative-state design, so
		// defaulting them to zero would quietly make the simulator easier than
		// reality.
		LateFraction:      orDefault(p.LateFraction, 0.07),
		DuplicateFraction: orDefault(p.DupFraction, 0.005),
	}
	// Defaults fills every behavioural knob we do not expose (heartbeat cadence,
	// session-duration shape, bg/pause episode counts) with the values measured
	// from the supplied extract. Turning those by hand is how you accidentally
	// generate traffic that no longer resembles the real stream.
	cfg.Defaults()

	// Flush a partial batch roughly once per wall-clock second in live mode.
	// Config.Defaults() cannot do this — it does not know SpeedFactor is set — so
	// cmd/sonyliv-gen applies the same rule at main.go:134 and this must too.
	//
	// Without it the generator buffers until BatchSize, so a run emits ONE chunk at
	// the end: the curve stays flat and then jumps, and the "api" sink makes a
	// single giant POST instead of the many small ones a producer actually sends.
	// Both defeat the point of watching a load run.
	if cfg.FlushEvery == 0 && cfg.SpeedFactor > 0 {
		cfg.FlushEvery = time.Duration(cfg.SpeedFactor * float64(time.Second))
	}

	gen, err := generator.New(cfg, content)
	if err != nil {
		return nil, fmt.Errorf("build generator: %w", err)
	}

	if p.BatchSize <= 0 {
		p.BatchSize = 50_000
	}
	if p.Workers <= 0 {
		p.Workers = 6
	}

	runID := uuid.New()
	var dest sink = chx.NewLoader(r.client, chx.LoaderOptions{
		Source: "mock-dashboard",
		RunID:  runID,
		// The generator's own fingerprint covers the config AND the content
		// sample, so two runs that differ in either get different deduplication
		// tokens. Without the content digest, re-pointing a run at different
		// catalogue rows would reuse the previous token and ClickHouse would
		// silently drop the second run as a replay.
		Fingerprint: gen.Fingerprint(),
		BatchSize:   p.BatchSize,
		Workers:     p.Workers,
		MaxRetries:  3,
		AsyncInsert: p.Async,
	})
	if p.Sink == "api" {
		// Prefer an explicitly configured sonyliv-api endpoint. Falling back to
		// the mock's own /api/events keeps the simulator usable standalone, but
		// when --api-url is set the generated load goes through the real ingest
		// service -- so it is subject to the same validation, dedup token and
		// audit rows as any external producer, and shows up in its /v1/stats.
		switch {
		case r.apiURL != "":
			dest = NewAPISink(r.apiURL, r.apiToken, r.apiInsecure)
		case r.selfURL != "":
			dest = NewAPISink(r.selfURL+"/api/events", r.token, false)
		default:
			return nil, errors.New(`sink "api" needs --api-url, or --listen on a resolvable address`)
		}
	}

	runCtx, cancel := context.WithCancel(context.Background())
	rn := &run{
		id:               runID,
		params:           p,
		startedAt:        time.Now(),
		cancel:           cancel,
		done:             make(chan struct{}),
		contentRequested: requested,
		contentResolved:  len(content),
		sink:             dest,
	}

	r.mu.Lock()
	r.current = rn
	r.mu.Unlock()

	go rn.execute(runCtx, gen, p.BatchSize)

	st := r.Status()
	return &st, nil
}

// resolveContent turns Params into the refs the generator draws from.
func (r *Runner) resolveContent(ctx context.Context, p Params) ([]chx.ContentRef, int, error) {
	if len(p.ContentIDs) > 0 {
		refs, err := r.client.ContentRefsByID(ctx, p.ContentIDs)
		if err != nil {
			return nil, 0, err
		}
		if len(refs) == 0 {
			return nil, len(p.ContentIDs), fmt.Errorf(
				"none of the %d selected content ids exist in the catalogue — load it first",
				len(p.ContentIDs))
		}
		return refs, len(p.ContentIDs), nil
	}

	pool := p.ContentPool
	if pool <= 0 {
		pool = 5000
	}
	refs, err := r.client.SampleContent(ctx, pool)
	if err != nil {
		return nil, 0, err
	}
	return refs, pool, nil
}

// execute pumps the generator into the loader, exactly as cmd/sonyliv-gen does.
func (rn *run) execute(ctx context.Context, gen *generator.Generator, batchSize int) {
	defer close(rn.done)
	defer rn.cancel()

	chunks := make(chan *chx.Chunk, rn.params.Workers*2)

	// Generator.Run closes `out` itself, so this must not close it too.
	//
	// And the result is handed back over a channel rather than assigned to
	// captured variables: loader.Run returns as soon as chunks is closed and
	// drained, which can happen before gen.Run's return values are stored.
	// Reading them without this handoff is a data race that would usually look
	// like a missing summary rather than a crash. Same shape cmd/sonyliv-gen uses.
	type genResult struct {
		summary generator.Summary
		err     error
	}
	genDone := make(chan genResult, 1)
	go func() {
		s, err := gen.Run(ctx, chunks, batchSize)
		genDone <- genResult{s, err}
	}()

	_, loadErr := rn.sink.Run(ctx, chunks)
	res := <-genDone
	summary, genErr := res.summary, res.err

	rn.mu.Lock()
	rn.summary = &summary
	rn.finished = true
	rn.finishedAt = time.Now()
	switch {
	case loadErr != nil && !errors.Is(loadErr, context.Canceled):
		rn.err = loadErr
	case genErr != nil && !errors.Is(genErr, context.Canceled):
		rn.err = genErr
	}
	rn.mu.Unlock()
}

// Stop cancels the in-flight run and waits for it to unwind.
func (r *Runner) Stop() bool {
	r.mu.Lock()
	rn := r.current
	r.mu.Unlock()
	if rn == nil {
		return false
	}
	rn.cancel()
	// Bounded wait: a stuck insert should not wedge the HTTP handler. The run
	// goroutine still exits on its own once the driver returns.
	select {
	case <-rn.done:
	case <-time.After(10 * time.Second):
	}
	return true
}

func (r *Runner) isFinishedLocked() bool {
	if r.current == nil {
		return true
	}
	r.current.mu.Lock()
	defer r.current.mu.Unlock()
	return r.current.finished
}

// Status reports the current or most recent run.
//
// Rows, batches and rate come from the loader's in-process counters, so polling
// this every second costs no ClickHouse queries at all — the only thing in the
// dashboard that does is the curve.
func (r *Runner) Status() Status {
	r.mu.Lock()
	rn := r.current
	r.mu.Unlock()

	if rn == nil {
		return Status{Running: false}
	}

	rn.mu.Lock()
	finished, runErr, summary, finishedAt := rn.finished, rn.err, rn.summary, rn.finishedAt
	rn.mu.Unlock()

	s := rn.sink.Stats()

	// Freeze elapsed and the rate once the run ends. Loader.Stats keeps measuring
	// against wall clock, so a finished run's throughput would otherwise decay
	// toward zero on every poll and look like a slowdown that never happened.
	elapsed := time.Since(rn.startedAt)
	if finished && !finishedAt.IsZero() {
		elapsed = finishedAt.Sub(rn.startedAt)
	}
	rowsPerSec := s.RowsPerSec
	if finished && elapsed > 0 {
		rowsPerSec = float64(s.Rows) / elapsed.Seconds()
	}
	params := rn.params
	st := Status{
		Running:          !finished,
		RunID:            rn.id.String(),
		StartedAt:        rn.startedAt,
		Elapsed:          elapsed.Seconds(),
		Params:           &params,
		ContentRequested: rn.contentRequested,
		ContentResolved:  rn.contentResolved,
		Rows:             s.Rows,
		Batches:          s.Batches,
		Retries:          s.Retries,
		RowsPerSec:       rowsPerSec,
		InsertP50:        float64(s.InsertP50.Microseconds()) / 1000,
		InsertP99:        float64(s.InsertP99.Microseconds()) / 1000,
		Summary:          summary,
		Finished:         finished,
	}
	if runErr != nil {
		st.Error = runErr.Error()
	}
	return st
}
