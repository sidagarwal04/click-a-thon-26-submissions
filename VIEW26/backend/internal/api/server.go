package api

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
	"github.com/view26/featurelens/internal/langfuse"
	"github.com/view26/featurelens/internal/orchestrator"
)

type langfuseService interface {
	Enabled() bool
	TraceInsights(context.Context, string) (langfuse.TraceInsights, error)
	CreateFeedback(context.Context, langfuse.FeedbackRequest) ([]langfuse.Score, error)
}

type Server struct {
	orchestrator *orchestrator.Orchestrator
	langfuse     langfuseService
	startedAt    time.Time
}

type Option func(*Server)

func WithLangfuse(service langfuseService) Option {
	return func(server *Server) { server.langfuse = service }
}

func New(orchestrator *orchestrator.Orchestrator, options ...Option) http.Handler {
	server := &Server{orchestrator: orchestrator, startedAt: time.Now().UTC()}
	for _, option := range options {
		option(server)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", server.health)
	mux.HandleFunc("GET /api/runs", server.listRuns)
	mux.HandleFunc("POST /api/runs", server.startRun)
	mux.HandleFunc("GET /api/runs/{id}", server.getRun)
	mux.HandleFunc("POST /api/runs/{id}/approve", server.approveRun)
	mux.HandleFunc("POST /api/runs/{id}/refresh-analytics", server.refreshRunAnalytics)
	mux.HandleFunc("GET /api/runs/{id}/events", server.runEvents)
	mux.HandleFunc("GET /api/context/latest", server.latestContext)
	mux.HandleFunc("GET /api/context/changelog", server.contextChangelog)
	mux.HandleFunc("GET /api/context/{version}", server.getContext)
	mux.HandleFunc("GET /api/context/{from}/diff/{to}", server.contextDiff)
	mux.HandleFunc("GET /api/catalog", server.catalog)
	mux.HandleFunc("POST /api/questions", server.ask)
	mux.HandleFunc("POST /api/conversations", server.converse)
	mux.HandleFunc("GET /api/traces/{id}/langfuse", server.langfuseTrace)
	mux.HandleFunc("POST /api/traces/{id}/feedback", server.langfuseFeedback)
	mux.HandleFunc("POST /api/admin/reset", server.reset)
	mux.HandleFunc("POST /mcp", server.mcp)
	return recoverMiddleware(corsMiddleware(mux))
}

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	latest := s.orchestrator.Store().LatestContext()
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok", "service": "featurelens-go", "context_version": latest.Version,
		"analytics_agent": s.orchestrator.AnalyticsStatus(),
		"tracing":         s.orchestrator.TracingStatus(),
		"uptime_seconds":  int(time.Since(s.startedAt).Seconds()),
	})
}

func (s *Server) listRuns(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"runs": s.orchestrator.Store().ListRuns()})
}

func (s *Server) startRun(w http.ResponseWriter, r *http.Request) {
	var input domain.FeatureInput
	if err := decodeJSON(r, &input); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	run, err := s.orchestrator.Start(r.Context(), input)
	if err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	writeJSON(w, http.StatusAccepted, run)
}

