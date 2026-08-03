package mock

import (
	"context"
	"crypto/subtle"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/fleet"
)

// The `all:` prefix is REQUIRED, not stylistic. Next's static export contains
// _next/ and __next.*.txt, and go:embed silently skips paths whose base name
// begins with "_" or ".". Without `all:` the binary compiles, serves index.html,
// and the page renders blank with no JavaScript and no error anywhere.
//
//go:embed all:web
var webFS embed.FS

// Server serves the dashboards and their control API.
type Server struct {
	client     *chx.Client
	runner     *Runner
	manual     *Manual
	fleet      *fleet.Fleet
	token      string
	corsOrigin string
	timeoutMS  int64
}

// NewServer wires the dashboards over one ClickHouse client.
//
// timeoutMS is the liveness lease the stepper evaluates against. It must match
// whatever the pipeline runs with, or the dashboard would show a different
// notion of "active" from the served answer.
// corsOrigin, when non-empty, is the single origin allowed to call /api/. It
// exists for `next dev`: the dashboard runs on :3000 while this serves :8088, and
// next.config rewrites cannot bridge them because rewrites are unsupported under
// output: 'export'. Empty in production, where the exported files are served from
// this same binary and the API is same-origin.
func NewServer(client *chx.Client, token, corsOrigin, selfURL string, timeoutMS int64) *Server {
	runner := NewRunner(client, selfURL, token)
	s := &Server{
		client:     client,
		runner:     runner,
		manual:     NewManual(client, timeoutMS),
		token:      token,
		corsOrigin: corsOrigin,
		timeoutMS:  timeoutMS,
	}
	// The fleet evaluates the same lease the stepper and the pipeline do. Passing
	// timeoutMS rather than a constant is what keeps its graph comparable to
	// ClickHouse's: a mismatch here would show up as a permanent gap between the two
	// lines that has nothing to do with either implementation being wrong.
	s.fleet = fleet.New(
		&fleetSink{client: client, runner: runner, runID: uuid.New()},
		&fleetStore{client: client},
		time.Duration(timeoutMS)*time.Millisecond,
		time.Now().UnixNano(),
	)
	return s
}

// Run drives the fleet until ctx is cancelled. Call it once, in a goroutine.
//
// Separate from Handler because the fleet keeps emitting events whether or not
// anyone is looking at the dashboard — that is what makes it a simulator rather
// than a UI.
func (s *Server) Run(ctx context.Context) { s.fleet.Run(ctx) }

// ReconcileFleet restores persisted sessions and catches them up. Call before Run.
//
// A failure here is reported, not fatal. The fleet still works from empty, and
// refusing to start the whole dashboard because a bookkeeping table is unreadable
// would trade a degraded feature for an outage.
func (s *Server) ReconcileFleet(ctx context.Context) (int, error) {
	return s.fleet.Reconcile(ctx)
}

