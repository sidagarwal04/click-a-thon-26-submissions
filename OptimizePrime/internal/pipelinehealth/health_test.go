package pipelinehealth_test

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/d-cryptic/clickathon/internal/pipelinehealth"
)

// fakeConn stands in for a live ClickHouse connection. It embeds driver.Conn
// so only the one method this package actually calls — QueryRow — needs an
// implementation; anything else panics, which is exactly what a test should do
// if the code under test starts calling methods these tests do not model.
type fakeConn struct {
	driver.Conn
	queryRow func(query string) driver.Row
}

func (c *fakeConn) QueryRow(_ context.Context, query string, _ ...any) driver.Row {
	return c.queryRow(query)
}

// fakeRow implements driver.Row with a pluggable Scan.
type fakeRow struct {
	scan func(dest ...any) error
}

func (r *fakeRow) Err() error                { return nil }
func (r *fakeRow) Scan(dest ...any) error    { return r.scan(dest...) }
func (r *fakeRow) ScanStruct(dest any) error { _ = dest; return errors.New("ScanStruct not modeled") }

// set assigns v into a **T scan destination the way clickhouse-go does for a
// Nullable column: the outer pointer receives the address of a value.
func set[T any](t *testing.T, dest any, v T) {
	t.Helper()
	p, ok := dest.(**T)
	if !ok {
		t.Fatalf("scan dest is %T, want **%T", dest, v)
	}
	*p = &v
}

// The seven v_cc_watermark column values the fake row scans, all DISTINCT so
// a swapped pair of scan destinations cannot go unnoticed — an audit probe
// showed that swapping raw/sealed survived an only-not-zero assertion.
var (
	wmRaw       = time.Date(2026, 7, 26, 11, 31, 0, 0, time.UTC)
	wmSealed    = wmRaw.Add(90 * time.Second)
	wmHourLast  = wmRaw.Truncate(time.Hour)
	wmHourFinal = wmRaw.Truncate(time.Hour).Add(-time.Hour)
	wmTrend     = wmRaw.Add(-30 * time.Second)
)

// watermarkRow builds a driver.Row that scans the seven v_cc_watermark
// columns. Nil-able behavior is exercised by the caller leaving fields unset.
func watermarkRow(t *testing.T, sealedLag int64, hourComplete uint8) driver.Row {
	t.Helper()
	return &fakeRow{scan: func(dest ...any) error {
		if len(dest) != 7 {
			t.Fatalf("Scan got %d dests, want 7 (v_cc_watermark has 7 columns)", len(dest))
		}
		set(t, dest[0], wmRaw)
		set(t, dest[1], wmSealed)
		set(t, dest[2], sealedLag)
		set(t, dest[3], wmHourLast)
		set(t, dest[4], wmHourFinal)
		set(t, dest[5], hourComplete)
		set(t, dest[6], wmTrend)
		return nil
	}}
}

func TestQueryWatermark_HealthySteadyState(t *testing.T) {
	t.Parallel()
	// NEGATIVE lag is the HEALTHY steady state (sealed tier leads raw by the
	// 60s tail grace) — the sign convention the brief calls out as the trap.
	conn := &fakeConn{queryRow: func(query string) driver.Row {
		if !strings.Contains(query, "v_cc_watermark") {
			t.Errorf("QueryWatermark queried %q, want v_cc_watermark", query)
		}
		return watermarkRow(t, -90, 1)
	}}

	wm, err := pipelinehealth.QueryWatermark(context.Background(), conn)
	if err != nil {
		t.Fatalf("QueryWatermark() error = %v, want nil", err)
	}
	if wm.SealedLagSeconds != -90 {
		t.Errorf("SealedLagSeconds = %d, want -90", wm.SealedLagSeconds)
	}
	if !wm.Healthy() {
		t.Error("Healthy() = false, want true — negative lag IS the healthy steady state")
	}
	if !wm.HourTierLastHourComplete {
		t.Error("HourTierLastHourComplete = false, want true")
	}
	// Each timestamp must land in ITS field. The five columns carry distinct
	// values precisely so a swapped pair of scan destinations fails here.
	if !wm.RawWatermark.Equal(wmRaw) || !wm.SealedWatermark.Equal(wmSealed) {
		t.Errorf("raw/sealed = %v/%v, want %v/%v", wm.RawWatermark, wm.SealedWatermark, wmRaw, wmSealed)
	}
	if !wm.HourTierLastHour.Equal(wmHourLast) || !wm.HourFinalThrough.Equal(wmHourFinal) {
		t.Errorf("hour_last/hour_final = %v/%v, want %v/%v", wm.HourTierLastHour, wm.HourFinalThrough, wmHourLast, wmHourFinal)
	}
	if !wm.TrendWatermark.Equal(wmTrend) {
		t.Errorf("TrendWatermark = %v, want %v", wm.TrendWatermark, wmTrend)
	}
}

