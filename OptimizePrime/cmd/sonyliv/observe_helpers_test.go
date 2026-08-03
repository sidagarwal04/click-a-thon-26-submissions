package main

import (
	"context"
	"errors"
	"io"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/d-cryptic/clickathon/internal/otelemit"
	"github.com/d-cryptic/clickathon/internal/pipelinehealth"
)

var (
	traceIDRe = regexp.MustCompile(`^[0-9a-f]{32}$`)
	spanIDRe  = regexp.MustCompile(`^[0-9a-f]{16}$`)
)

// fakeConn implements just QueryRow over an embedded driver.Conn; anything
// else the helpers might start calling panics loudly in the test.
type fakeConn struct {
	driver.Conn
	queryRow func(query string) driver.Row
}

func (c *fakeConn) QueryRow(_ context.Context, query string, _ ...any) driver.Row {
	return c.queryRow(query)
}

type fakeRow struct {
	scan func(dest ...any) error
}

func (r *fakeRow) Err() error                { return nil }
func (r *fakeRow) Scan(dest ...any) error    { return r.scan(dest...) }
func (r *fakeRow) ScanStruct(dest any) error { _ = dest; return errors.New("ScanStruct not modeled") }

// watermarkConn returns a conn whose single row scans a v_cc_watermark shape
// with the given sealed lag (dest[2]) — every other column stays NULL, which
// QueryWatermark must tolerate.
func watermarkConn(lag int64) *fakeConn {
	return &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(dest ...any) error {
			v := lag
			*(dest[2].(**int64)) = &v
			return nil
		}}
	}}
}

func errConn(err error) *fakeConn {
	return &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(...any) error { return err }}
	}}
}

func TestObserveRunLifecycle(t *testing.T) {
	t.Parallel()
	run, err := newObserveRun()
	if err != nil {
		t.Fatalf("newObserveRun() error = %v", err)
	}
	if !traceIDRe.MatchString(run.traceID) || !spanIDRe.MatchString(run.rootSpanID) {
		t.Fatalf("run ids = %q/%q, want 32/16 lower-hex chars", run.traceID, run.rootSpanID)
	}

	run.finish()
	if len(run.spans) != 1 {
		t.Fatalf("after finish, len(spans) = %d, want exactly the root span", len(run.spans))
	}
	root := run.spans[0]
	if root.Name != "sonyliv.observe.run" || root.SpanID != run.rootSpanID || root.TraceID != run.traceID {
		t.Errorf("root span = %+v, want name sonyliv.observe.run carrying the run's ids", root)
	}
	if root.ParentSpanID != "" {
		t.Errorf("root span has parent %q, want none", root.ParentSpanID)
	}
	if root.Status == nil || root.Status.Code != otelemit.StatusOK {
		t.Errorf("root span status = %+v, want OK", root.Status)
	}
}

func TestNewChildSpanStatus(t *testing.T) {
	t.Parallel()
	run, err := newObserveRun()
	if err != nil {
		t.Fatalf("newObserveRun() error = %v", err)
	}

	ok, err := newChildSpan(run, "child.ok", time.Now(), nil, nil)
	if err != nil {
		t.Fatalf("newChildSpan(nil err) error = %v", err)
	}
	if ok.Status == nil || ok.Status.Code != otelemit.StatusOK {
		t.Errorf("ok span status = %+v, want StatusOK", ok.Status)
	}
	if ok.ParentSpanID != run.rootSpanID || ok.TraceID != run.traceID {
		t.Errorf("child span not parented to the run: %+v", ok)
	}

	failed, err := newChildSpan(run, "child.fail", time.Now(), nil, errors.New("scan exploded"))
	if err != nil {
		t.Fatalf("newChildSpan(spanErr) error = %v", err)
	}
	if failed.Status == nil || failed.Status.Code != otelemit.StatusError || failed.Status.Message != "scan exploded" {
		t.Errorf("failed span status = %+v, want StatusError carrying the message", failed.Status)
	}
}

func TestObserveWatermark(t *testing.T) {
	t.Parallel()
	run, err := newObserveRun()
	if err != nil {
		t.Fatalf("newObserveRun() error = %v", err)
	}

	wm, span, err := observeWatermark(context.Background(), watermarkConn(-90), run)
	if err != nil {
		t.Fatalf("observeWatermark() error = %v", err)
	}
	if wm.SealedLagSeconds != -90 || !wm.Healthy() {
		t.Errorf("watermark = %+v, want lag=-90 healthy", wm)
	}
	if span.Name != "pipeline.watermark.query" || span.Status.Code != otelemit.StatusOK {
		t.Errorf("span = %+v, want pipeline.watermark.query / OK", span)
	}

	boom := errors.New("no such view")
	_, span, err = observeWatermark(context.Background(), errConn(boom), run)
	if !errors.Is(err, boom) {
		t.Fatalf("observeWatermark(err conn) error = %v, want it to wrap the query error", err)
	}
	if span.Status == nil || span.Status.Code != otelemit.StatusError {
		t.Errorf("error span status = %+v, want StatusError — the failure must still be visible as a span", span.Status)
	}
}

