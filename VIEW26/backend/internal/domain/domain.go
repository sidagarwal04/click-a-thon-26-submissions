package domain

import "time"

type RunStage string

const (
	StageReceived          RunStage = "received"
	StageProfiling         RunStage = "profiling"
	StageProfiled          RunStage = "profiled"
	StageSchemaProposed    RunStage = "schema_proposed"
	StageSchemaValidated   RunStage = "schema_validated"
	StageAwaitingApproval  RunStage = "awaiting_approval"
	StageSchemaExecuting   RunStage = "schema_executing"
	StageSchemaVerified    RunStage = "schema_verified"
	StageContextCandidate  RunStage = "context_candidate"
	StageContextPublished  RunStage = "context_published"
	StageAnalyticsComplete RunStage = "analytics_complete"
	StageEvaluated         RunStage = "evaluated"
	StageCompleted         RunStage = "completed"
	StageFailed            RunStage = "failed"
)

type FeatureInput struct {
	Name            string `json:"name"`
	Slug            string `json:"slug"`
	SchemaVersion   int    `json:"schema_version,omitempty"`
	SpecMarkdown    string `json:"spec_markdown"`
	EventsNDJSON    string `json:"events_ndjson"`
	UseExistingData bool   `json:"use_existing_data,omitempty"`
	Role            string `json:"role"`
	AutoApprove     bool   `json:"auto_approve"`
}

type FieldProfile struct {
	Path           string   `json:"path"`
	ColumnName     string   `json:"column_name"`
	ObservedKinds  []string `json:"observed_kinds"`
	ClickHouseType string   `json:"clickhouse_type"`
	Nullable       bool     `json:"nullable"`
	Seen           int      `json:"seen"`
	Nulls          int      `json:"nulls"`
	Distinct       int      `json:"distinct"`
	Examples       []string `json:"examples,omitempty"`
}

type EventProfile struct {
	Rows        int            `json:"rows"`
	SkippedRows int            `json:"skipped_rows,omitempty"`
	EventCounts map[string]int `json:"event_counts"`
	EventOrder  []string       `json:"event_order"`
	Fields      []FieldProfile `json:"fields"`
	Warnings    []string       `json:"warnings"`
}

type ColumnProposal struct {
	Name       string `json:"name"`
	SourcePath string `json:"source_path"`
	Type       string `json:"type"`
	Nullable   bool   `json:"nullable"`
}

type SchemaProposal struct {
	Version          int              `json:"version"`
	Database         string           `json:"database"`
	Table            string           `json:"table"`
	DDL              string           `json:"ddl"`
	Columns          []ColumnProposal `json:"columns"`
	PartitionBy      string           `json:"partition_by"`
	OrderBy          []string         `json:"order_by"`
	TTL              string           `json:"ttl,omitempty"`
	MaterializedView string           `json:"materialized_view,omitempty"`
	Rationale        []string         `json:"rationale"`
	Status           string           `json:"status"`
}

type ValidationCheck struct {
	Name    string `json:"name"`
	Passed  bool   `json:"passed"`
	Details string `json:"details"`
}

type SchemaValidation struct {
	Passed bool              `json:"passed"`
	Checks []ValidationCheck `json:"checks"`
}

type ContextNode struct {
	Key        string         `json:"key"`
	Type       string         `json:"type"`
	Name       string         `json:"name"`
	Properties map[string]any `json:"properties,omitempty"`
	Status     string         `json:"status"`
	Confidence float64        `json:"confidence"`
	Sources    []string       `json:"sources,omitempty"`
}

type ContextEdge struct {
	From       string         `json:"from"`
	Relation   string         `json:"relation"`
	To         string         `json:"to"`
	Properties map[string]any `json:"properties,omitempty"`
	Status     string         `json:"status"`
	Confidence float64        `json:"confidence"`
}

type ContextConflict struct {
	Key         string `json:"key"`
	Severity    string `json:"severity"`
	Description string `json:"description"`
	Declared    string `json:"declared"`
	Observed    string `json:"observed"`
	Resolution  string `json:"resolution,omitempty"`
	Status      string `json:"status"`
}

type NodeChange struct {
	Key    string      `json:"key"`
	Before ContextNode `json:"before"`
	After  ContextNode `json:"after"`
}

