package agent

import (
	"fmt"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/domain"
)

type ContextAgent struct{}

type baselineSourceTable struct {
	Name  string
	Grain string
	Role  string
}

var baselineSourceTables = []baselineSourceTable{
	{Name: "search_typed", Grain: "user", Role: "destination discovery search"},
	{Name: "landing_page_scrolled", Grain: "user", Role: "landing engagement signal"},
	{Name: "destination_card_clicked", Grain: "user", Role: "destination consideration signal"},
	{Name: "auth_completed", Grain: "user", Role: "authenticated journey milestone"},
	{Name: "application_started", Grain: "application", Role: "visa application entrant"},
	{Name: "document_uploaded", Grain: "application", Role: "document completion milestone"},
	{Name: "pay_now_clicked", Grain: "application", Role: "standard checkout entrant"},
	{Name: "purchase_completed", Grain: "application", Role: "standard checkout completion"},
}

func BaselineSourceTableNames() []string {
	names := make([]string, 0, len(baselineSourceTables))
	for _, table := range baselineSourceTables {
		names = append(names, table.Name)
	}
	return names
}

func BaselineContext() domain.ContextVersion {
	nodes := []domain.ContextNode{
		{Key: "domain:atlys-pre-purchase", Type: "business_domain", Name: "Atlys pre-purchase journey", Status: "declared", Confidence: .95, Sources: []string{"base_context.md"}, Properties: map[string]any{"north_star": "conversion", "scope": "destination discovery through purchase"}},
		{Key: "entity:user", Type: "entity", Name: "User", Status: "declared", Confidence: .95, Sources: []string{"base_context.md"}, Properties: map[string]any{"identifier": "user_id", "grain": "traveller"}},
		{Key: "entity:application", Type: "entity", Name: "Application", Status: "declared", Confidence: .95, Sources: []string{"base_context.md"}, Properties: map[string]any{"identifier": "application_id", "created_by": "application_started"}},
		{Key: "entity:destination", Type: "entity", Name: "Destination", Status: "declared", Confidence: .95, Sources: []string{"base_context.md"}, Properties: map[string]any{"identifier": "destination", "format": "ISO-2"}},
		{Key: "funnel:pre-purchase", Type: "funnel", Name: "Pre-purchase conversion funnel", Status: "verified", Confidence: .98, Sources: []string{"base_context.md", "ClickHouse catalog"}, Properties: map[string]any{"steps": []string{"destination_card_clicked", "application_started", "document_uploaded", "purchase_completed"}}},
		{Key: "metric:leadership-conversion", Type: "metric", Name: "Leadership conversion rate", Status: "contradicted", Confidence: .55, Sources: []string{"base_context.md"}, Properties: map[string]any{"numerator": "completed purchases", "denominator": "sessions", "superseded_by": "metric:funnel-conversion"}},
		{Key: "metric:funnel-conversion", Type: "metric", Name: "Funnel conversion rate", Status: "declared", Confidence: .9, Sources: []string{"base_context.md"}, Properties: map[string]any{"numerator": "purchase_completed users", "denominator": "application_started users", "canonical": true}},
		{Key: "issue:K1-ios-otp", Type: "known_issue", Name: "iOS WebKit OTP autofill regression", Status: "declared", Confidence: .8, Sources: []string{"base_context.md"}, Properties: map[string]any{"affected_segment": "iOS", "affected_transition": "pay_now_clicked -> purchase_completed"}},
		{Key: "issue:K2-passport-model", Type: "known_issue", Name: "Android passport scan regression", Status: "declared", Confidence: .75, Sources: []string{"base_context.md"}},
		{Key: "role:product-manager", Type: "role_profile", Name: "Product Manager", Status: "verified", Confidence: 1, Properties: map[string]any{"goals": []string{"adoption", "conversion impact", "drop-off", "recommended action"}, "answer_style": "headline, why, confidence, action"}},
		{Key: "role:growth", Type: "role_profile", Name: "Growth / Commercial", Status: "verified", Confidence: 1, Properties: map[string]any{"goals": []string{"incremental conversion", "channel performance", "revenue impact"}}},
		{Key: "role:instrumentation", Type: "role_profile", Name: "Data / Instrumentation", Status: "verified", Confidence: 1, Properties: map[string]any{"goals": []string{"event completeness", "schema quality", "data anomalies"}}},
		{Key: "rule:aggregate-in-clickhouse", Type: "operating_principle", Name: "Aggregate in ClickHouse", Status: "verified", Confidence: 1, Properties: map[string]any{"instruction": "Never send raw event rows to the LLM; aggregate in ClickHouse and interpret the results."}},
		{Key: "rule:clarify-conversion", Type: "operating_principle", Name: "Clarify conversion denominator", Status: "verified", Confidence: 1, Properties: map[string]any{"instruction": "Always distinguish session conversion from application conversion."}},
	}
	for _, table := range baselineSourceTables {
		nodes = append(nodes,
			domain.ContextNode{Key: "event:" + table.Name, Type: "event", Name: table.Name, Status: "declared", Confidence: .9, Sources: []string{"base_context.md"}, Properties: map[string]any{"grain": table.Grain, "role": table.Role}},
			domain.ContextNode{Key: "table:atlys." + table.Name, Type: "table", Name: table.Name, Status: "declared", Confidence: .9, Sources: []string{"base_context.md"}, Properties: map[string]any{"database": "atlys", "category": "source", "event_column": "event", "timestamp_column": "timestamp"}},
		)
	}
	edges := []domain.ContextEdge{
		{From: "entity:user", Relation: "STARTS", To: "entity:application", Status: "declared", Confidence: .95},
		{From: "entity:application", Relation: "TARGETS", To: "entity:destination", Status: "declared", Confidence: .95},
		{From: "issue:K1-ios-otp", Relation: "AFFECTS", To: "metric:funnel-conversion", Status: "inferred", Confidence: .8},
		{From: "role:product-manager", Relation: "INTERESTED_IN", To: "metric:funnel-conversion", Status: "verified", Confidence: 1},
		{From: "event:pay_now_clicked", Relation: "PRECEDES", To: "event:purchase_completed", Status: "declared", Confidence: .95},
	}
	for _, table := range baselineSourceTables {
		edges = append(edges,
			domain.ContextEdge{From: "domain:atlys-pre-purchase", Relation: "OBSERVES", To: "event:" + table.Name, Status: "declared", Confidence: .9},
			domain.ContextEdge{From: "event:" + table.Name, Relation: "STORED_IN", To: "table:atlys." + table.Name, Status: "declared", Confidence: .9},
		)
	}
	conflicts := []domain.ContextConflict{
		{Key: "conflict:eta-field", Severity: "high", Description: "The hand-written entity definition and physical schema disagree on the ETA field name and type.", Declared: "visa_issuance_eta_days Integer", Observed: "eta_shown Nullable(String)", Status: "open"},
		{Key: "conflict:conversion-denominator", Severity: "high", Description: "Two conversion definitions use different denominators.", Declared: "purchases / sessions", Observed: "purchases / application_started users in funnel dashboards", Resolution: "Canonical definition is metric:funnel-conversion (purchase_completed users / application_started users); the session-denominator definition is superseded.", Status: "open"},
		{Key: "conflict:legacy-sort-key", Severity: "medium", Description: "Existing tables are sorted by event id although queries filter by time and segments.", Declared: "time and segment analysis", Observed: "ORDER BY (id, timestamp, user_id)", Status: "open"},
		{Key: "conflict:timestamp-timezone", Severity: "high", Description: "Raw event timestamps have no timezone suffix and legacy and new tables normalize them differently.", Declared: "naive ISO timestamp strings", Observed: "legacy DateTime display differs from the explicit UTC feature table", Resolution: "Use aligned calendar dates for cross-table comparisons until timestamp provenance is formalized.", Status: "mitigated"},
	}
	return domain.ContextVersion{
		Version:        0,
		ParentVersion:  -1,
		Feature:        "baseline",
		State:          "published",
		SchemaVersions: []string{"atlys-existing:v0"},
		Nodes:          nodes,
		Edges:          edges,
		Conflicts:      conflicts,
		Summary:        "Baseline Atlys ontology compiled from the supplied context and known physical-schema contradictions.",
		CreatedAt:      time.Now().UTC(),
	}
}

