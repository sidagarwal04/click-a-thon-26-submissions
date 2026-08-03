package agent

import (
	"fmt"
	"strings"

	"github.com/view26/featurelens/internal/domain"
)

type analysisPlan struct {
	ID                  string
	Intent              string
	Answerability       string
	Grain               string
	Metrics             []string
	Dimensions          []string
	AllowedTables       []string
	RequiredEvidence    []string
	Limitations         []string
	SQL                 string
	RequestedSegment    string
	RequestedDimensions []string
}

func buildAnalysisPlan(question string, input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, sourceDatabase string) analysisPlan {
	return buildAnalysisPlanForIntent(classifyFeatureIntent(input, question), question, input, profile, schema, sourceDatabase)
}

func buildAnalysisPlanForIntent(intent, question string, input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, sourceDatabase string) analysisPlan {
	if strings.HasPrefix(intent, "recovery_") {
		switch intent {
		case "recovery_drop_step":
			return recoveryDropStepPlan(profile, schema)
		case "recovery_channel":
			return recoveryChannelPlan(profile, schema)
		case "recovery_timing":
			return recoveryTimingPlan(profile, schema)
		case "recovery_segments":
			return recoverySegmentsPlan(profile, schema)
		case "recovery_revenue":
			return unsupportedOutcomePlan(profile, schema, intent, "recovery-revenue", "The verified recovery table has no recovered-revenue or transaction-amount field, so revenue cannot be calculated from this feature context.")
		}
	}
	switch intent {
	case "support_demand_impact":
		return unsupportedOutcomePlan(profile, schema, intent, "support-demand-impact", "The verified Status Sharing table has no support-contact event, ticket identifier, or unshared comparison cohort, so support-demand reduction cannot be measured.")
	case "customer_geography":
		return customerGeographyPlan(profile, schema, question)
	case "group_size_completion":
		return groupSizeCompletionPlan(profile, schema)
	case "group_traveller_churn":
		return groupTravellerChurnPlan(profile, schema)
	case "group_document_bottleneck":
		return groupDocumentBottleneckPlan(profile, schema)
	case "group_segments":
		return groupSegmentsPlan(profile, schema)
	case "conversion_comparison":
		return conversionComparisonPlan(question, input, profile, schema, sourceDatabase)
	case "platform_failure":
		return platformFailurePlan(profile, schema)
	case "latency_performance":
		return latencyPlan(profile, schema, question)
	case "feature_adoption":
		return adoptionPlan(profile, schema, question)
	case "completion_trend":
		return completionTrendPlan(input, profile, schema)
	case "segment_comparison":
		return segmentCompletionPlan(input, profile, schema, question)
	case "funnel_diagnosis":
		return funnelDiagnosisPlan(input, profile, schema)
	default:
		return featureCompletionPlan(input, profile, schema, intent)
	}
}

func classifyFeatureIntent(input domain.FeatureInput, question string) string {
	slug := Slug(input.Slug)
	if slug == "" {
		slug = Slug(input.Name)
	}
	if strings.Contains(slug, "status_sharing") && strings.Contains(strings.ToLower(question), "support") {
		return "support_demand_impact"
	}
	if strings.Contains(slug, "abandoned_checkout_recovery") {
		if intent := recoveryIntent(question); intent != "" {
			return intent
		}
	}
	intent := ClassifyIntent(question)
	// The shared classifier recognizes the Group / Family destination prompt,
	// but portfolio questions often ask every feature for destination segments.
	// Keep the group-specific contract scoped to the group feature; every other
	// feature must use its own semantic funnel and the generic segment playbook.
	if intent == "group_segments" && !strings.Contains(slug, "group") && !strings.Contains(slug, "family") {
		return "segment_comparison"
	}
	return intent
}

func recoveryIntent(question string) string {
	lower := strings.ToLower(question)
	switch {
	case strings.Contains(lower, "amount recovered") || strings.Contains(lower, "recovered revenue") || strings.Contains(lower, "revenue recovered") || (strings.Contains(lower, "how much") && strings.Contains(lower, "revenue")):
		return "recovery_revenue"
	case strings.Contains(lower, "drop_step") || strings.Contains(lower, "recoverable"):
		return "recovery_drop_step"
	case strings.Contains(lower, "channel") || strings.Contains(lower, "open → click") || strings.Contains(lower, "open -> click"):
		return "recovery_channel"
	case strings.Contains(lower, "hours_since_drop") || strings.Contains(lower, "timing") || strings.Contains(lower, "1h") || strings.Contains(lower, "24h") || strings.Contains(lower, "48h"):
		return "recovery_timing"
	case strings.Contains(lower, "segment") || strings.Contains(lower, "device") || strings.Contains(lower, "geo") || strings.Contains(lower, "destination"):
		return "recovery_segments"
	default:
		return ""
	}
}

func unsupportedOutcomePlan(profile domain.EventProfile, schema domain.SchemaProposal, intent, playbook, reason string) analysisPlan {
	return analysisPlan{
		ID: "playbook:" + playbook + ":unsupported", Intent: intent, Answerability: "not_answerable", Grain: analysisGrain(profile),
		AllowedTables: []string{schema.Database + "." + schema.Table}, Limitations: []string{reason},
	}
}

func recoveryDropStepPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	if !hasField(profile, "drop_step") || !hasField(profile, "application_id") {
		return unsupportedRecoveryPlan(profile, schema, "recovery_drop_step", "recovery-drop-step", "drop_step or application_id is missing from verified instrumentation.")
	}
	sql := fmt.Sprintf(`SELECT
    drop_step,
    count() AS abandonments,
    sum(reconverted) AS reconversions,
    round(avg(reconverted), 4) AS recovery_rate
FROM
(
    SELECT
        application_id,
        anyIf(ifNull(toString(drop_step), 'unknown'), event_name = 'abandonment_detected') AS drop_step,
        max(event_name = 'reconverted') AS reconverted
    FROM %s
    GROUP BY application_id
)
GROUP BY drop_step
ORDER BY recovery_rate DESC, abandonments DESC
FORMAT JSONEachRow`, qualified(schema.Database, schema.Table))
	return analysisPlan{
		ID: "playbook:recovery-drop-step:v1", Intent: "recovery_drop_step", Answerability: "answerable", Grain: "application_id",
		Metrics: []string{"abandonments", "reconversions", "recovery rate"}, Dimensions: []string{"drop_step"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "most_recoverable_step"},
		Limitations: []string{"Observed reconversion is descriptive and does not estimate incremental lift versus an untreated holdout."}, SQL: sql,
	}
}

func recoveryChannelPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	if !hasField(profile, "channel") || !hasField(profile, "application_id") {
		return unsupportedRecoveryPlan(profile, schema, "recovery_channel", "recovery-channel", "channel or application_id is missing from verified instrumentation.")
	}
	sql := fmt.Sprintf(`SELECT
    channel,
    count() AS reminders,
    sum(opened) AS opens,
    sum(clicked) AS clicks,
    sum(reconverted) AS reconversions,
    round(opens / nullIf(reminders, 0), 4) AS open_rate,
    round(clicks / nullIf(opens, 0), 4) AS click_from_open_rate,
    round(reconversions / nullIf(reminders, 0), 4) AS recovery_rate
FROM
(
    SELECT
        application_id,
        anyIf(ifNull(toString(channel), 'unknown'), event_name = 'reminder_sent') AS channel,
        max(event_name = 'reminder_opened') AS opened,
        max(event_name = 'reminder_cta_clicked') AS clicked,
        max(event_name = 'reconverted') AS reconverted
    FROM %s
    GROUP BY application_id
)
GROUP BY channel
ORDER BY recovery_rate DESC, reminders DESC
FORMAT JSONEachRow`, qualified(schema.Database, schema.Table))
	return analysisPlan{
		ID: "playbook:recovery-channel:v1", Intent: "recovery_channel", Answerability: "answerable", Grain: "application_id",
		Metrics: []string{"open rate", "click-from-open rate", "recovery rate"}, Dimensions: []string{"channel"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "best_channel"},
		Limitations: []string{"Channel comparisons are observational and may reflect targeting differences between push, email, and WhatsApp cohorts."}, SQL: sql,
	}
}

func recoveryTimingPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	if !hasField(profile, "hours_since_drop") || !hasField(profile, "application_id") {
		return unsupportedRecoveryPlan(profile, schema, "recovery_timing", "recovery-timing", "hours_since_drop or application_id is missing from verified instrumentation.")
	}
	sql := fmt.Sprintf(`SELECT
    hours_since_drop,
    count() AS reminders,
    sum(opened) AS opens,
    sum(reconverted) AS reconversions,
    round(opens / nullIf(reminders, 0), 4) AS open_rate,
    round(reconversions / nullIf(reminders, 0), 4) AS recovery_rate
FROM
(
    SELECT
        application_id,
        anyIf(toFloat64(hours_since_drop), event_name = 'reminder_sent') AS hours_since_drop,
        max(event_name = 'reminder_opened') AS opened,
        max(event_name = 'reconverted') AS reconverted
    FROM %s
    GROUP BY application_id
)
GROUP BY hours_since_drop
ORDER BY hours_since_drop
FORMAT JSONEachRow`, qualified(schema.Database, schema.Table))
	return analysisPlan{
		ID: "playbook:recovery-timing:v1", Intent: "recovery_timing", Answerability: "answerable", Grain: "application_id",
		Metrics: []string{"reminders", "open rate", "recovery rate"}, Dimensions: []string{"hours_since_drop"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "best_timing"},
		Limitations: []string{"Timing cohorts are not randomized; urgency and drop-step mix can confound the observed recovery rate."}, SQL: sql,
	}
}

func recoverySegmentsPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	grain := analysisGrain(profile)
	queries := []string{}
	dimensions := []string{}
	for _, dimension := range []string{"device_type", "geoip_country_code", "destination"} {
		if !hasField(profile, dimension) {
			continue
		}
		dimensions = append(dimensions, dimension)
		queries = append(queries, fmt.Sprintf(`SELECT
    '%s' AS dimension,
    ifNull(toString(%s), 'unknown') AS segment,
    uniqExactIf(%s, event_name = 'abandonment_detected') AS abandonments,
    uniqExactIf(%s, event_name = 'reconverted') AS reconversions,
    round(reconversions / nullIf(abandonments, 0), 4) AS recovery_rate
FROM %s
GROUP BY %s`, dimension, identifier(dimension), identifier(grain), identifier(grain), qualified(schema.Database, schema.Table), identifier(dimension)))
	}
	if len(queries) == 0 {
		return unsupportedRecoveryPlan(profile, schema, "recovery_segments", "recovery-segments", "No verified device, GeoIP, or destination dimension is available.")
	}
	return analysisPlan{
		ID: "playbook:recovery-segments:v1", Intent: "recovery_segments", Answerability: "answerable", Grain: grain,
		Metrics: []string{"abandonments", "reconversions", "recovery rate"}, Dimensions: dimensions,
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "largest_recovery_segment"},
		Limitations: []string{"Segment rates describe observed recovery traffic and do not establish that the reminder caused reconversion."},
		SQL:         "SELECT * FROM (\n" + strings.Join(queries, "\nUNION ALL\n") + "\n) ORDER BY reconversions DESC, recovery_rate DESC\nFORMAT JSONEachRow",
	}
}

func unsupportedRecoveryPlan(profile domain.EventProfile, schema domain.SchemaProposal, intent, playbook, limitation string) analysisPlan {
	return analysisPlan{
		ID: "playbook:" + playbook + ":unsupported", Intent: intent, Answerability: "not_answerable", Grain: analysisGrain(profile),
		AllowedTables: []string{schema.Database + "." + schema.Table}, Limitations: []string{limitation},
	}
}

func customerGeographyPlan(profile domain.EventProfile, schema domain.SchemaProposal, question string) analysisPlan {
	segment := requestedOrigin(question)
	if !hasField(profile, "city") || segment == "" {
		return analysisPlan{
			ID:            "playbook:customer-geography:clarification-required:v1",
			Intent:        "customer_geography",
			Answerability: "not_answerable",
			Grain:         analysisGrain(profile),
			Metrics:       []string{"unique customers"},
			Dimensions:    availableDimensions(profile),
			AllowedTables: []string{schema.Database + "." + schema.Table},
			RequiredEvidence: []string{
				"verified customer identifier",
				"verified city-level customer-origin dimension",
			},
			Limitations: []string{
				"The selected feature schema has no verified city field, or the requested city could not be resolved.",
				"destination represents the visa or travel destination, not the customer's residence or current location.",
				"geoip_country_code is country-level and cannot establish a requested city.",
			},
		}
	}
	grain := "user_id"
	answerability := "partially_answerable"
	limitations := []string{
		"The observed city field is interpreted as event geo-city; it does not establish residence or hometown.",
		"The result counts unique users observed in the selected feature dataset, not the entire customer or CRM population.",
		"destination is deliberately excluded because it represents travel intent rather than customer origin.",
	}
	if !hasField(profile, grain) {
		grain = analysisGrain(profile)
		limitations = append(limitations, "A verified user_id is unavailable, so the result uses the feature analysis grain rather than unique customers.")
	}
	sql := fmt.Sprintf(`SELECT
    '%s' AS requested_city,
    uniqExactIf(events.%s, lowerUTF8(toString(events.city)) = lowerUTF8('%s')) AS customers,
    uniqExact(events.%s) AS total_customers,
    round(customers / nullIf(total_customers, 0), 4) AS customer_share
FROM %s AS events
FORMAT JSONEachRow`, escapeSQL(segment), identifier(grain), escapeSQL(segment), identifier(grain), qualified(schema.Database, schema.Table))
	return analysisPlan{
		ID: "playbook:customer-geography:v1", Intent: "customer_geography", Answerability: answerability, Grain: grain,
		Metrics: []string{"unique observed customers", "share of observed customers"}, Dimensions: []string{"city"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"requested_city", "customers", "total_customers", "customer_share"},
		Limitations: limitations, SQL: sql, RequestedSegment: segment,
	}
}

func groupSizeCompletionPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	if !hasField(profile, "group_size") {
		plan := completionPlan(profile, schema, "group_size_completion")
		plan.ID = "playbook:group-size-completion:unsupported"
		plan.Answerability = "not_answerable"
		plan.Limitations = []string{"The verified feature schema has no group_size field."}
		plan.SQL = ""
		return plan
	}
	stages := presentEvents(profile, "group_started", "group_submitted")
	if len(stages) < 2 {
		stages = append([]string{}, profile.EventOrder...)
	}
	first, last := stages[0], stages[len(stages)-1]
	grain := preferredDashboardGrain(profile, "group_id")
	sql := fmt.Sprintf(`SELECT
    group_size,
    count() AS groups_started,
    sum(completed) AS groups_submitted,
    round(groups_submitted / nullIf(groups_started, 0), 4) AS completion_rate
FROM
(
    SELECT
        %s AS entity_id,
        anyIf(toInt64(group_size), event_name = '%s') AS group_size,
        max(event_name = '%s') AS entered,
        max(event_name = '%s') AS completed
    FROM %s
    WHERE %s IS NOT NULL
    GROUP BY entity_id
)
WHERE entered = 1
GROUP BY group_size
HAVING groups_started > 0
ORDER BY group_size
FORMAT JSONEachRow`, identifier(grain), escapeSQL(first), escapeSQL(first), escapeSQL(last), qualified(schema.Database, schema.Table), identifier(grain))
	return analysisPlan{
		ID: "playbook:group-size-completion:v1", Intent: "group_size_completion", Answerability: "answerable", Grain: grain,
		Metrics: []string{"groups started", "groups submitted", "completion rate"}, Dimensions: []string{"group_size"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "lowest_completion_segment"},
		Limitations: []string{"The aggregate is descriptive and does not prove that group size causes abandonment."}, SQL: sql,
	}
}

func groupTravellerChurnPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	if !hasField(profile, "group_id") {
		return unsupportedGroupPlan(profile, schema, "group_traveller_churn", "group-traveller-churn", "The verified feature schema has no group_id field.")
	}
	table := qualified(schema.Database, schema.Table)
	sql := fmt.Sprintf(`SELECT
    uniqExactIf(group_id, event_name = 'group_started') AS groups_started,
    countIf(event_name = 'traveller_added') AS travellers_added,
    countIf(event_name = 'traveller_removed') AS travellers_removed,
    round(travellers_added / nullIf(groups_started, 0), 4) AS additions_per_group,
    round(travellers_removed / nullIf(groups_started, 0), 4) AS removals_per_group,
    round(travellers_removed / nullIf(travellers_added, 0), 4) AS removal_to_addition_rate
FROM %s
FORMAT JSONEachRow`, table)
	return analysisPlan{
		ID: "playbook:group-traveller-churn:v1", Intent: "group_traveller_churn", Answerability: "answerable", Grain: "group_id",
		Metrics: []string{"travellers added", "travellers removed", "additions per group", "removals per group", "removal-to-addition rate"}, Dimensions: []string{"group"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"groups_started", "travellers_added", "travellers_removed", "additions_per_group", "removals_per_group", "removal_to_addition_rate"}, SQL: sql,
	}
}

func groupDocumentBottleneckPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	if !hasField(profile, "group_id") || !hasField(profile, "group_size") || !hasField(profile, "docs_complete") {
		return unsupportedGroupPlan(profile, schema, "group_document_bottleneck", "group-document-bottleneck", "group_id, group_size, or docs_complete is missing from verified instrumentation.")
	}
	sql := fmt.Sprintf(`SELECT
    group_size,
    all_docs_complete,
    count() AS groups,
    sum(submitted) AS submissions,
    round(avg(submitted), 4) AS submission_rate
FROM
(
    SELECT
        group_id,
        any(group_size) AS group_size,
        minIf(toUInt8(ifNull(docs_complete, 0)), event_name = 'traveller_added') AS all_docs_complete,
        max(event_name = 'group_submitted') AS submitted
    FROM %s
    GROUP BY group_id
)
GROUP BY group_size, all_docs_complete
ORDER BY group_size, all_docs_complete DESC
FORMAT JSONEachRow`, qualified(schema.Database, schema.Table))
	return analysisPlan{
		ID: "playbook:group-document-bottleneck:v1", Intent: "group_document_bottleneck", Answerability: "partially_answerable", Grain: "group_id",
		Metrics: []string{"groups", "submissions", "submission rate"}, Dimensions: []string{"group_size", "all_docs_complete"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments"},
		Limitations: []string{"The association is descriptive; document completion may correlate with other sources of group complexity."}, SQL: sql,
	}
}

func groupSegmentsPlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	first, last := funnelBounds(profile)
	grain := analysisGrain(profile)
	queries := []string{}
	for _, dimension := range []string{"destination", "device_type", "geoip_country_code"} {
		if !hasField(profile, dimension) {
			continue
		}
		queries = append(queries, fmt.Sprintf(`SELECT
    '%s' AS dimension,
    toString(%s) AS segment,
    uniqExactIf(%s, event_name = '%s') AS groups_started,
    uniqExactIf(%s, event_name = '%s') AS groups_submitted,
    round(groups_submitted / nullIf(groups_started, 0), 4) AS completion_rate
FROM %s
GROUP BY %s`, dimension, identifier(dimension), identifier(grain), escapeSQL(first), identifier(grain), escapeSQL(last), qualified(schema.Database, schema.Table), identifier(dimension)))
	}
	if len(queries) == 0 {
		return unsupportedGroupPlan(profile, schema, "group_segments", "group-segments", "No verified group segmentation dimension is available.")
	}
	return analysisPlan{
		ID: "playbook:group-segments:v1", Intent: "group_segments", Answerability: "answerable", Grain: grain,
		Metrics: []string{"groups started", "groups submitted", "completion rate"}, Dimensions: []string{"destination", "device_type", "geoip_country_code"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "largest_segment"},
		Limitations: []string{"Segment volume describes observed group starts and should not be interpreted as market demand without exposure denominators."},
		SQL:         "SELECT * FROM (\n" + strings.Join(queries, "\nUNION ALL\n") + "\n) ORDER BY groups_started DESC, completion_rate DESC\nFORMAT JSONEachRow",
	}
}

