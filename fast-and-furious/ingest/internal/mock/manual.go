package mock

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Action is a button on the stepper.
type Action string

const (
	ActionStart      Action = "start"
	ActionPlay       Action = "play"
	ActionPause      Action = "pause"
	ActionResume     Action = "resume"
	ActionBackground Action = "background"
	ActionForeground Action = "foreground"
	ActionHeartbeat  Action = "heartbeat"
	ActionError      Action = "error"
	ActionEnd        Action = "end"

	// ActionAdBreak and ActionRateChange exist to make two deliberate
	// classification decisions visible. Both are 'liveness' in 003, NOT
	// play-state transitions, and both look like they should be pauses.
	ActionAdBreak    Action = "adbreak"
	ActionRateChange Action = "ratechange"
)

// actionEvents maps a button to the (event_type, event) pairs it emits.
//
// The pairs themselves live in internal/model, because internal/fleet emits the
// same wire strings and a second literal here would be a silent classifier
// disagreement — the kind that shows up as a concurrency figure a few percent
// wrong with nothing in the logs to explain it.
//
// ActionRateChange emits BOTH halves at the SAME millisecond, because that is
// what the real client does — 365 of 380 speed pairs in the supplied extract share
// a timestamp. It is here so the dashboard can demonstrate why classing them as
// pause/resume is unsafe: under stop-wins precedence the pair would collapse to
// STOPPED with no resume left to reopen it, which cost 41.9 hours of active time
// across 174 sessions when measured.
var actionEvents = map[Action][]model.EventPair{
	ActionStart:      {model.PairSessionStart},
	ActionPlay:       {model.PairPlay},
	ActionPause:      {model.PairPause},
	ActionResume:     {model.PairResume},
	ActionBackground: {model.PairBackground},
	ActionForeground: {model.PairForeground},
	ActionHeartbeat:  {model.PairHeartbeat},
	ActionError:      {model.PairError},
	ActionEnd:        {model.PairSessionEnd},
	ActionAdBreak:    {model.PairAdPause},
	ActionRateChange: {model.PairSpeedPause, model.PairSpeedResume},
}

// ManualSession is one hand-driven session and its event-time cursor.
type ManualSession struct {
	VideoSessionID string    `json:"video_session_id"`
	UserID         string    `json:"user_id"`
	ContentID      int64     `json:"content_id"`
	ContentTitle   string    `json:"content_title"`
	Platform       string    `json:"platform"`
	AppVersion     string    `json:"app_version"`
	Country        string    `json:"country"`
	StartEpoch     time.Time `json:"start_epoch"`

	// Clock is the event-time cursor. Every action stamps its events here and
	// then advances it.
	//
	// A virtual clock rather than wall-clock now(): the liveness lease is 120s,
	// so demonstrating an expiry against real time would mean waiting two
	// minutes. Advancing by +130s makes it one click, and it keeps a
	// demonstration reproducible.
	Clock time.Time `json:"clock"`

	EventsSent int `json:"events_sent"`
}

// Manual holds the hand-driven sessions.
type Manual struct {
	mu        sync.Mutex
	sessions  map[string]*ManualSession
	client    *chx.Client
	runID     uuid.UUID
	timeoutMS int64
}

// NewManual builds an empty stepper.
func NewManual(client *chx.Client, timeoutMS int64) *Manual {
	return &Manual{
		sessions:  make(map[string]*ManualSession),
		client:    client,
		runID:     uuid.New(),
		timeoutMS: timeoutMS,
	}
}

// hex64 mints a 64-character uppercase hex id, matching the source format.
func hex64() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		// crypto/rand failing is not a condition worth degrading for.
		panic(fmt.Sprintf("crypto/rand: %v", err))
	}
	return strings.ToUpper(hex.EncodeToString(b))
}

// NewSession mints a session pinned to one content id, its clock starting now.
func (m *Manual) NewSession(content chx.ContentInfo, platform, appVersion, country string) *ManualSession {
	now := time.Now().UTC().Truncate(time.Millisecond)
	s := &ManualSession{
		VideoSessionID: hex64(),
		UserID:         hex64(),
		ContentID:      content.ContentID,
		ContentTitle:   content.Title,
		Platform:       platform,
		AppVersion:     appVersion,
		Country:        country,
		StartEpoch:     now,
		Clock:          now,
	}
	m.mu.Lock()
	m.sessions[s.VideoSessionID] = s
	m.mu.Unlock()
	return s
}

// Sessions lists the hand-driven sessions, newest clock first.
func (m *Manual) Sessions() []*ManualSession {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]*ManualSession, 0, len(m.sessions))
	for _, s := range m.sessions {
		cp := *s
		out = append(out, &cp)
	}
	return out
}

// Session returns one session by id.
func (m *Manual) Session(vsid string) (*ManualSession, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	s, ok := m.sessions[vsid]
	if !ok {
		return nil, false
	}
	cp := *s
	return &cp, true
}

