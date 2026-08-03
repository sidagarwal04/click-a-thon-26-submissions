package llm

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"clickhouse-go-service/internal/config"
)

func TestGenerateJSONUsesResponsesStructuredOutput(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/responses" {
			t.Errorf("path = %q", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer test-key" {
			t.Error("missing bearer authorization")
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		text, ok := body["text"].(map[string]any)
		if !ok || text["format"] == nil {
			t.Errorf("request does not contain structured text format: %#v", body)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"resp_test","status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"{\"answer\":\"ok\"}"}]}]}`))
	}))
	defer server.Close()

	cfg := config.LLMConfig{APIKey: "test-key", BaseURL: server.URL + "/v1", ReasoningEffort: "low", RequestTimeout: time.Second, MaxOutputTokens: 100}
	client := NewClientWithHTTP(cfg, server.Client())
	var output struct {
		Answer string `json:"answer"`
	}
	_, err := client.GenerateJSON(context.Background(), "test-model", "test_schema", "Return JSON", "input", map[string]any{
		"type": "object", "properties": map[string]any{"answer": map[string]any{"type": "string"}},
		"required": []string{"answer"}, "additionalProperties": false,
	}, &output)
	if err != nil {
		t.Fatal(err)
	}
	if output.Answer != "ok" {
		t.Fatalf("answer = %q", output.Answer)
	}
}
