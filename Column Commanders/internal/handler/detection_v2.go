package handler

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/services/detectionv2"
)

type DetectionV2Handler struct {
	pipeline *detectionv2.Pipeline
}

func NewDetectionV2Handler(pipeline *detectionv2.Pipeline) *DetectionV2Handler {
	return &DetectionV2Handler{pipeline: pipeline}
}

type historicalDetectionRequest struct {
	Start       *time.Time `json:"start"`
	End         *time.Time `json:"end"`
	Investigate *bool      `json:"investigate"`
}

type realTimeDetectionRequest struct {
	Anchor      *time.Time `json:"anchor"`
	Investigate *bool      `json:"investigate"`
}

func (h *DetectionV2Handler) Historical(w http.ResponseWriter, r *http.Request) {
	var request historicalDetectionRequest
	if r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
	}
	investigate := true
	if request.Investigate != nil {
		investigate = *request.Investigate
	}
	pipelineRequest := detectionv2.HistoricalRequest{Investigate: investigate}
	if request.Start != nil {
		pipelineRequest.Start = *request.Start
	}
	if request.End != nil {
		pipelineRequest.End = *request.End
	}
	result, err := h.pipeline.RunHistorical(r.Context(), pipelineRequest)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "historical detection failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (h *DetectionV2Handler) RealTime(w http.ResponseWriter, r *http.Request) {
	var request realTimeDetectionRequest
	if r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
	}
	investigate := true
	if request.Investigate != nil {
		investigate = *request.Investigate
	}
	pipelineRequest := detectionv2.RealTimeRequest{Investigate: investigate}
	if request.Anchor != nil {
		pipelineRequest.Anchor = *request.Anchor
	}
	result, err := h.pipeline.RunRealTime(r.Context(), pipelineRequest)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "real-time detection failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (h *DetectionV2Handler) ListEpisodes(w http.ResponseWriter, r *http.Request) {
	episodes, err := h.pipeline.ListEpisodes(r.Context())
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to list episodes")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"episodes": episodes})
}

func (h *DetectionV2Handler) GetEpisode(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(routeID(r, "/api/v2/episodes/"))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid episode id")
		return
	}
	episode, ok, err := h.pipeline.GetEpisode(r.Context(), id)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to get episode")
		return
	}
	if !ok {
		writeError(w, http.StatusNotFound, "episode not found in this service process")
		return
	}
	writeJSON(w, http.StatusOK, episode)
}
