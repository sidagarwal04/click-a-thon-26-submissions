package detectionv2

import (
	"context"
	"io"
	"log/slog"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/services/anomalydetector"
)

func TestScannerBuildsAllApprovedResolutionQueries(t *testing.T) {
	registry, err := anomalydetector.DefaultMetricRegistry()
	if err != nil {
		t.Fatal(err)
	}
	scanner := NewScanner(nil, registry, config.DetectionConfig{LookbackWeeks: 5})
	for _, tc := range []struct {
		mode       anomalydetector.DetectionMode
		resolution anomalydetector.Resolution
		table      string
	}{
		{anomalydetector.ModeHistorical, anomalydetector.Resolution10m, "metrics_global_1m"},
		{anomalydetector.ModeHistorical, anomalydetector.Resolution1h, "metrics_global_1h"},
		{anomalydetector.ModeRealTime, anomalydetector.Resolution5m, "metrics_global_1m"},
		{anomalydetector.ModeRealTime, anomalydetector.Resolution10m, "metrics_global_1m"},
	} {
		sql, buildErr := scanner.BuildSQL(tc.mode, tc.resolution)
		if buildErr != nil {
			t.Fatalf("build %s/%s: %v", tc.mode, tc.resolution, buildErr)
		}
		for _, required := range []string{tc.table, "sum(fills)", "nullIf", "baseline_n", "max_rows_to_read", "ctr_z_threshold"} {
			if !strings.Contains(sql, required) {
				t.Errorf("%s/%s query missing %q", tc.mode, tc.resolution, required)
			}
		}
		if tc.mode == anomalydetector.ModeRealTime && !strings.Contains(sql, "b.window_start < t.window_start") {
			t.Errorf("real-time query can include future baseline peers")
		}
	}
}

func TestScannerUsesMetricSpecificCommercialFloors(t *testing.T) {
	registry, err := anomalydetector.DefaultMetricRegistry()
	if err != nil {
		t.Fatal(err)
	}
	scanner := NewScanner(nil, registry, config.DetectionConfig{
		LookbackWeeks:             5,
		V2AdditiveMinDeviationPct: 0.10,
		MinDeviationPct:           0.03,
		MinDeviationPctCTR:        0.15,
	})
	tuples, err := scanner.metricTuples()
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range []string{
		"tuple('requests'", "toFloat64(0.1)",
		"tuple('revenue'", "tuple('ctr'", "toFloat64(0.15)",
	} {
		if !strings.Contains(tuples, expected) {
			t.Fatalf("metric tuples missing %q:\n%s", expected, tuples)
		}
	}
}

func TestQualifyHistoricalEpisodesRequiresPersistence(t *testing.T) {
	ids := func(count int) []uuid.UUID {
		items := make([]uuid.UUID, count)
		for i := range items {
			items[i] = uuid.New()
		}
		return items
	}
	episodes := []Episode{
		{PrimaryMetric: anomalydetector.MetricCTR, DetectedResolutions: []anomalydetector.Resolution{anomalydetector.Resolution10m}, CandidateIDs: ids(1)},
		{PrimaryMetric: anomalydetector.MetricRevenue, DetectedResolutions: []anomalydetector.Resolution{anomalydetector.Resolution10m}, CandidateIDs: ids(3)},
		{PrimaryMetric: anomalydetector.MetricFillRate, DetectedResolutions: []anomalydetector.Resolution{anomalydetector.Resolution10m, anomalydetector.Resolution1h}, CandidateIDs: ids(2)},
	}
	qualified, suppressed := QualifyHistoricalEpisodes(episodes)
	if len(qualified) != 1 || len(suppressed) != 2 {
		t.Fatalf("qualified=%d suppressed=%d, want 1 and 2", len(qualified), len(suppressed))
	}
	if suppressed[0].PrimaryMetric != anomalydetector.MetricCTR {
		t.Fatalf("suppressed metric = %s, want ctr", suppressed[0].PrimaryMetric)
	}
}

func TestCandidatesForEpisodesReturnsOnlyQualifiedEvidence(t *testing.T) {
	kept := anomalydetector.Candidate{ID: uuid.New()}
	dropped := anomalydetector.Candidate{ID: uuid.New()}
	filtered := candidatesForEpisodes([]anomalydetector.Candidate{kept, dropped}, []Episode{{CandidateIDs: []uuid.UUID{kept.ID}}})
	if len(filtered) != 1 || filtered[0].ID != kept.ID {
		t.Fatalf("filtered candidates = %+v, want only %s", filtered, kept.ID)
	}
}

func TestCorrelateMergesOverlappingResolutions(t *testing.T) {
	start := time.Date(2026, 6, 18, 10, 0, 0, 0, time.UTC)
	candidates := []anomalydetector.Candidate{
		{ID: uuid.New(), Metric: anomalydetector.MetricRevenue, Direction: anomalydetector.DirectionDown, Resolution: anomalydetector.Resolution1h, WindowStart: start, WindowEnd: start.Add(time.Hour), Severity: anomalydetector.SeverityHigh},
		{ID: uuid.New(), Metric: anomalydetector.MetricRevenue, Direction: anomalydetector.DirectionDown, Resolution: anomalydetector.Resolution10m, WindowStart: start.Add(20 * time.Minute), WindowEnd: start.Add(30 * time.Minute), Severity: anomalydetector.SeverityCrit},
	}
	episodes := Correlate(candidates)
	if len(episodes) != 1 {
		t.Fatalf("episodes = %d, want 1", len(episodes))
	}
	if len(episodes[0].DetectedResolutions) != 2 || episodes[0].Severity != anomalydetector.SeverityCrit {
		t.Fatalf("episode did not retain multi-resolution confidence: %+v", episodes[0])
	}
}

