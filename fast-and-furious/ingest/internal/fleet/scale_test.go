package fleet

import (
	"fmt"
	"testing"
	"time"
)

// Where does the current design actually break? Run with:
//
//	go test ./internal/fleet/ -run TestScaleProfile -v -timeout 300s
//
// Not an assertion — a measurement, so the numbers in any scaling decision come
// from this machine rather than from arithmetic on the back of an envelope.
func TestScaleProfile(t *testing.T) {
	if testing.Short() {
		t.Skip("scale profile is slow")
	}
	for _, n := range []int{1_000, 10_000, 50_000, 100_000} {
		r := NewRegistry(lease, 1)
		created := 0
		for created < n {
			batch := n - created
			if batch > MaxPerCreate {
				batch = MaxPerCreate
			}
			sp := spec(batch)
			sp.TTLMinutes = 600
			if _, _, err := r.Create(sp, t0); err != nil {
				t.Fatalf("create at %d: %v", created, err)
			}
			created += batch
		}

		// One sweep with every session due: the worst tick.
		start := time.Now()
		rows := r.Sweep(at(31 * time.Second))
		sweepDue := time.Since(start)

		// One sweep with nothing due: the common tick, 4x a second.
		start = time.Now()
		r.Sweep(at(32 * time.Second))
		sweepIdle := time.Since(start)

		start = time.Now()
		r.Stats(at(32 * time.Second))
		stats := time.Since(start)

		start = time.Now()
		_, total := r.List(Filter{}, 0, 50, at(32*time.Second))
		list := time.Since(start)

		start = time.Now()
		pts := r.Curve(Filter{}, t0, at(30*time.Minute), at(30*time.Minute))
		curve := time.Since(start)

		start = time.Now()
		snap := r.snapshot()
		snapshot := time.Since(start)

		fmt.Printf("n=%-7d sweep(due)=%-9s sweep(idle)=%-9s stats=%-9s list=%-9s curve=%-9s snapshot=%-9s | rows=%d total=%d pts=%d dirty=%d\n",
			n, sweepDue.Round(time.Microsecond), sweepIdle.Round(time.Microsecond),
			stats.Round(time.Microsecond), list.Round(time.Microsecond),
			curve.Round(time.Microsecond), snapshot.Round(time.Microsecond),
			len(rows), total, len(pts), len(snap))
	}
}
