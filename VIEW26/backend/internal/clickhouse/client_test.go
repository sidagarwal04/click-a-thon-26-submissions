package clickhouse

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"sort"
	"strings"
	"sync"
	"testing"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
)

func TestApplyReusesExactExistingDatasetWithoutDuplicateInsert(t *testing.T) {
	ids := []string{"b", "a"}
	sorted := append([]string{}, ids...)
	sort.Strings(sorted)
	hash := sha256.Sum256([]byte(strings.Join(sorted, "\n")))
	fingerprint := strings.ToUpper(hex.EncodeToString(hash[:]))
	inserted := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("query")
		switch {
		case strings.HasPrefix(query, "CREATE"):
			w.WriteHeader(http.StatusOK)
		case strings.Contains(query, "SELECT count()"):
			_, _ = fmt.Fprintln(w, "2")
		case strings.Contains(query, "id_fingerprint"):
			_, _ = fmt.Fprintf(w, "{\"unique_ids\":2,\"id_fingerprint\":%q}\n", fingerprint)
		case strings.HasPrefix(query, "INSERT"):
			inserted = true
			w.WriteHeader(http.StatusOK)
		default:
			t.Fatalf("unexpected query: %s", query)
		}
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", http: server.Client(), enabled: true}
	proposal := domain.SchemaProposal{
		Database: "featurelens", Table: "events", DDL: "CREATE TABLE IF NOT EXISTS featurelens.events (id String) ENGINE=MergeTree ORDER BY id",
		Columns: []domain.ColumnProposal{{Name: "id", SourcePath: "id", Type: "String"}},
	}
	report, err := client.Apply(context.Background(), proposal, "{\"id\":\"a\"}\n{\"id\":\"b\"}")
	if err != nil {
		t.Fatal(err)
	}
	if report.Inserted != 2 {
		t.Fatalf("expected 2 rows reported, got %#v", report)
	}
	if inserted {
		t.Fatal("exact existing dataset was inserted a second time")
	}
}

