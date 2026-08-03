package agent

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

func sliceNodeKeys(t *testing.T, contextSlice map[string]any) map[string]bool {
	t.Helper()
	nodes, ok := contextSlice["nodes"].([]map[string]any)
	if !ok {
		t.Fatalf("context slice nodes have an unexpected shape: %#v", contextSlice["nodes"])
	}
	keys := map[string]bool{}
	for _, node := range nodes {
		keys[node["key"].(string)] = true
	}
	return keys
}

func sliceEdges(t *testing.T, contextSlice map[string]any) []domain.ContextEdge {
	t.Helper()
	edges, ok := contextSlice["edges"].([]domain.ContextEdge)
	if !ok {
		t.Fatalf("context slice edges have an unexpected shape: %#v", contextSlice["edges"])
	}
	return edges
}

func TestCompactContextEmitsClosedSubgraph(t *testing.T) {
	graph := domain.ContextVersion{
		Version: 3,
		Nodes: []domain.ContextNode{
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout", Status: "verified", Confidence: .95},
			{Key: "event:checkout_opened", Type: "event", Name: "checkout_opened", Status: "observed", Confidence: .99},
			{Key: "dimension:express_checkout:city", Type: "dimension", Name: "Express Checkout city", Status: "verified", Confidence: .92},
			{Key: "table:featurelens_poc.express_checkout_events_v1", Type: "table", Name: "express_checkout_events_v1", Status: "observed", Confidence: .98},
		},
		Edges: []domain.ContextEdge{
			{From: "feature:express_checkout", Relation: "EMITS", To: "event:checkout_opened"},
			{From: "feature:express_checkout", Relation: "HAS_DIMENSION", To: "dimension:express_checkout:city"},
			// The table is not in AllowedTables, so this edge would dangle.
			{From: "feature:express_checkout", Relation: "STORED_IN", To: "table:featurelens_poc.express_checkout_events_v1"},
		},
	}
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{Role: "product_manager", Feature: "Express Checkout"})
	keys := sliceNodeKeys(t, contextSlice)
	for _, edge := range sliceEdges(t, contextSlice) {
		if !keys[edge.From] || !keys[edge.To] {
			t.Fatalf("emitted edge references a node outside the slice: %#v (nodes %#v)", edge, keys)
		}
	}
	if keys["table:featurelens_poc.express_checkout_events_v1"] {
		t.Fatal("a table outside AllowedTables reached the slice")
	}
}

func TestCompactContextStripsTablePhysicalProperties(t *testing.T) {
	graph := domain.ContextVersion{
		Version: 3,
		Nodes: []domain.ContextNode{
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout", Status: "verified", Confidence: .95},
			{Key: "table:featurelens_poc.express_checkout_events_v1", Type: "table", Name: "express_checkout_events_v1", Status: "observed", Confidence: .98, Properties: map[string]any{
				"database":       "featurelens_poc",
				"schema_version": 1,
				"ddl":            "CREATE TABLE featurelens_poc.express_checkout_events_v1 (id String) ENGINE = MergeTree",
				"columns":        []string{"id", "event", "timestamp"},
				"column_types":   map[string]string{"id": "String"},
				"order_by":       "(event, timestamp)",
				"row_count":      123456,
			}},
		},
		Edges: []domain.ContextEdge{
			{From: "feature:express_checkout", Relation: "STORED_IN", To: "table:featurelens_poc.express_checkout_events_v1"},
		},
	}
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{
		Role: "product_manager", Feature: "Express Checkout",
		AllowedTables: []string{"featurelens_poc.express_checkout_events_v1"},
	})
	encoded, err := json.Marshal(contextSlice)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "CREATE TABLE") || strings.Contains(string(encoded), "ddl") {
		t.Fatalf("physical DDL leaked into the synthesis slice: %s", encoded)
	}
	keys := sliceNodeKeys(t, contextSlice)
	if !keys["table:featurelens_poc.express_checkout_events_v1"] {
		t.Fatal("allowed table was dropped from the slice")
	}
	if !strings.Contains(string(encoded), "featurelens_poc") {
		t.Fatalf("table lost its database identity: %s", encoded)
	}
}

