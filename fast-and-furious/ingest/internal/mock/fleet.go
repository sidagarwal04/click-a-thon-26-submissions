package mock

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/fleet"
	"github.com/sonyliv-clickathon/ingest/internal/model"
)

// fleetSink writes the fleet's batches through the existing insert paths.
//
// It resolves its destination per call rather than at construction, because
// UseExternalAPI runs after NewServer: binding the destination early would pin the
// fleet to the direct loader even when the process was told to produce through
// sonyliv-api.
type fleetSink struct {
	client *chx.Client
	runner *Runner
	runID  uuid.UUID
}

// Send writes one batch, synchronously, returning the write error.
//
// A fresh Loader per batch rather than one long-lived Loader fed by a channel: a
// channel-fed loader reports errors only when it finally returns, so a failing
// ClickHouse would look like a fleet that is writing fine. One per batch is once
// per second, not once per event — the trap internal/mock/manual.go documents.
//
// The Fingerprint is derived from the rows, and that is load-bearing. Loader's
// token is source|fingerprint|bs|n|ordinal, so a constant fingerprint with ordinal
// always 0 would make every batch's token identical and ClickHouse would silently
// deduplicate away every batch after the first. Hashing the rows makes distinct
// batches distinct while an identical resend still deduplicates — the idempotency
// we want.
func (fs *fleetSink) Send(ctx context.Context, rows []model.RawEvent) error {
	if len(rows) == 0 {
		return nil
	}
	var dest sink
	if url, token, insecure, ok := fs.runner.apiEndpoint(); ok {
		dest = NewAPISink(url, token, insecure)
	} else {
		dest = chx.NewLoader(fs.client, chx.LoaderOptions{
			Source:      "fleet",
			RunID:       fs.runID,
			Fingerprint: rowsFingerprint(rows),
			BatchSize:   len(rows),
			Workers:     1,
			MaxRetries:  3,
			AsyncInsert: true,
		})
	}

	chunks := make(chan *chx.Chunk, 1)
	chunks <- &chx.Chunk{Ordinal: 0, Rows: rows}
	close(chunks)

	if _, err := dest.Run(ctx, chunks); err != nil {
		return fmt.Errorf("fleet write %d rows: %w", len(rows), err)
	}
	return nil
}

// --- HTTP -------------------------------------------------------------------

func fleetFilter(r *http.Request) fleet.Filter {
	q := r.URL.Query()
	cid, _ := strconv.ParseInt(q.Get("content_id"), 10, 64)
	return fleet.Filter{
		ContentID:  cid,
		VideoType:  q.Get("video_type"),
		Platform:   q.Get("platform"),
		AppVersion: q.Get("app_version"),
		Country:    q.Get("country"),
		Phase:      q.Get("phase"),
		Mode:       q.Get("mode"),
	}
}

func (s *Server) handleFleetCreate(w http.ResponseWriter, r *http.Request) {
	var sp fleet.Spec
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<16)).Decode(&sp); err != nil {
		writeErr(w, http.StatusBadRequest, fmt.Errorf("decode spec: %w", err))
		return
	}

	// Resolve video_type from the catalogue rather than trusting the client. It is a
	// filter dimension on both lines of the graph, so a wrong value here would split
	// the comparison for a reason that has nothing to do with the pipeline.
	if sp.ContentID != 0 {
		refs, err := s.client.ContentRefsByID(r.Context(), []int64{sp.ContentID})
		if err != nil {
			writeErr(w, http.StatusInternalServerError, err)
			return
		}
		if len(refs) == 0 {
			writeErr(w, http.StatusBadRequest, fmt.Errorf(
				"content id %d is not in the catalogue — load it first", sp.ContentID))
			return
		}
		sp.VideoType = refs[0].VideoType
	}

	views, rows, err := s.fleet.Create(sp, time.Now().UTC().Truncate(time.Millisecond))
	if err != nil {
		code := http.StatusBadRequest
		if errors.Is(err, fleet.ErrTooMany) {
			code = http.StatusConflict
		}
		writeErr(w, code, err)
		return
	}
	if err := s.fleet.Emit(r.Context(), rows); err != nil {
		writeErr(w, http.StatusServiceUnavailable, err)
		return
	}
	// Before responding, so the sessions are in fleet_sessions by the time the
	// dashboard's next curve poll scopes itself from that table.
	s.fleet.PersistNow(r.Context())

	// A sample, not the whole batch: 100,000 views is a multi-megabyte body that
	// the create page throws away — it redirects to the listing, which pages.
	sample := views
	if len(sample) > 20 {
		sample = sample[:20]
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"created":  len(views),
		"sessions": sample,
	})
}

func (s *Server) handleFleetList(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	offset, _ := strconv.Atoi(q.Get("offset"))
	limit, _ := strconv.Atoi(q.Get("limit"))

	now := time.Now().UTC()
	sessions, total := s.fleet.List(fleetFilter(r), offset, limit, now)
	writeJSON(w, http.StatusOK, map[string]any{
		"sessions": sessions,
		"total":    total,
		"offset":   offset,
		"stats":    s.fleet.Stats(now),
	})
}