type ConflictChange struct {
	Key    string          `json:"key"`
	Before ContextConflict `json:"before"`
	After  ContextConflict `json:"after"`
}

// ContextDiff is the structured delta between two immutable context versions.
// It powers the changelog visualization and the regression-preservation gate:
// a non-empty RemovedNodeKeys means the child dropped part of the parent graph.
type ContextDiff struct {
	FromVersion      int               `json:"from_version"`
	ToVersion        int               `json:"to_version"`
	Feature          string            `json:"feature"`
	AddedNodes       []ContextNode     `json:"added_nodes"`
	ChangedNodes     []NodeChange      `json:"changed_nodes,omitempty"`
	RemovedNodeKeys  []string          `json:"removed_node_keys,omitempty"`
	AddedEdges       []ContextEdge     `json:"added_edges"`
	AddedConflicts   []ContextConflict `json:"added_conflicts,omitempty"`
	ChangedConflicts []ConflictChange  `json:"changed_conflicts,omitempty"`
	NodeCountBefore  int               `json:"node_count_before"`
	NodeCountAfter   int               `json:"node_count_after"`
	EdgeCountBefore  int               `json:"edge_count_before"`
	EdgeCountAfter   int               `json:"edge_count_after"`
}

type ContextVersion struct {
	Version        int               `json:"version"`
	ParentVersion  int               `json:"parent_version"`
	Feature        string            `json:"feature"`
	State          string            `json:"state"`
	SchemaVersions []string          `json:"schema_versions"`
	Nodes          []ContextNode     `json:"nodes"`
	Edges          []ContextEdge     `json:"edges"`
	Conflicts      []ContextConflict `json:"conflicts"`
	Summary        string            `json:"summary"`
	TraceID        string            `json:"trace_id,omitempty"`
	CreatedAt      time.Time         `json:"created_at"`
}

type CatalogColumn struct {
	Name string `json:"name"`
	Type string `json:"type"`
}

type CatalogTable struct {
	Database          string          `json:"database"`
	Name              string          `json:"name"`
	Category          string          `json:"category"`
	Engine            string          `json:"engine"`
	Rows              uint64          `json:"rows"`
	PartitionKey      string          `json:"partition_key,omitempty"`
	SortingKey        string          `json:"sorting_key,omitempty"`
	DDL               string          `json:"ddl,omitempty"`
	Columns           []CatalogColumn `json:"columns,omitempty"`
	ContextRegistered bool            `json:"context_registered"`
}

type DataCatalog struct {
	SourceDatabase  string         `json:"source_database"`
	ControlDatabase string         `json:"control_database"`
	Tables          []CatalogTable `json:"tables"`
	GeneratedAt     time.Time      `json:"generated_at"`
}

type AnalysisContract struct {
	Role             string   `json:"role"`
	Intent           string   `json:"intent"`
	Playbook         string   `json:"playbook"`
	Answerability    string   `json:"answerability"`
	Feature          string   `json:"feature"`
	Question         string   `json:"question"`
	ContextVersion   int      `json:"context_version"`
	SchemaVersions   []string `json:"schema_versions"`
	Grain            string   `json:"grain"`
	Metrics          []string `json:"metrics"`
	Guardrails       []string `json:"guardrails"`
	Dimensions       []string `json:"dimensions"`
	KnownIssues      []string `json:"known_issues"`
	AllowedTables    []string `json:"allowed_tables"`
	OperatingRules   []string `json:"operating_rules"`
	RequiredEvidence []string `json:"required_evidence"`
	Limitations      []string `json:"limitations,omitempty"`
	RequestedOutputs []string `json:"requested_outputs"`
}

type Insight struct {
	Headline          string            `json:"headline"`
	Summary           string            `json:"summary"`
	Why               string            `json:"why"`
	Confidence        float64           `json:"confidence"`
	RecommendedAction string            `json:"recommended_action"`
	KeyFindings       []KeyFinding      `json:"key_findings,omitempty"`
	Evidence          map[string]any    `json:"evidence"`
	SQL               string            `json:"sql"`
	ContextVersion    int               `json:"context_version"`
	SchemaVersion     string            `json:"schema_version"`
	TraceID           string            `json:"trace_id,omitempty"`
	Provenance        InsightProvenance `json:"provenance"`
	Trace             *AnalysisTrace    `json:"trace,omitempty"`
}

