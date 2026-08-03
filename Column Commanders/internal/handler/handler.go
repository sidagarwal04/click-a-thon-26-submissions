package handler

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strings"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/model"
)

// Handler holds dependencies for the core HTTP endpoints.
type Handler struct {
	db           *db.Client
	batchMaxSize int
	logger       *slog.Logger
}

// New creates a Handler.
func New(dbClient *db.Client, cfg *config.Config, logger *slog.Logger) *Handler {
	return &Handler{
		db:           dbClient,
		batchMaxSize: cfg.BatchMaxSize,
		logger:       logger,
	}
}

// Health handles GET /health
func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// routeID supports both net/http patterns and routers such as Gin whose
// path parameters are not copied into Request.PathValue by adapter handlers.
func routeID(r *http.Request, prefix string) string {
	if id := r.PathValue("id"); id != "" {
		return id
	}
	return strings.Trim(strings.TrimPrefix(r.URL.Path, prefix), "/")
}

// Insert handles POST /insert
func (h *Handler) Insert(w http.ResponseWriter, r *http.Request) {
	var req model.InsertRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if req.Event.Source == "" || req.Event.EventType == "" {
		writeError(w, http.StatusBadRequest, "source and event_type are required")
		return
	}
	if err := h.db.BatchInsert(r.Context(), []model.Event{req.Event}); err != nil {
		h.logger.Error("insert failed", slog.Any("error", err))
		writeError(w, http.StatusInternalServerError, "insert failed")
		return
	}
	writeJSON(w, http.StatusCreated, model.InsertResponse{Inserted: 1, Message: "inserted"})
}

// BatchInsert handles POST /batch
func (h *Handler) BatchInsert(w http.ResponseWriter, r *http.Request) {
	var req model.BatchInsertRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request body")
		return
	}
	if len(req.Events) == 0 {
		writeError(w, http.StatusBadRequest, "events array must not be empty")
		return
	}
	if len(req.Events) > h.batchMaxSize {
		writeError(w, http.StatusBadRequest,
			fmt.Sprintf("batch size %d exceeds maximum of %d", len(req.Events), h.batchMaxSize))
		return
	}
	for i, e := range req.Events {
		if e.Source == "" || e.EventType == "" {
			writeError(w, http.StatusBadRequest,
				fmt.Sprintf("event[%d]: source and event_type are required", i))
			return
		}
	}
	if err := h.db.BatchInsert(r.Context(), req.Events); err != nil {
		h.logger.Error("batch insert failed", slog.Any("error", err), slog.Int("count", len(req.Events)))
		writeError(w, http.StatusInternalServerError, "batch insert failed")
		return
	}
	writeJSON(w, http.StatusCreated, model.InsertResponse{
		Inserted: len(req.Events),
		Message:  "batch inserted",
	})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
