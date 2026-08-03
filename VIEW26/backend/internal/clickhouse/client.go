package clickhouse

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/domain"
	"github.com/view26/featurelens/internal/profiler"
)

type Client struct {
	endpoint        string
	user            string
	password        string
	controlDatabase string
	sourceDatabase  string
	http            *http.Client
	enabled         bool
}

func FromEnv() *Client {
	host := strings.TrimSpace(os.Getenv("CLICKHOUSE_HOST"))
	if host == "" {
		return &Client{http: http.DefaultClient}
	}
	secure := envBool("CLICKHOUSE_SECURE", true)
	scheme := "https"
	if !secure {
		scheme = "http"
	}
	port := strings.TrimSpace(os.Getenv("CLICKHOUSE_HTTP_PORT"))
	if port == "" {
		if secure {
			port = "8443"
		} else {
			port = "8123"
		}
	}
	return &Client{
		endpoint:        fmt.Sprintf("%s://%s:%s/", scheme, host, port),
		user:            envDefault("CLICKHOUSE_USER", "default"),
		password:        os.Getenv("CLICKHOUSE_PASSWORD"),
		controlDatabase: envDefault("CLICKHOUSE_CONTROL_DATABASE", "featurelens_poc"),
		sourceDatabase:  envDefault("CLICKHOUSE_SOURCE_DATABASE", "atlys"),
		enabled:         true,
		http: &http.Client{Timeout: 45 * time.Second, Transport: &http.Transport{
			TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12},
		}},
	}
}

func (c *Client) Enabled() bool { return c.enabled }

func (c *Client) SourceDatabase() string {
	if c.sourceDatabase == "" {
		return "atlys"
	}
	return c.sourceDatabase
}

func (c *Client) ControlDatabase() string {
	if c.controlDatabase == "" {
		return "featurelens_poc"
	}
	return c.controlDatabase
}

func NewDisabled() *Client { return &Client{http: http.DefaultClient, sourceDatabase: "atlys"} }

// DiscoverSourceCatalog reads the authoritative physical contracts for the
// canonical baseline tables. The semantic manifest supplies the expected names;
// system.tables and system.columns prove which contracts actually exist.
func (c *Client) DiscoverSourceCatalog(ctx context.Context, names []string) ([]domain.CatalogTable, error) {
	if !c.enabled {
		return nil, nil
	}
	if len(names) == 0 {
		return []domain.CatalogTable{}, nil
	}
	quotedNames := make([]string, 0, len(names))
	for _, name := range names {
		quotedNames = append(quotedNames, "'"+escape(name)+"'")
	}
	nameFilter := strings.Join(quotedNames, ", ")
	tables, err := c.QueryJSON(ctx, fmt.Sprintf(`SELECT database, name, engine, ifNull(total_rows, 0) AS total_rows, partition_key, sorting_key, create_table_query
FROM system.tables
WHERE database = '%s' AND name IN (%s)
ORDER BY name
FORMAT JSONEachRow`, escape(c.SourceDatabase()), nameFilter))
	if err != nil {
		return nil, fmt.Errorf("discover baseline source tables: %w", err)
	}
	columns, err := c.QueryJSON(ctx, fmt.Sprintf(`SELECT database, table, name, type
FROM system.columns
WHERE database = '%s' AND table IN (%s)
ORDER BY table, position
FORMAT JSONEachRow`, escape(c.SourceDatabase()), nameFilter))
	if err != nil {
		return nil, fmt.Errorf("discover baseline source columns: %w", err)
	}
	columnsByTable := map[string][]domain.CatalogColumn{}
	for _, row := range columns {
		tableName := fmt.Sprint(row["table"])
		columnsByTable[tableName] = append(columnsByTable[tableName], domain.CatalogColumn{
			Name: fmt.Sprint(row["name"]), Type: fmt.Sprint(row["type"]),
		})
	}
	byName := make(map[string]domain.CatalogTable, len(tables))
	for _, row := range tables {
		name := fmt.Sprint(row["name"])
		byName[name] = domain.CatalogTable{
			Database: fmt.Sprint(row["database"]), Name: name, Category: "source", Engine: fmt.Sprint(row["engine"]),
			Rows: uint64Value(row["total_rows"]), PartitionKey: fmt.Sprint(row["partition_key"]),
			SortingKey: fmt.Sprint(row["sorting_key"]), DDL: fmt.Sprint(row["create_table_query"]),
			Columns: columnsByTable[name], ContextRegistered: true,
		}
	}
	ordered := make([]domain.CatalogTable, 0, len(byName))
	for _, name := range names {
		if table, ok := byName[name]; ok {
			ordered = append(ordered, table)
		}
	}
	return ordered, nil
}

