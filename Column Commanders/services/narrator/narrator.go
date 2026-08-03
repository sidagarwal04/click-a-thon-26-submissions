package narrator

import (
	"context"
	"encoding/json"
	"errors"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/telemetry"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/investigation"
)

type JSONGenerator interface {
	GenerateJSON(ctx context.Context, model, schemaName, instructions, input string, schema map[string]any, output any) (string, error)
}

type Narrative struct {
	Headline       string   `json:"headline"`
	Summary        string   `json:"summary"`
	BusinessImpact string   `json:"business_impact"`
	RootCause      string   `json:"root_cause"`
	Evidence       []string `json:"evidence"`
	RuledOut       []string `json:"ruled_out"`
	Confidence     float64  `json:"confidence"`
	NextActions    []string `json:"next_actions"`
}

// DetectionV1Narrative adds an explicit final verdict to the shared narrative
// shape without changing the v2 narrator's established response contract.
type DetectionV1Narrative struct {
	Narrative
	Classification string `json:"classification"`
	Verdict        string `json:"verdict"`
}

type Narrator struct {
	llm   JSONGenerator
	model string
	cfg   config.LLMConfig
}

func New(llm JSONGenerator, cfg config.LLMConfig) *Narrator {
	return &Narrator{llm: llm, model: cfg.NarratorModel, cfg: cfg}
}

func (n *Narrator) Narrate(ctx context.Context, subject investigation.Subject, result investigation.Result) (Narrative, error) {
	if !n.cfg.NarrationEnabled {
		return Narrative{}, errors.New("LLM narration is disabled")
	}
	if result.Status != "verified" || len(result.Evidence) == 0 {
		return Narrative{}, errors.New("narration requires verified evidence")
	}
	ctx, span := telemetry.StartSpan(ctx, "investigation.narration")
	defer span.End()
	inputBytes, _ := json.Marshal(map[string]any{
		"episode": map[string]any{
			"id": subject.EpisodeID, "metric": subject.Metric, "direction": subject.Direction,
			"start": subject.Start, "end": subject.End, "resolutions": subject.Resolutions,
		},
		"verified_diagnosis": result.Diagnosis,
		"verified_evidence":  result.Evidence,
		"ruled_out":          result.RuledOut,
	})
	telemetry.SetSpanInput(span, json.RawMessage(inputBytes))
	var narrative Narrative
	_, err := n.llm.GenerateJSON(ctx, n.model, "anomaly_narrative", narratorInstructions, string(inputBytes), narrativeSchema(), &narrative)
	if err != nil {
		telemetry.RecordSpanError(span, err)
		return Narrative{}, err
	}
	telemetry.SetSpanOutput(span, narrative)
	return narrative, nil
}

// NarrateDetectionV1 turns the deterministic v1 drilldown verdict into an
// operations-facing narrative. The drilldown remains the source of truth: the
// model receives its computed findings only and never receives the SQL used to
// produce them.
func (n *Narrator) NarrateDetectionV1(ctx context.Context, signal anomalydetector.AnomalySignal, result *drilldown.DrillDownResult) (DetectionV1Narrative, error) {
	if !n.cfg.NarrationEnabled {
		return DetectionV1Narrative{}, errors.New("LLM narration is disabled")
	}
	if result == nil {
		return DetectionV1Narrative{}, errors.New("v1 narration requires a completed drilldown")
	}

	ctx, span := telemetry.StartSpan(ctx, "detection_v1.narration")
	defer span.End()
	inputBytes, err := json.Marshal(detectionV1NarratorInput(signal, result))
	if err != nil {
		telemetry.RecordSpanError(span, err)
		return DetectionV1Narrative{}, err
	}
	telemetry.SetSpanInput(span, json.RawMessage(inputBytes))

	var narrative DetectionV1Narrative
	_, err = n.llm.GenerateJSON(ctx, n.model, "detection_v1_narrative", detectionV1NarratorInstructions, string(inputBytes), detectionV1NarrativeSchema(result.Classification), &narrative)
	if err != nil {
		telemetry.RecordSpanError(span, err)
		return DetectionV1Narrative{}, err
	}
	if narrative.Classification != result.Classification {
		err = errors.New("v1 narration classification does not match deterministic verdict")
		telemetry.RecordSpanError(span, err)
		return DetectionV1Narrative{}, err
	}
	telemetry.SetSpanOutput(span, narrative)
	return narrative, nil
}

