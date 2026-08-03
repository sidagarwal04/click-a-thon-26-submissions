package chx

import (
	"strings"
	"testing"
)

// TestSplitStatementsIsCommentAware guards the DDL loader against the thing a
// naive strings.Split(sql, ";") gets wrong: the schema is heavily commented and
// those comments contain both semicolons and apostrophes.
func TestSplitStatementsIsCommentAware(t *testing.T) {
	sql := `
-- A comment with a semicolon; and an apostrophe's worth of trouble.
CREATE TABLE a (x UInt8) ENGINE = Memory;

/* block comment;
   spanning lines; with semicolons */
CREATE TABLE b (
    y String DEFAULT 'a;b',            -- literal containing a semicolon
    z String MATERIALIZED splitByChar('-', y)[1]
) ENGINE = Memory;
`
	got := splitStatements(sql)
	if len(got) != 2 {
		t.Fatalf("got %d statements, want 2:\n%q", len(got), got)
	}
	if !strings.HasPrefix(got[0], "CREATE TABLE a") {
		t.Errorf("statement 0 = %q", got[0])
	}
	if !strings.Contains(got[1], `'a;b'`) {
		t.Errorf("statement 1 lost its literal: %q", got[1])
	}
	if !strings.Contains(got[1], `splitByChar('-', y)`) {
		t.Errorf("statement 1 lost the quoted dash: %q", got[1])
	}
	for i, s := range got {
		if strings.Contains(s, "block comment") || strings.Contains(s, "worth of trouble") {
			t.Errorf("statement %d retained a comment: %q", i, s)
		}
	}
}

// TestSplitStatementsHandlesEscapes: the schema uses '\x1F' in a string literal.
func TestSplitStatementsHandlesEscapes(t *testing.T) {
	sql := `SELECT concatWithSeparator('\x1F', a, b); SELECT 1;`
	got := splitStatements(sql)
	if len(got) != 2 {
		t.Fatalf("got %d statements, want 2: %q", len(got), got)
	}
	if !strings.Contains(got[0], `'\x1F'`) {
		t.Errorf("escape sequence mangled: %q", got[0])
	}
}

// TestSchemaStatementsLoad checks the embedded DDL parses into the expected
// objects — a missing file or a stray semicolon would otherwise only show up
// against a live server.
func TestSchemaStatementsLoad(t *testing.T) {
	stmts, err := SchemaStatements()
	if err != nil {
		t.Fatalf("SchemaStatements: %v", err)
	}
	if len(stmts) == 0 {
		t.Fatal("no statements loaded from the embedded sql/ directory")
	}

	joined := strings.ToUpper(strings.Join(func() []string {
		out := make([]string, len(stmts))
		for i, s := range stmts {
			out[i] = s.SQL
		}
		return out
	}(), "\n"))

	for _, want := range []string{
		"CONTENT_DIM", "CONTENT_CURRENT", "CONTENT_DICT",
		"EVENTS_RAW", "DIRTY_SESSIONS", "EVENTS_RAW_TO_DIRTY_MV",
		"EVENTS_CLEAN", "EVENTS_RAW_TO_CLEAN_MV", "EVENTS_DEDUP",
		"INGEST_BATCHES", "INGEST_REJECTS",
	} {
		if !strings.Contains(joined, want) {
			t.Errorf("embedded schema is missing %s", want)
		}
	}

	// No object may carry the old sl_ prefix. Renaming half a schema is worse
	// than not renaming it: `schema` would create the new tables, the loader
	// would write to them, and a stray sl_-prefixed MV would keep draining an
	// empty one.
	if strings.Contains(joined, "SL_") {
		t.Error("embedded schema still contains an sl_-prefixed object name")
	}

	// Every statement must be idempotent, or `schema` stops being re-runnable.
	// ALTER ... MODIFY SETTING qualifies: it is metadata-only and converges to
	// the same state however many times it runs. It is also the only way a
	// settings correction reaches a database that already has the tables, since
	// CREATE TABLE IF NOT EXISTS is a no-op there.
	//
	// MODIFY QUERY qualifies for the same reason and is there for the same
	// job: CREATE MATERIALIZED VIEW IF NOT EXISTS is a no-op against an existing
	// MV, so it is the only way an updated MV body reaches a deployed database.
	// Re-running it with an identical body converges to the same definition.
	// Unlike DROP + CREATE it leaves no window in which inserts are silently
	// not propagated.
	//
	// ALTER ... MODIFY COLUMN qualifies too, and for the same purpose: it assigns
	// a fixed target type, so re-running converges. Widening an Enum8 by appending
	// a value is metadata-only — existing rows keep their encoding — and it is the
	// only way the new state reaches a database that already has the table.
	for _, s := range stmts {
		u := strings.ToUpper(s.SQL)
		idempotent := strings.Contains(u, "IF NOT EXISTS") ||
			strings.Contains(u, "OR REPLACE") ||
			strings.Contains(u, "MODIFY SETTING") ||
			strings.Contains(u, "MODIFY QUERY") ||
			strings.Contains(u, "MODIFY COLUMN")
		if !idempotent {
			t.Errorf("%s[%d] is not idempotent: %s", s.File, s.Index, s.Summary())
		}
	}
}

