package api

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/csvsrc"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// maxRejectsReported caps the response body. Every reject is still counted and
// quarantined; only the echo back to the caller is truncated, so a wholly-bad
// request cannot make the response larger than the request.
const maxRejectsReported = 100

// wireEvent is the JSON shape of one event.
//
// Field names are the events_raw column names, which are also the source CSV
// header — one vocabulary from producer to landing zone.
//
// Timestamps and content_id are json.Number so the exact same parsers the CSV
// path uses can be applied to their literal text. That is not fussiness:
// ParseContentID has to recover 18446744072721897294 as -987654322, which no
// int64 field could accept, and ParseEpochMillis rejects a value that is really
// seconds or microseconds — a check that only exists on the string form.
type wireEvent struct {
	VideoSessionID    string      `json:"video_session_id"`
	UserID            string      `json:"user_id"`
	ContentID         json.Number `json:"content_id"`
	EventType         string      `json:"event_type"`
	Event             string      `json:"event"`
	EventTimestamp    json.Number `json:"event_timestamp"`
	SessionStartEpoch json.Number `json:"session_start_epoch"`
	Platform          string      `json:"platform"`
	AppVersion        string      `json:"app_version"`
	Country           string      `json:"country"`
	AudioLanguage     string      `json:"audio_language"`
	SubtitleLanguage  string      `json:"subtitle_language"`
	PlayerVersion     string      `json:"player_version"`
}

// rejectOut is the caller-facing view of a quarantined row.
type rejectOut struct {
	Index  uint64 `json:"index"`
	Reason string `json:"reason"`
	Detail string `json:"detail"`
}

type ingestResponse struct {
	Accepted int         `json:"accepted"`
	Rejected int         `json:"rejected"`
	Batches  int         `json:"batches"`
	Mode     string      `json:"mode"`
	Rejects  []rejectOut `json:"rejects,omitempty"`
}

func (s *Server) handleEvents(w http.ResponseWriter, r *http.Request) {
	s.requests.Add(1)

	if n := contentLengthHint(r); n > s.opts.MaxBodyBytes {
		writeJSON(w, http.StatusRequestEntityTooLarge, errBody("body_too_large",
			fmt.Sprintf("Content-Length %d exceeds --max-body %d", n, s.opts.MaxBodyBytes)))
		return
	}

	arrayMode, err := decodeMode(r.Header.Get("Content-Type"))
	if err != nil {
		writeJSON(w, http.StatusUnsupportedMediaType, errBody("unsupported_media_type", err.Error()))
		return
	}

	// The body is hashed as it is read so the digest covers the exact bytes the
	// caller sent, and is available as the dedup fingerprint without buffering
	// the request a second time.
	limited := http.MaxBytesReader(w, r.Body, s.opts.MaxBodyBytes)
	hasher := sha256.New()
	tee := io.TeeReader(limited, hasher)

	rows, rejects, err := s.decodeEvents(tee, arrayMode)
	if err != nil {
		var tooBig *http.MaxBytesError
		switch {
		case errors.As(err, &tooBig):
			writeJSON(w, http.StatusRequestEntityTooLarge, errBody("body_too_large",
				fmt.Sprintf("body exceeds --max-body %d", s.opts.MaxBodyBytes)))
		case errors.Is(err, errTooManyRows):
			writeJSON(w, http.StatusRequestEntityTooLarge, errBody("too_many_rows",
				fmt.Sprintf("more than --max-rows %d events in one request", s.opts.MaxRows)))
		default:
			writeJSON(w, http.StatusBadRequest, errBody("malformed_body", err.Error()))
		}
		return
	}
	// Finish hashing whatever the decoder did not consume (trailing whitespace,
	// or bytes after a closing bracket) so the fingerprint is of the whole body.
	if _, err := io.Copy(io.Discard, tee); err != nil {
		writeJSON(w, http.StatusBadRequest, errBody("read_failed", err.Error()))
		return
	}

	// Quarantine before inserting: a row that cannot be stored should be
	// recorded even if the insert then fails.
	if len(rejects) > 0 && s.rejecter != nil {
		for _, rj := range rejects {
			s.rejecter.AddReject(model.Reject{
				Source:     SourceLabel,
				SourceLine: rj.Index,
				Reason:     rj.Reason,
				Detail:     rj.Detail,
			})
		}
	}
	s.rejectedRows.Add(uint64(len(rejects)))

	resp := ingestResponse{
		Rejected: len(rejects),
		Rejects:  rejects[:min(len(rejects), maxRejectsReported)],
		Mode:     "sync",
	}

	if len(rows) == 0 {
		// Nothing insertable. Still a 200: the caller's request was handled and
		// every bad row is accounted for.
		resp.Mode = "none"
		writeJSON(w, http.StatusOK, resp)
		return
	}

	// Below the threshold the server-side buffer earns its place by coalescing
	// across producers; at or above it the caller has already batched well and
	// buffering would only add a flush delay. Measured: a per-request dedup
	// token does NOT prevent that coalescing, so both modes set one and both are
	// idempotent on retry. See ingest/API_DESIGN.md §2.
	async := len(rows) < s.opts.SyncThreshold
	if async {
		resp.Mode = "async"
	}

	chunks := chunk(rows, s.opts.BatchSize)
	fingerprint := r.Header.Get("Idempotency-Key")
	if fingerprint == "" {
		fingerprint = hex.EncodeToString(hasher.Sum(nil))
	}

	if _, err := s.writer.Write(r.Context(), fingerprint, async, chunks); err != nil {
		s.opts.Log.Error("insert failed", "error", err, "rows", len(rows), "chunks", len(chunks))
		writeJSON(w, http.StatusBadGateway, errBody("insert_failed", err.Error()))
		return
	}

	s.acceptedRows.Add(uint64(len(rows)))
	resp.Accepted = len(rows)
	resp.Batches = len(chunks)
	writeJSON(w, http.StatusOK, resp)
}