func (c *Client) Catalog(ctx context.Context, baselineNames []string, graph domain.ContextVersion) (domain.DataCatalog, error) {
	catalog := domain.DataCatalog{SourceDatabase: c.SourceDatabase(), ControlDatabase: c.ControlDatabase(), GeneratedAt: time.Now().UTC()}
	if !c.enabled {
		return catalog, nil
	}
	rows, err := c.QueryJSON(ctx, fmt.Sprintf(`SELECT database, name, engine, ifNull(total_rows, 0) AS total_rows
FROM system.tables
WHERE database IN ('%s', '%s')
ORDER BY database, name
FORMAT JSONEachRow`, escape(c.SourceDatabase()), escape(c.ControlDatabase())))
	if err != nil {
		return domain.DataCatalog{}, fmt.Errorf("read live data catalog: %w", err)
	}
	baseline := make(map[string]bool, len(baselineNames))
	for _, name := range baselineNames {
		baseline[name] = true
	}
	registered := make(map[string]bool, len(graph.Nodes))
	for _, node := range graph.Nodes {
		if node.Type == "table" {
			registered[strings.TrimPrefix(node.Key, "table:")] = true
		}
	}
	governance := map[string]bool{
		"context_versions": true, "context_nodes": true, "context_edges": true, "context_conflicts": true,
		"schema_registry": true, "agent_runs": true, "context_evaluations": true, "context_diffs": true,
	}
	for _, row := range rows {
		database := fmt.Sprint(row["database"])
		name := fmt.Sprint(row["name"])
		category := "supporting"
		switch {
		case database == c.SourceDatabase() && baseline[name]:
			category = "source"
		case database == c.ControlDatabase() && governance[name]:
			category = "governance"
		case database == c.ControlDatabase() && versionedFeatureTable(name):
			category = "agent_created"
		}
		catalog.Tables = append(catalog.Tables, domain.CatalogTable{
			Database: database, Name: name, Category: category, Engine: fmt.Sprint(row["engine"]),
			Rows: uint64Value(row["total_rows"]), ContextRegistered: registered[database+"."+name],
		})
	}
	sort.SliceStable(catalog.Tables, func(i, j int) bool {
		order := map[string]int{"source": 0, "agent_created": 1, "governance": 2, "supporting": 3}
		left, right := catalog.Tables[i], catalog.Tables[j]
		if order[left.Category] != order[right.Category] {
			return order[left.Category] < order[right.Category]
		}
		if left.Database != right.Database {
			return left.Database < right.Database
		}
		return left.Name < right.Name
	})
	return catalog, nil
}

func (c *Client) Ping(ctx context.Context) error {
	if !c.enabled {
		return nil
	}
	_, err := c.query(ctx, "SELECT 1")
	return err
}