// Handler builds the route table.
// UseExternalAPI points "api"-sink load runs at a sonyliv-api endpoint rather
// than at this process's own /api/events.
func (s *Server) UseExternalAPI(url, token string, insecure bool) {
	s.runner.UseExternalAPI(url, token, insecure)
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	// readyz touches ClickHouse; healthz deliberately does not. A liveness probe
	// that fails when a dependency blips restarts a process that was fine.
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
		defer cancel()
		if err := s.client.Conn.Ping(ctx); err != nil {
			http.Error(w, "clickhouse unreachable: "+err.Error(), http.StatusServiceUnavailable)
			return
		}
		_, _ = w.Write([]byte("ready\n"))
	})

	// The Next.js static export, served from the embedded FS. FileServerFS
	// resolves "/" and "/manual/" to their index.html, which is why the export
	// sets trailingSlash: true.
	//
	// Registered as a bare "/" subtree pattern with no method, so it does not
	// conflict with the "/api/" subtree below — a method-qualified "GET /" would,
	// because it is a catch-all for every GET path.
	sub, err := fs.Sub(webFS, "web")
	if err != nil {
		panic("embedded web assets missing: " + err.Error())
	}
	mux.Handle("/", http.FileServerFS(sub))

	api := http.NewServeMux()
	// The ingest endpoint. Separate from the generator's control endpoints below:
	// this one RECEIVES events from any producer, those START and STOP the
	// generator. With Params.Sink = "api" the generator becomes a client of this.
	api.HandleFunc("POST /api/events", s.handleEvents)

	api.HandleFunc("GET /api/content", s.handleContent)
	api.HandleFunc("POST /api/sim/start", s.handleSimStart)
	api.HandleFunc("POST /api/sim/stop", s.handleSimStop)
	api.HandleFunc("GET /api/sim", s.handleSimStatus)
	api.HandleFunc("GET /api/curve", s.handleCurve)
	api.HandleFunc("POST /api/manual/session", s.handleManualNew)
	api.HandleFunc("GET /api/manual/sessions", s.handleManualList)
	api.HandleFunc("POST /api/manual/event", s.handleManualEvent)
	api.HandleFunc("GET /api/manual/session/{vsid}", s.handleManualState)

	// The fleet: a controllable population of autonomously ticking sessions.
	api.HandleFunc("POST /api/fleet/sessions", s.handleFleetCreate)
	api.HandleFunc("GET /api/fleet/sessions", s.handleFleetList)
	api.HandleFunc("GET /api/fleet/sessions/{id}", s.handleFleetGet)
	api.HandleFunc("POST /api/fleet/sessions/{id}/command", s.handleFleetCommand)
	api.HandleFunc("POST /api/fleet/bulk", s.handleFleetBulk)
	api.HandleFunc("POST /api/fleet/clear-ended", s.handleFleetClearEnded)
	api.HandleFunc("GET /api/fleet/stats", s.handleFleetStats)
	api.HandleFunc("GET /api/fleet/dimensions", s.handleFleetDimensions)
	api.HandleFunc("GET /api/fleet/curve", s.handleFleetCurve)

	mux.Handle("/api/", s.cors(s.auth(api)))
	return mux
}

// cors permits exactly one configured origin, and only when configured.
//
// Not a wildcard: this endpoint writes to ClickHouse, so any page in any tab
// could otherwise drive it. A single explicit origin keeps the dev convenience
// without turning production into an open write surface.
func (s *Server) cors(next http.Handler) http.Handler {
	if s.corsOrigin == "" {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Origin") == s.corsOrigin {
			w.Header().Set("Access-Control-Allow-Origin", s.corsOrigin)
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Vary", "Origin")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// auth gates the control API behind a shared token when one is configured.
//
// subtle.ConstantTimeCompare rather than ==: this is a secret comparison, and a
// length-or-prefix-dependent early return leaks information about it.
func (s *Server) auth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if s.token != "" {
			got := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
			if subtle.ConstantTimeCompare([]byte(got), []byte(s.token)) != 1 {
				http.Error(w, "unauthorized", http.StatusUnauthorized)
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("write json: %v", err)
	}
}

func writeErr(w http.ResponseWriter, code int, err error) {
	writeJSON(w, code, map[string]string{"error": err.Error()})
}

func (s *Server) handleContent(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	items, err := s.client.SearchContent(r.Context(), r.URL.Query().Get("q"), limit)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": items})
}

func (s *Server) handleSimStart(w http.ResponseWriter, r *http.Request) {
	var p Params
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&p); err != nil {
		writeErr(w, http.StatusBadRequest, fmt.Errorf("decode params: %w", err))
		return
	}
	if p.Concurrency <= 0 {
		writeErr(w, http.StatusBadRequest, errors.New("concurrency must be at least 1"))
		return
	}
	st, err := s.runner.Start(r.Context(), p)
	switch {
	case errors.Is(err, ErrRunInFlight):
		writeErr(w, http.StatusConflict, err)
		return
	case err != nil:
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	writeJSON(w, http.StatusOK, st)
}

func (s *Server) handleSimStop(w http.ResponseWriter, _ *http.Request) {
	stopped := s.runner.Stop()
	st := s.runner.Status()
	writeJSON(w, http.StatusOK, map[string]any{"stopped": stopped, "status": st})
}

func (s *Server) handleSimStatus(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, s.runner.Status())
}

func (s *Server) handleCurve(w http.ResponseWriter, r *http.Request) {
	minutes, _ := strconv.Atoi(r.URL.Query().Get("minutes"))
	points, err := Curve(r.Context(), s.client, minutes)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"points": points,
		// Surfaced in the payload, not just the page, so an API consumer cannot
		// mistake this for served concurrency. On the tuning extract the
		// lease estimate peaks 37% above the exact answer.
		"estimator": "heartbeat-lease approximation, not exact concurrency",
	})
}