func TestQueryWatermark_PositiveLagIsUnhealthy(t *testing.T) {
	t.Parallel()
	conn := &fakeConn{queryRow: func(string) driver.Row { return watermarkRow(t, 300, 0) }}

	wm, err := pipelinehealth.QueryWatermark(context.Background(), conn)
	if err != nil {
		t.Fatalf("QueryWatermark() error = %v, want nil", err)
	}
	if wm.Healthy() {
		t.Error("Healthy() = true, want false — POSITIVE lag means the finalizer is genuinely behind")
	}
	if wm.HourTierLastHourComplete {
		t.Error("HourTierLastHourComplete = true, want false for a 0 flag")
	}
}

func TestQueryWatermark_AllNullsScanToZeroValues(t *testing.T) {
	t.Parallel()
	// An empty pipeline (fresh database, view exists, no data) returns NULLs;
	// every dest stays nil and the typed struct must come back zero-valued
	// rather than dereferencing a nil pointer.
	conn := &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(...any) error { return nil }}
	}}

	wm, err := pipelinehealth.QueryWatermark(context.Background(), conn)
	if err != nil {
		t.Fatalf("QueryWatermark() error = %v, want nil", err)
	}
	if wm != (pipelinehealth.Watermark{}) {
		t.Errorf("all-NULL row = %+v, want zero-valued Watermark", wm)
	}
}

func TestQueryWatermark_ScanErrorIsWrapped(t *testing.T) {
	t.Parallel()
	scanErr := errors.New("code: 60, no such view")
	conn := &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(...any) error { return scanErr }}
	}}

	_, err := pipelinehealth.QueryWatermark(context.Background(), conn)
	if err == nil {
		t.Fatal("QueryWatermark() error = nil, want scan failure")
	}
	if !errors.Is(err, scanErr) {
		t.Errorf("error %v does not wrap the scan error (errors.Is = false)", err)
	}
	if !strings.Contains(err.Error(), "v_cc_watermark") {
		t.Errorf("error %q does not name the view it failed on", err)
	}
}

// buildStageRow scans the four system.query_log columns queryLatestInsert
// reads: event_time, query_duration_ms, read_rows, written_rows.
func buildStageRow(t *testing.T, at time.Time, durMS, read, written uint64) driver.Row {
	t.Helper()
	return &fakeRow{scan: func(dest ...any) error {
		if len(dest) != 4 {
			t.Fatalf("Scan got %d dests, want 4", len(dest))
		}
		*(dest[0].(*time.Time)) = at
		*(dest[1].(*uint64)) = durMS
		*(dest[2].(*uint64)) = read
		*(dest[3].(*uint64)) = written
		return nil
	}}
}

// dispatchStages routes the two stage queries the way the real query_log
// predicate does: cc_minute_delta is the one that must NOT touch ev_raw.
func dispatchStages(intervals, delta driver.Row) func(string) driver.Row {
	return func(query string) driver.Row {
		if strings.Contains(query, "NOT has") {
			return delta
		}
		return intervals
	}
}