func TestObserveBuildStages(t *testing.T) {
	t.Parallel()
	run, err := newObserveRun()
	if err != nil {
		t.Fatalf("newObserveRun() error = %v", err)
	}

	conn := &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(dest ...any) error {
			*(dest[0].(*time.Time)) = time.Now().Add(-time.Minute)
			*(dest[1].(*uint64)) = 5230
			*(dest[2].(*uint64)) = 896400
			*(dest[3].(*uint64)) = 121492
			return nil
		}}
	}}
	stages, span, err := observeBuildStages(context.Background(), conn, "sonyliv", run)
	if err != nil {
		t.Fatalf("observeBuildStages() error = %v", err)
	}
	if len(stages) != 2 || !stages[0].Found || !stages[1].Found {
		t.Errorf("stages = %+v, want both build stages found", stages)
	}
	if span.Name != "pipeline.build_stages.query" {
		t.Errorf("span name = %q, want pipeline.build_stages.query", span.Name)
	}

	boom := errors.New("query_log unreadable")
	_, span, err = observeBuildStages(context.Background(), errConn(boom), "sonyliv", run)
	if !errors.Is(err, boom) {
		t.Fatalf("observeBuildStages(err conn) error = %v, want wrapped query error", err)
	}
	if span.Status == nil || span.Status.Code != otelemit.StatusError {
		t.Errorf("error span status = %+v, want StatusError", span.Status)
	}
}

// greenEvidence is the CURRENT gate format — ord + scope columns and a SUMMARY
// row — matching what tools/reconcile.sh writes today (see the byte-for-byte
// captures in internal/pipelinehealth/testdata/).
const greenEvidence = `RECONCILE — serving layer vs ev_raw
target: cloud   commit: d6c85e2

== 1. THE GATE — truth recomputed from ev_raw, five minutes

   ┌─ord─┬─scope───┬─c1─────────────────────┬─c2───────────┬─c3─────────────┬─c4────────┬─verdict─┐
1. │   0 │ SUMMARY │ minutes_compared=17028 │ mismatched=0 │ max_abs_diff=0 │ peak=2887 │ PASS    │
2. │   2 │ sample  │ 2026-07-26 10:56:00    │ 2887         │ 2887           │ 0         │ PASS    │
   └─────┴─────────┴────────────────────────┴──────────────┴────────────────┴───────────┴─────────┘
`

func TestObserveReconcile(t *testing.T) {
	t.Parallel()
	run, err := newObserveRun()
	if err != nil {
		t.Fatalf("newObserveRun() error = %v", err)
	}

	path := filepath.Join(t.TempDir(), "reconcile.txt")
	if err := os.WriteFile(path, []byte(greenEvidence), 0o600); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	ev, found, span, err := observeReconcile(path, run)
	if err != nil {
		t.Fatalf("observeReconcile() error = %v", err)
	}
	if !found || !ev.Pass() {
		t.Errorf("found=%t Pass()=%t, want a found, passing gate", found, ev.Pass())
	}
	if span.Name != "pipeline.reconcile_evidence.read" {
		t.Errorf("span name = %q, want pipeline.reconcile_evidence.read", span.Name)
	}

	// Missing evidence is a legitimate state (fresh clone), not an error.
	_, found, _, err = observeReconcile(filepath.Join(t.TempDir(), "absent.txt"), run)
	if err != nil {
		t.Fatalf("observeReconcile(missing) error = %v, want nil", err)
	}
	if found {
		t.Error("found = true for a missing file, want false")
	}
}

func metricNames(metrics []otelemit.Metric) map[string]bool {
	names := make(map[string]bool, len(metrics))
	for _, m := range metrics {
		names[m.Name] = true
	}
	return names
}

// gaugeValue returns the single data-point value of the named gauge, failing
// the test if the metric is absent, has no gauge arm, or has more/fewer than
// one point. Metric NAMES appearing is not the contract a dashboard depends
// on — the VALUES are; an audit probe showed an inverted gate_pass survived a
// names-only assertion.
func gaugeValue(t *testing.T, metrics []otelemit.Metric, name string) float64 {
	t.Helper()
	for _, m := range metrics {
		if m.Name != name {
			continue
		}
		if m.Gauge == nil || len(m.Gauge.DataPoints) != 1 {
			t.Fatalf("metric %s: want exactly one gauge point, got %+v", name, m.Gauge)
		}
		p := m.Gauge.DataPoints[0]
		if p.AsDouble == nil {
			t.Fatalf("metric %s: point has no asDouble value", name)
		}
		return *p.AsDouble
	}
	t.Fatalf("metric %s not emitted", name)
	return 0
}

