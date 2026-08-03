package main

import (
	"fmt"
	"regexp"
	"strings"
)

// The serving layer, and nothing else. Anything not named here is refused before it
// reaches ClickHouse.
//
// This list is the SECOND line of defence, not the first. The first is the grant set in
// ingest/sql/manual/009_mcp_reader.sql: sonyliv_mcp simply cannot read events_clean or
// session_intervals, whatever SQL arrives. The guard exists because a clear "that table
// is outside the serving layer" is a better answer to a model than ACCESS_DENIED, and
// because refusing early keeps a malformed query from consuming a connection.
//
// The order matters for correctness of the argument: if the guard is ever talked past —
// and parsers are talked past — the grant still holds. Neither is trusted alone, and the
// guard is never the thing standing between a model and user identity.
var allowedRelations = map[string]bool{
	"serving_concurrency_live":   true,
	"serving_concurrency_minute": true,
	"serving_live_total":         true,
	"serving_live_content":       true,
	"serving_minute_current":     true,
	"serving_drop_signal":        true,
	"serving_watermark":          true,
	"serving_watermark_history":  true,
}

// Statement forms that are not a read. ClickHouse would reject most of these for a
// readonly = 2 user anyway; they are listed so the refusal names the actual problem.
var forbiddenLeadingKeywords = []string{
	"insert", "alter", "create", "drop", "truncate", "rename", "attach", "detach",
	"optimize", "grant", "revoke", "set", "system", "kill", "use", "delete", "update",
	"exchange", "undrop", "move", "backup", "restore",
}

// Table-valued functions that would reach outside the service entirely — the interesting
// bypass, since none of them are "a table" and so none would be caught by a name check.
var forbiddenFunctions = []string{
	"url", "file", "s3", "s3cluster", "remote", "remotesecure", "mysql", "postgresql",
	"jdbc", "odbc", "hdfs", "azureblobstorage", "gcs", "deltalake", "iceberg", "hudi",
	"executable", "cluster", "clusterallreplicas", "merge", "sqlite", "redis", "mongodb",
	"input", "generaterandom", "numbers_mt", "loop", "fuzzquery", "urlcluster",
	"filecluster", "hdfscluster", "icebergs3", "azureblobstoragecluster",
}

var (
	// Strips block and line comments so a payload cannot hide inside one. Applied before
	// every other check, since `SELECT /* FROM events_clean */ 1` and its inverse both
	// matter.
	reBlockComment = regexp.MustCompile(`(?s)/\*.*?\*/`)
	reLineComment  = regexp.MustCompile(`--[^\n]*`)
	// FROM/JOIN targets. Captures an optional database qualifier so `sonyliv_prod.x`,
	// `"x"` and bare `x` all normalise to the same relation name.
	reRelation = regexp.MustCompile(`(?i)\b(?:from|join)\s+([` + "`" + `"]?[A-Za-z_][A-Za-z0-9_]*[` + "`" + `"]?(?:\s*\.\s*[` + "`" + `"]?[A-Za-z_][A-Za-z0-9_]*[` + "`" + `"]?)?)`)
	reFunction = regexp.MustCompile(`(?i)\b([A-Za-z_][A-Za-z0-9_]*)\s*\(`)
	reIdent    = regexp.MustCompile("[`\"]")
)

// validateQuery accepts exactly one read-only SELECT/WITH statement against the serving
// layer and explains precisely why anything else is refused.
func validateQuery(q string) error {
	stripped := reLineComment.ReplaceAllString(reBlockComment.ReplaceAllString(q, " "), " ")
	trimmed := strings.TrimSpace(stripped)
	if trimmed == "" {
		return fmt.Errorf("empty query")
	}

	// One statement only. A trailing semicolon is fine; a second statement is not, or
	// the checks below would validate the first and ClickHouse would run both.
	if body := strings.TrimSuffix(trimmed, ";"); strings.Contains(body, ";") {
		return fmt.Errorf("only a single statement is allowed; found more than one ';'")
	}

	lower := strings.ToLower(trimmed)
	if !strings.HasPrefix(lower, "select") && !strings.HasPrefix(lower, "with") {
		for _, kw := range forbiddenLeadingKeywords {
			if strings.HasPrefix(lower, kw) {
				return fmt.Errorf("%s is not permitted: this connection is read-only and may only SELECT from the serving layer", strings.ToUpper(kw))
			}
		}
		return fmt.Errorf("query must begin with SELECT or WITH")
	}

	// Functions are checked BEFORE relations. A table-valued function appears as
	// `FROM url(...)`, so the relation check would otherwise catch it first and report
	// "url is outside the serving layer" — safe, but it misdescribes the problem, and a
	// model told the wrong reason tends to retry a variation of the same thing.
	// serving_drop_signal is also invoked with function syntax and is simply absent from
	// the forbidden list, so it passes through to the allowlist below.
	for _, m := range reFunction.FindAllStringSubmatch(stripped, -1) {
		fn := strings.ToLower(m[1])
		for _, bad := range forbiddenFunctions {
			if fn == bad {
				return fmt.Errorf("function %s() is not permitted: it can read outside the serving layer", fn)
			}
		}
	}

	// CTE names are legitimate JOIN/FROM targets and must not be mistaken for tables.
	cte := collectCTENames(stripped)

	for _, m := range reRelation.FindAllStringSubmatch(stripped, -1) {
		rel := normaliseRelation(m[1])
		if rel == "" || cte[rel] {
			continue
		}
		if !allowedRelations[rel] {
			return fmt.Errorf("relation %q is outside the serving layer; this connection exposes only: %s",
				rel, strings.Join(sortedAllowed(), ", "))
		}
	}

	return nil
}

// collectCTENames finds names bound by WITH ... AS ( ... ), so they are not treated as
// tables. Deliberately loose: a false positive here only means a name is *skipped* by the
// relation check, and a real table cannot be reached that way because the grant would
// still refuse it.
func collectCTENames(q string) map[string]bool {
	out := map[string]bool{}
	re := regexp.MustCompile(`(?i)(?:\bwith\s+|,\s*)([A-Za-z_][A-Za-z0-9_]*)\s+as\s*\(`)
	for _, m := range re.FindAllStringSubmatch(q, -1) {
		out[strings.ToLower(m[1])] = true
	}
	return out
}

// normaliseRelation reduces `sonyliv_prod`.`x` and "x" to x, and rejects a database
// qualifier that is not ours outright by returning the qualified name so the caller
// refuses it by allowlist miss.
func normaliseRelation(raw string) string {
	s := reIdent.ReplaceAllString(strings.TrimSpace(raw), "")
	s = strings.ToLower(strings.ReplaceAll(s, " ", ""))
	if i := strings.Index(s, "."); i >= 0 {
		db, tbl := s[:i], s[i+1:]
		if db != defaultDatabase() {
			// Returned qualified so the error names the real target — reaching into
			// `system` should not be reported as if it were a serving table typo.
			return db + "." + tbl
		}
		return tbl
	}
	return s
}

func sortedAllowed() []string {
	out := make([]string, 0, len(allowedRelations))
	for k := range allowedRelations {
		out = append(out, k)
	}
	// Stable output so an error message is diffable in tests.
	for i := 0; i < len(out); i++ {
		for j := i + 1; j < len(out); j++ {
			if out[j] < out[i] {
				out[i], out[j] = out[j], out[i]
			}
		}
	}
	return out
}
