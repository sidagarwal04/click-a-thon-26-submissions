package store

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/view26/featurelens/internal/domain"
)

type Memory struct {
	mu          sync.RWMutex
	runs        map[string]domain.FeatureRun
	contexts    map[int]domain.ContextVersion
	rejected    map[int][]domain.ContextVersion
	latest      int
	events      map[string][]domain.RunEvent
	subscribers map[string]map[int]chan domain.RunEvent
	nextSubID   int
}

func NewMemory(baseline domain.ContextVersion) *Memory {
	return &Memory{
		runs:        map[string]domain.FeatureRun{},
		contexts:    map[int]domain.ContextVersion{baseline.Version: baseline},
		rejected:    map[int][]domain.ContextVersion{},
		latest:      baseline.Version,
		events:      map[string][]domain.RunEvent{},
		subscribers: map[string]map[int]chan domain.RunEvent{},
	}
}

// Restore replaces the volatile published control-plane view with the durable
// ClickHouse payloads loaded at service startup. Event streams and subscribers
// remain process-local; published contexts and releases do not.
func (m *Memory) Restore(contexts []domain.ContextVersion, runs []domain.FeatureRun) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if len(m.subscribers) > 0 {
		return fmt.Errorf("cannot restore memory while subscribers are active")
	}
	restoredContexts := make(map[int]domain.ContextVersion, len(contexts))
	latest := -1
	for _, graph := range contexts {
		if graph.Version < 0 {
			return fmt.Errorf("invalid context version %d", graph.Version)
		}
		restoredContexts[graph.Version] = graph
		if graph.Version > latest {
			latest = graph.Version
		}
	}
	if len(restoredContexts) == 0 {
		return fmt.Errorf("durable control plane contains no context versions")
	}
	restoredRuns := make(map[string]domain.FeatureRun, len(runs))
	latestCompleted := map[string]domain.FeatureRun{}
	for _, run := range runs {
		if run.ID == "" {
			return fmt.Errorf("durable control plane contains a run without an id")
		}
		if run.Stage != domain.StageCompleted {
			restoredRuns[run.ID] = run
			continue
		}
		key := releaseKey(run)
		current, exists := latestCompleted[key]
		if !exists || run.UpdatedAt.After(current.UpdatedAt) || (run.UpdatedAt.Equal(current.UpdatedAt) && run.CreatedAt.After(current.CreatedAt)) {
			latestCompleted[key] = run
		}
	}
	for _, run := range latestCompleted {
		restoredRuns[run.ID] = run
	}
	m.contexts = restoredContexts
	m.latest = latest
	m.runs = restoredRuns
	m.rejected = map[int][]domain.ContextVersion{}
	m.events = map[string][]domain.RunEvent{}
	m.subscribers = map[string]map[int]chan domain.RunEvent{}
	m.nextSubID = 0
	return nil
}

var unsafeReleaseKey = regexp.MustCompile(`[^a-z0-9]+`)

func releaseKey(run domain.FeatureRun) string {
	name := strings.TrimSpace(run.Input.Slug)
	if name == "" {
		name = run.Input.Name
	}
	name = strings.Trim(unsafeReleaseKey.ReplaceAllString(strings.ToLower(name), "_"), "_")
	version := run.Input.SchemaVersion
	if version < 1 {
		version = 1
	}
	return fmt.Sprintf("%s:v%d", name, version)
}

// Reset clears the volatile control-plane state and restores the supplied
// immutable baseline. Source data and generated feature tables live in
// ClickHouse and are intentionally outside this store.
func (m *Memory) Reset(baseline domain.ContextVersion) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, listeners := range m.subscribers {
		for _, listener := range listeners {
			close(listener)
		}
	}
	m.runs = map[string]domain.FeatureRun{}
	m.contexts = map[int]domain.ContextVersion{baseline.Version: baseline}
	m.rejected = map[int][]domain.ContextVersion{}
	m.latest = baseline.Version
	m.events = map[string][]domain.RunEvent{}
	m.subscribers = map[string]map[int]chan domain.RunEvent{}
	m.nextSubID = 0
}

func (m *Memory) CreateRun(run domain.FeatureRun) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.runs[run.ID] = run
}