func TestBuildMetrics(t *testing.T) {
	t.Parallel()
	wm := &pipelinehealth.Watermark{SealedLagSeconds: -90, HourTierLastHourComplete: true}
	stages := []pipelinehealth.BuildStage{
		{Stage: "session_intervals", Found: true, DurationMS: 5230, RowsWritten: 121492, SecondsSinceLastRun: 120},
		{Stage: "cc_minute_delta", Found: false},
	}
	ev := &pipelinehealth.ReconcileEvidence{
		GeneratedAt: time.Now().Add(-10 * time.Minute),
		Summary:     pipelinehealth.ReconcileSummary{Found: true, MinutesCompared: 17028, Verdict: "PASS"},
	}

	metrics := buildMetrics(wm, stages, ev, true)
	for name, want := range map[string]float64{
		"sonyliv.watermark.sealed_lag_seconds": -90,
		"sonyliv.watermark.healthy":            1,
		"sonyliv.watermark.hour_tier_complete": 1,
		"sonyliv.build.stage_duration_seconds": 5.23,
		"sonyliv.build.stage_rows_written":     121492,
		"sonyliv.build.seconds_since_last_run": 120,
		"sonyliv.reconcile.gate_pass":          1,
		"sonyliv.reconcile.max_abs_delta":      0,
	} {
		if got := gaugeValue(t, metrics, name); got != want {
			t.Errorf("%s = %v, want %v", name, got, want)
		}
	}
	if age := gaugeValue(t, metrics, "sonyliv.reconcile.evidence_age_seconds"); age < 590 || age > 620 {
		t.Errorf("evidence_age_seconds = %v, want ~600 for evidence generated 10 minutes ago", age)
	}

	// A failing gate must emit gate_pass=0 and surface the drift magnitude —
	// the two numbers the alert fires on.
	failing := &pipelinehealth.ReconcileEvidence{
		GeneratedAt: time.Now(),
		Summary: pipelinehealth.ReconcileSummary{
			Found: true, MinutesCompared: 17028, Mismatched: 177, MaxAbsDiff: 39, Verdict: "MISMATCH"},
	}
	unhealthy := &pipelinehealth.Watermark{SealedLagSeconds: 600}
	metrics = buildMetrics(unhealthy, nil, failing, true)
	for name, want := range map[string]float64{
		"sonyliv.watermark.sealed_lag_seconds": 600,
		"sonyliv.watermark.healthy":            0,
		"sonyliv.watermark.hour_tier_complete": 0,
		"sonyliv.reconcile.gate_pass":          0,
		"sonyliv.reconcile.max_abs_delta":      39,
	} {
		if got := gaugeValue(t, metrics, name); got != want {
			t.Errorf("%s = %v, want %v", name, got, want)
		}
	}

	// No evidence and no found stages: those metric families must be ABSENT,
	// not emitted with fabricated zeros a dashboard would read as healthy.
	names := metricNames(buildMetrics(wm, []pipelinehealth.BuildStage{{Stage: "session_intervals", Found: false}}, ev, false))
	for name := range names {
		if strings.HasPrefix(name, "sonyliv.build.") || strings.HasPrefix(name, "sonyliv.reconcile.") {
			t.Errorf("buildMetrics emitted %s with no data behind it", name)
		}
	}
}

