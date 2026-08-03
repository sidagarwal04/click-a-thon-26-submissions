package store

import (
	"testing"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
)

func TestResetRestoresOnlyBaselineState(t *testing.T) {
	baseline := agent.BaselineContext()
	memory := NewMemory(baseline)
	next := baseline
	next.Version = 1
	next.ParentVersion = 0
	if err := memory.PublishContext(next); err != nil {
		t.Fatal(err)
	}
	memory.CreateRun(domain.FeatureRun{ID: "run_1", Stage: domain.StageCompleted, CreatedAt: time.Now(), UpdatedAt: time.Now()})
	stream, _ := memory.Subscribe("run_1")

	memory.Reset(baseline)

	if got := len(memory.ListRuns()); got != 0 {
		t.Fatalf("expected no runs after reset, got %d", got)
	}
	if got := memory.LatestContext().Version; got != 0 {
		t.Fatalf("expected context v0 after reset, got v%d", got)
	}
	if _, ok := memory.Context(1); ok {
		t.Fatal("context v1 survived reset")
	}
	if _, open := <-stream; open {
		t.Fatal("subscriber was not closed by reset")
	}
}

func TestQuarantineContextKeepsLatestUnchanged(t *testing.T) {
	baseline := agent.BaselineContext()
	memory := NewMemory(baseline)

	rejected := baseline
	rejected.Version = 1
	rejected.ParentVersion = 0
	rejected.State = "rejected"
	memory.QuarantineContext(rejected)

	if got := memory.LatestContext().Version; got != 0 {
		t.Fatalf("quarantined candidate became latest: v%d", got)
	}
	if _, ok := memory.Context(1); ok {
		t.Fatal("quarantined candidate is addressable as a published version")
	}
	if got := len(memory.RejectedContexts()); got != 1 {
		t.Fatalf("expected one quarantined candidate, got %d", got)
	}

	// A later successful evolution legitimately reuses the version number.
	published := baseline
	published.Version = 1
	published.ParentVersion = 0
	published.State = "published"
	if err := memory.PublishContext(published); err != nil {
		t.Fatalf("publish after quarantine failed: %v", err)
	}
	if got := memory.LatestContext().Version; got != 1 {
		t.Fatalf("expected v1 to publish after quarantine, got v%d", got)
	}
}

func TestRestoreHydratesPublishedContextsAndFeatureReleases(t *testing.T) {
	baseline := agent.BaselineContext()
	memory := NewMemory(baseline)
	next := baseline
	next.Version = 2
	next.ParentVersion = 1
	next.Feature = "status_sharing"
	now := time.Now()
	oldRun := domain.FeatureRun{ID: "run_status_old", Input: domain.FeatureInput{Name: "Status Sharing", SchemaVersion: 2}, Stage: domain.StageCompleted, CreatedAt: now.Add(-time.Hour), UpdatedAt: now.Add(-time.Hour)}
	run := domain.FeatureRun{ID: "run_status", Input: domain.FeatureInput{Name: "Status Sharing", SchemaVersion: 2}, Stage: domain.StageCompleted, CreatedAt: now, UpdatedAt: now}
	if err := memory.Restore([]domain.ContextVersion{baseline, next}, []domain.FeatureRun{oldRun, run}); err != nil {
		t.Fatal(err)
	}
	if memory.LatestContext().Version != 2 {
		t.Fatalf("latest durable context was not restored: v%d", memory.LatestContext().Version)
	}
	if restored, ok := memory.GetRun(run.ID); !ok || restored.Input.Name != "Status Sharing" {
		t.Fatalf("durable feature release was not restored: %#v ok=%t", restored, ok)
	}
	if len(memory.ListRuns()) != 1 {
		t.Fatalf("historical retries were restored as duplicate releases: %#v", memory.ListRuns())
	}
}
