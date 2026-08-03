package investigation

import (
	"context"
	"encoding/json"
	"time"

	"github.com/shopspring/decimal"

	"clickhouse-go-service/internal/query"
)

type Store struct{ qe *query.Executor }

func NewStore(qe *query.Executor) *Store { return &Store{qe: qe} }

func (s *Store) SaveStep(ctx context.Context, subject Subject, step Step) error {
	resultJSON, _ := json.Marshal(step.Result.Rows)
	return s.qe.InsertRows(ctx, "save_investigation_step", "investigation_steps", []string{
		"episode_id", "step_index", "state", "purpose", "query_sql", "validation_status",
		"decision", "result_rows", "result_json", "error", "created_at",
	}, []map[string]any{{
		"episode_id": subject.EpisodeID, "step_index": uint16(step.Index), "state": step.Action.State,
		"purpose": step.Action.Purpose, "query_sql": step.Action.SQL, "validation_status": step.Validation,
		"decision": step.Action.Decision, "result_rows": uint32(len(step.Result.Rows)),
		"result_json": string(resultJSON), "error": step.Error, "created_at": time.Now().UTC(),
	}})
}

func (s *Store) SaveEvidence(ctx context.Context, evidence Evidence) error {
	verified := uint8(0)
	if evidence.Verified {
		verified = 1
	}
	now := time.Now().UTC()
	return s.qe.InsertRows(ctx, "save_evidence_record", "evidence_records", []string{
		"evidence_id", "episode_id", "metric", "dimension", "segment", "window_start", "window_end",
		"current_value", "baseline_value", "deviation_pct", "contribution_pct", "revenue_impact",
		"baseline_n", "verified", "verification_query", "created_at", "version",
	}, []map[string]any{{
		"evidence_id": evidence.ID, "episode_id": evidence.EpisodeID, "metric": evidence.Metric,
		"dimension": evidence.Dimension, "segment": evidence.Segment,
		"window_start": evidence.WindowStart, "window_end": evidence.WindowEnd,
		"current_value": evidence.CurrentValue, "baseline_value": evidence.BaselineValue,
		"deviation_pct": evidence.DeviationPct, "contribution_pct": evidence.ContributionPct,
		"revenue_impact": decimal.NewFromFloatWithExponent(evidence.RevenueImpact, -9), "baseline_n": evidence.BaselineN,
		"verified": verified, "verification_query": evidence.VerificationSQL,
		"created_at": now, "version": uint64(now.UnixMilli()),
	}})
}
