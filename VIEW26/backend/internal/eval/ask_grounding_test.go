package eval

import (
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

func TestAskGroundingOracleUsesDistinctEntityGrain(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	if oracle.Evidence["entrants"] != float64(3) || oracle.Evidence["completions"] != float64(2) || oracle.Evidence["completion_rate"] != .6667 {
		t.Fatalf("oracle counted event rows instead of distinct applications: %#v", oracle.Evidence)
	}

	answer := groundedAnswer(run, oracle)
	report := ValidateAskGrounding(run, answer, oracle)
	if !report.Passed {
		t.Fatalf("truthful answer did not pass: %#v", report.Checks)
	}
}

func TestStatusSharingOracleUsesShareGrainAndRecipientCapableStages(t *testing.T) {
	ndjson := `{"id":"1","application_id":"a1","share_id":"s1","event":"share_clicked","timestamp":"2026-01-01 10:00:00.000"}
{"id":"2","application_id":"a2","share_id":"s2","event":"share_clicked","timestamp":"2026-01-01 10:00:01.000"}
{"id":"3","application_id":"a1","share_id":"s1","event":"link_generated","timestamp":"2026-01-01 10:00:02.000"}
{"id":"4","application_id":"a2","share_id":"s2","event":"link_generated","timestamp":"2026-01-01 10:00:03.000"}
{"id":"5","share_id":"s1","event":"link_opened","timestamp":"2026-01-01 10:01:00.000"}
{"id":"6","share_id":"s1","event":"recipient_cta_clicked","timestamp":"2026-01-01 10:02:00.000"}`
	profile := domain.EventProfile{
		Rows: 6, EventOrder: []string{"share_clicked", "link_generated", "link_opened", "recipient_cta_clicked"},
		Fields: []domain.FieldProfile{{ColumnName: "id"}, {ColumnName: "application_id"}, {ColumnName: "share_id"}, {ColumnName: "timestamp"}},
	}
	schema := domain.SchemaProposal{Version: 2, Database: "featurelens_poc", Table: "status_sharing_events_v2"}
	run := domain.FeatureRun{Input: domain.FeatureInput{Name: "Status Sharing", EventsNDJSON: ndjson, UseExistingData: true}, Profile: &profile, Schema: &schema}
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	if oracle.Evidence["entrants"] != float64(2) || oracle.Evidence["completions"] != float64(1) || oracle.Evidence["completion_rate"] != .5 {
		t.Fatalf("recipient rows with null application_id were lost: %#v", oracle.Evidence)
	}
}

func TestAskGroundingDetectsCorruptedEvidence(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	answer := groundedAnswer(run, oracle)
	answer.Insight.Evidence["completion_rate"] = .75

	report := ValidateAskGrounding(run, answer, oracle)
	if report.Passed || checkPassed(report.Checks, "table_truth") {
		t.Fatalf("a fabricated completion rate passed grounding: %#v", report.Checks)
	}
}

func TestAskGroundingDetectsUnauthorizedTableAndBrokenTrace(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	answer := groundedAnswer(run, oracle)
	answer.Insight.SQL = "SELECT count() FROM `shadow`.`customers` FORMAT JSONEachRow"

	report := ValidateAskGrounding(run, answer, oracle)
	if report.Passed || checkPassed(report.Checks, "sql_allowlist") || checkPassed(report.Checks, "query_trace") {
		t.Fatalf("unauthorized SQL or trace mismatch passed: %#v", report.Checks)
	}
}

func TestAskGroundingRejectsCorrectOverallMetricForSegmentQuestion(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	answer := groundedAnswer(run, oracle)
	answer.Contract.Question = "Which device type drives the most completion?"
	answer.Contract.Dimensions = []string{"device_type"}

	report := ValidateAskGrounding(run, answer, oracle)
	if report.Passed || checkPassed(report.Checks, "question_dimension_coverage") {
		t.Fatalf("an overall metric was accepted as a device answer: %#v", report.Checks)
	}
}

func TestAskGroundingRequiresEveryExplicitPlatformCut(t *testing.T) {
	run := completionFixture()
	run.Profile.Fields = append(run.Profile.Fields,
		domain.FieldProfile{ColumnName: "os"},
		domain.FieldProfile{ColumnName: "geoip_country_code"},
	)
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	answer := groundedAnswer(run, oracle)
	answer.Contract.Question = "Cut failure by device type, OS, and GeoIP country"
	answer.Contract.Dimensions = []string{"device_type", "os"}
	answer.Insight.Evidence["segments"] = []map[string]any{{"device_type": "ios", "os": "iOS"}}

	report := ValidateAskGrounding(run, answer, oracle)
	if report.Passed || checkPassed(report.Checks, "question_dimension_coverage") {
		t.Fatalf("missing GeoIP cut was accepted: %#v", report.Checks)
	}
}

func TestAskGroundingRejectsPercentageNotPresentInEvidence(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	answer := groundedAnswer(run, oracle)
	answer.Insight.Headline = "Completion improved to 99.9%"

	report := ValidateAskGrounding(run, answer, oracle)
	if report.Passed || checkPassed(report.Checks, "prose_percentage_grounding") {
		t.Fatalf("fabricated prose percentage passed: %#v", report.Checks)
	}
}

func TestAskGroundingAllowsExplicitAnswerConfidencePercentage(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	answer := groundedAnswer(run, oracle)
	answer.Insight.Confidence = .96
	answer.Insight.Why = "Confidence is 96% because the aggregate is complete."

	report := ValidateAskGrounding(run, answer, oracle)
	if !checkPassed(report.Checks, "prose_percentage_grounding") {
		t.Fatalf("explicit confidence was treated as a fabricated metric: %#v", report.Checks)
	}
}

func TestAskGroundingRequiresRankedEvidenceAnchorInAnswer(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "feature_completion")
	if err != nil {
		t.Fatal(err)
	}
	oracle.Evidence["best_segment"] = map[string]any{"dimension": "device_type", "segment": "ios", "completion_rate": .7}
	oracle.VerifiedKeys = append(oracle.VerifiedKeys, "best_segment")
	answer := groundedAnswer(run, oracle)
	answer.Insight.Headline = "Android leads completion"
	answer.Insight.Summary = "The strongest cohort is on Android."

	report := ValidateAskGrounding(run, answer, oracle)
	if report.Passed || checkPassed(report.Checks, "answer_anchor") {
		t.Fatalf("answer ignored its own ranked evidence: %#v", report.Checks)
	}
}

