package mock

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// Limits on POST /api/events.
//
// MaxIngestRows is not arbitrary. row_version packs the batch row sequence into
// 20 bits ((ingest_millis << 20) | seq), so a single chunk must stay under
// 1,048,576 rows or the sequence overflows into the millisecond field and
// silently corrupts conflict resolution. The API accepts more than that per
// request and splits into chunks below IngestChunkRows, so the bound holds no
// matter what a caller posts.
const (
	MaxIngestBytes  = 64 << 20 // 64 MiB of JSON
	MaxIngestRows   = 500_000
	IngestChunkRows = 50_000
	seqBudget       = 1 << 20
)

// EventIn is one event as a producer posts it.
//
// Field names are the SOURCE CSV header, not Go-ish names, so an external
// producer can post exactly the shape it already has. This is the same vocabulary
// events_raw uses; the rename into analytical terms happens once, server-side, at
// the boundary into events_clean.
//
// No normalization here either — no case folding, no event classification. Those
// rules live in the events_raw_to_clean_mv SELECT precisely so that this endpoint,
// the CSV loader and the generator cannot drift apart.
type EventIn struct {
	VideoSessionID string `json:"video_session_id"`
	UserID         string `json:"user_id"`
	ContentID      int64  `json:"content_id"`

	EventType string `json:"event_type"`
	Event     string `json:"event"`

	EventTimestamp    FlexTime `json:"event_timestamp"`
	SessionStartEpoch FlexTime `json:"session_start_epoch"`

	Platform         string `json:"platform"`
	AppVersion       string `json:"app_version"`
	Country          string `json:"country"`
	AudioLanguage    string `json:"audio_language"`
	SubtitleLanguage string `json:"subtitle_language"`
	PlayerVersion    string `json:"player_version"`
}

// FlexTime accepts either epoch milliseconds (what the source CSV carries) or an
// RFC3339 string (what a hand-written curl is likely to send). Accepting both
// costs one type and removes the commonest reason a producer's first POST fails.
type FlexTime struct{ time.Time }

func (t *FlexTime) UnmarshalJSON(b []byte) error {
	s := strings.TrimSpace(string(b))
	if s == "null" || s == `""` {
		return nil
	}
	if s[0] == '"' {
		var str string
		if err := json.Unmarshal(b, &str); err != nil {
			return err
		}
		// Epoch millis are also accepted as a quoted string, because JSON encoders
		// in several languages stringify int64 to dodge float precision loss.
		if ms, err := strconv.ParseInt(str, 10, 64); err == nil {
			t.Time = time.UnixMilli(ms).UTC()
			return nil
		}
		parsed, err := time.Parse(time.RFC3339Nano, str)
		if err != nil {
			return fmt.Errorf("timestamp %q is neither epoch millis nor RFC3339: %w", str, err)
		}
		t.Time = parsed.UTC()
		return nil
	}
	ms, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return fmt.Errorf("timestamp %s is not epoch millis: %w", s, err)
	}
	t.Time = time.UnixMilli(ms).UTC()
	return nil
}

func (e *EventIn) validate() error {
	switch {
	case len(e.VideoSessionID) == 0:
		return errors.New("video_session_id is required")
	case len(e.UserID) == 0:
		return errors.New("user_id is required")
	case e.EventType == "":
		return errors.New("event_type is required")
	case e.EventTimestamp.IsZero():
		return errors.New("event_timestamp is required")
	}
	// session_start_epoch is constant per session in the source and events_raw
	// partitions on it, so a missing value would scatter one session's rows across
	// partitions and break the guarantee ReplacingMergeTree relies on. Defaulting
	// it to the event time is wrong but silent; refusing is neither.
	if e.SessionStartEpoch.IsZero() {
		return errors.New("session_start_epoch is required (events_raw partitions on it)")
	}
	if e.Event == "" {
		// The source always carries one; a non-heartbeat event repeats its type.
		e.Event = e.EventType
	}
	return nil
}

func (e *EventIn) row() model.RawEvent {
	return model.RawEvent{
		VideoSessionID:    e.VideoSessionID,
		UserID:            e.UserID,
		ContentID:         e.ContentID,
		EventType:         e.EventType,
		Event:             e.Event,
		EventTimestamp:    e.EventTimestamp.Time,
		SessionStartEpoch: e.SessionStartEpoch.Time,
		Platform:          e.Platform,
		AppVersion:        e.AppVersion,
		Country:           e.Country,
		AudioLanguage:     e.AudioLanguage,
		SubtitleLanguage:  e.SubtitleLanguage,
		PlayerVersion:     e.PlayerVersion,
	}
}

// IngestResult is what POST /api/events returns.
type IngestResult struct {
	Accepted   int      `json:"accepted"`
	Rejected   int      `json:"rejected"`
	Chunks     int      `json:"chunks"`
	BatchIDs   []string `json:"batch_ids"`
	DedupKey   string   `json:"dedup_key"`
	DurationMS int64    `json:"duration_ms"`
	Errors     []string `json:"errors,omitempty"`
}

