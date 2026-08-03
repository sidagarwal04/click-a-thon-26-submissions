package pipelinehealth_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/d-cryptic/clickathon/internal/pipelinehealth"
)

// The green and mismatch fixtures in testdata/ are NOT hand-written. Both are
// byte-for-byte captures of what tools/reconcile.sh wrote against Cloud on
// 2026-08-01 at commit d6c85e2:
//
//	testdata/reconcile_green.txt    — the gate passing (mismatched=0)
//	testdata/reconcile_mismatch.txt — a REAL failure: the cloud serving layer
//	    had drifted from the committed model (177 mismatched minutes,
//	    max_abs_diff=39, peak served 2917 vs truth 2887) until it was rebuilt
//	    from committed SQL. Genuine gate output, not a simulated failure.
//
// The previous fixture here was a hand-maintained string that pinned the
// PRE-81c0161 five-column format; when the hardened gate added `ord`/`scope`
// columns and a SUMMARY row, the tests kept passing while the parser matched
// zero rows in production. Captured files make the fixture regenerable
// (re-run the gate, `cp evidence/reconcile.txt testdata/...`) instead of
// hand-editable. That old format survives below only as oldFormatEvidence,
// which must now parse as NOT a pass.

func TestReadReconcileEvidence_GreenFixture(t *testing.T) {
	t.Parallel()

	ev, found, err := pipelinehealth.ReadReconcileEvidence(filepath.Join("testdata", "reconcile_green.txt"))
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if !found {
		t.Fatal("found = false, want true")
	}
	if ev.Target != "cloud" || ev.Commit != "d6c85e2" {
		t.Errorf("target/commit = %q/%q, want cloud/d6c85e2", ev.Target, ev.Commit)
	}

	s := ev.Summary
	if !s.Found {
		t.Fatal("Summary.Found = false, want true")
	}
	if s.MinutesCompared != 17028 {
		t.Errorf("Summary.MinutesCompared = %d, want 17028", s.MinutesCompared)
	}
	if s.Mismatched != 0 {
		t.Errorf("Summary.Mismatched = %d, want 0", s.Mismatched)
	}
	if s.MaxAbsDiff != 0 {
		t.Errorf("Summary.MaxAbsDiff = %d, want 0", s.MaxAbsDiff)
	}
	if s.Peak != 2887 {
		t.Errorf("Summary.Peak = %d, want 2887", s.Peak)
	}

	if !ev.Pass() {
		t.Error("Pass() = false, want true — the gate is green")
	}
	if got := ev.MaxAbsDelta(); got != 0 {
		t.Errorf("MaxAbsDelta() = %d, want 0", got)
	}

	// The five derived sample rows — and ONLY those. Section 2 (MODEL
	// COMPARISON) rows in THIS fixture carry no PASS/MISMATCH verdict, so the
	// verdict requirement alone keeps them out here; the section fence itself
	// is pinned separately by TestReadReconcileEvidence_SectionFence.
	if len(ev.Minutes) != 5 {
		t.Fatalf("len(Minutes) = %d, want 5", len(ev.Minutes))
	}
	for _, m := range ev.Minutes {
		if m.Scope != "sample" {
			t.Errorf("Minutes scope = %q, want \"sample\": %+v", m.Scope, m)
		}
		if m.Verdict != "PASS" {
			t.Errorf("Minutes verdict = %q, want PASS: %+v", m.Verdict, m)
		}
	}

	// The documented peak minute: 2026-07-26 10:56:00, 2887 = 2887.
	peak := ev.Minutes[3]
	wantMinute := time.Date(2026, 7, 26, 10, 56, 0, 0, time.UTC)
	if !peak.Minute.Equal(wantMinute) {
		t.Errorf("Minutes[3].Minute = %v, want %v", peak.Minute, wantMinute)
	}
	if peak.TruthFromEvRaw != 2887 || peak.ServedFromDelta != 2887 {
		t.Errorf("Minutes[3] truth/served = %d/%d, want 2887/2887", peak.TruthFromEvRaw, peak.ServedFromDelta)
	}
}