// ApplySourceCatalog validates the declared baseline against the authoritative
// ClickHouse catalog. Stable node keys let every later context version inherit
// the same eight physical source contracts without copying their data.
func ApplySourceCatalog(graph domain.ContextVersion, catalog []domain.CatalogTable) domain.ContextVersion {
	observed := make(map[string]domain.CatalogTable, len(catalog))
	for _, table := range catalog {
		observed[table.Name] = table
	}

	nodes := append([]domain.ContextNode{}, graph.Nodes...)
	edges := append([]domain.ContextEdge{}, graph.Edges...)
	conflicts := append([]domain.ContextConflict{}, graph.Conflicts...)
	for _, definition := range baselineSourceTables {
		table, ok := observed[definition.Name]
		if !ok {
			conflicts = append(conflicts, domain.ContextConflict{
				Key: "conflict:missing-source-table:" + definition.Name, Severity: "high",
				Description: "A table declared by the baseline business context is missing from the ClickHouse source catalog.",
				Declared:    "atlys." + definition.Name, Observed: "not found", Status: "open",
			})
			continue
		}
		columnNames := make([]string, 0, len(table.Columns))
		columnTypes := make(map[string]string, len(table.Columns))
		for _, column := range table.Columns {
			columnNames = append(columnNames, column.Name)
			columnTypes[column.Name] = column.Type
		}
		nodes = append(nodes,
			domain.ContextNode{Key: "event:" + definition.Name, Type: "event", Name: definition.Name, Status: "observed", Confidence: .99, Sources: []string{"base_context.md", "ClickHouse system catalog"}, Properties: map[string]any{"grain": definition.Grain, "role": definition.Role, "row_count": table.Rows}},
			domain.ContextNode{Key: "table:" + table.Database + "." + table.Name, Type: "table", Name: table.Name, Status: "observed", Confidence: .99, Sources: []string{"ClickHouse system.tables", "ClickHouse system.columns"}, Properties: map[string]any{
				"database": table.Database, "category": "source", "engine": table.Engine, "row_count": table.Rows,
				"partition_by": table.PartitionKey, "order_by": table.SortingKey, "columns": columnNames,
				"column_types": columnTypes, "ddl": table.DDL,
			}},
		)
		edges = append(edges,
			domain.ContextEdge{From: "domain:atlys-pre-purchase", Relation: "OBSERVES", To: "event:" + definition.Name, Status: "verified", Confidence: .99},
			domain.ContextEdge{From: "event:" + definition.Name, Relation: "STORED_IN", To: "table:" + table.Database + "." + table.Name, Status: "verified", Confidence: .99},
		)
	}
	graph.Nodes = dedupeContextNodes(nodes)
	graph.Edges = dedupeContextEdges(edges)
	graph.Conflicts = dedupeContextConflicts(conflicts)
	graph.Summary = fmt.Sprintf("Baseline Atlys ontology verified against %d canonical ClickHouse source tables with versioned physical and business semantics.", len(catalog))
	return graph
}

