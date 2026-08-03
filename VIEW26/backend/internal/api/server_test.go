package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/clickhouse"
	"github.com/view26/featurelens/internal/domain"
	"github.com/view26/featurelens/internal/orchestrator"
	"github.com/view26/featurelens/internal/store"
	"go.opentelemetry.io/otel"
)

func TestApproveEndpointIsIdempotentAfterGate(t *testing.T) {
	memory := store.NewMemory(agent.BaselineContext())
	memory.CreateRun(domain.FeatureRun{
		ID:        "run_approved",
		Stage:     domain.StageContextCandidate,
		CreatedAt: time.Now().UTC(),
		UpdatedAt: time.Now().UTC(),
	})
	engine := orchestrator.New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	handler := New(engine)

	request := httptest.NewRequest(http.MethodPost, "/api/runs/run_approved/approve", nil)
	result := httptest.NewRecorder()
	handler.ServeHTTP(result, request)
	if result.Code != http.StatusAccepted {
		t.Fatalf("expected duplicate approval to return 202, got %d: %s", result.Code, result.Body.String())
	}
	var payload struct {
		Approved        bool   `json:"approved"`
		AlreadyApproved bool   `json:"already_approved"`
		Stage           string `json:"stage"`
	}
	if err := json.Unmarshal(result.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	if !payload.Approved || !payload.AlreadyApproved || payload.Stage != string(domain.StageContextCandidate) {
		t.Fatalf("unexpected approval response: %#v", payload)
	}
}

func TestResetEndpointRequiresConfirmationAndRestoresV0(t *testing.T) {
	baseline := agent.BaselineContext()
	memory := store.NewMemory(baseline)
	next := baseline
	next.Version = 1
	next.ParentVersion = 0
	if err := memory.PublishContext(next); err != nil {
		t.Fatal(err)
	}
	engine := orchestrator.New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	handler := New(engine)

	bad := httptest.NewRequest(http.MethodPost, "/api/admin/reset", bytes.NewBufferString(`{"confirmation":"RESET"}`))
	bad.Header.Set("Content-Type", "application/json")
	badResult := httptest.NewRecorder()
	handler.ServeHTTP(badResult, bad)
	if badResult.Code != http.StatusBadRequest {
		t.Fatalf("expected bad confirmation to return 400, got %d", badResult.Code)
	}

	request := httptest.NewRequestWithContext(context.Background(), http.MethodPost, "/api/admin/reset", bytes.NewBufferString(`{"confirmation":"RESET_CONTEXT"}`))
	request.Header.Set("Content-Type", "application/json")
	result := httptest.NewRecorder()
	handler.ServeHTTP(result, request)
	if result.Code != http.StatusOK {
		t.Fatalf("expected reset to return 200, got %d: %s", result.Code, result.Body.String())
	}
	if got := memory.LatestContext().Version; got != 0 {
		t.Fatalf("expected baseline v0, got v%d", got)
	}
}
