package detectionv2

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"sync"
	"time"

	"github.com/google/uuid"
	"golang.org/x/sync/errgroup"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/internal/telemetry"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/investigation"
	"clickhouse-go-service/services/narrator"
)

type Pipeline struct {
	qe       *query.Executor
	scanner  *Scanner
	repo     *Repository
	agent    *investigation.Agent
	narrator *narrator.Narrator
	registry *anomalydetector.MetricRegistry
	detCfg   config.DetectionConfig
	llmCfg   config.LLMConfig
	logger   *slog.Logger

	mu                 sync.RWMutex
	persistence        map[string]int
	episodes           map[uuid.UUID]Episode
	investigated       map[uuid.UUID]bool
	investigationSlots chan struct{}
}

func NewPipeline(qe *query.Executor, scanner *Scanner, repo *Repository, agent *investigation.Agent, llmNarrator *narrator.Narrator, registry *anomalydetector.MetricRegistry, detCfg config.DetectionConfig, llmCfg config.LLMConfig, logger *slog.Logger) *Pipeline {
	workers := detCfg.ParallelWorkers
	if workers <= 0 {
		workers = 1
	}
	workers = min(workers, 3)
	return &Pipeline{
		qe: qe, scanner: scanner, repo: repo, agent: agent, narrator: llmNarrator,
		registry: registry, detCfg: detCfg, llmCfg: llmCfg, logger: logger,
		persistence: make(map[string]int), episodes: make(map[uuid.UUID]Episode), investigated: make(map[uuid.UUID]bool),
		investigationSlots: make(chan struct{}, workers),
	}
}

func (p *Pipeline) DefaultHistoricalRange(ctx context.Context) (time.Time, time.Time, error) {
	anchor, err := p.ResolveAnchor(ctx)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	end := anchor.UTC().Truncate(time.Hour)
	return end.AddDate(0, 0, -7*p.detCfg.LookbackWeeks), end, nil
}

