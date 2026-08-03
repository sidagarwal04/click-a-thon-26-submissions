package alertmanager

import (
	"context"
	"fmt"
	"log/slog"

	"go.opentelemetry.io/otel/trace"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/telemetry"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/narrator"
)

// DrillDownRunner is satisfied by drilldown.Engine.
type DrillDownRunner interface {
	Investigate(ctx context.Context, signal anomalydetector.AnomalySignal) (*drilldown.DrillDownResult, error)
}

// VerdictNarrator is satisfied by narrator.Narrator. It runs only after the
// deterministic drilldown has completed.
type VerdictNarrator interface {
	NarrateDetectionV1(ctx context.Context, signal anomalydetector.AnomalySignal, result *drilldown.DrillDownResult) (narrator.DetectionV1Narrative, error)
}

// Manager processes DetectionResults, deduplicates incidents,
// and triggers async drilldown for new incidents.
type Manager struct {
	store    *Store
	dd       DrillDownRunner
	narrator VerdictNarrator
	cfg      config.DetectionConfig
	logger   *slog.Logger
}

// NewManager creates an AlertManager.
func NewManager(store *Store, dd DrillDownRunner, verdictNarrator VerdictNarrator, cfg config.DetectionConfig, logger *slog.Logger) *Manager {
	return &Manager{store: store, dd: dd, narrator: verdictNarrator, cfg: cfg, logger: logger}
}

// Store returns the underlying incident store (for handlers).
func (m *Manager) Store() *Store { return m.store }

// ProcessResult processes a DetectionResult:
//   - Upserts incidents for every anomalous signal
//   - Spawns async drilldown goroutines for new incidents
//   - Resolves incidents for metrics that returned to normal
func (m *Manager) ProcessResult(ctx context.Context, result anomalydetector.DetectionResult) ([]*Incident, error) {
	// Keyed by ID, not appended directly: two different detectors (e.g. zscore
	// and cusum_down) can legitimately corroborate the same incidentKey — that's
	// intentional (multiple detectors agreeing strengthens one incident, not two)
	// — but each Upsert call returns the same *Incident, so appending on every
	// signal would list it more than once in the response.
	updatedByID := make(map[string]*Incident)
	var order []string
	seen := make(map[incidentKey]bool)

	for _, signal := range result.Anomalies {
		key := keyFromSignal(signal)
		seen[key] = true

		inc, isNew, err := m.store.Upsert(ctx, signal)
		if err != nil {
			return nil, fmt.Errorf("alert manager: upsert: %w", err)
		}
		if _, exists := updatedByID[inc.ID]; !exists {
			order = append(order, inc.ID)
		}
		updatedByID[inc.ID] = inc

		if isNew {
			m.logger.Info("new incident",
				slog.String("id", inc.ID),
				slog.String("metric", inc.Metric),
				slog.String("detector", inc.DetectorID),
				slog.Float64("z_score", signal.ZScore),
				slog.Float64("deviation_pct", signal.DeviationPct),
				slog.String("severity", signal.Severity.String()),
			)
			traceCtx, traceSpan := telemetry.NewLangfuseTrace("anomaly-incident-" + signal.Metric + "-" + inc.ID[:8])
			telemetry.SetTraceName(traceSpan, signal.Metric+" anomaly incident")
			telemetry.SetSpanInput(traceSpan, map[string]any{
				"incident_id":   inc.ID,
				"metric":        signal.Metric,
				"detector_id":   signal.DetectorID,
				"z_score":       signal.ZScore,
				"deviation_pct": signal.DeviationPct,
				"severity":      signal.Severity.String(),
				"current_val":   signal.CurrentVal,
				"baseline_val":  signal.BaselineVal,
				"window_start":  signal.Window.Start,
				"window_end":    signal.Window.End,
				"dimension":     signal.Dimension,
				"segment":       signal.Segment,
			})
			go m.runDrillDown(inc.ID, signal, traceCtx, traceSpan)
		}
	}

	// Resolve incidents for metrics no longer anomalous
	for _, inc := range m.store.ListActive() {
		key := incidentKey{
			metric:    inc.Metric,
			direction: dirFromDetectorID(inc.DetectorID),
			dimension: inc.Dimension,
			segment:   inc.Segment,
		}
		if !seen[key] {
			if err := m.store.Resolve(ctx, key); err != nil {
				m.logger.Warn("failed to resolve incident",
					slog.String("id", inc.ID),
					slog.Any("error", err),
				)
			} else {
				m.logger.Info("incident resolved",
					slog.String("id", inc.ID),
					slog.String("metric", inc.Metric),
				)
			}
		}
	}

	updated := make([]*Incident, 0, len(order))
	for _, id := range order {
		updated = append(updated, updatedByID[id])
	}
	return updated, nil
}

// runDrillDown executes in a goroutine. The traceCtx carries the open
// Langfuse root span created in ProcessResult; drilldown and narration
// child spans attach to it automatically. The span is closed here after
// all work completes.
func (m *Manager) runDrillDown(incidentID string, signal anomalydetector.AnomalySignal, ctx context.Context, traceSpan trace.Span) {
	defer traceSpan.End()

	result, err := m.dd.Investigate(ctx, signal)
	if err != nil {
		m.logger.Error("drilldown failed",
			slog.String("incident_id", incidentID),
			slog.Any("error", err),
		)
		telemetry.RecordSpanError(traceSpan, err)
		return
	}

	var narrative *narrator.DetectionV1Narrative
	if m.narrator != nil {
		generated, narrationErr := m.narrator.NarrateDetectionV1(ctx, signal, result)
		if narrationErr != nil {
			m.logger.Error("incident narration failed",
				slog.String("incident_id", incidentID),
				slog.Any("error", narrationErr),
			)
		} else {
			narrative = &generated
		}
	}

	telemetry.SetSpanOutput(traceSpan, map[string]any{
		"classification":     result.Classification,
		"completeness_score": result.CompletenessScore,
		"culprit_count":      len(result.CulpritSegments),
		"ruled_out_dims":     result.RuledOutDims,
		"query_count":        len(result.AllQueries),
		"guilty_factor":      result.Decomposition.GuiltyFactor,
		"narrated":           narrative != nil,
		"execution_ms":       result.ExecutionTime.Milliseconds(),
	})

	m.store.AttachInvestigation(incidentID, result, narrative)
	m.logger.Info("drilldown attached",
		slog.String("incident_id", incidentID),
		slog.Bool("narrated", narrative != nil),
	)
}
