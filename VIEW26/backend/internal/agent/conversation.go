package agent

import (
	"context"

	"github.com/view26/featurelens/internal/domain"
)

// SynthesizeConversation applies the same governed LLM boundary used by
// feature answers to a portfolio draft. The caller supplies only aggregate
// evidence and a contract compiled from published feature context.
func (a AnalyticsAgent) SynthesizeConversation(ctx context.Context, contract domain.AnalysisContract, graph domain.ContextVersion, draft domain.Insight) (domain.Insight, domain.AnalysisTraceStep) {
	return a.synthesize(ctx, contract, graph, draft)
}
