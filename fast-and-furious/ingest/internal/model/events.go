package model

// EventPair is the (event_type, event) tuple the source stream carries.
//
// Both halves matter and neither is redundant: the classifier in
// sql/003_events_clean.sql keys `signal` off the pair, not off either column
// alone. "VideoHeartbeat" is a pause, a resume, an ad break, a rate change or a
// plain ping depending entirely on `event`.
type EventPair struct {
	Type  string
	Event string
}

// The canonical pairs, defined once.
//
// This file exists because two producers now emit these: the hand-driven stepper
// in internal/mock and the autonomous fleet in internal/fleet. A second literal
// "VideoHeartbeat"/"pause" in either one would be a silent classifier
// disagreement — the kind that surfaces as a concurrency number that is wrong by
// a few percent with nothing in the logs.
//
// Values are the exact strings observed in the supplied extract. They are the
// wire format, so they are not normalised, retitled or case-folded here.
var (
	PairSessionStart = EventPair{"VideoSessionStart", "VideoSessionStart"}
	PairPlay         = EventPair{"VideoPlay", "Play"}
	PairPause        = EventPair{"VideoHeartbeat", "pause"}
	PairResume       = EventPair{"VideoHeartbeat", "resume"}
	PairBackground   = EventPair{"AppBackgrounded", "AppBackgrounded"}
	PairForeground   = EventPair{"AppForegrounded", "AppForegrounded"}
	PairHeartbeat    = EventPair{"VideoHeartbeat", "network-activity"}
	PairError        = EventPair{"VideoError", "VideoError"}
	PairSessionEnd   = EventPair{"VideoSessionEnd", "VideoSessionEnd"}

	// PairAdPause and the speed pair are liveness signals, NOT play-state
	// transitions. They look like pauses and are deliberately not treated as
	// such: 36 of 45 AdPause events in the extract land while the session is
	// already stopped, and 365 of 380 speed pairs share a single millisecond, so
	// classing them as pause/resume collapses them to STOPPED under stop-wins
	// precedence with no resume left to reopen the session. Measured cost of
	// getting this wrong: 41.9 hours of active time across 174 sessions.
	PairAdPause     = EventPair{"VideoHeartbeat", "AdPause"}
	PairSpeedPause  = EventPair{"VideoHeartbeat", "speed-pause"}
	PairSpeedResume = EventPair{"VideoHeartbeat", "speed-resume"}
)