func (m *Memory) GetRun(id string) (domain.FeatureRun, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	run, ok := m.runs[id]
	return run, ok
}

func (m *Memory) UpdateRun(id string, update func(*domain.FeatureRun)) (domain.FeatureRun, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	run, ok := m.runs[id]
	if !ok {
		return domain.FeatureRun{}, fmt.Errorf("run %s not found", id)
	}
	update(&run)
	run.UpdatedAt = time.Now().UTC()
	m.runs[id] = run
	return run, nil
}

func (m *Memory) ListRuns() []domain.FeatureRun {
	m.mu.RLock()
	defer m.mu.RUnlock()
	runs := make([]domain.FeatureRun, 0, len(m.runs))
	for _, run := range m.runs {
		runs = append(runs, run)
	}
	sort.Slice(runs, func(i, j int) bool { return runs[i].CreatedAt.After(runs[j].CreatedAt) })
	return runs
}

func (m *Memory) LatestContext() domain.ContextVersion {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.contexts[m.latest]
}

// ListContexts returns every stored context version in ascending order.
func (m *Memory) ListContexts() []domain.ContextVersion {
	m.mu.RLock()
	defer m.mu.RUnlock()
	contexts := make([]domain.ContextVersion, 0, len(m.contexts))
	for _, context := range m.contexts {
		contexts = append(contexts, context)
	}
	sort.Slice(contexts, func(i, j int) bool { return contexts[i].Version < contexts[j].Version })
	return contexts
}

func (m *Memory) Context(version int) (domain.ContextVersion, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	context, ok := m.contexts[version]
	return context, ok
}

func (m *Memory) PublishContext(context domain.ContextVersion) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if context.ParentVersion != m.latest {
		return fmt.Errorf("context v%d is stale: parent v%d, latest v%d", context.Version, context.ParentVersion, m.latest)
	}
	m.contexts[context.Version] = context
	m.latest = context.Version
	return nil
}

// QuarantineContext records a candidate context version that failed a blocking
// evolution gate. Rejected candidates live outside the published version map so
// they never become latest and a later successful evolution can legitimately
// reuse the same version number.
func (m *Memory) QuarantineContext(context domain.ContextVersion) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.rejected[context.Version] = append(m.rejected[context.Version], context)
}

// RejectedContexts returns every quarantined candidate for audit and UI use.
func (m *Memory) RejectedContexts() []domain.ContextVersion {
	m.mu.RLock()
	defer m.mu.RUnlock()
	rejected := make([]domain.ContextVersion, 0, len(m.rejected))
	for _, candidates := range m.rejected {
		rejected = append(rejected, candidates...)
	}
	sort.Slice(rejected, func(i, j int) bool {
		if rejected[i].Version == rejected[j].Version {
			return rejected[i].CreatedAt.Before(rejected[j].CreatedAt)
		}
		return rejected[i].Version < rejected[j].Version
	})
	return rejected
}

func (m *Memory) AddEvent(event domain.RunEvent) {
	m.mu.Lock()
	m.events[event.RunID] = append(m.events[event.RunID], event)
	listeners := make([]chan domain.RunEvent, 0, len(m.subscribers[event.RunID]))
	for _, listener := range m.subscribers[event.RunID] {
		listeners = append(listeners, listener)
	}
	m.mu.Unlock()
	for _, listener := range listeners {
		select {
		case listener <- event:
		default:
		}
	}
}

func (m *Memory) Events(runID string) []domain.RunEvent {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return append([]domain.RunEvent{}, m.events[runID]...)
}

func (m *Memory) Subscribe(runID string) (<-chan domain.RunEvent, func()) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.nextSubID++
	id := m.nextSubID
	if m.subscribers[runID] == nil {
		m.subscribers[runID] = map[int]chan domain.RunEvent{}
	}
	stream := make(chan domain.RunEvent, 16)
	m.subscribers[runID][id] = stream
	return stream, func() {
		m.mu.Lock()
		defer m.mu.Unlock()
		if listener, ok := m.subscribers[runID][id]; ok {
			delete(m.subscribers[runID], id)
			close(listener)
		}
	}
}
