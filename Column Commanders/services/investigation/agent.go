package investigation

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"sort"
	"strings"
	"time"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/telemetry"
)

type JSONGenerator interface {
	GenerateJSON(ctx context.Context, model, schemaName, instructions, input string, schema map[string]any, output any) (string, error)
}

type AgentQueryExecutor interface {
	Execute(ctx context.Context, queryIndex int, validated ValidatedQuery, start, end time.Time) (QueryResult, error)
}

type CanonicalVerifier interface {
	Localize(ctx context.Context, subject Subject) ([]Evidence, error)
	Verify(ctx context.Context, subject Subject, dimension, segment string) (Evidence, error)
}

type EvidenceStore interface {
	SaveStep(ctx context.Context, subject Subject, step Step) error
	SaveEvidence(ctx context.Context, evidence Evidence) error
}

type Agent struct {
	llm       JSONGenerator
	model     string
	validator *Validator
	executor  AgentQueryExecutor
	verifier  CanonicalVerifier
	store     EvidenceStore
	cfg       config.LLMConfig
	logger    *slog.Logger
}

func NewAgent(llm JSONGenerator, validator *Validator, executor AgentQueryExecutor, verifier CanonicalVerifier, store EvidenceStore, cfg config.LLMConfig, logger *slog.Logger) *Agent {
	return &Agent{llm: llm, model: cfg.InvestigatorModel, validator: validator, executor: executor, verifier: verifier, store: store, cfg: cfg, logger: logger}
}

var stateOrder = map[string]int{
	"DISCOVER": 0, "CONFIRM": 1, "LOCALIZE": 2, "RULE_OUT": 3, "VERIFY": 4, "FINISH": 5,
}

