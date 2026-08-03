package pipelinehealth

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// ReconcileMinute is one detail row of THE GATE's output: either a derived
// sample minute or one of the (capped) mismatching minutes. These rows are
// EVIDENCE for humans and logs; the pass/fail verdict comes from the SUMMARY
// row alone — see ReconcileSummary.
type ReconcileMinute struct {
	Minute          time.Time
	Scope           string // "sample" or "MISMATCH" ("" in pre-81c0161 output)
	TruthFromEvRaw  int64
	ServedFromDelta int64
	Delta           int64
	Verdict         string // verdictPass or verdictMismatch
}

// The two verdict tokens sql/90_reconcile.sql emits, per row and in the
// SUMMARY.
const (
	verdictPass     = "PASS"
	verdictMismatch = "MISMATCH"
)

// ReconcileSummary is the gate's own accounting of what it checked — the
// first output row of sql/90_reconcile.sql, e.g.:
//
//	│ 0 │ SUMMARY │ minutes_compared=17028 │ mismatched=0 │ max_abs_diff=0 │ peak=2887 │ PASS │
//
// It exists because the gate once returned zero rows on an unseen day and was
// read as a pass; the summary makes "how much was checked" explicit. This
// parser trusts it over counting detail rows for the same reason a future
// column addition must not silently turn a green gate into zero parsed rows —
// the key=value tokens are position-independent.
type ReconcileSummary struct {
	Found           bool
	MinutesCompared int64
	Mismatched      int64
	MaxAbsDiff      int64
	Peak            int64
	Verdict         string // "PASS" or "MISMATCH"
}

// ReconcileEvidence is tools/reconcile.sh's output (evidence/reconcile.txt),
// parsed. This package reads that file rather than re-running
// sql/90_reconcile.sql itself: the gate's own script already writes
// deterministic, git-tracked evidence, and re-running the full ev_raw
// recompute here would (a) duplicate a ~900k-row scan on every observe call
// and (b) race the evidence file against whichever agent's own reconcile
// run is in flight. Freshness of the READING is exposed via GeneratedAt /
// the caller's own now() so staleness is visible rather than hidden.
type ReconcileEvidence struct {
	Path        string
	Target      string
	Commit      string
	GeneratedAt time.Time // evidence file's mtime
	Summary     ReconcileSummary
	Minutes     []ReconcileMinute
}

// Pass reports whether the gate's SUMMARY row attests a clean run over a
// non-empty comparison. No SUMMARY row — an empty file, a malformed file, or
// pre-81c0161 output — is NOT a pass: evidence that cannot be read must fail
// loudly, exactly like the gate itself fails when minutes_compared is absent.
// All three conditions are required; a verdict that disagrees with its own
// mismatch count means the evidence is corrupt and is also not a pass.
func (e *ReconcileEvidence) Pass() bool {
	s := e.Summary
	return s.Found && s.Verdict == verdictPass && s.MinutesCompared >= 1 && s.Mismatched == 0
}

// MaxAbsDelta is the largest |served - truth| the gate saw, the single number
// a dashboard tile would want if the gate is failing. It comes from the
// SUMMARY (which covers every compared minute), falling back to the parsed
// detail rows only when no summary exists.
func (e *ReconcileEvidence) MaxAbsDelta() int64 {
	if e.Summary.Found {
		return e.Summary.MaxAbsDiff
	}
	var m int64
	for _, r := range e.Minutes {
		d := r.Delta
		if d < 0 {
			d = -d
		}
		if d > m {
			m = d
		}
	}
	return m
}

var (
	targetCommitRe = regexp.MustCompile(`target:\s*(\S+)\s+commit:\s*(\S+)`)

	minutesComparedRe = regexp.MustCompile(`minutes_compared=(-?\d+)`)
	mismatchedRe      = regexp.MustCompile(`mismatched=(-?\d+)`)
	maxAbsDiffRe      = regexp.MustCompile(`max_abs_diff=(-?\d+)`)
	peakRe            = regexp.MustCompile(`peak=(-?\d+)`)
)