func (ContextAgent) Evolve(parent domain.ContextVersion, input domain.FeatureInput, profile domain.EventProfile, schema domain.SchemaProposal, traceID, state string) domain.ContextVersion {
	slug := Slug(input.Slug)
	if slug == "" {
		slug = Slug(input.Name)
	}
	version := parent.Version + 1
	nodes := append([]domain.ContextNode{}, parent.Nodes...)
	edges := append([]domain.ContextEdge{}, parent.Edges...)
	conflicts := append([]domain.ContextConflict{}, parent.Conflicts...)
	featureKey := "feature:" + slug
	tableKey := "table:" + schema.Database + "." + schema.Table
	nodes = append(nodes,
		domain.ContextNode{Key: featureKey, Type: "feature", Name: input.Name, Status: "verified", Confidence: .95, Sources: []string{"feature specification", "event sample"}, Properties: map[string]any{"slug": slug, "event_count": len(profile.EventCounts), "sample_rows": profile.Rows}},
		domain.ContextNode{Key: tableKey, Type: "table", Name: schema.Table, Status: "observed", Confidence: .98, Sources: []string{"schema verification"}, Properties: map[string]any{"database": schema.Database, "schema_version": schema.Version, "partition_by": schema.PartitionBy, "order_by": schema.OrderBy, "columns": schemaColumnNames(schema)}},
	)
	edges = append(edges, domain.ContextEdge{From: featureKey, Relation: "STORED_IN", To: tableKey, Status: "verified", Confidence: .98})
	dimensionDefinitions := governedDimensionDefinitions(profile)
	for _, definition := range dimensionDefinitions {
		dimensionKey := "dimension:" + slug + ":" + definition.Field
		nodes = append(nodes, domain.ContextNode{
			Key: dimensionKey, Type: "dimension", Name: input.Name + " · " + strings.ReplaceAll(definition.Field, "_", " "),
			Status: "verified", Confidence: .92, Sources: []string{"event profile", "schema verification", "semantic dimension catalog"},
			Properties: map[string]any{
				"field": definition.Field, "semantic_type": definition.SemanticType, "meaning": definition.Meaning,
				"aliases": definition.Aliases, "binding": "governed entrant event", "queryable": true,
			},
		})
		edges = append(edges,
			domain.ContextEdge{From: featureKey, Relation: "HAS_DIMENSION", To: dimensionKey, Status: "verified", Confidence: .92},
			domain.ContextEdge{From: dimensionKey, Relation: "STORED_IN", To: tableKey, Status: "verified", Confidence: .98, Properties: map[string]any{"column": definition.Field}},
		)
	}

	for _, eventName := range profile.EventOrder {
		eventKey := "event:" + eventName
		nodes = append(nodes, domain.ContextNode{Key: eventKey, Type: "event", Name: eventName, Status: "observed", Confidence: .99, Sources: []string{"event profile"}, Properties: map[string]any{"sample_count": profile.EventCounts[eventName]}})
		edges = append(edges,
			domain.ContextEdge{From: featureKey, Relation: "EMITS", To: eventKey, Status: "verified", Confidence: .99},
			domain.ContextEdge{From: eventKey, Relation: "STORED_IN", To: tableKey, Status: "verified", Confidence: .99},
		)
	}

	if dashboard := dashboardPlanFor(input, profile); len(dashboard.Stages) >= 2 {
		for index, eventName := range dashboard.Stages {
			for nodeIndex := range nodes {
				if nodes[nodeIndex].Key == "event:"+eventName {
					if nodes[nodeIndex].Properties == nil {
						nodes[nodeIndex].Properties = map[string]any{}
					}
					nodes[nodeIndex].Properties["sequence_position"] = index + 1
					break
				}
			}
			if index > 0 {
				edges = append(edges, domain.ContextEdge{From: "event:" + dashboard.Stages[index-1], Relation: "PRECEDES", To: "event:" + eventName, Status: "inferred", Confidence: .9})
			}
		}
		first := dashboard.Stages[0]
		last := dashboard.Stages[len(dashboard.Stages)-1]
		metricKey := "metric:" + slug + "-completion-rate"
		dimensions := governedDimensionNames(profile)
		nodes = append(nodes, domain.ContextNode{Key: metricKey, Type: "metric", Name: input.Name + " completion rate", Status: "verified", Confidence: .9, Sources: []string{"feature specification", "verified schema"}, Properties: map[string]any{"numerator_event": last, "denominator_event": first, "grain": dashboard.Grain, "dimensions": dimensions}})
		edges = append(edges,
			domain.ContextEdge{From: metricKey, Relation: "COMPUTED_FROM", To: "event:" + first, Status: "verified", Confidence: .95},
			domain.ContextEdge{From: metricKey, Relation: "COMPUTED_FROM", To: "event:" + last, Status: "verified", Confidence: .95},
			domain.ContextEdge{From: "role:product-manager", Relation: "INTERESTED_IN", To: metricKey, Status: "verified", Confidence: 1},
		)
		for _, definition := range dimensionDefinitions {
			edges = append(edges, domain.ContextEdge{From: metricKey, Relation: "SEGMENTED_BY", To: "dimension:" + slug + ":" + definition.Field, Status: "verified", Confidence: .92})
		}

		generalPlaybooks := []struct {
			key      string
			intent   string
			required []string
		}{
			{key: "playbook:feature-completion:v1", intent: "feature_completion", required: []string{"entrants", "completions", "completion_rate"}},
			{key: "playbook:completion-trend:v1", intent: "completion_trend", required: []string{"trend_series", "latest_completion_rate"}},
			{key: "playbook:segment-completion:v1", intent: "segment_comparison", required: []string{"segments", "best_segment", "weakest_segment"}},
			{key: "playbook:funnel-diagnosis:v1", intent: "funnel_diagnosis", required: []string{"stages", "largest_drop"}},
		}
		for _, playbook := range generalPlaybooks {
			if !contextHasNode(nodes, playbook.key) {
				nodes = append(nodes, domain.ContextNode{Key: playbook.key, Type: "analysis_playbook", Name: strings.ReplaceAll(strings.TrimPrefix(strings.TrimSuffix(playbook.key, ":v1"), "playbook:"), "-", " "), Status: "verified", Confidence: .95, Sources: []string{"analytics contract compiler"}, Properties: map[string]any{"intent": playbook.intent, "required_evidence": playbook.required, "execution": "aggregate in ClickHouse"}})
			}
			edges = append(edges,
				domain.ContextEdge{From: metricKey, Relation: "ANALYZED_BY", To: playbook.key, Status: "verified", Confidence: .95},
				domain.ContextEdge{From: playbook.key, Relation: "QUERIES", To: tableKey, Status: "verified", Confidence: .98},
			)
			if playbook.intent == "segment_comparison" {
				for _, definition := range dimensionDefinitions {
					edges = append(edges, domain.ContextEdge{From: playbook.key, Relation: "GROUPS_BY", To: "dimension:" + slug + ":" + definition.Field, Status: "verified", Confidence: .92})
				}
			}
		}
	}

	for index, question := range ExtractQuestions(input.SpecMarkdown) {
		questionKey := fmt.Sprintf("question:%s:%d", slug, index+1)
		intent := classifyFeatureIntent(input, question)
		playbookKey, requiredEvidence := playbookForIntent(intent)
		if intent == "conversion_comparison" && nullableCohortField(question, profile) != "" {
			playbookKey = "playbook:nullable-cohort-conversion:v1"
		}
		nodes = append(nodes, domain.ContextNode{Key: questionKey, Type: "business_question", Name: question, Status: "declared", Confidence: .95, Sources: []string{"feature specification"}, Properties: map[string]any{"role": "product_manager", "intent": intent, "required_evidence": requiredEvidence}})
		if !contextHasNode(nodes, playbookKey) {
			nodes = append(nodes, domain.ContextNode{Key: playbookKey, Type: "analysis_playbook", Name: strings.ReplaceAll(strings.TrimPrefix(strings.TrimSuffix(playbookKey, ":v1"), "playbook:"), "-", " "), Status: "verified", Confidence: .95, Sources: []string{"analytics contract compiler"}, Properties: map[string]any{"intent": intent, "required_evidence": requiredEvidence, "execution": "aggregate in ClickHouse"}})
		}
		edges = append(edges,
			domain.ContextEdge{From: featureKey, Relation: "ENABLES_QUESTION", To: questionKey, Status: "verified", Confidence: .95},
			domain.ContextEdge{From: "role:product-manager", Relation: "ASKS", To: questionKey, Status: "verified", Confidence: .95},
			domain.ContextEdge{From: questionKey, Relation: "RESOLVED_BY", To: playbookKey, Status: "verified", Confidence: .95},
			domain.ContextEdge{From: playbookKey, Relation: "QUERIES", To: tableKey, Status: "verified", Confidence: .98},
		)
		if intent == "conversion_comparison" && playbookKey != "playbook:nullable-cohort-conversion:v1" {
			edges = append(edges,
				domain.ContextEdge{From: playbookKey, Relation: "QUERIES", To: "table:atlys.pay_now_clicked", Status: "verified", Confidence: .98},
				domain.ContextEdge{From: playbookKey, Relation: "QUERIES", To: "table:atlys.purchase_completed", Status: "verified", Confidence: .98},
			)
		}
	}

	if strings.Contains(strings.ToLower(input.SpecMarkdown), "otp") {
		edges = append(edges, domain.ContextEdge{From: "issue:K1-ios-otp", Relation: "MAY_AFFECT", To: featureKey, Status: "inferred", Confidence: .85, Properties: map[string]any{"reason": "The feature introduces an OTP-dependent payment step."}})
	}
	nodes = dedupeContextNodes(nodes)
	edges = dedupeContextEdges(edges)
	schemaVersions := dedupeStrings(append(append([]string{}, parent.SchemaVersions...), fmt.Sprintf("%s:v%d", slug, schema.Version)))

	return domain.ContextVersion{
		Version:        version,
		ParentVersion:  parent.Version,
		Feature:        slug,
		State:          state,
		SchemaVersions: schemaVersions,
		Nodes:          nodes,
		Edges:          edges,
		Conflicts:      conflicts,
		Summary:        fmt.Sprintf("Context v%d adds %s, %d observed events, %d governed dimensions, its typed table, completion metric, and role-aware PM questions.", version, input.Name, len(profile.EventOrder), len(dimensionDefinitions)),
		TraceID:        traceID,
		CreatedAt:      time.Now().UTC(),
	}
}

