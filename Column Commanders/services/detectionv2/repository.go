package detectionv2

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/investigation"
)

type Repository struct {
	qe *query.Executor
}

func NewRepository(qe *query.Executor) *Repository { return &Repository{qe: qe} }

func (r *Repository) SaveCandidates(ctx context.Context, candidates []anomalydetector.Candidate) error {
	rows := make([]map[string]any, 0, len(candidates))
	for _, c := range candidates {
		rows = append(rows, map[string]any{
			"candidate_id": c.ID, "run_id": c.RunID, "mode": string(c.Mode),
			"resolution": string(c.Resolution), "metric": c.Metric, "direction": int8(c.Direction),
			"window_start": c.WindowStart, "window_end": c.WindowEnd,
			"current_value": c.CurrentValue, "baseline_value": c.BaselineValue,
			"deviation_pct": c.DeviationPct, "score": c.Score,
			"revenue_impact": c.RevenueImpact, "baseline_n": c.BaselineN,
			"severity": uint8(c.Severity), "status": c.Status,
			"detected_at": c.DetectedAt, "version": c.Version,
		})
	}
	return r.qe.InsertRows(ctx, "save_anomaly_candidates", "anomaly_candidates", []string{
		"candidate_id", "run_id", "mode", "resolution", "metric", "direction",
		"window_start", "window_end", "current_value", "baseline_value", "deviation_pct",
		"score", "revenue_impact", "baseline_n", "severity", "status", "detected_at", "version",
	}, rows)
}

func (r *Repository) SaveEpisodes(ctx context.Context, episodes []Episode) error {
	rows := make([]map[string]any, 0, len(episodes))
	for _, episode := range episodes {
		resolutions := make([]string, len(episode.DetectedResolutions))
		for i, resolution := range episode.DetectedResolutions {
			resolutions[i] = string(resolution)
		}
		rows = append(rows, map[string]any{
			"episode_id": episode.ID, "primary_metric": episode.PrimaryMetric,
			"direction": int8(episode.Direction), "start_time": episode.Start, "end_time": episode.End,
			"detected_resolutions": resolutions, "candidate_ids": episode.CandidateIDs,
			"severity": uint8(episode.Severity), "status": episode.Status,
			"verification_status": episode.VerificationStatus, "diagnosis": episode.Diagnosis,
			"root_cause_dimension": episode.RootCauseDimension, "root_cause_segment": episode.RootCauseSegment,
			"narration": episode.Narration, "confidence": episode.Confidence,
			"created_at": episode.CreatedAt, "updated_at": episode.UpdatedAt,
			"version": uint64(episode.UpdatedAt.UnixMilli()),
		})
	}
	return r.qe.InsertRows(ctx, "save_anomaly_episodes", "anomaly_episodes", []string{
		"episode_id", "primary_metric", "direction", "start_time", "end_time",
		"detected_resolutions", "candidate_ids", "severity", "status", "verification_status",
		"diagnosis", "root_cause_dimension", "root_cause_segment", "narration", "confidence", "created_at", "updated_at", "version",
	}, rows)
}

func (r *Repository) SaveTemplate(ctx context.Context, templateID any, purpose string, mode anomalydetector.DetectionMode, resolution anomalydetector.Resolution, sql string, expected []string, checksum string) error {
	now := time.Now().UTC()
	return r.qe.InsertRows(ctx, "save_query_template", "query_templates", []string{
		"template_id", "purpose", "mode", "resolution", "sql", "expected_columns",
		"metric_registry_checksum", "schema_fingerprint", "status", "created_at", "updated_at", "version",
	}, []map[string]any{{
		"template_id": templateID, "purpose": purpose, "mode": string(mode), "resolution": string(resolution),
		"sql": sql, "expected_columns": expected, "metric_registry_checksum": checksum,
		"schema_fingerprint": "detection-v2-1", "status": "active",
		"created_at": now, "updated_at": now, "version": uint64(now.UnixMilli()),
	}})
}

const selectEpisodesSQL = `SELECT episode_id, primary_metric, direction, start_time, end_time,
	detected_resolutions, candidate_ids, severity, status, verification_status,
	diagnosis, root_cause_dimension, root_cause_segment, narration, confidence,
	created_at, updated_at
FROM anomaly_episodes FINAL`

func (r *Repository) ListEpisodes(ctx context.Context) ([]Episode, error) {
	rows, err := r.qe.Rows(ctx, "list_anomaly_episodes_v2", selectEpisodesSQL+`
ORDER BY start_time DESC
	LIMIT 1000
	SETTINGS max_execution_time = 3, max_rows_to_read = 1000000, max_result_rows = 1000`)
	if err != nil {
		return nil, err
	}
	episodes, err := decodeEpisodes(rows)
	if err != nil {
		return nil, err
	}
	if err := r.hydrateEvidence(ctx, episodes); err != nil {
		return nil, err
	}
	return episodes, nil
}

