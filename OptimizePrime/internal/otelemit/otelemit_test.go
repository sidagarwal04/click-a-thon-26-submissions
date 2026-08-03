package otelemit_test

import (
	"encoding/json"
	"regexp"
	"testing"
	"time"

	"github.com/d-cryptic/clickathon/internal/otelemit"
)

var hex32 = regexp.MustCompile(`^[0-9a-f]{32}$`)
var hex16 = regexp.MustCompile(`^[0-9a-f]{16}$`)

func TestNewTraceID(t *testing.T) {
	t.Parallel()
	id, err := otelemit.NewTraceID()
	if err != nil {
		t.Fatalf("NewTraceID() error = %v", err)
	}
	if !hex32.MatchString(id) {
		t.Errorf("NewTraceID() = %q, want 32 lower-case hex chars (16 bytes)", id)
	}
}

func TestNewSpanID(t *testing.T) {
	t.Parallel()
	id, err := otelemit.NewSpanID()
	if err != nil {
		t.Fatalf("NewSpanID() error = %v", err)
	}
	if !hex16.MatchString(id) {
		t.Errorf("NewSpanID() = %q, want 16 lower-case hex chars (8 bytes)", id)
	}
}

func TestNewTraceIDIsRandom(t *testing.T) {
	t.Parallel()
	a, err := otelemit.NewTraceID()
	if err != nil {
		t.Fatalf("NewTraceID() error = %v", err)
	}
	b, err := otelemit.NewTraceID()
	if err != nil {
		t.Fatalf("NewTraceID() error = %v", err)
	}
	if a == b {
		t.Errorf("two calls to NewTraceID() returned the same id %q — collision or a broken RNG", a)
	}
}

// TestIntAttrEncodesAsJSONString pins the OTLP/HTTP JSON wire detail that a
// naive `json:"intValue"` int64 field would get wrong: the spec's JSON
// mapping represents int64 as a decimal STRING, because JSON numbers only
// round-trip exactly through float64's 53-bit mantissa. Getting this wrong
// would corrupt any duration_ms/rows_written attribute above 2^53.
func TestIntAttrEncodesAsJSONString(t *testing.T) {
	t.Parallel()
	attr := otelemit.IntAttr("rows_written", 121492)

	b, err := json.Marshal(attr)
	if err != nil {
		t.Fatalf("Marshal(IntAttr) error = %v", err)
	}

	var decoded struct {
		Key   string `json:"key"`
		Value struct {
			IntValue *string `json:"intValue"`
		} `json:"value"`
	}
	if err := json.Unmarshal(b, &decoded); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	if decoded.Value.IntValue == nil {
		t.Fatal("intValue is missing/null in the encoded JSON")
	}
	if *decoded.Value.IntValue != "121492" {
		t.Errorf("intValue = %q, want the STRING %q", *decoded.Value.IntValue, "121492")
	}
}

// TestSeverityConstantsAreLowerCase pins VERIFIED.md: HyperDX stores
// SeverityText lower-cased, so a saved search filtering `severity:error`
// only matches an emitted "error", never "ERROR". A future edit that
// capitalizes these constants would silently break every reconcile-failure
// alert without any test failing elsewhere.
func TestSeverityConstantsAreLowerCase(t *testing.T) {
	t.Parallel()
	for _, s := range []string{otelemit.SeverityInfo, otelemit.SeverityWarn, otelemit.SeverityError} {
		if s != stringsToLower(s) {
			t.Errorf("severity constant %q is not lower-case", s)
		}
	}
}

func stringsToLower(s string) string {
	b := []byte(s)
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + ('a' - 'A')
		}
	}
	return string(b)
}

func TestUnixNanoRoundTrips(t *testing.T) {
	t.Parallel()
	// Chosen so ns-since-epoch is well above 2^53 (float64's exact-integer
	// limit) — the case that would silently lose precision if UnixNano ever
	// went through a JSON number instead of a decimal string.
	tm := time.Date(2026, 7, 26, 10, 56, 0, 0, time.UTC)
	got := otelemit.UnixNano(tm)
	want := "1785063360000000000"
	if got != want {
		t.Errorf("UnixNano(%v) = %q, want %q", tm, got, want)
	}
}