type manualNewReq struct {
	ContentID  int64  `json:"content_id"`
	Title      string `json:"title"`
	VideoType  string `json:"video_type"`
	Platform   string `json:"platform"`
	AppVersion string `json:"app_version"`
	Country    string `json:"country"`
}

func (s *Server) handleManualNew(w http.ResponseWriter, r *http.Request) {
	var req manualNewReq
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<16)).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	if req.ContentID == 0 {
		writeErr(w, http.StatusBadRequest, errors.New("content_id is required — pick from the catalogue"))
		return
	}
	if req.Platform == "" {
		req.Platform = "ANDROID_PHONE"
	}
	if req.AppVersion == "" {
		req.AppVersion = "6.34.8"
	}
	if req.Country == "" {
		req.Country = "india"
	}
	sess := s.manual.NewSession(
		chx.ContentInfo{ContentID: req.ContentID, Title: req.Title, VideoType: req.VideoType},
		req.Platform, req.AppVersion, req.Country)
	writeJSON(w, http.StatusOK, sess)
}

func (s *Server) handleManualList(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"sessions": s.manual.Sessions()})
}

type manualEventReq struct {
	Session        string `json:"session"`
	Action         Action `json:"action"`
	AdvanceSeconds int    `json:"advance_seconds"`
}

func (s *Server) handleManualEvent(w http.ResponseWriter, r *http.Request) {
	var req manualEventReq
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<16)).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	sess, err := s.manual.Send(r.Context(), req.Session, req.Action,
		time.Duration(req.AdvanceSeconds)*time.Second)
	if err != nil {
		writeErr(w, http.StatusBadRequest, err)
		return
	}
	// Return the derived state alongside, so one click is one round trip: the UI
	// never has to guess what the event did.
	state, err := s.sessionState(r.Context(), sess)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, state)
}

func (s *Server) handleManualState(w http.ResponseWriter, r *http.Request) {
	vsid := r.PathValue("vsid")
	sess, ok := s.manual.Session(vsid)
	if !ok {
		writeErr(w, http.StatusNotFound, fmt.Errorf("unknown session %s", vsid))
		return
	}
	state, err := s.sessionState(r.Context(), sess)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err)
		return
	}
	writeJSON(w, http.StatusOK, state)
}

type sessionStateResp struct {
	Session   *ManualSession `json:"session"`
	Timeline  []TimelineRow  `json:"timeline"`
	Intervals []Interval     `json:"intervals"`
	ActiveMS  int64          `json:"active_ms"`
	TimeoutMS int64          `json:"timeout_ms"`
}

func (s *Server) sessionState(ctx context.Context, sess *ManualSession) (*sessionStateResp, error) {
	timeline, err := Timeline(ctx, s.client, sess.VideoSessionID, s.timeoutMS)
	if err != nil {
		return nil, err
	}
	intervals, err := Intervals(ctx, s.client, sess.VideoSessionID, s.timeoutMS, sess.Clock)
	if err != nil {
		return nil, err
	}
	var activeMS int64
	for _, iv := range intervals {
		activeMS += iv.End.Sub(iv.Start).Milliseconds()
	}
	return &sessionStateResp{
		Session:   sess,
		Timeline:  timeline,
		Intervals: intervals,
		ActiveMS:  activeMS,
		TimeoutMS: s.timeoutMS,
	}, nil
}

// StopRun cancels any in-flight load run, for shutdown.
func (s *Server) StopRun() { s.runner.Stop() }