func playbookForIntent(intent string) (string, []string) {
	switch intent {
	case "support_demand_impact":
		return "playbook:support-demand-impact:unsupported", nil
	case "recovery_revenue":
		return "playbook:recovery-revenue:unsupported", nil
	case "customer_geography":
		return "playbook:customer-geography:v1", []string{"requested_city", "customers", "total_customers", "customer_share"}
	case "group_size_completion":
		return "playbook:group-size-completion:v1", []string{"segments", "lowest_completion_segment"}
	case "group_traveller_churn":
		return "playbook:group-traveller-churn:v1", []string{"groups_started", "travellers_added", "travellers_removed", "additions_per_group", "removals_per_group"}
	case "group_document_bottleneck":
		return "playbook:group-document-bottleneck:v1", []string{"segments"}
	case "group_segments":
		return "playbook:group-segments:v1", []string{"segments", "largest_segment"}
	case "recovery_drop_step":
		return "playbook:recovery-drop-step:v1", []string{"segments", "most_recoverable_step"}
	case "recovery_channel":
		return "playbook:recovery-channel:v1", []string{"segments", "best_channel"}
	case "recovery_timing":
		return "playbook:recovery-timing:v1", []string{"segments", "best_timing"}
	case "recovery_segments":
		return "playbook:recovery-segments:v1", []string{"segments", "largest_recovery_segment"}
	case "conversion_comparison":
		return "playbook:conversion-comparison:v1", []string{"feature_completion_rate", "standard_conversion_rate", "percentage_point_lift", "relative_lift"}
	case "platform_failure":
		return "playbook:platform-failure:v1", []string{"segments", "worst_segment"}
	case "latency_performance":
		return "playbook:latency-performance:v1", []string{"payments", "avg_latency_ms", "p50_latency_ms", "p95_latency_ms"}
	case "feature_adoption":
		return "playbook:feature-adoption:v1", []string{"segments", "top_adoption_segment"}
	case "completion_trend":
		return "playbook:completion-trend:v1", []string{"trend_series", "latest_completion_rate"}
	case "segment_comparison":
		return "playbook:segment-completion:v1", []string{"segments", "best_segment", "weakest_segment"}
	case "funnel_diagnosis":
		return "playbook:funnel-diagnosis:v1", []string{"stages", "largest_drop"}
	default:
		return "playbook:feature-completion:v1", []string{"entrants", "completions", "completion_rate"}
	}
}