// ReadReconcileEvidence parses evidence/reconcile.txt. It returns
// (ReconcileEvidence{}, nil, false) — via the ok return — if the file does
// not exist yet, which is a legitimate state (a fresh clone before the first
// `make reconcile`), not an error.
func ReadReconcileEvidence(path string) (ReconcileEvidence, bool, error) {
	info, err := os.Stat(path)
	if os.IsNotExist(err) {
		return ReconcileEvidence{}, false, nil
	}
	if err != nil {
		return ReconcileEvidence{}, false, fmt.Errorf("stat %s: %w", path, err)
	}

	f, err := os.Open(path) // #nosec G304 -- path is an operator-controlled flag/default, not user input
	if err != nil {
		return ReconcileEvidence{}, false, fmt.Errorf("open %s: %w", path, err)
	}
	defer func() { _ = f.Close() }()

	ev := ReconcileEvidence{Path: path, GeneratedAt: info.ModTime()}
	inGate := false

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()

		if m := targetCommitRe.FindStringSubmatch(line); m != nil {
			ev.Target, ev.Commit = m[1], m[2]
			continue
		}
		// Section 2 (MODEL COMPARISON) rows share the box-drawing shape and
		// carry parseable minutes — the section fence keeps them out.
		if strings.HasPrefix(strings.TrimSpace(line), "== 1.") {
			inGate = true
			continue
		}
		if strings.HasPrefix(strings.TrimSpace(line), "== 2.") {
			inGate = false
			continue
		}
		if !inGate || !strings.Contains(line, "│") {
			continue
		}
		if s, ok := parseSummaryRow(line); ok {
			ev.Summary = s
			continue
		}
		if row, ok := parseGateRow(line); ok {
			ev.Minutes = append(ev.Minutes, row)
		}
	}
	if err := scanner.Err(); err != nil {
		return ReconcileEvidence{}, false, fmt.Errorf("scan %s: %w", path, err)
	}
	return ev, true, nil
}

// parseSummaryRow parses THE GATE's SUMMARY row by its key=value tokens, not
// by column position, so adding a column (which is exactly what broke the
// pre-81c0161 sample-row parser) cannot break it. All four tokens plus a
// recognizable verdict are required — a partial match is treated as no
// summary, which Pass() then treats as failure.
func parseSummaryRow(line string) (ReconcileSummary, bool) {
	if !strings.Contains(line, "SUMMARY") {
		return ReconcileSummary{}, false
	}
	verdict, ok := verdictField(line)
	if !ok {
		return ReconcileSummary{}, false
	}
	s := ReconcileSummary{Verdict: verdict}
	for _, field := range []struct {
		re  *regexp.Regexp
		dst *int64
	}{
		{minutesComparedRe, &s.MinutesCompared},
		{mismatchedRe, &s.Mismatched},
		{maxAbsDiffRe, &s.MaxAbsDiff},
		{peakRe, &s.Peak},
	} {
		m := field.re.FindStringSubmatch(line)
		if m == nil {
			return ReconcileSummary{}, false
		}
		v, err := strconv.ParseInt(m[1], 10, 64)
		if err != nil {
			return ReconcileSummary{}, false
		}
		*field.dst = v
	}
	s.Found = true
	return s, true
}

// parseGateRow parses one PrettyCompact detail row of THE GATE's table, e.g.:
//
//  5. │   2 │ sample  │ 2026-07-26 10:56:00 │ 2887 │ 2887 │ 0 │ PASS    │
//
// Rather than pinning the exact column count (the pre-81c0161 parser did, and
// an added column made it match zero rows), it anchors on the shape of the
// data: the first field that parses as a timestamp, followed by three
// integers, with a PASS/MISMATCH verdict somewhere after. Detail rows feed
// logs and dashboards only — Pass() never depends on them.
func parseGateRow(line string) (ReconcileMinute, bool) {
	parts := strings.Split(line, "│")
	fields := make([]string, 0, len(parts))
	for _, p := range parts {
		fields = append(fields, strings.TrimSpace(p))
	}

	verdict, ok := verdictField(line)
	if !ok {
		return ReconcileMinute{}, false
	}

	for i, f := range fields {
		minute, err := time.Parse("2006-01-02 15:04:05", f)
		if err != nil {
			continue
		}
		if i+3 >= len(fields) {
			return ReconcileMinute{}, false
		}
		truth, err1 := strconv.ParseInt(fields[i+1], 10, 64)
		served, err2 := strconv.ParseInt(fields[i+2], 10, 64)
		delta, err3 := strconv.ParseInt(fields[i+3], 10, 64)
		if err1 != nil || err2 != nil || err3 != nil {
			return ReconcileMinute{}, false
		}
		row := ReconcileMinute{
			Minute:          minute,
			TruthFromEvRaw:  truth,
			ServedFromDelta: served,
			Delta:           delta,
			Verdict:         verdict,
		}
		if i > 0 && (fields[i-1] == "sample" || fields[i-1] == verdictMismatch) {
			row.Scope = fields[i-1]
		}
		return row, true
	}
	return ReconcileMinute{}, false
}

// verdictField finds the row's verdict: the LAST field that is exactly PASS
// or MISMATCH, so a future trailing column cannot displace it and a leading
// scope column (which also says MISMATCH) cannot shadow it.
func verdictField(line string) (string, bool) {
	parts := strings.Split(line, "│")
	for i := len(parts) - 1; i >= 0; i-- {
		switch strings.TrimSpace(parts[i]) {
		case verdictPass:
			return verdictPass, true
		case verdictMismatch:
			return verdictMismatch, true
		}
	}
	return "", false
}