func TestQueryBuildStages_BothStagesFound(t *testing.T) {
	t.Parallel()
	ranAt := time.Now().Add(-2 * time.Minute)
	var queries []string
	dispatch := dispatchStages(
		buildStageRow(t, ranAt, 5230, 896400, 121492),
		buildStageRow(t, ranAt.Add(6*time.Second), 1210, 121492, 17028),
	)
	conn := &fakeConn{queryRow: func(query string) driver.Row {
		queries = append(queries, query)
		return dispatch(query)
	}}

	stages, err := pipelinehealth.QueryBuildStages(context.Background(), conn, "sonyliv")
	if err != nil {
		t.Fatalf("QueryBuildStages() error = %v, want nil", err)
	}

	// The predicates ARE the stage definitions — a wrong table name or a
	// dropped filter finds the wrong query_log rows while every value below
	// still checks out (an audit probe corrupted `.ev_raw` and survived a
	// routing-only fake). Pin each stage's load-bearing fragments, with the
	// database qualifier attached.
	if len(queries) != 2 {
		t.Fatalf("QueryBuildStages issued %d queries, want 2", len(queries))
	}
	wantFragments := [][]string{
		{`has(tables, 'sonyliv.session_intervals')`, `has(tables, 'sonyliv.ev_raw')`},
		{`has(tables, 'sonyliv.cc_minute_delta')`, `has(tables, 'sonyliv.session_intervals')`, `NOT has(tables, 'sonyliv.ev_raw')`},
	}
	for i, fragments := range wantFragments {
		for _, frag := range append(fragments, `type = 'QueryFinish'`, `query_kind = 'Insert'`) {
			if !strings.Contains(queries[i], frag) {
				t.Errorf("stage %d query missing %q:\n%s", i, frag, queries[i])
			}
		}
	}
	if len(stages) != 2 {
		t.Fatalf("len(stages) = %d, want 2", len(stages))
	}
	if stages[0].Stage != "session_intervals" || stages[1].Stage != "cc_minute_delta" {
		t.Errorf("stage order = %q,%q, want session_intervals,cc_minute_delta — build order is part of the contract",
			stages[0].Stage, stages[1].Stage)
	}
	si := stages[0]
	if !si.Found {
		t.Error("session_intervals Found = false, want true")
	}
	if si.DurationMS != 5230 || si.RowsRead != 896400 || si.RowsWritten != 121492 {
		t.Errorf("session_intervals = %+v, want 5230ms / 896400 read / 121492 written", si)
	}
	if si.SecondsSinceLastRun < 100 || si.SecondsSinceLastRun > 200 {
		t.Errorf("SecondsSinceLastRun = %.1f, want ~120 for a run 2 minutes ago", si.SecondsSinceLastRun)
	}
}

func TestQueryBuildStages_NoRunRecordedIsNotAnError(t *testing.T) {
	t.Parallel()
	// A fresh database has no query_log rows for the build yet. That is the
	// zero-rows sentinel, and must surface as Found=false — not as an error,
	// and never as a fabricated stage row.
	ranAt := time.Now().Add(-time.Hour)
	conn := &fakeConn{queryRow: dispatchStages(
		buildStageRow(t, ranAt, 5230, 896400, 121492),
		&fakeRow{scan: func(...any) error { return sql.ErrNoRows }},
	)}

	stages, err := pipelinehealth.QueryBuildStages(context.Background(), conn, "sonyliv")
	if err != nil {
		t.Fatalf("QueryBuildStages() error = %v, want nil — zero rows is a legitimate state", err)
	}
	if !stages[0].Found {
		t.Error("session_intervals Found = false, want true")
	}
	if stages[1].Found {
		t.Error("cc_minute_delta Found = true, want false when query_log has no such insert")
	}
	if stages[1].Stage != "cc_minute_delta" {
		t.Errorf("not-found stage keeps its name: got %q", stages[1].Stage)
	}
}

func TestQueryBuildStages_QueryErrorNamesTheStage(t *testing.T) {
	t.Parallel()
	boom := errors.New("code: 497, not enough privileges")
	conn := &fakeConn{queryRow: func(string) driver.Row {
		return &fakeRow{scan: func(...any) error { return boom }}
	}}

	_, err := pipelinehealth.QueryBuildStages(context.Background(), conn, "sonyliv")
	if err == nil {
		t.Fatal("QueryBuildStages() error = nil, want the query failure")
	}
	if !errors.Is(err, boom) {
		t.Errorf("error %v does not wrap the driver error", err)
	}
	if !strings.Contains(err.Error(), `"session_intervals"`) {
		t.Errorf("error %q does not name which stage failed", err)
	}
}
