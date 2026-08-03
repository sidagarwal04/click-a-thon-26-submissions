package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"clickhouse-go-service/services/alertmanager"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
)

// AnomalyHandler handles all anomaly detection HTTP endpoints.
type AnomalyHandler struct {
	engine   *anomalydetector.DetectionEngine
	alertMgr *alertmanager.Manager
}

// NewAnomalyHandler creates an AnomalyHandler.
func NewAnomalyHandler(engine *anomalydetector.DetectionEngine, alertMgr *alertmanager.Manager) *AnomalyHandler {
	return &AnomalyHandler{engine: engine, alertMgr: alertMgr}
}

// ── Request / Response models ─────────────────────────────────────────────────

type detectRequest struct {
	WindowEnd  *time.Time `json:"window_end"`
	WindowSize string     `json:"window_size"`
	Metric     string     `json:"metric"`
}

type windowResp struct {
	Start    string `json:"start"`
	End      string `json:"end"`
	Duration string `json:"duration"`
	Grain    string `json:"grain"`
}

type anomalyResp struct {
	Metric        string  `json:"metric"`
	DetectorID    string  `json:"detector_id"`
	Dimension     string  `json:"dimension,omitempty"`
	Segment       string  `json:"segment,omitempty"`
	CurrentValue  float64 `json:"current_value"`
	BaselineValue float64 `json:"baseline_value"`
	ZScore        float64 `json:"z_score"`
	CUSUMVal      float64 `json:"cusum_val,omitempty"`
	DeviationPct  string  `json:"deviation_pct"`
	Severity      string  `json:"severity"`
}

type incidentSummary struct {
	ID             string  `json:"id"`
	Metric         string  `json:"metric"`
	DetectorID     string  `json:"detector_id"`
	Dimension      string  `json:"dimension,omitempty"`
	Segment        string  `json:"segment,omitempty"`
	Severity       string  `json:"severity"`
	Status         string  `json:"status"`
	DeviationPct   string  `json:"deviation_pct"`
	ZScore         float64 `json:"z_score"`
	WindowStart    string  `json:"window_start"`
	WindowEnd      string  `json:"window_end"`
	CreatedAt      string  `json:"created_at"`
	DrilldownReady bool    `json:"drilldown_ready"`
}

type detectResponse struct {
	Window          windowResp        `json:"window"`
	AnomalyDetected bool              `json:"anomaly_detected"`
	Anomalies       []anomalyResp     `json:"anomalies"`
	Incidents       []incidentSummary `json:"incidents"`
	ExecutionTimeMs int64             `json:"execution_time_ms"`
}

// ── Handlers ─────────────────────────────────────────────────────────────────

// Detect handles POST /api/v1/detect
func (h *AnomalyHandler) Detect(w http.ResponseWriter, r *http.Request) {
	var req detectRequest
	if r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeError(w, http.StatusBadRequest, "invalid request body")
			return
		}
	}
	windowEnd := time.Time{}
	if req.WindowEnd != nil {
		windowEnd = *req.WindowEnd
	}
	h.runDetect(w, r, windowEnd, req.Metric)
}

// DetectAuto handles POST /api/v1/detect/auto
func (h *AnomalyHandler) DetectAuto(w http.ResponseWriter, r *http.Request) {
	h.runDetect(w, r, time.Time{}, "")
}

// ListIncidents handles GET /api/v1/incidents
func (h *AnomalyHandler) ListIncidents(w http.ResponseWriter, r *http.Request) {
	incidents := h.alertMgr.Store().ListActive()
	summaries := make([]incidentSummary, 0, len(incidents))
	for _, inc := range incidents {
		summaries = append(summaries, toIncidentSummary(inc))
	}
	writeJSON(w, http.StatusOK, map[string]any{"incidents": summaries})
}

// GetIncidentTrace handles GET /api/v1/incidents/{id}/trace
// Returns the full system-generated trace for an incident: signal metadata,
// each drilldown phase with its SQL and results, and the final narration.
func (h *AnomalyHandler) GetIncidentTrace(w http.ResponseWriter, r *http.Request) {
	id := routeID(r, "/api/v1/incidents/")
	// Strip trailing "/trace" if the id came from the prefix-strip path
	id = strings.TrimSuffix(id, "/trace")
	inc := h.alertMgr.Store().GetByID(id)
	if inc == nil {
		writeError(w, http.StatusNotFound, "incident not found")
		return
	}
	writeJSON(w, http.StatusOK, toIncidentTrace(inc))
}

