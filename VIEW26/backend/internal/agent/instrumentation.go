package agent

import (
	"fmt"
	"regexp"
	"sort"
	"strings"

	"github.com/view26/featurelens/internal/domain"
)

var unsafeSlug = regexp.MustCompile(`[^a-z0-9]+`)

type InstrumentationAgent struct {
	Database string
}

func (a InstrumentationAgent) Design(input domain.FeatureInput, profile domain.EventProfile) domain.SchemaProposal {
	database, table, version := a.Target(input)

	fieldByColumn := map[string]domain.FieldProfile{}
	for _, field := range profile.Fields {
		fieldByColumn[field.ColumnName] = field
	}
	ordered := preferredColumns(fieldByColumn)
	columns := make([]domain.ColumnProposal, 0, len(ordered))
	definitions := make([]string, 0, len(ordered))
	for _, name := range ordered {
		field := fieldByColumn[name]
		columnType := field.ClickHouseType
		if name == "event_name" {
			columnType = "LowCardinality(String)"
		}
		columns = append(columns, domain.ColumnProposal{
			Name:       name,
			SourcePath: field.Path,
			Type:       columnType,
			Nullable:   field.Nullable,
		})
		definitions = append(definitions, fmt.Sprintf("    `%s` %s", name, columnType))
	}

	orderBy := []string{
		"toDate(timestamp)",
		"event_name",
		"ifNull(destination, '')",
		"ifNull(device_type, '')",
		"ifNull(application_id, '')",
		"ifNull(user_id, '')",
		"timestamp",
	}
	orderBy = availableOrderExpressions(orderBy, fieldByColumn)
	partition := "toYYYYMM(timestamp)"
	if _, ok := fieldByColumn["timestamp"]; !ok {
		partition = "tuple()"
	}
	ddl := fmt.Sprintf("CREATE TABLE IF NOT EXISTS `%s`.`%s`\n(\n%s\n)\nENGINE = MergeTree\nPARTITION BY %s\nORDER BY (%s);",
		database,
		table,
		strings.Join(definitions, ",\n"),
		partition,
		strings.Join(orderBy, ", "),
	)

	return domain.SchemaProposal{
		Version:     version,
		Database:    database,
		Table:       table,
		DDL:         ddl,
		Columns:     columns,
		PartitionBy: partition,
		OrderBy:     orderBy,
		Rationale: []string{
			"One typed table per feature keeps feature funnels local while preserving the common event envelope.",
			"Monthly partitions support retention and time-window pruning without over-partitioning the sample.",
			"The sort key starts with date and the most common PM segment filters rather than the legacy random event id.",
			"Nested objects are flattened into typed columns so ClickHouse performs aggregation without JSON parsing.",
			"No TTL or materialized view is proposed until an observed workload demonstrates that it earns its maintenance cost.",
		},
		Status: "proposed",
	}
}

func (a InstrumentationAgent) Target(input domain.FeatureInput) (string, string, int) {
	database := a.Database
	if database == "" {
		database = "featurelens_poc"
	}
	slug := Slug(input.Slug)
	if slug == "" {
		slug = Slug(input.Name)
	}
	if slug == "" {
		slug = "feature"
	}
	version := input.SchemaVersion
	if version < 1 {
		version = 1
	}
	table := fmt.Sprintf("%s_events_v%d", slug, version)
	return database, table, version
}

func (a InstrumentationAgent) Validate(profile domain.EventProfile, proposal domain.SchemaProposal) domain.SchemaValidation {
	checks := []domain.ValidationCheck{
		{Name: "non_empty_sample", Passed: profile.Rows > 0, Details: fmt.Sprintf("%d NDJSON rows profiled", profile.Rows)},
		{Name: "event_discriminator", Passed: eventRows(profile) == profile.Rows, Details: fmt.Sprintf("%d/%d rows carry an event discriminator", eventRows(profile), profile.Rows)},
		{Name: "required_timestamp", Passed: requiredField(profile, "timestamp"), Details: "timestamp must be present and non-null on every event"},
		{Name: "typed_columns", Passed: len(proposal.Columns) >= 4, Details: fmt.Sprintf("%d typed columns generated", len(proposal.Columns))},
		{Name: "time_partition", Passed: proposal.PartitionBy != "" && proposal.PartitionBy != "tuple()", Details: proposal.PartitionBy},
		{Name: "analytics_sort_key", Passed: len(proposal.OrderBy) >= 3, Details: strings.Join(proposal.OrderBy, ", ")},
		{Name: "no_unresolved_mixed_types", Passed: len(profile.Warnings) == 0, Details: warningDetails(profile.Warnings)},
	}
	passed := true
	for _, check := range checks {
		if !check.Passed && check.Name != "no_unresolved_mixed_types" {
			passed = false
		}
	}
	return domain.SchemaValidation{Passed: passed, Checks: checks}
}

func eventRows(profile domain.EventProfile) int {
	total := 0
	for _, count := range profile.EventCounts {
		total += count
	}
	return total
}

func requiredField(profile domain.EventProfile, column string) bool {
	for _, field := range profile.Fields {
		if field.ColumnName == column {
			return field.Seen == profile.Rows && field.Nulls == 0
		}
	}
	return false
}

func Slug(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	value = unsafeSlug.ReplaceAllString(value, "_")
	return strings.Trim(value, "_")
}

func preferredColumns(fields map[string]domain.FieldProfile) []string {
	preferred := []string{"event_name", "id", "timestamp", "user_id", "application_id", "destination", "device_type", "os", "app_version", "geoip_country_code"}
	seen := map[string]bool{}
	ordered := make([]string, 0, len(fields))
	for _, name := range preferred {
		if _, ok := fields[name]; ok {
			ordered = append(ordered, name)
			seen[name] = true
		}
	}
	rest := make([]string, 0, len(fields))
	for name := range fields {
		if !seen[name] {
			rest = append(rest, name)
		}
	}
	sort.Strings(rest)
	return append(ordered, rest...)
}

func availableOrderExpressions(expressions []string, fields map[string]domain.FieldProfile) []string {
	available := make([]string, 0, len(expressions))
	for _, expression := range expressions {
		column := expression
		if strings.HasPrefix(expression, "toDate(") {
			column = "timestamp"
		}
		if strings.HasPrefix(expression, "ifNull(") {
			column = strings.TrimPrefix(expression, "ifNull(")
			column = strings.SplitN(column, ",", 2)[0]
		}
		if _, ok := fields[column]; ok {
			available = append(available, expression)
		}
	}
	if len(available) == 0 {
		return []string{"tuple()"}
	}
	return available
}

func warningDetails(warnings []string) string {
	if len(warnings) == 0 {
		return "No mixed-type warnings"
	}
	return strings.Join(warnings, "; ")
}
