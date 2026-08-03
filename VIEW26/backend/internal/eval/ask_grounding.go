package eval

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/domain"
)

// OracleResult is independently calculated from the retained-table NDJSON
// snapshot. A retained-data run cannot complete until that snapshot's table
// row count and event-ID fingerprint have been verified.
type OracleResult struct {
	Intent       string         `json:"intent"`
	Evidence     map[string]any `json:"evidence"`
	VerifiedKeys []string       `json:"verified_keys"`
	Completeness string         `json:"completeness"`
	Limitations  []string       `json:"limitations,omitempty"`
}

type GroundingCheck struct {
	Name    string `json:"name"`
	Passed  bool   `json:"passed"`
	Details string `json:"details"`
}

type AskGroundingReport struct {
	Feature      string           `json:"feature"`
	Question     string           `json:"question"`
	Intent       string           `json:"intent"`
	Passed       bool             `json:"passed"`
	Completeness string           `json:"completeness"`
	Checks       []GroundingCheck `json:"checks"`
	Limitations  []string         `json:"limitations,omitempty"`
}

type snapshotRow map[string]any

var tableReferencePattern = regexp.MustCompile(`(?i)\b(?:FROM|JOIN)\s+` + "`([^`]+)`\\.`([^`]+)`")
var questionTokenPattern = regexp.MustCompile(`[^a-z0-9_]+`)
var prosePercentagePattern = regexp.MustCompile(`(?i)([0-9]+(?:\.[0-9]+)?)\s*%`)

// BuildAskOracle deliberately does not inspect the answer SQL. It derives the
// expected result from the feature contract and the table snapshot, giving the
// Ask pipeline and its generated SQL an independent executable oracle.
func BuildAskOracle(run domain.FeatureRun, intent string) (OracleResult, error) {
	rows, err := parseSnapshot(run.Input.EventsNDJSON)
	if err != nil {
		return OracleResult{}, err
	}
	if len(rows) == 0 {
		return OracleResult{}, fmt.Errorf("retained-table snapshot is empty")
	}
	if run.Profile == nil {
		return OracleResult{}, fmt.Errorf("run has no verified event profile")
	}
	if len(rows) != run.Profile.Rows {
		return OracleResult{}, fmt.Errorf("snapshot/profile row mismatch: snapshot=%d profile=%d", len(rows), run.Profile.Rows)
	}

	first, last := eventBounds(*run.Profile)
	grain := analysisGrain(*run.Profile)
	result := OracleResult{Intent: intent, Completeness: "full"}
	switch intent {
	case "feature_completion":
		stages, dashboardGrain := dashboardContract(run)
		result.Evidence = completionEvidence(rows, dashboardGrain, stages[0], stages[len(stages)-1])
	case "group_size_completion":
		stages, dashboardGrain := dashboardContract(run)
		segments := multiDimensionCompletion(rows, dashboardGrain, stages[0], stages[len(stages)-1], []string{"group_size"}, 0, "groups_started", "groups_submitted")
		result.Evidence = map[string]any{"segments": segments, "lowest_completion_segment": extreme(segments, "completion_rate", false)}
	case "group_traveller_churn":
		result.Evidence = groupChurnEvidence(rows)
	case "group_document_bottleneck":
		segments := groupDocumentEvidence(rows)
		result.Evidence = map[string]any{"segments": segments, "lowest_submission_segment": extreme(segments, "submission_rate", false)}
	case "group_segments":
		segments := multiDimensionCompletion(rows, grain, first, last, []string{"destination", "device_type", "geoip_country_code"}, 0, "groups_started", "groups_submitted")
		sort.SliceStable(segments, func(i, j int) bool {
			if number(segments[i]["groups_started"]) == number(segments[j]["groups_started"]) {
				return number(segments[i]["completion_rate"]) > number(segments[j]["completion_rate"])
			}
			return number(segments[i]["groups_started"]) > number(segments[j]["groups_started"])
		})
		result.Evidence = map[string]any{"segments": segments, "largest_segment": firstRow(segments)}
	case "platform_failure":
		segments := platformEvidence(rows, grain, last, eventContaining(*run.Profile, "otp"))
		result.Evidence = map[string]any{"segments": segments, "worst_segment": firstRow(segments)}
	case "latency_performance":
		result.Evidence = latencyEvidence(rows, last, fieldContaining(*run.Profile, "latency_ms"))
	case "feature_adoption":
		selected := eventContaining(*run.Profile, "selected")
		if selected == "" && len(run.Profile.EventOrder) > 1 {
			selected = run.Profile.EventOrder[1]
		}
		question := strings.ToLower(runQuestion(run, intent))
		var segments []map[string]any
		if (strings.Contains(question, "currency pair") || strings.Contains(question, "currencies")) && hasField(*run.Profile, "from_currency") && hasField(*run.Profile, "to_currency") {
			segments = currencyPairAdoptionEvidence(rows, grain, first, selected)
		} else {
			segments = adoptionEvidence(rows, grain, first, selected, hasField(*run.Profile, "saved_method_type"))
		}
		result.Evidence = map[string]any{"segments": segments, "top_adoption_segment": firstMetric(segments, "adoption_rate")}
	case "conversion_comparison":
		// The retained feature snapshot cannot independently reconstruct the
		// pay_now_clicked/purchase_completed control cohort. It still verifies
		// every feature-side value and explicitly reports the join boundary.
		base := completionEvidence(rows, grain, first, last)
		result.Evidence = map[string]any{
			"feature_entrants":        base["entrants"],
			"feature_completions":     base["completions"],
			"feature_completion_rate": base["completion_rate"],
		}
		result.Completeness = "partial"
		result.Limitations = []string{"The standard-checkout control cohort requires an independent direct read of pay_now_clicked and purchase_completed; the feature-side cohort is fully verified."}
	case "segment_comparison":
		stages, dashboardGrain := dashboardContract(run)
		requested := requestedDimensions(run, runQuestion(run, intent))
		if len(requested) == 0 {
			requested = governedDimensions(*run.Profile)
		}
		segments := multiDimensionCompletion(rows, dashboardGrain, stages[0], stages[len(stages)-1], requested, 20, "entrants", "completions")
		sort.SliceStable(segments, func(i, j int) bool {
			if text(segments[i]["dimension"]) != text(segments[j]["dimension"]) {
				return text(segments[i]["dimension"]) < text(segments[j]["dimension"])
			}
			if number(segments[i]["completion_rate"]) != number(segments[j]["completion_rate"]) {
				return number(segments[i]["completion_rate"]) > number(segments[j]["completion_rate"])
			}
			return number(segments[i]["entrants"]) > number(segments[j]["entrants"])
		})
		result.Evidence = map[string]any{"segments": segments, "best_segment": extreme(segments, "completion_rate", true), "weakest_segment": extreme(segments, "completion_rate", false)}
	case "funnel_diagnosis":
		stages, dashboardGrain := dashboardContract(run)
		stageRows := funnelEvidence(rows, dashboardGrain, stages)
		result.Evidence = map[string]any{"stages": stageRows, "largest_drop": largestDrop(stageRows)}
	case "completion_trend":
		stages, dashboardGrain := dashboardContract(run)
		series := trendEvidence(rows, dashboardGrain, stages[0], stages[len(stages)-1])
		latestRate := float64(0)
		change := float64(0)
		if len(series) > 0 {
			latestRate = number(series[len(series)-1]["completion_rate"])
			change = latestRate - number(series[0]["completion_rate"])
		}
		result.Evidence = map[string]any{"trend_series": series, "latest_completion_rate": latestRate, "percentage_point_change": change}
	case "recovery_drop_step":
		segments := recoveryDropStepEvidence(rows)
		result.Evidence = map[string]any{"segments": segments, "most_recoverable_step": extreme(segments, "recovery_rate", true)}
	case "recovery_channel":
		segments := recoveryChannelEvidence(rows)
		result.Evidence = map[string]any{"segments": segments, "best_channel": extreme(segments, "recovery_rate", true)}
	case "recovery_timing":
		segments := recoveryTimingEvidence(rows)
		result.Evidence = map[string]any{"segments": segments, "best_timing": extreme(segments, "recovery_rate", true)}
	case "recovery_segments":
		segments := recoverySegmentEvidence(rows, grain)
		result.Evidence = map[string]any{"segments": segments, "largest_recovery_segment": firstRow(segments)}
	default:
		return OracleResult{}, fmt.Errorf("no independent oracle is registered for intent %q", intent)
	}
	for key := range result.Evidence {
		result.VerifiedKeys = append(result.VerifiedKeys, key)
	}
	sort.Strings(result.VerifiedKeys)
	return result, nil
}