func TestSegmentOracleAttributesDimensionAtEntrantEvent(t *testing.T) {
	run := completionFixture()
	run.QuestionAnswers = []domain.QuestionResponse{{Contract: domain.AnalysisContract{Intent: "segment_comparison", Question: "Compare completion by device"}}}
	oracle, err := BuildAskOracle(run, "segment_comparison")
	if err != nil {
		t.Fatal(err)
	}
	segments, ok := oracle.Evidence["segments"].([]map[string]any)
	if !ok || len(segments) != 0 {
		// The production contract deliberately suppresses cohorts below 20.
		t.Fatalf("small-cohort guardrail was not applied: %#v", oracle.Evidence)
	}

	// Replicate the fixture to cross the cohort threshold and make the first
	// event carry a different device than a later event. Attribution must stay
	// pinned to the entrant event.
	run = repeatedSegmentFixture()
	oracle, err = BuildAskOracle(run, "segment_comparison")
	if err != nil {
		t.Fatal(err)
	}
	segments = oracle.Evidence["segments"].([]map[string]any)
	ios := findSegment(segments, "device_type", "ios")
	android := findSegment(segments, "device_type", "android")
	if ios == nil || ios["entrants"] != float64(20) || ios["completions"] != float64(10) || android != nil {
		t.Fatalf("dimension was not attributed at entrant grain: %#v", segments)
	}
}

func TestFailClosedValidationRequiresNoQuery(t *testing.T) {
	answer := domain.QuestionResponse{
		Contract: domain.AnalysisContract{Answerability: "not_answerable"},
		Insight: domain.Insight{
			Evidence: map[string]any{"execution_mode": "not_executed"},
			Trace:    &domain.AnalysisTrace{Steps: []domain.AnalysisTraceStep{{ID: "tool.clickhouse.query", Status: "skipped"}}},
		},
	}
	for _, check := range ValidateFailClosed(answer) {
		if !check.Passed {
			t.Fatalf("valid fail-closed answer failed %s: %s", check.Name, check.Details)
		}
	}
	answer.Insight.SQL = "SELECT * FROM forbidden"
	if checkPassed(ValidateFailClosed(answer), "no_sql") {
		t.Fatal("not-answerable response was allowed to carry SQL")
	}
}