func detectionV1NarratorInput(signal anomalydetector.AnomalySignal, result *drilldown.DrillDownResult) map[string]any {
	culprits := make([]map[string]any, 0, len(result.CulpritSegments))
	for _, item := range result.CulpritSegments {
		culprits = append(culprits, map[string]any{
			"dimension": item.Dimension, "segment": item.Segment, "metric": item.Metric,
			"current_value": item.CurrentValue, "baseline_value": item.BaselineValue,
			"delta": item.Delta, "contribution_pct": item.ContributionPct,
			"cold_start": item.ColdStart, "z_score": item.ZScore,
		})
	}
	var pairwise any
	if result.Pairwise != nil {
		pairwise = map[string]any{
			"dimension_1": result.Pairwise.Dim1, "value_1": result.Pairwise.Value1,
			"dimension_2": result.Pairwise.Dim2, "value_2": result.Pairwise.Value2,
			"current_value": result.Pairwise.CurrentValue, "baseline_value": result.Pairwise.BaselineValue,
			"current_n": result.Pairwise.CurrentN,
		}
	}
	var holdOut any
	if result.HoldOut != nil {
		holdOut = map[string]any{
			"dimension": result.HoldOut.Dimension, "excluded_segment": result.HoldOut.ExcludedSegment,
			"excluding_value": result.HoldOut.ExcludingValue, "excluding_baseline": result.HoldOut.ExcludingBase,
			"deviation_pct": result.HoldOut.DeviationPct, "reverted": result.HoldOut.Reverted,
		}
	}

	return map[string]any{
		"incident": map[string]any{
			"metric": signal.Metric, "detector_id": signal.DetectorID,
			"dimension": signal.Dimension, "segment": signal.Segment,
			"window_start": signal.Window.Start, "window_end": signal.Window.End,
			"current_value": signal.CurrentVal, "baseline_value": signal.BaselineVal,
			"deviation_pct": signal.DeviationPct, "z_score": signal.ZScore,
			"severity": signal.Severity.String(),
		},
		"deterministic_verdict": map[string]any{
			"classification": result.Classification, "guilty_factor": result.Decomposition.GuiltyFactor,
			"completeness_score": result.CompletenessScore,
		},
		"factor_decomposition": map[string]any{
			"requests": factorDeltaInput(result.Decomposition.Requests), "fill_rate": factorDeltaInput(result.Decomposition.FillRate),
			"render_rate": factorDeltaInput(result.Decomposition.RenderRate), "ecpm": factorDeltaInput(result.Decomposition.ECPM),
			"revenue": factorDeltaInput(result.Decomposition.Revenue),
		},
		"culprit_segments":      culprits,
		"ruled_out_factors":     result.Decomposition.RuledOut,
		"ruled_out_dimensions":  result.RuledOutDims,
		"hold_out_verification": holdOut,
		"pairwise_finding":      pairwise,
	}
}

func factorDeltaInput(delta drilldown.FactorDelta) map[string]any {
	return map[string]any{
		"current": delta.Current, "baseline": delta.Baseline,
		"delta_pct": delta.DeltaPct, "is_guilty": delta.IsGuilty,
	}
}

func narrativeSchema() map[string]any {
	return map[string]any{
		"type": "object",
		"properties": map[string]any{
			"headline":        map[string]any{"type": "string"},
			"summary":         map[string]any{"type": "string"},
			"business_impact": map[string]any{"type": "string"},
			"root_cause":      map[string]any{"type": "string"},
			"evidence":        map[string]any{"type": "array", "items": map[string]any{"type": "string"}, "maxItems": 8},
			"ruled_out":       map[string]any{"type": "array", "items": map[string]any{"type": "string"}, "maxItems": 8},
			"confidence":      map[string]any{"type": "number", "minimum": 0, "maximum": 1},
			"next_actions":    map[string]any{"type": "array", "items": map[string]any{"type": "string"}, "maxItems": 6},
		},
		"required":             []string{"headline", "summary", "business_impact", "root_cause", "evidence", "ruled_out", "confidence", "next_actions"},
		"additionalProperties": false,
	}
}

func detectionV1NarrativeSchema(classification string) map[string]any {
	schema := narrativeSchema()
	properties := schema["properties"].(map[string]any)
	properties["classification"] = map[string]any{"type": "string", "enum": []string{classification}}
	properties["verdict"] = map[string]any{"type": "string", "minLength": 1}
	required := schema["required"].([]string)
	schema["required"] = append(required, "classification", "verdict")
	return schema
}

const narratorInstructions = `You narrate verified advertising anomaly investigations for an operations audience.
Use only the supplied verified evidence. Never introduce a number, segment, cause, or rule-out that is absent from the input.
State the affected metric and UTC interval, business impact, verified root cause, evidence, confidence, and concise next actions.
The headline, summary, and root_cause must explicitly name the verified dimension and segment (for example, os_version=Android 15). Explain the supplied contribution_pct as that segment's share of the metric movement. Never say that only global metrics were used, never ask the reader to find a dimension by hand, and never describe an unverified segment as causal.
Distinguish correlation from causation. If the verified evidence is narrow, make that limitation explicit.
Write plain, precise language. Return only the required structured JSON.`

const detectionV1NarratorInstructions = `You produce the final operations verdict for a deterministic advertising anomaly drilldown.
The supplied deterministic_verdict, factor decomposition, culprit segments, hold-out result, pairwise finding, and rule-outs are authoritative. Use only those supplied facts. Never invent a number, segment, cause, verification result, or rule-out.
State the affected metric and UTC interval, business impact, final classification, guilty factor, strongest supported root cause, evidence, confidence, and concise next actions. Make verdict a concise final determination that agrees with deterministic_verdict.classification.
For a single-segment verdict, name its dimension and segment. For an intersection verdict, name both dimensions and values. For a global verdict, explicitly say no supplied segment stands out and do not invent one.
Treat hold_out_verification.reverted=true as stronger support. If hold-out evidence is absent or did not revert, describe the cause as an attribution rather than a verified cause and lower confidence. Treat cold-start findings as observations, not verified causes.
Explain contribution_pct as the segment's share of the metric movement and completeness_score as how much of the movement the strongest attribution explains. Distinguish correlation from causation and state evidence limitations.
Write plain, precise language. Return only the required structured JSON.`