func TestBuildLogsSeverities(t *testing.T) {
	t.Parallel()
	run, err := newObserveRun()
	if err != nil {
		t.Fatalf("newObserveRun() error = %v", err)
	}
	healthy := &pipelinehealth.Watermark{SealedLagSeconds: -90}
	behind := &pipelinehealth.Watermark{SealedLagSeconds: 600}
	found := []pipelinehealth.BuildStage{{Stage: "session_intervals", Found: true, DurationMS: 5230, RowsWritten: 121492}}
	notFound := []pipelinehealth.BuildStage{{Stage: "cc_minute_delta", Found: false}}
	pass := &pipelinehealth.ReconcileEvidence{Summary: pipelinehealth.ReconcileSummary{
		Found: true, MinutesCompared: 17028, Mismatched: 0, Peak: 2887, Verdict: "PASS"}}
	mismatch := &pipelinehealth.ReconcileEvidence{Summary: pipelinehealth.ReconcileSummary{
		Found: true, MinutesCompared: 17028, Mismatched: 177, MaxAbsDiff: 39, Verdict: "MISMATCH"}}
	unattested := &pipelinehealth.ReconcileEvidence{Path: "evidence/reconcile.txt"}

	cases := []struct {
		name     string
		wm       *pipelinehealth.Watermark
		stages   []pipelinehealth.BuildStage
		ev       *pipelinehealth.ReconcileEvidence
		evFound  bool
		severity string // of the LAST log line (the reconcile one)
		bodySub  string
	}{
		{"all green", healthy, found, pass, true, otelemit.SeverityInfo, "reconcile gate: PASS"},
		{"gate mismatch is an error log", healthy, found, mismatch, true, otelemit.SeverityError, "177 of 17028 minutes mismatch"},
		{"unattested evidence is an error log", healthy, found, unattested, true, otelemit.SeverityError, "no SUMMARY row parsed"},
		{"missing evidence is a warn", healthy, found, unattested, false, otelemit.SeverityWarn, "make reconcile"},
		{"stage without a run warns", healthy, notFound, pass, true, otelemit.SeverityInfo, "reconcile gate: PASS"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			logs := buildLogs(tc.wm, tc.stages, tc.ev, tc.evFound, run)
			if len(logs) < 2 {
				t.Fatalf("len(logs) = %d, want at least watermark + reconcile lines", len(logs))
			}
			last := logs[len(logs)-1]
			if last.SeverityText != tc.severity {
				t.Errorf("reconcile log severity = %q, want %q", last.SeverityText, tc.severity)
			}
			if last.Body.StringValue == nil || !strings.Contains(*last.Body.StringValue, tc.bodySub) {
				t.Errorf("reconcile log body = %v, want it to contain %q", last.Body.StringValue, tc.bodySub)
			}
			if last.TraceID != run.traceID {
				t.Error("log not correlated to the observe run's trace")
			}
		})
	}

	// The watermark line itself: unhealthy lag must log at error severity —
	// this is the alertable signal, and info-level would never page anyone.
	logs := buildLogs(behind, nil, pass, true, run)
	if logs[0].SeverityText != otelemit.SeverityError {
		t.Errorf("unhealthy watermark log severity = %q, want error", logs[0].SeverityText)
	}
	// A stage with no recorded run logs a warn between watermark and reconcile.
	logs = buildLogs(healthy, notFound, pass, true, run)
	if logs[1].SeverityText != otelemit.SeverityWarn || !strings.Contains(*logs[1].Body.StringValue, "no run recorded") {
		t.Errorf("not-found stage log = %q/%v, want warn about no recorded run", logs[1].SeverityText, logs[1].Body.StringValue)
	}
}

func TestBoolToFloat(t *testing.T) {
	t.Parallel()
	if boolToFloat(true) != 1 || boolToFloat(false) != 0 {
		t.Error("boolToFloat: want true→1, false→0")
	}
}

func TestClampUint64ToInt64(t *testing.T) {
	t.Parallel()
	if got := clampUint64ToInt64(121492); got != 121492 {
		t.Errorf("clampUint64ToInt64(121492) = %d, want the value unchanged", got)
	}
	if got := clampUint64ToInt64(math.MaxUint64); got != math.MaxInt64 {
		t.Errorf("clampUint64ToInt64(MaxUint64) = %d, want clamped to MaxInt64, not wrapped negative", got)
	}
}

// captureStdout redirects os.Stdout for one call. printSummary writes with
// fmt.Printf, so this is the only way to assert on it. Not parallel-safe.
func captureStdout(t *testing.T, fn func()) string {
	t.Helper()
	old := os.Stdout
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatalf("pipe: %v", err)
	}
	os.Stdout = w
	fn()
	os.Stdout = old
	_ = w.Close()

	out, err := io.ReadAll(r)
	if err != nil {
		t.Fatalf("read captured stdout: %v", err)
	}
	return string(out)
}

func TestPrintSummary(t *testing.T) {
	wm := &pipelinehealth.Watermark{SealedLagSeconds: -90}
	stages := []pipelinehealth.BuildStage{
		{Stage: "session_intervals", Found: true, DurationMS: 5230, RowsWritten: 121492, SecondsSinceLastRun: 120},
		{Stage: "cc_minute_delta", Found: false},
	}
	ev := &pipelinehealth.ReconcileEvidence{
		Path:        "evidence/reconcile.txt",
		Commit:      "d6c85e2",
		GeneratedAt: time.Now(),
		Summary:     pipelinehealth.ReconcileSummary{Found: true, MinutesCompared: 17028, Verdict: "PASS"},
	}

	out := captureStdout(t, func() { printSummary(wm, stages, ev, true, "cafe0123") })
	for _, want := range []string{"trace cafe0123", "sealed_lag_s=-90", "session_intervals", "no run recorded", "pass=true", "minutes_compared=17028"} {
		if !strings.Contains(out, want) {
			t.Errorf("printSummary output missing %q:\n%s", want, out)
		}
	}

	out = captureStdout(t, func() { printSummary(wm, nil, ev, false, "cafe0123") })
	if !strings.Contains(out, "no evidence at evidence/reconcile.txt") {
		t.Errorf("printSummary without evidence should say where it looked:\n%s", out)
	}
}
