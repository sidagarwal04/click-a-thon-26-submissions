package chx

import (
	"context"
	"fmt"
	"strings"
)

// PreflightReport describes a target service in the terms that change how this
// pipeline behaves against it.
type PreflightReport struct {
	Version    string
	Deployment string // "ClickHouse Cloud (SharedMergeTree)", "self-managed", ...
	// AsyncInsertDefault is the server-side default, before the connection
	// override. Cloud ships it enabled.
	AsyncInsertDefault string
	DatabaseExists     bool
	Tables             []TableSettings
	MissingGrants      []string
}

// TableSettings is the deduplication configuration actually in force for one
// table, read back from the server rather than assumed from the DDL.
type TableSettings struct {
	Name                    string
	Exists                  bool
	Engine                  string
	NonReplicatedWindow     string
	ReplicatedWindow        string
	ReplicatedWindowSeconds string
}

// dedupGuaranteeTables are the tables whose idempotency depends on a
// deduplication window being set correctly for the engine in use.
//
// events_clean is deliberately absent. Its duplicate handling does not rely on
// an insert-deduplication window at all: nothing inserts into it directly, and
// row-level duplicates are collapsed by ReplacingMergeTree and resolved by the
// events_dedup view. A missing window there would be harmless, so reporting it
// as a problem would be noise.
var dedupGuaranteeTables = []string{"events_raw", "content_dim"}

// defaultReplicatedWindowSeconds is the ClickHouse default for
// replicated_deduplication_window_seconds: one hour. Left alone, a replicated
// or shared table stops deduplicating a replay after that, which turns
// "re-running a load is a no-op" into a silent double-load overnight.
const defaultReplicatedWindowSeconds = "3600"

// Problems lists what would go wrong if this pipeline loaded into the service
// as configured. An empty result means the preflight is clean.
//
// Separated from the printing so it can be tested against engine families that
// cannot be created on a single node — which is the whole point of the check.
func (r *PreflightReport) Problems(user string) []string {
	var problems []string

	for _, tb := range r.Tables {
		if !tb.Exists || !IsReplicatedEngine(tb.Engine) {
			continue
		}
		// The trap: deduplication on this engine is governed by the replicated
		// window, and the load succeeds either way. Only replay reveals it.
		if tb.ReplicatedWindow == "" || tb.ReplicatedWindow == "0" {
			problems = append(problems, fmt.Sprintf(
				"%s is %s but replicated_deduplication_window is %q — a retried or replayed batch will duplicate rows",
				tb.Name, tb.Engine, tb.ReplicatedWindow))
		}
		if tb.ReplicatedWindowSeconds == defaultReplicatedWindowSeconds {
			problems = append(problems, fmt.Sprintf(
				"%s still has the default replicated_deduplication_window_seconds=%s — replay is a no-op for one hour, then silently double-loads",
				tb.Name, defaultReplicatedWindowSeconds))
		}
	}

	for _, g := range r.MissingGrants {
		problems = append(problems, fmt.Sprintf("user %q cannot %s", user, g))
	}
	return problems
}

// IsReplicatedEngine reports whether deduplication for this engine is governed
// by the replicated window rather than the non-replicated one. SharedMergeTree
// is the ClickHouse Cloud engine and behaves as replicated here.
func IsReplicatedEngine(engine string) bool {
	e := strings.ToLower(engine)
	return strings.Contains(e, "replicated") || strings.Contains(e, "shared")
}

// Preflight inspects a service before the first load.
//
// Everything here is read from the server. The DDL says what was requested; the
// engine decides what is in force, and on ClickHouse Cloud those differ in ways
// that do not surface as an error.
func (c *Client) Preflight(ctx context.Context) (*PreflightReport, error) {
	r := &PreflightReport{}

	var err error
	if r.Version, err = c.ServerVersion(ctx); err != nil {
		return nil, err
	}
	if r.Deployment, err = c.deployment(ctx); err != nil {
		return nil, err
	}
	// The `default` column, not `value`. This connection sets async_insert=0
	// for the bulk path, and `value` reports that override straight back — the
	// pipeline's own setting dressed up as the server's, which is worse than
	// printing nothing.
	if err := c.Conn.QueryRow(ctx,
		"SELECT default FROM system.settings WHERE name = 'async_insert'").Scan(&r.AsyncInsertDefault); err != nil {
		r.AsyncInsertDefault = "unknown"
	}
	if err := c.Conn.QueryRow(ctx,
		"SELECT count() > 0 FROM system.databases WHERE name = ?", c.Database).Scan(&r.DatabaseExists); err != nil {
		return nil, fmt.Errorf("check database %s: %w", c.Database, err)
	}

	for _, name := range dedupGuaranteeTables {
		ts, err := c.tableSettings(ctx, name)
		if err != nil {
			return nil, err
		}
		r.Tables = append(r.Tables, ts)
	}

	r.MissingGrants = c.missingGrants(ctx)
	return r, nil
}

