// Package fleet runs a controllable population of live video sessions.
//
// Each session ticks on wall-clock time, emitting heartbeats at a configured
// cadence until an operator pauses, backgrounds, silences or ends it. That makes
// it a different tool from the two producers in internal/mock: the load simulator
// there maximises throughput and decides session behaviour from measured
// distributions, and the stepper advances a virtual clock one click at a time.
// Neither can answer "what happens to concurrency if I background 200 of these
// right now", which is what this package exists for.
//
// The other reason it exists: the fleet knows the exact truth. It does not infer
// activity from an event stream, it *decides* activity and records the interval at
// the moment of transition. That makes it an independent oracle for the
// ClickHouse pipeline — see curve.go.
package fleet

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Command is an operator action on one session.
type Command string

const (
	CmdPause      Command = "pause"
	CmdResume     Command = "resume"
	CmdBackground Command = "background"
	CmdForeground Command = "foreground"

	// CmdSilence and CmdUnsilence write NO event. They stop and restart the
	// heartbeat ticker, which is the app-killed / network-dropped case: the
	// pipeline cannot know it happened and only notices when the lease expires.
	// This is the one control that demonstrates what actually bounds an unclosed
	// session.
	CmdSilence   Command = "silence"
	CmdUnsilence Command = "unsilence"

	// CmdEnd is the delete button. It closes the session cleanly with a
	// VideoSessionEnd, so the pipeline sees a session_end signal rather than
	// inferring abandonment.
	CmdEnd Command = "end"
)

// commandPairs maps a command to the event it writes.
//
// CmdSilence and CmdUnsilence are absent, and that absence is the definition:
// they write nothing. A lookup miss is how the code distinguishes them, so adding
// an entry here would silently make the app-killed case observable to the pipeline.
var commandPairs = map[Command]model.EventPair{
	CmdPause:      model.PairPause,
	CmdResume:     model.PairResume,
	CmdBackground: model.PairBackground,
	CmdForeground: model.PairForeground,
	CmdEnd:        model.PairSessionEnd,
}

// Phase is the coarse lifecycle label shown in the listing.
type Phase string

const (
	PhaseActive       Phase = "active"
	PhasePaused       Phase = "paused"
	PhaseBackgrounded Phase = "backgrounded"
	// PhaseExpired means still nominally playing and foregrounded, but no
	// eligible liveness signal inside the lease — so the pipeline counts it as
	// gone. Distinct from paused on purpose: it is the state you reach by
	// silencing, and the one most people do not expect to exist.
	PhaseExpired Phase = "expired"
	PhaseEnded   Phase = "ended"
)

// Interval is one active range, half-open [Start, End).
type Interval struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// Session is one live session and the state the activity predicate reads.
//
// foreground and playing are independent booleans, not one enum, because the
// pipeline models them that way and the simulator has to speak the same
// language. Collapsing them was measured at 38,958 disagreements across 98.8% of
// sessions — all overcounts — so an enum here would make the comparison line in
// curve.go meaningless.
type Session struct {
	ID           string `json:"video_session_id"`
	UserID       string `json:"user_id"`
	ContentID    int64  `json:"content_id"`
	ContentTitle string `json:"content_title"`
	VideoType    string `json:"video_type"`

	Platform   string `json:"platform"`
	AppVersion string `json:"app_version"`
	Country    string `json:"country"`

	// StartEpoch is session_start_epoch, constant for the session's whole life.
	// events_raw partitions on it and 006's session_start_date derives from it, so
	// it must never move.
	StartEpoch time.Time     `json:"start_epoch"`
	Cadence    time.Duration `json:"-"`

	// ExpiresAt is when the simulator retires this session on its own, by writing
	// a real VideoSessionEnd. Without it a fleet left running heartbeats into
	// events_raw forever — a demo quietly becoming an unattended writer.
	ExpiresAt time.Time `json:"expires_at"`

	// Mode decides who drives. Manual sessions hold whatever state an operator put
	// them in; autonomous ones pause, background and end themselves from the
	// measured rates. Both are still individually addressable — the mode changes
	// who acts, not whether you can.
	Mode Mode `json:"mode"`

	// endsAt and nextBehaviour are the autonomous schedule. Unset for manual.
	endsAt        time.Time
	nextBehaviour time.Time

	started      bool
	ended        bool
	foreground   bool
	playing      bool
	heartbeating bool

	// lastEligible is the newest liveness signal that landed while the session was
	// otherwise active. The lease runs to lastEligible+timeout.
	//
	// Only *eligible* signals count. A heartbeat sent while paused is recorded by
	// the client and ignored here, exactly as the pipeline ignores it, which is why
	// a session paused for longer than the lease does not silently stay leased.
	lastEligible time.Time

	// openSince is the start of the in-flight active interval, zero when inactive.
	openSince time.Time
	intervals []Interval

	eventsSent int
	nextTick   time.Time
	endedAt    time.Time

	// dirty marks state the store has not seen yet. Persisting every session on
	// every tick would rewrite the whole table once a second; persisting only what
	// changed keeps the write proportional to activity.
	dirty bool
}

