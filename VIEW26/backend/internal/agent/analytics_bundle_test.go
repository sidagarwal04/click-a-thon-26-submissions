package agent

import (
	"context"
	"strings"
	"testing"

	"github.com/view26/featurelens/internal/domain"
)

type bundleTestReader struct{}

func (bundleTestReader) Enabled() bool          { return true }
func (bundleTestReader) SourceDatabase() string { return "atlys" }
func (bundleTestReader) QueryJSON(_ context.Context, query string) ([]map[string]any, error) {
	switch {
	case strings.Contains(query, "AS step"):
		return []map[string]any{
			{"step": 1.0, "stage": "feature_shown", "entities": 100.0},
			{"step": 2.0, "stage": "feature_completed", "entities": 62.0},
		}, nil
	case strings.Contains(query, "toStartOfWeek"):
		return []map[string]any{
			{"granularity": "week", "date": "2026-06-29", "entrants": 50.0, "completions": 28.0, "completion_rate": .56},
			{"granularity": "week", "date": "2026-07-06", "entrants": 50.0, "completions": 34.0, "completion_rate": .68},
		}, nil
	case strings.Contains(query, "AS dimension"):
		return []map[string]any{
			{"dimension": "device_type", "segment": "ios", "entrants": 40.0, "completions": 30.0, "completion_rate": .75},
			{"dimension": "device_type", "segment": "android", "entrants": 60.0, "completions": 32.0, "completion_rate": .5333},
		}, nil
	default:
		return nil, nil
	}
}

func TestBuildFeatureBundlePublishesKPIsChartsAndRankedActions(t *testing.T) {
	analytics := AnalyticsAgent{Reader: bundleTestReader{}}
	profile := domain.EventProfile{
		Rows: 200, EventOrder: []string{"feature_shown", "feature_completed"},
		EventCounts: map[string]int{"feature_shown": 100, "feature_completed": 62},
		Fields:      []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "device_type"}},
	}
	answers := []domain.QuestionResponse{
		{
			Contract: domain.AnalysisContract{Intent: "latency_performance", Playbook: "playbook:latency-performance:v1"},
			Insight:  domain.Insight{Headline: "Latency is measurable", Summary: "P95 is available.", RecommendedAction: "Watch the tail.", Confidence: .92, TraceID: "trace-bundle", Evidence: map[string]any{"p95_latency_ms": 2400.0, "payments": 62.0}},
		},
		{
			Contract: domain.AnalysisContract{Intent: "conversion_comparison", Playbook: "playbook:conversion-comparison:v1"},
			Insight:  domain.Insight{Headline: "Conversion is above standard", Summary: "The aligned cohort is higher.", RecommendedAction: "Validate with an experiment.", Confidence: .88, TraceID: "trace-bundle", Evidence: map[string]any{"percentage_point_lift": .08, "feature_entrants": 100.0}},
		},
	}
	bundle := analytics.BuildFeatureBundle(context.Background(), "product_manager", domain.FeatureInput{Name: "Feature"}, profile, domain.SchemaProposal{Database: "featurelens", Table: "feature_events_v1", Version: 1}, domain.ContextVersion{Version: 3}, answers, "trace-bundle")

	if bundle.Status != "ready" || len(bundle.Charts) != 3 || len(bundle.KPIs) != 6 {
		t.Fatalf("unexpected bundle shape: status=%s charts=%d kpis=%d", bundle.Status, len(bundle.Charts), len(bundle.KPIs))
	}
	if len(bundle.Insights) != 2 || bundle.Insights[0].Intent != "conversion_comparison" {
		t.Fatalf("product-manager ranking did not prioritize conversion: %#v", bundle.Insights)
	}
	if bundle.KPIs[2].Key != "completion_rate" || bundle.KPIs[2].FormattedValue != "62.0%" {
		t.Fatalf("completion KPI is not grounded in the funnel: %#v", bundle.KPIs)
	}
	if bundle.KPIs[0].Key != "p95_latency" || bundle.KPIs[1].Key != "lift_vs_standard" || bundle.KPIs[3].Key != "largest_funnel_loss" {
		t.Fatalf("decision KPIs are not ordered from the declared playbooks and opportunity evidence: %#v", bundle.KPIs)
	}
	if bundle.KPIs[0].Label != "Slowest 5% time to pay" {
		t.Fatalf("latency KPI is not phrased as a product outcome: %#v", bundle.KPIs[0])
	}
	if bundle.KPIs[3].Label != "Largest drop-off · feature shown → feature completed" || bundle.KPIs[3].FormattedValue != "38.0%" {
		t.Fatalf("funnel loss KPI does not identify a positive, explicit transition: %#v", bundle.KPIs[3])
	}
	for _, evidence := range bundle.Evidence {
		if evidence.Status != "completed" || evidence.SQL == "" {
			t.Fatalf("bundle query lost provenance: %#v", evidence)
		}
	}
}

