package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"time"

	"github.com/sonyliv-clickathon/ingest/concurrency"
)

// cmdConcurrency drives the serving layers.
//
//	sonyliv-ingest concurrency --layer all               full rebuild from scratch
//	sonyliv-ingest concurrency --layer live --loop 10s   keep the live dashboard moving
//	sonyliv-ingest concurrency --layer minute --day D    rebuild one UTC day
//
// The three layers are separate flags rather than one command because they have
// genuinely different cadences: intervals is the expensive per-session step, live
// runs every few seconds over a short window, and minute rebuilds a whole day at a
// time on a lag. Collapsing them would force the cheapest work to pay the cost of
// the most expensive.
func cmdConcurrency(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("concurrency", flag.ExitOnError)
	envPath := fs.String("env", "", "path to .env (default: nearest .env walking up)")
	layer := fs.String("layer", "all",
		"which layer to build: intervals | live | minute | all")
	day := fs.String("day", "",
		"UTC day for --layer minute, YYYY-MM-DD (default: every day with active time)")
	liveWindow := fs.Duration("live-window", 30*time.Minute,
		"how much trailing time the live layer rebuilds each pass")
	lag := fs.Duration("lag", concurrency.DefaultLag,
		"how far behind the ingest watermark the minute layer publishes, so the late-arrival window has closed")
	loop := fs.Duration("loop", 0,
		"repeat every interval instead of running once (0 = run once)")
	minuteEvery := fs.Duration("minute-every", time.Minute,
		"in --loop mode, how often to also rebuild the minute layer (0 = never)")
	full := fs.Bool("full", false,
		"recompute every session rather than only those dirtied since the last pass")
	timeoutMS := fs.Uint64("heartbeat-timeout-ms", concurrency.DefaultHeartbeatTimeoutMS,
		"liveness lease in milliseconds; must match the policy the numbers are defended under")
	policy := fs.String("policy-version", concurrency.DefaultPolicyVersion,
		"semantic contract stamped onto every row")
	dirtyCap := fs.Int("dirty-cap", 50_000,
		"most sessions one incremental pass will recompute before it insists on --full")
	_ = fs.Parse(args)

	client, err := connect(ctx, *envPath)
	if err != nil {
		return err
	}
	defer client.Close()

	r := concurrency.NewRunner(client)
	r.HeartbeatTimeoutMS = *timeoutMS
	r.PolicyVersion = *policy

	switch *layer {
	case "intervals", "live", "minute", "all":
	default:
		return fmt.Errorf("unknown --layer %q (want intervals, live, minute or all)", *layer)
	}
	if *day != "" && *layer != "minute" {
		return errors.New("--day only applies to --layer minute")
	}

	// lastPass seeds the dirty-session query. Zero on the first pass means "every
	// session dirtied at any point", which is the correct cold start.
	var lastPass time.Time
	// The minute layer rebuilds whole day partitions, so it runs on its own slower
	// cadence rather than every live tick. Zero value means "never run yet", so the
	// first pass always builds it.
	var lastMinute time.Time

	pass := func() error {
		switch *layer {
		case "intervals":
			_, err := runIntervals(ctx, r, *full, *dirtyCap, &lastPass)
			return err
		case "live":
			touched, err := runIntervals(ctx, r, *full, *dirtyCap, &lastPass)
			if err != nil {
				return err
			}
			if err := runLive(ctx, r, *liveWindow); err != nil {
				return err
			}
			// Without this the minute layer never advances in a live loop, and its
			// freshness tile reports "time since someone last ran it by hand" —
			// which grows without bound and looks exactly like a stalled pipeline.
			if *loop > 0 && *minuteEvery > 0 && time.Since(lastMinute) >= *minuteEvery {
				// Scope the rebuild to the days the recomputed sessions occupy.
				// A full sweep here rewrote every service day once a minute.
				if err := runMinuteScoped(ctx, r, *lag, touched); err != nil {
					return err
				}
				lastMinute = time.Now()
			}
			return nil
		case "minute":
			return runMinute(ctx, r, *day, *lag)
		case "all":
			if _, err := runIntervals(ctx, r, true, *dirtyCap, &lastPass); err != nil {
				return err
			}
			if err := runLive(ctx, r, *liveWindow); err != nil {
				return err
			}
			return runMinute(ctx, r, "", *lag)
		}
		return nil
	}

	if *loop == 0 {
		return pass()
	}

	fmt.Printf("looping every %s; Ctrl-C to stop\n", *loop)
	ticker := time.NewTicker(*loop)
	defer ticker.Stop()
	for {
		if err := pass(); err != nil {
			// A transient failure must not kill a long-running loop — the next
			// tick recomputes the same window from scratch, so one lost pass
			// leaves no gap behind it.
			fmt.Printf("pass failed, retrying next tick: %v\n", err)
		}
		select {
		case <-ctx.Done():
			fmt.Println("\nstopping")
			return nil
		case <-ticker.C:
		}
	}
}

