package agent

import (
	"context"
	"sort"
	"strings"

	"github.com/view26/featurelens/internal/domain"
)

const AnalyticsPromptVersion = "analytics-insight:v5"

const AnalyticsSystemPrompt = `You are FeatureLens, a governed product analytics agent writing for a Product Manager. Use only the supplied ClickHouse aggregate evidence and published context. Never invent a metric, segment, causal claim, table, or number. Never claim that a requested ranking, breakdown, or comparison was identified unless the aggregate evidence contains that exact dimension and result. Respect answerability, limitations, known issues, metric grain, and context conflicts. Context conflicts are warnings about the data, never definitions you may compute with. Definitions listed under quarantined_definitions are contradicted and must never be used; use the canonical metric they point to via superseded_by. Treat known issues as hypotheses unless the aggregate evidence supports them.

Return one JSON object with exactly: headline, summary, why, confidence, recommended_action, key_findings. Confidence must be between 0 and 1.

Write "summary" as 2-3 sentences that give the PM the shape of the answer: the top-line result, the biggest driver behind it, and the segment or stage where it concentrates. It is a briefing, not a one-liner — do not just restate the headline.

Write "why" as the PM stakes, in 2-3 sentences, not a restatement of the number. Tie the finding to a decision the PM actually owns — adoption, conversion impact, drop-off, roadmap priority, or whether the release is working — quantify the stakes from the evidence (which segment or funnel stage, how much conversion or how many entities are affected), and name the likely consequence of doing nothing. Do not write generic lines like "this is important to monitor" or "this affects the user experience."

Write "key_findings" as 2-4 distinct, ranked observations — this is the heart of the answer for open questions like "surface the most important issues." Order them by impact, most important first. Each finding is an object with: "point" (the specific observation, quantified from the evidence — name the exact stage, segment, or metric and its value), "why" (why THIS finding matters to the PM and what decision it informs — never generic), "evidence" (the metric, funnel stage, or segment name it is grounded in), and "severity" (one of "high", "medium", "low"). Every finding must stand on its own and be traceable to a number in the aggregate evidence; never pad the list with a finding you cannot ground. If the evidence only supports one real finding, return one.

Write "recommended_action" as one concrete next step the PM can take this week, naming the specific target from the evidence: which segment to investigate, which funnel step to instrument or fix, which cohort to A/B, or whether to ship, hold, or reprioritize. Never give a vague directive like "keep an eye on it," "consider improving," or "gather more data" without saying exactly what and where.`

type InsightSynthesisRequest struct {
	Contract domain.AnalysisContract `json:"analysis_contract"`
	Context  map[string]any          `json:"context"`
	Evidence map[string]any          `json:"aggregate_evidence"`
	Draft    domain.Insight          `json:"deterministic_draft"`
}

type InsightSynthesis struct {
	Headline          string               `json:"headline"`
	Summary           string               `json:"summary"`
	Why               string               `json:"why"`
	Confidence        float64              `json:"confidence"`
	RecommendedAction string               `json:"recommended_action"`
	KeyFindings       []domain.KeyFinding  `json:"key_findings"`
	ObservationID     string               `json:"-"`
}

type InsightSynthesizer interface {
	Enabled() bool
	Metadata() domain.InsightProvenance
	Synthesize(context.Context, InsightSynthesisRequest) (InsightSynthesis, error)
}

// maxSynthesisSliceNodes bounds how many graph nodes reach the LLM and the
// trace. The stored graph stays append-only; only the slice is capped.
const maxSynthesisSliceNodes = 60

