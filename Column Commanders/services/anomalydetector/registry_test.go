package anomalydetector

import (
	"strings"
	"testing"
)

func TestDefaultMetricRegistryContainsAllMetrics(t *testing.T) {
	registry, err := DefaultMetricRegistry()
	if err != nil {
		t.Fatalf("default registry: %v", err)
	}

	want := []string{
		MetricRequests,
		MetricRevenue,
		MetricFillRate,
		MetricRenderRate,
		MetricCTR,
		MetricECPM,
		MetricRPR,
	}
	for _, name := range want {
		if _, ok := registry.Get(name); !ok {
			t.Errorf("metric %q is missing", name)
		}
	}
	if got := len(registry.Definitions()); got != len(want) {
		t.Fatalf("registry has %d definitions, want %d", got, len(want))
	}
}

func TestRatioExpressionsDivideAfterRollup(t *testing.T) {
	registry, err := DefaultMetricRegistry()
	if err != nil {
		t.Fatal(err)
	}

	tests := map[string]string{
		MetricFillRate:   "sum(fills) / nullIf(sum(requests), 0)",
		MetricRenderRate: "sum(impressions) / nullIf(sum(fills), 0)",
		MetricCTR:        "sum(clicks) / nullIf(sum(impressions), 0)",
		MetricECPM:       "sum(revenue) * 1000 / nullIf(sum(impressions), 0)",
		MetricRPR:        "sum(revenue) / nullIf(sum(requests), 0)",
	}
	for name, want := range tests {
		definition, ok := registry.Get(name)
		if !ok {
			t.Fatalf("metric %q is missing", name)
		}
		got, err := definition.SQLExpression()
		if err != nil {
			t.Fatalf("metric %q: %v", name, err)
		}
		if got != want {
			t.Errorf("metric %q expression = %q, want %q", name, got, want)
		}
		if strings.Contains(got, "avg(") {
			t.Errorf("metric %q must not average a ratio: %s", name, got)
		}
	}
}

func TestRegistryRejectsSQLInjectionColumn(t *testing.T) {
	_, err := NewMetricRegistry([]MetricDefinition{{
		Name:      "unsafe",
		Kind:      MetricAdditive,
		Numerator: AggregateColumn("requests); DROP TABLE ad_events; --"),
		Threshold: 0.05,
	}})
	if err == nil {
		t.Fatal("expected unsupported-column error")
	}
}

func TestRegistryChecksumIsOrderIndependent(t *testing.T) {
	a := []MetricDefinition{
		{Name: MetricRequests, Kind: MetricAdditive, Numerator: ColumnRequests, Threshold: 0.05},
		{Name: MetricRevenue, Kind: MetricAdditive, Numerator: ColumnRevenue, Threshold: 0.05},
	}
	b := []MetricDefinition{a[1], a[0]}

	left, err := NewMetricRegistry(a)
	if err != nil {
		t.Fatal(err)
	}
	right, err := NewMetricRegistry(b)
	if err != nil {
		t.Fatal(err)
	}
	if left.Checksum() != right.Checksum() {
		t.Fatal("checksum should not depend on input order")
	}
}

func TestRegistryChecksumChangesWithThreshold(t *testing.T) {
	left, _ := NewMetricRegistry([]MetricDefinition{{
		Name: MetricRequests, Kind: MetricAdditive, Numerator: ColumnRequests, Threshold: 0.05,
	}})
	right, _ := NewMetricRegistry([]MetricDefinition{{
		Name: MetricRequests, Kind: MetricAdditive, Numerator: ColumnRequests, Threshold: 0.10,
	}})
	if left.Checksum() == right.Checksum() {
		t.Fatal("checksum should change with the effective definition")
	}
}