// runIntervals recomputes session_intervals, incrementally unless asked not to.
//
// The incremental path reads dirty_sessions, which an insert-time materialized
// view on events_raw maintains. That makes a pass proportional to what actually
// changed rather than to the size of the history — the difference between a
// ten-second loop being viable and not.
// The returned slice is the workset it recomputed: nil for a full rebuild (meaning
// "every day"), empty for a pass with nothing to do.
func runIntervals(ctx context.Context, r *concurrency.Runner, full bool, dirtyCap int, lastPass *time.Time) ([]uint64, error) {
	watermark, err := r.Watermark(ctx)
	if err != nil {
		return nil, fmt.Errorf("read ingest watermark: %w", err)
	}

	// Captured BEFORE the workset is chosen, not after the pass finishes. A session
	// dirtied while this pass is running must be picked up by the next one, and
	// advancing lastPass to the finish time would skip it.
	passStart := time.Now().UTC()

	var keys []uint64
	if !full {
		keys, err = r.DirtySessions(ctx, *lastPass, dirtyCap)
		if err != nil {
			return nil, fmt.Errorf("read dirty sessions: %w", err)
		}
		if len(keys) == 0 {
			// Nothing new. Say so rather than rewriting every interval for no
			// reason — a quiet pass is the normal state of a live loop.
			fmt.Printf("intervals  no sessions dirtied since %s, skipped\n",
				lastPass.UTC().Format("15:04:05"))
			*lastPass = passStart
			return []uint64{}, nil
		}
		if len(keys) >= dirtyCap {
			// lastPass is in-process state, so a RESTARTED loop starts at the zero
			// time and asks for every session ever dirtied. With any backlog that
			// is always at or above the cap, and the error used to return before
			// lastPass advanced — so every subsequent tick asked the same question
			// and got the same answer. The loop could never recover on its own, and
			// --full did not help because it skipped this block and left lastPass
			// zero too. Measured: 446,130 sessions queued against a cap of 50,000,
			// wedged across restarts until the cap was raised by hand.
			//
			// On a cold start, promote to the full rebuild the error asks for
			// instead of demanding a human do it. Intervals REPLACES each session's
			// row, so a full pass is idempotent and safe to reach for. Mid-run the
			// guard still fires: once lastPass is set, a spike this large means
			// something abnormal and silently rebuilding everything would hide it.
			if lastPass.IsZero() {
				fmt.Printf("intervals  cold start with %d sessions queued (cap %d) — "+
					"promoting to a full rebuild\n", len(keys), dirtyCap)
				keys = nil // empty workset means every session
			} else {
				return nil, fmt.Errorf("%d sessions dirtied, at or above --dirty-cap %d: "+
					"run once with --full rather than catching up in slices", len(keys), dirtyCap)
			}
		}
	}

	st, err := r.Intervals(ctx, keys, watermark)
	if err != nil {
		return nil, err
	}
	// Set on every successful pass, including --full and the promoted cold start.
	// Leaving it zero after a full pass was the second half of the wedge.
	*lastPass = passStart
	fmt.Println(st)
	// The cursor is wall-clock, not the event watermark, because
	// dirty_sessions.last_ingested_at records when a row was inserted rather than
	// when it happened. An event-time cursor would re-read the same sessions
	// forever whenever the stream replays history — which is what a backfill is.
	*lastPass = time.Now().UTC()
	return keys, nil
}

func runLive(ctx context.Context, r *concurrency.Runner, window time.Duration) error {
	end := time.Now().UTC()
	st, err := r.Live(ctx, end.Add(-window), end)
	if err != nil {
		return err
	}
	fmt.Println(st)
	return nil
}