func TestDecisionKPILabelsDeduplicateSegmentsAndKeepDenominators(t *testing.T) {
	results := map[string][]map[string]any{
		"funnel": {
			{"stage": "feature_shown", "entities": 100.0},
			{"stage": "feature_completed", "entities": 50.0},
		},
	}
	answers := []domain.QuestionResponse{
		{
			Contract: domain.AnalysisContract{Intent: "platform_failure", Playbook: "playbook:platform-failure:v1"},
			Insight: domain.Insight{Confidence: .96, Evidence: map[string]any{"worst_segment": map[string]any{
				"device_type": "ios", "os": "iOS", "otp_success_rate": .836, "otp_entries": 412.0,
			}}},
		},
		{
			Contract: domain.AnalysisContract{Intent: "recovery_channel", Playbook: "playbook:recovery-channel:v1"},
			Insight: domain.Insight{Confidence: .9, Evidence: map[string]any{"best_channel": map[string]any{
				"channel": "push", "recovery_rate": .047, "reminders": 780.0,
			}}},
		},
	}
	kpis := buildBundleKPIs(results, answers, "dashboard:feature:v1", "trace-kpi")
	if kpis[0].Label != "Weakest OTP cohort · ios" || kpis[0].SampleSize != 412 {
		t.Fatalf("OTP KPI duplicated its platform or lost its denominator: %#v", kpis[0])
	}
	if kpis[1].Label != "Best recovery channel · push" || kpis[1].SampleSize != 780 {
		t.Fatalf("recovery KPI lost its business label or denominator: %#v", kpis[1])
	}
}

func TestDashboardPlanUsesFeatureSemanticGrainAndStages(t *testing.T) {
	sharingProfile := domain.EventProfile{
		EventOrder: []string{"share_clicked", "channel_selected", "link_generated", "link_opened", "recipient_cta_clicked"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "share_id"}, {ColumnName: "channel"}},
	}
	sharing := dashboardPlanFor(domain.FeatureInput{Name: "Status Sharing"}, sharingProfile)
	if sharing.Grain != "share_id" || strings.Join(sharing.Stages, ",") != "link_generated,link_opened,recipient_cta_clicked" {
		t.Fatalf("status sharing mixed creator and recipient grains: %#v", sharing)
	}

	groupProfile := domain.EventProfile{
		EventOrder: []string{"group_started", "traveller_added", "traveller_removed", "group_submitted"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "group_id"}},
	}
	group := dashboardPlanFor(domain.FeatureInput{Name: "Group / Family"}, groupProfile)
	if group.Grain != "group_id" || strings.Contains(strings.Join(group.Stages, ","), "traveller_removed") {
		t.Fatalf("group dashboard treated an optional event as a funnel stage: %#v", group)
	}
	segmentSQL := featureSegmentsSQL(sharingProfile, sharing, domain.SchemaProposal{Database: "featurelens", Table: "sharing_events_v2"})
	if !strings.Contains(segmentSQL, "GROUP BY entity_id") || !strings.Contains(segmentSQL, "WHERE entered = 1") || !strings.Contains(segmentSQL, "HAVING entrants >= 20") {
		t.Fatalf("segment plan did not carry entrant dimensions at the semantic grain: %s", segmentSQL)
	}
	if strings.Contains(segmentSQL, "LIMIT 5 BY dimension") {
		t.Fatalf("segment plan cannot truncate cohorts before selecting the true weakest segment: %s", segmentSQL)
	}
}

func TestGenericDashboardExcludesFailureBranchesFromCompletion(t *testing.T) {
	profile := domain.EventProfile{
		EventOrder: []string{"field_shown", "coupon_entered", "coupon_applied", "checkout_completed", "coupon_rejected"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}},
	}
	plan := dashboardPlanFor(domain.FeatureInput{Name: "Unseen promotion"}, profile)
	if strings.Join(plan.Stages, ",") != "field_shown,coupon_entered,coupon_applied,checkout_completed" {
		t.Fatalf("failure branch became the generic completion stage: %#v", plan)
	}
}