func (r *Repository) GetEpisode(ctx context.Context, id uuid.UUID) (Episode, bool, error) {
	row, err := r.qe.Row(ctx, "get_anomaly_episode_v2", selectEpisodesSQL+`
WHERE episode_id = toUUID({episode_id:String})
LIMIT 1
	SETTINGS max_execution_time = 3`, "episode_id", id.String())
	if err != nil {
		if errors.Is(err, db.ErrNoRows) {
			return Episode{}, false, nil
		}
		return Episode{}, false, err
	}
	episodes, err := decodeEpisodes([]map[string]any{row})
	if err != nil {
		return Episode{}, false, err
	}
	if err := r.hydrateEvidence(ctx, episodes); err != nil {
		return Episode{}, false, err
	}
	return episodes[0], true, nil
}

func (r *Repository) GetEpisodesByIDs(ctx context.Context, ids []uuid.UUID) ([]Episode, error) {
	if len(ids) == 0 {
		return nil, nil
	}
	rows, err := r.qe.Rows(ctx, "get_anomaly_episodes_by_id_v2", selectEpisodesSQL+`
WHERE has({episode_ids:Array(UUID)}, episode_id)
SETTINGS max_execution_time = 3, max_rows_to_read = 1000000, max_result_rows = 1000`, "episode_ids", ids)
	if err != nil {
		return nil, err
	}
	return decodeEpisodes(rows)
}

func (r *Repository) GetCandidatesByIDs(ctx context.Context, ids []uuid.UUID) ([]anomalydetector.Candidate, error) {
	if len(ids) == 0 {
		return nil, nil
	}
	rows, err := r.qe.Rows(ctx, "get_anomaly_candidates_by_id_v2", `SELECT candidate_id, run_id, mode, resolution,
	metric, direction, window_start, window_end, current_value, baseline_value,
	deviation_pct, score, revenue_impact, baseline_n, severity, status, detected_at, version
FROM anomaly_candidates FINAL
WHERE has({candidate_ids:Array(UUID)}, candidate_id)
LIMIT 1000
SETTINGS max_execution_time = 3, max_rows_to_read = 1000000, max_result_rows = 1000`, "candidate_ids", ids)
	if err != nil {
		return nil, err
	}
	return decodeCandidates(rows)
}

func (r *Repository) hydrateEvidence(ctx context.Context, episodes []Episode) error {
	if len(episodes) == 0 {
		return nil
	}
	ids := make([]uuid.UUID, len(episodes))
	indexes := make(map[uuid.UUID]int, len(episodes))
	for i := range episodes {
		ids[i] = episodes[i].ID
		indexes[episodes[i].ID] = i
	}
	rows, err := r.qe.Rows(ctx, "get_episode_evidence_v2", `SELECT evidence_id, episode_id, metric, dimension, segment,
	window_start, window_end, current_value, baseline_value, deviation_pct,
	contribution_pct, revenue_impact, baseline_n, verified
FROM evidence_records FINAL
WHERE has({episode_ids:Array(UUID)}, episode_id) AND verified = 1
ORDER BY created_at DESC
LIMIT 1000
SETTINGS max_execution_time = 3, max_rows_to_read = 1000000, max_result_rows = 1000`, "episode_ids", ids)
	if err != nil {
		return err
	}
	for _, row := range rows {
		episodeID, parseErr := uuid.Parse(fmt.Sprint(row["episode_id"]))
		if parseErr != nil {
			return fmt.Errorf("decode evidence episode id: %w", parseErr)
		}
		index, ok := indexes[episodeID]
		if !ok {
			continue
		}
		evidenceID, parseErr := uuid.Parse(fmt.Sprint(row["evidence_id"]))
		if parseErr != nil {
			return fmt.Errorf("decode evidence id: %w", parseErr)
		}
		windowStart, startOK := asTime(row["window_start"])
		windowEnd, endOK := asTime(row["window_end"])
		if !startOK || !endOK {
			return fmt.Errorf("decode evidence %s timestamps", evidenceID)
		}
		episodes[index].Evidence = append(episodes[index].Evidence, investigation.Evidence{
			ID: evidenceID, EpisodeID: episodeID, Metric: fmt.Sprint(row["metric"]),
			Dimension: fmt.Sprint(row["dimension"]), Segment: fmt.Sprint(row["segment"]),
			WindowStart: windowStart, WindowEnd: windowEnd,
			CurrentValue: asFloat(row["current_value"]), BaselineValue: asFloat(row["baseline_value"]),
			DeviationPct: asFloat(row["deviation_pct"]), ContributionPct: asFloat(row["contribution_pct"]),
			RevenueImpact: asFloat(row["revenue_impact"]), BaselineN: uint16(asFloat(row["baseline_n"])),
			Verified: asFloat(row["verified"]) == 1,
		})
	}
	return nil
}