func (s *Server) handleFleetGet(w http.ResponseWriter, r *http.Request) {
	v, ok := s.fleet.Get(r.PathValue("id"), time.Now().UTC())
	if !ok {
		writeErr(w, http.StatusNotFound, fmt.Errorf("unknown session %s", r.PathValue("id")))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"session":    v,
		"timeout_ms": s.timeoutMS,
	})
}

type fleetCommandReq struct {
	Command fleet.Command `json:"command"`
}

func (s *Server) handleFleetCommand(w http.ResponseWriter, r *http.Request) {
	var req fleetCommandReq
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<14)).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	v, rows, err := s.fleet.Command(r.PathValue("id"), req.Command,
		time.Now().UTC().Truncate(time.Millisecond))
	if err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	if err := s.fleet.Emit(r.Context(), rows); err != nil {
		writeErr(w, http.StatusServiceUnavailable, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"session":    v,
		"wrote":      len(rows),
		"timeout_ms": s.timeoutMS,
	})
}

type fleetBulkReq struct {
	Command fleet.Command `json:"command"`
	// IDs is an explicit selection. Ignored when All is set.
	IDs []string `json:"ids"`
	// All applies the command to every session matching the query-string filter,
	// including ones the client has never seen. That is what "select all matching"
	// means when the page holds 50 of 2,000 rows — and evaluating the filter here
	// rather than shipping 2,000 ids also means the set cannot be stale on arrival.
	All bool `json:"all"`
}

// handleFleetBulk applies one command to many sessions.
//
// The filter comes from the query string, through the same fleetFilter helper the
// listing uses, so "respects the current filter" is literally the same parse rather
// than a second one that could drift.
func (s *Server) handleFleetBulk(w http.ResponseWriter, r *http.Request) {
	var req fleetBulkReq
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	if !req.All && len(req.IDs) == 0 {
		writeErr(w, http.StatusBadRequest,
			errors.New(`nothing selected: pass "ids" or "all": true`))
		return
	}

	now := time.Now().UTC().Truncate(time.Millisecond)
	var (
		res  fleet.BulkResult
		rows []model.RawEvent
		err  error
	)
	if req.All {
		res, rows, err = s.fleet.CommandMatching(fleetFilter(r), req.Command, now)
	} else {
		res, rows, err = s.fleet.CommandMany(req.IDs, req.Command, now)
	}
	if err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	if err := s.fleet.Emit(r.Context(), rows); err != nil {
		writeErr(w, http.StatusServiceUnavailable, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"applied": res.Applied,
		"skipped": res.Skipped,
		"unknown": res.Unknown,
		"wrote":   len(rows),
		"stats":   s.fleet.Stats(now),
	})
}

func (s *Server) handleFleetStats(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"stats":      s.fleet.Stats(time.Now().UTC()),
		"writes":     s.fleet.WriteStats(),
		"timeout_ms": s.timeoutMS,
		"max_create": fleet.MaxPerCreate,
		"max_live":   fleet.MaxLive,
	})
}

func (s *Server) handleFleetDimensions(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, s.fleet.Dimensions())
}

func (s *Server) handleFleetClearEnded(w http.ResponseWriter, r *http.Request) {
	// ClearEnded, not RemoveEnded: the store needs tombstones, or the next restart
	// resurrects every session the operator just cleared.
	removed, err := s.fleet.ClearEnded(r.Context())
	if err != nil {
		// 207: the memory side succeeded and the durable side did not, and the
		// count is still worth reporting. A bare 500 would suggest nothing happened.
		writeJSON(w, http.StatusMultiStatus, map[string]any{
			"removed": removed,
			"error":   err.Error(),
		})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"removed": removed})
}

// handleFleetCurve returns both lines: what the fleet recorded, and what the
// pipeline infers from the events it wrote.
//
// A ClickHouse failure does not fail the request. The generator line is computed
// in-process and is still the more useful of the two when the database is
// unreachable — and an empty comparison line with an error beside it says
// "unreachable", where a 500 would say nothing at all.
func (s *Server) handleFleetCurve(w http.ResponseWriter, r *http.Request) {
	minutes, _ := strconv.Atoi(r.URL.Query().Get("minutes"))
	if minutes <= 0 || minutes > 720 {
		minutes = 30
	}
	now := time.Now().UTC()
	from := now.Add(-time.Duration(minutes) * time.Minute)
	f := fleetFilter(r)

	resp := map[string]any{
		"from":       from,
		"to":         now,
		"minutes":    minutes,
		"generator":  s.fleet.Curve(f, from, now, now),
		"timeout_ms": s.timeoutMS,
	}

	// Count only — the scope itself is resolved inside the query, against
	// fleet_sessions. There is no cap and nothing to truncate.
	_, scoped := s.fleet.List(f, 0, 1, now)
	resp["scoped_sessions"] = scoped

	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	points, err := FleetCurve(ctx, s.client, f, from, now, s.timeoutMS)
	if err != nil {
		resp["clickhouse"] = []fleet.CurvePoint{}
		resp["clickhouse_error"] = err.Error()
	} else {
		resp["clickhouse"] = points
	}
	writeJSON(w, http.StatusOK, resp)
}
