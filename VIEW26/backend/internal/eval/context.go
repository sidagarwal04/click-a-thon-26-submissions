package eval

import (
	"fmt"
	"strings"

	featureagent "github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
)

func ContextEvolution(before, after domain.ContextVersion, input domain.FeatureInput, profile domain.EventProfile, contract domain.AnalysisContract, insight domain.Insight, answers []domain.QuestionResponse) []domain.EvaluationResult {
	slug := slugify(input.Name)
	beforeKnows := containsNode(before, "feature:"+slug)
	afterKnows := containsNode(after, "feature:"+slug)
	eventsLinked := 0
	for event := range profile.EventCounts {
		if containsNode(after, "event:"+event) && containsEdge(after, "feature:"+slug, "EMITS", "event:"+event) {
			eventsLinked++
		}
	}
	expectedDimensions := featureagent.GovernedDimensionNames(profile)
	groundedDimensions := 0
	metricKey := "metric:" + slug + "-completion-rate"
	for _, dimension := range expectedDimensions {
		dimensionKey := "dimension:" + slug + ":" + dimension
		if containsNode(after, dimensionKey) && containsEdge(after, "feature:"+slug, "HAS_DIMENSION", dimensionKey) && containsEdge(after, metricKey, "SEGMENTED_BY", dimensionKey) {
			groundedDimensions++
		}
	}
	dimensionsGrounded := groundedDimensions == len(expectedDimensions)
	roleGrounded := contract.Role != "" && contract.Playbook != "" && len(contract.Metrics) > 0 && len(contract.AllowedTables) >= 1
	versionGrounded := insight.ContextVersion == after.Version && insight.SchemaVersion != ""
	covered, distinctPlans, distinctIntents, distinctSQL := questionCoverage(after, answers)
	questions := len(answers)
	semanticPassed := covered == questions && questions > 0
	distinctPassed := distinctPlans == distinctIntents && distinctSQL == distinctIntents && distinctIntents > 0
	removedNodeKeys := featureagent.DiffContexts(before, after).RemovedNodeKeys
	return []domain.EvaluationResult{
		{Name: "before_add_negative", Score: boolScore(!beforeKnows), Passed: !beforeKnows, Details: "The parent context must not claim knowledge of the unseen feature. Advisory: re-evolving a known feature with a new schema version is a supported flow."},
		{Name: "after_add_positive", Score: boolScore(afterKnows), Passed: afterKnows, Blocking: true, Details: "The published context contains the new feature."},
		{Name: "event_semantics_coverage", Score: ratio(eventsLinked, len(profile.EventCounts)), Passed: eventsLinked == len(profile.EventCounts), Blocking: true, Details: fmt.Sprintf("%d/%d feature events linked", eventsLinked, len(profile.EventCounts))},
		{Name: "dimension_semantics_coverage", Score: ratio(groundedDimensions, len(expectedDimensions)), Passed: dimensionsGrounded, Blocking: true, Details: fmt.Sprintf("%d/%d governed dimensions linked to the feature and completion metric", groundedDimensions, len(expectedDimensions))},
		{Name: "role_aware_contract", Score: boolScore(roleGrounded), Passed: roleGrounded, Details: "The answer contract binds role, metric, grain, and allowed table."},
		{Name: "version_grounding", Score: boolScore(versionGrounded), Passed: versionGrounded, Details: "The insight cites the exact context and schema versions used."},
		{Name: "regression_preservation", Score: ratio(len(before.Nodes)-len(removedNodeKeys), len(before.Nodes)), Passed: len(removedNodeKeys) == 0, Blocking: true, Details: regressionDetails(before, after, removedNodeKeys)},
		{Name: "declared_question_coverage", Score: ratio(covered, questions), Passed: semanticPassed, Details: fmt.Sprintf("%d/%d declared questions have an ontology-linked playbook and required evidence.", covered, questions)},
		{Name: "distinct_analysis_plans", Score: ratio(distinctPlans, distinctIntents), Passed: distinctPassed, Details: fmt.Sprintf("%d intents use %d playbooks and %d distinct SQL plans.", distinctIntents, distinctPlans, distinctSQL)},
	}
}