func TestReadReconcileEvidence_MismatchFixture(t *testing.T) {
	t.Parallel()

	ev, found, err := pipelinehealth.ReadReconcileEvidence(filepath.Join("testdata", "reconcile_mismatch.txt"))
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if !found {
		t.Fatal("found = false, want true")
	}
	if ev.Pass() {
		t.Error("Pass() = true, want false — 177 minutes disagreed")
	}
	if got := ev.MaxAbsDelta(); got != 39 {
		t.Errorf("MaxAbsDelta() = %d, want 39 (from the SUMMARY, which saw all 17028 minutes)", got)
	}
	if ev.Summary.Mismatched != 177 {
		t.Errorf("Summary.Mismatched = %d, want 177", ev.Summary.Mismatched)
	}
	if ev.Summary.Verdict != "MISMATCH" {
		t.Errorf("Summary.Verdict = %q, want MISMATCH", ev.Summary.Verdict)
	}

	// 20 mismatching minutes (the gate's cap) + 5 samples.
	if len(ev.Minutes) != 25 {
		t.Fatalf("len(Minutes) = %d, want 25", len(ev.Minutes))
	}
	var mismatchRows int
	for _, m := range ev.Minutes {
		if m.Scope == "MISMATCH" {
			mismatchRows++
		}
	}
	if mismatchRows != 20 {
		t.Errorf("MISMATCH-scope rows = %d, want 20", mismatchRows)
	}

	// The peak minute as the real drift served it: 2917 against truth 2887.
	var peak *pipelinehealth.ReconcileMinute
	wantMinute := time.Date(2026, 7, 26, 10, 56, 0, 0, time.UTC)
	for i := range ev.Minutes {
		m := &ev.Minutes[i]
		if m.Scope == "sample" && m.Minute.Equal(wantMinute) {
			peak = m
			break
		}
	}
	if peak == nil {
		t.Fatal("peak sample minute 2026-07-26 10:56:00 not parsed")
	}
	if peak.TruthFromEvRaw != 2887 || peak.ServedFromDelta != 2917 || peak.Delta != 30 || peak.Verdict != "MISMATCH" {
		t.Errorf("peak sample = %+v, want truth=2887 served=2917 delta=30 MISMATCH", *peak)
	}
}

// oldFormatEvidence is the PRE-81c0161 gate output: five columns, no SUMMARY
// row. The old parser read this happily — which is exactly how it kept
// passing its tests while parsing zero rows of the real output. Under the
// summary-based parser this file must be NOT a pass, even though every
// visible row says PASS: no SUMMARY means no attestation of how much was
// compared, and unattested evidence fails.
const oldFormatEvidence = `RECONCILE — serving layer vs ev_raw
target: cloud   commit: 34c3f05

== 1. THE GATE — truth recomputed from ev_raw, five minutes
   (peak, both data boundaries, two arbitrary; any non-zero delta is a failure)

   ┌──────────────minute─┬─truth_from_ev_raw─┬─served_from_delta─┬─delta─┬─verdict─┐
1. │ 2026-07-14 15:43:00 │                 1 │                 1 │     0 │ PASS    │
2. │ 2026-07-26 06:09:00 │                16 │                16 │     0 │ PASS    │
3. │ 2026-07-26 10:56:00 │              2887 │              2887 │     0 │ PASS    │
4. │ 2026-07-26 11:10:00 │              2450 │              2450 │     0 │ PASS    │
5. │ 2026-07-26 11:31:00 │                 5 │                 5 │     0 │ PASS    │
   └─────────────────────┴───────────────────┴───────────────────┴───────┴─────────┘

== 2. MODEL COMPARISON — the same minutes under three definitions

   ┌──────────────minute─┬─session_aware─┬─stateless─┬─naive_session_span─┬─naive_overcount─┬─pct_overcount─┐
1. │ 2026-07-14 15:43:00 │             1 │         1 │                  1 │               0 │             0 │
   └─────────────────────┴───────────────┴───────────┴────────────────────┴─────────────────┴───────────────┘
`

func writeFixture(t *testing.T, contents string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "reconcile.txt")
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	return path
}

