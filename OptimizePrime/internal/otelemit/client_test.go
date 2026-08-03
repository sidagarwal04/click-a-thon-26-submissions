package otelemit_test

import (
	"context"
	"encoding/json"
	"io"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/d-cryptic/clickathon/internal/otelemit"
)

// capture records what the fake collector received, so tests assert on the
// actual wire request — method, path, headers, body — not on client internals.
type capture struct {
	mu     sync.Mutex
	method string
	path   string
	header http.Header
	body   []byte
}

func newCollector(t *testing.T, status int, respBody string) (*httptest.Server, *capture) {
	t.Helper()
	c := &capture{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Errorf("read request body: %v", err)
		}
		c.mu.Lock()
		c.method, c.path, c.header, c.body = r.Method, r.URL.Path, r.Header.Clone(), body
		c.mu.Unlock()
		w.WriteHeader(status)
		_, _ = io.WriteString(w, respBody)
	}))
	t.Cleanup(srv.Close)
	return srv, c
}

func testPayloads() (otelemit.MetricsPayload, otelemit.LogsPayload, otelemit.TracesPayload) {
	now := otelemit.UnixNano(time.Date(2026, 7, 26, 10, 56, 0, 0, time.UTC))
	res := otelemit.Resource{Attributes: []otelemit.KeyValue{otelemit.StringAttr("service.name", "sonyliv-pipeline")}}
	metrics := otelemit.MetricsPayload{ResourceMetrics: []otelemit.ResourceMetrics{{
		Resource: res,
		ScopeMetrics: []otelemit.ScopeMetrics{{
			Scope:   otelemit.Scope{Name: "test"},
			Metrics: []otelemit.Metric{otelemit.GaugeMetric("sonyliv.test.gauge", "a test gauge", "1", otelemit.Point(now, 2887))},
		}},
	}}}
	logs := otelemit.LogsPayload{ResourceLogs: []otelemit.ResourceLogs{{
		Resource: res,
		ScopeLogs: []otelemit.ScopeLogs{{
			Scope:      otelemit.Scope{Name: "test"},
			LogRecords: []otelemit.LogRecord{otelemit.Log(now, otelemit.SeverityInfo, "hello", nil, "", "")},
		}},
	}}}
	traces := otelemit.TracesPayload{ResourceSpans: []otelemit.ResourceSpans{{
		Resource: res,
		ScopeSpans: []otelemit.ScopeSpans{{
			Scope: otelemit.Scope{Name: "test"},
			Spans: []otelemit.Span{{
				TraceID: strings.Repeat("ab", 16), SpanID: strings.Repeat("cd", 8),
				Name: "test.span", Kind: otelemit.SpanKindInternal,
				StartTimeUnixNano: now, EndTimeUnixNano: now,
				Status: &otelemit.Status{Code: otelemit.StatusOK},
			}},
		}},
	}}}
	return metrics, logs, traces
}

// TestClientPostsEachSignalToItsPath pins the OTLP/HTTP contract per signal:
// POST, the /v1/<signal> suffix on the base endpoint, JSON content type, and
// the ingestion key in the `authorization` header (VERIFIED.md: no key = 401).
func TestClientPostsEachSignalToItsPath(t *testing.T) {
	t.Parallel()
	metrics, logs, traces := testPayloads()

	cases := []struct {
		name     string
		post     func(*otelemit.Client, context.Context) error
		wantPath string
	}{
		{"metrics", func(c *otelemit.Client, ctx context.Context) error { return c.PostMetrics(ctx, metrics) }, "/v1/metrics"},
		{"logs", func(c *otelemit.Client, ctx context.Context) error { return c.PostLogs(ctx, logs) }, "/v1/logs"},
		{"traces", func(c *otelemit.Client, ctx context.Context) error { return c.PostTraces(ctx, traces) }, "/v1/traces"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			srv, got := newCollector(t, http.StatusOK, "")
			client := otelemit.New(srv.URL, "test-ingestion-key")

			if err := tc.post(client, context.Background()); err != nil {
				t.Fatalf("Post%s error = %v, want nil", tc.name, err)
			}

			got.mu.Lock()
			defer got.mu.Unlock()
			if got.method != http.MethodPost {
				t.Errorf("method = %q, want POST", got.method)
			}
			if got.path != tc.wantPath {
				t.Errorf("path = %q, want %q", got.path, tc.wantPath)
			}
			if ct := got.header.Get("Content-Type"); ct != "application/json" {
				t.Errorf("Content-Type = %q, want application/json", ct)
			}
			if auth := got.header.Get("authorization"); auth != "test-ingestion-key" {
				t.Errorf("authorization = %q, want the ingestion key", auth)
			}
			if !json.Valid(got.body) {
				t.Errorf("body is not valid JSON: %q", got.body)
			}
		})
	}
}

