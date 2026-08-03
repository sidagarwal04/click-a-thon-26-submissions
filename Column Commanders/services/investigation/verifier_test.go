package investigation

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

func TestAttributionSQLUsesLosslessJoinsAndMetricImpact(t *testing.T) {
	registry, _ := anomalydetector.DefaultMetricRegistry()
	metric, _ := registry.Get(anomalydetector.MetricFillRate)
	sql, err := buildAttributionSQL(attributionDimensions(metric), metric, 3, false, 20)
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range []string{
		"FROM (SELECT event_time", "ANY LEFT JOIN apps",
		"ANY LEFT JOIN geo_device", "ARRAY JOIN", "fills / nullIf(requests, 0)",
		"metric_impact / nullIf(global_metric_impact, 0)", "max_rows_to_read",
	} {
		if !strings.Contains(sql, expected) {
			t.Errorf("attribution SQL missing %q", expected)
		}
	}
	for _, excluded := range []string{"tuple('advertiser'", "tuple('adv_vertical'", "tuple('campaign_type'"} {
		if strings.Contains(sql, excluded) {
			t.Errorf("request-denominator attribution must exclude structurally incomplete %q", excluded)
		}
	}
	if strings.Contains(sql, "ANY LEFT JOIN advertisers") {
		t.Error("fill-rate attribution must not join structurally incomplete advertiser dimensions")
	}
	revenue, _ := registry.Get(anomalydetector.MetricRevenue)
	revenueSQL, err := buildAttributionSQL(attributionDimensions(revenue), revenue, 3, false, 20)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(revenueSQL, "ANY LEFT JOIN advertisers") {
		t.Error("revenue attribution should include advertiser dimensions")
	}
}

func TestConfiguredCanonicalVerificationExecutes(t *testing.T) {
	if os.Getenv("CLICKHOUSE_INTEGRATION_TEST") != "1" {
		t.Skip("set CLICKHOUSE_INTEGRATION_TEST=1 to execute canonical verification")
	}
	cfg := config.Load()
	client, err := db.NewClient(cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer client.Close()
	registry, _ := anomalydetector.DefaultMetricRegistry()
	executor := query.NewExecutor(client, slog.New(slog.NewTextHandler(io.Discard, nil)))
	verifier := NewVerifier(executor, registry, cfg.Detection)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	_, err = verifier.Verify(ctx, Subject{
		EpisodeID: uuid.New(), Metric: anomalydetector.MetricRevenue,
		Mode:  anomalydetector.ModeHistorical,
		Start: time.Date(2026, 6, 23, 10, 0, 0, 0, time.UTC),
		End:   time.Date(2026, 6, 23, 11, 0, 0, 0, time.UTC),
	}, "ad_format", "banner")
	if err != nil {
		t.Fatal(err)
	}

	localized, err := verifier.Localize(ctx, Subject{
		EpisodeID: uuid.New(), Metric: anomalydetector.MetricFillRate,
		Direction: anomalydetector.DirectionDown, Mode: anomalydetector.ModeHistorical,
		Start: time.Date(2026, 6, 23, 7, 0, 0, 0, time.UTC),
		End:   time.Date(2026, 6, 23, 9, 10, 0, 0, time.UTC),
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(localized) == 0 {
		t.Fatal("dimension sweep returned no candidates")
	}
	if localized[0].Dimension != "os_version" || localized[0].Segment != "Android 15" || !localized[0].Verified {
		t.Fatalf("top attribution = %+v, want verified os_version=Android 15", localized[0])
	}
}