func TestDestinationSegmentsUseFeatureSemanticPlanOutsideGroupFeature(t *testing.T) {
	profile := domain.EventProfile{
		EventOrder: []string{"link_generated", "recipient_cta_clicked"},
		Fields: []domain.FieldProfile{
			{ColumnName: "share_id"}, {ColumnName: "device_type"}, {ColumnName: "geoip_country_code"}, {ColumnName: "destination"},
		},
	}
	plan := buildAnalysisPlan("Where are we losing conversions by device, geo, and destination?", domain.FeatureInput{Name: "Status Sharing", Slug: "status_sharing"}, profile, domain.SchemaProposal{Database: "featurelens_poc", Table: "status_sharing_events_v2"}, "atlys")
	if plan.Intent != "segment_comparison" || plan.Grain != "share_id" || !strings.Contains(plan.SQL, "recipient_cta_clicked") || strings.Contains(plan.SQL, "groups_submitted") {
		t.Fatalf("portfolio segment prompt escaped the feature semantic funnel: %#v", plan)
	}
}

func TestNullableCohortComparisonUsesTheQuestionMarker(t *testing.T) {
	profile := domain.EventProfile{
		EventOrder: []string{"field_shown", "offer_entered", "checkout_completed", "offer_rejected"},
		Fields: []domain.FieldProfile{
			{ColumnName: "application_id"}, {ColumnName: "offer_code", Nullable: true},
		},
	}
	plan := buildAnalysisPlan("Do offer users convert versus rows where `offer_code` is null?", domain.FeatureInput{Name: "Unseen offer"}, profile, domain.SchemaProposal{Database: "featurelens_poc", Table: "unseen_offer_events_v1"}, "atlys")
	if plan.ID != "playbook:nullable-cohort-conversion:v1" || plan.Grain != "application_id" || !strings.Contains(plan.SQL, "offer_code") || !strings.Contains(plan.SQL, "checkout_completed") || strings.Contains(plan.SQL, "purchase_completed") {
		t.Fatalf("nullable cohort question did not compile to an in-table treatment comparison: %#v", plan)
	}
}

func TestDecisionInboxPlansUseFeatureSemanticsAndAbstainWhenEvidenceIsMissing(t *testing.T) {
	schema := domain.SchemaProposal{Database: "featurelens_poc", Table: "events_v2"}
	sharingProfile := domain.EventProfile{
		EventOrder: []string{"share_clicked", "channel_selected", "link_generated", "link_opened", "recipient_cta_clicked"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "share_id"}},
	}
	sharing := buildAnalysisPlan("Who shares and who engages?", domain.FeatureInput{Name: "Status Sharing", Slug: "status_sharing"}, sharingProfile, schema, "atlys")
	if sharing.Intent != "feature_completion" || sharing.Grain != "share_id" || !strings.Contains(sharing.SQL, "event_name = 'link_generated'") || !strings.Contains(sharing.SQL, "event_name = 'recipient_cta_clicked'") || strings.Contains(sharing.SQL, "event_name = 'share_clicked'") {
		t.Fatalf("status-sharing claim is not bound to the recipient-capable share funnel: %#v", sharing)
	}
	support := buildAnalysisPlan("Does sharing reduce support demand?", domain.FeatureInput{Name: "Status Sharing", Slug: "status_sharing"}, sharingProfile, schema, "atlys")
	if support.Intent != "support_demand_impact" || support.Answerability != "not_answerable" || support.SQL != "" {
		t.Fatalf("unsupported support-impact claim did not fail closed: %#v", support)
	}

	groupProfile := domain.EventProfile{
		EventOrder: []string{"group_started", "traveller_added", "group_submitted"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "group_id"}, {ColumnName: "group_size"}},
	}
	group := buildAnalysisPlan("Which group sizes complete best?", domain.FeatureInput{Name: "Group / Family"}, groupProfile, schema, "atlys")
	if group.Intent != "group_size_completion" || group.Grain != "group_id" || !strings.Contains(group.SQL, "GROUP BY group_size") || !strings.Contains(group.SQL, "groups_started") {
		t.Fatalf("group-size claim is not a group-grain cohort comparison: %#v", group)
	}

	recovery := buildAnalysisPlan("How much revenue is recovered?", domain.FeatureInput{Name: "Abandoned Checkout Recovery", Slug: "abandoned_checkout_recovery"}, domain.EventProfile{EventOrder: []string{"abandonment_detected", "reconverted"}, Fields: []domain.FieldProfile{{ColumnName: "application_id"}}}, schema, "atlys")
	if recovery.Intent != "recovery_revenue" || recovery.Answerability != "not_answerable" || recovery.SQL != "" {
		t.Fatalf("revenue claim was emitted without a revenue field: %#v", recovery)
	}

	forexProfile := domain.EventProfile{
		EventOrder: []string{"forex_offer_shown", "currency_selected", "forex_purchased"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "from_currency"}, {ColumnName: "to_currency"}, {ColumnName: "device_type"}},
	}
	forex := buildAnalysisPlan("Which currency pairs have the strongest adoption?", domain.FeatureInput{Name: "Instant Forex"}, forexProfile, schema, "atlys")
	if forex.Intent != "feature_adoption" || strings.Join(forex.Dimensions, ",") != "from_currency,to_currency" || !strings.Contains(forex.SQL, "'currency_pair' AS dimension") || strings.Contains(forex.SQL, "'device_type' AS dimension") {
		t.Fatalf("currency-pair question was answered with unrelated segments: %#v", forex)
	}
}