// statementCreating returns the DDL statement that creates the named object.
func statementCreating(t *testing.T, object string) string {
	t.Helper()
	stmts, err := SchemaStatements()
	if err != nil {
		t.Fatalf("SchemaStatements: %v", err)
	}
	for _, s := range stmts {
		u := strings.ToUpper(s.SQL)
		if !strings.HasPrefix(u, "CREATE") {
			continue
		}
		// Match the object name as it appears after the {{db}} placeholder, so
		// "events_raw" does not also match "events_raw_to_clean_mv".
		if strings.Contains(s.SQL, "{{db}}."+object+"\n") ||
			strings.Contains(s.SQL, "{{db}}."+object+"\r\n") ||
			strings.Contains(s.SQL, "{{db}}."+object+" ") ||
			strings.HasSuffix(strings.TrimSpace(s.SQL), "{{db}}."+object) {
			return s.SQL
		}
	}
	t.Fatalf("no CREATE statement found for %s", object)
	return ""
}

// TestLandingZoneIsNotReplacing.
//
// events_raw is the evidence layer: the duplicate rate, the conflicting-payload
// row, and the ability to re-derive events_clean under a corrected rule all
// depend on it keeping every row it was given. A ReplacingMergeTree here would
// make its row count drift with merge activity and delete the losing copy of a
// conflict, and nothing downstream would notice until someone tried to explain
// a number. Cheap to assert, impossible to spot in review six files later.
func TestLandingZoneIsNotReplacing(t *testing.T) {
	ddl := strings.ToUpper(statementCreating(t, "events_raw"))
	if strings.Contains(ddl, "REPLACINGMERGETREE") {
		t.Error("events_raw must be a plain MergeTree: it is the audit layer, and " +
			"replacement would make its row count and its duplicate rate non-deterministic")
	}
	if !strings.Contains(ddl, "ENGINE = MERGETREE") {
		t.Error("events_raw is no longer ENGINE = MergeTree")
	}
}

// TestLandingZoneCarriesNoNormalization.
//
// The raw/clean split only holds if nothing normalizes on the way in. A
// MATERIALIZED column added to events_raw for convenience would quietly become
// a second place a rule lives, and the two would drift.
func TestLandingZoneCarriesNoNormalization(t *testing.T) {
	ddl := statementCreating(t, "events_raw")
	for _, banned := range []string{"lowerUTF8", "upperUTF8", "signal", "is_periodic_ping", "_norm"} {
		if strings.Contains(ddl, banned) {
			t.Errorf("events_raw contains %q: normalization belongs in events_raw_to_clean_mv, "+
				"so that every producer gets one rule instead of each client implementing it", banned)
		}
	}
	// The two derived keys are the deliberate exception: they are lossless
	// functions of an id, not a semantic correction.
	if !strings.Contains(ddl, "sipHash64(video_session_id)") {
		t.Error("events_raw lost the session_key derivation")
	}
}

// TestCleanLayerIsReplacingOnTheDedupKey.
//
// Three things have to agree or the dedup silently stops working:
// the engine must replace, the version column it replaces by must be the one
// the MV computes, and the sort key must be exactly the semantic event key.
// A sort key that drifts from the dedup key is the dangerous one — the table
// still works, it just stops collapsing anything.
func TestCleanLayerIsReplacingOnTheDedupKey(t *testing.T) {
	ddl := statementCreating(t, "events_clean")

	if !strings.Contains(ddl, "ENGINE = ReplacingMergeTree(row_version)") {
		t.Error("events_clean must be ReplacingMergeTree(row_version); without it, re-delivered " +
			"rows accumulate forever and every events_dedup read pays to group them away")
	}
	if !strings.Contains(ddl, "ORDER BY (session_key, event_ts, event_type, event)") {
		t.Error("events_clean's ORDER BY must be exactly the semantic event key, or the engine " +
			"and the events_dedup view disagree about what a duplicate is")
	}
	// Collapse is only total because a session cannot straddle partitions.
	if !strings.Contains(ddl, "PARTITION BY toYYYYMMDD(session_start_ts)") {
		t.Error("events_clean must partition by session start: ReplacingMergeTree cannot collapse " +
			"across partitions, and partitioning by event time would split a session")
	}
}