// Spec is what the create form submits.
type Spec struct {
	Count        int    `json:"count"`
	ContentID    int64  `json:"content_id"`
	ContentTitle string `json:"content_title"`
	VideoType    string `json:"video_type"`

	Platform   string `json:"platform"`
	AppVersion string `json:"app_version"`
	Country    string `json:"country"`

	// CadenceSeconds is the heartbeat interval. The extract's clients ping about
	// every 30s; changing it changes how fast a silenced session's lease decays
	// relative to its ticks, which is the whole demonstration.
	CadenceSeconds int `json:"cadence_seconds"`

	// TTLMinutes is how long the session lives before the simulator ends it
	// cleanly. Zero takes DefaultTTL.
	TTLMinutes int `json:"ttl_minutes"`

	// Mode is manual (default) or autonomous. Autonomous sessions drive their own
	// lifecycle, which is what makes a large batch of them a load test.
	Mode Mode `json:"mode"`
}

// hexID mints a 64-character uppercase hex id, matching the source format.
//
// internal/mock has a twin of this. Deliberately not shared, unlike the event
// pairs in model: if these two drift, both still produce 64 hex characters and
// nothing downstream can tell, whereas a drifted event string silently
// misclassifies a signal.
func hexID() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		panic(fmt.Sprintf("crypto/rand: %v", err))
	}
	return strings.ToUpper(hex.EncodeToString(b))
}

// newSession mints a session in the pre-start state. Nothing is active until
// start() runs.
func newSession(sp Spec, now time.Time) *Session {
	return &Session{
		ID:           hexID(),
		UserID:       hexID(),
		ContentID:    sp.ContentID,
		ContentTitle: sp.ContentTitle,
		VideoType:    sp.VideoType,
		Platform:     sp.Platform,
		AppVersion:   sp.AppVersion,
		Country:      sp.Country,
		StartEpoch:   now,
		Cadence:      time.Duration(sp.CadenceSeconds) * time.Second,
		ExpiresAt:    now.Add(time.Duration(sp.TTLMinutes) * time.Minute),
		Mode:         sp.Mode,
		heartbeating: true,
		dirty:        true,
	}
}

// expired reports whether the session has outlived its TTL.
func (s *Session) expired(now time.Time) bool {
	return !s.ExpiresAt.IsZero() && !now.Before(s.ExpiresAt)
}

// leaseExpiry is when the lease runs out, or the zero time if no eligible signal
// has ever landed.
func (s *Session) leaseExpiry(timeout time.Duration) time.Time {
	if s.lastEligible.IsZero() {
		return time.Time{}
	}
	return s.lastEligible.Add(timeout)
}

// isActive is the pipeline's five-term predicate, evaluated at now.
//
// Identical in structure to the SQL at state.go:139 and to the `active` column in
// concurrency/sql/010_recompute_sessions.sql: started AND NOT end_seen AND
// foreground AND playing AND inside the lease.
func (s *Session) isActive(now time.Time, timeout time.Duration) bool {
	if !s.started || s.ended || !s.foreground || !s.playing {
		return false
	}
	exp := s.leaseExpiry(timeout)
	return !exp.IsZero() && now.Before(exp)
}

// phase labels the session for the listing.
func (s *Session) phase(now time.Time, timeout time.Duration) Phase {
	switch {
	case s.ended:
		return PhaseEnded
	case !s.foreground:
		return PhaseBackgrounded
	case !s.playing:
		return PhasePaused
	case s.isActive(now, timeout):
		return PhaseActive
	default:
		return PhaseExpired
	}
}

// isLiveness reports whether a pair extends the lease when eligible.
//
// Mirrors `signal IN ('play','resume','liveness')` from 003's classifier. Note
// what is absent: AppForegrounded is a visibility setter, not liveness, so
// foregrounding a long-backgrounded session does NOT revive it — it stays outside
// the lease until the next heartbeat. That is real pipeline behaviour and the
// fleet reproduces it rather than smoothing it over.
func isLiveness(p model.EventPair) bool {
	switch p {
	case model.PairPlay, model.PairResume, model.PairHeartbeat,
		model.PairAdPause, model.PairSpeedPause, model.PairSpeedResume:
		return true
	default:
		return false
	}
}

// emit builds one raw event at `at` and counts it.
func (s *Session) emit(p model.EventPair, at time.Time, batchID uuid.UUID, seq uint32) model.RawEvent {
	s.eventsSent++
	return model.RawEvent{
		// All three of these are overwritten at the chunk boundary — the loader
		// restamps IngestBatchID and BatchRowSeq per chunk (loader.go:240) and fills
		// SourceFile from LoaderOptions.Source, because batch identity belongs to the
		// write and not to the row. Set here so a RawEvent built by the fleet is
		// complete and self-consistent in tests, not because the values survive.
		IngestBatchID: batchID,
		BatchRowSeq:   seq,

		VideoSessionID:    s.ID,
		UserID:            s.UserID,
		ContentID:         s.ContentID,
		EventType:         p.Type,
		Event:             p.Event,
		EventTimestamp:    at,
		SessionStartEpoch: s.StartEpoch,

		Platform:         s.Platform,
		AppVersion:       s.AppVersion,
		Country:          s.Country,
		AudioLanguage:    "hin",
		SubtitleLanguage: "unk",
		PlayerVersion:    "1.8.2",
	}
}