// GetIncident handles GET /api/v1/incidents/{id}
func (h *AnomalyHandler) GetIncident(w http.ResponseWriter, r *http.Request) {
	id := routeID(r, "/api/v1/incidents/")
	inc := h.alertMgr.Store().GetByID(id)
	if inc == nil {
		writeError(w, http.StatusNotFound, "incident not found")
		return
	}
	if inc.DrillDown == nil {
		writeJSON(w, http.StatusAccepted, map[string]any{
			"incident":  toIncidentSummary(inc),
			"drilldown": nil,
			"message":   "incident analysis in progress, retry in a few seconds",
		})
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"incident":    toIncidentSummary(inc),
		"drilldown":   toDrillDownResp(inc.DrillDown),
		"narration":   inc.Narration,
		"queries_run": len(inc.DrillDown.AllQueries),
	})
}

// ── Internal ─────────────────────────────────────────────────────────────────

func (h *AnomalyHandler) runDetect(w http.ResponseWriter, r *http.Request, windowEnd time.Time, metricFilter string) {
	if metricFilter != "" && !isV1MetricSupported(metricFilter) {
		writeError(w, http.StatusBadRequest, "unsupported v1 metric: "+metricFilter+"; supported metrics are revenue, fill_rate, ecpm, ctr, requests")
		return
	}
	window, err := h.engine.ResolveWindow(r.Context(), windowEnd)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "failed to resolve window")
		return
	}

	result, err := h.engine.Detect(r.Context(), window)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "detection failed: "+err.Error())
		return
	}

	if metricFilter != "" {
		filtered := result.Anomalies[:0]
		for _, a := range result.Anomalies {
			if a.Metric == metricFilter {
				filtered = append(filtered, a)
			}
		}
		result.Anomalies = filtered
	}

	incidents, _ := h.alertMgr.ProcessResult(r.Context(), result)

	writeJSON(w, http.StatusOK, detectResponse{
		Window: windowResp{
			Start:    window.Start.Format(time.RFC3339),
			End:      window.End.Format(time.RFC3339),
			Duration: window.Duration.String(),
			Grain:    window.Grain(),
		},
		AnomalyDetected: result.HasAnomalies(),
		Anomalies:       toAnomalyResps(result.Anomalies),
		Incidents:       toIncidentSummaries(incidents),
		ExecutionTimeMs: result.ExecutionTime.Milliseconds(),
	})
}

func isV1MetricSupported(metric string) bool {
	switch metric {
	case anomalydetector.MetricRevenue, anomalydetector.MetricFillRate, anomalydetector.MetricECPM, anomalydetector.MetricCTR, anomalydetector.MetricRequests:
		return true
	default:
		return false
	}
}

// ── Response builders ─────────────────────────────────────────────────────────

func toAnomalyResps(signals []anomalydetector.AnomalySignal) []anomalyResp {
	out := make([]anomalyResp, 0, len(signals))
	for _, s := range signals {
		out = append(out, anomalyResp{
			Metric:        s.Metric,
			DetectorID:    s.DetectorID,
			Dimension:     s.Dimension,
			Segment:       s.Segment,
			CurrentValue:  s.CurrentVal,
			BaselineValue: s.BaselineVal,
			ZScore:        s.ZScore,
			CUSUMVal:      s.CUSUMVal,
			DeviationPct:  formatPct(s.DeviationPct),
			Severity:      s.Severity.String(),
		})
	}
	return out
}