func (s *Server) getRun(w http.ResponseWriter, r *http.Request) {
	run, ok := s.orchestrator.Store().GetRun(r.PathValue("id"))
	if !ok {
		writeError(w, http.StatusNotFound, fmt.Errorf("run not found"))
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (s *Server) approveRun(w http.ResponseWriter, r *http.Request) {
	runID := r.PathValue("id")
	before, _ := s.orchestrator.Store().GetRun(runID)
	if err := s.orchestrator.Approve(runID); err != nil {
		writeError(w, http.StatusConflict, err)
		return
	}
	after, _ := s.orchestrator.Store().GetRun(runID)
	writeJSON(w, http.StatusAccepted, map[string]any{
		"approved":         true,
		"already_approved": before.Stage != domain.StageAwaitingApproval,
		"run_id":           runID,
		"stage":            after.Stage,
	})
}

func (s *Server) refreshRunAnalytics(w http.ResponseWriter, r *http.Request) {
	run, err := s.orchestrator.RefreshAnalytics(r.Context(), r.PathValue("id"))
	if err != nil {
		status := http.StatusConflict
		if strings.Contains(err.Error(), "not found") {
			status = http.StatusNotFound
		} else if strings.Contains(err.Error(), "persist") {
			status = http.StatusInternalServerError
		}
		writeError(w, status, err)
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (s *Server) runEvents(w http.ResponseWriter, r *http.Request) {
	if _, ok := s.orchestrator.Store().GetRun(r.PathValue("id")); !ok {
		writeError(w, http.StatusNotFound, fmt.Errorf("run not found"))
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeError(w, http.StatusInternalServerError, fmt.Errorf("streaming unsupported"))
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	for _, event := range s.orchestrator.Store().Events(r.PathValue("id")) {
		writeSSE(w, event)
	}
	flusher.Flush()
	stream, cancel := s.orchestrator.Store().Subscribe(r.PathValue("id"))
	defer cancel()
	for {
		select {
		case <-r.Context().Done():
			return
		case event, open := <-stream:
			if !open {
				return
			}
			writeSSE(w, event)
			flusher.Flush()
			if event.Stage == domain.StageCompleted || event.Stage == domain.StageFailed {
				return
			}
		}
	}
}

func (s *Server) latestContext(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, s.orchestrator.Store().LatestContext())
}

func (s *Server) getContext(w http.ResponseWriter, r *http.Request) {
	version, err := strconv.Atoi(r.PathValue("version"))
	if err != nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("invalid context version"))
		return
	}
	graph, ok := s.orchestrator.Store().Context(version)
	if !ok {
		writeError(w, http.StatusNotFound, fmt.Errorf("context v%d not found", version))
		return
	}
	writeJSON(w, http.StatusOK, graph)
}

func (s *Server) contextDiff(w http.ResponseWriter, r *http.Request) {
	from, err := strconv.Atoi(r.PathValue("from"))
	if err != nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("invalid from version"))
		return
	}
	to, err := strconv.Atoi(r.PathValue("to"))
	if err != nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("invalid to version"))
		return
	}
	diff, err := s.diff(from, to)
	if err != nil {
		writeError(w, http.StatusNotFound, err)
		return
	}
	writeJSON(w, http.StatusOK, diff)
}

func (s *Server) catalog(w http.ResponseWriter, r *http.Request) {
	catalog, err := s.orchestrator.Catalog(r.Context())
	if err != nil {
		writeError(w, http.StatusBadGateway, err)
		return
	}
	writeJSON(w, http.StatusOK, catalog)
}

func (s *Server) ask(w http.ResponseWriter, r *http.Request) {
	var request domain.QuestionRequest
	if err := decodeJSON(r, &request); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	answer, err := s.orchestrator.Ask(r.Context(), request)
	if err != nil {
		writeError(w, http.StatusUnprocessableEntity, err)
		return
	}
	writeJSON(w, http.StatusOK, answer)
}

func (s *Server) converse(w http.ResponseWriter, r *http.Request) {
	var request domain.ConversationRequest
	if err := decodeJSON(r, &request); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	answer, err := s.orchestrator.Converse(r.Context(), request)
	if err != nil {
		writeError(w, http.StatusUnprocessableEntity, err)
		return
	}
	writeJSON(w, http.StatusOK, answer)
}

func (s *Server) langfuseTrace(w http.ResponseWriter, r *http.Request) {
	traceID := strings.ToLower(strings.TrimSpace(r.PathValue("id")))
	if !validHexID(traceID, 32) {
		writeError(w, http.StatusBadRequest, fmt.Errorf("trace id must be 32 hexadecimal characters"))
		return
	}
	if s.langfuse == nil || !s.langfuse.Enabled() {
		writeJSON(w, http.StatusOK, langfuse.TraceInsights{
			Enabled: false, Status: "disabled", TraceID: traceID,
			Observations: []langfuse.Observation{}, Scores: []langfuse.Score{}, FetchedAt: time.Now().UTC(),
		})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
	defer cancel()
	insights, err := s.langfuse.TraceInsights(ctx, traceID)
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Errorf("Langfuse insights unavailable: %w", err))
		return
	}
	writeJSON(w, http.StatusOK, insights)
}

