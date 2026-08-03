package agent

import (
	"encoding/json"

	"github.com/view26/featurelens/internal/domain"
)

// DiffContexts computes the structured delta between two immutable context
// versions. Node changes compare status, confidence, and properties so the
// declared -> observed upgrades performed by ApplySourceCatalog and the
// dedupe helpers are visible in the changelog.
func DiffContexts(from, to domain.ContextVersion) domain.ContextDiff {
	diff := domain.ContextDiff{
		FromVersion:     from.Version,
		ToVersion:       to.Version,
		Feature:         to.Feature,
		AddedNodes:      []domain.ContextNode{},
		AddedEdges:      []domain.ContextEdge{},
		NodeCountBefore: len(from.Nodes),
		NodeCountAfter:  len(to.Nodes),
		EdgeCountBefore: len(from.Edges),
		EdgeCountAfter:  len(to.Edges),
	}

	beforeNodes := make(map[string]domain.ContextNode, len(from.Nodes))
	for _, node := range from.Nodes {
		beforeNodes[node.Key] = node
	}
	afterNodeKeys := make(map[string]bool, len(to.Nodes))
	for _, node := range to.Nodes {
		afterNodeKeys[node.Key] = true
		before, existed := beforeNodes[node.Key]
		if !existed {
			diff.AddedNodes = append(diff.AddedNodes, node)
			continue
		}
		if !sameNode(before, node) {
			diff.ChangedNodes = append(diff.ChangedNodes, domain.NodeChange{Key: node.Key, Before: before, After: node})
		}
	}
	for _, node := range from.Nodes {
		if !afterNodeKeys[node.Key] {
			diff.RemovedNodeKeys = append(diff.RemovedNodeKeys, node.Key)
		}
	}

	beforeEdges := make(map[string]bool, len(from.Edges))
	for _, edge := range from.Edges {
		beforeEdges[edgeKey(edge)] = true
	}
	for _, edge := range to.Edges {
		if !beforeEdges[edgeKey(edge)] {
			diff.AddedEdges = append(diff.AddedEdges, edge)
		}
	}

	beforeConflicts := make(map[string]domain.ContextConflict, len(from.Conflicts))
	for _, conflict := range from.Conflicts {
		beforeConflicts[conflict.Key] = conflict
	}
	for _, conflict := range to.Conflicts {
		before, existed := beforeConflicts[conflict.Key]
		if !existed {
			diff.AddedConflicts = append(diff.AddedConflicts, conflict)
			continue
		}
		if before != conflict {
			diff.ChangedConflicts = append(diff.ChangedConflicts, domain.ConflictChange{Key: conflict.Key, Before: before, After: conflict})
		}
	}
	return diff
}

func sameNode(left, right domain.ContextNode) bool {
	if left.Status != right.Status || left.Confidence != right.Confidence || left.Name != right.Name || left.Type != right.Type {
		return false
	}
	leftProperties, _ := json.Marshal(left.Properties)
	rightProperties, _ := json.Marshal(right.Properties)
	return string(leftProperties) == string(rightProperties)
}

func edgeKey(edge domain.ContextEdge) string {
	return edge.From + "|" + edge.Relation + "|" + edge.To
}