func (p *Pipeline) ResolveAnchor(ctx context.Context) (time.Time, error) {
	row, err := p.qe.Row(ctx, "detection_v2_anchor", query.GetDataAnchorSQL)
	if err != nil {
		row, err = p.qe.Row(ctx, "detection_v2_anchor_fallback", query.GetDataAnchorFallbackSQL)
		if err != nil {
			return time.Time{}, err
		}
	}
	anchor := fmt.Sprint(row["anchor"])
	for _, layout := range []string{"2006-01-02 15:04:05.999999999", "2006-01-02 15:04:05", time.RFC3339Nano} {
		if parsed, parseErr := time.ParseInLocation(layout, anchor, time.UTC); parseErr == nil {
			return parsed.UTC(), nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported data anchor %q", anchor)
}

func (p *Pipeline) RunHistorical(ctx context.Context, request HistoricalRequest) (RunResult, error) {
	if request.Start.IsZero() || request.End.IsZero() {
		start, end, err := p.DefaultHistoricalRange(ctx)
		if err != nil {
			return RunResult{}, err
		}
		request.Start, request.End = start, end
	}
	if !request.Start.Before(request.End) {
		return RunResult{}, errors.New("historical start must be before end")
	}
	return p.run(ctx, anomalydetector.ModeHistorical, request.Start.UTC(), request.End.UTC(), request.Investigate,
		[]anomalydetector.Resolution{anomalydetector.Resolution10m, anomalydetector.Resolution1h})
}

func (p *Pipeline) RunRealTime(ctx context.Context, request RealTimeRequest) (RunResult, error) {
	anchor := request.Anchor
	if anchor.IsZero() {
		var err error
		anchor, err = p.ResolveAnchor(ctx)
		if err != nil {
			return RunResult{}, err
		}
	}
	closed := anchor.UTC().Add(-p.detCfg.LatenessAllowance).Truncate(time.Minute)
	runID := uuid.New()
	started := time.Now().UTC()
	fastEnd := closed.Truncate(5 * time.Minute)
	standardEnd := closed.Truncate(10 * time.Minute)

	results := make([][]anomalydetector.Candidate, 2)
	g, scanCtx := errgroup.WithContext(ctx)
	g.Go(func() error {
		items, err := p.scanner.Scan(scanCtx, runID, anomalydetector.ModeRealTime, anomalydetector.Resolution5m, fastEnd.Add(-5*time.Minute), fastEnd)
		results[0] = items
		return err
	})
	g.Go(func() error {
		items, err := p.scanner.Scan(scanCtx, runID, anomalydetector.ModeRealTime, anomalydetector.Resolution10m, standardEnd.Add(-10*time.Minute), standardEnd)
		results[1] = items
		return err
	})
	if err := g.Wait(); err != nil {
		return RunResult{}, err
	}
	candidates := append([]anomalydetector.Candidate(nil), results[0]...)
	candidates = append(candidates, p.persistentStandard(results[1])...)
	return p.finishRun(ctx, RunResult{RunID: runID, Mode: anomalydetector.ModeRealTime, StartedAt: started, Candidates: candidates}, request.Investigate)
}

func (p *Pipeline) run(ctx context.Context, mode anomalydetector.DetectionMode, start, end time.Time, investigate bool, resolutions []anomalydetector.Resolution) (RunResult, error) {
	runID := uuid.New()
	started := time.Now().UTC()
	ctx, span := telemetry.NewLangfuseTrace("anomaly-detection-" + string(mode))
	defer span.End()
	telemetry.SetSpanInput(span, map[string]any{"run_id": runID, "mode": mode, "start": start, "end": end})

	results := make([][]anomalydetector.Candidate, len(resolutions))
	g, scanCtx := errgroup.WithContext(ctx)
	for i, resolution := range resolutions {
		i, resolution := i, resolution
		g.Go(func() error {
			items, err := p.scanner.Scan(scanCtx, runID, mode, resolution, start, end)
			results[i] = items
			return err
		})
	}
	if err := g.Wait(); err != nil {
		telemetry.RecordSpanError(span, err)
		return RunResult{}, err
	}
	var candidates []anomalydetector.Candidate
	for _, items := range results {
		candidates = append(candidates, items...)
	}
	result, err := p.finishRun(ctx, RunResult{RunID: runID, Mode: mode, StartedAt: started, Candidates: candidates}, investigate)
	if err != nil {
		telemetry.RecordSpanError(span, err)
		return RunResult{}, err
	}
	telemetry.SetSpanOutput(span, map[string]any{"candidates": len(result.Candidates), "episodes": len(result.Episodes)})
	return result, nil
}

func (p *Pipeline) finishRun(ctx context.Context, result RunResult, investigate bool) (RunResult, error) {
	sortCandidates(result.Candidates)
	if err := p.repo.SaveCandidates(ctx, result.Candidates); err != nil {
		return RunResult{}, err
	}
	allCandidates := result.Candidates
	allEpisodes := Correlate(allCandidates)
	result.Episodes = allEpisodes
	if result.Mode == anomalydetector.ModeHistorical {
		var suppressed []Episode
		result.Episodes, suppressed = PrepareHistoricalEpisodes(allEpisodes, p.detCfg.V2HistoricalMergeGap)
		result.SuppressedEpisodeCount = len(suppressed)
		result.Candidates = candidatesForEpisodes(allCandidates, result.Episodes)
		result.SuppressedCandidateCount = len(allCandidates) - len(result.Candidates)
	}
	p.restoreKnownEpisodes(ctx, result.Episodes)
	var claimed []Episode
	if investigate && p.llmCfg.InvestigationEnabled {
		claimed = p.claimInvestigations(result.Episodes, p.detCfg.MaxEpisodesPerRun)
	}
	if err := p.repo.SaveEpisodes(ctx, result.Episodes); err != nil {
		return RunResult{}, err
	}
	result.FinishedAt = time.Now().UTC()
	p.rememberEpisodes(result.Episodes)
	if len(claimed) > 0 {
		candidates := append([]anomalydetector.Candidate(nil), result.Candidates...)
		p.startInvestigations(result.Mode, candidates, claimed)
	}
	return result, nil
}

// startInvestigations deliberately detaches model work from the HTTP request.
// Discovery and persistence return promptly while bounded investigations update
// each episode independently for GET /api/v2/episodes/:id polling.
func (p *Pipeline) startInvestigations(mode anomalydetector.DetectionMode, candidates []anomalydetector.Candidate, episodes []Episode) {
	go func() {
		g := new(errgroup.Group)
		for _, item := range episodes {
			episode := item
			g.Go(func() error {
				p.runInvestigation(mode, candidates, episode)
				return nil
			})
		}
		_ = g.Wait()
	}()
}

func (p *Pipeline) runInvestigation(mode anomalydetector.DetectionMode, candidates []anomalydetector.Candidate, episode Episode) {
	p.investigationSlots <- struct{}{}
	defer func() { <-p.investigationSlots }()
	p.investigateEpisode(mode, candidates, episode)
}

func (p *Pipeline) investigateEpisode(mode anomalydetector.DetectionMode, candidates []anomalydetector.Candidate, episode Episode) {
	perEpisodeTimeout := max(2*time.Minute, p.llmCfg.RequestTimeout*time.Duration(p.llmCfg.MaxSteps+2))
	ctx, cancel := context.WithTimeout(context.Background(), perEpisodeTimeout)
	defer cancel()

	subject := subjectForEpisode(episode, mode, candidates)
	result, err := p.agent.Investigate(ctx, subject)
	if err != nil {
		p.logger.Error("episode investigation failed", slog.String("episode_id", episode.ID.String()), slog.Any("error", err))
		episode.VerificationStatus = "error"
		episode.Diagnosis = "Investigation failed before canonical verification completed."
		p.releaseInvestigation(episode.ID)
	} else {
		episode.VerificationStatus = result.Status
		episode.Diagnosis = result.Diagnosis
		episode.RootCauseDimension = result.RootCauseDimension
		episode.RootCauseSegment = result.RootCauseSegment
		episode.Confidence = float32(result.Confidence)
		episode.Evidence = result.Evidence
		episode.RuledOut = result.RuledOut
		if result.Status == "verified" && p.llmCfg.NarrationEnabled {
			narrative, narrationErr := p.narrator.Narrate(ctx, subject, result)
			if narrationErr != nil {
				p.logger.Error("episode narration failed", slog.String("episode_id", episode.ID.String()), slog.Any("error", narrationErr))
			} else {
				encoded, _ := json.Marshal(narrative)
				episode.Narration = string(encoded)
			}
		}
		if result.Status != "verified" {
			p.releaseInvestigation(episode.ID)
		}
	}
	episode.UpdatedAt = time.Now().UTC()
	p.rememberEpisodes([]Episode{episode})

	saveCtx, saveCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer saveCancel()
	if saveErr := p.repo.SaveEpisodes(saveCtx, []Episode{episode}); saveErr != nil {
		p.logger.Error("persist investigated episode failed", slog.String("episode_id", episode.ID.String()), slog.Any("error", saveErr))
	}
}

func (p *Pipeline) CompileTemplates(ctx context.Context) error {
	for _, item := range []struct {
		mode       anomalydetector.DetectionMode
		resolution anomalydetector.Resolution
	}{
		{anomalydetector.ModeHistorical, anomalydetector.Resolution10m},
		{anomalydetector.ModeHistorical, anomalydetector.Resolution1h},
		{anomalydetector.ModeRealTime, anomalydetector.Resolution5m},
		{anomalydetector.ModeRealTime, anomalydetector.Resolution10m},
	} {
		sql, err := p.scanner.BuildSQL(item.mode, item.resolution)
		if err != nil {
			return err
		}
		id := uuid.NewSHA1(uuid.NameSpaceOID, []byte("discovery|"+string(item.mode)+"|"+string(item.resolution)+"|"+p.registry.Checksum()))
		if err := p.repo.SaveTemplate(ctx, id, "multi_metric_discovery", item.mode, item.resolution, sql,
			[]string{"window_start", "metric", "current_value", "baseline_value", "deviation_pct", "z_score", "revenue_impact", "baseline_n"}, p.registry.Checksum()); err != nil {
			return err
		}
	}
	return nil
}

func (p *Pipeline) StartScheduler(ctx context.Context) {
	if !p.detCfg.SchedulerEnabled {
		return
	}
	frequency := p.detCfg.CheckFrequency
	if frequency <= 0 {
		frequency = time.Minute
	}
	go func() {
		ticker := time.NewTicker(frequency)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				timeout := max(30*time.Second, p.llmCfg.RequestTimeout*time.Duration(p.llmCfg.MaxSteps+1))
				runCtx, cancel := context.WithTimeout(context.Background(), timeout)
				_, err := p.RunRealTime(runCtx, RealTimeRequest{Investigate: p.llmCfg.InvestigationEnabled})
				cancel()
				if err != nil {
					p.logger.Error("scheduled real-time detection failed", slog.Any("error", err))
				}
			}
		}
	}()
}

