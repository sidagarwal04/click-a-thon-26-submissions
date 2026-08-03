package generator

import (
	"container/heap"
	"math"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// action is a scheduled step in a session's lifecycle.
type action uint8

const (
	actSpawn action = iota // periodic tick that opens new sessions
	actStart
	actPlay
	actHeartbeat
	actBackground
	actForeground
	actPause
	actResume
	actError
	actEnd
)

// spawnTick is the event-time interval between concurrency-control ticks.
const spawnTick = 200 * time.Millisecond

// session is one player lifecycle.
type session struct {
	id     string
	userID string

	contentID int64
	platform  string
	appVer    string
	audioLang string
	subLang   string
	playerVer string
	videoRes  string

	startTime time.Time
	endTime   time.Time // planned

	emitsTrio    bool
	foreground   bool
	playing      bool
	ended        bool
	backgrounded bool

	// fgScheduled is true while a return-to-foreground is pending. endPending
	// records that the session's End came due while the user was away; see
	// runEnd for why it is held rather than emitted.
	fgScheduled bool
	endPending  bool
}

// task is a scheduled action.
type task struct {
	when time.Time
	seq  uint64 // insertion order; makes ties deterministic
	act  action
	s    *session
}

type taskHeap []task

func (h taskHeap) Len() int { return len(h) }
func (h taskHeap) Less(i, j int) bool {
	if h[i].when.Equal(h[j].when) {
		return h[i].seq < h[j].seq
	}
	return h[i].when.Before(h[j].when)
}
func (h taskHeap) Swap(i, j int) { h[i], h[j] = h[j], h[i] }
func (h *taskHeap) Push(x any)   { *h = append(*h, x.(task)) }
func (h *taskHeap) Pop() any     { old := *h; n := len(old); x := old[n-1]; *h = old[:n-1]; return x }

// pendingEvent is an emitted event waiting for its arrival time.
//
// Separating event time from arrival time is the whole point: an event that
// happened at 10:05 may reach the pipeline at 10:07, after events that happened
// later. 99.65% of sessions in the source contain at least one such row, so a
// generator that emitted in perfect time order would validate nothing.
type pendingEvent struct {
	arrival time.Time
	seq     uint64
	ev      model.RawEvent
}

type pendingHeap []pendingEvent

func (h pendingHeap) Len() int { return len(h) }
func (h pendingHeap) Less(i, j int) bool {
	if h[i].arrival.Equal(h[j].arrival) {
		return h[i].seq < h[j].seq
	}
	return h[i].arrival.Before(h[j].arrival)
}
func (h pendingHeap) Swap(i, j int) { h[i], h[j] = h[j], h[i] }
func (h *pendingHeap) Push(x any)   { *h = append(*h, x.(pendingEvent)) }
func (h *pendingHeap) Pop() any     { old := *h; n := len(old); x := old[n-1]; *h = old[:n-1]; return x }

// schedule queues an action.
func (g *Generator) schedule(when time.Time, act action, s *session) {
	g.seq++
	heap.Push(&g.tasks, task{when: when, seq: g.seq, act: act, s: s})
}

// runTask advances one session (or the spawner) by one step.
func (g *Generator) runTask(t task) {
	switch t.act {
	case actSpawn:
		g.runSpawn()
	case actStart:
		g.runStart(t.s)
	case actPlay:
		g.runPlay(t.s)
	case actHeartbeat:
		g.runHeartbeat(t.s)
	case actBackground:
		g.runBackground(t.s)
	case actForeground:
		g.runForeground(t.s)
	case actPause:
		g.runPause(t.s)
	case actResume:
		g.runResume(t.s)
	case actError:
		g.runError(t.s)
	case actEnd:
		g.runEnd(t.s)
	}
}

// runSpawn is the closed-loop concurrency controller.
//
// Concurrency, not event count, is the dial this workload is described in
// ("if minute 1 has 300K concurrent sessions..."). Each tick nudges the active
// count a fixed fraction of the way toward target, which converges quickly
// without the thundering herd a "spawn the whole deficit now" rule produces.
func (g *Generator) runSpawn() {
	if g.now.After(g.cutoff) {
		return // stop opening sessions past the cutoff; existing ones continue
	}

	want := float64(g.cfg.TargetConcurrency)
	if g.cfg.RampUp > 0 {
		elapsed := g.now.Sub(g.cfg.StartTime)
		if elapsed < g.cfg.RampUp {
			want *= float64(elapsed) / float64(g.cfg.RampUp)
		}
	}

	deficit := want - float64(g.active)
	if deficit > 0 {
		// 5% of the deficit per tick: ~60 ticks (12 event-seconds) to converge,
		// and in steady state this exactly replaces churn.
		n := int(math.Ceil(deficit * 0.05))
		n = min(n, 500)
		for range n {
			g.spawnSession()
		}
	}

	g.schedule(g.now.Add(spawnTick), actSpawn, nil)
}

// spawnSession creates a session and schedules its whole lifecycle skeleton.
func (g *Generator) spawnSession() {
	profile := platformDist.pick(g.rnd)
	content := g.content[g.rnd.IntN(len(g.content))]

	userID := g.users[g.rnd.IntN(len(g.users))]
	if g.cfg.BotSessionShare > 0 && g.rnd.Float64() < g.cfg.BotSessionShare {
		userID = g.botUser
	}

	s := &session{
		id:         g.hexID(),
		userID:     userID,
		contentID:  content.ContentID,
		platform:   profile.Name,
		appVer:     appVersionDist.pick(g.rnd),
		audioLang:  audioLanguageDist.pick(g.rnd),
		subLang:    subtitleLanguageDist.pick(g.rnd),
		playerVer:  playerVersionDist.pick(g.rnd),
		videoRes:   videoResolutionDist.pick(g.rnd),
		startTime:  g.now,
		emitsTrio:  g.rnd.Float64() < profile.TrioProbability,
		foreground: true,
	}
	s.endTime = s.startTime.Add(g.lognormalDuration())

	g.active++
	g.peakActive = max(g.peakActive, g.active)
	g.summary.Sessions++

	g.schedule(s.startTime, actStart, s)
}

func (g *Generator) runStart(s *session) {
	// VideoSessionStart fires before the player knows its track metadata, so
	// language and player-version columns carry placeholders here and real
	// values later. This inconsistency is in the source and is exactly what the
	// server-side normalization exists to absorb.
	ev := g.newEvent(s, "VideoSessionStart", "VideoSessionStart", g.now)
	ev.AudioLanguage = startAudioPlaceholder(g.rnd)
	ev.SubtitleLanguage = startSubtitlePlaceholder(g.rnd)
	ev.PlayerVersion = startPlayerVersion(g.rnd, s.playerVer)
	g.emit(ev)

	// Play follows the start by a short, right-skewed delay (p50 ~1.7s).
	playAt := g.now.Add(g.expDuration(2*time.Second) + 300*time.Millisecond)
	g.schedule(playAt, actPlay, s)

	// Terminal end. Left scheduled even for sessions that will be cut off by
	// the run boundary; if the cutoff arrives first the session stays open.
	g.schedule(s.endTime, actEnd, s)

	// Episodes are spread over the session from the moment playback starts,
	// not from the session start. The pre-play gap is not a window anything
	// can happen in: a background episode drawn into it would put the session
	// away before it ever played and then VideoPlay would fire on a
	// backgrounded session, and a pause drawn into it is silently discarded by
	// runPause, quietly thinning the pause rate.
	for range g.poisson(g.cfg.BackgroundEpisodes) {
		g.schedule(g.uniformWithin(playAt, s.endTime), actBackground, s)
	}
	for range g.poisson(g.cfg.PauseEpisodes) {
		g.schedule(g.uniformWithin(playAt, s.endTime), actPause, s)
	}
	// VideoError never terminates a session in the source — it is a quality
	// signal only, and 100% of the 293 errors are followed by further events.
	if g.rnd.Float64() < g.cfg.ErrorProbability {
		g.schedule(g.uniformWithin(playAt, s.endTime), actError, s)
	}
}

// runPlay starts playback. It cannot be reached on a backgrounded session:
// runStart is the only source of actBackground and schedules it strictly after
// playAt.
func (g *Generator) runPlay(s *session) {
	if s.ended {
		return
	}
	s.playing = true
	g.emit(g.newEvent(s, "VideoPlay", "Play", g.now))
	g.schedule(g.now.Add(g.jitter(g.cfg.HeartbeatInterval, 0.02)), actHeartbeat, s)
}

// runHeartbeat emits the periodic ping and reschedules itself.
//
// Three behaviours from the source are reproduced here, because each one breaks
// a different naive liveness rule:
//
//   - Backgrounded: heartbeats stop entirely. Only 17.7% of background windows
//     contain any event at all, and 78.5% of windows over 120s contain none.
//     A liveness rule that waits out a timeout before deactivating would credit
//     up to two minutes of phantom viewing per background episode.
//   - Foreground pause: the ping continues at roughly 39% of nominal rate.
//     Pause is therefore NOT detectable from silence — it must be read from the
//     explicit 'pause' event.
//   - No trio: sessions on clients that do not emit the bundle still emit other
//     telemetry, so liveness must accept any event name.
func (g *Generator) runHeartbeat(s *session) {
	if s.ended {
		return
	}

	next := g.jitter(g.cfg.HeartbeatInterval, 0.02)

	switch {
	case s.backgrounded:
		// Silent. Keep the timer alive so the ping resumes on foreground.

	case !s.playing:
		// Paused but foregrounded: reduced-rate pings.
		if g.rnd.Float64() < 0.39 {
			g.emitPing(s)
		}

	default:
		g.emitPing(s)
		// Bursty non-periodic telemetry between the ticks.
		if g.rnd.Float64() < 0.35 {
			at := g.now.Add(time.Duration(g.rnd.Float64() * float64(next)))
			g.emit(g.newEvent(s, "VideoHeartbeat", telemetryDist.pick(g.rnd), at))
		}
	}

	g.schedule(g.now.Add(next), actHeartbeat, s)
}

// emitPing sends either the three-event bundle at one identical millisecond, or
// a single telemetry event for clients that do not emit the bundle.
func (g *Generator) emitPing(s *session) {
	if !s.emitsTrio {
		g.emit(g.newEvent(s, "VideoHeartbeat", telemetryDist.pick(g.rnd), g.now))
		return
	}
	for _, name := range trioEvents {
		g.emit(g.newEvent(s, "VideoHeartbeat", name, g.now))
	}
}

func (g *Generator) runBackground(s *session) {
	if s.ended || s.backgrounded {
		return
	}
	s.backgrounded = true
	s.foreground = false
	g.emit(g.newEvent(s, "AppBackgrounded", "AppBackgrounded", g.now))

	// The pause burst observed within ~5s of the background edge.
	if g.rnd.Float64() < 0.45 {
		at := g.now.Add(time.Duration(g.rnd.Float64() * float64(3*time.Second)))
		g.emit(g.newEvent(s, "VideoHeartbeat", "pause", at))
		s.playing = false
	}

	window := g.backgroundWindow()

	// ~2.6% of background windows never close — the session ends while
	// backgrounded. Those sessions must not be counted as active in the gap.
	if g.rnd.Float64() < 0.026 {
		return
	}
	s.fgScheduled = true
	g.schedule(g.now.Add(window), actForeground, s)
}

func (g *Generator) runForeground(s *session) {
	if s.ended || !s.backgrounded {
		return
	}
	s.backgrounded = false
	s.fgScheduled = false
	s.foreground = true
	g.emit(g.newEvent(s, "AppForegrounded", "AppForegrounded", g.now))

	// The session's planned End came due while the user was away. Close it
	// shortly after they return, which is what the source shows.
	if s.endPending {
		s.endPending = false
		g.schedule(g.now.Add(g.expDuration(30*time.Second)+time.Second), actEnd, s)
		return
	}

	// Foregrounding does not itself resume playback: only 2.2% of foreground
	// events are followed by a VideoPlay. Resume arrives as a heartbeat.
	if !s.playing && g.rnd.Float64() < 0.6 {
		at := g.now.Add(time.Duration(g.rnd.Float64() * float64(2*time.Second)))
		g.emit(g.newEvent(s, "VideoHeartbeat", "resume", at))
		s.playing = true
	}
}

func (g *Generator) runPause(s *session) {
	if s.ended || s.backgrounded || !s.playing {
		return
	}
	s.playing = false
	g.emit(g.newEvent(s, "VideoHeartbeat", "pause", g.now))

	g.schedule(g.now.Add(g.pauseWindow()), actResume, s)
}

func (g *Generator) runResume(s *session) {
	if s.ended || s.playing {
		return
	}
	// Resume also fires on buffer recovery, which is why the source has 4,440
	// more resumes than pauses. Emitting it unconditionally reproduces that.
	s.playing = true
	g.emit(g.newEvent(s, "VideoHeartbeat", "resume", g.now))
}

func (g *Generator) runError(s *session) {
	if s.ended {
		return
	}
	g.emit(g.newEvent(s, "VideoError", "VideoError", g.now))
}

func (g *Generator) runEnd(s *session) {
	if s.ended {
		return
	}

	// A session does not close in the middle of a background window unless it
	// is one of the few that genuinely die there (those have no pending return
	// to foreground, so they fall through and end here).
	//
	// Without this, a background window longer than the session's remaining
	// time would be silently truncated by the End event — which biased the
	// generated background distribution to a 21s median against the measured
	// 35s, and cut its p90 to a third. Background duration is the single input
	// the whole foreground-only problem turns on, so getting its tail wrong
	// would make the generated stream easier than reality.
	if s.backgrounded && s.fgScheduled {
		s.endPending = true
		return
	}

	s.ended = true
	g.active--
	g.emit(g.newEvent(s, "VideoSessionEnd", "VideoSessionEnd", g.now))

	// 2.2% of sessions trail events after their End, dominated by exit-to-
	// background telemetry. VideoSessionEnd is not a hard terminator in the
	// source, and a pipeline that assumes it is will mis-handle those rows.
	if g.rnd.Float64() < 0.022 {
		at := g.now.Add(time.Duration(g.rnd.Float64() * float64(30*time.Second)))
		g.emit(g.newEvent(s, "AppBackgrounded", "AppBackgrounded", at))
	}
}

// newEvent builds an event with the session's steady-state dimensions.
func (g *Generator) newEvent(s *session, eventType, event string, at time.Time) model.RawEvent {
	return model.RawEvent{
		VideoSessionID:    s.id,
		UserID:            s.userID,
		ContentID:         s.contentID,
		EventType:         eventType,
		Event:             event,
		EventTimestamp:    at,
		SessionStartEpoch: s.startTime,
		Platform:          s.platform,
		AppVersion:        s.appVer,
		Country:           "india",
		AudioLanguage:     s.audioLang,
		SubtitleLanguage:  s.subLang,
		PlayerVersion:     s.playerVer,
		VideoResolution:   s.videoRes,
	}
}

// emit queues an event for delivery, applying lateness and duplication.
func (g *Generator) emit(ev model.RawEvent) {

	arrival := ev.EventTimestamp
	if g.cfg.LateFraction > 0 && g.rnd.Float64() < g.cfg.LateFraction {
		// Right-skewed delay: most late events are seconds late, a few are
		// minutes late, matching the observed within-session lateness profile.
		delay := g.expDuration(g.cfg.LateMax / 4)
		if delay > g.cfg.LateMax {
			delay = g.cfg.LateMax
		}
		arrival = arrival.Add(delay)
		g.summary.LateEvents++
	}

	g.push(arrival, ev)

	// Exact duplicates: same payload, same fingerprint, delivered twice. The
	// source has 4,210 of these (0.465%), so the pipeline must be able to
	// identify them rather than double-count a session start.
	if g.cfg.DuplicateFraction > 0 && g.rnd.Float64() < g.cfg.DuplicateFraction {
		dupArrival := arrival.Add(time.Duration(g.rnd.Float64() * float64(500*time.Millisecond)))
		g.push(dupArrival, ev)
		g.summary.Duplicates++
	}
}

func (g *Generator) push(arrival time.Time, ev model.RawEvent) {
	g.seq++
	heap.Push(&g.pending, pendingEvent{arrival: arrival, seq: g.seq, ev: ev})
}

// poisson draws a count with the given mean, used for per-session episode
// counts.
func (g *Generator) poisson(mean float64) int {
	if mean <= 0 {
		return 0
	}
	// Knuth's method; means here are small (1-3) so the loop is short.
	l := math.Exp(-mean)
	k, p := 0, 1.0
	for {
		p *= g.rnd.Float64()
		if p <= l {
			return k
		}
		k++
		if k > 64 {
			return k
		}
	}
}

// uniformWithin picks a time inside a session's span, biased away from the
// very edges so episodes do not collide with start and end handling.
//
// It never returns a time before start. A session whose window has already
// closed (playback would begin after its planned end) would otherwise schedule
// into the past, and the scheduler's clock would have to run backwards.
func (g *Generator) uniformWithin(start, end time.Time) time.Time {
	span := end.Sub(start)
	if span <= 2*time.Second {
		return start.Add(max(span, 0) / 2)
	}
	offset := time.Duration(g.rnd.Float64() * float64(span-2*time.Second))
	return start.Add(time.Second + offset)
}