func (s *Server) langfuseFeedback(w http.ResponseWriter, r *http.Request) {
	traceID := strings.ToLower(strings.TrimSpace(r.PathValue("id")))
	if !validHexID(traceID, 32) {
		writeError(w, http.StatusBadRequest, fmt.Errorf("trace id must be 32 hexadecimal characters"))
		return
	}
	if s.langfuse == nil || !s.langfuse.Enabled() {
		writeError(w, http.StatusServiceUnavailable, langfuse.ErrDisabled)
		return
	}
	var request struct {
		Helpful       *bool  `json:"helpful"`
		Issue         string `json:"issue,omitempty"`
		Comment       string `json:"comment,omitempty"`
		ObservationID string `json:"observation_id,omitempty"`
	}
	if err := decodeJSON(r, &request); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if request.Helpful == nil {
		writeError(w, http.StatusBadRequest, fmt.Errorf("helpful is required"))
		return
	}
	request.Issue = strings.ToLower(strings.TrimSpace(request.Issue))
	allowedIssues := map[string]bool{"": true, "wrong_answer": true, "missing_context": true, "bad_sql": true, "unclear": true, "other": true}
	if !allowedIssues[request.Issue] {
		writeError(w, http.StatusBadRequest, fmt.Errorf("unsupported issue category"))
		return
	}
	request.Comment = strings.TrimSpace(request.Comment)
	if len([]rune(request.Comment)) > 500 {
		writeError(w, http.StatusBadRequest, fmt.Errorf("comment must be 500 characters or fewer"))
		return
	}
	request.ObservationID = strings.ToLower(strings.TrimSpace(request.ObservationID))
	if request.ObservationID != "" && !validHexID(request.ObservationID, 16) {
		writeError(w, http.StatusBadRequest, fmt.Errorf("observation id must be 16 hexadecimal characters"))
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()
	insights, err := s.langfuse.TraceInsights(ctx, traceID)
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Errorf("could not verify Langfuse trace: %w", err))
		return
	}
	if len(insights.Observations) == 0 {
		writeError(w, http.StatusConflict, fmt.Errorf("trace is still syncing to Langfuse"))
		return
	}
	if request.ObservationID != "" && !containsObservation(insights.Observations, request.ObservationID) {
		writeError(w, http.StatusBadRequest, fmt.Errorf("observation does not belong to this trace"))
		return
	}
	scores, err := s.langfuse.CreateFeedback(ctx, langfuse.FeedbackRequest{
		TraceID: traceID, ObservationID: request.ObservationID, Helpful: *request.Helpful,
		Issue: request.Issue, Comment: request.Comment, Actor: "product_manager",
	})
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Errorf("save Langfuse feedback: %w", err))
		return
	}
	writeJSON(w, http.StatusCreated, map[string]any{"saved": true, "scores": scores})
}

func (s *Server) reset(w http.ResponseWriter, r *http.Request) {
	var request struct {
		Confirmation string `json:"confirmation"`
	}
	if err := decodeJSON(r, &request); err != nil {
		writeError(w, http.StatusBadRequest, err)
		return
	}
	if request.Confirmation != "RESET_CONTEXT" {
		writeError(w, http.StatusBadRequest, fmt.Errorf("confirmation must be RESET_CONTEXT"))
		return
	}
	baseline, err := s.orchestrator.Reset(r.Context())
	if err != nil {
		writeError(w, http.StatusConflict, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"reset":           true,
		"context_version": baseline.Version,
		"context":         baseline,
		"preserved": map[string]any{
			"source_database":      true,
			"feature_event_tables": true,
		},
	})
}

func (s *Server) diff(fromVersion, toVersion int) (domain.ContextDiff, error) {
	from, ok := s.orchestrator.Store().Context(fromVersion)
	if !ok {
		return domain.ContextDiff{}, fmt.Errorf("context v%d not found", fromVersion)
	}
	to, ok := s.orchestrator.Store().Context(toVersion)
	if !ok {
		return domain.ContextDiff{}, fmt.Errorf("context v%d not found", toVersion)
	}
	return agent.DiffContexts(from, to), nil
}

// contextChangelog walks every stored context version and summarizes the
// delta each one introduced over its parent — the version timeline that
// powers the "context changes over time" visualization.
func (s *Server) contextChangelog(w http.ResponseWriter, _ *http.Request) {
	contexts := s.orchestrator.Store().ListContexts()
	byVersion := make(map[int]domain.ContextVersion, len(contexts))
	for _, graph := range contexts {
		byVersion[graph.Version] = graph
	}
	entries := make([]map[string]any, 0, len(contexts))
	for _, graph := range contexts {
		entry := map[string]any{
			"version":        graph.Version,
			"parent_version": graph.ParentVersion,
			"feature":        graph.Feature,
			"state":          graph.State,
			"summary":        graph.Summary,
			"node_count":     len(graph.Nodes),
			"edge_count":     len(graph.Edges),
			"conflict_count": len(graph.Conflicts),
			"trace_id":       graph.TraceID,
			"created_at":     graph.CreatedAt,
		}
		if parent, ok := byVersion[graph.ParentVersion]; ok {
			diff := agent.DiffContexts(parent, graph)
			entry["added_node_count"] = len(diff.AddedNodes)
			entry["changed_node_count"] = len(diff.ChangedNodes)
			entry["added_edge_count"] = len(diff.AddedEdges)
			entry["added_conflict_count"] = len(diff.AddedConflicts)
			entry["changed_conflict_count"] = len(diff.ChangedConflicts)
			entry["removed_node_keys"] = diff.RemovedNodeKeys
		}
		entries = append(entries, entry)
	}
	writeJSON(w, http.StatusOK, map[string]any{"changelog": entries, "latest_version": s.orchestrator.Store().LatestContext().Version})
}

