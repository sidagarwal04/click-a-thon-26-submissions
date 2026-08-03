package anomalydetector

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"sort"
	"time"

	"golang.org/x/sync/errgroup"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector/baseline"
)

// Detector is the interface every detection algorithm must implement.
// Defined here to avoid circular imports with the detector sub-package.
type Detector interface {
	Name() string
	Metrics() []string
	Detect(ctx context.Context, w Window) ([]AnomalySignal, error)
}

// DetectionEngine orchestrates all registered detectors for a given window.
type DetectionEngine struct {
	detectors []Detector
	qe        *query.Executor
	cfg       config.DetectionConfig
	logger    *slog.Logger
}

// NewDetectionEngine creates a DetectionEngine with the given detectors.
func NewDetectionEngine(detectors []Detector, qe *query.Executor, cfg config.DetectionConfig, logger *slog.Logger) *DetectionEngine {
	return &DetectionEngine{
		detectors: detectors,
		qe:        qe,
		cfg:       cfg,
		logger:    logger,
	}
}

// ResolveWindow returns the Window for detection.
// If windowEnd is zero, auto-resolves from the data watermark.
// The returned window always covers a complete period (no open/partial windows).
func (e *DetectionEngine) ResolveWindow(ctx context.Context, windowEnd time.Time) (Window, error) {
	if windowEnd.IsZero() {
		anchor, err := e.GetDataAnchor(ctx)
		if err != nil {
			return Window{}, fmt.Errorf("resolve window: %w", err)
		}
		windowEnd = anchor
	}
	windowEnd = snapToCompleteBoundary(windowEnd, e.cfg.Window)
	return Window{
		Start:    windowEnd.Add(-e.cfg.Window),
		End:      windowEnd,
		Duration: e.cfg.Window,
	}, nil
}

// GetDataAnchor returns max(event_time) from the watermark table (O(1)).
// Falls back to a full table scan if the watermark is not populated.
func (e *DetectionEngine) GetDataAnchor(ctx context.Context) (time.Time, error) {
	row, err := e.qe.Row(ctx, "data_anchor", query.GetDataAnchorSQL)
	if err != nil {
		if errors.Is(err, db.ErrNoRows) {
			row, err = e.qe.Row(ctx, "data_anchor_fallback", query.GetDataAnchorFallbackSQL)
		}
		if err != nil {
			return time.Time{}, fmt.Errorf("get data anchor: %w", err)
		}
	}
	anchor, ok := row["anchor"].(string)
	if !ok || anchor == "" {
		return time.Time{}, fmt.Errorf("get data anchor: empty result")
	}
	t, err := parseDataAnchor(anchor)
	if err != nil {
		return time.Time{}, fmt.Errorf("get data anchor: parse %q: %w", anchor, err)
	}
	return t, nil
}

func parseDataAnchor(anchor string) (time.Time, error) {
	layouts := []string{
		"2006-01-02 15:04:05.999999999",
		"2006-01-02 15:04:05",
		"2006-01-02",
	}
	for _, layout := range layouts {
		if parsed, err := time.ParseInLocation(layout, anchor, time.UTC); err == nil {
			return parsed.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported timestamp format")
}

// Detect runs all registered detectors concurrently for the given window.
// ErrInsufficientBaseline from any detector is treated as a warning, not an error.
func (e *DetectionEngine) Detect(ctx context.Context, w Window) (DetectionResult, error) {
	start := time.Now()
	e.logger.Info("detection started",
		slog.String("window_start", w.Start.Format(time.RFC3339)),
		slog.String("window_end", w.End.Format(time.RFC3339)),
		slog.String("grain", w.Grain()),
		slog.Int("detectors", len(e.detectors)),
	)

	// Inject a per-run baseline cache so detectors share SQL results
	ctx = baseline.WithCache(ctx)

	type result struct {
		signals []AnomalySignal
	}
	results := make([]result, len(e.detectors))

	g, gctx := errgroup.WithContext(ctx)
	for i, d := range e.detectors {
		i, d := i, d
		g.Go(func() error {
			sigs, err := d.Detect(gctx, w)
			if err != nil {
				if errors.Is(err, baseline.ErrInsufficientBaseline) {
					e.logger.Warn("insufficient baseline",
						slog.String("detector", d.Name()),
						slog.String("window_end", w.End.Format(time.RFC3339)),
					)
					return nil
				}
				return fmt.Errorf("detector %s: %w", d.Name(), err)
			}
			results[i] = result{signals: sigs}
			return nil
		})
	}

	if err := g.Wait(); err != nil {
		return DetectionResult{}, err
	}

	var allSignals []AnomalySignal
	for _, r := range results {
		allSignals = append(allSignals, r.signals...)
	}

	anomalies := filterAndSort(allSignals)

	elapsed := time.Since(start)
	e.logger.Info("detection complete",
		slog.Int("total_signals", len(allSignals)),
		slog.Int("anomalies", len(anomalies)),
		slog.Int64("elapsed_ms", elapsed.Milliseconds()),
	)

	return DetectionResult{
		Window:        w,
		Signals:       allSignals,
		Anomalies:     anomalies,
		ExecutionTime: elapsed,
	}, nil
}

// filterAndSort keeps anomalous signals and sorts by severity desc, then |z| desc.
func filterAndSort(signals []AnomalySignal) []AnomalySignal {
	var out []AnomalySignal
	for _, s := range signals {
		if s.IsAnomaly {
			out = append(out, s)
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Severity != out[j].Severity {
			return out[i].Severity > out[j].Severity
		}
		return math.Abs(out[i].ZScore) > math.Abs(out[j].ZScore)
	})
	return out
}

// snapToCompleteBoundary truncates t to the last complete boundary for the given duration.
func snapToCompleteBoundary(t time.Time, duration time.Duration) time.Time {
	if duration < 24*time.Hour {
		return t.Truncate(time.Hour)
	}
	return t.UTC().Truncate(24 * time.Hour)
}
