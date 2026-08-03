package fleet

import (
	"testing"
	"time"
)

const lease = 120 * time.Second

var t0 = time.Date(2026, 8, 2, 10, 0, 0, 0, time.UTC)

func spec(n int) Spec {
	return Spec{
		Count: n, ContentID: 4242, ContentTitle: "Test Match", VideoType: "LIVE",
		Platform: "ANDROID_PHONE", AppVersion: "6.34.8", Country: "india",
		CadenceSeconds: 30,
	}
}

// mkOne creates a single session and returns the registry and its id.
func mkOne(t *testing.T) (*Registry, string) {
	t.Helper()
	r := NewRegistry(lease, 1)
	views, rows, err := r.Create(spec(1), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("create emitted %d rows, want 2 (start + play)", len(rows))
	}
	return r, views[0].ID
}

func at(d time.Duration) time.Time { return t0.Add(d) }

func mustGet(t *testing.T, r *Registry, id string, now time.Time) *View {
	t.Helper()
	v, ok := r.Get(id, now)
	if !ok {
		t.Fatalf("session %s missing", id)
	}
	return v
}

func cmd(t *testing.T, r *Registry, id string, c Command, now time.Time) *View {
	t.Helper()
	v, _, err := r.Command(id, c, now)
	if err != nil {
		t.Fatalf("command %s: %v", c, err)
	}
	return v
}

// A session is active from the instant it is created: start and play land on the
// same millisecond and neither is a stop, so precedence never engages.
func TestCreateIsActiveImmediately(t *testing.T) {
	r, id := mkOne(t)
	v := mustGet(t, r, id, t0)

	if !v.Active || v.Phase != PhaseActive {
		t.Fatalf("active=%v phase=%s, want active", v.Active, v.Phase)
	}
	if !v.LeaseExpires.Equal(at(lease)) {
		t.Errorf("lease expires %s, want %s", v.LeaseExpires, at(lease))
	}
}

// Pause closes the interval at the pause instant, not at some later observation.
func TestPauseClosesIntervalAtEventTime(t *testing.T) {
	r, id := mkOne(t)
	v := cmd(t, r, id, CmdPause, at(10*time.Second))

	if v.Active || v.Phase != PhasePaused {
		t.Fatalf("active=%v phase=%s, want paused", v.Active, v.Phase)
	}
	if len(v.Intervals) != 1 {
		t.Fatalf("got %d intervals, want 1: %+v", len(v.Intervals), v.Intervals)
	}
	if !v.Intervals[0].Start.Equal(t0) || !v.Intervals[0].End.Equal(at(10*time.Second)) {
		t.Errorf("interval %v, want [t0, t0+10s)", v.Intervals[0])
	}
}

// A heartbeat sent while paused must NOT extend the lease. The client still sends
// it and the pipeline still ignores it, so the fleet has to ignore it too —
// otherwise a session paused past the lease would stay leased forever.
func TestHeartbeatWhilePausedDoesNotExtendLease(t *testing.T) {
	r, id := mkOne(t)
	cmd(t, r, id, CmdPause, at(10*time.Second))

	if rows := r.Sweep(at(40 * time.Second)); len(rows) != 1 {
		t.Fatalf("sweep emitted %d rows, want 1 heartbeat", len(rows))
	}
	v := mustGet(t, r, id, at(40*time.Second))
	if !v.LeaseExpires.Equal(at(lease)) {
		t.Errorf("lease expires %s, want %s (unchanged by a paused heartbeat)",
			v.LeaseExpires, at(lease))
	}
}

// Foregrounding a session whose lease already expired does NOT revive it. This is
// the behaviour people least expect, and it is real: AppForegrounded is a
// visibility setter, not a liveness signal, so nothing extends the lease until the
// next heartbeat arrives.
func TestForegroundAloneDoesNotReviveAnExpiredLease(t *testing.T) {
	r, id := mkOne(t)
	cmd(t, r, id, CmdBackground, at(10*time.Second))

	v := cmd(t, r, id, CmdForeground, at(200*time.Second))
	if v.Active {
		t.Fatalf("active after foreground at +200s; lease expired at +120s")
	}
	if v.Phase != PhaseExpired {
		t.Errorf("phase %s, want %s", v.Phase, PhaseExpired)
	}
	if !v.Foreground || !v.Playing {
		t.Errorf("foreground=%v playing=%v, both want true", v.Foreground, v.Playing)
	}

	// The next heartbeat is eligible, so it revives the session.
	if rows := r.Sweep(at(201 * time.Second)); len(rows) != 1 {
		t.Fatalf("sweep emitted %d rows, want 1 heartbeat", len(rows))
	}
	if v := mustGet(t, r, id, at(201*time.Second)); !v.Active {
		t.Fatalf("still inactive after an eligible heartbeat at +201s")
	}
}

