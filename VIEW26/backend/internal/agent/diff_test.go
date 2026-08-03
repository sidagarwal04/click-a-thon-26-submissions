package agent

import (
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

func TestDiffContextsBaselineToEvolvedVersion(t *testing.T) {
	contextAgent := ContextAgent{}
	parent := BaselineContext()
	input := domain.FeatureInput{Name: "Express Checkout", Slug: "express_checkout", SpecMarkdown: "# Express Checkout\n- Does it lift conversion?"}
	profile := domain.EventProfile{Rows: 10, EventOrder: []string{"express_checkout_shown"}, EventCounts: map[string]int{"express_checkout_shown": 10}}
	child := contextAgent.Evolve(parent, input, profile, domain.SchemaProposal{Database: "featurelens_poc", Table: "express_checkout_events_v1", Version: 1}, "trace-diff", "published")

	diff := DiffContexts(parent, child)
	if diff.FromVersion != parent.Version || diff.ToVersion != child.Version {
		t.Fatalf("diff versions wrong: %#v", diff)
	}
	if len(diff.AddedNodes) == 0 || len(diff.AddedEdges) == 0 {
		t.Fatalf("evolution delta was not captured: %d nodes %d edges", len(diff.AddedNodes), len(diff.AddedEdges))
	}
	if len(diff.RemovedNodeKeys) != 0 {
		t.Fatalf("copy-on-write evolution must never remove parent nodes: %#v", diff.RemovedNodeKeys)
	}
	addedFeature := false
	for _, node := range diff.AddedNodes {
		if node.Key == "feature:express_checkout" {
			addedFeature = true
		}
	}
	if !addedFeature {
		t.Fatal("diff does not list the new feature node as added")
	}
}

func TestDiffContextsDetectsChangedAndRemovedNodes(t *testing.T) {
	from := domain.ContextVersion{Version: 1, Nodes: []domain.ContextNode{
		{Key: "table:atlys.search_typed", Type: "table", Name: "search_typed", Status: "declared", Confidence: .9},
		{Key: "metric:gone", Type: "metric", Name: "dropped metric", Status: "declared", Confidence: .9},
	}}
	to := domain.ContextVersion{Version: 2, Nodes: []domain.ContextNode{
		{Key: "table:atlys.search_typed", Type: "table", Name: "search_typed", Status: "observed", Confidence: .98},
	}}
	diff := DiffContexts(from, to)
	if len(diff.ChangedNodes) != 1 || diff.ChangedNodes[0].Key != "table:atlys.search_typed" {
		t.Fatalf("declared -> observed upgrade was not detected: %#v", diff.ChangedNodes)
	}
	if len(diff.RemovedNodeKeys) != 1 || diff.RemovedNodeKeys[0] != "metric:gone" {
		t.Fatalf("removed node was not detected: %#v", diff.RemovedNodeKeys)
	}
}

func TestCompactContextQuarantinesContradictedDefinitions(t *testing.T) {
	graph := BaselineContext()
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{Role: "product_manager", Feature: "conversion", Question: "How is conversion?"})

	for _, node := range contextSlice["nodes"].([]map[string]any) {
		if node["key"] == "metric:leadership-conversion" {
			t.Fatal("contradicted definition reached the usable node list")
		}
	}
	quarantined := contextSlice["quarantined_definitions"].([]map[string]any)
	found := false
	for _, warning := range quarantined {
		if warning["key"] == "metric:leadership-conversion" {
			found = true
			if warning["superseded_by"] != "metric:funnel-conversion" {
				t.Fatalf("quarantined definition does not point at the canonical metric: %#v", warning)
			}
			if _, leaked := warning["properties"]; leaked {
				t.Fatalf("quarantined definition leaked its formula: %#v", warning)
			}
		}
	}
	if !found {
		t.Fatalf("contradicted metric was not quarantined: %#v", quarantined)
	}
}

func TestRelevantIssuesIgnoreQuestionWording(t *testing.T) {
	graph := domain.ContextVersion{
		Nodes: []domain.ContextNode{
			{Key: "issue:K1-ios-otp", Type: "known_issue", Name: "iOS WebKit OTP autofill regression"},
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout"},
		},
		Edges: []domain.ContextEdge{
			{From: "issue:K1-ios-otp", Relation: "MAY_AFFECT", To: "feature:express_checkout"},
		},
	}
	input := domain.FeatureInput{Name: "Express Checkout"}
	issues := relevantIssues(graph, input, "Why do Apple users complete purchases less often?")
	if len(issues) != 1 || issues[0] != "iOS WebKit OTP autofill regression" {
		t.Fatalf("linked issue was dropped for a reworded question: %#v", issues)
	}
}

func TestResolveIntentFromGraphRoutesParaphrases(t *testing.T) {
	graph := domain.ContextVersion{Nodes: []domain.ContextNode{
		{Key: "question:express_checkout:1", Type: "business_question", Name: "Is there a platform where OTP fails more?", Properties: map[string]any{"intent": "platform_failure"}},
		{Key: "question:other_feature:1", Type: "business_question", Name: "Is there a platform where OTP fails more?", Properties: map[string]any{"intent": "feature_completion"}},
	}}
	intent, ok := resolveIntentFromGraph(graph, "express_checkout", "Is there a platform where OTP fails more often?")
	if !ok || intent != "platform_failure" {
		t.Fatalf("paraphrase did not route through the graph: %q %v", intent, ok)
	}
	if _, ok := resolveIntentFromGraph(graph, "express_checkout", "What colour should the button be?"); ok {
		t.Fatal("a novel question must fall back to the keyword classifier")
	}
}
