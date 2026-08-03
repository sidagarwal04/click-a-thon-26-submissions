package chx

import (
	"strings"
	"testing"
)

// engine_full in the shape ClickHouse returns it for events_raw, mirroring the
// DDL in sql/002_events_raw.sql. The ORDER BY tuple's comma is the thing that
// broke the first parser: splitting the whole string on "," puts
// "event_timestamp) SETTINGS non_replicated_deduplication_window" in one chunk,
// and the first setting silently reads as unset — a false clean bill of health
// from `doctor`.
const rawEventsEngineFull = "MergeTree PARTITION BY toYYYYMM(event_timestamp) " +
	"ORDER BY (video_session_id, event_timestamp) " +
	"SETTINGS non_replicated_deduplication_window = 1000, " +
	"replicated_deduplication_window = 1000, " +
	"replicated_deduplication_window_seconds = 2592000, index_granularity = 8192"

// events_clean is a ReplacingMergeTree whose version column is named inside the
// engine parentheses, ahead of a four-column ORDER BY tuple. Both are commas
// the parser has to walk past before it reaches SETTINGS, so this is the
// stricter case of the two.
const eventsCleanEngineFull = "ReplacingMergeTree(row_version) " +
	"PARTITION BY toYYYYMMDD(session_start_ts) " +
	"ORDER BY (session_key, event_ts, event_type, event) " +
	"SETTINGS index_granularity = 8192"

func TestSettingFromParsesPastTheOrderByTuple(t *testing.T) {
	for _, tc := range []struct{ name, want string }{
		{"non_replicated_deduplication_window", "1000"},
		{"replicated_deduplication_window", "1000"},
		{"replicated_deduplication_window_seconds", "2592000"},
		{"index_granularity", "8192"},
		{"not_a_setting", ""},
	} {
		if got := settingFrom(rawEventsEngineFull, tc.name); got != tc.want {
			t.Errorf("settingFrom(%s) = %q, want %q", tc.name, got, tc.want)
		}
	}

	// The engine's own parenthesised version column must not be mistaken for
	// part of the settings tail.
	if got := settingFrom(eventsCleanEngineFull, "index_granularity"); got != "8192" {
		t.Errorf("settingFrom(index_granularity) on a ReplacingMergeTree = %q, want 8192", got)
	}
	if got := settingFrom(eventsCleanEngineFull, "row_version"); got != "" {
		t.Errorf("the RMT version column parsed as a setting: got %q", got)
	}

	// A setting name must not match as a prefix of a longer one.
	short := "MergeTree ORDER BY a SETTINGS replicated_deduplication_window_seconds = 2592000"
	if got := settingFrom(short, "replicated_deduplication_window"); got != "" {
		t.Errorf("prefix match leaked: got %q, want empty", got)
	}

	if got := settingFrom("MergeTree ORDER BY a", "anything"); got != "" {
		t.Errorf("a table with no SETTINGS clause returned %q", got)
	}
}

func TestIsReplicatedEngine(t *testing.T) {
	// SharedMergeTree is what ClickHouse Cloud substitutes for MergeTree, and
	// it deduplicates through the replicated window.
	for _, e := range []string{"ReplicatedMergeTree", "SharedMergeTree", "SharedReplacingMergeTree"} {
		if !IsReplicatedEngine(e) {
			t.Errorf("%s should be treated as replicated", e)
		}
	}
	for _, e := range []string{"MergeTree", "ReplacingMergeTree", ""} {
		if IsReplicatedEngine(e) {
			t.Errorf("%s should not be treated as replicated", e)
		}
	}
}

// TestProblemsCatchesTheCloudDedupTrap covers the case a single-node test
// cluster cannot produce: a SharedMergeTree carrying the server defaults. The
// load would succeed and the idempotency guarantee would be quietly gone.
func TestProblemsCatchesTheCloudDedupTrap(t *testing.T) {
	report := &PreflightReport{
		Tables: []TableSettings{{
			Name:   "events_raw",
			Exists: true,
			Engine: "SharedMergeTree",
			// Set on the table, but the timer is left at the default.
			NonReplicatedWindow:     "1000",
			ReplicatedWindow:        "1000",
			ReplicatedWindowSeconds: defaultReplicatedWindowSeconds,
		}},
	}

	problems := report.Problems("default")
	if len(problems) != 1 {
		t.Fatalf("got %d problems, want 1: %v", len(problems), problems)
	}
	if !strings.Contains(problems[0], "replicated_deduplication_window_seconds") {
		t.Errorf("problem does not name the expiring window: %s", problems[0])
	}
}

func TestProblemsCatchesAnUnsetReplicatedWindow(t *testing.T) {
	report := &PreflightReport{
		Tables: []TableSettings{{
			Name:                    "content_dim",
			Exists:                  true,
			Engine:                  "SharedReplacingMergeTree",
			NonReplicatedWindow:     "100",
			ReplicatedWindow:        "0",
			ReplicatedWindowSeconds: "2592000",
		}},
	}
	problems := report.Problems("default")
	if len(problems) != 1 || !strings.Contains(problems[0], "duplicate rows") {
		t.Fatalf("an unset replicated window was not flagged: %v", problems)
	}
}

// TestProblemsIgnoresTheLocalEngine: the non-replicated window has no timer, so
// the same settings that are a problem on Cloud are correct on a laptop.
// Flagging them there would train the operator to ignore the warning.
func TestProblemsIsQuietOnANonReplicatedEngine(t *testing.T) {
	report := &PreflightReport{
		Tables: []TableSettings{{
			Name:                    "events_raw",
			Exists:                  true,
			Engine:                  "MergeTree",
			NonReplicatedWindow:     "1000",
			ReplicatedWindow:        "10000",
			ReplicatedWindowSeconds: defaultReplicatedWindowSeconds,
		}},
	}
	if problems := report.Problems("default"); len(problems) != 0 {
		t.Errorf("a correctly configured local table was flagged: %v", problems)
	}
}

func TestProblemsSkipsTablesThatDoNotExistYet(t *testing.T) {
	report := &PreflightReport{
		Tables: []TableSettings{{Name: "events_raw", Exists: false}},
	}
	if problems := report.Problems("default"); len(problems) != 0 {
		t.Errorf("a not-yet-created table was flagged: %v", problems)
	}
}

func TestProblemsReportsMissingGrants(t *testing.T) {
	report := &PreflightReport{MissingGrants: []string{"SELECT from system tables"}}
	problems := report.Problems("readonly_user")
	if len(problems) != 1 || !strings.Contains(problems[0], "readonly_user") {
		t.Fatalf("missing grant not reported against the user: %v", problems)
	}
}
