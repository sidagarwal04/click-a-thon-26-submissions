package orchestrator

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/clickhouse"
	"github.com/view26/featurelens/internal/domain"
	"github.com/view26/featurelens/internal/store"
	"go.opentelemetry.io/otel"
)

func TestFeatureEvolutionPublishesContextAndPassesGates(t *testing.T) {
	memory := store.NewMemory(agent.BaselineContext())
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	run, err := engine.Start(context.Background(), domain.FeatureInput{
		Name: "Express Checkout", Role: "product_manager", AutoApprove: true,
		SpecMarkdown: "# Express Checkout\n\n## Questions the PM will ask\n- Does Express lift conversion vs standard checkout?\n- Is there a platform where OTP fails more? Cut OTP success\n  and confirmation by device and OS.\n- How much faster is Express?\n- Which segments adopt Express most?",
		EventsNDJSON: `{"event":"express_shown","id":"e1","timestamp":"2026-06-08T06:00:00.000","user_id":"u1","application_id":"a1","device_type":"ios","os":"iOS","geoip_country_code":"IN"}
{"event":"express_selected","id":"e2","timestamp":"2026-06-08T06:00:20.000","user_id":"u1","application_id":"a1","device_type":"ios","os":"iOS","geoip_country_code":"IN","saved_method_type":"card"}
{"event":"otp_entered","id":"e3","timestamp":"2026-06-08T06:00:40.000","user_id":"u1","application_id":"a1","device_type":"ios","os":"iOS","geoip_country_code":"IN","otp_success":true}
{"event":"express_completed","id":"e4","timestamp":"2026-06-08T06:01:00.000","user_id":"u1","application_id":"a1","device_type":"ios","os":"iOS","geoip_country_code":"IN","payment":{"latency_ms":2000}}`,
	})
	if err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		current, _ := memory.GetRun(run.ID)
		if current.Stage == domain.StageCompleted {
			if current.Context == nil || current.Context.Version != 1 {
				t.Fatalf("context was not published: %#v", current.Context)
			}
			for _, evaluation := range current.Evaluations {
				if !evaluation.Passed {
					t.Fatalf("evaluation failed: %#v", evaluation)
				}
			}
			if len(current.QuestionAnswers) != 4 {
				t.Fatalf("expected four declared question answers, got %d", len(current.QuestionAnswers))
			}
			if current.AnalyticsBundle == nil || len(current.AnalyticsBundle.Insights) != 3 || len(current.AnalyticsBundle.Charts) == 0 {
				t.Fatalf("feature analytics bundle was not published: %#v", current.AnalyticsBundle)
			}
			plans := map[string]bool{}
			for _, answer := range current.QuestionAnswers {
				plans[answer.Contract.Playbook] = true
			}
			if len(plans) != 4 {
				t.Fatalf("expected four distinct playbooks, got %#v", plans)
			}
			return
		}
		if current.Stage == domain.StageFailed {
			t.Fatalf("run failed: %s", current.Error)
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("run did not complete")
}

func TestResetIsRejectedWhileRunAwaitsApproval(t *testing.T) {
	memory := store.NewMemory(agent.BaselineContext())
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	run, err := engine.Start(context.Background(), domain.FeatureInput{
		Name: "Unseen feature", Role: "product_manager",
		SpecMarkdown: "# Unseen\n\n- Does this feature complete?",
		EventsNDJSON: `{"event":"unseen_started","id":"u1","timestamp":"2026-08-01T08:00:00Z","application_id":"a1"}
{"event":"unseen_completed","id":"u2","timestamp":"2026-08-01T08:01:00Z","application_id":"a1"}`,
	})
	if err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		current, _ := memory.GetRun(run.ID)
		if current.Stage == domain.StageAwaitingApproval {
			if _, resetErr := engine.Reset(context.Background()); resetErr == nil {
				t.Fatal("reset was allowed while a run awaited approval")
			}
			if err := engine.Approve(run.ID); err != nil {
				t.Fatal(err)
			}
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("run did not reach approval gate")
}

func TestApproveIsIdempotentAfterApprovalGate(t *testing.T) {
	memory := store.NewMemory(agent.BaselineContext())
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	run, err := engine.Start(context.Background(), domain.FeatureInput{
		Name: "Retry safe approval", Role: "product_manager",
		SpecMarkdown: "# Retry safe approval\n\n- Does this feature complete?",
		EventsNDJSON: `{"event":"retry_started","id":"r1","timestamp":"2026-08-01T08:00:00Z","application_id":"a1"}
{"event":"retry_completed","id":"r2","timestamp":"2026-08-01T08:01:00Z","application_id":"a1"}`,
	})
	if err != nil {
		t.Fatal(err)
	}

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		current, _ := memory.GetRun(run.ID)
		if current.Stage == domain.StageAwaitingApproval {
			if err := engine.Approve(run.ID); err != nil {
				t.Fatalf("first approval failed: %v", err)
			}
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	deadline = time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		current, _ := memory.GetRun(run.ID)
		if approvalWasAccepted(current.Stage) {
			if err := engine.Approve(run.ID); err != nil {
				t.Fatalf("duplicate approval at %s failed: %v", current.Stage, err)
			}
			return
		}
		if current.Stage == domain.StageFailed {
			t.Fatalf("run failed: %s", current.Error)
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("run did not cross the approval gate")
}

func TestApproveStillRejectsRunsBeforeApprovalGate(t *testing.T) {
	memory := store.NewMemory(agent.BaselineContext())
	memory.CreateRun(domain.FeatureRun{ID: "run_not_ready", Stage: domain.StageSchemaValidated})
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")

	if err := engine.Approve("run_not_ready"); err == nil {
		t.Fatal("approval was accepted before the human gate")
	}
}

func TestStartIsIdempotentForSameFeatureAndSchemaVersion(t *testing.T) {
	memory := store.NewMemory(agent.BaselineContext())
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	input := domain.FeatureInput{
		Name: "Unseen feature", SchemaVersion: 1, Role: "product_manager", AutoApprove: true,
		SpecMarkdown: "# Unseen\n\n- Does this feature complete?",
		EventsNDJSON: `{"event":"unseen_started","id":"u1","timestamp":"2026-08-01T08:00:00Z","application_id":"a1"}
{"event":"unseen_completed","id":"u2","timestamp":"2026-08-01T08:01:00Z","application_id":"a1"}`,
	}
	first, err := engine.Start(context.Background(), input)
	if err != nil {
		t.Fatal(err)
	}
	second, err := engine.Start(context.Background(), input)
	if err != nil {
		t.Fatal(err)
	}
	if first.ID != second.ID || len(memory.ListRuns()) != 1 {
		t.Fatalf("duplicate run created: first=%s second=%s count=%d", first.ID, second.ID, len(memory.ListRuns()))
	}
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		current, _ := memory.GetRun(first.ID)
		if current.Stage == domain.StageCompleted {
			return
		}
		if current.Stage == domain.StageFailed {
			t.Fatalf("run failed: %s", current.Error)
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("idempotent run did not complete")
}

func TestRefreshAnalyticsRebuildsExistingDecisionInboxWithCurrentGuardrails(t *testing.T) {
	baseline := agent.BaselineContext()
	graph := baseline
	graph.Version = 1
	graph.ParentVersion = 0
	graph.Nodes = append(graph.Nodes, domain.ContextNode{Key: "feature:status_sharing", Type: "feature", Name: "Status Sharing", Status: "verified", Confidence: 1})
	memory := store.NewMemory(baseline)
	if err := memory.PublishContext(graph); err != nil {
		t.Fatal(err)
	}
	profile := domain.EventProfile{
		Rows: 2, EventOrder: []string{"link_generated", "recipient_cta_clicked"}, EventCounts: map[string]int{"link_generated": 1, "recipient_cta_clicked": 1},
		Fields: []domain.FieldProfile{{ColumnName: "id"}, {ColumnName: "share_id"}, {ColumnName: "timestamp"}},
	}
	schema := domain.SchemaProposal{Version: 2, Database: "featurelens_test", Table: "status_sharing_events_v2", Status: "verified"}
	now := time.Now().UTC()
	run := domain.FeatureRun{
		ID: "run_status", Stage: domain.StageCompleted, CreatedAt: now, UpdatedAt: now, Context: &graph, Profile: &profile, Schema: &schema,
		Input: domain.FeatureInput{Name: "Status Sharing", Slug: "status_sharing", Role: "product_manager", SpecMarkdown: "# Status Sharing\n\n- Who shares and who engages?\n- Does sharing reduce support demand?", EventsNDJSON: `{"event":"link_generated","id":"1","share_id":"s1","timestamp":"2026-01-01T00:00:00Z"}
{"event":"recipient_cta_clicked","id":"2","share_id":"s1","timestamp":"2026-01-01T00:01:00Z"}`},
		QuestionAnswers: []domain.QuestionResponse{{Contract: domain.AnalysisContract{Intent: "feature_completion"}, Insight: domain.Insight{Headline: "stale false claim"}}},
	}
	memory.CreateRun(run)
	engine := New(memory, clickhouse.NewDisabled(), otel.Tracer("test"), "featurelens_test")
	refreshed, err := engine.RefreshAnalytics(context.Background(), run.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(refreshed.QuestionAnswers) != 2 {
		t.Fatalf("expected both declared questions to be rebuilt: %#v", refreshed.QuestionAnswers)
	}
	completion, support := refreshed.QuestionAnswers[0], refreshed.QuestionAnswers[1]
	if completion.Contract.Grain != "unique share_id within the selected period" || !strings.Contains(completion.Insight.SQL, "link_generated") || !strings.Contains(completion.Insight.SQL, "recipient_cta_clicked") {
		t.Fatalf("sharing completion kept the stale application funnel: %#v", completion)
	}
	if support.Contract.Intent != "support_demand_impact" || support.Contract.Answerability != "not_answerable" || support.Insight.SQL != "" {
		t.Fatalf("unsupported support claim did not fail closed on refresh: %#v", support)
	}
	if refreshed.AnalyticsBundle == nil || len(refreshed.AnalyticsBundle.Insights) != 1 || refreshed.AnalyticsBundle.Insights[0].Headline == "stale false claim" {
		t.Fatalf("Decision Inbox retained an unsupported or stale claim: %#v", refreshed.AnalyticsBundle)
	}
}