// Resume, unlike foreground, IS a liveness signal, so it revives the session on
// its own even after the lease has run out.
func TestResumeRevivesAnExpiredLease(t *testing.T) {
	r, id := mkOne(t)
	cmd(t, r, id, CmdPause, at(10*time.Second))

	v := cmd(t, r, id, CmdResume, at(300*time.Second))
	if !v.Active {
		t.Fatalf("resume at +300s did not revive; lease expires %s", v.LeaseExpires)
	}
	if !v.LeaseExpires.Equal(at(300*time.Second + lease)) {
		t.Errorf("lease expires %s, want %s", v.LeaseExpires, at(300*time.Second+lease))
	}
}

// Silencing writes nothing, so the interval must end at the lease expiry — NOT at
// the sweep that happens to notice. Getting this wrong credits the session with up
// to a full sweep interval of activity it never had, and breaks conservation.
func TestSilenceEndsIntervalAtLeaseExpiryNotAtObservation(t *testing.T) {
	r, id := mkOne(t)

	v, rows, err := r.Command(id, CmdSilence, at(10*time.Second))
	if err != nil {
		t.Fatalf("silence: %v", err)
	}
	if len(rows) != 0 {
		t.Fatalf("silence wrote %d events, want 0 — the pipeline must not be told", len(rows))
	}
	if !v.Active {
		t.Fatalf("silence should not end activity immediately; the lease still holds")
	}

	// Sweep long after expiry. No heartbeat is due, and the interval must close at
	// +120s.
	if rows := r.Sweep(at(300 * time.Second)); len(rows) != 0 {
		t.Fatalf("silenced session emitted %d rows, want 0", len(rows))
	}
	v = mustGet(t, r, id, at(300*time.Second))
	if v.Phase != PhaseExpired {
		t.Errorf("phase %s, want %s", v.Phase, PhaseExpired)
	}
	if len(v.Intervals) != 1 {
		t.Fatalf("got %d intervals, want 1: %+v", len(v.Intervals), v.Intervals)
	}
	if !v.Intervals[0].End.Equal(at(lease)) {
		t.Errorf("interval ends %s, want %s (lease expiry, not sweep time)",
			v.Intervals[0].End, at(lease))
	}
}

// Ending writes a session_end and refuses further commands.
func TestEndClosesAndLocks(t *testing.T) {
	r, id := mkOne(t)
	v, rows, err := r.Command(id, CmdEnd, at(60*time.Second))
	if err != nil {
		t.Fatalf("end: %v", err)
	}
	if len(rows) != 1 {
		t.Fatalf("end wrote %d rows, want 1", len(rows))
	}
	if v.Phase != PhaseEnded || v.Active {
		t.Fatalf("phase=%s active=%v, want ended", v.Phase, v.Active)
	}
	if len(v.Intervals) != 1 || !v.Intervals[0].End.Equal(at(60*time.Second)) {
		t.Errorf("intervals %+v, want one ending at +60s", v.Intervals)
	}
	if _, _, err := r.Command(id, CmdPause, at(70*time.Second)); err == nil {
		t.Error("pause after end succeeded, want an error")
	}
	// A sweep must not resurrect it with a heartbeat.
	if rows := r.Sweep(at(90 * time.Second)); len(rows) != 0 {
		t.Errorf("ended session emitted %d rows on sweep, want 0", len(rows))
	}
}