func unsupportedGroupPlan(profile domain.EventProfile, schema domain.SchemaProposal, intent, playbook, limitation string) analysisPlan {
	return analysisPlan{
		ID: "playbook:" + playbook + ":unsupported", Intent: intent, Answerability: "not_answerable", Grain: analysisGrain(profile),
		AllowedTables: []string{schema.Database + "." + schema.Table}, Limitations: []string{limitation},
	}
}

func requestedOrigin(question string) string {
	lower := strings.ToLower(question)
	index := strings.Index(lower, " from ")
	if index < 0 {
		return ""
	}
	value := strings.TrimSpace(question[index+len(" from "):])
	value = strings.Trim(value, " ?!.,;:\"'")
	return value
}

func conversionComparisonPlan(question string, input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, sourceDatabase string) analysisPlan {
	if cohortField := nullableCohortField(question, profile); cohortField != "" {
		return nullableCohortComparisonPlan(input, profile, schema, cohortField)
	}
	dashboard := dashboardPlanFor(input, profile)
	first, last := dashboard.Stages[0], dashboard.Stages[len(dashboard.Stages)-1]
	grain := analysisGrain(profile)
	featureTable := qualified(schema.Database, schema.Table)
	payTable := qualified(sourceDatabase, "pay_now_clicked")
	purchaseTable := qualified(sourceDatabase, "purchase_completed")
	sql := fmt.Sprintf(`WITH
	(SELECT min(toDate(timestamp)) FROM %s WHERE event_name = '%s') AS window_start_date,
	(SELECT max(toDate(timestamp)) FROM %s WHERE event_name = '%s') AS window_end_date
SELECT
    feature_entrants,
    feature_completions,
    round(feature_completions / nullIf(feature_entrants, 0), 4) AS feature_completion_rate,
    standard_entrants,
    standard_completions,
    round(standard_completions / nullIf(standard_entrants, 0), 4) AS standard_conversion_rate,
    round(feature_completion_rate - standard_conversion_rate, 4) AS percentage_point_lift,
    round((feature_completion_rate / nullIf(standard_conversion_rate, 0)) - 1, 4) AS relative_lift
FROM
(
    SELECT
        uniqExactIf(%s, event_name = '%s') AS feature_entrants,
        uniqExactIf(%s, event_name = '%s') AS feature_completions
    FROM %s
) feature
CROSS JOIN
(
    SELECT
        count() AS standard_entrants,
        countIf(completed.application_id != '') AS standard_completions
    FROM
    (
        SELECT application_id
        FROM %s
		WHERE toDate(timestamp) >= window_start_date AND toDate(timestamp) <= window_end_date AND application_id IS NOT NULL
        GROUP BY application_id
    ) entrants
    LEFT JOIN
    (
        SELECT application_id
        FROM %s
		WHERE toDate(timestamp) >= window_start_date AND toDate(timestamp) <= window_end_date + INTERVAL 1 DAY AND application_id IS NOT NULL
        GROUP BY application_id
    ) completed USING application_id
) standard
FORMAT JSONEachRow`, featureTable, escapeSQL(first), featureTable, escapeSQL(last), identifier(grain), escapeSQL(first), identifier(grain), escapeSQL(last), featureTable, payTable, purchaseTable)
	return analysisPlan{
		ID: "playbook:conversion-comparison:v1", Intent: "conversion_comparison", Answerability: "answerable", Grain: grain,
		Metrics:    []string{"feature completion rate", "standard checkout conversion rate", "percentage-point difference", "relative difference"},
		Dimensions: []string{"aligned observation window"}, AllowedTables: []string{schema.Database + "." + schema.Table, sourceDatabase + ".pay_now_clicked", sourceDatabase + ".purchase_completed"},
		RequiredEvidence: []string{"feature_completion_rate", "standard_conversion_rate", "percentage_point_lift", "relative_lift"},
		Limitations:      []string{"The comparison is observational and does not establish causal lift."}, SQL: sql,
	}
}

// nullableCohortField resolves a treatment/baseline marker from the business
// question and the verified physical profile. This supports unseen comparisons
// such as "rows where `coupon_code` is null" without hard-coding a feature.
func nullableCohortField(question string, profile domain.EventProfile) string {
	lower := strings.ToLower(question)
	if !strings.Contains(lower, "null") && !strings.Contains(lower, "baseline") {
		return ""
	}
	for _, field := range profile.Fields {
		name := strings.ToLower(field.ColumnName)
		if field.Nullable && strings.Contains(lower, name) {
			return field.ColumnName
		}
	}
	return ""
}