// handleEvents is the ingest endpoint: POST /api/events.
//
// Accepts NDJSON (Content-Type: application/x-ndjson) or a JSON array
// (application/json). NDJSON is the streaming shape — it decodes row by row with
// bounded memory, which is what a real producer should send. The array form
// exists because it is what a person writing a curl by hand will reach for.
//
// Idempotency: the deduplication token is derived from an Idempotency-Key header
// when present, otherwise from a hash of the decoded rows. Either way a repeated
// POST of the same payload is dropped by ClickHouse block deduplication rather
// than double-counted, and two genuinely different payloads never collide. This
// matters more than usual here because
// deduplicate_blocks_in_dependent_materialized_views is on, so a colliding token
// would also suppress the dirty_sessions row and the session would never be
// recompacted.
func (s *Server) handleEvents(w http.ResponseWriter, r *http.Request) {
	started := time.Now()
	ct := r.Header.Get("Content-Type")
	body := http.MaxBytesReader(w, r.Body, MaxIngestBytes)

	var (
		rows     []model.RawEvent
		rejected int
		problems []string
	)

	add := func(in EventIn, n int) {
		if err := in.validate(); err != nil {
			rejected++
			if len(problems) < 10 {
				problems = append(problems, fmt.Sprintf("row %d: %v", n, err))
			}
			return
		}
		rows = append(rows, in.row())
	}

	switch {
	case strings.Contains(ct, "application/x-ndjson"), strings.Contains(ct, "application/jsonl"):
		sc := bufio.NewScanner(body)
		// Default token size is 64KB; an event with long ids and versions fits, but
		// raise it so a fat row is a parse error rather than a truncation.
		sc.Buffer(make([]byte, 0, 256<<10), 1<<20)
		n := 0
		for sc.Scan() {
			line := strings.TrimSpace(sc.Text())
			if line == "" {
				continue
			}
			n++
			if len(rows) >= MaxIngestRows {
				writeErr(w, http.StatusRequestEntityTooLarge,
					fmt.Errorf("more than %d rows in one request; split it", MaxIngestRows))
				return
			}
			var in EventIn
			if err := json.Unmarshal([]byte(line), &in); err != nil {
				rejected++
				if len(problems) < 10 {
					problems = append(problems, fmt.Sprintf("row %d: %v", n, err))
				}
				continue
			}
			add(in, n)
		}
		if err := sc.Err(); err != nil {
			writeErr(w, http.StatusBadRequest, fmt.Errorf("read ndjson: %w", err))
			return
		}

	case strings.Contains(ct, "application/json"), ct == "":
		var batch []EventIn
		if err := json.NewDecoder(body).Decode(&batch); err != nil {
			writeErr(w, http.StatusBadRequest,
				fmt.Errorf("decode JSON array (or send Content-Type: application/x-ndjson): %w", err))
			return
		}
		if len(batch) > MaxIngestRows {
			writeErr(w, http.StatusRequestEntityTooLarge,
				fmt.Errorf("%d rows in one request exceeds the %d limit; split it", len(batch), MaxIngestRows))
			return
		}
		for i := range batch {
			add(batch[i], i+1)
		}

	default:
		writeErr(w, http.StatusUnsupportedMediaType,
			fmt.Errorf("Content-Type %q: send application/x-ndjson or application/json", ct))
		return
	}

	if len(rows) == 0 {
		writeJSON(w, http.StatusBadRequest, IngestResult{
			Rejected: rejected,
			Errors:   append(problems, "no valid rows"),
		})
		return
	}

	res, err := s.ingest(r.Context(), rows, r.Header.Get("Idempotency-Key"))
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}
	res.Rejected = rejected
	res.Errors = problems
	res.DurationMS = time.Since(started).Milliseconds()
	writeJSON(w, http.StatusOK, res)
}

// ingest splits rows into chunks and writes them through the shared loader.
//
// Chunking is what keeps _batch_row_seq inside its 20-bit budget: the loader
// stamps seq as the index within a chunk, so a chunk below seqBudget can never
// overflow row_version regardless of how large the request was.
func (s *Server) ingest(ctx context.Context, rows []model.RawEvent, idemKey string) (IngestResult, error) {
	if IngestChunkRows >= seqBudget {
		// A compile-time-ish guard on the constant above, checked once at runtime
		// rather than trusting a comment to stay true.
		return IngestResult{}, fmt.Errorf(
			"IngestChunkRows %d exceeds the %d row_version sequence budget", IngestChunkRows, seqBudget)
	}

	fingerprint := idemKey
	if fingerprint == "" {
		fingerprint = rowsFingerprint(rows)
	} else {
		// Hash the caller's key rather than trusting it into a token verbatim: it
		// is untrusted input that ends up in a ClickHouse setting string.
		sum := sha256.Sum256([]byte(idemKey))
		fingerprint = hex.EncodeToString(sum[:])[:32]
	}

	loader := chx.NewLoader(s.client, chx.LoaderOptions{
		Source:      "api",
		RunID:       uuid.New(),
		Fingerprint: fingerprint,
		BatchSize:   IngestChunkRows,
		Workers:     1,
		MaxRetries:  2,
		// Async insert: this endpoint exists to absorb many small producer POSTs,
		// which is exactly the case server-side buffering is for. Loader forces
		// wait_for_async_insert=1, so the response only returns once the server has
		// flushed — the caller's 200 means durable, not merely queued.
		AsyncInsert: true,
	})

	chunks := make(chan *chx.Chunk, 4)
	res := IngestResult{Accepted: len(rows)}
	go func() {
		defer close(chunks)
		for i, ord := 0, uint32(0); i < len(rows); i, ord = i+IngestChunkRows, ord+1 {
			end := min(i+IngestChunkRows, len(rows))
			id := uuid.New()
			res.BatchIDs = append(res.BatchIDs, id.String())
			for j := range rows[i:end] {
				rows[i+j].IngestBatchID = id
			}
			chunks <- &chx.Chunk{Ordinal: ord, Rows: rows[i:end]}
		}
	}()

	stats, err := loader.Run(ctx, chunks)
	if err != nil {
		return res, fmt.Errorf("ingest: %w", err)
	}
	res.Chunks = int(stats.Batches)
	res.DedupKey = fingerprint
	return res, nil
}
