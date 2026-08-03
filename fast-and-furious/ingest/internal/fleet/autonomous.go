package fleet

import (
	"math"
	"math/rand"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/generator"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Mode is how a session decides what to do next.
type Mode string

const (
	// ModeManual: the session holds whatever state an operator put it in and only
	// heartbeats. This is what the fleet has always done.
	ModeManual Mode = "manual"

	// ModeAutonomous: the session drives its own pauses, backgrounds and ending
	// from the rates measured on the supplied extract. A hundred thousand of these
	// IS the load test — same write path, same event shapes, but every session
	// stays individually addressable, which the old generator's sessions never
	// were.
	ModeAutonomous Mode = "autonomous"
)

// Behaviour rates, taken from internal/generator rather than restated.
//
// The episode COUNTS are per session over its whole life; the window durations
// are properties of how people use a player. Both are measured, and the reason
// they live in one place is that two producers with their own copies would drift
// into two different definitions of "realistic".
const (
	autoSessionMedian = generator.MeasuredSessionMedian
	autoSessionP99    = generator.MeasuredSessionP99
	autoBgEpisodes    = generator.MeasuredBackgroundEpisodes
	autoPauseEpisodes = generator.MeasuredPauseEpisodes
	autoErrorProb     = generator.MeasuredErrorProbability
)

// lognormal draws a duration with the given median and upper quantile.
//
// Same shape internal/generator uses: fit sigma from the p90/median ratio, then
// exponentiate a normal draw. Session lengths and pause windows are both heavily
// right-skewed in the extract, so a normal or uniform draw would produce a
// population that looks nothing like the real one.
func lognormalDraw(rnd *rand.Rand, median, upper time.Duration, z float64) time.Duration {
	mu := math.Log(float64(median))
	sigma := (math.Log(float64(upper)) - mu) / z
	return time.Duration(math.Exp(mu + sigma*rnd.NormFloat64()))
}

// planAutonomous sets a session's own ending and its first behaviour change.
//
// The ending is clamped to the TTL: the TTL is the operator's ceiling on how long
// the fleet may write, and a lognormal p99 of 74 minutes would otherwise sail past
// a 10-minute lifetime.
func (s *Session) planAutonomous(rnd *rand.Rand, now time.Time) {
	life := lognormalDraw(rnd, autoSessionMedian, autoSessionP99, generator.Z90)
	if life < 30*time.Second {
		life = 30 * time.Second
	}
	s.endsAt = now.Add(life)
	if !s.ExpiresAt.IsZero() && s.endsAt.After(s.ExpiresAt) {
		s.endsAt = s.ExpiresAt
	}
	s.scheduleBehaviour(rnd, now, life)
}

// scheduleBehaviour picks when this session next changes state.
//
// Exponential with a mean of life/episodes: over a session of that length the
// expected number of episodes matches the measured count, and the gaps are
// memoryless, which is what stops a whole batch created together from changing
// state in lockstep.
func (s *Session) scheduleBehaviour(rnd *rand.Rand, now time.Time, life time.Duration) {
	episodes := autoBgEpisodes + autoPauseEpisodes
	mean := time.Duration(float64(life) / episodes)
	if mean < time.Second {
		mean = time.Second
	}
	s.nextBehaviour = now.Add(time.Duration(rnd.ExpFloat64() * float64(mean)))
}

// autoStep advances one autonomous session, returning the pair to emit (if any).
//
// Called from the sweep, which already holds the lock and is already walking every
// session — so this costs one extra time comparison per session per tick, not a
// second scheduler.
//
// The order matters. Ending is checked first because a session past its life
// should close rather than pause on its way out, and a session in a pause or
// background window is resumed before a new episode can be chosen, so the two can
// never nest.
func (s *Session) autoStep(rnd *rand.Rand, now time.Time) (model.EventPair, bool) {
	if !s.endsAt.IsZero() && !now.Before(s.endsAt) {
		return model.PairSessionEnd, true
	}
	if s.nextBehaviour.IsZero() || now.Before(s.nextBehaviour) {
		return model.EventPair{}, false
	}

	life := s.endsAt.Sub(s.StartEpoch)
	if life <= 0 {
		life = autoSessionMedian
	}

	// Currently inside an episode: come back out of it.
	switch {
	case !s.playing:
		s.scheduleBehaviour(rnd, now, life)
		return model.PairResume, true
	case !s.foreground:
		s.scheduleBehaviour(rnd, now, life)
		return model.PairForeground, true
	}

	// Active: start a new episode. Pause and background are chosen in proportion
	// to their measured counts (2.5 pauses to 1.35 backgrounds per session), and
	// the window length decides when the session comes back.
	total := autoPauseEpisodes + autoBgEpisodes
	if rnd.Float64() < autoPauseEpisodes/total {
		s.nextBehaviour = now.Add(max(
			lognormalDraw(rnd, generator.PauseWindowMedian, generator.PauseWindowP90, generator.Z90),
			time.Second))
		// A small share of stops are errors rather than deliberate pauses. Same
		// signal class as a pause, so the state machine treats them identically —
		// which is the point of carrying it: it exercises that equivalence.
		if rnd.Float64() < autoErrorProb {
			return model.PairError, true
		}
		return model.PairPause, true
	}
	s.nextBehaviour = now.Add(max(
		lognormalDraw(rnd, generator.BgWindowMedian, generator.BgWindowP90, generator.Z90),
		2*time.Second))
	return model.PairBackground, true
}