func nullableCohortComparisonPlan(input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, cohortField string) analysisPlan {
	dashboard := dashboardPlanFor(input, profile)
	first, last := dashboard.Stages[0], dashboard.Stages[len(dashboard.Stages)-1]
	grain := dashboard.Grain
	table := qualified(schema.Database, schema.Table)
	field := identifier(cohortField)
	sql := fmt.Sprintf(`SELECT
    countIf(entered = 1 AND treated = 1) AS feature_entrants,
    countIf(completed_treated = 1) AS feature_completions,
    round(feature_completions / nullIf(feature_entrants, 0), 4) AS feature_completion_rate,
    countIf(entered = 1 AND treated = 0) AS standard_entrants,
    countIf(completed_standard = 1) AS standard_completions,
    round(standard_completions / nullIf(standard_entrants, 0), 4) AS standard_conversion_rate,
    round(feature_completion_rate - standard_conversion_rate, 4) AS percentage_point_lift,
    round((feature_completion_rate / nullIf(standard_conversion_rate, 0)) - 1, 4) AS relative_lift
FROM
(
    SELECT
        %s AS entity_id,
        max(event_name = '%s') AS entered,
        max(%s IS NOT NULL AND notEmpty(toString(%s))) AS treated,
        max(event_name = '%s' AND %s IS NOT NULL AND notEmpty(toString(%s))) AS completed_treated,
        max(event_name = '%s' AND (%s IS NULL OR empty(toString(%s)))) AS completed_standard
    FROM %s
    GROUP BY entity_id
)
FORMAT JSONEachRow`, identifier(grain), escapeSQL(first), field, field, escapeSQL(last), field, field, escapeSQL(last), field, field, table)
	return analysisPlan{
		ID: "playbook:nullable-cohort-conversion:v1", Intent: "conversion_comparison", Answerability: "answerable", Grain: grain,
		Metrics:    []string{"treated cohort completion rate", "null-marker baseline completion rate", "percentage-point difference", "relative difference"},
		Dimensions: []string{cohortField + " presence"}, AllowedTables: []string{schema.Database + "." + schema.Table},
		RequiredEvidence: []string{"feature_completion_rate", "standard_conversion_rate", "percentage_point_lift", "relative_lift"},
		Limitations:      []string{"The cohort comparison is observational; the nullable marker may be selected by users and does not establish causal lift."}, SQL: sql,
	}
}

func platformFailurePlan(profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	grain := analysisGrain(profile)
	otpEvent := eventContaining(profile, "otp")
	_, last := funnelBounds(profile)
	if otpEvent == "" || !hasField(profile, "otp_success") || !hasField(profile, "device_type") {
		plan := completionPlan(profile, schema, "platform_failure")
		plan.ID = "playbook:platform-failure:unsupported"
		plan.Answerability = "not_answerable"
		plan.Limitations = []string{"OTP event, otp_success, or device_type is missing from verified instrumentation."}
		return plan
	}
	dimensions := []string{"device_type"}
	selectDimensions := []string{"ifNull(toString(device_type), 'unknown') AS device_type"}
	groupDimensions := []string{"device_type"}
	if hasField(profile, "os") {
		dimensions = append(dimensions, "os")
		selectDimensions = append(selectDimensions, "ifNull(toString(os), 'unknown') AS os")
		groupDimensions = append(groupDimensions, "os")
	}
	sql := fmt.Sprintf(`SELECT
    %s,
    countIf(event_name = '%s') AS otp_entries,
    round(avgIf(toFloat64(otp_success), event_name = '%s'), 4) AS otp_success_rate,
    uniqExactIf(%s, event_name = '%s') AS confirmations,
    round(confirmations / nullIf(otp_entries, 0), 4) AS confirmation_from_otp
FROM %s
GROUP BY %s
HAVING otp_entries > 0
ORDER BY otp_success_rate ASC, confirmation_from_otp ASC
FORMAT JSONEachRow`, strings.Join(selectDimensions, ",\n    "), escapeSQL(otpEvent), escapeSQL(otpEvent), identifier(grain), escapeSQL(last), qualified(schema.Database, schema.Table), strings.Join(groupDimensions, ", "))
	return analysisPlan{
		ID: "playbook:platform-failure:v1", Intent: "platform_failure", Answerability: "answerable", Grain: grain,
		Metrics: []string{"OTP attempts", "OTP success rate", "confirmation from OTP"}, Dimensions: dimensions,
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "worst_segment"}, SQL: sql,
	}
}

func latencyPlan(profile domain.EventProfile, schema domain.SchemaProposal, question string) analysisPlan {
	grain := analysisGrain(profile)
	latencyField := fieldContaining(profile, "latency_ms")
	_, last := funnelBounds(profile)
	if latencyField == "" {
		plan := completionPlan(profile, schema, "latency_performance")
		plan.ID = "playbook:latency:unsupported"
		plan.Answerability = "not_answerable"
		plan.Limitations = []string{"No verified latency field is available."}
		return plan
	}
	sql := fmt.Sprintf(`SELECT
    countIf(event_name = '%s') AS payments,
    round(avgIf(%s, event_name = '%s'), 1) AS avg_latency_ms,
    quantileExactIf(0.5)(%s, event_name = '%s') AS p50_latency_ms,
    quantileExactIf(0.95)(%s, event_name = '%s') AS p95_latency_ms
FROM %s
FORMAT JSONEachRow`, escapeSQL(last), identifier(latencyField), escapeSQL(last), identifier(latencyField), escapeSQL(last), identifier(latencyField), escapeSQL(last), qualified(schema.Database, schema.Table))
	limitations := []string{}
	answerability := "answerable"
	if strings.Contains(strings.ToLower(question), "faster") {
		answerability = "partially_answerable"
		limitations = append(limitations, "Standard checkout has no equivalent latency metric, so relative speed cannot yet be calculated.")
	}
	return analysisPlan{
		ID: "playbook:latency-performance:v1", Intent: "latency_performance", Answerability: answerability, Grain: grain,
		Metrics: []string{"average latency", "p50 latency", "p95 latency"}, Dimensions: []string{"confirmed payments"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"payments", "avg_latency_ms", "p50_latency_ms", "p95_latency_ms"}, Limitations: limitations, SQL: sql,
	}
}