// apply writes one pair into the session, updating state, lease and intervals.
//
// Order matters and is the subtle part of this file:
//  1. reconcile first, so an interval that the lease already ended is closed at the
//     expiry instant rather than at `at`;
//  2. mutate state;
//  3. extend the lease only if the pair is liveness AND the post-mutation state is
//     eligible;
//  4. re-sync the interval against the new state.
//
// Doing (3) before (2) would let a `resume` fail its own eligibility check, since
// playing is still false at that point — the session would resume and instantly
// read as lease-expired.
func (s *Session) apply(p model.EventPair, at time.Time, timeout time.Duration, batchID uuid.UUID, seq uint32) model.RawEvent {
	s.reconcile(at, timeout)

	switch p {
	case model.PairSessionStart:
		s.started, s.foreground = true, true
	case model.PairPlay, model.PairResume:
		s.playing = true
	case model.PairPause, model.PairError:
		s.playing = false
	case model.PairBackground:
		s.foreground = false
	case model.PairForeground:
		s.foreground = true
	case model.PairSessionEnd:
		s.ended = true
		s.endedAt = at
	}

	if isLiveness(p) && s.started && !s.ended && s.foreground && s.playing {
		s.lastEligible = at
	}

	s.syncInterval(at, timeout)
	s.dirty = true
	return s.emit(p, at, batchID, seq)
}

// reconcile closes an in-flight interval whose lease expired before now.
//
// This is the one transition that no event causes: the session goes inactive
// because time passed. Called from the scheduler sweep and before every command,
// so a session's recorded intervals are correct whether or not anyone is watching.
func (s *Session) reconcile(now time.Time, timeout time.Duration) {
	if s.openSince.IsZero() || s.isActive(now, timeout) {
		return
	}
	s.closeInterval(s.inactiveAt(now, timeout))
	// A lease expiry is a real state change even though no event caused it, so it
	// has to reach the store like any other.
	s.dirty = true
}

// syncInterval opens or closes the in-flight interval to match the state at now.
func (s *Session) syncInterval(now time.Time, timeout time.Duration) {
	active := s.isActive(now, timeout)
	switch {
	case active && s.openSince.IsZero():
		s.openSince = now
	case !active && !s.openSince.IsZero():
		s.closeInterval(s.inactiveAt(now, timeout))
	}
}

// inactiveAt is the instant activity actually stopped.
//
// If the five-term predicate still holds on everything except the lease, the lease
// is what ended it — and it ended at the expiry, which is in the past. Using `now`
// there would credit the session with up to a full sweep interval of activity it
// did not have, and would break the conservation check against ClickHouse.
func (s *Session) inactiveAt(now time.Time, timeout time.Duration) time.Time {
	if s.started && !s.ended && s.foreground && s.playing {
		if exp := s.leaseExpiry(timeout); !exp.IsZero() && exp.Before(now) {
			return exp
		}
	}
	return now
}

// closeInterval records [openSince, end) and clears the cursor.
func (s *Session) closeInterval(end time.Time) {
	if end.After(s.openSince) {
		s.intervals = append(s.intervals, Interval{Start: s.openSince, End: end})
	}
	s.openSince = time.Time{}
}

// activeIntervals returns the closed intervals plus the in-flight one, clipped to
// the earlier of now and the lease expiry.
//
// Clipping matters: an active session's interval has no recorded end yet, and
// reporting it as open-ended would count activity past the point the pipeline
// stops counting.
// Always a copy: the result travels out through a View to an HTTP handler, while
// this session keeps being mutated under the registry lock. Returning the live
// slice would share backing memory across that boundary.
func (s *Session) activeIntervals(now time.Time, timeout time.Duration) []Interval {
	out := make([]Interval, len(s.intervals), len(s.intervals)+1)
	copy(out, s.intervals)
	if s.openSince.IsZero() {
		return out
	}
	end := now
	if exp := s.leaseExpiry(timeout); !exp.IsZero() && exp.Before(end) {
		end = exp
	}
	if end.After(s.openSince) {
		out = append(out, Interval{Start: s.openSince, End: end})
	}
	return out
}

// activeMS is the total recorded active time as of now.
func (s *Session) activeMS(now time.Time, timeout time.Duration) int64 {
	var total int64
	for _, iv := range s.activeIntervals(now, timeout) {
		total += iv.End.Sub(iv.Start).Milliseconds()
	}
	return total
}