// Send stamps an action's events at the session's clock, advancing it first by
// advance, and writes them.
//
// advance is applied BEFORE stamping, so "+130s then Heartbeat" produces a
// heartbeat 130 seconds after the previous event — which is how you blow the
// lease deliberately.
func (m *Manual) Send(ctx context.Context, vsid string, action Action, advance time.Duration) (*ManualSession, error) {
	pairs, ok := actionEvents[action]
	if !ok {
		return nil, fmt.Errorf("unknown action %q", action)
	}

	m.mu.Lock()
	s, ok := m.sessions[vsid]
	if !ok {
		m.mu.Unlock()
		return nil, fmt.Errorf("unknown session %s", vsid)
	}
	if advance > 0 {
		s.Clock = s.Clock.Add(advance)
	}
	stamp := s.Clock
	snapshot := *s
	m.mu.Unlock()

	batchID := uuid.New()
	rows := make([]model.RawEvent, 0, len(pairs))
	for i, p := range pairs {
		rows = append(rows, model.RawEvent{
			IngestBatchID: batchID,
			BatchRowSeq:   uint32(i),
			// SourceFile is deliberately not set: Loader.sendChunk stamps it from
			// LoaderOptions.Source, because the origin label is a property of the
			// write and not of the row. Setting it here would be silently
			// overwritten.

			VideoSessionID: snapshot.VideoSessionID,
			UserID:         snapshot.UserID,
			ContentID:      snapshot.ContentID,

			EventType:      p.Type,
			Event:          p.Event,
			EventTimestamp: stamp,
			// Every event of a session carries the same session_start_epoch;
			// events_raw relies on it being constant per session for its
			// partition key, and 006's session_start_date derives from it.
			SessionStartEpoch: snapshot.StartEpoch,

			Platform:         snapshot.Platform,
			AppVersion:       snapshot.AppVersion,
			Country:          snapshot.Country,
			AudioLanguage:    "hin",
			SubtitleLanguage: "unk",
			PlayerVersion:    "1.8.2",
		})
	}

	if err := m.insert(ctx, batchID, rows); err != nil {
		return nil, err
	}

	m.mu.Lock()
	s.EventsSent += len(rows)
	out := *s
	m.mu.Unlock()
	return &out, nil
}

// insert writes one small batch through the shared loader.
//
// Reuses chx.Loader rather than opening a second insert path, so manual events
// get the same retry, deduplication-token and batch-audit behaviour as a CSV
// load. Async is on: a one- or two-row insert is precisely the case server-side
// async buffering exists for, and it is the same path the ingest API will use, so
// the stepper doubles as that path's end-to-end test.
//
// Fingerprint is per-event, and this is the subtle part. Loader's token is
// source|fingerprint|bs|n|ordinal. With a constant source and fingerprint every
// single-row insert would produce the SAME token, so ClickHouse block
// deduplication would silently swallow every event after the first. Deriving the
// fingerprint from the rows themselves makes distinct events distinct, while an
// identical resend still dedups — which is the idempotency we want.
func (m *Manual) insert(ctx context.Context, batchID uuid.UUID, rows []model.RawEvent) error {
	loader := chx.NewLoader(m.client, chx.LoaderOptions{
		Source:      "manual",
		RunID:       m.runID,
		Fingerprint: rowsFingerprint(rows),
		BatchSize:   len(rows),
		Workers:     1,
		MaxRetries:  2,
		AsyncInsert: true,
	})

	chunks := make(chan *chx.Chunk, 1)
	chunks <- &chx.Chunk{Ordinal: 0, Rows: rows}
	close(chunks)

	if _, err := loader.Run(ctx, chunks); err != nil {
		return fmt.Errorf("send manual event: %w", err)
	}
	return nil
}

// rowsFingerprint hashes the canonical form of the rows.
//
// The field list and the \x1F separator match the canonical fingerprint
// documented in sql/002_events_raw.sql, so a client-side identity and the
// server-side `sonyliv-ingest verify` identity agree by construction rather than
// by two places happening to list the same columns.
func rowsFingerprint(rows []model.RawEvent) string {
	h := sha256.New()
	for _, e := range rows {
		fmt.Fprintf(h, "%s\x1F%s\x1F%d\x1F%s\x1F%s\x1F%d\x1F%s\x1F%s\x1F%s\x1F%s\x1F%s\x1F%s\x1F%d\x1E",
			e.VideoSessionID, e.UserID, e.ContentID,
			e.EventType, e.Event, e.EventTimestamp.UnixMilli(),
			e.Platform, e.AppVersion, e.Country,
			e.AudioLanguage, e.SubtitleLanguage, e.PlayerVersion,
			e.SessionStartEpoch.UnixMilli())
	}
	return hex.EncodeToString(h.Sum(nil))[:32]
}
