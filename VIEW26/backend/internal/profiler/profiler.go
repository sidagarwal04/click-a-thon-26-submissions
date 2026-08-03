package profiler

import (
	"encoding/json"
	"fmt"
	"math"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/view26/featurelens/internal/domain"
)

var nonIdentifier = regexp.MustCompile(`[^a-zA-Z0-9_]+`)

// maxSkippedRatio is the fraction of malformed lines above which the sample
// is rejected outright instead of being partially ingested.
const maxSkippedRatio = 0.1

type fieldStats struct {
	seen     int
	nulls    int
	kinds    map[string]struct{}
	distinct map[string]struct{}
	examples []string
}

type SkippedLine struct {
	Line   int
	Reason string
}

// ForEachRow is the single NDJSON iterator shared by profiling and insertion so
// both passes agree on which lines count as rows. Malformed lines are collected
// rather than aborting the scan.
func ForEachRow(ndjson string, fn func(line int, row map[string]any)) (int, []SkippedLine) {
	rows := 0
	skipped := []SkippedLine{}
	for index, text := range strings.Split(ndjson, "\n") {
		trimmed := strings.TrimSpace(text)
		if trimmed == "" {
			continue
		}
		var row map[string]any
		if err := json.Unmarshal([]byte(trimmed), &row); err != nil {
			snippet := trimmed
			if len(snippet) > 120 {
				snippet = snippet[:120] + "…"
			}
			skipped = append(skipped, SkippedLine{Line: index + 1, Reason: fmt.Sprintf("%v — %q", err, snippet)})
			continue
		}
		rows++
		fn(index+1, row)
	}
	return rows, skipped
}