// deployment distinguishes ClickHouse Cloud from a self-managed server.
//
// It matters because Cloud substitutes SharedMergeTree for MergeTree, which
// moves deduplication onto a different, timer-expiring window.
//
// Detected from cloud_mode. An earlier version inferred it from
// default_table_engine and got it wrong against a real service: Cloud reports
// ReplicatedMergeTree there while actually creating SharedMergeTree tables, so
// a genuine Cloud service was labelled self-managed.
func (c *Client) deployment(ctx context.Context) (string, error) {
	var cloudMode bool
	if err := c.Conn.QueryRow(ctx,
		"SELECT value = '1' FROM system.settings WHERE name = 'cloud_mode'").Scan(&cloudMode); err != nil {
		// Older servers predate the setting; absence means not Cloud.
		return "self-managed", nil
	}
	if cloudMode {
		return "ClickHouse Cloud — tables become Shared*MergeTree, deduplication uses the replicated window", nil
	}
	return "self-managed", nil
}

// tableSettings reads the deduplication settings in force for one table.
func (c *Client) tableSettings(ctx context.Context, name string) (TableSettings, error) {
	ts := TableSettings{Name: name}

	var engineFull string
	err := c.Conn.QueryRow(ctx,
		"SELECT engine, engine_full FROM system.tables WHERE database = ? AND name = ?",
		c.Database, name).Scan(&ts.Engine, &engineFull)
	if err != nil {
		// Not created yet is a normal state before the first `schema` run.
		return ts, nil
	}
	ts.Exists = true

	// The per-table override lives in engine_full; anything absent there is
	// inherited from the server default, which is exactly the case worth
	// showing as blank rather than guessing at.
	ts.NonReplicatedWindow = settingFrom(engineFull, "non_replicated_deduplication_window")
	ts.ReplicatedWindow = settingFrom(engineFull, "replicated_deduplication_window")
	ts.ReplicatedWindowSeconds = settingFrom(engineFull, "replicated_deduplication_window_seconds")

	// An unset replicated window falls back to the server default, which is
	// what actually governs the table. Report that, not the blank.
	if ts.ReplicatedWindow == "" {
		ts.ReplicatedWindow = c.serverDefault(ctx, "replicated_deduplication_window")
	}
	if ts.ReplicatedWindowSeconds == "" {
		ts.ReplicatedWindowSeconds = c.serverDefault(ctx, "replicated_deduplication_window_seconds")
	}
	return ts, nil
}

func (c *Client) serverDefault(ctx context.Context, name string) string {
	var v string
	if err := c.Conn.QueryRow(ctx,
		"SELECT value FROM system.merge_tree_settings WHERE name = ?", name).Scan(&v); err != nil {
		return ""
	}
	return v
}

// settingFrom extracts one `name = value` pair from an engine_full clause.
//
// Only the tail after SETTINGS is parsed. engine_full leads with the ORDER BY
// tuple, whose own commas would otherwise split a setting away from its name:
//
//	MergeTree PARTITION BY ... ORDER BY (video_session_id,
//	event_timestamp) SETTINGS non_replicated_deduplication_window = 1000, replicated_...
//
// Splitting that on commas puts "event) SETTINGS non_replicated_deduplication_window"
// in one chunk, and the first setting silently reads as unset.
func settingFrom(engineFull, name string) string {
	idx := strings.LastIndex(engineFull, "SETTINGS ")
	if idx < 0 {
		return ""
	}
	for _, part := range strings.Split(engineFull[idx+len("SETTINGS "):], ",") {
		key, value, ok := strings.Cut(part, "=")
		if !ok {
			continue
		}
		if strings.TrimSpace(key) == name {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

// missingGrants names the privileges the pipeline needs and the user lacks.
//
// Checked by attempting the cheapest harmless form of each, because
// SHOW GRANTS has to be parsed and does not account for roles the same way the
// access check does.
func (c *Client) missingGrants(ctx context.Context) []string {
	var missing []string
	checks := []struct {
		what  string
		query string
	}{
		{"SELECT from system tables", "SELECT 1 FROM system.tables LIMIT 1"},
		{"read system.merge_tree_settings (needed to verify deduplication)",
			"SELECT 1 FROM system.merge_tree_settings LIMIT 1"},
	}
	for _, chk := range checks {
		if err := c.Conn.Exec(ctx, chk.query); err != nil {
			missing = append(missing, chk.what)
		}
	}
	return missing
}