func (p *Pipeline) ListEpisodes(ctx context.Context) ([]Episode, error) {
	return p.repo.ListEpisodes(ctx)
}

func (p *Pipeline) GetEpisode(ctx context.Context, id uuid.UUID) (Episode, bool, error) {
	p.mu.RLock()
	episode, ok := p.episodes[id]
	p.mu.RUnlock()
	if ok {
		return p.resumeIfNeeded(episode), true, nil
	}
	episode, ok, err := p.repo.GetEpisode(ctx, id)
	if err != nil || !ok {
		return episode, ok, err
	}
	return p.resumeIfNeeded(episode), true, nil
}

// resumeIfNeeded makes GET polling self-healing. A process restart loses the
// detached goroutine that owned an "investigating" episode, while episodes
// beyond a run's immediate work budget remain "pending". The candidates are
// durable, so either state can safely be reclaimed by the first poller.
func (p *Pipeline) resumeIfNeeded(episode Episode) Episode {
	if !p.llmCfg.InvestigationEnabled || (episode.VerificationStatus != "pending" && episode.VerificationStatus != "investigating") {
		return episode
	}
	p.mu.Lock()
	if p.investigated[episode.ID] {
		if current, ok := p.episodes[episode.ID]; ok {
			episode = current
		}
		p.mu.Unlock()
		return episode
	}
	p.investigated[episode.ID] = true
	episode.VerificationStatus = "investigating"
	episode.UpdatedAt = time.Now().UTC()
	p.episodes[episode.ID] = episode
	p.mu.Unlock()

	go p.resumeInvestigation(episode)
	return episode
}