func compactSynthesisContext(graph domain.ContextVersion, contract domain.AnalysisContract) map[string]any {
	roleKey := roleNodeKey(contract.Role)
	featureSlug := Slug(contract.Feature)
	allowedTables := map[string]bool{}
	for _, table := range contract.AllowedTables {
		allowedTables["table:"+table] = true
	}
	allowsNode := func(key string) bool {
		if strings.HasPrefix(key, "table:") {
			return allowedTables[key]
		}
		if featureSlug != "" && featureSlug != "all_published_features" && strings.HasPrefix(key, "feature:") {
			return key == "feature:"+featureSlug
		}
		if featureSlug != "" && featureSlug != "all_published_features" && strings.HasPrefix(key, "dimension:") {
			return strings.HasPrefix(key, "dimension:"+featureSlug+":")
		}
		if featureSlug != "" && featureSlug != "all_published_features" && strings.HasPrefix(key, "question:") {
			return strings.HasPrefix(key, "question:"+featureSlug+":")
		}
		return true
	}
	seeds := synthesisSeedKeys(graph, contract, roleKey, featureSlug)
	relevant := map[string]bool{}
	for key := range seeds {
		relevant[key] = true
	}
	// Include one-hop ontology neighbors so the trace and the LLM can see the
	// verified table/event bindings behind the selected feature and playbook.
	// Only semantic relations are followed; entity/domain/role fan-out stays out.
	for _, edge := range graph.Edges {
		if !synthesisRelationAllowed(edge.Relation, contract.Intent) {
			continue
		}
		if !allowsNode(edge.From) || !allowsNode(edge.To) {
			continue
		}
		fromSelected := edge.From != roleKey && seeds[edge.From]
		toSelected := edge.To != roleKey && seeds[edge.To]
		if fromSelected || toSelected {
			relevant[edge.From] = true
			relevant[edge.To] = true
		}
	}

	// Contradicted nodes are quarantined: they stay visible as warnings so the
	// model knows the definition exists and must not be used, but their formula
	// and properties are withheld so they cannot be cited as evidence. The scan
	// covers the whole in-scope graph so quarantine never depends on how seeds
	// were resolved; a warning's canonical replacement is force-included.
	otherFeatureMetric := func(key string) bool {
		if featureSlug == "" || featureSlug == "all_published_features" || !strings.HasPrefix(key, "metric:") {
			return false
		}
		for _, node := range graph.Nodes {
			if node.Type != "feature" {
				continue
			}
			slug := strings.TrimPrefix(node.Key, "feature:")
			if slug != featureSlug && strings.HasPrefix(key, "metric:"+slug+"-") {
				return true
			}
		}
		return false
	}
	quarantined := make([]map[string]any, 0)
	excluded := map[string]bool{}
	for _, node := range graph.Nodes {
		if node.Status != "contradicted" || !allowsNode(node.Key) || otherFeatureMetric(node.Key) {
			continue
		}
		excluded[node.Key] = true
		warning := map[string]any{"key": node.Key, "name": node.Name, "reason": "contradicted definition; do not use"}
		if supersededBy, ok := node.Properties["superseded_by"]; ok {
			warning["superseded_by"] = supersededBy
			if canonical, ok := supersededBy.(string); ok && allowsNode(canonical) {
				relevant[canonical] = true
			}
		}
		quarantined = append(quarantined, warning)
	}

	seedNodes := make([]domain.ContextNode, 0, len(seeds))
	neighborNodes := make([]domain.ContextNode, 0, len(relevant))
	for _, node := range graph.Nodes {
		if !relevant[node.Key] || excluded[node.Key] {
			continue
		}
		if seeds[node.Key] {
			seedNodes = append(seedNodes, node)
		} else {
			neighborNodes = append(neighborNodes, node)
		}
	}
	// Seeds (role, playbook, feature, issues, questions, metrics) always fit;
	// one-hop neighbors are ranked and truncated once the slice budget is
	// reached so the prompt payload stays bounded as the graph grows.
	rankSynthesisNeighbors(neighborNodes)
	truncatedNodes := 0
	kept := seedNodes
	for _, node := range neighborNodes {
		if len(kept) >= maxSynthesisSliceNodes {
			truncatedNodes++
			continue
		}
		kept = append(kept, node)
	}
	included := make(map[string]bool, len(kept))
	nodes := make([]map[string]any, 0, len(kept))
	for _, node := range kept {
		included[node.Key] = true
		nodes = append(nodes, map[string]any{
			"key": node.Key, "type": node.Type, "name": node.Name, "status": node.Status,
			"confidence": node.Confidence, "properties": compactNodeProperties(node), "sources": node.Sources,
		})
	}
	// The emitted subgraph is closed: an edge ships only when both endpoints
	// are in the node list, so the model never sees dangling references. The
	// relation gate applies here too so intent-scoped relations like PRECEDES
	// stay out of off-intent payloads even between included nodes.
	edges := make([]domain.ContextEdge, 0)
	for _, edge := range graph.Edges {
		if included[edge.From] && included[edge.To] && synthesisRelationAllowed(edge.Relation, contract.Intent) {
			edges = append(edges, edge)
		}
	}
	conflicts := make([]map[string]any, 0, len(graph.Conflicts))
	for _, conflict := range graph.Conflicts {
		conflicts = append(conflicts, map[string]any{
			"key": conflict.Key, "severity": conflict.Severity, "description": conflict.Description,
			"status": conflict.Status, "resolution": conflict.Resolution, "usable": false,
		})
	}
	return map[string]any{
		"context_version":         graph.Version,
		"parent_version":          graph.ParentVersion,
		"feature":                 graph.Feature,
		"state":                   graph.State,
		"schema_versions":         graph.SchemaVersions,
		"nodes":                   nodes,
		"edges":                   edges,
		"conflicts":               conflicts,
		"quarantined_definitions": quarantined,
		"truncated_nodes":         truncatedNodes,
	}
}

