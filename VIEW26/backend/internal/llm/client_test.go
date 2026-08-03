package llm

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
	"go.opentelemetry.io/otel"
)

func TestClientSynthesizesStructuredInsightFromGovernedInput(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer secret" {
			t.Fatal("missing bearer token")
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		messages := request["messages"].([]any)
		user := messages[1].(map[string]any)["content"].(string)
		if !strings.Contains(user, "feature_completion_rate") || strings.Contains(user, "raw-event-row") {
			t.Fatalf("request was not governed aggregate context: %s", user)
		}
		format := request["response_format"].(map[string]any)
		if format["type"] != "json_schema" || format["json_schema"].(map[string]any)["strict"] != true {
			t.Fatalf("strict structured output was not requested: %#v", format)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"{\"headline\":\"Express is up\",\"summary\":\"Conversion improved in the aligned window.\",\"why\":\"The verified aggregate is higher.\",\"confidence\":0.8,\"recommended_action\":\"Validate with an experiment.\"}"}}]}`))
	}))
	defer server.Close()

	client := New(Config{Provider: "test", BaseURL: server.URL, APIKey: "secret", Model: "test-model", Timeout: time.Second}, otel.Tracer("test"))
	result, err := client.Synthesize(context.Background(), agent.InsightSynthesisRequest{
		Contract: domain.AnalysisContract{Role: "product_manager", Playbook: "playbook:conversion-comparison:v1", ContextVersion: 1},
		Context:  map[string]any{"context_version": 1},
		Evidence: map[string]any{"feature_completion_rate": .51},
		Draft:    domain.Insight{Headline: "draft"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Headline != "Express is up" || result.Confidence != .8 {
		t.Fatalf("unexpected result %#v", result)
	}
}

func TestOpenRouterRequiresStructuredOutputCapableProvider(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		provider := request["provider"].(map[string]any)
		if provider["require_parameters"] != true {
			t.Fatalf("OpenRouter provider routing is not constrained: %#v", provider)
		}
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"{\"headline\":\"Finding\",\"summary\":\"Summary\",\"why\":\"Why\",\"confidence\":0.8,\"recommended_action\":\"Act\"}"}}]}`))
	}))
	defer server.Close()
	client := New(Config{Provider: "openrouter", BaseURL: server.URL, APIKey: "secret", Model: "openai/gpt-4.1-mini"}, otel.Tracer("test"))
	if _, err := client.Synthesize(context.Background(), agent.InsightSynthesisRequest{}); err != nil {
		t.Fatal(err)
	}
}

func TestClientRejectsInvalidStructuredInsight(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"{\"headline\":\"Invented\",\"summary\":\"x\",\"why\":\"x\",\"confidence\":1.5,\"recommended_action\":\"x\"}"}}]}`))
	}))
	defer server.Close()
	client := New(Config{BaseURL: server.URL, APIKey: "secret", Model: "test-model"}, otel.Tracer("test"))
	_, err := client.Synthesize(context.Background(), agent.InsightSynthesisRequest{})
	if err == nil {
		t.Fatal("expected invalid confidence to be rejected")
	}
}