func (p *Pipeline) resumeInvestigation(episode Episode) {
	loadCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	candidates, err := p.repo.GetCandidatesByIDs(loadCtx, episode.CandidateIDs)
	cancel()
	if err != nil || len(candidates) == 0 {
		if err == nil {
			err = errors.New("no persisted candidates found for episode")
		}
		p.failResumedInvestigation(episode, err)
		return
	}
	mode := candidates[0].Mode
	if mode != anomalydetector.ModeHistorical && mode != anomalydetector.ModeRealTime {
		p.failResumedInvestigation(episode, fmt.Errorf("unsupported persisted detection mode %q", mode))
		return
	}
	// Persist ownership before model work so every subsequent poll reports the
	// state this process is actually executing.
	saveCtx, saveCancel := context.WithTimeout(context.Background(), 15*time.Second)
	if err := p.repo.SaveEpisodes(saveCtx, []Episode{episode}); err != nil {
		p.logger.Warn("persist resumed investigation state failed", slog.String("episode_id", episode.ID.String()), slog.Any("error", err))
	}
	saveCancel()
	p.runInvestigation(mode, candidates, episode)
}

func (p *Pipeline) failResumedInvestigation(episode Episode, err error) {
	p.logger.Error("resume episode investigation failed", slog.String("episode_id", episode.ID.String()), slog.Any("error", err))
	episode.VerificationStatus = "error"
	episode.Diagnosis = "Investigation could not be resumed from its persisted anomaly candidates."
	episode.UpdatedAt = time.Now().UTC()
	p.rememberEpisodes([]Episode{episode})
	p.releaseInvestigation(episode.ID)
	saveCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if saveErr := p.repo.SaveEpisodes(saveCtx, []Episode{episode}); saveErr != nil {
		p.logger.Error("persist resumed investigation failure failed", slog.String("episode_id", episode.ID.String()), slog.Any("error", saveErr))
	}
}

func (p *Pipeline) persistentStandard(items []anomalydetector.Candidate) []anomalydetector.Candidate {
	p.mu.Lock()
	defer p.mu.Unlock()
	seen := make(map[string]bool, len(items))
	var emitted []anomalydetector.Candidate
	for _, candidate := range items {
		key := fmt.Sprintf("%s|%d|%s", candidate.Metric, candidate.Direction, candidate.Resolution)
		seen[key] = true
		p.persistence[key]++
		if p.persistence[key] >= p.detCfg.PersistenceChecks {
			emitted = append(emitted, candidate)
		}
	}
	for key := range p.persistence {
		if !seen[key] {
			delete(p.persistence, key)
		}
	}
	return emitted
}

