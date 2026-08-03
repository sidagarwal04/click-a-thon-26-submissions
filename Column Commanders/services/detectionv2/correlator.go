package detectionv2

import (
	"fmt"
	"sort"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/services/anomalydetector"
)

func Correlate(candidates []anomalydetector.Candidate) []Episode {
	if len(candidates) == 0 {
		return nil
	}
	sortCandidates(candidates)
	now := time.Now().UTC()
	var episodes []Episode
	for _, candidate := range candidates {
		matched := -1
		for i := len(episodes) - 1; i >= 0; i-- {
			episode := &episodes[i]
			if episode.PrimaryMetric != candidate.Metric || episode.Direction != candidate.Direction {
				continue
			}
			if candidate.WindowStart.After(episode.End.Add(10*time.Minute)) || candidate.WindowEnd.Before(episode.Start.Add(-10*time.Minute)) {
				continue
			}
			matched = i
			break
		}
		if matched < 0 {
			episodes = append(episodes, Episode{
				PrimaryMetric:       candidate.Metric,
				Direction:           candidate.Direction,
				Start:               candidate.WindowStart,
				End:                 candidate.WindowEnd,
				DetectedResolutions: []anomalydetector.Resolution{candidate.Resolution},
				CandidateIDs:        []uuid.UUID{candidate.ID},
				Severity:            candidate.Severity,
				Status:              "open",
				VerificationStatus:  "pending",
				CreatedAt:           now,
				UpdatedAt:           now,
			})
			continue
		}
		episode := &episodes[matched]
		if candidate.WindowStart.Before(episode.Start) {
			episode.Start = candidate.WindowStart
		}
		if candidate.WindowEnd.After(episode.End) {
			episode.End = candidate.WindowEnd
		}
		episode.CandidateIDs = append(episode.CandidateIDs, candidate.ID)
		if !containsResolution(episode.DetectedResolutions, candidate.Resolution) {
			episode.DetectedResolutions = append(episode.DetectedResolutions, candidate.Resolution)
		}
		if candidate.Severity > episode.Severity {
			episode.Severity = candidate.Severity
		}
	}
	for i := range episodes {
		finalizeEpisode(&episodes[i])
	}
	return episodes
}

// ConsolidateHistoricalEpisodes joins sparse detections belonging to one
// sustained incident. At a noisy seasonal slot an incident may clear the
// threshold for several hours, disappear where baseline variance is wider,
// and reappear later the same day. Treating every reappearance as a new event
// inflates the dashboard without adding operational information.
func ConsolidateHistoricalEpisodes(episodes []Episode, maxGap time.Duration) []Episode {
	if len(episodes) < 2 || maxGap <= 0 {
		return episodes
	}
	sort.Slice(episodes, func(i, j int) bool {
		if episodes[i].PrimaryMetric != episodes[j].PrimaryMetric {
			return episodes[i].PrimaryMetric < episodes[j].PrimaryMetric
		}
		if episodes[i].Direction != episodes[j].Direction {
			return episodes[i].Direction < episodes[j].Direction
		}
		return episodes[i].Start.Before(episodes[j].Start)
	})

	merged := make([]Episode, 0, len(episodes))
	for _, episode := range episodes {
		if len(merged) == 0 {
			merged = append(merged, episode)
			continue
		}
		current := &merged[len(merged)-1]
		if current.PrimaryMetric != episode.PrimaryMetric || current.Direction != episode.Direction || episode.Start.After(current.End.Add(maxGap)) {
			merged = append(merged, episode)
			continue
		}
		if episode.Start.Before(current.Start) {
			current.Start = episode.Start
		}
		if episode.End.After(current.End) {
			current.End = episode.End
		}
		current.CandidateIDs = append(current.CandidateIDs, episode.CandidateIDs...)
		for _, resolution := range episode.DetectedResolutions {
			if !containsResolution(current.DetectedResolutions, resolution) {
				current.DetectedResolutions = append(current.DetectedResolutions, resolution)
			}
		}
		if episode.Severity > current.Severity {
			current.Severity = episode.Severity
		}
	}
	for i := range merged {
		finalizeEpisode(&merged[i])
	}
	sort.Slice(merged, func(i, j int) bool { return merged[i].Start.Before(merged[j].Start) })
	return merged
}

// PrepareHistoricalEpisodes intentionally qualifies before consolidating.
// Reversing these operations lets isolated noise points manufacture the three
// candidates required for persistence merely because they are less than one
// merge gap apart.
func PrepareHistoricalEpisodes(episodes []Episode, maxGap time.Duration) (qualified, suppressed []Episode) {
	qualified, suppressed = QualifyHistoricalEpisodes(episodes)
	return ConsolidateHistoricalEpisodes(qualified, maxGap), suppressed
}

func finalizeEpisode(e *Episode) {
	sort.Slice(e.DetectedResolutions, func(i, j int) bool { return e.DetectedResolutions[i] < e.DetectedResolutions[j] })
	sort.Slice(e.CandidateIDs, func(i, j int) bool { return e.CandidateIDs[i].String() < e.CandidateIDs[j].String() })
	key := fmt.Sprintf("%s|%d|%s|%s", e.PrimaryMetric, e.Direction, e.Start.Format(time.RFC3339Nano), e.End.Format(time.RFC3339Nano))
	e.ID = uuid.NewSHA1(uuid.NameSpaceOID, []byte(key))
}

// QualifyHistoricalEpisodes separates actionable episodes from isolated
// discovery signals. Multiple resolutions increase confidence, but historical
// episodes must also persist across at least three nearby candidate windows.
// Candidates are still persisted regardless of this decision.
func QualifyHistoricalEpisodes(episodes []Episode) (qualified, suppressed []Episode) {
	for _, episode := range episodes {
		if len(episode.CandidateIDs) >= 3 {
			qualified = append(qualified, episode)
			continue
		}
		suppressed = append(suppressed, episode)
	}
	return qualified, suppressed
}

func candidatesForEpisodes(candidates []anomalydetector.Candidate, episodes []Episode) []anomalydetector.Candidate {
	ids := make(map[uuid.UUID]struct{})
	for _, episode := range episodes {
		for _, id := range episode.CandidateIDs {
			ids[id] = struct{}{}
		}
	}
	filtered := make([]anomalydetector.Candidate, 0, len(ids))
	for _, candidate := range candidates {
		if _, ok := ids[candidate.ID]; ok {
			filtered = append(filtered, candidate)
		}
	}
	return filtered
}

func containsResolution(items []anomalydetector.Resolution, wanted anomalydetector.Resolution) bool {
	for _, item := range items {
		if item == wanted {
			return true
		}
	}
	return false
}