func adoptionPlan(profile domain.EventProfile, schema domain.SchemaProposal, question string) analysisPlan {
	grain := analysisGrain(profile)
	first, _ := funnelBounds(profile)
	selected := eventContaining(profile, "selected")
	if selected == "" && len(profile.EventOrder) > 1 {
		selected = profile.EventOrder[1]
	}
	table := qualified(schema.Database, schema.Table)
	queries := []string{}
	dimensions := []string{}
	requested := requestedDimensions(question, profile)
	lowerQuestion := strings.ToLower(question)
	wantsCurrencyPair := (strings.Contains(lowerQuestion, "currency pair") || strings.Contains(lowerQuestion, "currencies")) && hasField(profile, "from_currency") && hasField(profile, "to_currency")
	if wantsCurrencyPair {
		queries = append(queries, fmt.Sprintf(`SELECT
    'currency_pair' AS dimension,
    from_currency,
    to_currency,
    concat(from_currency, ' → ', to_currency) AS segment,
    count() AS denominator,
    sum(selected) AS numerator,
    round(numerator / nullIf(denominator, 0), 4) AS rate,
    'adoption_rate' AS metric
FROM
(
    SELECT
        %s AS entity_id,
        anyIf(toString(from_currency), event_name = '%s') AS from_currency,
        anyIf(toString(to_currency), event_name = '%s') AS to_currency,
        max(event_name = '%s') AS entered,
        max(event_name = '%s') AS selected
    FROM %s
    WHERE %s IS NOT NULL
    GROUP BY entity_id
)
WHERE entered = 1
GROUP BY from_currency, to_currency`, identifier(grain), escapeSQL(first), escapeSQL(first), escapeSQL(first), escapeSQL(selected), table, identifier(grain)))
		dimensions = []string{"from_currency", "to_currency"}
	} else {
		for _, dimension := range []string{"device_type", "geoip_country_code"} {
			if !hasField(profile, dimension) {
				continue
			}
			dimensions = append(dimensions, dimension)
			queries = append(queries, fmt.Sprintf(`SELECT '%s' AS dimension, ifNull(toString(%s), 'unknown') AS segment, 'adoption_rate' AS metric,
    uniqExactIf(%s, event_name = '%s') AS denominator,
    uniqExactIf(%s, event_name = '%s') AS numerator,
    round(numerator / nullIf(denominator, 0), 4) AS rate
FROM %s GROUP BY %s`, dimension, identifier(dimension), identifier(grain), escapeSQL(first), identifier(grain), escapeSQL(selected), table, identifier(dimension)))
		}
	}
	limitations := []string{}
	if !wantsCurrencyPair && hasField(profile, "saved_method_type") {
		dimensions = append(dimensions, "saved_method_type")
		queries = append(queries, fmt.Sprintf(`SELECT 'saved_method_type' AS dimension, ifNull(toString(saved_method_type), 'unknown') AS segment, 'selected_share' AS metric,
    (SELECT uniqExactIf(%s, event_name = '%s') FROM %s) AS denominator,
    uniqExactIf(%s, event_name = '%s' AND saved_method_type IS NOT NULL) AS numerator,
    round(numerator / nullIf(denominator, 0), 4) AS rate
FROM %s GROUP BY saved_method_type`, identifier(grain), escapeSQL(selected), table, identifier(grain), escapeSQL(selected), table))
		limitations = append(limitations, "Saved-method results are selection mix, not eligibility-adjusted adoption, because method type is emitted only after selection.")
	}
	if len(queries) == 0 {
		plan := completionPlan(profile, schema, "feature_adoption")
		plan.ID = "playbook:feature-adoption:unsupported"
		plan.Answerability = "not_answerable"
		plan.Limitations = []string{"No verified adoption dimension is available."}
		return plan
	}
	sql := "SELECT * FROM (\n" + strings.Join(queries, "\nUNION ALL\n") + "\n) ORDER BY metric ASC, rate DESC\nFORMAT JSONEachRow"
	return analysisPlan{
		ID: "playbook:feature-adoption:v1", Intent: "feature_adoption", Answerability: "answerable", Grain: grain,
		Metrics: []string{"selection adoption rate", "selected method mix"}, Dimensions: dimensions,
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "top_adoption_segment"}, Limitations: limitations, SQL: sql, RequestedDimensions: requested,
	}
}