// The conservation identity: the curve's summed active milliseconds must equal the
// summed interval durations. This is a total function over the fold, so it catches
// a bucketing or clipping error that a spot-check on one session would miss.
func TestCurveConservesActiveMilliseconds(t *testing.T) {
	r := NewRegistry(lease, 7)
	views, _, err := r.Create(spec(5), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	// Drive the fleet into a mixed state, deliberately crossing minute boundaries.
	r.Sweep(at(25 * time.Second))
	cmd(t, r, views[0].ID, CmdPause, at(70*time.Second))
	cmd(t, r, views[1].ID, CmdBackground, at(95*time.Second))
	cmd(t, r, views[2].ID, CmdSilence, at(30*time.Second))
	cmd(t, r, views[3].ID, CmdEnd, at(150*time.Second))
	r.Sweep(at(160 * time.Second))
	now := at(400 * time.Second)
	r.Sweep(now)

	var fromIntervals int64
	all, _ := r.List(Filter{}, 0, 500, now)
	for _, v := range all {
		for _, iv := range v.Intervals {
			fromIntervals += iv.End.Sub(iv.Start).Milliseconds()
		}
	}

	var fromCurve int64
	for _, p := range r.Curve(Filter{}, t0.Add(-time.Minute), now.Add(time.Minute), now) {
		fromCurve += p.ActiveMS
	}

	if fromIntervals != fromCurve {
		t.Fatalf("conservation broken: intervals %d ms, curve %d ms (delta %d)",
			fromIntervals, fromCurve, fromCurve-fromIntervals)
	}
	if fromIntervals == 0 {
		t.Fatal("no active time recorded; the test drove nothing")
	}
}

// The curve counts a session once per minute it touches, and emits empty minutes
// rather than leaving gaps for a chart to interpolate across.
func TestCurveShapeAndDenseMinutes(t *testing.T) {
	r := NewRegistry(lease, 3)
	views, _, err := r.Create(spec(2), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cmd(t, r, views[0].ID, CmdPause, at(30*time.Second))

	// No sweeps, so the surviving session's lease runs out at exactly +120s — which
	// makes minute 2 empty and proves the curve emits it rather than skipping it.
	now := at(150 * time.Second)
	pts := r.Curve(Filter{}, t0, now, now)
	if len(pts) != 3 {
		t.Fatalf("got %d points, want 3 dense minutes", len(pts))
	}
	// Minute 0: both sessions active for part of it.
	if pts[0].Sessions != 2 {
		t.Errorf("minute 0 sessions %d, want 2", pts[0].Sessions)
	}
	// Minute 1: only the un-paused one.
	if pts[1].Sessions != 1 {
		t.Errorf("minute 1 sessions %d, want 1", pts[1].Sessions)
	}
	// Minute 2: the lease expired on its boundary, so this minute is genuinely
	// empty and must still be present.
	if pts[2].Sessions != 0 || pts[2].ActiveMS != 0 {
		t.Errorf("minute 2 = %+v, want an empty but present point", pts[2])
	}
	// Average concurrency can never exceed the any-overlap count.
	for i, p := range pts {
		if avg := float64(p.ActiveMS) / 60000; avg > float64(p.Sessions)+1e-9 {
			t.Errorf("point %d: average %.3f exceeds count %d", i, avg, p.Sessions)
		}
	}
}

// A session with several active islands inside one minute must count ONCE.
//
// Found in production rather than by this test: a 20-session fleet reported 21 for
// the minute in which one session was paused and resumed, because both the Go fold
// and the SQL counted island-minutes instead of distinct sessions. The comparison
// graph could not catch it — both sides shared the error, so they agreed exactly.
func TestCurveCountsSessionsNotIslands(t *testing.T) {
	r := NewRegistry(lease, 13)
	views, _, err := r.Create(spec(1), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	id := views[0].ID

	// Pause and resume inside the first minute: two islands, one minute.
	cmd(t, r, id, CmdPause, at(10*time.Second))
	cmd(t, r, id, CmdResume, at(20*time.Second))
	cmd(t, r, id, CmdPause, at(30*time.Second))

	now := at(45 * time.Second)
	v := mustGet(t, r, id, now)
	if len(v.Intervals) != 2 {
		t.Fatalf("got %d intervals, want 2 in one minute: %+v", len(v.Intervals), v.Intervals)
	}

	pts := r.Curve(Filter{}, t0, now, now)
	if len(pts) != 1 {
		t.Fatalf("got %d points, want 1", len(pts))
	}
	if pts[0].Sessions != 1 {
		t.Errorf("minute 0 counted %d sessions, want 1 — islands are being counted",
			pts[0].Sessions)
	}
	// Milliseconds still accumulate across both islands: 0–10s plus 20–30s.
	if want := int64(20_000); pts[0].ActiveMS != want {
		t.Errorf("active_ms %d, want %d (both islands)", pts[0].ActiveMS, want)
	}
}

func TestFilterNarrowsListAndCurve(t *testing.T) {
	r := NewRegistry(lease, 11)
	a := spec(3)
	a.Platform = "ANDROID_PHONE"
	if _, _, err := r.Create(a, t0); err != nil {
		t.Fatalf("create a: %v", err)
	}
	b := spec(2)
	b.Platform = "FIRETV"
	b.ContentID = 999
	if _, _, err := r.Create(b, t0); err != nil {
		t.Fatalf("create b: %v", err)
	}

	if _, total := r.List(Filter{Platform: "FIRETV"}, 0, 50, t0); total != 2 {
		t.Errorf("FIRETV total %d, want 2", total)
	}
	if _, total := r.List(Filter{ContentID: 4242}, 0, 50, t0); total != 3 {
		t.Errorf("content 4242 total %d, want 3", total)
	}
	pts := r.Curve(Filter{Platform: "FIRETV"}, t0, t0, t0.Add(time.Second))
	if len(pts) == 0 || pts[0].Sessions != 2 {
		t.Errorf("filtered curve first point %+v, want 2 sessions", pts)
	}
	if got := r.Dimensions()["platform"]; len(got) != 2 {
		t.Errorf("dimensions platform %v, want 2 distinct", got)
	}
}

// Bulk over a filter must touch exactly the matching sessions and nothing else.
func TestCommandMatchingRespectsTheFilter(t *testing.T) {
	r := NewRegistry(lease, 21)
	a := spec(4)
	a.Platform = "ANDROID_PHONE"
	if _, _, err := r.Create(a, t0); err != nil {
		t.Fatalf("create a: %v", err)
	}
	b := spec(3)
	b.Platform = "FIRETV"
	if _, _, err := r.Create(b, t0); err != nil {
		t.Fatalf("create b: %v", err)
	}

	res, rows, err := r.CommandMatching(Filter{Platform: "FIRETV"}, CmdPause, at(time.Second))
	if err != nil {
		t.Fatalf("bulk pause: %v", err)
	}
	if res.Applied != 3 || res.Skipped != 0 {
		t.Fatalf("result %+v, want 3 applied / 0 skipped", res)
	}
	if len(rows) != 3 {
		t.Fatalf("wrote %d rows, want 3", len(rows))
	}

	now := at(2 * time.Second)
	if _, total := r.List(Filter{Phase: "paused"}, 0, 50, now); total != 3 {
		t.Errorf("%d paused, want 3", total)
	}
	if _, total := r.List(Filter{Phase: "active"}, 0, 50, now); total != 4 {
		t.Errorf("%d still active, want the 4 ANDROID_PHONE sessions", total)
	}
}

// A no-op must be skipped, not written. Pausing 500 sessions of which 400 are
// already paused should write 100 events — otherwise a bulk button becomes a way
// to flood events_raw with events that change nothing.
func TestBulkSkipsNoOpsAndEndedSessions(t *testing.T) {
	r := NewRegistry(lease, 23)
	views, _, err := r.Create(spec(5), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cmd(t, r, views[0].ID, CmdPause, at(time.Second)) // already paused
	cmd(t, r, views[1].ID, CmdEnd, at(time.Second))   // ended

	res, rows, err := r.CommandMatching(Filter{}, CmdPause, at(2*time.Second))
	if err != nil {
		t.Fatalf("bulk pause: %v", err)
	}
	// 3 still playing get paused; 1 already paused and 1 ended are skipped.
	if res.Applied != 3 || res.Skipped != 2 {
		t.Fatalf("result %+v, want 3 applied / 2 skipped", res)
	}
	if len(rows) != 3 {
		t.Errorf("wrote %d rows, want 3 — no-ops must not be written", len(rows))
	}

	// The ended session stays ended.
	if v := mustGet(t, r, views[1].ID, at(3*time.Second)); v.Phase != PhaseEnded {
		t.Errorf("ended session became %s", v.Phase)
	}
}

// Bulk over an explicit id list touches only those ids, and reports ids it no
// longer knows rather than failing the batch.
func TestCommandManyByID(t *testing.T) {
	r := NewRegistry(lease, 27)
	views, _, err := r.Create(spec(4), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	ids := []string{views[0].ID, views[2].ID, "NOT-A-SESSION"}

	res, rows, err := r.CommandMany(ids, CmdPause, at(time.Second))
	if err != nil {
		t.Fatalf("bulk: %v", err)
	}
	if res.Applied != 2 || res.Unknown != 1 {
		t.Fatalf("result %+v, want 2 applied / 1 unknown", res)
	}
	if len(rows) != 2 {
		t.Errorf("wrote %d rows, want 2", len(rows))
	}
	if _, total := r.List(Filter{Phase: "paused"}, 0, 50, at(2*time.Second)); total != 2 {
		t.Errorf("%d paused, want 2", total)
	}
}

// Silence in bulk still writes nothing — the property that makes it the
// app-killed case has to survive the bulk path.
func TestBulkSilenceWritesNothing(t *testing.T) {
	r := NewRegistry(lease, 29)
	if _, _, err := r.Create(spec(6), t0); err != nil {
		t.Fatalf("create: %v", err)
	}
	res, rows, err := r.CommandMatching(Filter{}, CmdSilence, at(time.Second))
	if err != nil {
		t.Fatalf("bulk silence: %v", err)
	}
	if res.Applied != 6 {
		t.Fatalf("applied %d, want 6", res.Applied)
	}
	if len(rows) != 0 {
		t.Fatalf("wrote %d events, want 0", len(rows))
	}
	// Every lease runs out and no heartbeat renews it.
	if st := r.Stats(at(200 * time.Second)); st.Expired != 6 {
		t.Errorf("expired %d, want 6 (stats %+v)", st.Expired, st)
	}
}

func TestBulkRejectsUnknownCommand(t *testing.T) {
	r := NewRegistry(lease, 31)
	if _, _, err := r.Create(spec(2), t0); err != nil {
		t.Fatalf("create: %v", err)
	}
	if _, _, err := r.CommandMatching(Filter{}, Command("obliterate"), t0); err == nil {
		t.Error("want an error for an unknown command")
	}
}

func TestListPagination(t *testing.T) {
	r := NewRegistry(lease, 5)
	if _, _, err := r.Create(spec(120), t0); err != nil {
		t.Fatalf("create: %v", err)
	}
	page, total := r.List(Filter{}, 100, 50, t0)
	if total != 120 {
		t.Errorf("total %d, want 120", total)
	}
	if len(page) != 20 {
		t.Errorf("last page %d rows, want 20", len(page))
	}
	if empty, _ := r.List(Filter{}, 500, 50, t0); len(empty) != 0 {
		t.Errorf("past-the-end page returned %d rows", len(empty))
	}
}

func TestCreateValidation(t *testing.T) {
	r := NewRegistry(lease, 1)
	for _, tc := range []struct {
		name string
		mut  func(*Spec)
	}{
		{"zero count", func(s *Spec) { s.Count = 0 }},
		{"over limit", func(s *Spec) { s.Count = MaxPerCreate + 1 }},
		{"no content", func(s *Spec) { s.ContentID = 0 }},
		{"cadence too low", func(s *Spec) { s.CadenceSeconds = 1 }},
		{"cadence too high", func(s *Spec) { s.CadenceSeconds = 100000 }},
	} {
		t.Run(tc.name, func(t *testing.T) {
			sp := spec(1)
			tc.mut(&sp)
			if _, _, err := r.Create(sp, t0); err == nil {
				t.Error("want an error")
			}
		})
	}
}

func TestRemoveEndedReclaimsCapacity(t *testing.T) {
	r := NewRegistry(lease, 1)
	views, _, err := r.Create(spec(3), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	cmd(t, r, views[0].ID, CmdEnd, at(time.Second))

	if got := r.RemoveEnded(); len(got) != 1 {
		t.Fatalf("removed %v, want 1 id", got)
	}
	if _, total := r.List(Filter{}, 0, 50, at(time.Second)); total != 2 {
		t.Errorf("total after removal %d, want 2", total)
	}
	if st := r.Stats(at(time.Second)); st.Total != 2 || st.Active != 2 {
		t.Errorf("stats %+v, want 2 total / 2 active", st)
	}
}

// Heartbeat ticks must be staggered across the cadence, or every session fires on
// the same instant and the insert rate becomes a sawtooth the workload never had.
func TestFirstTicksAreStaggered(t *testing.T) {
	r := NewRegistry(lease, 99)
	views, _, err := r.Create(spec(200), t0)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	seen := make(map[time.Time]int)
	for _, v := range views {
		if v.NextTick.Before(t0) || !v.NextTick.Before(at(30*time.Second)) {
			t.Fatalf("next tick %s outside [t0, t0+30s)", v.NextTick)
		}
		seen[v.NextTick.Truncate(time.Second)]++
	}
	// 200 sessions over a 30s cadence should touch most seconds; anything under a
	// third means they are effectively synchronised.
	if len(seen) < 10 {
		t.Errorf("first ticks landed in only %d distinct seconds, want spread", len(seen))
	}
}
