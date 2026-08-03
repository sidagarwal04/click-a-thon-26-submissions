package main

import "time"

type MetricType string

const (
	MetricRevenue  MetricType = "revenue"
	MetricFillRate MetricType = "fill_rate"
	MetricECPM     MetricType = "ecpm"
	MetricRequests MetricType = "requests"
	MetricClicks   MetricType = "clicks"
	MetricCTR      MetricType = "ctr"
)

type AnalyzeRequest struct {
	Metric      string `json:"metric"`
	WindowStart string `json:"window_start,omitempty"`
	WindowEnd   string `json:"window_end,omitempty"`
}

type AnomalyRecord struct {
	Timestamp     time.Time `json:"timestamp"`
	Metric        string    `json:"metric"`
	CurrentValue  float64   `json:"current_value"`
	BaselineValue float64   `json:"baseline_value"`
	ZScore        float64   `json:"z_score"`
	PctChange     float64   `json:"pct_change"`
}

type FactorDecomposition struct {
	RequestsDeltaPct  float64 `json:"requests_delta_pct"`
	FillRateDeltaPct  float64 `json:"fill_rate_delta_pct"`
	RenderRateDeltaPct float64 `json:"render_rate_delta_pct"`
	ECPMDeltaPct      float64 `json:"ecpm_delta_pct"`
	PrimaryFactor     string  `json:"primary_driver_factor"`
	Explanation       string  `json:"explanation"`
}

type SegmentContribution struct {
	Dimension     string  `json:"dimension"`
	Value         string  `json:"value"`
	CurrentMetric float64 `json:"current_metric"`
	BaseMetric    float64 `json:"baseline_metric"`
	SegmentDelta  float64 `json:"segment_delta"`
	ShareOfDelta  float64 `json:"share_of_delta"`
	ZScore        float64 `json:"z_score"`
}

type RuledOutItem struct {
	Dimension string `json:"dimension"`
	Reason    string `json:"reason"`
}

type RCAEvidence struct {
	AnomalyDetected         bool                  `json:"anomaly_detected"`
	Metric                  string                `json:"metric"`
	WindowStart             string                `json:"window_start"`
	WindowEnd               string                `json:"window_end"`
	CurrentValue            float64               `json:"current_value"`
	BaselineValue           float64               `json:"baseline_value"`
	Delta                   float64               `json:"delta"`
	PctChange               float64               `json:"pct_change"`
	ZScore                  float64               `json:"z_score"`
	FactorDecomposition     *FactorDecomposition  `json:"factor_decomposition,omitempty"`
	TopContributingSegments []SegmentContribution `json:"top_contributing_segments"`
	RuledOut                []RuledOutItem        `json:"ruled_out"`
	ExecutionTimeMs         int64                 `json:"execution_time_ms"`
}