// ValidateAskGrounding checks numerical truth and the context-layer trust
// contract. Extra evidence is allowed, but every oracle field must match.
func ValidateAskGrounding(run domain.FeatureRun, answer domain.QuestionResponse, oracle OracleResult) AskGroundingReport {
	report := AskGroundingReport{Feature: run.Input.Name, Question: answer.Contract.Question, Intent: answer.Contract.Intent, Passed: true, Completeness: oracle.Completeness, Limitations: oracle.Limitations}
	add := func(name string, passed bool, details string) {
		report.Checks = append(report.Checks, GroundingCheck{Name: name, Passed: passed, Details: details})
		if !passed {
			report.Passed = false
		}
	}

	add("feature_route", strings.EqualFold(answer.Contract.Feature, run.Input.Name), fmt.Sprintf("answer=%q expected=%q", answer.Contract.Feature, run.Input.Name))
	add("intent_route", answer.Contract.Intent == oracle.Intent, fmt.Sprintf("answer=%q expected=%q", answer.Contract.Intent, oracle.Intent))
	wantedTable := ""
	if run.Schema != nil {
		wantedTable = run.Schema.Database + "." + run.Schema.Table
	}
	add("feature_table_allowlisted", wantedTable != "" && contains(answer.Contract.AllowedTables, wantedTable), fmt.Sprintf("wanted=%s allowed=%v", wantedTable, answer.Contract.AllowedTables))
	unauthorized := unauthorizedTables(answer.Insight.SQL, answer.Contract.AllowedTables)
	add("sql_allowlist", len(unauthorized) == 0, fmt.Sprintf("unauthorized=%v", unauthorized))
	add("context_version_consistent", answer.Contract.ContextVersion > 0 && answer.Contract.ContextVersion == answer.Insight.ContextVersion, fmt.Sprintf("contract=v%d insight=v%d", answer.Contract.ContextVersion, answer.Insight.ContextVersion))
	add("schema_version_consistent", contains(answer.Contract.SchemaVersions, answer.Insight.SchemaVersion), fmt.Sprintf("contract=%v insight=%s", answer.Contract.SchemaVersions, answer.Insight.SchemaVersion))
	add("clickhouse_execution", text(answer.Insight.Evidence["execution_mode"]) == "clickhouse", fmt.Sprintf("execution_mode=%v", answer.Insight.Evidence["execution_mode"]))
	tracePassed, traceDetail := validateQueryTrace(answer)
	add("query_trace", tracePassed, traceDetail)
	missing := missingRequiredEvidence(answer.Contract.RequiredEvidence, answer.Insight.Evidence)
	add("required_evidence", len(missing) == 0, fmt.Sprintf("missing=%v", missing))
	requestedDimensions := inferQuestionDimensions(*run.Profile, answer.Contract.Question)
	uncoveredDimensions := uncoveredQuestionDimensions(requestedDimensions, answer)
	add("question_dimension_coverage", len(uncoveredDimensions) == 0, fmt.Sprintf("requested=%v uncovered=%v", requestedDimensions, uncoveredDimensions))
	ungroundedPercentages := ungroundedProsePercentages(answer)
	add("prose_percentage_grounding", len(ungroundedPercentages) == 0, fmt.Sprintf("ungrounded=%v", ungroundedPercentages))
	anchorPassed, anchorDetails := validateAnswerAnchor(answer)
	add("answer_anchor", anchorPassed, anchorDetails)
	if mismatches := compareEvidence(oracle.Evidence, answer.Insight.Evidence, "evidence"); len(mismatches) > 0 {
		add("table_truth", false, strings.Join(mismatches, "; "))
	} else {
		add("table_truth", true, fmt.Sprintf("matched independent keys %v", oracle.VerifiedKeys))
	}
	return report
}

func inferQuestionDimensions(profile domain.EventProfile, question string) []string {
	normalized := " " + strings.TrimSpace(questionTokenPattern.ReplaceAllString(strings.ToLower(question), " ")) + " "
	type candidate struct {
		field   string
		aliases []string
	}
	candidates := []candidate{
		{field: "device_type", aliases: []string{"device", "devices", "device type", "device_type", "mobile", "platform"}},
		{field: "os", aliases: []string{" os ", "operating system", "platform"}},
		{field: "app_version", aliases: []string{"app version", "app_version", "client version"}},
		{field: "geoip_country_code", aliases: []string{" geo ", "geography", "geoip", "geoip_country_code", "country", "countries"}},
		{field: "city", aliases: []string{"city", "cities"}},
		{field: "destination", aliases: []string{"destination", "destinations"}},
		{field: "channel", aliases: []string{"channel", "channels"}},
		{field: "saved_method_type", aliases: []string{"saved method", "saved method type", "saved_method_type", "payment method"}},
		{field: "group_size", aliases: []string{"group size", "group_size", "party size"}},
		{field: "status_shared", aliases: []string{"status shared", "status_shared", "approval status"}},
		{field: "recipient_is_new_user", aliases: []string{"new user", "recipient_is_new_user", "recipient type"}},
		{field: "from_currency", aliases: []string{"from currency", "source currency", "currency pair", "currencies"}},
		{field: "to_currency", aliases: []string{"to currency", "target currency", "currency pair", "currencies"}},
		{field: "source_currency", aliases: []string{"from currency", "source currency", "currency pair", "currencies"}},
		{field: "target_currency", aliases: []string{"to currency", "target currency", "currency pair", "currencies"}},
		{field: "currency", aliases: []string{"currency", "currencies"}},
	}
	requested := []string{}
	for _, candidate := range candidates {
		if !hasField(profile, candidate.field) {
			continue
		}
		for _, alias := range candidate.aliases {
			needle := alias
			if !strings.HasPrefix(needle, " ") {
				needle = " " + needle
			}
			if !strings.HasSuffix(needle, " ") {
				needle += " "
			}
			if strings.Contains(normalized, needle) {
				requested = append(requested, candidate.field)
				break
			}
		}
	}
	return unique(requested)
}