func toIncidentSummary(inc *alertmanager.Incident) incidentSummary {
	return incidentSummary{
		ID:             inc.ID,
		Metric:         inc.Metric,
		DetectorID:     inc.DetectorID,
		Dimension:      inc.Dimension,
		Segment:        inc.Segment,
		Severity:       inc.Severity.String(),
		Status:         string(inc.Status),
		DeviationPct:   formatPct(inc.DeviationPct),
		ZScore:         inc.ZScore,
		WindowStart:    inc.Window.Start.Format(time.RFC3339),
		WindowEnd:      inc.Window.End.Format(time.RFC3339),
		CreatedAt:      inc.CreatedAt.Format(time.RFC3339),
		DrilldownReady: inc.DrillDown != nil,
	}
}

func toIncidentSummaries(incidents []*alertmanager.Incident) []incidentSummary {
	out := make([]incidentSummary, 0, len(incidents))
	for _, inc := range incidents {
		out = append(out, toIncidentSummary(inc))
	}
	return out
}

func toDrillDownResp(dd *drilldown.DrillDownResult) any {
	if dd == nil {
		return nil
	}
	culprits := make([]map[string]any, 0, len(dd.CulpritSegments))
	for _, s := range dd.CulpritSegments {
		culprits = append(culprits, map[string]any{
			"dimension":        s.Dimension,
			"segment":          s.Segment,
			"metric":           s.Metric,
			"current_value":    s.CurrentValue,
			"baseline_value":   s.BaselineValue,
			"delta":            s.Delta,
			"contribution_pct": s.ContributionPct,
			"cold_start":       s.ColdStart,
			"z_score":          s.ZScore,
		})
	}
	var holdOut map[string]any
	if dd.HoldOut != nil {
		holdOut = map[string]any{
			"dimension":        dd.HoldOut.Dimension,
			"excluded_segment": dd.HoldOut.ExcludedSegment,
			"value_excluding":  dd.HoldOut.ExcludingValue,
			"baseline":         dd.HoldOut.ExcludingBase,
			"deviation_pct":    formatPct(dd.HoldOut.DeviationPct),
			"reverted":         dd.HoldOut.Reverted,
		}
	}

	var pairwise map[string]any
	if dd.Pairwise != nil {
		pairwise = map[string]any{
			"dim1":           dd.Pairwise.Dim1,
			"value1":         dd.Pairwise.Value1,
			"dim2":           dd.Pairwise.Dim2,
			"value2":         dd.Pairwise.Value2,
			"current_value":  dd.Pairwise.CurrentValue,
			"baseline_value": dd.Pairwise.BaselineValue,
			"current_n":      dd.Pairwise.CurrentN,
		}
	}

	return map[string]any{
		"anomaly_date":  dd.AnomalyDate,
		"baseline_date": dd.BaselineDate,
		"guilty_factor": dd.Decomposition.GuiltyFactor,
		"factor_decomposition": map[string]any{
			"fill_rate":   factorDeltaMap(dd.Decomposition.FillRate),
			"render_rate": factorDeltaMap(dd.Decomposition.RenderRate),
			"ecpm":        factorDeltaMap(dd.Decomposition.ECPM),
			"requests":    factorDeltaMap(dd.Decomposition.Requests),
		},
		"culprit_segments":     culprits,
		"ruled_out_factors":    dd.Decomposition.RuledOut,
		"ruled_out_dimensions": dd.RuledOutDims,
		"hold_out":             holdOut,
		"pairwise":             pairwise,
		"classification":       dd.Classification,
		"completeness_score":   dd.CompletenessScore,
		"execution_time_ms":    dd.ExecutionTime.Milliseconds(),
	}
}

