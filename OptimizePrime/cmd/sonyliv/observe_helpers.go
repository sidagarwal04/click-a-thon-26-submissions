package main

import (
	"context"
	"fmt"
	"math"
	"strings"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/d-cryptic/clickathon/internal/otelemit"
	"github.com/d-cryptic/clickathon/internal/pipelinehealth"
)

// observeRun tracks the one trace an `observe` invocation produces: a root
// span plus one child span per signal gathered, all sharing traceID so
// HyperDX (or a future Langfuse emitter reusing the same id — see
// docs/OBSERVABILITY.md) can show them as one run.
type observeRun struct {
	traceID    string
	rootSpanID string
	start      time.Time
	spans      []otelemit.Span
}

func newObserveRun() (*observeRun, error) {
	traceID, err := otelemit.NewTraceID()
	if err != nil {
		return nil, fmt.Errorf("new observe run: %w", err)
	}
	rootSpanID, err := otelemit.NewSpanID()
	if err != nil {
		return nil, fmt.Errorf("new observe run: %w", err)
	}
	return &observeRun{traceID: traceID, rootSpanID: rootSpanID, start: time.Now()}, nil
}

// finish appends the root span, covering everything from newObserveRun to
// this call. Child spans must already be in run.spans by the time this runs.
func (r *observeRun) finish() {
	r.spans = append(r.spans, otelemit.Span{
		TraceID:           r.traceID,
		SpanID:            r.rootSpanID,
		Name:              "sonyliv.observe.run",
		Kind:              otelemit.SpanKindInternal,
		StartTimeUnixNano: otelemit.UnixNano(r.start),
		EndTimeUnixNano:   otelemit.UnixNano(time.Now()),
		Status:            &otelemit.Status{Code: otelemit.StatusOK},
	})
}

func newChildSpan(run *observeRun, name string, start time.Time, attrs []otelemit.KeyValue, spanErr error) (otelemit.Span, error) {
	id, err := otelemit.NewSpanID()
	if err != nil {
		return otelemit.Span{}, fmt.Errorf("new child span %q: %w", name, err)
	}
	status := &otelemit.Status{Code: otelemit.StatusOK}
	if spanErr != nil {
		status = &otelemit.Status{Code: otelemit.StatusError, Message: spanErr.Error()}
	}
	return otelemit.Span{
		TraceID:           run.traceID,
		SpanID:            id,
		ParentSpanID:      run.rootSpanID,
		Name:              name,
		Kind:              otelemit.SpanKindInternal,
		StartTimeUnixNano: otelemit.UnixNano(start),
		EndTimeUnixNano:   otelemit.UnixNano(time.Now()),
		Attributes:        attrs,
		Status:            status,
	}, nil
}

func observeWatermark(ctx context.Context, conn driver.Conn, run *observeRun) (*pipelinehealth.Watermark, otelemit.Span, error) {
	start := time.Now()
	wm, queryErr := pipelinehealth.QueryWatermark(ctx, conn)

	attrs := []otelemit.KeyValue{
		otelemit.IntAttr("sonyliv.watermark.sealed_lag_s", wm.SealedLagSeconds),
		otelemit.BoolAttr("sonyliv.watermark.healthy", wm.Healthy()),
	}
	span, err := newChildSpan(run, "pipeline.watermark.query", start, attrs, queryErr)
	if err != nil {
		return &wm, otelemit.Span{}, err
	}
	if queryErr != nil {
		return &wm, span, fmt.Errorf("observe watermark: %w", queryErr)
	}
	return &wm, span, nil
}

func observeBuildStages(ctx context.Context, conn driver.Conn, database string, run *observeRun) ([]pipelinehealth.BuildStage, otelemit.Span, error) {
	start := time.Now()
	stages, queryErr := pipelinehealth.QueryBuildStages(ctx, conn, database)

	names := make([]string, 0, len(stages))
	for _, s := range stages {
		names = append(names, fmt.Sprintf("%s(found=%t)", s.Stage, s.Found))
	}
	attrs := []otelemit.KeyValue{otelemit.StringAttr("sonyliv.build.stages", strings.Join(names, ","))}
	span, err := newChildSpan(run, "pipeline.build_stages.query", start, attrs, queryErr)
	if err != nil {
		return stages, otelemit.Span{}, err
	}
	if queryErr != nil {
		return stages, span, fmt.Errorf("observe build stages: %w", queryErr)
	}
	return stages, span, nil
}

func observeReconcile(path string, run *observeRun) (*pipelinehealth.ReconcileEvidence, bool, otelemit.Span, error) {
	start := time.Now()
	ev, found, readErr := pipelinehealth.ReadReconcileEvidence(path)

	attrs := []otelemit.KeyValue{
		otelemit.BoolAttr("sonyliv.reconcile.evidence_found", found),
		otelemit.StringAttr("sonyliv.reconcile.path", path),
	}
	span, err := newChildSpan(run, "pipeline.reconcile_evidence.read", start, attrs, readErr)
	if err != nil {
		return &ev, found, otelemit.Span{}, err
	}
	if readErr != nil {
		return &ev, found, span, fmt.Errorf("observe reconcile evidence: %w", readErr)
	}
	return &ev, found, span, nil
}

