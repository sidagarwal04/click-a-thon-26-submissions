package investigation

import (
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/services/anomalydetector"
)

type Subject struct {
	EpisodeID   uuid.UUID                     `json:"episode_id"`
	Metric      string                        `json:"metric"`
	Direction   anomalydetector.Direction     `json:"direction"`
	Mode        anomalydetector.DetectionMode `json:"mode"`
	Start       time.Time                     `json:"start"`
	End         time.Time                     `json:"end"`
	Resolutions []anomalydetector.Resolution  `json:"resolutions"`
	Candidates  []anomalydetector.Candidate   `json:"candidates"`
}

type AgentAction struct {
	State              string   `json:"state"`
	Action             string   `json:"action"`
	Purpose            string   `json:"purpose"`
	SQL                string   `json:"sql"`
	ExpectedColumns    []string `json:"expected_columns"`
	Decision           string   `json:"decision"`
	RootCauseDimension string   `json:"root_cause_dimension"`
	RootCauseSegment   string   `json:"root_cause_segment"`
	Confidence         float64  `json:"confidence"`
}

type Step struct {
	Index      int         `json:"index"`
	Action     AgentAction `json:"action"`
	Validation string      `json:"validation"`
	Result     QueryResult `json:"result"`
	Error      string      `json:"error,omitempty"`
	ResponseID string      `json:"response_id,omitempty"`
}

type Evidence struct {
	ID              uuid.UUID `json:"evidence_id"`
	EpisodeID       uuid.UUID `json:"episode_id"`
	Metric          string    `json:"metric"`
	Dimension       string    `json:"dimension"`
	Segment         string    `json:"segment"`
	WindowStart     time.Time `json:"window_start"`
	WindowEnd       time.Time `json:"window_end"`
	CurrentValue    float64   `json:"current_value"`
	BaselineValue   float64   `json:"baseline_value"`
	DeviationPct    float64   `json:"deviation_pct"`
	ContributionPct float64   `json:"contribution_pct"`
	RevenueImpact   float64   `json:"revenue_impact"`
	BaselineN       uint16    `json:"baseline_n"`
	Verified        bool      `json:"verified"`
	VerificationSQL string    `json:"-"`
}

type Result struct {
	Diagnosis          string     `json:"diagnosis"`
	RootCauseDimension string     `json:"root_cause_dimension"`
	RootCauseSegment   string     `json:"root_cause_segment"`
	Confidence         float64    `json:"confidence"`
	Status             string     `json:"status"`
	Steps              []Step     `json:"steps"`
	Evidence           []Evidence `json:"evidence"`
	RuledOut           []string   `json:"ruled_out"`
}