// runMinute rebuilds either one named day or every day holding active time.
//
// The lag is enforced as a publish cutoff at MINUTE granularity, not by skipping
// days. An earlier version tested whether a whole day had cleared the watermark
// minus lag, which cannot express this: the open day's midnight is always older
// than any cutoff, so today was published right up to the freshest minute — making
// "corrected, published on a lag" a claim the layer did not honour. The cutoff is
// passed into the rollup, which simply does not write minutes at or after it.
// runMinuteScoped rebuilds only the days that could have changed: the days the
// recomputed sessions occupy, plus the day holding the publish cutoff.
//
// That last one is not optional. The cutoff advances every pass, so newly settled
// minutes become publishable even when no session changed — without it, a quiet
// stream would freeze the layer at whatever the cutoff was when the last session
// moved.
//
// touched == nil means a full rebuild was requested; empty means nothing changed, in
// which case only the cutoff day needs revisiting.
func runMinuteScoped(ctx context.Context, r *concurrency.Runner, lag time.Duration, touched []uint64) error {
	watermark, err := r.Watermark(ctx)
	if err != nil {
		return fmt.Errorf("read ingest watermark: %w", err)
	}
	publishUntil := watermark.Add(-lag)

	var days []time.Time
	if touched == nil {
		if days, err = r.ServiceDays(ctx); err != nil {
			return fmt.Errorf("list service days: %w", err)
		}
	} else if len(touched) > 0 {
		if days, err = r.ServiceDaysFor(ctx, touched); err != nil {
			return fmt.Errorf("list service days for workset: %w", err)
		}
	}

	cutoffDay := publishUntil.UTC().Truncate(24 * time.Hour)
	seen := false
	for _, d := range days {
		if d.Equal(cutoffDay) {
			seen = true
			break
		}
	}
	if !seen {
		days = append(days, cutoffDay)
	}

	var built int
	for _, d := range days {
		if !d.Before(publishUntil) {
			continue
		}
		st, err := r.Minute(ctx, d, publishUntil)
		if err != nil {
			return err
		}
		fmt.Printf("%s day=%s\n", st, d.Format("2006-01-02"))
		built++
	}
	fmt.Printf("minute     %d day(s) rebuilt (scoped to %d changed session(s)), published through %s\n",
		built, len(touched), publishUntil.Truncate(concurrency.MinuteBucket).Format("2006-01-02 15:04:05"))
	return nil
}

func runMinute(ctx context.Context, r *concurrency.Runner, day string, lag time.Duration) error {
	watermark, err := r.Watermark(ctx)
	if err != nil {
		return fmt.Errorf("read ingest watermark: %w", err)
	}
	publishUntil := watermark.Add(-lag)

	if day != "" {
		d, err := time.ParseInLocation("2006-01-02", day, time.UTC)
		if err != nil {
			return fmt.Errorf("--day %q: %w", day, err)
		}
		st, err := r.Minute(ctx, d, publishUntil)
		if err != nil {
			return err
		}
		fmt.Printf("%s day=%s\n", st, day)
		return nil
	}

	days, err := r.ServiceDays(ctx)
	if err != nil {
		return fmt.Errorf("list service days: %w", err)
	}
	if len(days) == 0 {
		fmt.Println("minute     session_intervals holds no active time, nothing to build")
		return nil
	}

	var built, skipped int
	for _, d := range days {
		// A day starting at or after the cutoff has nothing publishable in it yet.
		// Rebuilding it would drop its partition, so leave it alone entirely.
		if !d.Before(publishUntil) {
			skipped++
			continue
		}
		st, err := r.Minute(ctx, d, publishUntil)
		if err != nil {
			return err
		}
		fmt.Printf("%s day=%s\n", st, d.Format("2006-01-02"))
		built++
	}
	fmt.Printf("minute     %d day(s) rebuilt, published through %s (watermark %s less %s)\n",
		built, publishUntil.Truncate(concurrency.MinuteBucket).Format("2006-01-02 15:04:05"),
		watermark.Format("15:04:05"), lag)
	if skipped > 0 {
		fmt.Printf("minute     %d day(s) not yet publishable\n", skipped)
	}
	return nil
}