func featureCompletionPlan(input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, intent string) analysisPlan {
	dashboard := dashboardPlanFor(input, profile)
	first, last := dashboard.Stages[0], dashboard.Stages[len(dashboard.Stages)-1]
	return completionPlanWithBinding(profile, schema, intent, dashboard.Grain, first, last)
}

func completionPlan(profile domain.EventProfile, schema domain.SchemaProposal, intent string) analysisPlan {
	first, last := funnelBounds(profile)
	grain := analysisGrain(profile)
	return completionPlanWithBinding(profile, schema, intent, grain, first, last)
}

func completionPlanWithBinding(profile domain.EventProfile, schema domain.SchemaProposal, intent, grain, first, last string) analysisPlan {
	sql := fmt.Sprintf(`SELECT
    uniqExactIf(%s, event_name = '%s') AS entrants,
    uniqExactIf(%s, event_name = '%s') AS completions,
    round(completions / nullIf(entrants, 0), 4) AS completion_rate
FROM %s
FORMAT JSONEachRow`, identifier(grain), escapeSQL(first), identifier(grain), escapeSQL(last), qualified(schema.Database, schema.Table))
	return analysisPlan{
		ID: "playbook:feature-completion:v1", Intent: intent, Answerability: "answerable", Grain: grain,
		Metrics: []string{"entrants", "completions", "completion rate"}, Dimensions: availableDimensions(profile),
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"entrants", "completions", "completion_rate"}, SQL: sql,
	}
}

func completionTrendPlan(input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	dashboard := dashboardPlanFor(input, profile)
	return analysisPlan{
		ID: "playbook:completion-trend:v1", Intent: "completion_trend", Answerability: "answerable", Grain: dashboard.Grain,
		Metrics: []string{"period entrants", "period completions", "period completion rate"}, Dimensions: []string{"reporting period"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"trend_series", "latest_completion_rate"},
		Limitations: []string{"Weekly or monthly rates are descriptive and can move with traffic mix or incomplete ingestion windows."},
		SQL:         featureTrendSQL(dashboard, schema),
	}
}

func segmentCompletionPlan(input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, question string) analysisPlan {
	dashboard := dashboardPlanFor(input, profile)
	dimensions := governedDimensionNames(profile)
	requested := requestedDimensions(question, profile)
	if len(requested) > 0 {
		dimensions = requested
	}
	sql := featureSegmentsSQLForDimensions(profile, dashboard, schema, dimensions)
	if sql == "" {
		return analysisPlan{
			ID: "playbook:segment-completion:unsupported", Intent: "segment_comparison", Answerability: "not_answerable", Grain: dashboard.Grain,
			AllowedTables:       []string{schema.Database + "." + schema.Table},
			Limitations:         []string{"No verified analytical dimension requested by this question is available for this feature."},
			RequestedDimensions: requested,
		}
	}
	limitations := []string{"Segment differences are observational and may reflect eligibility or traffic-mix differences."}
	if len(requested) > 0 {
		limitations = nil
		for _, dimension := range requested {
			limitations = append(limitations, dimensionLimitations(dimension)...)
		}
		limitations = dedupeStrings(limitations)
	}
	return analysisPlan{
		ID: "playbook:segment-completion:v1", Intent: "segment_comparison", Answerability: "answerable", Grain: dashboard.Grain,
		Metrics: []string{"entrants", "completions", "completion rate"}, Dimensions: dimensions,
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"segments", "best_segment", "weakest_segment"},
		Limitations: limitations, SQL: sql, RequestedDimensions: requested,
	}
}

func funnelDiagnosisPlan(input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal) analysisPlan {
	dashboard := dashboardPlanFor(input, profile)
	return analysisPlan{
		ID: "playbook:funnel-diagnosis:v1", Intent: "funnel_diagnosis", Answerability: "answerable", Grain: dashboard.Grain,
		Metrics: []string{"unique entities at stage", "stage-to-stage drop", "stage-to-stage retention"}, Dimensions: []string{"funnel stage"},
		AllowedTables: []string{schema.Database + "." + schema.Table}, RequiredEvidence: []string{"stages", "largest_drop"},
		Limitations: []string{"Stage counts describe observed progression and do not establish why an entity dropped."},
		SQL:         featureFunnelSQL(dashboard, schema),
	}
}

func eventContaining(profile domain.EventProfile, token string) string {
	for _, event := range profile.EventOrder {
		if strings.Contains(strings.ToLower(event), token) {
			return event
		}
	}
	return ""
}

func fieldContaining(profile domain.EventProfile, token string) string {
	for _, field := range profile.Fields {
		if strings.Contains(strings.ToLower(field.ColumnName), token) {
			return field.ColumnName
		}
	}
	return ""
}

func qualified(database, table string) string { return identifier(database) + "." + identifier(table) }
func identifier(value string) string          { return "`" + strings.ReplaceAll(value, "`", "") + "`" }
func escapeSQL(value string) string           { return strings.ReplaceAll(value, "'", "''") }