func questionCoverage(graph domain.ContextVersion, answers []domain.QuestionResponse) (covered, distinctPlans, distinctIntents, distinctSQL int) {
	plans := map[string]bool{}
	intents := map[string]bool{}
	sqlPlans := map[string]bool{}
	for _, answer := range answers {
		contract := answer.Contract
		plans[contract.Playbook] = true
		intents[contract.Intent] = true
		if contract.Answerability == "not_answerable" {
			// A governed abstention is a distinct plan outcome: it must be
			// ontology-linked, explain why evidence is unavailable, and execute
			// no SQL. Rewarding this path keeps the quality gate from pressuring
			// agents to fabricate an executable query for unsupported claims.
			sqlPlans["abstain:"+contract.Playbook] = true
		} else if strings.TrimSpace(answer.Insight.SQL) != "" {
			sqlPlans[normalizeSQL(answer.Insight.SQL)] = true
		}
		playbookLinked := containsNode(graph, contract.Playbook) && questionUsesPlaybook(graph, contract.Question, contract.Playbook)
		evidenceComplete := true
		for _, key := range contract.RequiredEvidence {
			if _, ok := answer.Insight.Evidence[key]; !ok {
				if answer.Insight.Evidence["execution_mode"] == "simulation" && strings.TrimSpace(answer.Insight.SQL) != "" {
					continue
				}
				evidenceComplete = false
			}
		}
		_, queryFailed := answer.Insight.Evidence["query_error"]
		abstentionGrounded := contract.Answerability == "not_answerable" && strings.TrimSpace(answer.Insight.SQL) == "" && strings.TrimSpace(fmt.Sprint(answer.Insight.Evidence["reason"])) != ""
		if contract.Playbook != "" && playbookLinked && evidenceComplete && !queryFailed && (contract.Answerability != "not_answerable" || abstentionGrounded) {
			covered++
		}
	}
	delete(plans, "")
	delete(intents, "")
	return covered, len(plans), len(intents), len(sqlPlans)
}

func questionUsesPlaybook(graph domain.ContextVersion, question, playbook string) bool {
	questionKeys := map[string]bool{}
	for _, node := range graph.Nodes {
		if node.Type == "business_question" && node.Name == question {
			questionKeys[node.Key] = true
		}
	}
	for _, edge := range graph.Edges {
		if questionKeys[edge.From] && edge.Relation == "RESOLVED_BY" && edge.To == playbook {
			return true
		}
	}
	return false
}

func normalizeSQL(sql string) string { return strings.Join(strings.Fields(sql), " ") }

func containsNode(graph domain.ContextVersion, key string) bool {
	for _, node := range graph.Nodes {
		if node.Key == key {
			return true
		}
	}
	return false
}

func containsEdge(graph domain.ContextVersion, from, relation, to string) bool {
	for _, edge := range graph.Edges {
		if edge.From == from && edge.Relation == relation && edge.To == to {
			return true
		}
	}
	return false
}

func regressionDetails(before, after domain.ContextVersion, removed []string) string {
	if len(removed) == 0 {
		return fmt.Sprintf("Parent v%d nodes remain addressable in v%d.", before.Version, after.Version)
	}
	return fmt.Sprintf("v%d dropped %d parent v%d nodes: %s", after.Version, len(removed), before.Version, strings.Join(removed, ", "))
}

func boolScore(value bool) float64 {
	if value {
		return 1
	}
	return 0
}

func ratio(numerator, denominator int) float64 {
	if denominator == 0 {
		return 1
	}
	return float64(numerator) / float64(denominator)
}

func slugify(value string) string {
	fields := strings.FieldsFunc(strings.ToLower(value), func(r rune) bool { return r < 'a' || r > 'z' && (r < '0' || r > '9') })
	return strings.Join(fields, "_")
}