func investigationOrder(episodes []Episode, limit int) []int {
	indexes := make([]int, len(episodes))
	for i := range indexes {
		indexes[i] = i
	}
	sort.Slice(indexes, func(i, j int) bool {
		left, right := episodes[indexes[i]], episodes[indexes[j]]
		if left.Severity != right.Severity {
			return left.Severity > right.Severity
		}
		return len(left.DetectedResolutions) > len(right.DetectedResolutions)
	})
	if limit > 0 && len(indexes) > limit {
		indexes = indexes[:limit]
	}
	return indexes
}

func subjectForEpisode(episode Episode, mode anomalydetector.DetectionMode, candidates []anomalydetector.Candidate) investigation.Subject {
	ids := make(map[uuid.UUID]bool, len(episode.CandidateIDs))
	for _, id := range episode.CandidateIDs {
		ids[id] = true
	}
	var related []anomalydetector.Candidate
	for _, candidate := range candidates {
		if ids[candidate.ID] {
			related = append(related, candidate)
		}
	}
	return investigation.Subject{
		EpisodeID: episode.ID, Metric: episode.PrimaryMetric, Direction: episode.Direction, Mode: mode,
		Start: episode.Start, End: episode.End, Resolutions: episode.DetectedResolutions, Candidates: related,
	}
}

func (p *Pipeline) rememberEpisodes(episodes []Episode) {
	p.mu.Lock()
	defer p.mu.Unlock()
	for _, episode := range episodes {
		p.episodes[episode.ID] = episode
	}
}

func (p *Pipeline) restoreKnownEpisodes(ctx context.Context, episodes []Episode) {
	known := make(map[uuid.UUID]Episode, len(episodes))
	missing := make([]uuid.UUID, 0, len(episodes))
	p.mu.RLock()
	for _, episode := range episodes {
		if item, ok := p.episodes[episode.ID]; ok {
			known[episode.ID] = item
		} else {
			missing = append(missing, episode.ID)
		}
	}
	p.mu.RUnlock()
	if len(missing) > 0 {
		persisted, err := p.repo.GetEpisodesByIDs(ctx, missing)
		if err != nil {
			p.logger.Warn("restore persisted episodes failed", slog.Any("error", err))
		} else {
			for _, item := range persisted {
				known[item.ID] = item
			}
		}
	}
	for i := range episodes {
		item, ok := known[episodes[i].ID]
		if !ok {
			continue
		}
		episodes[i].VerificationStatus = item.VerificationStatus
		episodes[i].Diagnosis = item.Diagnosis
		episodes[i].RootCauseDimension = item.RootCauseDimension
		episodes[i].RootCauseSegment = item.RootCauseSegment
		episodes[i].Narration = item.Narration
		episodes[i].Confidence = item.Confidence
		episodes[i].Evidence = item.Evidence
		episodes[i].RuledOut = item.RuledOut
		episodes[i].CreatedAt = item.CreatedAt
		episodes[i].UpdatedAt = item.UpdatedAt
	}
}

func (p *Pipeline) claimInvestigations(episodes []Episode, limit int) []Episode {
	indexes := investigationOrder(episodes, 0)
	p.mu.Lock()
	defer p.mu.Unlock()
	claimed := make([]Episode, 0, min(len(indexes), max(limit, 0)))
	for _, index := range indexes {
		if limit > 0 && len(claimed) >= limit {
			break
		}
		episode := &episodes[index]
		if p.investigated[episode.ID] || episode.VerificationStatus == "verified" {
			continue
		}
		p.investigated[episode.ID] = true
		episode.VerificationStatus = "investigating"
		episode.UpdatedAt = time.Now().UTC()
		claimed = append(claimed, *episode)
	}
	return claimed
}

func (p *Pipeline) releaseInvestigation(id uuid.UUID) {
	p.mu.Lock()
	defer p.mu.Unlock()
	delete(p.investigated, id)
}
