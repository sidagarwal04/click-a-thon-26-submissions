package langfuse

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sort"
	"testing"
	"time"
)

func TestTraceInsightsReadsObservationFirstAPIs(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		username, password, ok := r.BasicAuth()
		if !ok || username != "public" || password != "secret" {
			t.Fatalf("missing Langfuse basic auth")
		}
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/public/v2/observations":
			if r.URL.Query().Get("traceId") != "0123456789abcdef0123456789abcdef" || r.URL.Query().Get("fields") == "" {
				t.Fatalf("observation request lost its trace filter: %s", r.URL.RawQuery)
			}
			_, _ = w.Write([]byte(`{"data":[{"id":"0123456789abcdef","traceId":"0123456789abcdef0123456789abcdef","projectId":"project-1","name":"analytics.portfolio_conversation","type":"AGENT","input":"{\"question\":\"Where is loss?\"}","output":"{\"headline\":\"OTP\"}","latency":1.25},{"id":"fedcba9876543210","traceId":"0123456789abcdef0123456789abcdef","projectId":"project-1","parentObservationId":"0123456789abcdef","name":"analytics.llm_synthesize","type":"GENERATION","providedModelName":"test-model","usageDetails":{"total":123},"totalCost":"0.0125","latency":0.8}],"meta":{"cursor":null}}`))
		case "/api/public/v3/scores":
			_, _ = w.Write([]byte(`{"data":[{"id":"score-1","name":"groundedness","value":0.94,"dataType":"NUMERIC","source":"EVAL","comment":"Evidence aligned","subject":{"kind":"observation","id":"fedcba9876543210","traceId":"0123456789abcdef0123456789abcdef"}}],"meta":{"cursor":null}}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	client := New(Config{BaseURL: server.URL, PublicKey: "public", SecretKey: "secret", HTTPClient: &http.Client{Timeout: time.Second}})
	insights, err := client.TraceInsights(context.Background(), "0123456789abcdef0123456789abcdef")
	if err != nil {
		t.Fatal(err)
	}
	if insights.Status != "synced" || len(insights.Observations) != 2 || len(insights.Scores) != 1 {
		t.Fatalf("unexpected trace insight: %#v", insights)
	}
	if insights.Observations[0].Input.(map[string]any)["question"] != "Where is loss?" {
		t.Fatalf("observation input was not normalized from JSON: %#v", insights.Observations[0].Input)
	}
	if insights.Summary.TotalCost != .0125 || insights.Summary.TotalTokens != 123 || insights.Summary.Latency != 1.25 {
		t.Fatalf("trace summary is incorrect: %#v", insights.Summary)
	}
	if insights.URL != server.URL+"/project/project-1/traces/0123456789abcdef0123456789abcdef" {
		t.Fatalf("unexpected trace URL %q", insights.URL)
	}
}

func TestCreateFeedbackWritesTypedIdempotentScores(t *testing.T) {
	written := []map[string]any{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/public/scores" || r.Method != http.MethodPost {
			t.Fatalf("unexpected request %s %s", r.Method, r.URL.Path)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		written = append(written, body)
		w.Header().Set("Content-Type", "application/json")
		response := map[string]any{
			"id": body["id"], "name": body["name"], "value": body["value"], "dataType": body["dataType"], "source": "API",
			"subject": map[string]any{"kind": "observation", "id": body["observationId"], "traceId": body["traceId"]},
		}
		_ = json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := New(Config{BaseURL: server.URL, PublicKey: "public", SecretKey: "secret"})
	created, err := client.CreateFeedback(context.Background(), FeedbackRequest{
		TraceID: "0123456789abcdef0123456789abcdef", ObservationID: "0123456789abcdef",
		Helpful: false, Issue: "missing_context", Comment: "City cut is absent", Actor: "product_manager",
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(created) != 2 || len(written) != 2 {
		t.Fatalf("expected helpful and issue scores, got created=%d written=%d", len(created), len(written))
	}
	names := []string{written[0]["name"].(string), written[1]["name"].(string)}
	sort.Strings(names)
	if names[0] != "issue_category" || names[1] != "user_helpful" {
		t.Fatalf("unexpected feedback scores: %#v", names)
	}
	for _, item := range written {
		if item["id"] == "" || item["traceId"] == "" || item["observationId"] == "" {
			t.Fatalf("score lost correlation or idempotency fields: %#v", item)
		}
	}
}