// TestDedupViewResolvesWithoutFinal.
//
// Replacement is eventual. The view is what makes the answer independent of
// whether a merge has run, and it can only do that with argMax — a FINAL here
// would both shift compaction cost onto every read and, on a Cloud replica that
// has not seen the freshest parts, still not guarantee what it looks like it
// guarantees. [official: insert-optimize-avoid-final]
func TestDedupViewResolvesWithoutFinal(t *testing.T) {
	ddl := statementCreating(t, "events_dedup")

	if strings.Contains(strings.ToUpper(ddl), " FINAL") {
		t.Error("events_dedup must not use FINAL; resolve with argMax by row_version")
	}
	if !strings.Contains(ddl, "argMax(") {
		t.Error("events_dedup no longer resolves with argMax")
	}
	if !strings.Contains(ddl, "GROUP BY session_key, event_ts, event_type, event") {
		t.Error("events_dedup must group by exactly the semantic event key, matching " +
			"events_clean's ORDER BY")
	}
}

// TestDedupSettingsCoverBothEngineFamilies.
//
// Which deduplication window a table honours is chosen by the engine, not by
// the DDL: a local MergeTree reads non_replicated_deduplication_window, and the
// SharedMergeTree that ClickHouse Cloud creates from the same statement reads
// the replicated_* pair instead. Setting only the first is the trap — it passes
// every local test and silently stops deduplicating in production.
func TestDedupSettingsCoverBothEngineFamilies(t *testing.T) {
	stmts, err := SchemaStatements()
	if err != nil {
		t.Fatalf("SchemaStatements: %v", err)
	}

	// Tables that carry a deduplication guarantee, and the statement kinds that
	// must state it for both engine families.
	for _, table := range []string{"EVENTS_RAW", "CONTENT_DIM"} {
		var stated bool
		for _, s := range stmts {
			u := strings.ToUpper(s.SQL)
			if !strings.Contains(u, table) {
				continue
			}
			if !strings.Contains(u, "NON_REPLICATED_DEDUPLICATION_WINDOW") {
				continue
			}
			if !strings.Contains(u, "REPLICATED_DEDUPLICATION_WINDOW =") {
				t.Errorf("%s states non_replicated_deduplication_window without the replicated "+
					"equivalent: deduplication would be off on ClickHouse Cloud", table)
			}
			// The replicated window also expires on a timer (server default
			// 3600s) where the non-replicated one never does.
			if !strings.Contains(u, "REPLICATED_DEDUPLICATION_WINDOW_SECONDS") {
				t.Errorf("%s does not override replicated_deduplication_window_seconds: "+
					"replay stops being a no-op an hour after the load", table)
			}
			stated = true
		}
		if !stated {
			t.Errorf("no deduplication settings found for %s", table)
		}
	}
}

// TestContentDictionaryKeepsASignedKey.
//
// A simple-key dictionary key is always UInt64 — ClickHouse coerces the
// declared Int64 without complaint and then throws on any lookup of a negative
// id. The catalogue contains one (-987654322), so a plain LAYOUT(HASHED())
// makes enrichment fail on real data while looking correct in the DDL. This is
// asserted statically because reproducing it needs both a live server and an
// event that references that specific id.
func TestContentDictionaryKeepsASignedKey(t *testing.T) {
	stmts, err := SchemaStatements()
	if err != nil {
		t.Fatalf("SchemaStatements: %v", err)
	}

	var dict string
	for _, s := range stmts {
		if strings.Contains(strings.ToUpper(s.SQL), "CREATE OR REPLACE DICTIONARY") {
			dict = strings.ToUpper(s.SQL)
			break
		}
	}
	if dict == "" {
		t.Fatal("no CREATE DICTIONARY statement found in the embedded schema")
	}

	if !strings.Contains(dict, "COMPLEX_KEY_HASHED") {
		t.Error("the content dictionary must use COMPLEX_KEY_HASHED: a simple key is " +
			"coerced to UInt64 and every lookup of the catalogue's negative content_id throws")
	}
	if !strings.Contains(dict, "CONTENT_ID  INT64") {
		t.Error("the dictionary key must stay Int64 to match content_dim")
	}
}

// TestRenderRedactsPassword: dry-run output and error messages are meant to be
// pasted into a review, so the dictionary's credentials must not ride along.
func TestRenderRedactsPassword(t *testing.T) {
	c := &Client{Database: "default", user: "svc", password: "s3cr3t"}

	const tmpl = `SOURCE(CLICKHOUSE(DB '{{db}}' USER '{{ch_user}}' PASSWORD '{{ch_password}}'))`

	redacted := c.Render(tmpl, true)
	if strings.Contains(redacted, "s3cr3t") {
		t.Errorf("redacted render leaked the password: %s", redacted)
	}
	if !strings.Contains(redacted, "'default'") || !strings.Contains(redacted, "'svc'") {
		t.Errorf("redacted render dropped non-secret substitutions: %s", redacted)
	}

	live := c.Render(tmpl, false)
	if !strings.Contains(live, "'s3cr3t'") {
		t.Errorf("live render did not substitute the password: %s", live)
	}
}

func TestEscapeSQLString(t *testing.T) {
	// A password containing a quote must not be able to close the literal.
	got := escapeSQLString(`pa'ss\word`)
	if want := `pa\'ss\\word`; got != want {
		t.Errorf("escapeSQLString = %q, want %q", got, want)
	}
}
