package alertmanager

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/narrator"
)

// Store holds active incidents in memory and persists them to ClickHouse.
type Store struct {
	mu     sync.RWMutex
	active map[incidentKey]*Incident
	byID   map[string]*Incident
	qe     *query.Executor
}

// NewStore creates an incident store.
func NewStore(qe *query.Executor) *Store {
	return &Store{
		active: make(map[incidentKey]*Incident),
		byID:   make(map[string]*Incident),
		qe:     qe,
	}
}

// GetActive returns the active incident for the given key, or nil.
func (s *Store) GetActive(key incidentKey) *Incident {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.active[key]
}

// GetByID returns an incident by its UUID, or nil if not found.
func (s *Store) GetByID(id string) *Incident {
	s.mu.RLock()
	defer s.mu.RUnlock()
	inc := s.byID[id]
	if inc == nil {
		return nil
	}
	cp := *inc
	return &cp
}

// Upsert creates a new incident or updates an existing one.
// Returns (incident, isNew): isNew=true means drilldown should be triggered.
func (s *Store) Upsert(ctx context.Context, signal anomalydetector.AnomalySignal) (*Incident, bool, error) {
	key := keyFromSignal(signal)
	s.mu.Lock()
	defer s.mu.Unlock()

	if existing, ok := s.active[key]; ok {
		existing.UpdatedAt = time.Now()
		existing.ZScore = signal.ZScore
		existing.CUSUMVal = signal.CUSUMVal
		existing.DeviationPct = signal.DeviationPct
		if signal.Severity > existing.Severity {
			existing.Severity = signal.Severity
		}
		_ = s.persist(ctx, existing) // best-effort
		return existing, false, nil
	}

	inc := &Incident{
		ID:           uuid.NewString(),
		Metric:       signal.Metric,
		DetectorID:   signal.DetectorID,
		Dimension:    signal.Dimension,
		Segment:      signal.Segment,
		Window:       signal.Window,
		Severity:     signal.Severity,
		Status:       StatusActive,
		ZScore:       signal.ZScore,
		CUSUMVal:     signal.CUSUMVal,
		DeviationPct: signal.DeviationPct,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}
	s.active[key] = inc
	s.byID[inc.ID] = inc
	_ = s.persist(ctx, inc)
	return inc, true, nil
}

// Resolve marks an incident resolved.
func (s *Store) Resolve(ctx context.Context, key incidentKey) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	inc, ok := s.active[key]
	if !ok {
		return nil
	}
	now := time.Now()
	inc.Status = StatusResolved
	inc.ResolvedAt = &now
	inc.UpdatedAt = now
	delete(s.active, key)
	return s.persist(ctx, inc)
}

// AttachInvestigation atomically publishes the completed deterministic
// drilldown and its optional LLM narration. A failed/disabled narrator leaves
// Narration nil while still making the drilldown available.
func (s *Store) AttachInvestigation(id string, dd *drilldown.DrillDownResult, narrative *narrator.DetectionV1Narrative) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if inc, ok := s.byID[id]; ok {
		inc.DrillDown = dd
		inc.Narration = narrative
		inc.UpdatedAt = time.Now()
	}
}

// ListActive returns copies of all active incidents.
func (s *Store) ListActive() []*Incident {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]*Incident, 0, len(s.active))
	for _, inc := range s.active {
		cp := *inc
		out = append(out, &cp)
	}
	return out
}

func (s *Store) persist(ctx context.Context, inc *Incident) error {
	return s.qe.Exec(ctx, "persist_incident", query.UpsertIncidentSQL,
		"id", inc.ID,
		"metric", inc.Metric,
		"detector_id", inc.DetectorID,
		"dimension", inc.Dimension,
		"segment", inc.Segment,
		"window_start", inc.Window.Start.UTC().Format("2006-01-02 15:04:05"),
		"window_end", inc.Window.End.UTC().Format("2006-01-02 15:04:05"),
		"severity", fmt.Sprintf("%d", inc.Severity),
		"status", string(inc.Status),
		"z_score", fmt.Sprintf("%f", inc.ZScore),
		"cusum_val", fmt.Sprintf("%f", inc.CUSUMVal),
		"deviation_pct", fmt.Sprintf("%f", inc.DeviationPct),
	)
}

func incidentKeyFromIncident(inc *Incident) incidentKey {
	return incidentKey{
		metric:    inc.Metric,
		direction: dirFromDetectorID(inc.DetectorID),
		dimension: inc.Dimension,
		segment:   inc.Segment,
	}
}