func TestConversionOracleMarksUnseenControlJoinPartial(t *testing.T) {
	run := completionFixture()
	oracle, err := BuildAskOracle(run, "conversion_comparison")
	if err != nil {
		t.Fatal(err)
	}
	if oracle.Completeness != "partial" || len(oracle.Limitations) == 0 {
		t.Fatalf("control-table boundary was hidden: %#v", oracle)
	}
	if _, exists := oracle.Evidence["standard_conversion_rate"]; exists {
		t.Fatal("feature snapshot must not pretend to independently verify the standard-checkout table")
	}
}

func completionFixture() domain.FeatureRun {
	ndjson := `{"id":"1","application_id":"a","event":"shown","timestamp":"2026-01-01 10:00:00.000","device_type":"ios"}
{"id":"2","application_id":"a","event":"shown","timestamp":"2026-01-01 10:01:00.000","device_type":"ios"}
{"id":"3","application_id":"a","event":"confirmed","timestamp":"2026-01-01 10:02:00.000","device_type":"android"}
{"id":"4","application_id":"b","event":"shown","timestamp":"2026-01-01 11:00:00.000","device_type":"ios"}
{"id":"5","application_id":"c","event":"shown","timestamp":"2026-01-01 12:00:00.000","device_type":"android"}
{"id":"6","application_id":"c","event":"confirmed","timestamp":"2026-01-01 12:02:00.000","device_type":"android"}`
	profile := domain.EventProfile{
		Rows: 6, EventOrder: []string{"shown", "confirmed"}, EventCounts: map[string]int{"shown": 4, "confirmed": 2},
		Fields: []domain.FieldProfile{{ColumnName: "id"}, {ColumnName: "application_id"}, {ColumnName: "timestamp"}, {ColumnName: "device_type"}},
	}
	schema := domain.SchemaProposal{Version: 1, Database: "featurelens_poc", Table: "fixture_events_v1"}
	return domain.FeatureRun{Input: domain.FeatureInput{Name: "Fixture", EventsNDJSON: ndjson, UseExistingData: true}, Profile: &profile, Schema: &schema}
}

func repeatedSegmentFixture() domain.FeatureRun {
	run := completionFixture()
	rows := ""
	for index := 0; index < 20; index++ {
		rows += `{"id":"s` + itoa(index) + `","application_id":"a` + itoa(index) + `","event":"shown","timestamp":"2026-01-01 10:00:00.000","device_type":"ios"}` + "\n"
		if index < 10 {
			rows += `{"id":"c` + itoa(index) + `","application_id":"a` + itoa(index) + `","event":"confirmed","timestamp":"2026-01-01 10:01:00.000","device_type":"android"}` + "\n"
		}
	}
	run.Input.EventsNDJSON = rows
	run.Profile.Rows = 30
	run.QuestionAnswers = []domain.QuestionResponse{{Contract: domain.AnalysisContract{Intent: "segment_comparison", Question: "Compare completion by device"}}}
	return run
}

func groundedAnswer(run domain.FeatureRun, oracle OracleResult) domain.QuestionResponse {
	sql := "SELECT uniqExact(application_id) FROM `featurelens_poc`.`fixture_events_v1` FORMAT JSONEachRow"
	evidence := map[string]any{"execution_mode": "clickhouse"}
	for key, value := range oracle.Evidence {
		evidence[key] = value
	}
	return domain.QuestionResponse{
		Contract: domain.AnalysisContract{
			Feature: run.Input.Name, Intent: oracle.Intent, Question: "What is completion?", ContextVersion: 2,
			SchemaVersions: []string{"fixture:v1"}, AllowedTables: []string{"featurelens_poc.fixture_events_v1"}, RequiredEvidence: oracle.VerifiedKeys,
		},
		Insight: domain.Insight{
			Evidence: evidence, SQL: sql, ContextVersion: 2, SchemaVersion: "fixture:v1",
			Trace: &domain.AnalysisTrace{Steps: []domain.AnalysisTraceStep{{ID: "tool.clickhouse.query", Status: "completed", Input: map[string]any{"sql": sql}}}},
		},
	}
}

func checkPassed(checks []GroundingCheck, name string) bool {
	for _, check := range checks {
		if check.Name == name {
			return check.Passed
		}
	}
	return false
}

func findSegment(rows []map[string]any, dimension, segment string) map[string]any {
	for _, row := range rows {
		if row["dimension"] == dimension && row["segment"] == segment {
			return row
		}
	}
	return nil
}

func itoa(value int) string {
	if value < 10 {
		return string(rune('0' + value))
	}
	return string(rune('0'+value/10)) + string(rune('0'+value%10))
}