func TestLoadControlPlaneDecodesLatestDurablePayloads(t *testing.T) {
	graph := domain.ContextVersion{Version: 3, ParentVersion: 2, Feature: "status_sharing", State: "published"}
	run := domain.FeatureRun{ID: "run_status", Input: domain.FeatureInput{Name: "Status Sharing"}, Stage: domain.StageCompleted}
	graphPayload, _ := json.Marshal(graph)
	runPayload, _ := json.Marshal(run)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("query")
		switch {
		case strings.Contains(query, ".context_versions FINAL"):
			encoded, _ := json.Marshal(map[string]any{"payload": string(graphPayload)})
			_, _ = fmt.Fprintln(w, string(encoded))
		case strings.Contains(query, ".agent_runs FINAL"):
			encoded, _ := json.Marshal(map[string]any{"payload": string(runPayload)})
			_, _ = fmt.Fprintln(w, string(encoded))
		default:
			t.Fatalf("unexpected query: %s", query)
		}
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", controlDatabase: "featurelens", http: server.Client(), enabled: true}
	contexts, runs, err := client.LoadControlPlane(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(contexts) != 1 || contexts[0].Version != 3 || len(runs) != 1 || runs[0].ID != run.ID {
		t.Fatalf("unexpected restored control plane: contexts=%#v runs=%#v", contexts, runs)
	}
}

func TestApplyQuarantinesRowsInsteadOfFailingBatch(t *testing.T) {
	var insertBody string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("query")
		switch {
		case strings.HasPrefix(query, "CREATE"):
			w.WriteHeader(http.StatusOK)
		case strings.Contains(query, "SELECT count()"):
			_, _ = fmt.Fprintln(w, "0")
		case strings.HasPrefix(query, "INSERT"):
			body, _ := io.ReadAll(r.Body)
			insertBody = string(body)
			w.WriteHeader(http.StatusOK)
		default:
			t.Fatalf("unexpected query: %s", query)
		}
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", http: server.Client(), enabled: true}
	proposal := domain.SchemaProposal{
		Database: "featurelens", Table: "events", DDL: "CREATE TABLE IF NOT EXISTS featurelens.events (id String, amount Nullable(Int64)) ENGINE=MergeTree ORDER BY id",
		Columns: []domain.ColumnProposal{
			{Name: "id", SourcePath: "id", Type: "String"},
			{Name: "amount", SourcePath: "amount", Type: "Nullable(Int64)", Nullable: true},
		},
	}
	ndjson := `{"id":"a","amount":42}
{"id":"b","amount":"17"}
{"id":"c","amount":"n/a"}
{"amount":5}
this line is not JSON`
	report, err := client.Apply(context.Background(), proposal, ndjson)
	if err != nil {
		t.Fatal(err)
	}
	if report.Inserted != 3 || report.Quarantined != 1 {
		t.Fatalf("unexpected report: %#v", report)
	}
	rows := strings.Split(strings.TrimSpace(insertBody), "\n")
	if len(rows) != 3 {
		t.Fatalf("expected 3 inserted rows, got %d: %q", len(rows), insertBody)
	}
	if !strings.Contains(insertBody, `"amount":17`) {
		t.Fatalf("numeric string was not coerced to Int64: %q", insertBody)
	}
	if !strings.Contains(insertBody, `"id":"c","amount":null`) && !strings.Contains(insertBody, `"amount":null,"id":"c"`) {
		t.Fatalf("uncoercible nullable value was not nulled: %q", insertBody)
	}
	quarantineWarned := false
	for _, warning := range report.Warnings {
		if strings.Contains(warning, "required field id is missing") {
			quarantineWarned = true
		}
	}
	if !quarantineWarned {
		t.Fatalf("quarantine reason missing from warnings: %#v", report.Warnings)
	}
}

func TestResetControlPlaneNeverTruncatesEvidenceTables(t *testing.T) {
	var mu sync.Mutex
	queries := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		queries = append(queries, r.URL.Query().Get("query"))
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", controlDatabase: "featurelens_control", http: server.Client(), enabled: true}
	if err := client.ResetControlPlane(context.Background(), agent.BaselineContext()); err != nil {
		t.Fatal(err)
	}

	mu.Lock()
	defer mu.Unlock()
	truncated := 0
	for _, query := range queries {
		if strings.HasPrefix(query, "TRUNCATE TABLE") {
			truncated++
			if strings.Contains(query, "_events_v") || strings.Contains(query, "`atlys`") {
				t.Fatalf("reset targeted evidence data: %s", query)
			}
		}
	}
	if truncated != 8 {
		t.Fatalf("expected eight control tables to be truncated, got %d: %#v", truncated, queries)
	}
}

func TestReadExistingFeatureRestoresCanonicalEventEnvelope(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasPrefix(r.URL.Query().Get("query"), "SELECT * FROM") {
			t.Fatalf("unexpected query: %s", r.URL.Query().Get("query"))
		}
		_, _ = fmt.Fprintln(w, `{"event_name":"checkout_shown","id":"a","timestamp":"2026-08-01 08:00:00.000"}`)
		_, _ = fmt.Fprintln(w, `{"event_name":"checkout_completed","id":"b","timestamp":"2026-08-01 08:01:00.000"}`)
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", http: server.Client(), enabled: true}
	ndjson, err := client.ReadExistingFeature(context.Background(), "featurelens", "checkout_events_v1")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(ndjson, "event_name") || !strings.Contains(ndjson, `"event":"checkout_shown"`) {
		t.Fatalf("event envelope was not restored: %s", ndjson)
	}
}

func TestExistingSchemaUsesAuthoritativeClickHouseCatalog(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("query")
		switch {
		case strings.HasPrefix(query, "DESCRIBE TABLE"):
			_, _ = fmt.Fprintln(w, `{"name":"event_name","type":"LowCardinality(String)"}`)
			_, _ = fmt.Fprintln(w, `{"name":"id","type":"String"}`)
			_, _ = fmt.Fprintln(w, `{"name":"timestamp","type":"DateTime64(3, 'UTC')"}`)
			_, _ = fmt.Fprintln(w, `{"name":"application_id","type":"Nullable(String)"}`)
		case strings.Contains(query, "FROM system.tables"):
			_, _ = fmt.Fprintln(w, `{"partition_key":"toYYYYMM(timestamp)","sorting_key":"toDate(timestamp), event_name, ifNull(application_id, ''), timestamp"}`)
		case strings.HasPrefix(query, "SHOW CREATE TABLE"):
			_, _ = fmt.Fprintln(w, "CREATE TABLE featurelens.checkout_events_v1 (...) ENGINE = MergeTree")
		default:
			t.Fatalf("unexpected query: %s", query)
		}
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", http: server.Client(), enabled: true}
	schema, err := client.ExistingSchema(context.Background(), "featurelens", "checkout_events_v1", 1)
	if err != nil {
		t.Fatal(err)
	}
	if len(schema.Columns) != 4 || schema.Columns[0].SourcePath != "event" {
		t.Fatalf("unexpected catalog columns: %#v", schema.Columns)
	}
	if len(schema.OrderBy) != 4 {
		t.Fatalf("sorting key was not split safely: %#v", schema.OrderBy)
	}
	if !strings.Contains(schema.DDL, "CREATE TABLE") {
		t.Fatalf("physical DDL missing: %q", schema.DDL)
	}
}

func TestDiscoverSourceCatalogUsesTablesAndColumns(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query := r.URL.Query().Get("query")
		switch {
		case strings.Contains(query, "FROM system.tables"):
			_, _ = fmt.Fprintln(w, `{"database":"atlys","name":"application_started","engine":"MergeTree","total_rows":154413,"partition_key":"","sorting_key":"id, timestamp","create_table_query":"CREATE TABLE atlys.application_started"}`)
			_, _ = fmt.Fprintln(w, `{"database":"atlys","name":"purchase_completed","engine":"MergeTree","total_rows":7054,"partition_key":"","sorting_key":"id, timestamp","create_table_query":"CREATE TABLE atlys.purchase_completed"}`)
		case strings.Contains(query, "FROM system.columns"):
			_, _ = fmt.Fprintln(w, `{"database":"atlys","table":"application_started","name":"id","type":"String"}`)
			_, _ = fmt.Fprintln(w, `{"database":"atlys","table":"purchase_completed","name":"id","type":"String"}`)
		default:
			t.Fatalf("unexpected query: %s", query)
		}
	}))
	defer server.Close()

	client := &Client{endpoint: server.URL + "/", user: "test", sourceDatabase: "atlys", http: server.Client(), enabled: true}
	tables, err := client.DiscoverSourceCatalog(context.Background(), []string{"application_started", "purchase_completed"})
	if err != nil {
		t.Fatal(err)
	}
	if len(tables) != 2 || tables[0].Name != "application_started" || tables[0].Rows != 154413 {
		t.Fatalf("unexpected source catalog: %#v", tables)
	}
	if len(tables[1].Columns) != 1 || tables[1].Columns[0].Name != "id" {
		t.Fatalf("source columns were not attached: %#v", tables[1])
	}
}
