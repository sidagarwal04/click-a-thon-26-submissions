package fleet

import (
	"testing"
	"time"
)

func ttlSpec(n, ttlMinutes int) Spec {
	sp := spec(n)
	sp.TTLMinutes = ttlMinutes
	return sp
}

// A session past its TTL is ended by the sweep, cleanly, with a real event.
//
// This is what stops a fleet nobody is watching from writing into events_raw
// indefinitely — and it must be an END rather than a silent drop, or the pipeline
// would be left inferring abandonment from a lease it never saw expire.
func TestSweepEndsExpiredSessions(t *testing.T) {
	r := NewRegistry(lease, 41)
	views, _, err := r.Create(ttlSpec(3, 5), t0) // 5-minute TTL
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if !views[0].ExpiresAt.Equal(at(5 * time.Minute)) {
		t.Fatalf("expires at %s, want %s", views[0].ExpiresAt, at(5*time.Minute))
	}

	// Just before expiry: heartbeats, no ends.
	rows := r.Sweep(at(4 * time.Minute))
	for _, e := range rows {
		if e.Event == "VideoSessionEnd" {
			t.Fatal("ended before the TTL elapsed")
		}
	}

	// Past expiry: three ends, and nothing left alive.
	ends := 0
	for _, e := range r.Sweep(at(5*time.Minute + time.Second)) {
		if e.Event == "VideoSessionEnd" {
			ends++
		}
	}
	if ends != 3 {
		t.Fatalf("%d ends, want 3", ends)
	}
	if st := r.Stats(at(6 * time.Minute)); st.Ended != 3 || st.Active != 0 {
		t.Errorf("stats %+v, want 3 ended / 0 active", st)
	}
	// And it stays quiet afterwards.
	if rows := r.Sweep(at(7 * time.Minute)); len(rows) != 0 {
		t.Errorf("expired fleet still emitted %d rows", len(rows))
	}
}

func TestCreateRejectsOutOfRangeTTL(t *testing.T) {
	r := NewRegistry(lease, 43)
	if _, _, err := r.Create(ttlSpec(1, 100000), t0); err == nil {
		t.Error("want an error for a TTL past the maximum")
	}
	// Zero takes the default rather than meaning "never".
	views, _, err := r.Create(ttlSpec(1, 0), t0)
	if err != nil {
		t.Fatalf("create with default ttl: %v", err)
	}
	if !views[0].ExpiresAt.Equal(t0.Add(DefaultTTL)) {
		t.Errorf("expires at %s, want the default %s", views[0].ExpiresAt, DefaultTTL)
	}
}

