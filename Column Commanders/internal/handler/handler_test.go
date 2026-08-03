package handler

import (
	"net/http/httptest"
	"testing"
)

func TestRouteIDFallsBackToRouterURLPath(t *testing.T) {
	request := httptest.NewRequest("GET", "/api/v2/episodes/5c809276-6096-52ab-bb1d-acf337b5a896", nil)
	got := routeID(request, "/api/v2/episodes/")
	if want := "5c809276-6096-52ab-bb1d-acf337b5a896"; got != want {
		t.Fatalf("routeID() = %q, want %q", got, want)
	}
}

func TestRouteIDPrefersStandardPathValue(t *testing.T) {
	request := httptest.NewRequest("GET", "/ignored", nil)
	request.SetPathValue("id", "standard-id")
	if got := routeID(request, "/api/v2/episodes/"); got != "standard-id" {
		t.Fatalf("routeID() = %q, want standard-id", got)
	}
}

func TestV1SupportedMetrics(t *testing.T) {
	for _, metric := range []string{"revenue", "fill_rate", "ecpm", "ctr", "requests"} {
		if !isV1MetricSupported(metric) {
			t.Errorf("expected %q to be supported", metric)
		}
	}
	for _, metric := range []string{"render_rate", "unknown"} {
		if isV1MetricSupported(metric) {
			t.Errorf("expected %q to be rejected", metric)
		}
	}
}