// SourceLabel is the fixed origin label for API traffic.
//
// Deliberately not caller-supplied. Source participates in the deduplication
// token, so a client that varied it between an attempt and its retry would
// defeat the idempotency the token exists to provide.
const SourceLabel = "api"

var errTooManyRows = errors.New("too many rows")

// decodeMode picks the reader from the content type. Strict on purpose: guessing
// wrong turns a JSON array into one malformed "line" and reports a confusing error.
func decodeMode(contentType string) (arrayMode bool, err error) {
	mt := strings.TrimSpace(strings.Split(contentType, ";")[0])
	switch strings.ToLower(mt) {
	case "application/json":
		return true, nil
	case "", "application/x-ndjson", "application/jsonl", "application/x-jsonlines", "text/plain":
		return false, nil
	default:
		return false, fmt.Errorf("content-type %q: use application/x-ndjson (one event per line) or application/json (array)", mt)
	}
}

// decodeEvents streams the body into validated rows plus rejects.
//
// Streamed rather than unmarshalled whole: memory stays proportional to one
// event, so --max-body can be generous without the process being at the mercy of
// a single request.
func (s *Server) decodeEvents(body io.Reader, arrayMode bool) ([]model.RawEvent, []rejectOut, error) {
	dec := json.NewDecoder(body)
	dec.UseNumber()

	if arrayMode {
		tok, err := dec.Token()
		if err != nil {
			return nil, nil, fmt.Errorf("expected a JSON array: %w", err)
		}
		if d, ok := tok.(json.Delim); !ok || d != '[' {
			return nil, nil, fmt.Errorf("expected a JSON array, got %v", tok)
		}
	}

	var (
		rows    []model.RawEvent
		rejects []rejectOut
		index   uint64
	)
	for {
		if arrayMode && !dec.More() {
			break
		}
		var we wireEvent
		if err := dec.Decode(&we); err != nil {
			if errors.Is(err, io.EOF) && !arrayMode {
				break
			}
			return nil, nil, fmt.Errorf("event %d: %w", index+1, err)
		}
		index++
		if int(index) > s.opts.MaxRows {
			return nil, nil, errTooManyRows
		}
		ev, rj := validate(&we)
		if rj != nil {
			rj.Index = index
			rejects = append(rejects, *rj)
			continue
		}
		rows = append(rows, *ev)
	}
	return rows, rejects, nil
}

// validate converts a wire event into a row, or explains why it cannot.
//
// The checks and their reason codes mirror csvsrc.EventReader.Next exactly, so a
// row rejected from a CSV is rejected identically from the API and shows up in
// ingest_rejects under the same reason. Note what is NOT here: no case folding,
// no event classification, no empty-to-unknown. model.RawEvent is source-faithful
// and every normalization rule lives in events_raw_to_clean_mv so all producers
// get identical results by construction.
func validate(we *wireEvent) (*model.RawEvent, *rejectOut) {
	reject := func(reason, detail string) *rejectOut {
		return &rejectOut{Reason: reason, Detail: detail}
	}

	sessionID, err := csvsrc.NormalizeHexID(we.VideoSessionID)
	if err != nil {
		return nil, reject(csvsrc.ReasonBadSessionID, err.Error())
	}
	userID, err := csvsrc.NormalizeHexID(we.UserID)
	if err != nil {
		return nil, reject(csvsrc.ReasonBadUserID, err.Error())
	}
	contentID, err := csvsrc.ParseContentID(we.ContentID.String())
	if err != nil {
		return nil, reject(csvsrc.ReasonBadContentID, err.Error())
	}
	eventTS, err := csvsrc.ParseEpochMillis(we.EventTimestamp.String())
	if err != nil {
		return nil, reject(csvsrc.ReasonBadTimestamp, "event_timestamp: "+err.Error())
	}
	sessionStart, err := csvsrc.ParseEpochMillis(we.SessionStartEpoch.String())
	if err != nil {
		return nil, reject(csvsrc.ReasonBadTimestamp, "session_start_epoch: "+err.Error())
	}

	return &model.RawEvent{
		SourceFile:        SourceLabel,
		VideoSessionID:    sessionID,
		UserID:            userID,
		ContentID:         contentID,
		EventType:         we.EventType,
		Event:             we.Event,
		EventTimestamp:    eventTS,
		SessionStartEpoch: sessionStart,
		Platform:          we.Platform,
		AppVersion:        we.AppVersion,
		Country:           we.Country,
		AudioLanguage:     we.AudioLanguage,
		SubtitleLanguage:  we.SubtitleLanguage,
		PlayerVersion:     we.PlayerVersion,
	}, nil
}

// chunk cuts rows into insert-sized pieces, in order.
//
// Order and size both matter. chx.Loader stamps BatchRowSeq from the row's index
// WITHIN its chunk, and 003_events_clean.sql packs that into row_version as
// (ingest_millis << 20) | seq — so a chunk larger than 1,048,575 rows would
// overflow the sequence into the millisecond field and silently corrupt conflict
// resolution. Cutting at BatchSize (default 50,000) keeps seq two orders of
// magnitude clear of that, and MaxRows bounds the request besides.
func chunk(rows []model.RawEvent, size int) []*chx.Chunk {
	if size <= 0 {
		size = DefaultBatchSize
	}
	out := make([]*chx.Chunk, 0, (len(rows)+size-1)/size)
	for i, ord := 0, uint32(0); i < len(rows); i, ord = i+size, ord+1 {
		out = append(out, &chx.Chunk{Ordinal: ord, Rows: rows[i:min(i+size, len(rows))]})
	}
	return out
}
