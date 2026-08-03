package chx

import (
	"context"
	"errors"
	"fmt"
	"testing"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/google/uuid"
)

// TestInsertSettingsRouteSmallChunksThroughTheServerBuffer pins the fix for the
// 2026-08-01 load test, where 22,314 batches averaged 55 rows because the
// generator's timer flush bypasses the --batch-size floor. Each became its own
// part. Small writes must now go async so the server coalesces them.
func TestInsertSettingsRouteSmallChunksThroughTheServerBuffer(t *testing.T) {
	cases := []struct {
		name       string
		rows       int
		forceAsync bool
		wantAsync  bool
	}{
		{"the measured generator batch", 55, false, true},
		{"the measured api batch", 144, false, true},
		{"just below the floor", AsyncInsertRowThreshold - 1, false, true},
		{"exactly at the floor", AsyncInsertRowThreshold, false, false},
		{"a properly sized batch", 50000, false, false},
		{"--async forces it regardless", 50000, true, true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			s := insertSettings("tok", tc.rows, tc.forceAsync)

			if s["insert_deduplication_token"] != "tok" {
				t.Errorf("token not propagated: %v", s["insert_deduplication_token"])
			}
			if got := s["async_insert"]; got != boolToInt(tc.wantAsync) {
				t.Errorf("%d rows: async_insert = %v, want %v", tc.rows, got, boolToInt(tc.wantAsync))
			}

			if tc.wantAsync {
				// Without this the dedup token is inert and a retry duplicates.
				if s["async_insert_deduplicate"] != 1 {
					t.Error("async path must enable async_insert_deduplicate or the token does nothing")
				}
				if s["wait_for_async_insert"] != 1 {
					t.Error("fire-and-forget would hide a failed write")
				}
				// events_raw has two dependent MVs; the docs say do not combine.
				if _, present := s["deduplicate_blocks_in_dependent_materialized_views"]; present {
					t.Error("must not combine dependent-MV dedup with async_insert")
				}
				return
			}
			if s["deduplicate_blocks_in_dependent_materialized_views"] != 1 {
				t.Error("sync path must close the retry hole through the dependent MVs")
			}
		})
	}
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// TestDedupTokenDistinguishesEveryChunking is the correctness property behind
// "re-running a load is a no-op".
//
// The token is what ClickHouse deduplicates on. If two chunks that hold
// different rows can produce the same token, the second one is silently
// dropped and the load loses data with no error anywhere.
func TestDedupTokenDistinguishesEveryChunking(t *testing.T) {
	base := LoaderOptions{Source: "csv:raw.csv", Fingerprint: "abc123", BatchSize: 50000}

	variants := map[string]LoaderOptions{
		"baseline":            base,
		"different source":    withOpts(base, func(o *LoaderOptions) { o.Source = "generator" }),
		"different file":      withOpts(base, func(o *LoaderOptions) { o.Fingerprint = "def456" }),
		"different batchsize": withOpts(base, func(o *LoaderOptions) { o.BatchSize = 10000 }),
	}

	seen := map[string]string{}
	for name, opts := range variants {
		l := &Loader{opts: opts}
		tok := l.dedupToken(0, 50000)
		if prev, clash := seen[tok]; clash {
			t.Errorf("%q and %q produce the same token %q", name, prev, tok)
		}
		seen[tok] = name
	}

	// Ordinal and row count must both move the token.
	l := &Loader{opts: base}
	if l.dedupToken(0, 50000) == l.dedupToken(1, 50000) {
		t.Error("ordinal does not affect the token")
	}
	if l.dedupToken(5, 50000) == l.dedupToken(5, 12345) {
		t.Error("row count does not affect the token — a short final chunk would collide")
	}
}

// TestBatchIDIsDeterministic: the batch UUID is derived from the token, so the
// same batch is identifiable across machines and runs.
func TestBatchIDIsDeterministic(t *testing.T) {
	l := &Loader{opts: LoaderOptions{Source: "csv:raw.csv", Fingerprint: "abc123", BatchSize: 50000}}

	tok := l.dedupToken(3, 50000)
	a := uuid.NewSHA1(batchNamespace, []byte(tok))
	b := uuid.NewSHA1(batchNamespace, []byte(tok))
	if a != b {
		t.Fatalf("batch id is not stable: %s vs %s", a, b)
	}
	if a == uuid.NewSHA1(batchNamespace, []byte(l.dedupToken(4, 50000))) {
		t.Error("different ordinals produced the same batch id")
	}
}

// TestIsRetryableStopsOnPermanentErrors: retrying a wrong table name or bad
// credentials only delays a clear error message.
func TestIsRetryableStopsOnPermanentErrors(t *testing.T) {
	permanent := []int32{16, 43, 47, 53, 60, 62, 81, 192, 193, 497, 516}
	for _, code := range permanent {
		err := fmt.Errorf("wrapped: %w", &clickhouse.Exception{Code: code, Message: "nope"})
		if IsRetryable(err) {
			t.Errorf("code %d (%s) should not be retried", code, permanentServerErrors[code])
		}
	}

	// TOO_MANY_PARTS resolves itself once merges catch up — retry it.
	transient := &clickhouse.Exception{Code: 252, Message: "too many parts"}
	if !IsRetryable(fmt.Errorf("wrapped: %w", transient)) {
		t.Error("TOO_MANY_PARTS should be retried")
	}
	// A bare network error carries no code.
	if !IsRetryable(errors.New("connection reset by peer")) {
		t.Error("an untyped transport error should be retried")
	}
	// Cancellation never is.
	if IsRetryable(context.Canceled) || IsRetryable(context.DeadlineExceeded) {
		t.Error("context errors must not be retried")
	}
	if IsRetryable(nil) {
		t.Error("nil is not an error")
	}
}

func TestInsertStatement(t *testing.T) {
	got := insertStatement("default", "events_raw", []string{"a", "b", "c"})
	if want := "INSERT INTO default.events_raw (a, b, c)"; got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func withOpts(base LoaderOptions, mutate func(*LoaderOptions)) LoaderOptions {
	mutate(&base)
	return base
}