func (a *Agent) Investigate(ctx context.Context, subject Subject) (Result, error) {
	if !a.cfg.InvestigationEnabled {
		return Result{Status: "disabled", Diagnosis: "LLM investigation is disabled"}, nil
	}
	ctx, span := telemetry.StartSpan(ctx, "investigation.agent")
	defer span.End()
	telemetry.SetSpanInput(span, subject)

	transcript := []any{map[string]any{"episode": subject}}
	result := Result{Status: "insufficient_evidence"}
	currentState := "DISCOVER"
	queryCount := 0
	canonicalCandidates, localizationErr := a.verifier.Localize(ctx, subject)
	if localizationErr != nil {
		a.logger.Error("deterministic dimension sweep failed", slog.String("episode_id", subject.EpisodeID.String()), slog.Any("error", localizationErr))
		transcript = append(transcript, map[string]any{"dimension_sweep_error": localizationErr.Error()})
	} else {
		transcript = append(transcript, map[string]any{
			"deterministic_dimension_sweep": canonicalCandidates,
			"instruction":                   "Investigate the strongest verified segment candidates. FINISH with an exact dimension and segment from this list after ruling out plausible alternatives.",
		})
		if len(canonicalCandidates) > 0 {
			currentState = "LOCALIZE"
		}
	}

	for stepIndex := 1; stepIndex <= a.cfg.MaxSteps; stepIndex++ {
		input, _ := json.Marshal(map[string]any{
			"current_state": currentState,
			"queries_used":  queryCount,
			"max_queries":   a.cfg.MaxQueries,
			"transcript":    transcript,
		})
		var action AgentAction
		responseID, err := a.llm.GenerateJSON(ctx, a.model, "investigation_action", investigationInstructions, string(input), investigationActionSchema(), &action)
		step := Step{Index: stepIndex, Action: action, ResponseID: responseID}
		if err != nil {
			step.Validation = "llm_error"
			step.Error = err.Error()
			result.Steps = append(result.Steps, step)
			_ = a.store.SaveStep(ctx, subject, step)
			if fallback, ok := a.canonicalFallback(ctx, subject, canonicalCandidates, result.Steps); ok {
				telemetry.SetSpanOutput(span, fallback)
				return fallback, nil
			}
			telemetry.RecordSpanError(span, err)
			return result, fmt.Errorf("investigation step %d: %w", stepIndex, err)
		}

		if err := validateTransition(currentState, action); err != nil {
			step.Validation = "rejected"
			step.Error = err.Error()
			result.Steps = append(result.Steps, step)
			_ = a.store.SaveStep(ctx, subject, step)
			transcript = append(transcript, map[string]any{"validation_error": err.Error(), "rejected_action": action})
			continue
		}

		if action.Action == "query" {
			if queryCount >= a.cfg.MaxQueries {
				step.Validation = "rejected"
				step.Error = "query budget exhausted"
				result.Steps = append(result.Steps, step)
				_ = a.store.SaveStep(ctx, subject, step)
				transcript = append(transcript, map[string]any{"validation_error": step.Error})
				continue
			}
			validated, validationErr := a.validator.Validate(QueryRequest{
				Purpose: action.Purpose, SQL: action.SQL, ExpectedColumns: action.ExpectedColumns,
			}, subject.Mode)
			if validationErr != nil {
				step.Validation = "rejected"
				step.Error = validationErr.Error()
				result.Steps = append(result.Steps, step)
				_ = a.store.SaveStep(ctx, subject, step)
				transcript = append(transcript, map[string]any{"validation_error": validationErr.Error(), "rejected_query": action.SQL})
				continue
			}
			queryCount++
			queryResult, executionErr := a.executor.Execute(ctx, queryCount, validated, subject.Start, subject.End)
			step.Validation = "approved"
			step.Result = queryResult
			if executionErr != nil {
				step.Error = executionErr.Error()
				step.Validation = "execution_failed"
			}
			result.Steps = append(result.Steps, step)
			_ = a.store.SaveStep(ctx, subject, step)
			if executionErr != nil {
				transcript = append(transcript, map[string]any{"execution_error": executionErr.Error(), "purpose": action.Purpose})
				continue
			}
			currentState = action.State
			transcript = append(transcript, map[string]any{
				"state": action.State, "purpose": action.Purpose, "decision": action.Decision,
				"rows": trimRows(queryResult.Rows, 25),
			})
			continue
		}

		if queryCount == 0 && len(canonicalCandidates) == 0 {
			step.Validation = "rejected"
			step.Error = "at least one approved evidence query is required before FINISH"
			result.Steps = append(result.Steps, step)
			_ = a.store.SaveStep(ctx, subject, step)
			transcript = append(transcript, map[string]any{"verification_error": step.Error})
			continue
		}
		evidence, verificationErr := a.verifier.Verify(ctx, subject, action.RootCauseDimension, action.RootCauseSegment)
		if verificationErr != nil || !evidence.Verified {
			message := "canonical verification rejected the proposed root cause"
			if verificationErr != nil {
				message = verificationErr.Error()
			}
			step.Validation = "verification_failed"
			step.Error = message
			result.Steps = append(result.Steps, step)
			_ = a.store.SaveStep(ctx, subject, step)
			if verificationErr == nil {
				_ = a.store.SaveEvidence(ctx, evidence)
			}
			transcript = append(transcript, map[string]any{"verification_error": message, "proposed_evidence": evidence})
			currentState = "VERIFY"
			continue
		}

		step.Validation = "verified"
		result.Steps = append(result.Steps, step)
		_ = a.store.SaveStep(ctx, subject, step)
		_ = a.store.SaveEvidence(ctx, evidence)
		result.Diagnosis = action.Decision
		result.RootCauseDimension = action.RootCauseDimension
		result.RootCauseSegment = action.RootCauseSegment
		result.Confidence = clamp(action.Confidence, 0, 1)
		result.Status = "verified"
		result.Evidence = []Evidence{evidence}
		result.RuledOut = collectRuleOuts(result.Steps)
		telemetry.SetSpanOutput(span, result)
		return result, nil
	}

	if fallback, ok := a.canonicalFallback(ctx, subject, canonicalCandidates, result.Steps); ok {
		telemetry.SetSpanOutput(span, fallback)
		return fallback, nil
	}

	result.Diagnosis = "The investigation exhausted its bounded step budget without verified evidence."
	result.RuledOut = collectRuleOuts(result.Steps)
	telemetry.SetSpanOutput(span, result)
	return result, nil
}

func (a *Agent) canonicalFallback(ctx context.Context, subject Subject, candidates []Evidence, steps []Step) (Result, bool) {
	for _, evidence := range candidates {
		if !evidence.Verified {
			continue
		}
		_ = a.store.SaveEvidence(ctx, evidence)
		return Result{
			Status:             "verified",
			Diagnosis:          fmt.Sprintf("Deterministic dimension attribution identified %s=%s as the strongest verified contributor to the %s anomaly.", evidence.Dimension, evidence.Segment, subject.Metric),
			RootCauseDimension: evidence.Dimension,
			RootCauseSegment:   evidence.Segment,
			Confidence:         clamp(math.Abs(evidence.ContributionPct), 0, 1),
			Evidence:           []Evidence{evidence},
			RuledOut:           collectRuleOuts(steps),
			Steps:              steps,
		}, true
	}
	return Result{}, false
}

func validateTransition(current string, action AgentAction) error {
	currentRank, ok := stateOrder[current]
	if !ok {
		return fmt.Errorf("unknown current state %q", current)
	}
	nextRank, ok := stateOrder[action.State]
	if !ok {
		return fmt.Errorf("unknown requested state %q", action.State)
	}
	if action.Action != "query" && action.Action != "finish" {
		return fmt.Errorf("unsupported action %q", action.Action)
	}
	if action.Action == "finish" {
		if action.State != "FINISH" || currentRank < stateOrder["VERIFY"] {
			return errors.New("FINISH is allowed only after the VERIFY state")
		}
		return nil
	}
	if action.State == "FINISH" {
		return errors.New("a query action cannot use FINISH state")
	}
	if nextRank < currentRank || nextRank > currentRank+1 {
		return fmt.Errorf("invalid state transition %s -> %s", current, action.State)
	}
	return nil
}