// TestClientMetricsWireShape decodes what actually went over the wire and
// checks the OTLP JSON field names — resourceMetrics / scopeMetrics / gauge /
// dataPoints / asDouble — since a struct-tag typo would ingest as nothing.
func TestClientMetricsWireShape(t *testing.T) {
	t.Parallel()
	metrics, _, _ := testPayloads()
	srv, got := newCollector(t, http.StatusOK, "")
	client := otelemit.New(srv.URL, "k")

	if err := client.PostMetrics(context.Background(), metrics); err != nil {
		t.Fatalf("PostMetrics error = %v", err)
	}

	var wire struct {
		ResourceMetrics []struct {
			ScopeMetrics []struct {
				Metrics []struct {
					Name  string `json:"name"`
					Gauge struct {
						DataPoints []struct {
							TimeUnixNano string   `json:"timeUnixNano"`
							AsDouble     *float64 `json:"asDouble"`
						} `json:"dataPoints"`
					} `json:"gauge"`
				} `json:"metrics"`
			} `json:"scopeMetrics"`
		} `json:"resourceMetrics"`
	}
	got.mu.Lock()
	body := got.body
	got.mu.Unlock()
	if err := json.Unmarshal(body, &wire); err != nil {
		t.Fatalf("wire body did not decode as OTLP metrics JSON: %v\n%s", err, body)
	}
	m := wire.ResourceMetrics[0].ScopeMetrics[0].Metrics[0]
	if m.Name != "sonyliv.test.gauge" {
		t.Errorf("metric name on the wire = %q, want sonyliv.test.gauge", m.Name)
	}
	dp := m.Gauge.DataPoints[0]
	if dp.AsDouble == nil || *dp.AsDouble != 2887 {
		t.Errorf("asDouble = %v, want 2887", dp.AsDouble)
	}
	if dp.TimeUnixNano != "1785063360000000000" {
		t.Errorf("timeUnixNano = %q, want the decimal STRING \"1785063360000000000\"", dp.TimeUnixNano)
	}
}

// TestClientNon2xxIsAnError pins the failure contract: a 401 (the wrong or
// missing ingestion key) must produce an error naming the status and carrying
// the collector's response body, not a silent drop.
func TestClientNon2xxIsAnError(t *testing.T) {
	t.Parallel()
	metrics, _, _ := testPayloads()
	srv, _ := newCollector(t, http.StatusUnauthorized, `{"error":"invalid ingestion key"}`)
	client := otelemit.New(srv.URL, "wrong-key")

	err := client.PostMetrics(context.Background(), metrics)
	if err == nil {
		t.Fatal("PostMetrics error = nil, want HTTP 401 failure")
	}
	if !strings.Contains(err.Error(), "HTTP 401") {
		t.Errorf("error %q does not name the status code", err)
	}
	if !strings.Contains(err.Error(), "invalid ingestion key") {
		t.Errorf("error %q does not carry the collector's response body", err)
	}
}

func TestClientUnreachableCollectorIsAnError(t *testing.T) {
	t.Parallel()
	_, logs, _ := testPayloads()
	// A server that existed and is gone — the realistic `make stack-down` case.
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	endpoint := srv.URL
	srv.Close()

	err := otelemit.New(endpoint, "k").PostLogs(context.Background(), logs)
	if err == nil {
		t.Fatal("PostLogs error = nil, want a connection failure")
	}
	if !strings.Contains(err.Error(), "/v1/logs") {
		t.Errorf("error %q does not name which signal path failed", err)
	}
}

// TestClientUnmarshalablePayloadFailsBeforePosting: a NaN gauge value cannot
// be marshaled to JSON. The client must fail at marshal time — before any
// bytes hit the network — rather than posting a truncated payload.
func TestClientUnmarshalablePayloadFailsBeforePosting(t *testing.T) {
	t.Parallel()
	srv, got := newCollector(t, http.StatusOK, "")
	client := otelemit.New(srv.URL, "k")

	now := otelemit.UnixNano(time.Now())
	bad := otelemit.MetricsPayload{ResourceMetrics: []otelemit.ResourceMetrics{{
		ScopeMetrics: []otelemit.ScopeMetrics{{
			Metrics: []otelemit.Metric{otelemit.GaugeMetric("bad", "", "1", otelemit.Point(now, math.NaN()))},
		}},
	}}}

	err := client.PostMetrics(context.Background(), bad)
	if err == nil {
		t.Fatal("PostMetrics(NaN) error = nil, want a marshal failure")
	}
	if !strings.Contains(err.Error(), "marshal") {
		t.Errorf("error %q does not say it failed at marshal", err)
	}
	got.mu.Lock()
	defer got.mu.Unlock()
	if got.method != "" {
		t.Error("collector received a request; a marshal failure must not POST anything")
	}
}