func ungroundedProsePercentages(answer domain.QuestionResponse) []float64 {
	prose := strings.Join([]string{answer.Insight.Headline, answer.Insight.Summary, answer.Insight.Why, answer.Insight.RecommendedAction}, " ")
	evidenceNumbers := []float64{answer.Insight.Confidence}
	collectEvidenceNumbers(answer.Insight.Evidence, &evidenceNumbers)
	ungrounded := []float64{}
	for _, match := range prosePercentagePattern.FindAllStringSubmatch(prose, -1) {
		claimed, err := strconv.ParseFloat(match[1], 64)
		if err != nil {
			continue
		}
		grounded := false
		for _, evidenceValue := range evidenceNumbers {
			if math.Abs(claimed-evidenceValue) <= .12 || math.Abs(claimed-evidenceValue*100) <= .12 {
				grounded = true
				break
			}
		}
		if !grounded {
			ungrounded = append(ungrounded, claimed)
		}
	}
	return ungrounded
}

func collectEvidenceNumbers(value any, output *[]float64) {
	if parsed, ok := numeric(value); ok {
		*output = append(*output, parsed)
		return
	}
	switch typed := value.(type) {
	case map[string]any:
		for _, nested := range typed {
			collectEvidenceNumbers(nested, output)
		}
	case []map[string]any:
		for _, row := range typed {
			collectEvidenceNumbers(row, output)
		}
	case []any:
		for _, nested := range typed {
			collectEvidenceNumbers(nested, output)
		}
	}
}

func validateAnswerAnchor(answer domain.QuestionResponse) (bool, string) {
	type anchorDefinition struct {
		evidenceKey string
		fields      []string
	}
	definitions := []anchorDefinition{
		{evidenceKey: "lowest_completion_segment", fields: []string{"group_size"}},
		{evidenceKey: "lowest_submission_segment", fields: []string{"group_size"}},
		{evidenceKey: "largest_segment", fields: []string{"segment"}},
		{evidenceKey: "worst_segment", fields: []string{"device_type", "os"}},
		{evidenceKey: "top_adoption_segment", fields: []string{"segment"}},
		{evidenceKey: "most_recoverable_step", fields: []string{"drop_step"}},
		{evidenceKey: "best_channel", fields: []string{"channel"}},
		{evidenceKey: "best_timing", fields: []string{"hours_since_drop"}},
		{evidenceKey: "largest_recovery_segment", fields: []string{"segment"}},
		{evidenceKey: "best_segment", fields: []string{"segment"}},
		{evidenceKey: "weakest_segment", fields: []string{"segment"}},
		{evidenceKey: "largest_drop", fields: []string{"to_stage"}},
	}
	prose := strings.ToLower(answer.Insight.Headline + " " + answer.Insight.Summary)
	for _, definition := range definitions {
		value, exists := answer.Insight.Evidence[definition.evidenceKey]
		if !exists {
			continue
		}
		row, ok := value.(map[string]any)
		if !ok {
			continue
		}
		anchors := []string{}
		for _, field := range definition.fields {
			anchor := strings.ToLower(text(row[field]))
			if anchor != "" {
				anchors = append(anchors, anchor)
				if strings.Contains(prose, anchor) {
					return true, fmt.Sprintf("%s=%s is present in the answer", definition.evidenceKey, anchor)
				}
			}
		}
		return false, fmt.Sprintf("%s anchors %v are absent from headline and summary", definition.evidenceKey, anchors)
	}
	return true, "no ranked answer anchor is required for this intent"
}

func uncoveredQuestionDimensions(requested []string, answer domain.QuestionResponse) []string {
	if len(requested) == 0 {
		return nil
	}
	rows, _ := asRows(answer.Insight.Evidence["segments"])
	uncovered := []string{}
	for _, dimension := range requested {
		contractCovered := contains(answer.Contract.Dimensions, dimension)
		evidenceCovered := false
		for _, row := range rows {
			if text(row["dimension"]) == dimension {
				evidenceCovered = true
				break
			}
			if _, ok := row[dimension]; ok {
				evidenceCovered = true
				break
			}
		}
		if !contractCovered || !evidenceCovered {
			uncovered = append(uncovered, dimension)
		}
	}
	return uncovered
}

func ValidateFailClosed(answer domain.QuestionResponse) []GroundingCheck {
	checks := []GroundingCheck{
		{Name: "not_answerable_contract", Passed: answer.Contract.Answerability == "not_answerable", Details: "answerability=" + answer.Contract.Answerability},
		{Name: "no_sql", Passed: strings.TrimSpace(answer.Insight.SQL) == "", Details: fmt.Sprintf("sql_bytes=%d", len(strings.TrimSpace(answer.Insight.SQL)))},
		{Name: "not_executed", Passed: text(answer.Insight.Evidence["execution_mode"]) == "not_executed", Details: fmt.Sprintf("execution_mode=%v", answer.Insight.Evidence["execution_mode"])},
	}
	querySkipped := false
	if answer.Insight.Trace != nil {
		for _, step := range answer.Insight.Trace.Steps {
			if step.ID == "tool.clickhouse.query" && step.Status == "skipped" {
				querySkipped = true
			}
		}
	}
	checks = append(checks, GroundingCheck{Name: "query_skipped", Passed: querySkipped, Details: fmt.Sprintf("skipped=%t", querySkipped)})
	return checks
}