func schemaColumnNames(schema domain.SchemaProposal) []string {
	columns := make([]string, 0, len(schema.Columns))
	for _, column := range schema.Columns {
		columns = append(columns, column.Name)
	}
	return columns
}

func dedupeContextNodes(nodes []domain.ContextNode) []domain.ContextNode {
	deduped := make([]domain.ContextNode, 0, len(nodes))
	indices := map[string]int{}
	for _, node := range nodes {
		if index, exists := indices[node.Key]; exists {
			deduped[index] = node
			continue
		}
		indices[node.Key] = len(deduped)
		deduped = append(deduped, node)
	}
	return deduped
}

func dedupeContextEdges(edges []domain.ContextEdge) []domain.ContextEdge {
	deduped := make([]domain.ContextEdge, 0, len(edges))
	indices := map[string]int{}
	for _, edge := range edges {
		key := edge.From + "\x00" + edge.Relation + "\x00" + edge.To
		if index, exists := indices[key]; exists {
			deduped[index] = edge
			continue
		}
		indices[key] = len(deduped)
		deduped = append(deduped, edge)
	}
	return deduped
}

func dedupeContextConflicts(conflicts []domain.ContextConflict) []domain.ContextConflict {
	deduped := make([]domain.ContextConflict, 0, len(conflicts))
	indices := map[string]int{}
	for _, conflict := range conflicts {
		if index, exists := indices[conflict.Key]; exists {
			deduped[index] = conflict
			continue
		}
		indices[conflict.Key] = len(deduped)
		deduped = append(deduped, conflict)
	}
	return deduped
}

func dedupeStrings(values []string) []string {
	deduped := make([]string, 0, len(values))
	seen := map[string]bool{}
	for _, value := range values {
		if seen[value] {
			continue
		}
		seen[value] = true
		deduped = append(deduped, value)
	}
	return deduped
}

func contextHasNode(nodes []domain.ContextNode, key string) bool {
	for _, node := range nodes {
		if node.Key == key {
			return true
		}
	}
	return false
}

func ExtractQuestions(markdown string) []string {
	questions := []string{}
	current := ""
	flush := func() {
		current = strings.TrimSpace(strings.ReplaceAll(current, "**", ""))
		if strings.Contains(current, "?") {
			questions = append(questions, strings.Join(strings.Fields(current), " "))
		}
		current = ""
	}
	for _, line := range strings.Split(markdown, "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "- ") {
			flush()
			current = strings.TrimSpace(strings.TrimPrefix(trimmed, "- "))
			continue
		}
		if current != "" && trimmed != "" && !strings.HasPrefix(trimmed, "#") {
			current += " " + trimmed
			continue
		}
		if current != "" {
			flush()
		}
	}
	flush()
	return questions
}