// A snapshot carries only what changed, and clears the flag behind it.
func TestSnapshotIsIncremental(t *testing.T) {
	r := NewRegistry(lease, 47)
	views, _, err := r.Create(spec(4), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if n := len(r.snapshot()); n != 4 {
		t.Fatalf("first snapshot has %d rows, want 4", n)
	}
	if n := len(r.snapshot()); n != 0 {
		t.Fatalf("second snapshot has %d rows, want 0 — nothing changed", n)
	}

	cmd(t, r, views[1].ID, CmdPause, at(time.Second))
	rows := r.snapshot()
	if len(rows) != 1 || rows[0].ID != views[1].ID {
		t.Fatalf("snapshot after one pause = %d rows, want just the paused session", len(rows))
	}
	if rows[0].Playing {
		t.Error("snapshot did not carry the paused state")
	}
}

// Restore rebuilds state, and the intervals survive the round trip exactly.
func TestRestoreRoundTrip(t *testing.T) {
	src := NewRegistry(lease, 53)
	views, _, err := src.Create(spec(3), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cmd(t, src, views[0].ID, CmdPause, at(20*time.Second))
	cmd(t, src, views[1].ID, CmdBackground, at(30*time.Second))
	rows := src.snapshot()

	dst := NewRegistry(lease, 59)
	now := at(40 * time.Second)
	if events := dst.Restore(rows, now); len(events) != 0 {
		t.Fatalf("restore emitted %d events, want 0 — nothing had expired", len(events))
	}

	for _, want := range views {
		got, ok := dst.Get(want.ID, now)
		if !ok {
			t.Fatalf("session %s missing after restore", want.ID[:8])
		}
		before, _ := src.Get(want.ID, now)
		if got.Phase != before.Phase {
			t.Errorf("%s phase %s, want %s", want.ID[:8], got.Phase, before.Phase)
		}
		if len(got.Intervals) != len(before.Intervals) {
			t.Errorf("%s has %d intervals, want %d", want.ID[:8],
				len(got.Intervals), len(before.Intervals))
		}
		if got.ActiveMS != before.ActiveMS {
			t.Errorf("%s active_ms %d, want %d", want.ID[:8], got.ActiveMS, before.ActiveMS)
		}
	}
}

// The catch-up is the point of Restore: a session whose TTL elapsed while the
// process was down is ended AT its expiry, not at startup.
//
// Stamping the end at startup instead would credit the session with all the
// downtime, and the fleet's ground-truth line would disagree with ClickHouse for a
// reason that is purely an artifact of the restart.
func TestRestoreEndsSessionsThatExpiredWhileDown(t *testing.T) {
	src := NewRegistry(lease, 61)
	if _, _, err := src.Create(ttlSpec(2, 5), t0); err != nil {
		t.Fatalf("create: %v", err)
	}
	rows := src.snapshot()

	// Come back up an hour later.
	dst := NewRegistry(lease, 67)
	now := at(time.Hour)
	events := dst.Restore(rows, now)

	if len(events) != 2 {
		t.Fatalf("restore emitted %d events, want 2 session ends", len(events))
	}
	for _, e := range events {
		if e.Event != "VideoSessionEnd" {
			t.Errorf("emitted %q, want VideoSessionEnd", e.Event)
		}
		if !e.EventTimestamp.Equal(at(5 * time.Minute)) {
			t.Errorf("end stamped %s, want the expiry %s",
				e.EventTimestamp, at(5*time.Minute))
		}
	}
	if st := dst.Stats(now); st.Ended != 2 {
		t.Errorf("stats %+v, want 2 ended", st)
	}

	// The recorded activity stops at the lease, not at the TTL and not at startup:
	// heartbeats stopped when the process died, so the lease is what bounds it.
	v, _ := dst.Get(events[0].VideoSessionID, now)
	if len(v.Intervals) != 1 {
		t.Fatalf("got %d intervals, want 1: %+v", len(v.Intervals), v.Intervals)
	}
	if !v.Intervals[0].End.Equal(at(lease)) {
		t.Errorf("interval ends %s, want the lease expiry %s", v.Intervals[0].End, at(lease))
	}
}

// A restored session that needs no catch-up must not be marked dirty, or every
// restart would rewrite the whole table for nothing.
func TestRestoreDoesNotDirtyUnchangedSessions(t *testing.T) {
	src := NewRegistry(lease, 71)
	if _, _, err := src.Create(spec(3), t0); err != nil {
		t.Fatalf("create: %v", err)
	}
	rows := src.snapshot()

	dst := NewRegistry(lease, 73)
	dst.Restore(rows, at(10*time.Second)) // well inside both lease and TTL

	if n := len(dst.snapshot()); n != 0 {
		t.Errorf("%d sessions dirty after a no-op restore, want 0", n)
	}
}

// Restore is idempotent: replaying the same rows must not duplicate sessions.
func TestRestoreIgnoresDuplicates(t *testing.T) {
	src := NewRegistry(lease, 79)
	if _, _, err := src.Create(spec(2), t0); err != nil {
		t.Fatalf("create: %v", err)
	}
	rows := src.snapshot()

	dst := NewRegistry(lease, 83)
	dst.Restore(rows, at(time.Second))
	dst.Restore(rows, at(2*time.Second))

	if _, total := dst.List(Filter{}, 0, 50, at(3*time.Second)); total != 2 {
		t.Errorf("%d sessions after a double restore, want 2", total)
	}
}

// Tombstones are what stop a cleared session coming back on the next restart.
func TestRemovedRowsAreSkippedByRestore(t *testing.T) {
	r := NewRegistry(lease, 89)
	views, _, err := r.Create(spec(2), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cmd(t, r, views[0].ID, CmdEnd, at(time.Second))
	rows := r.snapshot()
	rows = append(rows, removedRows(r.RemoveEnded(), at(2*time.Second))...)

	dst := NewRegistry(lease, 97)
	dst.Restore(rows, at(3*time.Second))
	if _, total := dst.List(Filter{}, 0, 50, at(3*time.Second)); total != 1 {
		t.Errorf("%d sessions restored, want 1 — the cleared one must stay gone", total)
	}
}