func TestReadReconcileEvidence_OldFormatIsNotAPass(t *testing.T) {
	t.Parallel()
	path := writeFixture(t, oldFormatEvidence)

	ev, found, err := pipelinehealth.ReadReconcileEvidence(path)
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if !found {
		t.Fatal("found = false, want true")
	}
	if ev.Summary.Found {
		t.Error("Summary.Found = true, want false — pre-81c0161 output has no SUMMARY row")
	}
	if ev.Pass() {
		t.Error("Pass() = true, want false — all-PASS rows without a SUMMARY are unattested evidence")
	}
	// The detail rows themselves still parse (they feed logs), including the
	// MaxAbsDelta fallback when no summary exists.
	if len(ev.Minutes) != 5 {
		t.Errorf("len(Minutes) = %d, want 5", len(ev.Minutes))
	}
	if got := ev.MaxAbsDelta(); got != 0 {
		t.Errorf("MaxAbsDelta() = %d, want 0 (row fallback)", got)
	}
}

// TestReadReconcileEvidence_OldFormatMismatchStillVisible pins the historical
// incremental-absorption bug shape (2924 served vs 2887 truth, delta 37): even
// in the unattested old format, the failure magnitude must surface through the
// row fallback rather than reading as 0.
func TestReadReconcileEvidence_OldFormatMismatchStillVisible(t *testing.T) {
	t.Parallel()
	path := writeFixture(t, strings.Replace(oldFormatEvidence,
		"3. │ 2026-07-26 10:56:00 │              2887 │              2887 │     0 │ PASS    │",
		"3. │ 2026-07-26 10:56:00 │              2887 │              2924 │    37 │ MISMATCH│", 1))

	ev, _, err := pipelinehealth.ReadReconcileEvidence(path)
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if ev.Pass() {
		t.Error("Pass() = true, want false")
	}
	if got := ev.MaxAbsDelta(); got != 37 {
		t.Errorf("MaxAbsDelta() = %d, want 37 (row fallback)", got)
	}
}

func TestReadReconcileEvidence_EmptyFileIsNotAPass(t *testing.T) {
	t.Parallel()
	path := writeFixture(t, "")

	ev, found, err := pipelinehealth.ReadReconcileEvidence(path)
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if !found {
		t.Fatal("found = false, want true — the file exists, it is just empty")
	}
	if ev.Pass() {
		t.Error("Pass() = true, want false — an empty evidence file must fail")
	}
	if got := ev.MaxAbsDelta(); got != 0 {
		t.Errorf("MaxAbsDelta() = %d, want 0", got)
	}
}

func TestReadReconcileEvidence_MalformedFileIsNotAPass(t *testing.T) {
	t.Parallel()
	path := writeFixture(t, "PASS PASS PASS\nnothing here resembles the gate\nSUMMARY but no key=value tokens │ PASS │\n")

	ev, found, err := pipelinehealth.ReadReconcileEvidence(path)
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if !found {
		t.Fatal("found = false, want true")
	}
	if ev.Pass() {
		t.Error("Pass() = true, want false — malformed evidence must fail")
	}
	if ev.Summary.Found {
		t.Error("Summary.Found = true, want false — a SUMMARY line missing its tokens is no summary")
	}
}

func TestReadReconcileEvidence_NotFound(t *testing.T) {
	t.Parallel()
	_, found, err := pipelinehealth.ReadReconcileEvidence(filepath.Join(t.TempDir(), "does-not-exist.txt"))
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil (missing file is a legitimate state)", err)
	}
	if found {
		t.Error("found = true, want false")
	}
}

// TestReadReconcileEvidence_SurvivesAddedColumn is the regression the whole
// rewrite exists for: the pre-81c0161 parser pinned an exact column count, so
// the hardened gate's two new columns made it match zero rows while its tests
// stayed green. Inserting yet another column into today's format must leave
// both the SUMMARY (key=value tokens) and the detail rows (timestamp-anchored)
// readable.
func TestReadReconcileEvidence_SurvivesAddedColumn(t *testing.T) {
	t.Parallel()
	green, err := os.ReadFile(filepath.Join("testdata", "reconcile_green.txt"))
	if err != nil {
		t.Fatalf("read green fixture: %v", err)
	}
	// Simulate the gate growing a column: a new field after `scope`.
	widened := strings.ReplaceAll(string(green), "│ SUMMARY │", "│ SUMMARY │ v2 │")
	widened = strings.ReplaceAll(widened, "│ sample  │", "│ sample  │ v2 │")
	path := writeFixture(t, widened)

	ev, _, err := pipelinehealth.ReadReconcileEvidence(path)
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if !ev.Summary.Found {
		t.Fatal("Summary.Found = false, want true — key=value tokens are position-independent")
	}
	if !ev.Pass() {
		t.Error("Pass() = false, want true — an added column must not fail a green gate")
	}
	if len(ev.Minutes) != 5 {
		t.Errorf("len(Minutes) = %d, want 5 — detail rows must survive an added column too", len(ev.Minutes))
	}
}