func TestCompactContextRanksNeighborTruncation(t *testing.T) {
	nodes := []domain.ContextNode{
		{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout", Status: "verified", Confidence: .95},
	}
	edges := []domain.ContextEdge{}
	neighborCount := maxSynthesisSliceNodes + 5
	for i := 0; i < neighborCount-1; i++ {
		key := fmt.Sprintf("event:filler_%02d", i)
		nodes = append(nodes, domain.ContextNode{Key: key, Type: "event", Name: key, Status: "declared", Confidence: .5})
		edges = append(edges, domain.ContextEdge{From: "feature:express_checkout", Relation: "EMITS", To: key})
	}
	// Listed last in graph order: without ranking it would be truncated.
	nodes = append(nodes, domain.ContextNode{Key: "event:winner", Type: "event", Name: "winner", Status: "verified", Confidence: .99})
	edges = append(edges, domain.ContextEdge{From: "feature:express_checkout", Relation: "EMITS", To: "event:winner"})

	contextSlice := compactSynthesisContext(domain.ContextVersion{Version: 3, Nodes: nodes, Edges: edges}, domain.AnalysisContract{Role: "product_manager", Feature: "Express Checkout"})
	keys := sliceNodeKeys(t, contextSlice)
	if !keys["event:winner"] {
		t.Fatal("the highest-evidence neighbor was truncated despite ranking")
	}
	wantTruncated := 1 + neighborCount - maxSynthesisSliceNodes // one seed always fits
	if got := contextSlice["truncated_nodes"].(int); got != wantTruncated {
		t.Fatalf("truncated_nodes = %d, want %d", got, wantTruncated)
	}
	dropped := 0
	for i := 0; i < neighborCount-1; i++ {
		if !keys[fmt.Sprintf("event:filler_%02d", i)] {
			dropped++
		}
	}
	if dropped != wantTruncated {
		t.Fatalf("expected %d declared fillers dropped, got %d", wantTruncated, dropped)
	}
}

func TestCompactContextPortfolioSeedsEveryFeature(t *testing.T) {
	graph := domain.ContextVersion{
		Version: 5,
		Nodes: []domain.ContextNode{
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout", Status: "verified", Confidence: .95},
			{Key: "feature:instant_forex", Type: "feature", Name: "Instant Forex", Status: "verified", Confidence: .95},
			{Key: "metric:express_checkout-completion-rate", Type: "metric", Name: "Express Checkout completion rate", Status: "verified", Confidence: .9},
			{Key: "metric:instant_forex-completion-rate", Type: "metric", Name: "Instant Forex completion rate", Status: "verified", Confidence: .9},
		},
	}
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{
		Role: "product_manager", Feature: "All published features",
		Playbook: "playbook:cross-feature-conversation:v1", Intent: "portfolio_conversation",
	})
	keys := sliceNodeKeys(t, contextSlice)
	for _, key := range []string{"feature:express_checkout", "feature:instant_forex", "metric:express_checkout-completion-rate", "metric:instant_forex-completion-rate"} {
		if !keys[key] {
			t.Fatalf("portfolio slice is missing %s: %#v", key, keys)
		}
	}
}

func TestCompactContextResolvesMetricsByKeyNotName(t *testing.T) {
	graph := domain.ContextVersion{
		Version: 3,
		Nodes: []domain.ContextNode{
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout", Status: "verified", Confidence: .95},
			{Key: "feature:instant_forex", Type: "feature", Name: "Instant Forex", Status: "verified", Confidence: .95},
			// Key follows the convention but the name shares nothing with the feature.
			{Key: "metric:express_checkout-completion-rate", Type: "metric", Name: "Fast pay completion", Status: "verified", Confidence: .9},
			// Name matches the feature but the key belongs to another feature.
			{Key: "metric:instant_forex-old", Type: "metric", Name: "Express Checkout legacy KPI", Status: "declared", Confidence: .6},
		},
	}
	contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{Role: "product_manager", Feature: "Express Checkout"})
	keys := sliceNodeKeys(t, contextSlice)
	if !keys["metric:express_checkout-completion-rate"] {
		t.Fatal("key-conventional metric was not seeded")
	}
	if keys["metric:instant_forex-old"] {
		t.Fatal("another feature's metric leaked in via name matching")
	}
}

func TestCompactContextPrecedesIsIntentGated(t *testing.T) {
	graph := domain.ContextVersion{
		Version: 3,
		Nodes: []domain.ContextNode{
			{Key: "feature:express_checkout", Type: "feature", Name: "Express Checkout", Status: "verified", Confidence: .95},
			{Key: "event:checkout_opened", Type: "event", Name: "checkout_opened", Status: "observed", Confidence: .99},
			{Key: "event:otp_verified", Type: "event", Name: "otp_verified", Status: "observed", Confidence: .99},
		},
		Edges: []domain.ContextEdge{
			{From: "feature:express_checkout", Relation: "EMITS", To: "event:checkout_opened"},
			{From: "feature:express_checkout", Relation: "EMITS", To: "event:otp_verified"},
			{From: "event:checkout_opened", Relation: "PRECEDES", To: "event:otp_verified"},
		},
	}
	precedesCount := func(intent string) int {
		contextSlice := compactSynthesisContext(graph, domain.AnalysisContract{Role: "product_manager", Feature: "Express Checkout", Intent: intent})
		count := 0
		for _, edge := range sliceEdges(t, contextSlice) {
			if edge.Relation == "PRECEDES" {
				count++
			}
		}
		return count
	}
	if precedesCount("funnel_diagnosis") != 1 {
		t.Fatal("PRECEDES ordering is missing from the funnel diagnosis slice")
	}
	if precedesCount("segment_comparison") != 0 {
		t.Fatal("PRECEDES ordering leaked into a segment comparison slice")
	}
}
