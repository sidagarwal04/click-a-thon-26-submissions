package anomalydetector

import "time"

// Metric name constants — use these everywhere, never raw strings.
const (
	MetricRequests   string = "requests"
	MetricRevenue    string = "revenue"
	MetricFillRate   string = "fill_rate"
	MetricRenderRate string = "render_rate"
	MetricCTR        string = "ctr"
	MetricECPM       string = "ecpm"
	MetricRPR        string = "rpr"
)

// Resolution identifies the rollup resolution that produced an anomaly.
type Resolution string

const (
	Resolution5m  Resolution = "5m"
	Resolution10m Resolution = "10m"
	Resolution1h  Resolution = "1h"
)

// DetectionMode distinguishes offline leave-one-out discovery from live
// detection, where future data is never an eligible baseline peer.
type DetectionMode string

const (
	ModeHistorical DetectionMode = "historical"
	ModeRealTime   DetectionMode = "real_time"
)

// Severity represents how strongly anomalous a signal is.
type Severity int

const (
	SeverityLow    Severity = 1
	SeverityMedium Severity = 2
	SeverityHigh   Severity = 3
	SeverityCrit   Severity = 4
)

func (s Severity) String() string {
	switch s {
	case SeverityLow:
		return "low"
	case SeverityMedium:
		return "medium"
	case SeverityHigh:
		return "high"
	case SeverityCrit:
		return "critical"
	default:
		return "unknown"
	}
}

// Window describes a complete time window for detection.
// Both Start and End are UTC. End is always a complete boundary
// (end of last complete hour or day — never the currently open period).
type Window struct {
	Start      time.Time
	End        time.Time
	Duration   time.Duration
	Resolution Resolution
	Mode       DetectionMode
}

// Target returns the inclusive period whose aggregates detectors must query.
// End is the exclusive boundary of the window and must never be used as the
// target bucket, or daily requests will inspect the following calendar day.
func (w Window) Target() time.Time { return w.Start }

// Grain returns "hourly" for sub-day windows, "daily" otherwise.
func (w Window) Grain() string {
	if w.Resolution == Resolution5m || w.Resolution == Resolution10m {
		return "minute"
	}
	if w.Duration < 24*time.Hour {
		return "hourly"
	}
	return "daily"
}

// AnomalySignal is the output of one Detector for one metric in one window.
type AnomalySignal struct {
	Metric       string
	Window       Window
	DetectorID   string // "zscore" | "volume" | "cusum_down" | "cusum_up" | "segment_zscore"
	CurrentVal   float64
	BaselineVal  float64
	ZScore       float64 // 0 if not applicable
	CUSUMVal     float64 // 0 if not applicable
	DeviationPct float64 // (current - baseline) / baseline
	Severity     Severity
	IsAnomaly    bool
	BaselineN    int // number of prior same-period observations used
	// Dimension/Segment identify a broad-segment signal (e.g. Dimension="os_version",
	// Segment="Android 15"). Both are "" for platform-wide signals.
	Dimension  string
	Segment    string
	Resolution Resolution
	Mode       DetectionMode
}

// DetectionResult is the aggregated output of DetectionEngine.Detect().
type DetectionResult struct {
	Window        Window
	Signals       []AnomalySignal // all signals, including non-anomalous
	Anomalies     []AnomalySignal // only signals where IsAnomaly == true
	ExecutionTime time.Duration
}

// HasAnomalies returns true if at least one genuine anomaly was detected.
func (r DetectionResult) HasAnomalies() bool {
	return len(r.Anomalies) > 0
}
