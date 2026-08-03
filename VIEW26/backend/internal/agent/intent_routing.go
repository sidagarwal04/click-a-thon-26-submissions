package agent

import (
	"strings"

	"github.com/view26/featurelens/internal/domain"
)

const graphIntentSimilarityThreshold = 0.6

var intentStopwords = map[string]bool{
	"a": true, "an": true, "and": true, "are": true, "by": true, "do": true, "does": true,
	"for": true, "how": true, "in": true, "is": true, "it": true, "of": true, "on": true,
	"or": true, "our": true, "the": true, "their": true, "this": true, "to": true,
	"we": true, "what": true, "which": true, "with": true,
}

// resolveIntentFromGraph routes a question through the context layer itself:
// it matches the question against the feature's declared business_question
// nodes (created at Evolve time with a stored intent and a RESOLVED_BY
// playbook edge) using token-set Jaccard similarity. Declared spec questions
// and close paraphrases route deterministically through the versioned
// ontology; only novel questions fall back to the keyword classifier.
func resolveIntentFromGraph(graph domain.ContextVersion, featureSlug, question string) (string, bool) {
	questionTokens := intentTokens(question)
	if len(questionTokens) == 0 {
		return "", false
	}
	prefix := "question:" + featureSlug + ":"
	bestScore := 0.0
	bestIntent := ""
	for _, node := range graph.Nodes {
		if node.Type != "business_question" || !strings.HasPrefix(node.Key, prefix) {
			continue
		}
		intent, ok := node.Properties["intent"].(string)
		if !ok || intent == "" {
			continue
		}
		score := jaccard(questionTokens, intentTokens(node.Name))
		if score > bestScore {
			bestScore = score
			bestIntent = intent
		}
	}
	if bestScore >= graphIntentSimilarityThreshold {
		return bestIntent, true
	}
	return "", false
}

func intentTokens(text string) map[string]bool {
	normalized := strings.Map(func(r rune) rune {
		if r >= 'a' && r <= 'z' || r >= '0' && r <= '9' {
			return r
		}
		if r >= 'A' && r <= 'Z' {
			return r + ('a' - 'A')
		}
		return ' '
	}, text)
	tokens := map[string]bool{}
	for _, field := range strings.Fields(normalized) {
		if !intentStopwords[field] {
			tokens[field] = true
		}
	}
	return tokens
}

func jaccard(left, right map[string]bool) float64 {
	if len(left) == 0 || len(right) == 0 {
		return 0
	}
	intersection := 0
	for token := range left {
		if right[token] {
			intersection++
		}
	}
	union := len(left) + len(right) - intersection
	return float64(intersection) / float64(union)
}