func TestConsolidateHistoricalEpisodesMergesSparseSustainedIncident(t *testing.T) {
	start := time.Date(2026, 6, 23, 1, 0, 0, 0, time.UTC)
	firstID, secondID, separateID := uuid.New(), uuid.New(), uuid.New()
	episodes := []Episode{
		{PrimaryMetric: anomalydetector.MetricFillRate, Direction: anomalydetector.DirectionDown,
			Start: start, End: start.Add(2 * time.Hour), CandidateIDs: []uuid.UUID{firstID},
			DetectedResolutions: []anomalydetector.Resolution{anomalydetector.Resolution1h}, Severity: anomalydetector.SeverityHigh},
		{PrimaryMetric: anomalydetector.MetricFillRate, Direction: anomalydetector.DirectionDown,
			Start: start.Add(20 * time.Hour), End: start.Add(21 * time.Hour), CandidateIDs: []uuid.UUID{secondID},
			DetectedResolutions: []anomalydetector.Resolution{anomalydetector.Resolution10m}, Severity: anomalydetector.SeverityCrit},
		{PrimaryMetric: anomalydetector.MetricFillRate, Direction: anomalydetector.DirectionDown,
			Start: start.Add(50 * time.Hour), End: start.Add(51 * time.Hour), CandidateIDs: []uuid.UUID{separateID},
			DetectedResolutions: []anomalydetector.Resolution{anomalydetector.Resolution1h}, Severity: anomalydetector.SeverityHigh},
	}

	merged := ConsolidateHistoricalEpisodes(episodes, 24*time.Hour)
	if len(merged) != 2 {
		t.Fatalf("episodes = %d, want 2", len(merged))
	}
	if len(merged[0].CandidateIDs) != 2 || len(merged[0].DetectedResolutions) != 2 {
		t.Fatalf("sustained incident evidence not merged: %+v", merged[0])
	}
	if !merged[0].End.Equal(start.Add(21*time.Hour)) || merged[0].Severity != anomalydetector.SeverityCrit {
		t.Fatalf("sustained incident bounds/severity incorrect: %+v", merged[0])
	}
	if len(merged[1].CandidateIDs) != 1 || merged[1].CandidateIDs[0] != separateID {
		t.Fatalf("separate incident was incorrectly merged: %+v", merged[1])
	}
}

func TestPrepareHistoricalEpisodesDoesNotLetNoiseManufacturePersistence(t *testing.T) {
	start := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC)
	var episodes []Episode
	for i := 0; i < 3; i++ {
		windowStart := start.Add(time.Duration(i) * 12 * time.Hour)
		episodes = append(episodes, Episode{
			PrimaryMetric: anomalydetector.MetricCTR, Direction: anomalydetector.DirectionUp,
			Start: windowStart, End: windowStart.Add(10 * time.Minute),
			CandidateIDs: []uuid.UUID{uuid.New()},
		})
	}

	qualified, suppressed := PrepareHistoricalEpisodes(episodes, 24*time.Hour)
	if len(qualified) != 0 || len(suppressed) != 3 {
		t.Fatalf("qualified=%d suppressed=%d, want 0 and 3", len(qualified), len(suppressed))
	}
}

func TestConfiguredScannerQueriesExecute(t *testing.T) {
	if os.Getenv("CLICKHOUSE_INTEGRATION_TEST") != "1" {
		t.Skip("set CLICKHOUSE_INTEGRATION_TEST=1 to execute scanner queries")
	}
	cfg := config.Load()
	client, err := db.NewClient(cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	registry, _ := anomalydetector.DefaultMetricRegistry()
	executor := query.NewExecutor(client, slog.New(slog.NewTextHandler(io.Discard, nil)))
	scanner := NewScanner(executor, registry, cfg.Detection)
	end := time.Date(2026, 7, 5, 23, 0, 0, 0, time.UTC)
	for _, tc := range []struct {
		mode       anomalydetector.DetectionMode
		resolution anomalydetector.Resolution
		duration   time.Duration
	}{
		{anomalydetector.ModeHistorical, anomalydetector.Resolution10m, 10 * time.Minute},
		{anomalydetector.ModeHistorical, anomalydetector.Resolution1h, time.Hour},
		{anomalydetector.ModeRealTime, anomalydetector.Resolution5m, 5 * time.Minute},
		{anomalydetector.ModeRealTime, anomalydetector.Resolution10m, 10 * time.Minute},
	} {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		_, scanErr := scanner.Scan(ctx, uuid.New(), tc.mode, tc.resolution, end.Add(-tc.duration), end)
		cancel()
		if scanErr != nil {
			t.Fatalf("execute %s/%s: %v", tc.mode, tc.resolution, scanErr)
		}
	}
}