func (c *Client) Initialize(ctx context.Context) error {
	if !c.enabled {
		return nil
	}
	statements := []string{
		"CREATE DATABASE IF NOT EXISTS `" + c.controlDatabase + "`",
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.context_versions (version UInt32, parent_version Int32, feature LowCardinality(String), state LowCardinality(String), summary String, trace_id String, payload String, created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY version`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.context_nodes (context_version UInt32, node_key String, node_type LowCardinality(String), name String, status LowCardinality(String), confidence Float32, properties String, sources Array(String), created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY (context_version, node_key)`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.context_edges (context_version UInt32, from_key String, relation LowCardinality(String), to_key String, status LowCardinality(String), confidence Float32, properties String, created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY (context_version, from_key, relation, to_key)`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.context_conflicts (context_version UInt32, conflict_key String, severity LowCardinality(String), description String, declared String, observed String, resolution String, status LowCardinality(String), created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY (context_version, conflict_key)`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.schema_registry (feature String, context_version UInt32, schema_version UInt32, database String, table_name String, ddl String, status LowCardinality(String), trace_id String, created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY (feature, schema_version)`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.agent_runs (run_id String, feature String, stage LowCardinality(String), execution_mode LowCardinality(String), context_version UInt32, trace_id String, payload String, updated_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(updated_at) ORDER BY run_id`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.context_evaluations (run_id String, context_version UInt32, evaluation String, score Float32, passed UInt8, details String, trace_id String, created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY (run_id, evaluation)`, c.controlDatabase),
		fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.context_diffs (context_version UInt32, parent_version Int32, feature LowCardinality(String), kind LowCardinality(String), item_key String, payload String, created_at DateTime64(3, 'UTC')) ENGINE = ReplacingMergeTree(created_at) ORDER BY (context_version, kind, item_key)`, c.controlDatabase),
	}
	for _, statement := range statements {
		if _, err := c.query(ctx, statement); err != nil {
			return err
		}
	}
	return nil
}

func (c *Client) SaveRun(ctx context.Context, run domain.FeatureRun) error {
	if !c.enabled {
		return nil
	}
	payload, _ := json.Marshal(run)
	contextVersion := 0
	if run.Context != nil {
		contextVersion = run.Context.Version
	}
	return c.insertJSONRows(ctx, c.controlDatabase+".agent_runs", []map[string]any{{
		"run_id": run.ID, "feature": run.Input.Name, "stage": run.Stage, "execution_mode": run.ExecutionMode,
		"context_version": contextVersion, "trace_id": run.TraceID, "payload": string(payload), "updated_at": run.UpdatedAt,
	}})
}

// LoadControlPlane restores the latest durable representation of published
// contexts and agent runs. ReplacingMergeTree FINAL is required because every
// stage and analytics refresh writes a new version under the same key.
func (c *Client) LoadControlPlane(ctx context.Context) ([]domain.ContextVersion, []domain.FeatureRun, error) {
	if !c.enabled {
		return nil, nil, nil
	}
	contextRows, err := c.QueryJSON(ctx, fmt.Sprintf(`SELECT payload
FROM %s.context_versions FINAL
ORDER BY version
FORMAT JSONEachRow`, c.controlDatabase))
	if err != nil {
		return nil, nil, fmt.Errorf("load context versions: %w", err)
	}
	contexts := make([]domain.ContextVersion, 0, len(contextRows))
	for _, row := range contextRows {
		var graph domain.ContextVersion
		if err := json.Unmarshal([]byte(fmt.Sprint(row["payload"])), &graph); err != nil {
			return nil, nil, fmt.Errorf("decode context version payload: %w", err)
		}
		contexts = append(contexts, graph)
	}
	runRows, err := c.QueryJSON(ctx, fmt.Sprintf(`SELECT payload
FROM %s.agent_runs FINAL
ORDER BY updated_at DESC
FORMAT JSONEachRow`, c.controlDatabase))
	if err != nil {
		return nil, nil, fmt.Errorf("load agent runs: %w", err)
	}
	runs := make([]domain.FeatureRun, 0, len(runRows))
	for _, row := range runRows {
		var run domain.FeatureRun
		if err := json.Unmarshal([]byte(fmt.Sprint(row["payload"])), &run); err != nil {
			return nil, nil, fmt.Errorf("decode agent run payload: %w", err)
		}
		runs = append(runs, run)
	}
	return contexts, runs, nil
}

func (c *Client) SaveContext(ctx context.Context, graph domain.ContextVersion, schema domain.SchemaProposal, evaluations []domain.EvaluationResult, diff *domain.ContextDiff, runID string) error {
	if !c.enabled {
		return nil
	}
	if err := c.saveGraph(ctx, graph); err != nil {
		return err
	}
	if err := c.saveDiff(ctx, graph, diff); err != nil {
		return err
	}
	if err := c.insertJSONRows(ctx, c.controlDatabase+".schema_registry", []map[string]any{{
		"feature": graph.Feature, "context_version": graph.Version, "schema_version": schema.Version, "database": schema.Database, "table_name": schema.Table,
		"ddl": schema.DDL, "status": schema.Status, "trace_id": graph.TraceID, "created_at": graph.CreatedAt,
	}}); err != nil {
		return err
	}
	return c.SaveEvaluations(ctx, graph.Version, evaluations, graph.TraceID, runID)
}

// SaveEvaluations persists gate results keyed by run so rejected candidate
// versions leave a durable audit trail without entering context_versions.
func (c *Client) SaveEvaluations(ctx context.Context, contextVersion int, evaluations []domain.EvaluationResult, traceID, runID string) error {
	if !c.enabled {
		return nil
	}
	rows := make([]map[string]any, 0, len(evaluations))
	for _, evaluation := range evaluations {
		rows = append(rows, map[string]any{"run_id": runID, "context_version": contextVersion, "evaluation": evaluation.Name, "score": evaluation.Score, "passed": evaluation.Passed, "details": evaluation.Details, "trace_id": traceID, "created_at": time.Now().UTC()})
	}
	return c.insertJSONRows(ctx, c.controlDatabase+".context_evaluations", rows)
}

func (c *Client) SaveBaseline(ctx context.Context, graph domain.ContextVersion) error {
	if !c.enabled {
		return nil
	}
	if err := c.saveGraph(ctx, graph); err != nil {
		return err
	}
	rows := make([]map[string]any, 0)
	for _, node := range graph.Nodes {
		if node.Type != "table" || fmt.Sprint(node.Properties["category"]) != "source" {
			continue
		}
		database := fmt.Sprint(node.Properties["database"])
		if database == "" || node.Name == "" {
			continue
		}
		rows = append(rows, map[string]any{
			"feature": "baseline:" + node.Name, "context_version": graph.Version, "schema_version": 0,
			"database": database, "table_name": node.Name, "ddl": fmt.Sprint(node.Properties["ddl"]),
			"status": node.Status, "trace_id": graph.TraceID, "created_at": graph.CreatedAt,
		})
	}
	return c.insertJSONRows(ctx, c.controlDatabase+".schema_registry", rows)
}

// ResetControlPlane removes only FeatureLens governance state. Raw source
// tables and agent-created feature event tables are preserved so a baseline
// reset never destroys the evidence used by a later evolution run.
func (c *Client) ResetControlPlane(ctx context.Context, baseline domain.ContextVersion) error {
	if !c.enabled {
		return nil
	}
	tables := []string{
		"context_diffs",
		"context_evaluations",
		"agent_runs",
		"schema_registry",
		"context_edges",
		"context_nodes",
		"context_conflicts",
		"context_versions",
	}
	for _, table := range tables {
		statement := fmt.Sprintf("TRUNCATE TABLE IF EXISTS `%s`.`%s`", c.controlDatabase, table)
		if _, err := c.query(ctx, statement); err != nil {
			return fmt.Errorf("reset control table %s: %w", table, err)
		}
	}
	if err := c.SaveBaseline(ctx, baseline); err != nil {
		return fmt.Errorf("restore baseline context: %w", err)
	}
	return nil
}

func (c *Client) saveGraph(ctx context.Context, graph domain.ContextVersion) error {
	payload, _ := json.Marshal(graph)
	if err := c.insertJSONRows(ctx, c.controlDatabase+".context_versions", []map[string]any{{
		"version": graph.Version, "parent_version": graph.ParentVersion, "feature": graph.Feature, "state": graph.State,
		"summary": graph.Summary, "trace_id": graph.TraceID, "payload": string(payload), "created_at": graph.CreatedAt,
	}}); err != nil {
		return err
	}
	nodes := make([]map[string]any, 0, len(graph.Nodes))
	for _, node := range graph.Nodes {
		properties, _ := json.Marshal(node.Properties)
		nodes = append(nodes, map[string]any{"context_version": graph.Version, "node_key": node.Key, "node_type": node.Type, "name": node.Name, "status": node.Status, "confidence": node.Confidence, "properties": string(properties), "sources": node.Sources, "created_at": graph.CreatedAt})
	}
	if err := c.insertJSONRows(ctx, c.controlDatabase+".context_nodes", nodes); err != nil {
		return err
	}
	edges := make([]map[string]any, 0, len(graph.Edges))
	for _, edge := range graph.Edges {
		properties, _ := json.Marshal(edge.Properties)
		edges = append(edges, map[string]any{"context_version": graph.Version, "from_key": edge.From, "relation": edge.Relation, "to_key": edge.To, "status": edge.Status, "confidence": edge.Confidence, "properties": string(properties), "created_at": graph.CreatedAt})
	}
	if err := c.insertJSONRows(ctx, c.controlDatabase+".context_edges", edges); err != nil {
		return err
	}
	conflicts := make([]map[string]any, 0, len(graph.Conflicts))
	for _, conflict := range graph.Conflicts {
		conflicts = append(conflicts, map[string]any{"context_version": graph.Version, "conflict_key": conflict.Key, "severity": conflict.Severity, "description": conflict.Description, "declared": conflict.Declared, "observed": conflict.Observed, "resolution": conflict.Resolution, "status": conflict.Status, "created_at": graph.CreatedAt})
	}
	return c.insertJSONRows(ctx, c.controlDatabase+".context_conflicts", conflicts)
}

func (c *Client) saveDiff(ctx context.Context, graph domain.ContextVersion, diff *domain.ContextDiff) error {
	if diff == nil {
		return nil
	}
	rows := make([]map[string]any, 0)
	appendRow := func(kind, itemKey string, item any) {
		payload, _ := json.Marshal(item)
		rows = append(rows, map[string]any{
			"context_version": graph.Version, "parent_version": graph.ParentVersion, "feature": graph.Feature,
			"kind": kind, "item_key": itemKey, "payload": string(payload), "created_at": graph.CreatedAt,
		})
	}
	for _, node := range diff.AddedNodes {
		appendRow("added_node", node.Key, node)
	}
	for _, change := range diff.ChangedNodes {
		appendRow("changed_node", change.Key, change)
	}
	for _, key := range diff.RemovedNodeKeys {
		appendRow("removed_node", key, map[string]any{"key": key})
	}
	for _, edge := range diff.AddedEdges {
		appendRow("added_edge", edge.From+"|"+edge.Relation+"|"+edge.To, edge)
	}
	for _, conflict := range diff.AddedConflicts {
		appendRow("added_conflict", conflict.Key, conflict)
	}
	for _, change := range diff.ChangedConflicts {
		appendRow("changed_conflict", change.Key, change)
	}
	return c.insertJSONRows(ctx, c.controlDatabase+".context_diffs", rows)
}

// InsertReport describes what Apply actually did with the sample: how many
// rows landed, how many were quarantined, and why. Verification must compare
// against Inserted, not the profiled row count.
type InsertReport struct {
	Inserted    int
	Quarantined int
	Warnings    []string
}

func (r *InsertReport) warn(message string) {
	const detailed = 8
	if len(r.Warnings) < detailed {
		r.Warnings = append(r.Warnings, message)
		return
	}
	if len(r.Warnings) == detailed {
		r.Warnings = append(r.Warnings, "…further insert warnings suppressed")
	}
}

func (c *Client) Apply(ctx context.Context, proposal domain.SchemaProposal, ndjson string) (InsertReport, error) {
	report := InsertReport{}
	if !c.enabled {
		return report, nil
	}
	if _, err := c.query(ctx, "CREATE DATABASE IF NOT EXISTS `"+proposal.Database+"`"); err != nil {
		return report, err
	}
	if _, err := c.query(ctx, proposal.DDL); err != nil {
		return report, err
	}
	rows := make([]map[string]any, 0)
	ids := make([]string, 0)
	profiler.ForEachRow(ndjson, func(line int, source map[string]any) {
		flat := profiler.FlattenRow(source)
		row := map[string]any{}
		for _, column := range proposal.Columns {
			nullable := column.Nullable || strings.Contains(column.Type, "Nullable")
			value, ok := flat[column.SourcePath]
			if !ok || value == nil {
				if !nullable {
					report.Quarantined++
					report.warn(fmt.Sprintf("Quarantined row at line %d: required field %s is missing", line, column.SourcePath))
					return
				}
				row[column.Name] = nil
				continue
			}
			coerced, ok := coerceValue(value, column.Type)
			if !ok {
				if !nullable {
					report.Quarantined++
					report.warn(fmt.Sprintf("Quarantined row at line %d: field %s value %v cannot be stored as %s", line, column.SourcePath, value, column.Type))
					return
				}
				report.warn(fmt.Sprintf("Nulled field %s at line %d: value %v cannot be stored as %s", column.SourcePath, line, value, column.Type))
				row[column.Name] = nil
				continue
			}
			row[column.Name] = coerced
		}
		if id, ok := flat["id"].(string); ok && id != "" {
			ids = append(ids, id)
		}
		rows = append(rows, row)
	})
	report.Inserted = len(rows)
	if len(rows) == 0 {
		return report, nil
	}
	reuse, err := c.reuseVerifiedRows(ctx, proposal, ids, len(rows))
	if err != nil {
		return report, err
	}
	if reuse {
		return report, nil
	}
	var body bytes.Buffer
	for _, row := range rows {
		encoded, _ := json.Marshal(row)
		body.Write(encoded)
		body.WriteByte('\n')
	}
	insert := fmt.Sprintf("INSERT INTO `%s`.`%s` FORMAT JSONEachRow", proposal.Database, proposal.Table)
	_, err = c.send(ctx, insert, &body)
	return report, err
}

func (c *Client) Verify(ctx context.Context, proposal domain.SchemaProposal, expectedRows int) error {
	if !c.enabled {
		return nil
	}
	query := fmt.Sprintf("SELECT count() FROM `%s`.`%s` FORMAT TabSeparated", proposal.Database, proposal.Table)
	value, err := c.query(ctx, query)
	if err != nil {
		return err
	}
	count, err := strconv.Atoi(strings.TrimSpace(string(value)))
	if err != nil {
		return fmt.Errorf("parse verification count: %w", err)
	}
	if count != expectedRows {
		return fmt.Errorf("verification expected exactly %d rows, found %d", expectedRows, count)
	}
	return nil
}

func (c *Client) VerifyRetainedFeature(ctx context.Context, proposal domain.SchemaProposal, ndjson string, expectedRows int) error {
	if !c.enabled {
		return fmt.Errorf("ClickHouse runtime is not configured")
	}
	ids := []string{}
	profiler.ForEachRow(ndjson, func(_ int, row map[string]any) {
		if id, ok := row["id"].(string); ok && id != "" {
			ids = append(ids, id)
		}
	})
	reused, err := c.reuseVerifiedRows(ctx, proposal, ids, expectedRows)
	if err != nil {
		return err
	}
	if !reused {
		return fmt.Errorf("retained feature table %s.%s is empty", proposal.Database, proposal.Table)
	}
	return c.Verify(ctx, proposal, expectedRows)
}

func (c *Client) QueryJSON(ctx context.Context, query string) ([]map[string]any, error) {
	if !c.enabled {
		return nil, fmt.Errorf("ClickHouse runtime is not configured")
	}
	data, err := c.query(ctx, query)
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	rows := []map[string]any{}
	for {
		var row map[string]any
		if err := decoder.Decode(&row); err != nil {
			if err == io.EOF {
				break
			}
			return nil, err
		}
		rows = append(rows, row)
	}
	return rows, nil
}

// ReadExistingFeature rehydrates a retained typed feature table into the
// canonical event envelope expected by the profiler. This keeps raw rows
// server-side and lets a reset replay the real dataset instead of a UI sample.
func (c *Client) ReadExistingFeature(ctx context.Context, database, table string) (string, error) {
	if !c.enabled {
		return "", fmt.Errorf("ClickHouse runtime is not configured")
	}
	data, err := c.query(ctx, fmt.Sprintf("SELECT * FROM %s.%s ORDER BY %s, %s FORMAT JSONEachRow", quoteIdentifier(database), quoteIdentifier(table), quoteIdentifier("timestamp"), quoteIdentifier("id")))
	if err != nil {
		return "", fmt.Errorf("read retained feature table %s.%s: %w", database, table, err)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var output bytes.Buffer
	encoder := json.NewEncoder(&output)
	rows := 0
	for {
		var row map[string]any
		if err := decoder.Decode(&row); err != nil {
			if err == io.EOF {
				break
			}
			return "", fmt.Errorf("decode retained feature row: %w", err)
		}
		if event, ok := row["event_name"]; ok {
			row["event"] = event
			delete(row, "event_name")
		}
		if err := encoder.Encode(row); err != nil {
			return "", fmt.Errorf("encode retained feature row: %w", err)
		}
		rows++
	}
	if rows == 0 {
		return "", fmt.Errorf("retained feature table %s.%s is empty", database, table)
	}
	return strings.TrimSpace(output.String()), nil
}

// ExistingSchema returns the physical ClickHouse contract already verified for
// a retained dataset, preventing a replay from registering a schema inferred
// from serialized values rather than the authoritative catalog.
func (c *Client) ExistingSchema(ctx context.Context, database, table string, version int) (domain.SchemaProposal, error) {
	if !c.enabled {
		return domain.SchemaProposal{}, fmt.Errorf("ClickHouse runtime is not configured")
	}
	columnRows, err := c.QueryJSON(ctx, fmt.Sprintf("DESCRIBE TABLE %s.%s FORMAT JSONEachRow", quoteIdentifier(database), quoteIdentifier(table)))
	if err != nil {
		return domain.SchemaProposal{}, fmt.Errorf("describe retained feature table: %w", err)
	}
	columns := make([]domain.ColumnProposal, 0, len(columnRows))
	for _, row := range columnRows {
		name, _ := row["name"].(string)
		columnType, _ := row["type"].(string)
		if name == "" || columnType == "" {
			continue
		}
		sourcePath := name
		if name == "event_name" {
			sourcePath = "event"
		}
		columns = append(columns, domain.ColumnProposal{Name: name, SourcePath: sourcePath, Type: columnType, Nullable: strings.Contains(columnType, "Nullable(")})
	}
	if len(columns) == 0 {
		return domain.SchemaProposal{}, fmt.Errorf("retained feature table %s.%s has no columns", database, table)
	}
	metadata, err := c.QueryJSON(ctx, fmt.Sprintf("SELECT partition_key, sorting_key FROM system.tables WHERE database = '%s' AND name = '%s' FORMAT JSONEachRow", escape(database), escape(table)))
	if err != nil || len(metadata) != 1 {
		if err == nil {
			err = fmt.Errorf("catalog returned %d rows", len(metadata))
		}
		return domain.SchemaProposal{}, fmt.Errorf("inspect retained feature table keys: %w", err)
	}
	ddlBytes, err := c.query(ctx, fmt.Sprintf("SHOW CREATE TABLE %s.%s", quoteIdentifier(database), quoteIdentifier(table)))
	if err != nil {
		return domain.SchemaProposal{}, fmt.Errorf("read retained feature DDL: %w", err)
	}
	partition := fmt.Sprint(metadata[0]["partition_key"])
	orderBy := splitExpressions(fmt.Sprint(metadata[0]["sorting_key"]))
	return domain.SchemaProposal{
		Version: version, Database: database, Table: table, DDL: strings.TrimSpace(string(ddlBytes)), Columns: columns,
		PartitionBy: partition, OrderBy: orderBy, Status: "proposed",
		Rationale: []string{
			"Reused the authoritative schema from the ClickHouse catalog for this retained feature dataset.",
			"Verified event IDs and row count must match before the existing table can be reused.",
			"No rows are appended during a retained-table replay.",
		},
	}, nil
}

func (c *Client) reuseVerifiedRows(ctx context.Context, proposal domain.SchemaProposal, ids []string, expectedRows int) (bool, error) {
	countQuery := fmt.Sprintf("SELECT count() FROM `%s`.`%s` FORMAT TabSeparated", proposal.Database, proposal.Table)
	data, err := c.query(ctx, countQuery)
	if err != nil {
		return false, err
	}
	count, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return false, fmt.Errorf("parse existing row count: %w", err)
	}
	if count == 0 {
		return false, nil
	}
	if count != expectedRows || len(ids) != expectedRows {
		return false, fmt.Errorf("refusing to append into non-empty %s.%s: existing rows=%d, incoming rows=%d; create a new schema version", proposal.Database, proposal.Table, count, expectedRows)
	}
	sortedIDs := append([]string{}, ids...)
	sort.Strings(sortedIDs)
	hash := sha256.Sum256([]byte(strings.Join(sortedIDs, "\n")))
	expectedHash := strings.ToUpper(hex.EncodeToString(hash[:]))
	fingerprintQuery := fmt.Sprintf(`SELECT uniqExact(id) AS unique_ids, hex(SHA256(arrayStringConcat(arraySort(groupArray(id)), '\n'))) AS id_fingerprint FROM %s.%s FORMAT JSONEachRow`, quoteIdentifier(proposal.Database), quoteIdentifier(proposal.Table))
	rows, err := c.QueryJSON(ctx, fingerprintQuery)
	if err != nil || len(rows) != 1 {
		if err == nil {
			err = fmt.Errorf("unexpected fingerprint result")
		}
		return false, err
	}
	uniqueIDs, err := strconv.Atoi(fmt.Sprint(rows[0]["unique_ids"]))
	if err != nil || uniqueIDs != expectedRows || !strings.EqualFold(fmt.Sprint(rows[0]["id_fingerprint"]), expectedHash) {
		return false, fmt.Errorf("refusing to reuse %s.%s: incoming event IDs do not match the verified existing dataset", proposal.Database, proposal.Table)
	}
	return true, nil
}

func (c *Client) Aggregate(ctx context.Context, proposal domain.SchemaProposal, firstEvent, lastEvent, grainColumn string) (map[string]any, string, error) {
	if !c.enabled {
		return nil, "", fmt.Errorf("ClickHouse runtime is not configured")
	}
	query := fmt.Sprintf(`SELECT
    uniqExactIf(%s, event_name = '%s') AS entrants,
    uniqExactIf(%s, event_name = '%s') AS completions,
    round(completions / nullIf(entrants, 0), 4) AS completion_rate
FROM %s.%s
FORMAT JSONEachRow`, quoteIdentifier(grainColumn), escape(firstEvent), quoteIdentifier(grainColumn), escape(lastEvent), proposal.Database, proposal.Table)
	data, err := c.query(ctx, query)
	if err != nil {
		return nil, query, err
	}
	var result map[string]any
	if err := json.Unmarshal(bytes.TrimSpace(data), &result); err != nil {
		return nil, query, err
	}
	return result, query, nil
}

func (c *Client) query(ctx context.Context, query string) ([]byte, error) {
	return c.send(ctx, query, nil)
}

func (c *Client) send(ctx context.Context, query string, body *bytes.Buffer) ([]byte, error) {
	endpoint, err := url.Parse(c.endpoint)
	if err != nil {
		return nil, err
	}
	values := endpoint.Query()
	values.Set("query", query)
	endpoint.RawQuery = values.Encode()
	var requestBody *bytes.Reader
	if body == nil {
		requestBody = bytes.NewReader(nil)
	} else {
		requestBody = bytes.NewReader(body.Bytes())
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.String(), requestBody)
	if err != nil {
		return nil, err
	}
	req.SetBasicAuth(c.user, c.password)
	response, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	var result bytes.Buffer
	_, _ = result.ReadFrom(response.Body)
	if response.StatusCode >= 300 {
		return nil, fmt.Errorf("ClickHouse returned %s: %s", response.Status, strings.TrimSpace(result.String()))
	}
	return result.Bytes(), nil
}

func (c *Client) insertJSONRows(ctx context.Context, table string, rows []map[string]any) error {
	if len(rows) == 0 {
		return nil
	}
	var body bytes.Buffer
	for _, row := range rows {
		encoded, err := json.Marshal(row)
		if err != nil {
			return err
		}
		body.Write(encoded)
		body.WriteByte('\n')
	}
	_, err := c.send(ctx, "INSERT INTO "+table+" FORMAT JSONEachRow", &body)
	return err
}

// coerceValue converts a decoded JSON value into a shape ClickHouse accepts
// for the column type, so a single wrong-typed value degrades to one
// quarantined row or nulled field instead of failing the whole insert batch.
// The second return is false when no safe conversion exists.
func coerceValue(value any, columnType string) (any, bool) {
	switch {
	case strings.Contains(columnType, "DateTime"):
		switch typed := value.(type) {
		case string:
			return strings.ReplaceAll(typed, "T", " "), true
		case float64:
			return typed, true
		}
		return nil, false
	case strings.Contains(columnType, "UInt8"):
		switch typed := value.(type) {
		case bool:
			if typed {
				return 1, true
			}
			return 0, true
		case float64:
			if typed == 0 || typed == 1 {
				return int(typed), true
			}
		case string:
			if flag, err := strconv.ParseBool(strings.TrimSpace(typed)); err == nil {
				if flag {
					return 1, true
				}
				return 0, true
			}
		}
		return nil, false
	case strings.Contains(columnType, "Int"):
		switch typed := value.(type) {
		case float64:
			if math.Trunc(typed) == typed {
				return int64(typed), true
			}
		case string:
			if parsed, err := strconv.ParseInt(strings.TrimSpace(typed), 10, 64); err == nil {
				return parsed, true
			}
		}
		return nil, false
	case strings.Contains(columnType, "Float"):
		switch typed := value.(type) {
		case float64:
			return typed, true
		case string:
			if parsed, err := strconv.ParseFloat(strings.TrimSpace(typed), 64); err == nil {
				return parsed, true
			}
		}
		return nil, false
	case strings.Contains(columnType, "String"):
		switch typed := value.(type) {
		case string:
			return typed, true
		case bool:
			return strconv.FormatBool(typed), true
		case float64:
			if math.Trunc(typed) == typed {
				return strconv.FormatInt(int64(typed), 10), true
			}
			return strconv.FormatFloat(typed, 'f', -1, 64), true
		}
		encoded, err := json.Marshal(value)
		if err != nil {
			return nil, false
		}
		return string(encoded), true
	}
	return value, true
}

func splitExpressions(value string) []string {
	result := []string{}
	start := 0
	depth := 0
	for index, character := range value {
		switch character {
		case '(':
			depth++
		case ')':
			if depth > 0 {
				depth--
			}
		case ',':
			if depth == 0 {
				if expression := strings.TrimSpace(value[start:index]); expression != "" {
					result = append(result, expression)
				}
				start = index + 1
			}
		}
	}
	if expression := strings.TrimSpace(value[start:]); expression != "" {
		result = append(result, expression)
	}
	return result
}

func envDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func envBool(key string, fallback bool) bool {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.ParseBool(value)
	return err == nil && parsed
}

func uint64Value(value any) uint64 {
	parsed, err := strconv.ParseUint(fmt.Sprint(value), 10, 64)
	if err != nil {
		return 0
	}
	return parsed
}

func versionedFeatureTable(name string) bool {
	marker := strings.LastIndex(name, "_events_v")
	if marker < 1 || marker+len("_events_v") >= len(name) {
		return false
	}
	_, err := strconv.Atoi(name[marker+len("_events_v"):])
	return err == nil
}

func escape(value string) string { return strings.ReplaceAll(value, "'", "''") }

func quoteIdentifier(value string) string { return "`" + strings.ReplaceAll(value, "`", "") + "`" }