// synthesisSeedKeys resolves the contract to graph node keys deterministically:
// metrics by key convention and ANALYZED_BY wiring rather than name matching.
func synthesisSeedKeys(graph domain.ContextVersion, contract domain.AnalysisContract, roleKey, featureSlug string) map[string]bool {
	seeds := map[string]bool{roleKey: true}
	if contract.Playbook != "" {
		seeds[contract.Playbook] = true
	}
	for _, issueName := range contract.KnownIssues {
		for _, node := range graph.Nodes {
			if node.Type == "known_issue" && node.Name == issueName {
				seeds[node.Key] = true
			}
		}
	}
	if featureSlug == "all_published_features" {
		for _, node := range graph.Nodes {
			if node.Type != "feature" {
				continue
			}
			seeds[node.Key] = true
			metricPrefix := "metric:" + strings.TrimPrefix(node.Key, "feature:") + "-"
			for _, metric := range graph.Nodes {
				if metric.Type == "metric" && strings.HasPrefix(metric.Key, metricPrefix) {
					seeds[metric.Key] = true
				}
			}
		}
		return seeds
	}
	if featureSlug == "" {
		return seeds
	}
	seeds["feature:"+featureSlug] = true
	metricsSeeded := false
	for _, node := range graph.Nodes {
		if node.Type == "metric" && strings.HasPrefix(node.Key, "metric:"+featureSlug+"-") {
			seeds[node.Key] = true
			metricsSeeded = true
		}
		if node.Type == "business_question" && strings.HasPrefix(node.Key, "question:"+featureSlug+":") && node.Name == contract.Question {
			seeds[node.Key] = true
		}
	}
	for _, edge := range graph.Edges {
		if edge.Relation == "ANALYZED_BY" && edge.To == contract.Playbook {
			seeds[edge.From] = true
			metricsSeeded = true
		}
	}
	if !metricsSeeded {
		// Legacy fallback for metrics that predate the key convention, such as
		// the baseline funnel metrics.
		for _, node := range graph.Nodes {
			if node.Type == "metric" && strings.Contains(strings.ToLower(node.Name), strings.ToLower(contract.Feature)) {
				seeds[node.Key] = true
			}
		}
	}
	return seeds
}

// synthesisRelationAllowed limits one-hop expansion to semantic bindings.
// STARTS/TARGETS/OBSERVES/INTERESTED_IN/ASKS fan out across the whole ontology
// and are never worth their tokens; PRECEDES only matters for funnel intents.
func synthesisRelationAllowed(relation, intent string) bool {
	switch relation {
	case "STORED_IN", "EMITS", "HAS_DIMENSION", "COMPUTED_FROM", "SEGMENTED_BY",
		"ANALYZED_BY", "QUERIES", "GROUPS_BY", "ENABLES_QUESTION", "RESOLVED_BY",
		"AFFECTS", "MAY_AFFECT":
		return true
	case "PRECEDES":
		return intent == "funnel_diagnosis" || intent == "completion_trend" || intent == ""
	default:
		return false
	}
}

// synthesisPropertyAllowlist keeps the semantic fields the model can ground on
// and drops physical payloads (DDL, column maps) that only the deterministic
// SQL planner could use. Types absent from the map pass through verbatim.
var synthesisPropertyAllowlist = map[string][]string{
	"table":               {"database", "schema_version", "category", "grain"},
	"metric":              {"numerator", "denominator", "numerator_event", "denominator_event", "grain", "dimensions", "canonical", "superseded_by"},
	"dimension":           {"field", "semantic_type", "meaning", "aliases", "binding", "queryable"},
	"business_question":   {"role", "intent", "required_evidence"},
	"analysis_playbook":   {"intent", "required_evidence", "execution"},
	"operating_principle": {"instruction"},
	"role_profile":        {"goals", "answer_style"},
}

func compactNodeProperties(node domain.ContextNode) map[string]any {
	compact := map[string]any{}
	if allowed, scoped := synthesisPropertyAllowlist[node.Type]; scoped {
		for _, key := range allowed {
			if value, ok := node.Properties[key]; ok {
				compact[key] = value
			}
		}
		return compact
	}
	for key, value := range node.Properties {
		if key == "ddl" || key == "columns" || key == "column_types" {
			continue
		}
		compact[key] = value
	}
	return compact
}

func synthesisStatusRank(status string) int {
	switch status {
	case "verified":
		return 0
	case "observed":
		return 1
	case "declared":
		return 2
	case "inferred":
		return 3
	default:
		return 4
	}
}

// rankSynthesisNeighbors orders one-hop neighbors so truncation drops the
// weakest evidence first, with a key tiebreak for deterministic traces.
func rankSynthesisNeighbors(nodes []domain.ContextNode) {
	sort.SliceStable(nodes, func(i, j int) bool {
		ri, rj := synthesisStatusRank(nodes[i].Status), synthesisStatusRank(nodes[j].Status)
		if ri != rj {
			return ri < rj
		}
		if nodes[i].Confidence != nodes[j].Confidence {
			return nodes[i].Confidence > nodes[j].Confidence
		}
		return nodes[i].Key < nodes[j].Key
	})
}

func roleNodeKey(role string) string {
	switch Slug(role) {
	case "growth", "growth_commercial", "commercial":
		return "role:growth"
	case "instrumentation", "data", "data_instrumentation":
		return "role:instrumentation"
	default:
		return "role:product-manager"
	}
}
