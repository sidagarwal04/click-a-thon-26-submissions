package detectionv2

import (
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/investigation"
)

// Episode is a group of overlapping anomaly candidates for the same metric
// and direction. Multiple resolutions raise confidence without duplicating an
// incident.
type Episode struct {
	ID                  uuid.UUID                    `json:"episode_id"`
	PrimaryMetric       string                       `json:"primary_metric"`
	Direction           anomalydetector.Direction    `json:"direction"`
	Start               time.Time                    `json:"start"`
	End                 time.Time                    `json:"end"`
	DetectedResolutions []anomalydetector.Resolution `json:"detected_resolutions"`
	CandidateIDs        []uuid.UUID                  `json:"candidate_ids"`
	Severity            anomalydetector.Severity     `json:"severity"`
	Status              string                       `json:"status"`
	VerificationStatus  string                       `json:"verification_status"`
	Diagnosis           string                       `json:"diagnosis,omitempty"`
	RootCauseDimension  string                       `json:"root_cause_dimension,omitempty"`
	RootCauseSegment    string                       `json:"root_cause_segment,omitempty"`
	Narration           string                       `json:"narration,omitempty"`
	Confidence          float32                      `json:"confidence"`
	Evidence            []investigation.Evidence     `json:"evidence,omitempty"`
	RuledOut            []string                     `json:"ruled_out,omitempty"`
	CreatedAt           time.Time                    `json:"created_at"`
	UpdatedAt           time.Time                    `json:"updated_at"`
}

type RunResult struct {
	RunID                    uuid.UUID                     `json:"run_id"`
	Mode                     anomalydetector.DetectionMode `json:"mode"`
	StartedAt                time.Time                     `json:"started_at"`
	FinishedAt               time.Time                     `json:"finished_at"`
	Candidates               []anomalydetector.Candidate   `json:"candidates"`
	Episodes                 []Episode                     `json:"episodes"`
	SuppressedCandidateCount int                           `json:"suppressed_candidate_count,omitempty"`
	SuppressedEpisodeCount   int                           `json:"suppressed_episode_count,omitempty"`
}

type HistoricalRequest struct {
	Start       time.Time
	End         time.Time
	Investigate bool
}

type RealTimeRequest struct {
	Anchor      time.Time
	Investigate bool
}