// KeyFinding is one ranked observation inside an insight: what was seen, why it
// matters to the PM, and the evidence anchor it is grounded in. An insight
// answering an open analytical question ("surface the most important issues")
// carries several of these so the answer reads as a prioritized list, not a
// single headline.
type KeyFinding struct {
	Point    string `json:"point"`              // the observation, quantified from evidence
	Why      string `json:"why"`                // why this specific finding matters to the PM
	Evidence string `json:"evidence,omitempty"` // the metric/segment/stage it is grounded in
	Severity string `json:"severity,omitempty"` // high | medium | low, for ordering and emphasis
}

type AnalysisTrace struct {
	TraceID        string              `json:"trace_id"`
	Role           string              `json:"role"`
	Feature        string              `json:"feature"`
	Question       string              `json:"question"`
	ContextVersion int                 `json:"context_version"`
	SchemaVersion  string              `json:"schema_version"`
	DatasetRows    int                 `json:"dataset_rows"`
	StartedAt      time.Time           `json:"started_at"`
	CompletedAt    time.Time           `json:"completed_at"`
	Steps          []AnalysisTraceStep `json:"steps"`
}

type AnalysisTraceStep struct {
	ID            string         `json:"id"`
	ObservationID string         `json:"observation_id,omitempty"`
	Kind          string         `json:"kind"`
	Status        string         `json:"status"`
	DurationMS    int64          `json:"duration_ms"`
	Input         map[string]any `json:"input,omitempty"`
	Output        any            `json:"output,omitempty"`
	Error         string         `json:"error,omitempty"`
}

type InsightProvenance struct {
	Generator     string `json:"generator"`
	Status        string `json:"status"`
	Provider      string `json:"provider,omitempty"`
	Model         string `json:"model,omitempty"`
	PromptVersion string `json:"prompt_version"`
	Reason        string `json:"reason,omitempty"`
}

type AnalyticsKPI struct {
	Key            string  `json:"key"`
	Label          string  `json:"label"`
	Value          float64 `json:"value"`
	FormattedValue string  `json:"formatted_value"`
	Unit           string  `json:"unit,omitempty"`
	Direction      string  `json:"direction,omitempty"`
	Confidence     float64 `json:"confidence"`
	SampleSize     float64 `json:"sample_size,omitempty"`
	SourcePlaybook string  `json:"source_playbook,omitempty"`
	TraceID        string  `json:"trace_id,omitempty"`
}

type AnalyticsPoint struct {
	Label      string  `json:"label"`
	Value      float64 `json:"value"`
	SampleSize float64 `json:"sample_size,omitempty"`
}

type AnalyticsSeries struct {
	Key    string           `json:"key"`
	Label  string           `json:"label"`
	Points []AnalyticsPoint `json:"points"`
}

type AnalyticsChart struct {
	Key      string            `json:"key"`
	Type     string            `json:"type"`
	Title    string            `json:"title"`
	Subtitle string            `json:"subtitle"`
	Unit     string            `json:"unit,omitempty"`
	Series   []AnalyticsSeries `json:"series"`
	SQL      string            `json:"sql"`
	TraceID  string            `json:"trace_id,omitempty"`
}

type RankedInsight struct {
	Rank              int     `json:"rank"`
	Intent            string  `json:"intent"`
	Headline          string  `json:"headline"`
	Summary           string  `json:"summary"`
	Why               string  `json:"why"`
	RecommendedAction string  `json:"recommended_action"`
	Confidence        float64 `json:"confidence"`
	Playbook          string  `json:"playbook"`
	TraceID           string  `json:"trace_id,omitempty"`
}

type AnalyticsEvidence struct {
	ID         string           `json:"id"`
	Status     string           `json:"status"`
	SQL        string           `json:"sql"`
	Rows       []map[string]any `json:"rows,omitempty"`
	DurationMS int64            `json:"duration_ms"`
	Error      string           `json:"error,omitempty"`
}