func decodeEpisodes(rows []map[string]any) ([]Episode, error) {
	episodes := make([]Episode, 0, len(rows))
	for _, row := range rows {
		id, ok := row["episode_id"].(uuid.UUID)
		if !ok {
			parsed, err := uuid.Parse(fmt.Sprint(row["episode_id"]))
			if err != nil {
				return nil, fmt.Errorf("decode episode id: %w", err)
			}
			id = parsed
		}
		start, startOK := asTime(row["start_time"])
		end, endOK := asTime(row["end_time"])
		created, createdOK := asTime(row["created_at"])
		updated, updatedOK := asTime(row["updated_at"])
		if !startOK || !endOK || !createdOK || !updatedOK {
			return nil, fmt.Errorf("decode episode %s timestamps", id)
		}
		resolutions := make([]anomalydetector.Resolution, 0)
		if values, ok := row["detected_resolutions"].([]string); ok {
			for _, value := range values {
				resolutions = append(resolutions, anomalydetector.Resolution(value))
			}
		}
		candidateIDs, _ := row["candidate_ids"].([]uuid.UUID)
		episodes = append(episodes, Episode{
			ID: id, PrimaryMetric: fmt.Sprint(row["primary_metric"]),
			Direction: anomalydetector.Direction(int8(asFloat(row["direction"]))),
			Start:     start, End: end, DetectedResolutions: resolutions, CandidateIDs: candidateIDs,
			Severity: anomalydetector.Severity(uint8(asFloat(row["severity"]))),
			Status:   fmt.Sprint(row["status"]), VerificationStatus: fmt.Sprint(row["verification_status"]),
			Diagnosis: fmt.Sprint(row["diagnosis"]), RootCauseDimension: fmt.Sprint(row["root_cause_dimension"]),
			RootCauseSegment: fmt.Sprint(row["root_cause_segment"]), Narration: fmt.Sprint(row["narration"]),
			Confidence: float32(asFloat(row["confidence"])), CreatedAt: created, UpdatedAt: updated,
		})
	}
	return episodes, nil
}

func decodeCandidates(rows []map[string]any) ([]anomalydetector.Candidate, error) {
	candidates := make([]anomalydetector.Candidate, 0, len(rows))
	for _, row := range rows {
		id, err := parseUUID(row["candidate_id"])
		if err != nil {
			return nil, fmt.Errorf("decode candidate id: %w", err)
		}
		runID, err := parseUUID(row["run_id"])
		if err != nil {
			return nil, fmt.Errorf("decode candidate %s run id: %w", id, err)
		}
		windowStart, startOK := asTime(row["window_start"])
		windowEnd, endOK := asTime(row["window_end"])
		detectedAt, detectedOK := asTime(row["detected_at"])
		if !startOK || !endOK || !detectedOK {
			return nil, fmt.Errorf("decode candidate %s timestamps", id)
		}
		candidates = append(candidates, anomalydetector.Candidate{
			ID: id, RunID: runID,
			Mode:        anomalydetector.DetectionMode(fmt.Sprint(row["mode"])),
			Resolution:  anomalydetector.Resolution(fmt.Sprint(row["resolution"])),
			Metric:      fmt.Sprint(row["metric"]),
			Direction:   anomalydetector.Direction(int8(asFloat(row["direction"]))),
			WindowStart: windowStart, WindowEnd: windowEnd,
			CurrentValue: asFloat(row["current_value"]), BaselineValue: asFloat(row["baseline_value"]),
			DeviationPct: asFloat(row["deviation_pct"]), Score: asFloat(row["score"]),
			RevenueImpact: fmt.Sprint(row["revenue_impact"]), BaselineN: uint16(asFloat(row["baseline_n"])),
			Severity: anomalydetector.Severity(uint8(asFloat(row["severity"]))), Status: fmt.Sprint(row["status"]),
			DetectedAt: detectedAt, Version: uint64(asFloat(row["version"])),
		})
	}
	return candidates, nil
}

func parseUUID(value any) (uuid.UUID, error) {
	if id, ok := value.(uuid.UUID); ok {
		return id, nil
	}
	return uuid.Parse(fmt.Sprint(value))
}

func mustJSON(value any) string {
	encoded, _ := json.Marshal(value)
	return string(encoded)
}