func parseSnapshot(ndjson string) ([]snapshotRow, error) {
	scanner := bufio.NewScanner(strings.NewReader(ndjson))
	scanner.Buffer(make([]byte, 64*1024), 16*1024*1024)
	rows := []snapshotRow{}
	for scanner.Scan() {
		if strings.TrimSpace(scanner.Text()) == "" {
			continue
		}
		decoder := json.NewDecoder(strings.NewReader(scanner.Text()))
		decoder.UseNumber()
		row := snapshotRow{}
		if err := decoder.Decode(&row); err != nil {
			return nil, fmt.Errorf("decode snapshot row %d: %w", len(rows)+1, err)
		}
		rows = append(rows, row)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return rows, nil
}

func completionEvidence(rows []snapshotRow, grain, first, last string) map[string]any {
	entrants := distinctWhere(rows, grain, func(row snapshotRow) bool { return event(row) == first })
	completions := distinctWhere(rows, grain, func(row snapshotRow) bool { return event(row) == last })
	return map[string]any{"entrants": float64(entrants), "completions": float64(completions), "completion_rate": divide(float64(completions), float64(entrants))}
}

func segmentedCompletion(rows []snapshotRow, grain, first, last, dimension string, minimum int) []map[string]any {
	return multiDimensionCompletion(rows, grain, first, last, []string{dimension}, minimum, "entrants", "completions")
}

func multiDimensionCompletion(rows []snapshotRow, grain, first, last string, dimensions []string, minimum int, entrantKey, completionKey string) []map[string]any {
	output := []map[string]any{}
	for _, dimension := range dimensions {
		type entityState struct {
			segment            string
			entered, completed bool
		}
		entities := map[string]*entityState{}
		for _, row := range rows {
			id := text(row[grain])
			if id == "" {
				continue
			}
			state := entities[id]
			if state == nil {
				state = &entityState{}
				entities[id] = state
			}
			if event(row) == first {
				state.entered = true
				state.segment = nullableText(row[dimension])
			}
			if event(row) == last {
				state.completed = true
			}
		}
		type counts struct{ entrants, completions int }
		groups := map[string]*counts{}
		for _, state := range entities {
			if !state.entered {
				continue
			}
			group := groups[state.segment]
			if group == nil {
				group = &counts{}
				groups[state.segment] = group
			}
			group.entrants++
			if state.completed {
				group.completions++
			}
		}
		for segment, group := range groups {
			if group.entrants < minimum {
				continue
			}
			row := map[string]any{"dimension": dimension, "segment": segment, entrantKey: float64(group.entrants), completionKey: float64(group.completions), "completion_rate": divide(float64(group.completions), float64(group.entrants))}
			if len(dimensions) == 1 && dimension == "group_size" {
				row["group_size"] = parseDimension(segment)
				delete(row, "dimension")
				delete(row, "segment")
			}
			output = append(output, row)
		}
	}
	if len(dimensions) == 1 && dimensions[0] == "group_size" {
		sort.SliceStable(output, func(i, j int) bool { return number(output[i]["group_size"]) < number(output[j]["group_size"]) })
	}
	return output
}

func groupChurnEvidence(rows []snapshotRow) map[string]any {
	groups := distinctWhere(rows, "group_id", func(row snapshotRow) bool { return event(row) == "group_started" })
	added, removed := 0, 0
	for _, row := range rows {
		switch event(row) {
		case "traveller_added":
			added++
		case "traveller_removed":
			removed++
		}
	}
	return map[string]any{
		"groups_started": float64(groups), "travellers_added": float64(added), "travellers_removed": float64(removed),
		"additions_per_group": divide(float64(added), float64(groups)), "removals_per_group": divide(float64(removed), float64(groups)),
		"removal_to_addition_rate": divide(float64(removed), float64(added)),
	}
}

func groupDocumentEvidence(rows []snapshotRow) []map[string]any {
	type state struct {
		size                        float64
		hasDocs, allDocs, submitted bool
	}
	groups := map[string]*state{}
	for _, row := range rows {
		id := text(row["group_id"])
		if id == "" {
			continue
		}
		group := groups[id]
		if group == nil {
			group = &state{allDocs: true}
			groups[id] = group
		}
		if value := number(row["group_size"]); !math.IsNaN(value) && value != 0 {
			group.size = value
		}
		if event(row) == "traveller_added" {
			group.hasDocs = true
			if number(row["docs_complete"]) != 1 {
				group.allDocs = false
			}
		}
		if event(row) == "group_submitted" {
			group.submitted = true
		}
	}
	type key struct {
		size     int
		complete bool
	}
	type counts struct{ groups, submissions int }
	cohorts := map[key]*counts{}
	for _, group := range groups {
		complete := group.hasDocs && group.allDocs
		cohortKey := key{size: int(group.size), complete: complete}
		cohort := cohorts[cohortKey]
		if cohort == nil {
			cohort = &counts{}
			cohorts[cohortKey] = cohort
		}
		cohort.groups++
		if group.submitted {
			cohort.submissions++
		}
	}
	output := []map[string]any{}
	for cohortKey, cohort := range cohorts {
		complete := float64(0)
		if cohortKey.complete {
			complete = 1
		}
		output = append(output, map[string]any{"group_size": float64(cohortKey.size), "all_docs_complete": complete, "groups": float64(cohort.groups), "submissions": float64(cohort.submissions), "submission_rate": divide(float64(cohort.submissions), float64(cohort.groups))})
	}
	sort.SliceStable(output, func(i, j int) bool {
		if number(output[i]["group_size"]) == number(output[j]["group_size"]) {
			return number(output[i]["all_docs_complete"]) > number(output[j]["all_docs_complete"])
		}
		return number(output[i]["group_size"]) < number(output[j]["group_size"])
	})
	return output
}

func platformEvidence(rows []snapshotRow, grain, last, otpEvent string) []map[string]any {
	type counts struct {
		entries       int
		success       float64
		successes     int
		confirmations map[string]bool
	}
	groups := map[string]*counts{}
	for _, row := range rows {
		device, osName := nullableText(row["device_type"]), nullableText(row["os"])
		key := device + "\x00" + osName
		group := groups[key]
		if group == nil {
			group = &counts{confirmations: map[string]bool{}}
			groups[key] = group
		}
		if event(row) == otpEvent {
			group.entries++
			value := number(row["otp_success"])
			if !math.IsNaN(value) {
				group.success += value
				group.successes++
			}
		}
		if event(row) == last && text(row[grain]) != "" {
			group.confirmations[text(row[grain])] = true
		}
	}
	output := []map[string]any{}
	for key, group := range groups {
		if group.entries == 0 {
			continue
		}
		parts := strings.Split(key, "\x00")
		output = append(output, map[string]any{"device_type": parts[0], "os": parts[1], "otp_entries": float64(group.entries), "otp_success_rate": divide(group.success, float64(group.successes)), "confirmations": float64(len(group.confirmations)), "confirmation_from_otp": divide(float64(len(group.confirmations)), float64(group.entries))})
	}
	sort.SliceStable(output, func(i, j int) bool {
		if number(output[i]["otp_success_rate"]) == number(output[j]["otp_success_rate"]) {
			return number(output[i]["confirmation_from_otp"]) < number(output[j]["confirmation_from_otp"])
		}
		return number(output[i]["otp_success_rate"]) < number(output[j]["otp_success_rate"])
	})
	return output
}

func latencyEvidence(rows []snapshotRow, last, field string) map[string]any {
	values := []float64{}
	for _, row := range rows {
		if event(row) == last {
			if value := number(row[field]); !math.IsNaN(value) {
				values = append(values, value)
			}
		}
	}
	sort.Float64s(values)
	average := float64(0)
	for _, value := range values {
		average += value
	}
	if len(values) > 0 {
		average /= float64(len(values))
	}
	return map[string]any{"payments": float64(len(values)), "avg_latency_ms": round(average, 1), "p50_latency_ms": quantileExact(values, .5), "p95_latency_ms": quantileExact(values, .95)}
}

func adoptionEvidence(rows []snapshotRow, grain, first, selected string, savedMethod bool) []map[string]any {
	output := []map[string]any{}
	for _, dimension := range []string{"device_type", "geoip_country_code"} {
		output = append(output, adoptionByDimension(rows, grain, first, selected, dimension)...)
	}
	if savedMethod {
		denominator := distinctWhere(rows, grain, func(row snapshotRow) bool { return event(row) == selected })
		groups := map[string]map[string]bool{}
		for _, row := range rows {
			if event(row) != selected || text(row[grain]) == "" {
				continue
			}
			segment := nullableText(row["saved_method_type"])
			if groups[segment] == nil {
				groups[segment] = map[string]bool{}
			}
			if row["saved_method_type"] != nil && text(row["saved_method_type"]) != "" {
				groups[segment][text(row[grain])] = true
			}
		}
		for segment, ids := range groups {
			output = append(output, map[string]any{"dimension": "saved_method_type", "segment": segment, "metric": "selected_share", "denominator": float64(denominator), "numerator": float64(len(ids)), "rate": divide(float64(len(ids)), float64(denominator))})
		}
	}
	sort.SliceStable(output, func(i, j int) bool {
		if text(output[i]["metric"]) != text(output[j]["metric"]) {
			return text(output[i]["metric"]) < text(output[j]["metric"])
		}
		return number(output[i]["rate"]) > number(output[j]["rate"])
	})
	return output
}

func currencyPairAdoptionEvidence(rows []snapshotRow, grain, first, selected string) []map[string]any {
	type entityState struct {
		from, to          string
		entered, selected bool
	}
	entities := map[string]*entityState{}
	for _, row := range rows {
		id := text(row[grain])
		if id == "" {
			continue
		}
		state := entities[id]
		if state == nil {
			state = &entityState{}
			entities[id] = state
		}
		if event(row) == first {
			state.entered = true
			state.from = text(row["from_currency"])
			state.to = text(row["to_currency"])
		}
		if event(row) == selected {
			state.selected = true
		}
	}
	type counts struct{ denominator, numerator int }
	groups := map[string]*counts{}
	for _, state := range entities {
		if !state.entered {
			continue
		}
		key := state.from + "\x00" + state.to
		group := groups[key]
		if group == nil {
			group = &counts{}
			groups[key] = group
		}
		group.denominator++
		if state.selected {
			group.numerator++
		}
	}
	output := make([]map[string]any, 0, len(groups))
	for key, group := range groups {
		parts := strings.SplitN(key, "\x00", 2)
		output = append(output, map[string]any{
			"dimension": "currency_pair", "from_currency": parts[0], "to_currency": parts[1], "segment": parts[0] + " → " + parts[1],
			"metric": "adoption_rate", "denominator": float64(group.denominator), "numerator": float64(group.numerator),
			"rate": divide(float64(group.numerator), float64(group.denominator)),
		})
	}
	sort.SliceStable(output, func(i, j int) bool {
		if number(output[i]["rate"]) == number(output[j]["rate"]) {
			return text(output[i]["segment"]) < text(output[j]["segment"])
		}
		return number(output[i]["rate"]) > number(output[j]["rate"])
	})
	return output
}

func adoptionByDimension(rows []snapshotRow, grain, first, selected, dimension string) []map[string]any {
	type sets struct{ denominator, numerator map[string]bool }
	groups := map[string]*sets{}
	for _, row := range rows {
		if event(row) != first && event(row) != selected {
			continue
		}
		segment := nullableText(row[dimension])
		group := groups[segment]
		if group == nil {
			group = &sets{denominator: map[string]bool{}, numerator: map[string]bool{}}
			groups[segment] = group
		}
		id := text(row[grain])
		if event(row) == first {
			group.denominator[id] = true
		}
		if event(row) == selected {
			group.numerator[id] = true
		}
	}
	output := []map[string]any{}
	for segment, group := range groups {
		output = append(output, map[string]any{"dimension": dimension, "segment": segment, "metric": "adoption_rate", "denominator": float64(len(group.denominator)), "numerator": float64(len(group.numerator)), "rate": divide(float64(len(group.numerator)), float64(len(group.denominator)))})
	}
	return output
}

func recoveryDropStepEvidence(rows []snapshotRow) []map[string]any {
	states := recoveryStates(rows)
	type counts struct{ abandonments, reconversions int }
	groups := map[string]*counts{}
	for _, state := range states {
		group := groups[state.dropStep]
		if group == nil {
			group = &counts{}
			groups[state.dropStep] = group
		}
		group.abandonments++
		if state.reconverted {
			group.reconversions++
		}
	}
	output := []map[string]any{}
	for segment, group := range groups {
		output = append(output, map[string]any{"drop_step": segment, "abandonments": float64(group.abandonments), "reconversions": float64(group.reconversions), "recovery_rate": divide(float64(group.reconversions), float64(group.abandonments))})
	}
	sortByMetric(output, "recovery_rate", true, "abandonments")
	return output
}

type recoveryState struct {
	dropStep, channel            string
	timing                       float64
	opened, clicked, reconverted bool
}

func recoveryStates(rows []snapshotRow) map[string]*recoveryState {
	states := map[string]*recoveryState{}
	for _, row := range rows {
		id := text(row["application_id"])
		if id == "" {
			continue
		}
		state := states[id]
		if state == nil {
			state = &recoveryState{dropStep: "unknown", channel: "unknown"}
			states[id] = state
		}
		switch event(row) {
		case "abandonment_detected":
			state.dropStep = nullableText(row["drop_step"])
		case "reminder_sent":
			state.channel = nullableText(row["channel"])
			state.timing = number(row["hours_since_drop"])
		case "reminder_opened":
			state.opened = true
		case "reminder_cta_clicked":
			state.clicked = true
		case "reconverted":
			state.reconverted = true
		}
	}
	return states
}

func recoveryChannelEvidence(rows []snapshotRow) []map[string]any {
	type counts struct{ reminders, opens, clicks, reconversions int }
	groups := map[string]*counts{}
	for _, state := range recoveryStates(rows) {
		group := groups[state.channel]
		if group == nil {
			group = &counts{}
			groups[state.channel] = group
		}
		group.reminders++
		if state.opened {
			group.opens++
		}
		if state.clicked {
			group.clicks++
		}
		if state.reconverted {
			group.reconversions++
		}
	}
	output := []map[string]any{}
	for channel, group := range groups {
		output = append(output, map[string]any{"channel": channel, "reminders": float64(group.reminders), "opens": float64(group.opens), "clicks": float64(group.clicks), "reconversions": float64(group.reconversions), "open_rate": divide(float64(group.opens), float64(group.reminders)), "click_from_open_rate": divide(float64(group.clicks), float64(group.opens)), "recovery_rate": divide(float64(group.reconversions), float64(group.reminders))})
	}
	sortByMetric(output, "recovery_rate", true, "reminders")
	return output
}

func recoveryTimingEvidence(rows []snapshotRow) []map[string]any {
	type counts struct{ reminders, opens, reconversions int }
	groups := map[float64]*counts{}
	for _, state := range recoveryStates(rows) {
		group := groups[state.timing]
		if group == nil {
			group = &counts{}
			groups[state.timing] = group
		}
		group.reminders++
		if state.opened {
			group.opens++
		}
		if state.reconverted {
			group.reconversions++
		}
	}
	output := []map[string]any{}
	for timing, group := range groups {
		output = append(output, map[string]any{"hours_since_drop": timing, "reminders": float64(group.reminders), "opens": float64(group.opens), "reconversions": float64(group.reconversions), "open_rate": divide(float64(group.opens), float64(group.reminders)), "recovery_rate": divide(float64(group.reconversions), float64(group.reminders))})
	}
	sort.SliceStable(output, func(i, j int) bool {
		return number(output[i]["hours_since_drop"]) < number(output[j]["hours_since_drop"])
	})
	return output
}

func recoverySegmentEvidence(rows []snapshotRow, grain string) []map[string]any {
	segments := []map[string]any{}
	for _, dimension := range []string{"device_type", "geoip_country_code", "destination"} {
		values := multiDimensionRecovery(rows, grain, dimension)
		segments = append(segments, values...)
	}
	sort.SliceStable(segments, func(i, j int) bool {
		if number(segments[i]["reconversions"]) == number(segments[j]["reconversions"]) {
			return number(segments[i]["recovery_rate"]) > number(segments[j]["recovery_rate"])
		}
		return number(segments[i]["reconversions"]) > number(segments[j]["reconversions"])
	})
	return segments
}

func multiDimensionRecovery(rows []snapshotRow, grain, dimension string) []map[string]any {
	type sets struct{ abandoned, recovered map[string]bool }
	groups := map[string]*sets{}
	for _, row := range rows {
		if event(row) != "abandonment_detected" && event(row) != "reconverted" {
			continue
		}
		segment := nullableText(row[dimension])
		group := groups[segment]
		if group == nil {
			group = &sets{abandoned: map[string]bool{}, recovered: map[string]bool{}}
			groups[segment] = group
		}
		if event(row) == "abandonment_detected" {
			group.abandoned[text(row[grain])] = true
		} else {
			group.recovered[text(row[grain])] = true
		}
	}
	output := []map[string]any{}
	for segment, group := range groups {
		output = append(output, map[string]any{"dimension": dimension, "segment": segment, "abandonments": float64(len(group.abandoned)), "reconversions": float64(len(group.recovered)), "recovery_rate": divide(float64(len(group.recovered)), float64(len(group.abandoned)))})
	}
	return output
}

func funnelEvidence(rows []snapshotRow, grain string, stages []string) []map[string]any {
	output := []map[string]any{}
	for index, stage := range stages {
		output = append(output, map[string]any{"step": float64(index + 1), "stage": stage, "entities": float64(distinctWhere(rows, grain, func(row snapshotRow) bool { return event(row) == stage }))})
	}
	return output
}

func largestDrop(stages []map[string]any) map[string]any {
	if len(stages) == 0 {
		return map[string]any{}
	}
	result := map[string]any{"from_stage": text(stages[0]["stage"]), "to_stage": text(stages[0]["stage"]), "drop": float64(0), "retention_rate": float64(1)}
	for index := 1; index < len(stages); index++ {
		previous, current := number(stages[index-1]["entities"]), number(stages[index]["entities"])
		if previous-current > number(result["drop"]) {
			result = map[string]any{"from_stage": text(stages[index-1]["stage"]), "to_stage": text(stages[index]["stage"]), "drop": previous - current, "retention_rate": rawDivide(current, previous)}
		}
	}
	return result
}

func trendEvidence(rows []snapshotRow, grain, first, last string) []map[string]any {
	minDate, maxDate := time.Time{}, time.Time{}
	for _, row := range rows {
		date, ok := timestamp(row)
		if !ok {
			continue
		}
		if minDate.IsZero() || date.Before(minDate) {
			minDate = date
		}
		if maxDate.IsZero() || date.After(maxDate) {
			maxDate = date
		}
	}
	granularity := "week"
	if !minDate.IsZero() && int(maxDate.Sub(minDate).Hours()/24)+1 >= 120 {
		granularity = "month"
	}
	type sets struct{ entrants, completions map[string]bool }
	periods := map[string]*sets{}
	for _, row := range rows {
		date, ok := timestamp(row)
		if !ok {
			continue
		}
		period := periodStart(date, granularity)
		group := periods[period]
		if group == nil {
			group = &sets{entrants: map[string]bool{}, completions: map[string]bool{}}
			periods[period] = group
		}
		if event(row) == first {
			group.entrants[text(row[grain])] = true
		}
		if event(row) == last {
			group.completions[text(row[grain])] = true
		}
	}
	output := []map[string]any{}
	for period, group := range periods {
		if len(group.entrants) == 0 {
			continue
		}
		output = append(output, map[string]any{"granularity": granularity, "date": period, "entrants": float64(len(group.entrants)), "completions": float64(len(group.completions)), "completion_rate": divide(float64(len(group.completions)), float64(len(group.entrants)))})
	}
	sort.SliceStable(output, func(i, j int) bool { return text(output[i]["date"]) < text(output[j]["date"]) })
	return output
}

func dashboardContract(run domain.FeatureRun) ([]string, string) {
	stages := append([]string{}, run.Profile.EventOrder...)
	grain := analysisGrain(*run.Profile)
	slug := strings.ToLower(strings.ReplaceAll(run.Input.Name, " ", "_"))
	candidates := []string{}
	switch {
	case strings.Contains(slug, "express_checkout"):
		candidates = []string{"express_checkout_shown", "express_checkout_selected", "otp_entered", "express_payment_confirmed"}
	case strings.Contains(slug, "group") || strings.Contains(slug, "family"):
		candidates = []string{"group_started", "traveller_added", "group_submitted"}
		if hasField(*run.Profile, "group_id") {
			grain = "group_id"
		}
	case strings.Contains(slug, "status_sharing"):
		candidates = []string{"link_generated", "link_opened", "recipient_cta_clicked"}
		if hasField(*run.Profile, "share_id") {
			grain = "share_id"
		}
	case strings.Contains(slug, "abandoned_checkout_recovery"):
		candidates = []string{"abandonment_detected", "reminder_sent", "reminder_opened", "reminder_cta_clicked", "reconverted"}
	case strings.Contains(slug, "forex"):
		candidates = []string{"forex_offer_shown", "currency_selected", "forex_added_to_cart", "forex_purchased"}
	}
	if len(candidates) > 0 {
		present := map[string]bool{}
		for _, value := range stages {
			present[value] = true
		}
		stages = nil
		for _, value := range candidates {
			if present[value] {
				stages = append(stages, value)
			}
		}
	}
	return stages, grain
}

func validateQueryTrace(answer domain.QuestionResponse) (bool, string) {
	if answer.Insight.Trace == nil {
		return false, "analysis trace is missing"
	}
	for _, step := range answer.Insight.Trace.Steps {
		if step.ID != "tool.clickhouse.query" {
			continue
		}
		inputSQL := text(step.Input["sql"])
		return step.Status == "completed" && inputSQL == answer.Insight.SQL, fmt.Sprintf("status=%s sql_matches=%t", step.Status, inputSQL == answer.Insight.SQL)
	}
	return false, "ClickHouse query step is missing"
}

func unauthorizedTables(sql string, allowed []string) []string {
	allowedSet := map[string]bool{}
	for _, table := range allowed {
		allowedSet[strings.ToLower(table)] = true
	}
	bad := []string{}
	for _, match := range tableReferencePattern.FindAllStringSubmatch(sql, -1) {
		table := strings.ToLower(match[1] + "." + match[2])
		if !allowedSet[table] {
			bad = append(bad, table)
		}
	}
	return unique(bad)
}

func compareEvidence(expected map[string]any, actual map[string]any, path string) []string {
	mismatches := []string{}
	for key, expectedValue := range expected {
		actualValue, ok := actual[key]
		if !ok {
			mismatches = append(mismatches, path+"."+key+" missing")
			continue
		}
		mismatches = append(mismatches, compareValue(expectedValue, actualValue, path+"."+key)...)
	}
	return mismatches
}

func compareValue(expected, actual any, path string) []string {
	if expectedRows, ok := asRows(expected); ok {
		actualRows, ok := asRows(actual)
		if !ok {
			return []string{fmt.Sprintf("%s expected rows, got %T", path, actual)}
		}
		if len(expectedRows) != len(actualRows) {
			return []string{fmt.Sprintf("%s row count expected=%d actual=%d; unexpected=%v", path, len(expectedRows), len(actualRows), unexpectedRowKeys(expectedRows, actualRows))}
		}
		expectedCanonical := canonicalRows(expectedRows)
		actualCanonical := canonicalRows(actualRows)
		for index := range expectedCanonical {
			if mismatch := compareEvidence(expectedCanonical[index], actualCanonical[index], fmt.Sprintf("%s[%d]", path, index)); len(mismatch) > 0 {
				return mismatch
			}
		}
		return nil
	}
	if expectedMap, ok := expected.(map[string]any); ok {
		actualMap, ok := actual.(map[string]any)
		if !ok {
			return []string{fmt.Sprintf("%s expected object, got %T", path, actual)}
		}
		return compareEvidence(expectedMap, actualMap, path)
	}
	expectedNumber, expectedNumeric := numeric(expected)
	actualNumber, actualNumeric := numeric(actual)
	if expectedNumeric && actualNumeric {
		if math.Abs(expectedNumber-actualNumber) > 0.00011 {
			return []string{fmt.Sprintf("%s expected=%v actual=%v", path, expected, actual)}
		}
		return nil
	}
	if text(expected) != text(actual) {
		return []string{fmt.Sprintf("%s expected=%v actual=%v", path, expected, actual)}
	}
	return nil
}

func asRows(value any) ([]map[string]any, bool) {
	switch typed := value.(type) {
	case []map[string]any:
		return typed, true
	case []any:
		rows := make([]map[string]any, 0, len(typed))
		for _, item := range typed {
			row, ok := item.(map[string]any)
			if !ok {
				return nil, false
			}
			rows = append(rows, row)
		}
		return rows, true
	default:
		return nil, false
	}
}

func canonicalRows(rows []map[string]any) []map[string]any {
	copyRows := append([]map[string]any{}, rows...)
	sort.SliceStable(copyRows, func(i, j int) bool { return canonicalKey(copyRows[i]) < canonicalKey(copyRows[j]) })
	return copyRows
}

func canonicalKey(row map[string]any) string {
	keys := make([]string, 0, len(row))
	for key := range row {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	var output strings.Builder
	for _, key := range keys {
		output.WriteString(key)
		output.WriteByte('=')
		output.WriteString(text(row[key]))
		output.WriteByte('|')
	}
	return output.String()
}

func unexpectedRowKeys(expected, actual []map[string]any) []string {
	expectedKeys := map[string]bool{}
	for _, row := range expected {
		expectedKeys[rowIdentity(row)] = true
	}
	unexpected := []string{}
	for _, row := range actual {
		key := rowIdentity(row)
		if !expectedKeys[key] {
			unexpected = append(unexpected, key)
		}
	}
	sort.Strings(unexpected)
	return unexpected
}

func rowIdentity(row map[string]any) string {
	parts := []string{}
	for _, key := range []string{"dimension", "segment", "metric", "device_type", "os", "group_size", "all_docs_complete", "drop_step", "channel", "hours_since_drop", "stage", "date"} {
		if value, ok := row[key]; ok {
			parts = append(parts, key+"="+text(value))
		}
	}
	if len(parts) == 0 {
		return canonicalKey(row)
	}
	return strings.Join(parts, ",")
}

func missingRequiredEvidence(required []string, evidence map[string]any) []string {
	missing := []string{}
	for _, key := range required {
		value, ok := evidence[key]
		if !ok || value == nil || text(value) == "" {
			missing = append(missing, key)
		}
	}
	return missing
}

func eventBounds(profile domain.EventProfile) (string, string) {
	if len(profile.EventOrder) == 0 {
		return "", ""
	}
	return profile.EventOrder[0], profile.EventOrder[len(profile.EventOrder)-1]
}
func analysisGrain(profile domain.EventProfile) string {
	for _, value := range []string{"application_id", "user_id", "id"} {
		if hasField(profile, value) {
			return value
		}
	}
	return "id"
}
func hasField(profile domain.EventProfile, wanted string) bool {
	for _, field := range profile.Fields {
		if field.ColumnName == wanted {
			return true
		}
	}
	return false
}
func eventContaining(profile domain.EventProfile, token string) string {
	for _, value := range profile.EventOrder {
		if strings.Contains(strings.ToLower(value), token) {
			return value
		}
	}
	return ""
}
func fieldContaining(profile domain.EventProfile, token string) string {
	for _, value := range profile.Fields {
		if strings.Contains(strings.ToLower(value.ColumnName), token) {
			return value.ColumnName
		}
	}
	return ""
}
func event(row snapshotRow) string {
	if value := text(row["event"]); value != "" {
		return value
	}
	return text(row["event_name"])
}
func distinctWhere(rows []snapshotRow, field string, predicate func(snapshotRow) bool) int {
	values := map[string]bool{}
	for _, row := range rows {
		if predicate(row) && text(row[field]) != "" {
			values[text(row[field])] = true
		}
	}
	return len(values)
}
func divide(numerator, denominator float64) float64 {
	if denominator == 0 {
		return 0
	}
	return round(numerator/denominator, 4)
}
func rawDivide(numerator, denominator float64) float64 {
	if denominator == 0 {
		return 0
	}
	return numerator / denominator
}
func round(value float64, digits int) float64 {
	scale := math.Pow10(digits)
	return math.Round(value*scale) / scale
}
func quantileExact(values []float64, q float64) float64 {
	if len(values) == 0 {
		return 0
	}
	// ClickHouse quantileExact selects the upper middle element for an even
	// cohort (index floor(level*n)), unlike the nearest-rank convention.
	index := int(math.Floor(q * float64(len(values))))
	if index < 0 {
		index = 0
	}
	if index >= len(values) {
		index = len(values) - 1
	}
	return values[index]
}
func nullableText(value any) string {
	result := text(value)
	if result == "" || result == "<nil>" {
		return "unknown"
	}
	return result
}
func text(value any) string {
	if value == nil {
		return ""
	}
	switch typed := value.(type) {
	case string:
		return typed
	case json.Number:
		return typed.String()
	default:
		return fmt.Sprint(value)
	}
}
func number(value any) float64 {
	parsed, ok := numeric(value)
	if !ok {
		return math.NaN()
	}
	return parsed
}
func numeric(value any) (float64, bool) {
	switch typed := value.(type) {
	case float64:
		return typed, true
	case float32:
		return float64(typed), true
	case int:
		return float64(typed), true
	case int64:
		return float64(typed), true
	case json.Number:
		parsed, err := typed.Float64()
		return parsed, err == nil
	case bool:
		if typed {
			return 1, true
		}
		return 0, true
	case string:
		parsed, err := strconv.ParseFloat(typed, 64)
		return parsed, err == nil
	default:
		return 0, false
	}
}
func parseDimension(value string) any {
	parsed, err := strconv.ParseFloat(value, 64)
	if err == nil {
		return parsed
	}
	return value
}
func firstRow(rows []map[string]any) map[string]any {
	if len(rows) == 0 {
		return map[string]any{}
	}
	return rows[0]
}
func firstMetric(rows []map[string]any, metric string) map[string]any {
	for _, row := range rows {
		if text(row["metric"]) == metric {
			return row
		}
	}
	return firstRow(rows)
}
func extreme(rows []map[string]any, metric string, highest bool) map[string]any {
	if len(rows) == 0 {
		return map[string]any{}
	}
	result := rows[0]
	for _, row := range rows[1:] {
		if (highest && number(row[metric]) > number(result[metric])) || (!highest && number(row[metric]) < number(result[metric])) {
			result = row
		}
	}
	return result
}
func sortByMetric(rows []map[string]any, metric string, descending bool, tie string) {
	sort.SliceStable(rows, func(i, j int) bool {
		if number(rows[i][metric]) == number(rows[j][metric]) {
			return number(rows[i][tie]) > number(rows[j][tie])
		}
		if descending {
			return number(rows[i][metric]) > number(rows[j][metric])
		}
		return number(rows[i][metric]) < number(rows[j][metric])
	})
}
func contains(values []string, wanted string) bool {
	for _, value := range values {
		if strings.EqualFold(value, wanted) {
			return true
		}
	}
	return false
}
func unique(values []string) []string {
	seen := map[string]bool{}
	output := []string{}
	for _, value := range values {
		if !seen[value] {
			seen[value] = true
			output = append(output, value)
		}
	}
	return output
}
func governedDimensions(profile domain.EventProfile) []string {
	catalog := []string{"device_type", "os", "app_version", "geoip_country_code", "city", "destination", "channel", "saved_method_type", "group_size", "from_currency", "to_currency", "source_currency", "target_currency", "currency"}
	output := []string{}
	for _, value := range catalog {
		if hasField(profile, value) {
			output = append(output, value)
		}
	}
	return output
}
func requestedDimensions(run domain.FeatureRun, question string) []string {
	lower := " " + strings.ToLower(question) + " "
	aliases := map[string][]string{
		"device_type": {"device", "devices", "mobile", "platform"}, "os": {"os", "operating system", "platform"},
		"geoip_country_code": {"geo", "geography", "country", "countries", "geoip"}, "city": {"city", "cities", "geo city"},
		"destination":   {"destination", "destinations", "travel destination"},
		"from_currency": {"from currency", "source currency", "currency pair", "currency pairs", "currencies"},
		"to_currency":   {"to currency", "target currency", "currency pair", "currency pairs", "currencies"},
	}
	output := []string{}
	for _, field := range governedDimensions(*run.Profile) {
		for _, alias := range aliases[field] {
			if strings.Contains(lower, " "+alias+" ") || strings.Contains(lower, " "+alias+"?") || strings.Contains(lower, " "+alias+",") {
				output = append(output, field)
				break
			}
		}
	}
	return output
}
func runQuestion(run domain.FeatureRun, intent string) string {
	for _, answer := range run.QuestionAnswers {
		if answer.Contract.Intent == intent {
			return answer.Contract.Question
		}
	}
	return ""
}
func timestamp(row snapshotRow) (time.Time, bool) {
	value := text(row["timestamp"])
	for _, layout := range []string{"2006-01-02 15:04:05.000", "2006-01-02 15:04:05", time.RFC3339Nano} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, true
		}
	}
	return time.Time{}, false
}
func periodStart(value time.Time, granularity string) string {
	if granularity == "month" {
		return time.Date(value.Year(), value.Month(), 1, 0, 0, 0, 0, value.Location()).Format("2006-01-02")
	}
	weekday := (int(value.Weekday()) + 6) % 7
	return value.AddDate(0, 0, -weekday).Format("2006-01-02")
}