type FeatureAnalyticsBundle struct {
	Feature        string              `json:"feature"`
	Role           string              `json:"role"`
	Status         string              `json:"status"`
	ContextVersion int                 `json:"context_version"`
	SchemaVersion  string              `json:"schema_version"`
	GeneratedAt    time.Time           `json:"generated_at"`
	KPIs           []AnalyticsKPI      `json:"kpis"`
	Charts         []AnalyticsChart    `json:"charts"`
	Insights       []RankedInsight     `json:"insights"`
	Playbooks      []string            `json:"playbooks"`
	Evidence       []AnalyticsEvidence `json:"evidence"`
	Limitations    []string            `json:"limitations,omitempty"`
}

type EvaluationResult struct {
	Name    string  `json:"name"`
	Score   float64 `json:"score"`
	Passed  bool    `json:"passed"`
	Details string  `json:"details"`
	// Blocking gates are structural and deterministic; a failing blocking gate
	// rejects the candidate context version before publish. Advisory gates
	// depend on ClickHouse/LLM execution and never block a publish.
	Blocking bool `json:"blocking"`
}

type FeatureRun struct {
	ID               string                  `json:"id"`
	Input            FeatureInput            `json:"input"`
	Stage            RunStage                `json:"stage"`
	ExecutionMode    string                  `json:"execution_mode"`
	BaseContext      int                     `json:"base_context_version"`
	Profile          *EventProfile           `json:"profile,omitempty"`
	Schema           *SchemaProposal         `json:"schema,omitempty"`
	Validation       *SchemaValidation       `json:"validation,omitempty"`
	Context          *ContextVersion         `json:"context,omitempty"`
	ContextDiff      *ContextDiff            `json:"context_diff,omitempty"`
	AnalysisContract *AnalysisContract       `json:"analysis_contract,omitempty"`
	Insight          *Insight                `json:"insight,omitempty"`
	QuestionAnswers  []QuestionResponse      `json:"question_answers,omitempty"`
	AnalyticsBundle  *FeatureAnalyticsBundle `json:"analytics_bundle,omitempty"`
	Evaluations      []EvaluationResult      `json:"evaluations,omitempty"`
	TraceID          string                  `json:"trace_id,omitempty"`
	Error            string                  `json:"error,omitempty"`
	CreatedAt        time.Time               `json:"created_at"`
	UpdatedAt        time.Time               `json:"updated_at"`
}

type RunEvent struct {
	RunID     string    `json:"run_id"`
	Stage     RunStage  `json:"stage"`
	Message   string    `json:"message"`
	Timestamp time.Time `json:"timestamp"`
}

type QuestionRequest struct {
	Role           string `json:"role"`
	Feature        string `json:"feature"`
	Question       string `json:"question"`
	ContextVersion *int   `json:"context_version,omitempty"`
	AllowStale     bool   `json:"allow_stale,omitempty"`
}

type QuestionResponse struct {
	Contract AnalysisContract `json:"contract"`
	Insight  Insight          `json:"insight"`
}

type ConversationMessage struct {
	Role         string   `json:"role"`
	Content      string   `json:"content"`
	FeatureScope []string `json:"feature_scope,omitempty"`
}

type ConversationRequest struct {
	Role           string                `json:"role"`
	Question       string                `json:"question"`
	Features       []string              `json:"features,omitempty"`
	ActiveFeatures []string              `json:"active_features,omitempty"`
	History        []ConversationMessage `json:"history,omitempty"`
	ContextVersion *int                  `json:"context_version,omitempty"`
	AllowStale     bool                  `json:"allow_stale,omitempty"`
}

type ConversationResponse struct {
	ResolvedQuestion string             `json:"resolved_question"`
	FeatureScope     []string           `json:"feature_scope"`
	ContextVersion   int                `json:"context_version"`
	Mode             string             `json:"mode"`
	Contract         AnalysisContract   `json:"contract"`
	Insight          Insight            `json:"insight"`
	KPIs             []AnalyticsKPI     `json:"kpis,omitempty"`
	Charts           []AnalyticsChart   `json:"charts,omitempty"`
	Sources          []QuestionResponse `json:"sources"`
	FollowUpPrompts  []string           `json:"follow_up_prompts"`
}
