package alertmanager

import (
	"time"

	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/narrator"
)

// IncidentStatus represents the lifecycle state of an incident.
type IncidentStatus string

const (
	StatusActive   IncidentStatus = "active"
	StatusResolved IncidentStatus = "resolved"
)

// Incident represents an ongoing or resolved anomaly event.
type Incident struct {
	ID           string
	Metric       string
	DetectorID   string
	Dimension    string // "" for platform-wide incidents, e.g. "os_version" otherwise
	Segment      string // "" for platform-wide incidents, e.g. "Android 15" otherwise
	Window       anomalydetector.Window
	Severity     anomalydetector.Severity
	Status       IncidentStatus
	ZScore       float64
	CUSUMVal     float64
	DeviationPct float64
	DrillDown    *drilldown.DrillDownResult
	Narration    *narrator.DetectionV1Narrative
	CreatedAt    time.Time
	UpdatedAt    time.Time
	ResolvedAt   *time.Time
}

// incidentKey uniquely identifies an incident for deduplication. Dimension and
// segment are part of the key so a segment-level incident (e.g. os_version =
// Android 15) never collides with the platform-wide incident of the same
// metric/direction, or with a different segment's incident.
type incidentKey struct {
	metric    string
	direction string // "down" | "up"
	dimension string
	segment   string
}

func keyFromSignal(s anomalydetector.AnomalySignal) incidentKey {
	dir := "down"
	if s.ZScore > 0 || s.CUSUMVal > 0 {
		dir = "up"
	}
	return incidentKey{metric: s.Metric, direction: dir, dimension: s.Dimension, segment: s.Segment}
}

func dirFromDetectorID(id string) string {
	if id == "cusum_up" {
		return "up"
	}
	return "down"
}
