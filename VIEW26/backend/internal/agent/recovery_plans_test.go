package agent

import (
	"strings"
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

func TestRecoveryQuestionsCompileToDistinctPlans(t *testing.T) {
	profile := domain.EventProfile{
		EventOrder: []string{"abandonment_detected", "reminder_sent", "reminder_opened", "reminder_cta_clicked", "resumed_at_step", "reconverted"},
		Fields: []domain.FieldProfile{
			{ColumnName: "application_id"}, {ColumnName: "drop_step"}, {ColumnName: "channel"},
			{ColumnName: "hours_since_drop"}, {ColumnName: "device_type"}, {ColumnName: "geoip_country_code"}, {ColumnName: "destination"},
		},
	}
	input := domain.FeatureInput{Name: "Abandoned Checkout Recovery", Slug: "abandoned_checkout_recovery"}
	schema := domain.SchemaProposal{Database: "featurelens_poc", Table: "abandoned_checkout_recovery_events_v2"}
	questions := []string{
		"Reconversion rate by drop_step — which step is most recoverable?",
		"Which channel recovers best (open → click → reconvert)?",
		"Does timing (hours_since_drop) matter — send at 1h vs 24h vs 48h?",
		"Segment cuts by device, geo, and destination.",
	}
	plans := map[string]bool{}
	sql := map[string]bool{}
	for _, question := range questions {
		plan := buildAnalysisPlan(question, input, profile, schema, "atlys")
		if plan.Answerability == "not_answerable" || strings.TrimSpace(plan.SQL) == "" {
			t.Fatalf("question %q did not compile to an executable plan: %#v", question, plan)
		}
		plans[plan.ID] = true
		sql[strings.Join(strings.Fields(plan.SQL), " ")] = true
	}
	if len(plans) != len(questions) || len(sql) != len(questions) {
		t.Fatalf("expected four distinct recovery plans and SQL queries, got %d plans and %d queries", len(plans), len(sql))
	}
}

func TestRecoveryContextLinksQuestionsToCompiledPlaybooks(t *testing.T) {
	profile := domain.EventProfile{
		Rows:        4,
		EventCounts: map[string]int{"abandonment_detected": 2, "reminder_sent": 1, "reconverted": 1},
		EventOrder:  []string{"abandonment_detected", "reminder_sent", "reconverted"},
		Fields:      []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "drop_step"}, {ColumnName: "channel"}, {ColumnName: "hours_since_drop"}, {ColumnName: "device_type"}},
	}
	input := domain.FeatureInput{
		Name: "Abandoned Checkout Recovery", Slug: "abandoned_checkout_recovery",
		SpecMarkdown: "## Questions the PM will ask\n- Which drop_step is most recoverable?\n- Which channel recovers best?\n- Does hours_since_drop timing matter?\n- Segment cuts by device?",
	}
	schema := domain.SchemaProposal{Version: 2, Database: "featurelens_poc", Table: "abandoned_checkout_recovery_events_v2"}
	graph := (ContextAgent{}).Evolve(BaselineContext(), input, profile, schema, "trace", "published")
	for _, expected := range []string{"playbook:recovery-drop-step:v1", "playbook:recovery-channel:v1", "playbook:recovery-timing:v1", "playbook:recovery-segments:v1"} {
		if !contextHasNode(graph.Nodes, expected) {
			t.Fatalf("context did not publish compiled playbook %s", expected)
		}
	}
}