func investigationActionSchema() map[string]any {
	dimensionNames := make([]string, 0, len(dimensions)+1)
	dimensionNames = append(dimensionNames, "")
	for name := range dimensions {
		dimensionNames = append(dimensionNames, name)
	}
	sort.Strings(dimensionNames)
	return map[string]any{
		"type": "object",
		"properties": map[string]any{
			"state":                map[string]any{"type": "string", "enum": []string{"DISCOVER", "CONFIRM", "LOCALIZE", "RULE_OUT", "VERIFY", "FINISH"}},
			"action":               map[string]any{"type": "string", "enum": []string{"query", "finish"}},
			"purpose":              map[string]any{"type": "string"},
			"sql":                  map[string]any{"type": "string"},
			"expected_columns":     map[string]any{"type": "array", "items": map[string]any{"type": "string"}, "maxItems": 20},
			"decision":             map[string]any{"type": "string"},
			"root_cause_dimension": map[string]any{"type": "string", "enum": dimensionNames},
			"root_cause_segment":   map[string]any{"type": "string"},
			"confidence":           map[string]any{"type": "number", "minimum": 0, "maximum": 1},
		},
		"required":             []string{"state", "action", "purpose", "sql", "expected_columns", "decision", "root_cause_dimension", "root_cause_segment", "confidence"},
		"additionalProperties": false,
	}
}

const investigationInstructions = `You are a bounded ClickHouse anomaly-investigation agent for advertising telemetry.
Progress through DISCOVER -> CONFIRM -> LOCALIZE -> RULE_OUT -> VERIFY -> FINISH. Emit one JSON action per turn.
Use query actions to obtain evidence. Do not invent values. FINISH only after evidence isolates one approved dimension and segment.

The transcript may contain a deterministic_dimension_sweep. It uses the same seasonal baseline and metric-specific contribution calculation as canonical verification. Treat verified=true rows as canonical root-cause candidates, prioritize the largest positive contribution_pct, use follow-up queries only to distinguish close candidates or rule out alternatives, and FINISH with the exact dimension and segment text from a verified row. Never conclude that only global metrics are available when this sweep is present.

Approved tables and columns:
- ad_events(event_time, app_id, geo_device_id, advertiser_id, ad_format, is_filled, is_impression, is_click, revenue)
- apps(app_id, category, publisher_tier)
- advertisers(advertiser_id, vertical, campaign_type)
- geo_device(geo_device_id, region, country, device_model, os_version)
- metrics_global_1m/window_start and metrics_global_1h/window_start with requests, fills, impressions, clicks, revenue

Rules for every SQL query:
- Only SELECT or WITH. Use unqualified approved table names.
- Use {window_start:String} and {window_end:String} to bound event_time or window_start. Never use now() or future data.
- Use ANY LEFT JOIN for dimension tables and filter the fact time range before joining so unmatched fact rows are retained. Join only the dimension table needed by the query and report attributed-row coverage.
- Advertiser fields are absent on unfilled requests. Do not use advertiser, advertiser vertical, or campaign type to explain requests, fill_rate, or rpr; that missingness is an outcome of the funnel rather than a causal segment.
- Recompute ratios after aggregation: sum(fills)/sum(requests), sum(impressions)/sum(fills), sum(clicks)/sum(impressions), sum(revenue)*1000/sum(impressions), sum(revenue)/sum(requests). Never average a ratio.
- Include a final LIMIT no larger than 1000. Do not include SETTINGS; the application adds hard limits.
- Return explicit aliases and list them in expected_columns.
- CTEs are allowed, but every CTE must ultimately read from an approved table.
- Do not reuse a source column name as an aggregate alias; use names such as total_revenue and total_fills.
- When if/multiIf branches mix integer aggregates with normalized fractional values, cast the integer branch with toFloat64 so ClickHouse does not produce a Variant type.
- Prefer contribution and revenue-impact queries, then confirm the strongest segment and rule out plausible alternatives.
- Put an empty string in finish-only fields during query actions; put empty SQL and expected_columns during FINISH.

All numerical claims in decision must be directly supported by returned rows. If evidence is insufficient, continue querying within the budget.`

func trimRows(rows []map[string]any, limit int) []map[string]any {
	if len(rows) <= limit {
		return rows
	}
	return rows[:limit]
}

func collectRuleOuts(steps []Step) []string {
	seen := map[string]struct{}{}
	for _, step := range steps {
		if step.Action.State != "RULE_OUT" || strings.TrimSpace(step.Action.Decision) == "" {
			continue
		}
		seen[step.Action.Decision] = struct{}{}
	}
	items := make([]string, 0, len(seen))
	for item := range seen {
		items = append(items, item)
	}
	sort.Strings(items)
	return items
}

func clamp(value, low, high float64) float64 {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}