// TestReadReconcileEvidence_SectionFence pins the fence itself: a row OUTSIDE
// section 1 that has the full gate-row shape — timestamp, three integers, a
// PASS verdict — must not be parsed as a gate minute. Without this file the
// fence was untested (an audit probe removed it and every test stayed green,
// because no fixture had a verdict-bearing row outside the gate section); a
// future gate section that DOES emit verdicts elsewhere would silently pollute
// Minutes.
func TestReadReconcileEvidence_SectionFence(t *testing.T) {
	t.Parallel()
	fixture := `RECONCILE — serving layer vs ev_raw
target: cloud   commit: d6c85e2

== 1. THE GATE — truth recomputed from ev_raw, five minutes

   ┌─ord─┬─scope───┬─c1─────────────────────┬─c2───────────┬─c3─────────────┬─c4────────┬─verdict─┐
1. │   0 │ SUMMARY │ minutes_compared=17028 │ mismatched=0 │ max_abs_diff=0 │ peak=2887 │ PASS    │
2. │   2 │ sample  │ 2026-07-26 10:56:00    │ 2887         │ 2887           │ 0         │ PASS    │
   └─────┴─────────┴────────────────────────┴──────────────┴────────────────┴───────────┴─────────┘

== 2. PER-MINUTE SPOT CHECK — informational, NOT part of the gate

1. │ 2026-07-26 11:10:00 │ 2450 │ 2450 │ 0 │ PASS │
`
	path := writeFixture(t, fixture)

	ev, _, err := pipelinehealth.ReadReconcileEvidence(path)
	if err != nil {
		t.Fatalf("ReadReconcileEvidence() error = %v, want nil", err)
	}
	if len(ev.Minutes) != 1 {
		t.Fatalf("len(Minutes) = %d, want 1 — the section-2 row leaked past the fence: %+v", len(ev.Minutes), ev.Minutes)
	}
	want := time.Date(2026, 7, 26, 10, 56, 0, 0, time.UTC)
	if !ev.Minutes[0].Minute.Equal(want) {
		t.Errorf("Minutes[0] = %v, want the section-1 sample %v", ev.Minutes[0].Minute, want)
	}
}

// TestPass_SummaryGuards exercises the three-way conjunction directly: a
// summary that attests nothing (0 minutes), or contradicts itself, must not
// pass no matter what its verdict string says.
func TestPass_SummaryGuards(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name    string
		summary pipelinehealth.ReconcileSummary
		want    bool
	}{
		{"green", pipelinehealth.ReconcileSummary{Found: true, MinutesCompared: 17028, Mismatched: 0, Verdict: "PASS"}, true},
		{"no summary parsed", pipelinehealth.ReconcileSummary{}, false},
		{"zero minutes compared", pipelinehealth.ReconcileSummary{Found: true, MinutesCompared: 0, Mismatched: 0, Verdict: "PASS"}, false},
		{"verdict PASS but mismatched>0", pipelinehealth.ReconcileSummary{Found: true, MinutesCompared: 100, Mismatched: 3, Verdict: "PASS"}, false},
		{"verdict MISMATCH", pipelinehealth.ReconcileSummary{Found: true, MinutesCompared: 100, Mismatched: 3, Verdict: "MISMATCH"}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			ev := pipelinehealth.ReconcileEvidence{Summary: tc.summary}
			if got := ev.Pass(); got != tc.want {
				t.Errorf("Pass() = %t, want %t for %+v", got, tc.want, tc.summary)
			}
		})
	}
}
