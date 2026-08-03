// Command sonyliv-gen generates a synthetic SonyLIV event stream and ingests it
// through the same writer path as the CSV loader.
//
// The primary dial is concurrency, not row count: this workload is described in
// "how many sessions are active right now", and event volume is a consequence
// of that times the heartbeat cadence. --max-events and --eps cap the output
// when a fixed budget matters.
//
//	# demo: 2,000 concurrent sessions, 10 event-minutes at 30x, live pacing
//	sonyliv-gen --concurrency 2000 --duration 10m --speed 30
//
//	# load test: 5 million events as fast as the service will take them
//	sonyliv-gen --concurrency 20000 --max-events 5000000
//
//	# small-writer mode: 500-row batches through the async insert buffer
//	sonyliv-gen --concurrency 200 --duration 2m --batch-size 500 --async
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/config"
	"github.com/sonyliv-clickathon/ingest/internal/generator"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "\nerror: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	fs := flag.NewFlagSet("sonyliv-gen", flag.ExitOnError)

	// connection
	envPath := fs.String("env", "", "path to .env")

	// volume and shape — the knobs the demo is driven with
	// NOT a database dial. This is the number of simulated viewers inside the
	// generated event stream. The DB connection count is CLICKHOUSE_MAX_OPEN_CONNS
	// (default 16) and is completely independent — `--concurrency 50000` asks for
	// 50,000 fake viewers served through at most 16 sockets. Measured on
	// 2026-08-01: peak 23 TCP connections per replica against a 4,096 limit.
	// The startup banner prints both so the two can never be confused again.
	concurrency := fs.Int("concurrency", 500, "SIMULATED VIEWER sessions in the generated stream (NOT database connections — see --help notes)")
	duration := fs.Duration("duration", 0, "event-time span to generate, e.g. 10m (0 = until --max-events)")
	maxEvents := fs.Int64("max-events", 0, "hard cap on emitted rows (0 = unlimited)")
	rampUp := fs.Duration("ramp-up", 30*time.Second, "event-time over which concurrency climbs to target")
	speed := fs.Float64("speed", 0, "event-seconds per wall-second; 30 = 30x real time, 0 = as fast as possible")
	eps := fs.Int("eps", 0, "wall-clock events/second ceiling (0 = unlimited)")
	flushEvery := fs.Duration("flush-every", 0, "send a partial batch after this much EVENT time (0 = only at --batch-size; auto-set to ~1 wall-second when --speed is used)")
	drain := fs.Bool("drain", false, "let in-flight sessions finish past the cutoff instead of leaving them open")
	startAt := fs.String("start-at", "", "event-time origin, RFC3339 (default: now, truncated to the minute)")

	// realism knobs, defaulted from the measured extract
	seed := fs.Int64("seed", 20260801, "RNG seed; same seed + same flags = byte-identical output")
	heartbeat := fs.Duration("heartbeat", 40*time.Second, "periodic ping cadence (source p50 is 40s, not the documented 60s)")
	sessionMedian := fs.Duration("session-median", 12*time.Minute, "median session duration")
	sessionP99 := fs.Duration("session-p99", 74*time.Minute, "p99 session duration (sets the lognormal tail)")
	bgEpisodes := fs.Float64("bg-episodes", 1.35, "mean AppBackgrounded episodes per session")
	pauseEpisodes := fs.Float64("pause-episodes", 2.5, "mean pause episodes per session")
	errorProb := fs.Float64("error-prob", 0.027, "probability a session emits one VideoError")
	lateFraction := fs.Float64("late-fraction", 0.07, "share of events that arrive out of order")
	lateMax := fs.Duration("late-max", 2*time.Minute, "maximum arrival delay for a late event")
	dupFraction := fs.Float64("dup-fraction", 0.005, "share of events delivered twice, byte-identical")
	userPool := fs.Int("user-pool", 100000, "distinct users to draw from")
	botShare := fs.Float64("bot-share", 0, "share of sessions owned by one shared identity (reproduces the observed 95-concurrent outlier)")
	contentPool := fs.Int("content-pool", 5000, "catalogue rows to draw content ids from")

	// write path
	batchSize := fs.Int("batch-size", 50000, "rows per INSERT (recommended 10000-100000)")
	workers := fs.Int("workers", 6, "concurrent INSERT streams")
	retries := fs.Int("retries", 3, "retry attempts per batch (same dedup token)")
	async := fs.Bool("async", false, "route batches through the server-side async insert buffer (for small --batch-size)")
	dryRun := fs.Bool("dry-run", false, "generate and count without writing to ClickHouse")

	_ = fs.Parse(os.Args[1:])

	if *duration <= 0 && *maxEvents <= 0 {
		fs.Usage()
		return fmt.Errorf("set --duration, --max-events, or both; otherwise the run never terminates")
	}
	if *batchSize < 1000 && !*async {
		return fmt.Errorf("--batch-size %d is below the 1,000-row minimum. "+
			"If you are deliberately testing a producer that cannot batch, add --async "+
			"so ClickHouse buffers server-side instead of creating one part per insert", *batchSize)
	}
	if err := chx.ValidateWritePath(*workers, *retries); err != nil {
		return err
	}
	if *contentPool < 1 {
		return fmt.Errorf("--content-pool must be at least 1, got %d", *contentPool)
	}

	start := time.Now().UTC().Truncate(time.Minute)
	if *startAt != "" {
		t, err := time.Parse(time.RFC3339, *startAt)
		if err != nil {
			return fmt.Errorf("--start-at: %w", err)
		}
		start = t.UTC()
	}

	cfg := generator.Config{
		Seed:               *seed,
		StartTime:          start,
		Duration:           *duration,
		Drain:              *drain,
		TargetConcurrency:  *concurrency,
		RampUp:             *rampUp,
		MaxEvents:          *maxEvents,
		EventsPerSecond:    *eps,
		SpeedFactor:        *speed,
		FlushEvery:         *flushEvery,
		HeartbeatInterval:  *heartbeat,
		SessionMedian:      *sessionMedian,
		SessionP99:         *sessionP99,
		BackgroundEpisodes: *bgEpisodes,
		PauseEpisodes:      *pauseEpisodes,
		ErrorProbability:   *errorProb,
		LateFraction:       *lateFraction,
		LateMax:            *lateMax,
		DuplicateFraction:  *dupFraction,
		UserPoolSize:       *userPool,
		BotSessionShare:    *botShare,
	}

	// In live mode, default to flushing roughly once per wall-clock second so a
	// dashboard reading the serving layer sees the curve build.
	if cfg.FlushEvery == 0 && cfg.SpeedFactor > 0 {
		cfg.FlushEvery = time.Duration(cfg.SpeedFactor * float64(time.Second))
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	chCfg, err := config.Load(*envPath)
	if err != nil {
		return err
	}
	client, err := chx.Open(ctx, chCfg)
	if err != nil {
		return err
	}
	defer client.Close()

	version, err := client.ServerVersion(ctx)
	if err != nil {
		return err
	}
	fmt.Printf("connected to %s (ClickHouse %s)\n", chCfg.Redacted(), version)

	// Draw from the real catalogue so generated events join the dictionary the
	// same way replayed events do.
	content, err := client.SampleContent(ctx, *contentPool)
	if err != nil {
		return err
	}

	gen, err := generator.New(cfg, content)
	if err != nil {
		return err
	}

	// From the generator, not from cfg: New normalizes defaults and derives the
	// catalogue digest, so only it knows the identity of what will be written.
	fingerprint := gen.Fingerprint()
	runID := uuid.New()

	fmt.Printf("\ngenerating:\n")
	fmt.Printf("  target concurrency : %d SIMULATED VIEWER sessions (not DB connections)\n", cfg.TargetConcurrency)
	fmt.Printf("  db connections     : %d max open, %d insert workers — this is the real client concurrency\n",
		chCfg.MaxOpenConns, *workers)
	fmt.Printf("  event-time window  : %s", cfg.StartTime.Format(time.RFC3339))
	if cfg.Duration > 0 {
		fmt.Printf(" .. %s (%s)", cfg.StartTime.Add(cfg.Duration).Format(time.RFC3339), cfg.Duration)
	}
	fmt.Println()
	if cfg.MaxEvents > 0 {
		fmt.Printf("  max events         : %d\n", cfg.MaxEvents)
	}
	if cfg.SpeedFactor > 0 {
		fmt.Printf("  pacing             : %.0fx real time (live mode)\n", cfg.SpeedFactor)
	} else {
		fmt.Printf("  pacing             : unthrottled (backfill mode)\n")
	}
	if cfg.EventsPerSecond > 0 {
		fmt.Printf("  rate ceiling       : %d events/s\n", cfg.EventsPerSecond)
	}
	if cfg.FlushEvery > 0 {
		fmt.Printf("  partial flush      : every %s of event time\n", cfg.FlushEvery)
	}
	fmt.Printf("  content pool       : %d catalogue rows\n", len(content))
	fmt.Printf("  disorder / dups    : %.1f%% late (max %s) / %.2f%% duplicated\n",
		cfg.LateFraction*100, cfg.LateMax, cfg.DuplicateFraction*100)
	fmt.Printf("  open sessions      : %s\n", openSessionNote(cfg.Drain))
	fmt.Printf("  write path         : batch=%d workers=%d async=%t\n", *batchSize, *workers, *async)
	fmt.Printf("  fingerprint        : %s (re-running these exact flags is a no-op)\n", fingerprint)
	fmt.Printf("  run_id             : %s\n\n", runID)

	chunks := make(chan *chx.Chunk, *workers*2)

	genDone := make(chan struct {
		s   generator.Summary
		err error
	}, 1)
	go func() {
		s, err := gen.Run(ctx, chunks, *batchSize)
		genDone <- struct {
			s   generator.Summary
			err error
		}{s, err}
	}()

	started := time.Now()

	if *dryRun {
		var rows, batches int64
		for c := range chunks {
			rows += int64(len(c.Rows))
			batches++
		}
		res := <-genDone
		if res.err != nil {
			return res.err
		}
		fmt.Printf("dry run: %d rows in %d batches, %d sessions, peak concurrency %d, %s\n",
			rows, batches, res.s.Sessions, res.s.PeakConcurrency,
			time.Since(started).Round(time.Millisecond))
		return nil
	}

	audit := chx.NewAuditWriter(ctx, client)
	loader := chx.NewLoader(client, chx.LoaderOptions{
		Source:      "generator",
		RunID:       runID,
		Fingerprint: fingerprint,
		BatchSize:   *batchSize,
		Workers:     *workers,
		MaxRetries:  *retries,
		AsyncInsert: *async,
		Audit:       audit,
		Progress:    func(s chx.Stats) { fmt.Printf("  %s\n", s) },
	})

	stats, loadErr := loader.Run(ctx, chunks)
	res := <-genDone

	if err := audit.Close(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "warning: audit flush: %v\n", err)
	}
	if loadErr != nil {
		return loadErr
	}
	if res.err != nil && ctx.Err() == nil {
		return res.err
	}

	elapsed := time.Since(started)
	fmt.Printf("\ngeneration complete in %s\n", elapsed.Round(time.Millisecond))
	fmt.Printf("  %s\n", stats)
	fmt.Printf("  sessions opened    : %d\n", res.s.Sessions)
	fmt.Printf("  left open at cutoff: %d  <- the incremental-update case\n", res.s.SessionsOpen)
	fmt.Printf("  peak concurrency   : %d\n", res.s.PeakConcurrency)
	fmt.Printf("  late arrivals      : %d\n", res.s.LateEvents)
	fmt.Printf("  duplicates emitted : %d\n", res.s.Duplicates)
	if res.s.DroppedPastCutoff > 0 {
		fmt.Printf("  dropped past cutoff: %d  (event time beyond the window; --drain keeps them)\n",
			res.s.DroppedPastCutoff)
	}
	if !res.s.FirstEventTime.IsZero() {
		fmt.Printf("  event-time range   : %s .. %s\n",
			res.s.FirstEventTime.Format("2006-01-02 15:04:05.000"),
			res.s.LastEventTime.Format("2006-01-02 15:04:05.000"))
	}
	fmt.Println("\nrun `sonyliv-ingest verify` for the integrity report")
	return nil
}

func openSessionNote(drain bool) string {
	if drain {
		return "none (--drain lets every session finish)"
	}
	return "hard cutoff, sessions still playing stay open"
}