func TestDecisionInboxExcludesNotAnswerableClaims(t *testing.T) {
	answers := []domain.QuestionResponse{
		{Contract: domain.AnalysisContract{Intent: "feature_completion", Answerability: "answerable"}, Insight: domain.Insight{Headline: "Grounded", Confidence: .9}},
		{Contract: domain.AnalysisContract{Intent: "support_demand_impact", Answerability: "not_answerable"}, Insight: domain.Insight{Headline: "Unsupported", Confidence: .99}},
	}
	insights := rankBundleInsights("product_manager", answers)
	if len(insights) != 1 || insights[0].Headline != "Grounded" {
		t.Fatalf("Decision Inbox included an unsupported claim: %#v", insights)
	}
}

func TestConversationalFollowUpsCompileToGovernedChartPlans(t *testing.T) {
	profile := domain.EventProfile{
		EventOrder: []string{"feature_shown", "feature_selected", "feature_completed"},
		Fields:     []domain.FieldProfile{{ColumnName: "application_id"}, {ColumnName: "device_type"}, {ColumnName: "os"}, {ColumnName: "city"}},
	}
	input := domain.FeatureInput{Name: "Conversation Feature"}
	schema := domain.SchemaProposal{Database: "featurelens", Table: "conversation_events_v1"}

	trend := buildAnalysisPlan("Show the completion trend over time", input, profile, schema, "atlys")
	if trend.Intent != "completion_trend" || !strings.Contains(trend.SQL, ") AS bounds") || !strings.Contains(trend.SQL, "GROUP BY granularity, date") || !strings.Contains(trend.SQL, "toStartOfWeek") || !strings.Contains(trend.SQL, "toStartOfMonth") {
		t.Fatalf("trend follow-up did not compile to an adaptive governed plan: %#v", trend)
	}
	segments := buildAnalysisPlan("Break it down by device and OS", input, profile, schema, "atlys")
	if segments.Intent != "segment_comparison" || !strings.Contains(segments.SQL, "GROUP BY entity_id") || !strings.Contains(segments.SQL, "WHERE entered = 1") {
		t.Fatalf("segment follow-up lost entrant-grain propagation: %#v", segments)
	}
	cities := buildAnalysisPlan("Which cities have the highest completion rate?", input, profile, schema, "atlys")
	if cities.Intent != "segment_comparison" || strings.Join(cities.RequestedDimensions, ",") != "city" || strings.Join(cities.Dimensions, ",") != "city" || !strings.Contains(cities.SQL, "'city' AS dimension") || strings.Contains(cities.SQL, "'device_type' AS dimension") {
		t.Fatalf("city ranking did not compile to a dimension-specific plan: %#v", cities)
	}
	deviceAndOS := buildAnalysisPlan("Break it down by device and OS", input, profile, schema, "atlys")
	if strings.Join(deviceAndOS.RequestedDimensions, ",") != "device_type,os" || !strings.Contains(deviceAndOS.SQL, "'device_type' AS dimension") || !strings.Contains(deviceAndOS.SQL, "'os' AS dimension") {
		t.Fatalf("multi-dimension request lost one of its governed cuts: %#v", deviceAndOS)
	}
	funnel := buildAnalysisPlan("Where is the largest funnel drop?", input, profile, schema, "atlys")
	if funnel.Intent != "funnel_diagnosis" || !strings.Contains(funnel.SQL, "AS step") {
		t.Fatalf("funnel follow-up did not compile to governed stage counts: %#v", funnel)
	}
}