type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      any             `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
}

func (s *Server) mcp(w http.ResponseWriter, r *http.Request) {
	var request rpcRequest
	if err := decodeJSON(r, &request); err != nil {
		writeRPCError(w, nil, -32700, err.Error())
		return
	}
	switch request.Method {
	case "initialize":
		writeRPC(w, request.ID, map[string]any{
			"protocolVersion": "2025-06-18",
			"capabilities":    map[string]any{"tools": map[string]any{"listChanged": false}},
			"serverInfo":      map[string]any{"name": "featurelens", "version": "0.1.0"},
		})
	case "notifications/initialized":
		w.WriteHeader(http.StatusAccepted)
	case "tools/list":
		writeRPC(w, request.ID, map[string]any{"tools": mcpTools()})
	case "tools/call":
		s.mcpCall(w, r, request)
	default:
		writeRPCError(w, request.ID, -32601, "method not found")
	}
}

func (s *Server) mcpCall(w http.ResponseWriter, r *http.Request, request rpcRequest) {
	var params struct {
		Name      string          `json:"name"`
		Arguments json.RawMessage `json:"arguments"`
	}
	if err := json.Unmarshal(request.Params, &params); err != nil {
		writeRPCError(w, request.ID, -32602, err.Error())
		return
	}
	var result any
	var err error
	switch params.Name {
	case "submit_feature":
		var input domain.FeatureInput
		err = json.Unmarshal(params.Arguments, &input)
		if err == nil {
			result, err = s.orchestrator.Start(r.Context(), input)
		}
	case "get_feature_run":
		var args struct {
			RunID string `json:"run_id"`
		}
		err = json.Unmarshal(params.Arguments, &args)
		if err == nil {
			var ok bool
			result, ok = s.orchestrator.Store().GetRun(args.RunID)
			if !ok {
				err = fmt.Errorf("run not found")
			}
		}
	case "approve_schema":
		var args struct {
			RunID string `json:"run_id"`
		}
		err = json.Unmarshal(params.Arguments, &args)
		if err == nil {
			err = s.orchestrator.Approve(args.RunID)
			result = map[string]any{"approved": err == nil, "run_id": args.RunID}
		}
	case "ask_business_question":
		var args domain.QuestionRequest
		err = json.Unmarshal(params.Arguments, &args)
		if err == nil {
			result, err = s.orchestrator.Ask(r.Context(), args)
		}
	case "ask_feature_portfolio":
		var args domain.ConversationRequest
		err = json.Unmarshal(params.Arguments, &args)
		if err == nil {
			result, err = s.orchestrator.Converse(r.Context(), args)
		}
	case "get_context_diff":
		var args struct {
			From int `json:"from_version"`
			To   int `json:"to_version"`
		}
		err = json.Unmarshal(params.Arguments, &args)
		if err == nil {
			result, err = s.diff(args.From, args.To)
		}
	case "run_context_evaluations":
		var args struct {
			RunID string `json:"run_id"`
		}
		err = json.Unmarshal(params.Arguments, &args)
		if err == nil {
			run, ok := s.orchestrator.Store().GetRun(args.RunID)
			if !ok {
				err = fmt.Errorf("run not found")
			} else {
				result = map[string]any{"run_id": args.RunID, "evaluations": run.Evaluations}
			}
		}
	default:
		err = fmt.Errorf("unknown tool %q", params.Name)
	}
	if err != nil {
		writeMCPResult(w, request.ID, map[string]any{"error": err.Error()}, true)
		return
	}
	writeMCPResult(w, request.ID, result, false)
}

func mcpTools() []map[string]any {
	object := func(properties map[string]any, required ...string) map[string]any {
		return map[string]any{"type": "object", "properties": properties, "required": required}
	}
	stringField := func(description string) map[string]any {
		return map[string]any{"type": "string", "description": description}
	}
	integerField := func(description string) map[string]any {
		return map[string]any{"type": "integer", "description": description}
	}
	stringArrayField := func(description string) map[string]any {
		return map[string]any{"type": "array", "description": description, "items": map[string]any{"type": "string"}}
	}
	return []map[string]any{
		{"name": "submit_feature", "description": "Start an approval-gated feature evolution run from a Markdown spec and NDJSON event sample.", "inputSchema": object(map[string]any{"name": stringField("Feature name"), "slug": stringField("Optional stable slug"), "schema_version": integerField("Optional positive schema version; defaults to 1"), "spec_markdown": stringField("Feature specification"), "events_ndjson": stringField("One JSON event per line"), "role": stringField("Question role; defaults to product_manager"), "auto_approve": map[string]any{"type": "boolean"}}, "name", "spec_markdown", "events_ndjson")},
		{"name": "get_feature_run", "description": "Read the stage, proposal, context, insight, and evaluations for a run.", "inputSchema": object(map[string]any{"run_id": stringField("Run identifier")}, "run_id")},
		{"name": "approve_schema", "description": "Approve a validated schema proposal before any ClickHouse write.", "inputSchema": object(map[string]any{"run_id": stringField("Run identifier")}, "run_id")},
		{"name": "ask_business_question", "description": "Ask a role-aware business question through the latest published context graph. Pinning an older context_version requires allow_stale and stamps the answer with a staleness warning.", "inputSchema": object(map[string]any{"role": stringField("Business role"), "feature": stringField("Feature name or slug"), "question": stringField("Business question"), "context_version": integerField("Optional pinned context version; must be the latest unless allow_stale is true"), "allow_stale": map[string]any{"type": "boolean", "description": "Explicitly allow answering from a pinned historical context version"}}, "question")},
		{"name": "ask_feature_portfolio", "description": "Ask across published features using the latest published context, preserve an optional prior feature scope, and return governed charts, source evidence, follow-up prompts, and a complete trace. Pinning an older context_version requires allow_stale.", "inputSchema": object(map[string]any{"role": stringField("Business role"), "question": stringField("Business question or contextual follow-up"), "features": stringArrayField("Optional explicit feature scope"), "active_features": stringArrayField("Feature scope returned by the previous answer"), "context_version": integerField("Optional pinned context version; must be the latest unless allow_stale is true"), "allow_stale": map[string]any{"type": "boolean", "description": "Explicitly allow answering from a pinned historical context version"}}, "question")},
		{"name": "get_context_diff", "description": "Inspect ontology nodes and edges added between two immutable context versions.", "inputSchema": object(map[string]any{"from_version": integerField("Parent context version"), "to_version": integerField("Child context version")}, "from_version", "to_version")},
		{"name": "run_context_evaluations", "description": "Read the before/after, grounding, role-awareness, and regression evaluation suite for a run.", "inputSchema": object(map[string]any{"run_id": stringField("Run identifier")}, "run_id")},
	}
}

func writeMCPResult(w http.ResponseWriter, id, value any, isError bool) {
	encoded, _ := json.MarshalIndent(value, "", "  ")
	writeRPC(w, id, map[string]any{
		"content":           []map[string]any{{"type": "text", "text": string(encoded)}},
		"structuredContent": value,
		"isError":           isError,
	})
}

func writeRPC(w http.ResponseWriter, id, result any) {
	writeJSON(w, http.StatusOK, map[string]any{"jsonrpc": "2.0", "id": id, "result": result})
}

func writeRPCError(w http.ResponseWriter, id any, code int, message string) {
	writeJSON(w, http.StatusOK, map[string]any{"jsonrpc": "2.0", "id": id, "error": map[string]any{"code": code, "message": message}})
}

func writeSSE(w http.ResponseWriter, event domain.RunEvent) {
	encoded, _ := json.Marshal(event)
	_, _ = fmt.Fprintf(w, "event: stage\ndata: %s\n\n", encoded)
}

func decodeJSON(r *http.Request, target any) error {
	decoder := json.NewDecoder(io.LimitReader(r.Body, 20<<20))
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func writeError(w http.ResponseWriter, status int, err error) {
	writeJSON(w, status, map[string]any{"error": err.Error()})
}

func validHexID(value string, size int) bool {
	if len(value) != size {
		return false
	}
	for _, character := range value {
		if !((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f')) {
			return false
		}
	}
	return true
}

func containsObservation(observations []langfuse.Observation, observationID string) bool {
	for _, observation := range observations {
		if observation.ID == observationID {
			return true
		}
	}
	return false
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Accept, MCP-Protocol-Version")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				log.Printf("panic: %v", recovered)
				writeError(w, http.StatusInternalServerError, fmt.Errorf("internal server error"))
			}
		}()
		next.ServeHTTP(w, r)
	})
}