// toIncidentTrace builds the complete structured trace for an incident.
func toIncidentTrace(inc *alertmanager.Incident) map[string]any {
	traceID := "anomaly-incident-" + inc.Metric + "-" + inc.ID[:8]

	incidentMeta := map[string]any{
		"id":            inc.ID,
		"metric":        inc.Metric,
		"detector_id":   inc.DetectorID,
		"z_score":       inc.ZScore,
		"cusum_val":     inc.CUSUMVal,
		"deviation_pct": formatPct(inc.DeviationPct),
		"severity":      inc.Severity.String(),
		"status":        string(inc.Status),
		"window_start":  inc.Window.Start.Format(time.RFC3339),
		"window_end":    inc.Window.End.Format(time.RFC3339),
		"dimension":     inc.Dimension,
		"segment":       inc.Segment,
		"created_at":    inc.CreatedAt.Format(time.RFC3339),
	}

	if inc.DrillDown == nil {
		return map[string]any{
			"trace_id": traceID,
			"status":   "pending",
			"message":  "drilldown investigation in progress, retry in a few seconds",
			"incident": incidentMeta,
		}
	}

	dd := inc.DrillDown
	phases := []map[string]any{{
		"name":          "factor_decomposition",
		"guilty_factor": dd.Decomposition.GuiltyFactor,
		"ruled_out":     dd.Decomposition.RuledOut,
		"factors": map[string]any{
			"requests":    factorDeltaMap(dd.Decomposition.Requests),
			"fill_rate":   factorDeltaMap(dd.Decomposition.FillRate),
			"render_rate": factorDeltaMap(dd.Decomposition.RenderRate),
			"ecpm":        factorDeltaMap(dd.Decomposition.ECPM),
			"revenue":     factorDeltaMap(dd.Decomposition.Revenue),
		},
	}}

	culprits := make([]map[string]any, 0, len(dd.CulpritSegments))
	for _, s := range dd.CulpritSegments {
		culprits = append(culprits, map[string]any{
			"dimension":        s.Dimension,
			"segment":          s.Segment,
			"metric":           s.Metric,
			"current_value":    s.CurrentValue,
			"baseline_value":   s.BaselineValue,
			"delta":            s.Delta,
			"contribution_pct": s.ContributionPct,
			"cold_start":       s.ColdStart,
			"z_score":          s.ZScore,
		})
	}
	phases = append(phases, map[string]any{
		"name":             "contributions",
		"culprit_segments": culprits,
		"ruled_out_dims":   dd.RuledOutDims,
	})

	if len(dd.CulpritSegments) > 0 && dd.CulpritSegments[0].ZScore != 0 {
		top := dd.CulpritSegments[0]
		phases = append(phases, map[string]any{
			"name":          "segment_zscore",
			"top_dimension": top.Dimension,
			"top_segment":   top.Segment,
			"top_zscore":    top.ZScore,
		})
	}

	if dd.Pairwise != nil {
		phases = append(phases, map[string]any{
			"name":           "pairwise",
			"dim1":           dd.Pairwise.Dim1,
			"segment1":       dd.Pairwise.Value1,
			"dim2":           dd.Pairwise.Dim2,
			"segment2":       dd.Pairwise.Value2,
			"current_value":  dd.Pairwise.CurrentValue,
			"baseline_value": dd.Pairwise.BaselineValue,
			"current_n":      dd.Pairwise.CurrentN,
		})
	}

	if dd.HoldOut != nil {
		phases = append(phases, map[string]any{
			"name":                "holdout",
			"dimension":           dd.HoldOut.Dimension,
			"excluded_segment":    dd.HoldOut.ExcludedSegment,
			"value_excluding":     dd.HoldOut.ExcludingValue,
			"baseline_excluding":  dd.HoldOut.ExcludingBase,
			"deviation_with_excl": formatPct(dd.HoldOut.DeviationPct),
			"reverted":            dd.HoldOut.Reverted,
		})
	}

	result := map[string]any{
		"trace_id":           traceID,
		"status":             "completed",
		"incident":           incidentMeta,
		"classification":     dd.Classification,
		"completeness_score": dd.CompletenessScore,
		"anomaly_date":       dd.AnomalyDate,
		"baseline_date":      dd.BaselineDate,
		"phases":             phases,
		"sql_audit_trail":    dd.AllQueries,
		"execution_time_ms":  dd.ExecutionTime.Milliseconds(),
	}
	if inc.Narration != nil {
		result["narration"] = inc.Narration
	}
	return result
}

func factorDeltaMap(fd drilldown.FactorDelta) map[string]any {
	return map[string]any{
		"current":   fd.Current,
		"baseline":  fd.Baseline,
		"delta_pct": fd.DeltaPct,
		"is_guilty": fd.IsGuilty,
	}
}

func formatPct(f float64) string {
	sign := ""
	if f > 0 {
		sign = "+"
	}
	return fmt.Sprintf("%s%.1f%%", sign, f*100)
}
