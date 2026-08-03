package api

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/clickhouse"
	"github.com/view26/featurelens/internal/langfuse"
	"github.com/view26/featurelens/internal/orchestrator"
	"github.com/view26/featurelens/internal/store"
	"go.opentelemetry.io/otel"
)

type langfuseStub struct {
	insights langfuse.TraceInsights
	feedback langfuse.FeedbackRequest
}

func (stub *langfuseStub) Enabled() bool { return true }

func (stub *langfuseStub) TraceInsights(_ context.Context, traceID string) (langfuse.TraceInsights, error) {
	result := stub.insights
	result.TraceID = traceID
	return result, nil
}

func (stub *langfuseStub) CreateFeedback(_ context.Context, request langfuse.FeedbackRequest) ([]langfuse.Score, error) {
	stub.feedback = request
	return []langfuse.Score{{ID: "score-1", Name: "user_helpful", Value: request.Helpful, DataType: "BOOLEAN", Source: "API"}}, nil
}

func TestLangfuseTraceAndFeedbackEndpoints(t *testing.T) {
	baseline := agent.BaselineContext()
	engine := orchestrator.New(store.NewMemory(baseline), clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	stub := &langfuseStub{insights: langfuse.TraceInsights{
		Enabled: true, Status: "synced", Observations: []langfuse.Observation{{ID: "0123456789abcdef"}}, Scores: []langfuse.Score{},
	}}
	handler := New(engine, WithLangfuse(stub))
	traceID := "0123456789abcdef0123456789abcdef"

	read := httptest.NewRecorder()
	handler.ServeHTTP(read, httptest.NewRequest(http.MethodGet, "/api/traces/"+traceID+"/langfuse", nil))
	if read.Code != http.StatusOK {
		t.Fatalf("trace endpoint returned %d: %s", read.Code, read.Body.String())
	}

	bad := httptest.NewRecorder()
	handler.ServeHTTP(bad, httptest.NewRequest(http.MethodPost, "/api/traces/"+traceID+"/feedback", bytes.NewBufferString(`{"helpful":false,"issue":"invented"}`)))
	if bad.Code != http.StatusBadRequest {
		t.Fatalf("invalid feedback returned %d: %s", bad.Code, bad.Body.String())
	}

	feedback := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/traces/"+traceID+"/feedback", bytes.NewBufferString(`{"helpful":false,"issue":"missing_context","comment":"Missing city cut","observation_id":"0123456789abcdef"}`))
	request.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(feedback, request)
	if feedback.Code != http.StatusCreated {
		t.Fatalf("feedback endpoint returned %d: %s", feedback.Code, feedback.Body.String())
	}
	if stub.feedback.TraceID != traceID || stub.feedback.ObservationID != "0123456789abcdef" || stub.feedback.Helpful || stub.feedback.Issue != "missing_context" {
		t.Fatalf("feedback request was not validated and forwarded: %#v", stub.feedback)
	}
}
