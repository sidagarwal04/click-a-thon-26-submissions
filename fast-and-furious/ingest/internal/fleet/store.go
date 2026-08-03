package fleet

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// TTL bounds. A session that never expires is a writer nobody remembers starting.
const (
	DefaultTTL = 60 * time.Minute
	MinTTL     = time.Minute
	MaxTTL     = 24 * time.Hour
)

// Persisted is one session flattened for storage.
//
// A separate type from Session on purpose. Session's fields are unexported
// because nothing outside this package may mutate the state machine, and this is
// the one sanctioned crossing — a plain record with no methods, no behaviour, and
// no way to put a session into a state its own transitions could not reach.
type Persisted struct {
	ID           string
	UserID       string
	ContentID    int64
	ContentTitle string
	VideoType    string

	Platform   string
	AppVersion string
	Country    string

	StartEpoch     time.Time
	CadenceSeconds int
	ExpiresAt      time.Time
	Mode           string
	EndsAt         time.Time
	NextBehaviour  time.Time

	Started      bool
	Ended        bool
	Foreground   bool
	Playing      bool
	Heartbeating bool

	LastEligible time.Time
	OpenSince    time.Time
	Intervals    []Interval

	EventsSent int
	NextTick   time.Time
	Removed    bool
	UpdatedAt  time.Time
}

// Store is durable storage for fleet state.
//
// The fleet knows nothing about ClickHouse; internal/mock implements this over
// the connection the process already has. Save is upsert-by-id — the store is
// expected to keep exactly one current row per session, which is why
// 007_fleet_sessions.sql is a ReplacingMergeTree and not an append log.
type Store interface {
	Save(ctx context.Context, rows []Persisted) error
	Load(ctx context.Context) ([]Persisted, error)
}

// snapshot returns rows for sessions changed since the last call, clearing their
// dirty flags.
//
// Only the changed ones: at MaxLive a full rewrite every few seconds would push
// tens of thousands of rows carrying interval arrays, to record that nothing
// happened. Work stays proportional to activity, which is the same principle the
// pipeline's own incremental recompute rests on.
func (r *Registry) snapshot() []Persisted {
	r.mu.Lock()
	defer r.mu.Unlock()

	out := make([]Persisted, 0, 64)
	for _, id := range r.order {
		s, ok := r.sessions[id]
		if !ok || !s.dirty {
			continue
		}
		out = append(out, Persisted{
			ID: s.ID, UserID: s.UserID,
			ContentID: s.ContentID, ContentTitle: s.ContentTitle, VideoType: s.VideoType,
			Platform: s.Platform, AppVersion: s.AppVersion, Country: s.Country,
			StartEpoch:     s.StartEpoch,
			CadenceSeconds: int(s.Cadence / time.Second),
			ExpiresAt:      s.ExpiresAt,
			Mode:           string(s.Mode),
			EndsAt:         s.endsAt,
			NextBehaviour:  s.nextBehaviour,
			Started:        s.started, Ended: s.ended,
			Foreground: s.foreground, Playing: s.playing, Heartbeating: s.heartbeating,
			LastEligible: s.lastEligible,
			OpenSince:    s.openSince,
			// Copied, not aliased: the caller holds this after the lock drops while
			// the session keeps appending.
			Intervals:  append([]Interval(nil), s.intervals...),
			EventsSent: s.eventsSent,
			NextTick:   s.nextTick,
			UpdatedAt:  time.Now().UTC(),
		})
		s.dirty = false
	}
	return out
}

// removedRows returns tombstones for ids dropped from the registry.
func removedRows(ids []string, now time.Time) []Persisted {
	out := make([]Persisted, 0, len(ids))
	for _, id := range ids {
		out = append(out, Persisted{ID: id, Removed: true, UpdatedAt: now})
	}
	return out
}

// Restore rebuilds the registry from stored rows and catches each session up to
// now. Returns the events that catching up produced.
//
// The catch-up is the whole point, and it is not cosmetic. While the process was
// down, wall-clock time kept passing for state the sessions had already committed
// to: leases ran out, and TTLs elapsed. Loading the rows verbatim would resurrect
// sessions as though they had been suspended, and the fleet's ground-truth line
// would then disagree with ClickHouse for a reason that is purely an artifact of
// the restart.
//
// So each session is replayed forward:
//   - a lease that expired while down closes its interval AT the expiry instant,
//     not at startup;
//   - a session whose TTL elapsed while down is ended, with the VideoSessionEnd
//     stamped at its expiry — a late event, which events_raw is built to absorb.
func (r *Registry) Restore(rows []Persisted, now time.Time) []model.RawEvent {
	r.mu.Lock()
	defer r.mu.Unlock()

	var events []model.RawEvent
	batchID := uuid.New()

	// Collect tombstones before restoring anything. A tombstone can arrive in the
	// same slice as the live row it retires — the ReplacingMergeTree collapses that
	// pair on merge, so the store usually filters it, but Restore must not depend
	// on that. Row order would otherwise decide whether a cleared session comes
	// back, which is exactly the kind of thing that works until it doesn't.
	removed := make(map[string]struct{})
	for _, p := range rows {
		if p.Removed && p.ID != "" {
			removed[p.ID] = struct{}{}
		}
	}

	for _, p := range rows {
		if p.Removed || p.ID == "" {
			continue
		}
		if _, gone := removed[p.ID]; gone {
			continue
		}
		if _, exists := r.sessions[p.ID]; exists {
			continue
		}
		s := &Session{
			ID: p.ID, UserID: p.UserID,
			ContentID: p.ContentID, ContentTitle: p.ContentTitle, VideoType: p.VideoType,
			Platform: p.Platform, AppVersion: p.AppVersion, Country: p.Country,
			StartEpoch:    p.StartEpoch,
			Cadence:       time.Duration(p.CadenceSeconds) * time.Second,
			ExpiresAt:     p.ExpiresAt,
			Mode:          Mode(p.Mode),
			endsAt:        p.EndsAt,
			nextBehaviour: p.NextBehaviour,
			started:       p.Started, ended: p.Ended,
			foreground: p.Foreground, playing: p.Playing, heartbeating: p.Heartbeating,
			lastEligible: p.LastEligible,
			openSince:    p.OpenSince,
			intervals:    append([]Interval(nil), p.Intervals...),
			eventsSent:   p.EventsSent,
			nextTick:     p.NextTick,
		}
		if s.Cadence <= 0 {
			s.Cadence = DefaultCadence
		}
		if s.Mode == "" {
			s.Mode = ModeManual
		}

		// Retire anything whose TTL elapsed while the process was down, at the
		// instant it actually elapsed. dirty starts false so a session that needs
		// no catch-up is not rewritten to the store just for having been loaded;
		// apply() and reconcile() set it themselves when they change something.
		s.dirty = false
		if !s.ended && s.expired(now) {
			at := s.ExpiresAt
			if at.Before(s.StartEpoch) {
				at = s.StartEpoch
			}
			events = append(events,
				s.apply(model.PairSessionEnd, at, r.timeout, batchID, uint32(len(events))))
		}
		// Close any interval the lease ended while we were not watching.
		s.reconcile(now, r.timeout)

		r.sessions[s.ID] = s
		r.order = append(r.order, s.ID)
	}
	return events
}
