package agent

import (
	"fmt"
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

func TestBaselineDeclaresAllCanonicalSourceTables(t *testing.T) {
	graph := BaselineContext()
	names := BaselineSourceTableNames()
	if len(names) != 8 {
		t.Fatalf("expected eight canonical source tables, got %#v", names)
	}
	for _, name := range names {
		if !hasContextNode(graph, "table:atlys."+name) || !hasContextNode(graph, "event:"+name) {
			t.Fatalf("baseline is missing source semantics for %s", name)
		}
		if !hasContextEdge(graph, "event:"+name, "STORED_IN", "table:atlys."+name) {
			t.Fatalf("baseline does not bind event %s to its table", name)
		}
	}
}

func TestApplySourceCatalogPromotesAllTablesToObserved(t *testing.T) {
	catalog := []domain.CatalogTable{}
	for index, name := range BaselineSourceTableNames() {
		catalog = append(catalog, domain.CatalogTable{
			Database: "atlys", Name: name, Engine: "MergeTree", Rows: uint64(index + 1),
			SortingKey: "id, timestamp", Columns: []domain.CatalogColumn{{Name: "id", Type: "String"}},
			DDL: fmt.Sprintf("CREATE TABLE atlys.%s", name),
		})
	}
	graph := ApplySourceCatalog(BaselineContext(), catalog)
	for _, name := range BaselineSourceTableNames() {
		node := findContextNode(graph, "table:atlys."+name)
		if node == nil || node.Status != "observed" || node.Properties["engine"] != "MergeTree" {
			t.Fatalf("source catalog did not verify %s: %#v", name, node)
		}
	}
	if len(graph.Nodes) != len(BaselineContext().Nodes) {
		t.Fatalf("catalog promotion duplicated stable nodes: before=%d after=%d", len(BaselineContext().Nodes), len(graph.Nodes))
	}
}

func TestExtractQuestionsPreservesMultilineBusinessQuestion(t *testing.T) {
	spec := `# Feature

## Events
- event_one
- event_two

## Questions the PM will ask
- Does it lift conversion?
- Is there a platform where OTP fails more? Cut success
  and confirmation by device / OS.
- How much faster is it?
- Which segments adopt it most?`
	questions := ExtractQuestions(spec)
	if len(questions) != 4 {
		t.Fatalf("expected 4 questions, got %#v", questions)
	}
	if questions[1] != "Is there a platform where OTP fails more? Cut success and confirmation by device / OS." {
		t.Fatalf("multiline question was not normalized: %q", questions[1])
	}
}

func TestContextEvolutionReplacesStableKeysWithoutDuplicates(t *testing.T) {
	agent := ContextAgent{}
	input := domain.FeatureInput{Name: "Group / Family", Slug: "group_family", SpecMarkdown: "# Group / Family\n- Where do group applications drop off?"}
	profile := domain.EventProfile{Rows: 2, EventOrder: []string{"group_started", "group_submitted"}, EventCounts: map[string]int{"group_started": 1, "group_submitted": 1}}
	v1 := agent.Evolve(BaselineContext(), input, profile, domain.SchemaProposal{Database: "atlys", Table: "group_family_events_v1", Version: 1}, "trace-1", "published")
	profile.Rows = 5453
	v2 := agent.Evolve(v1, input, profile, domain.SchemaProposal{Database: "atlys", Table: "group_family_events_v2", Version: 2}, "trace-2", "published")

	nodeKeys := map[string]bool{}
	for _, node := range v2.Nodes {
		if nodeKeys[node.Key] {
			t.Fatalf("duplicate context node %q", node.Key)
		}
		nodeKeys[node.Key] = true
	}
	edgeKeys := map[string]bool{}
	for _, edge := range v2.Edges {
		key := edge.From + "|" + edge.Relation + "|" + edge.To
		if edgeKeys[key] {
			t.Fatalf("duplicate context edge %q", key)
		}
		edgeKeys[key] = true
	}
	featureRows := 0
	for _, node := range v2.Nodes {
		if node.Key == "feature:group_family" {
			featureRows, _ = node.Properties["sample_rows"].(int)
		}
	}
	if featureRows != 5453 {
		t.Fatalf("expected latest feature evidence to replace old node, got %d rows", featureRows)
	}
}

func TestContextEvolutionPublishesGovernedDimensionSemantics(t *testing.T) {
	contextAgent := ContextAgent{}
	input := domain.FeatureInput{Name: "Express Checkout", Slug: "express_checkout", SpecMarkdown: "# Express Checkout"}
	profile := domain.EventProfile{
		Rows: 100, EventOrder: []string{"express_checkout_shown", "express_payment_confirmed"},
		EventCounts: map[string]int{"express_checkout_shown": 60, "express_payment_confirmed": 40},
		Fields:      []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "device_type"}, {ColumnName: "city"}},
	}
	graph := contextAgent.Evolve(BaselineContext(), input, profile, domain.SchemaProposal{Database: "featurelens_poc", Table: "express_checkout_events_v1", Version: 1}, "trace-city", "published")

	var cityNode *domain.ContextNode
	var metricNode *domain.ContextNode
	for index := range graph.Nodes {
		node := &graph.Nodes[index]
		if node.Key == "dimension:express_checkout:city" {
			cityNode = node
		}
		if node.Key == "metric:express_checkout-completion-rate" {
			metricNode = node
		}
	}
	if cityNode == nil || cityNode.Properties["semantic_type"] != "event_location_city" {
		t.Fatalf("city was not promoted with event-location semantics: %#v", cityNode)
	}
	if metricNode == nil || !containsStringValue(metricNode.Properties["dimensions"], "city") {
		t.Fatalf("completion metric does not expose governed city segmentation: %#v", metricNode)
	}
	if !hasContextEdge(graph, "metric:express_checkout-completion-rate", "SEGMENTED_BY", "dimension:express_checkout:city") ||
		!hasContextEdge(graph, "playbook:segment-completion:v1", "GROUPS_BY", "dimension:express_checkout:city") {
		t.Fatalf("city dimension is not connected to the metric and segment playbook")
	}
}

func containsStringValue(value any, wanted string) bool {
	values, ok := value.([]string)
	if !ok {
		return false
	}
	for _, value := range values {
		if value == wanted {
			return true
		}
	}
	return false
}

func hasContextEdge(graph domain.ContextVersion, from, relation, to string) bool {
	for _, edge := range graph.Edges {
		if edge.From == from && edge.Relation == relation && edge.To == to {
			return true
		}
	}
	return false
}

func hasContextNode(graph domain.ContextVersion, key string) bool {
	return findContextNode(graph, key) != nil
}

func findContextNode(graph domain.ContextVersion, key string) *domain.ContextNode {
	for index := range graph.Nodes {
		if graph.Nodes[index].Key == key {
			return &graph.Nodes[index]
		}
	}
	return nil
}