func buildMetrics(
	wm *pipelinehealth.Watermark,
	stages []pipelinehealth.BuildStage,
	ev *pipelinehealth.ReconcileEvidence,
	evFound bool,
) []otelemit.Metric {
	now := otelemit.UnixNano(time.Now())

	metrics := []otelemit.Metric{
		otelemit.GaugeMetric(
			"sonyliv.watermark.sealed_lag_seconds",
			"Seconds the sealed (finalized) delta tier is behind raw ingestion. NEGATIVE is the healthy steady state (up to ~2min tail grace) — only POSITIVE means the finalizer is genuinely behind.",
			"s",
			otelemit.Point(now, float64(wm.SealedLagSeconds)),
		),
		otelemit.GaugeMetric(
			"sonyliv.watermark.healthy",
			"1 if sealed_lag_s <= 0 (finalizer caught up), else 0.",
			"1",
			otelemit.Point(now, boolToFloat(wm.Healthy())),
		),
		otelemit.GaugeMetric(
			"sonyliv.watermark.hour_tier_complete",
			"1 if the newest stored hour in cc_hour_agg is sealed rather than still accumulating.",
			"1",
			otelemit.Point(now, boolToFloat(wm.HourTierLastHourComplete)),
		),
	}

	var durationPoints, rowsPoints, freshnessPoints []otelemit.NumberDataPoint
	for _, s := range stages {
		if !s.Found {
			continue
		}
		stageAttr := otelemit.StringAttr("stage", s.Stage)
		durationPoints = append(durationPoints, otelemit.Point(now, float64(s.DurationMS)/1000.0, stageAttr))
		rowsPoints = append(rowsPoints, otelemit.Point(now, float64(s.RowsWritten), stageAttr))
		freshnessPoints = append(freshnessPoints, otelemit.Point(now, s.SecondsSinceLastRun, stageAttr))
	}
	if len(durationPoints) > 0 {
		metrics = append(metrics,
			otelemit.GaugeMetric("sonyliv.build.stage_duration_seconds",
				"Duration of the most recent tools/build-model.sh stage, from system.query_log.query_duration_ms.",
				"s", durationPoints...),
			otelemit.GaugeMetric("sonyliv.build.stage_rows_written",
				"Rows written by the most recent run of this build stage.",
				"1", rowsPoints...),
			otelemit.GaugeMetric("sonyliv.build.seconds_since_last_run",
				"Freshness of the served answer: how long ago this build stage last ran.",
				"s", freshnessPoints...),
		)
	}

	if evFound {
		pass := boolToFloat(ev.Pass())
		metrics = append(metrics,
			otelemit.GaugeMetric("sonyliv.reconcile.gate_pass",
				"1 if every sampled minute in the last reconcile run matched ev_raw truth, else 0.",
				"1", otelemit.Point(now, pass)),
			otelemit.GaugeMetric("sonyliv.reconcile.max_abs_delta",
				"Largest |served - truth| across the reconcile gate's sampled minutes.",
				"1", otelemit.Point(now, float64(ev.MaxAbsDelta()))),
			otelemit.GaugeMetric("sonyliv.reconcile.evidence_age_seconds",
				"How long ago evidence/reconcile.txt was generated — the gate's own freshness.",
				"s", otelemit.Point(now, time.Since(ev.GeneratedAt).Seconds())),
		)
	}

	return metrics
}