func Profile(ndjson string) (domain.EventProfile, error) {
	result := domain.EventProfile{
		EventCounts: map[string]int{},
		EventOrder:  []string{},
		Warnings:    []string{},
	}
	stats := map[string]*fieldStats{}
	seenEvents := map[string]bool{}

	rows, skipped := ForEachRow(ndjson, func(_ int, row map[string]any) {
		flat := map[string]any{}
		flatten("", row, flat)
		for path, value := range flat {
			entry := stats[path]
			if entry == nil {
				entry = &fieldStats{kinds: map[string]struct{}{}, distinct: map[string]struct{}{}}
				stats[path] = entry
			}
			entry.seen++
			if value == nil {
				entry.nulls++
				continue
			}
			kind, normalized := valueKind(value)
			entry.kinds[kind] = struct{}{}
			if len(entry.distinct) < 2048 {
				entry.distinct[normalized] = struct{}{}
			}
			if len(entry.examples) < 3 && !contains(entry.examples, normalized) {
				entry.examples = append(entry.examples, normalized)
			}
		}
		if event, ok := row["event"].(string); ok && event != "" {
			result.EventCounts[event]++
			if !seenEvents[event] {
				result.EventOrder = append(result.EventOrder, event)
				seenEvents[event] = true
			}
		}
	})
	result.Rows = rows
	result.SkippedRows = len(skipped)
	if rows == 0 {
		if len(skipped) > 0 {
			return result, fmt.Errorf("no valid JSON event rows: all %d non-empty lines are malformed (line %d: %s)", len(skipped), skipped[0].Line, skipped[0].Reason)
		}
		return result, fmt.Errorf("event sample is empty")
	}
	if float64(len(skipped)) > maxSkippedRatio*float64(rows+len(skipped)) {
		return result, fmt.Errorf("%d of %d non-empty lines are malformed JSON (line %d: %s); refusing a mostly-invalid sample", len(skipped), rows+len(skipped), skipped[0].Line, skipped[0].Reason)
	}
	for index, entry := range skipped {
		if index == 5 {
			result.Warnings = append(result.Warnings, fmt.Sprintf("…and %d more malformed lines were skipped", len(skipped)-index))
			break
		}
		result.Warnings = append(result.Warnings, fmt.Sprintf("Skipped malformed JSON at line %d: %s", entry.Line, entry.Reason))
	}
	if len(result.EventCounts) == 0 {
		result.Warnings = append(result.Warnings, "No `event` field was observed; a feature funnel cannot be inferred.")
	}

	paths := make([]string, 0, len(stats))
	for path := range stats {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	for _, path := range paths {
		entry := stats[path]
		kinds := make([]string, 0, len(entry.kinds))
		for kind := range entry.kinds {
			kinds = append(kinds, kind)
		}
		sort.Strings(kinds)
		nullable := entry.nulls > 0 || entry.seen < result.Rows
		result.Fields = append(result.Fields, domain.FieldProfile{
			Path:           path,
			ColumnName:     ColumnName(path),
			ObservedKinds:  kinds,
			ClickHouseType: clickHouseType(path, kinds, entry, nullable),
			Nullable:       nullable,
			Seen:           entry.seen,
			Nulls:          entry.nulls + (result.Rows - entry.seen),
			Distinct:       len(entry.distinct),
			Examples:       entry.examples,
		})
		if len(kinds) > 1 && !(len(kinds) == 2 && kinds[0] == "float" && kinds[1] == "integer") {
			result.Warnings = append(result.Warnings, fmt.Sprintf("Field %s contains mixed types: %s", path, strings.Join(kinds, ", ")))
		}
	}
	return result, nil
}

func FlattenRow(row map[string]any) map[string]any {
	flat := map[string]any{}
	flatten("", row, flat)
	return flat
}

func ColumnName(path string) string {
	if path == "event" {
		return "event_name"
	}
	name := strings.ToLower(strings.ReplaceAll(path, ".", "_"))
	name = nonIdentifier.ReplaceAllString(name, "_")
	name = strings.Trim(name, "_")
	if name == "" {
		return "field"
	}
	if name[0] >= '0' && name[0] <= '9' {
		return "field_" + name
	}
	return name
}

func flatten(prefix string, value any, out map[string]any) {
	switch typed := value.(type) {
	case map[string]any:
		for key, child := range typed {
			path := key
			if prefix != "" {
				path = prefix + "." + key
			}
			flatten(path, child, out)
		}
	case []any:
		encoded, _ := json.Marshal(typed)
		out[prefix] = string(encoded)
	default:
		out[prefix] = typed
	}
}

func valueKind(value any) (string, string) {
	switch typed := value.(type) {
	case string:
		return "string", typed
	case bool:
		return "boolean", strconv.FormatBool(typed)
	case float64:
		if math.Trunc(typed) == typed {
			return "integer", strconv.FormatInt(int64(typed), 10)
		}
		return "float", strconv.FormatFloat(typed, 'f', -1, 64)
	default:
		encoded, _ := json.Marshal(typed)
		return "string", string(encoded)
	}
}

func clickHouseType(path string, kinds []string, stats *fieldStats, nullable bool) string {
	base := "String"
	lower := strings.ToLower(path)
	switch {
	case path == "timestamp":
		base = "DateTime64(3, 'UTC')"
	case len(kinds) == 1 && kinds[0] == "boolean":
		base = "UInt8"
	case len(kinds) > 0 && allNumeric(kinds):
		if contains(kinds, "float") {
			base = "Float64"
		} else {
			base = "Int64"
		}
	case isLowCardinalityField(lower) && len(stats.distinct) <= 256:
		base = "LowCardinality(String)"
	}
	if nullable && !strings.HasPrefix(base, "LowCardinality(") {
		return "Nullable(" + base + ")"
	}
	if nullable && strings.HasPrefix(base, "LowCardinality(") {
		return "LowCardinality(Nullable(String))"
	}
	return base
}

func allNumeric(kinds []string) bool {
	for _, kind := range kinds {
		if kind != "integer" && kind != "float" {
			return false
		}
	}
	return len(kinds) > 0
}

func isLowCardinalityField(path string) bool {
	for _, token := range []string{"event", "device_type", "os", "app_version", "geoip_country_code", "destination", "currency", "channel", "status", "method", "relation", "source", "drop_step"} {
		if path == token || strings.HasSuffix(path, "."+token) || strings.HasSuffix(path, "_"+token) {
			return true
		}
	}
	return false
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