func buildLogs(
	wm *pipelinehealth.Watermark,
	stages []pipelinehealth.BuildStage,
	ev *pipelinehealth.ReconcileEvidence,
	evFound bool,
	run *observeRun,
) []otelemit.LogRecord {
	now := otelemit.UnixNano(time.Now())
	var logs []otelemit.LogRecord

	wmSeverity := otelemit.SeverityInfo
	if !wm.Healthy() {
		wmSeverity = otelemit.SeverityError
	}
	logs = append(logs, otelemit.Log(now, wmSeverity, fmt.Sprintf(
		"watermark: raw=%s sealed=%s sealed_lag_s=%d healthy=%t hour_tier_complete=%t",
		wm.RawWatermark.Format(time.RFC3339), wm.SealedWatermark.Format(time.RFC3339),
		wm.SealedLagSeconds, wm.Healthy(), wm.HourTierLastHourComplete,
	), []otelemit.KeyValue{
		otelemit.IntAttr("sealed_lag_s", wm.SealedLagSeconds),
		otelemit.BoolAttr("healthy", wm.Healthy()),
	}, run.traceID, run.rootSpanID))

	for _, s := range stages {
		if !s.Found {
			logs = append(logs, otelemit.Log(now, otelemit.SeverityWarn,
				fmt.Sprintf("build stage %s: no run recorded in system.query_log yet", s.Stage),
				[]otelemit.KeyValue{otelemit.StringAttr("stage", s.Stage)}, run.traceID, run.rootSpanID))
			continue
		}
		logs = append(logs, otelemit.Log(now, otelemit.SeverityInfo, fmt.Sprintf(
			"build stage %s: %dms, %d rows written, last ran %s ago",
			s.Stage, s.DurationMS, s.RowsWritten, time.Duration(s.SecondsSinceLastRun*float64(time.Second)).Round(time.Second),
		), []otelemit.KeyValue{
			otelemit.StringAttr("stage", s.Stage),
			otelemit.IntAttr("duration_ms", clampUint64ToInt64(s.DurationMS)),
			otelemit.IntAttr("rows_written", clampUint64ToInt64(s.RowsWritten)),
		}, run.traceID, run.rootSpanID))
	}

	switch {
	case !evFound:
		logs = append(logs, otelemit.Log(now, otelemit.SeverityWarn,
			fmt.Sprintf("reconcile evidence not found at %s — run `make reconcile` first", ev.Path),
			nil, run.traceID, run.rootSpanID))
	case ev.Pass():
		logs = append(logs, otelemit.Log(now, otelemit.SeverityInfo, fmt.Sprintf(
			"reconcile gate: PASS (%d minutes compared, 0 mismatched, peak %d, evidence commit %s, %s old)",
			ev.Summary.MinutesCompared, ev.Summary.Peak, ev.Commit, time.Since(ev.GeneratedAt).Round(time.Second),
		), []otelemit.KeyValue{
			otelemit.BoolAttr("pass", true),
			otelemit.StringAttr("commit", ev.Commit),
		}, run.traceID, run.rootSpanID))
	case !ev.Summary.Found:
		logs = append(logs, otelemit.Log(now, otelemit.SeverityError, fmt.Sprintf(
			"reconcile gate: FAIL — no SUMMARY row parsed from %s; the evidence is unreadable or predates the hardened gate (commit %s, %s old)",
			ev.Path, ev.Commit, time.Since(ev.GeneratedAt).Round(time.Second),
		), []otelemit.KeyValue{
			otelemit.BoolAttr("pass", false),
			otelemit.StringAttr("commit", ev.Commit),
		}, run.traceID, run.rootSpanID))
	default:
		logs = append(logs, otelemit.Log(now, otelemit.SeverityError, fmt.Sprintf(
			"reconcile gate: FAIL — %d of %d minutes mismatch, max |delta|=%d (evidence commit %s, %s old)",
			ev.Summary.Mismatched, ev.Summary.MinutesCompared, ev.MaxAbsDelta(), ev.Commit, time.Since(ev.GeneratedAt).Round(time.Second),
		), []otelemit.KeyValue{
			otelemit.BoolAttr("pass", false),
			otelemit.IntAttr("max_abs_delta", ev.MaxAbsDelta()),
			otelemit.StringAttr("commit", ev.Commit),
		}, run.traceID, run.rootSpanID))
	}

	return logs
}

func boolToFloat(b bool) float64 {
	if b {
		return 1
	}
	return 0
}

// clampUint64ToInt64 converts a row/duration count for an int64-typed OTLP
// attribute, clamping at math.MaxInt64 instead of wrapping — gosec G115 flags
// the bare uint64->int64 conversion because it CAN overflow in general; a
// query_log row/ms count never will in practice, but clamping (rather than a
// lint suppression) is the version of "handle it" that stays correct if that
// assumption is ever wrong.
func clampUint64ToInt64(v uint64) int64 {
	if v > math.MaxInt64 {
		return math.MaxInt64
	}
	return int64(v) // #nosec G115 -- bounded by the check above
}

func printSummary(
	wm *pipelinehealth.Watermark,
	stages []pipelinehealth.BuildStage,
	ev *pipelinehealth.ReconcileEvidence,
	evFound bool,
	traceID string,
) {
	fmt.Printf("trace %s\n\n", traceID)
	fmt.Printf("watermark   sealed_lag_s=%-6d healthy=%-5t hour_tier_complete=%t\n",
		wm.SealedLagSeconds, wm.Healthy(), wm.HourTierLastHourComplete)
	for _, s := range stages {
		if !s.Found {
			fmt.Printf("build       %-18s no run recorded\n", s.Stage)
			continue
		}
		fmt.Printf("build       %-18s %6dms  %8d rows written  %s ago\n",
			s.Stage, s.DurationMS, s.RowsWritten,
			time.Duration(s.SecondsSinceLastRun*float64(time.Second)).Round(time.Second))
	}
	switch {
	case !evFound:
		fmt.Printf("reconcile   no evidence at %s\n", ev.Path)
	default:
		fmt.Printf("reconcile   pass=%-5t max_abs_delta=%-4d minutes_compared=%-6d commit=%-10s %s old\n",
			ev.Pass(), ev.MaxAbsDelta(), ev.Summary.MinutesCompared, ev.Commit, time.Since(ev.GeneratedAt).Round(time.Second))
	}
}
