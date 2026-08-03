package orchestrator

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/view26/featurelens/internal/agent"
	ch "github.com/view26/featurelens/internal/clickhouse"
	"github.com/view26/featurelens/internal/domain"
	"github.com/view26/featurelens/internal/eval"
	"github.com/view26/featurelens/internal/profiler"
	"github.com/view26/featurelens/internal/store"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

type Orchestrator struct {
	store           *store.Memory
	clickhouse      *ch.Client
	instrumentation agent.InstrumentationAgent
	contextAgent    agent.ContextAgent
	analytics       agent.AnalyticsAgent
	tracer          trace.Tracer
	tracingEnabled  bool
	mu              sync.Mutex
	approvals       map[string]chan struct{}
	refreshing      map[string]bool
	resetting       bool
}

type Option func(*Orchestrator)

func WithInsightSynthesizer(synthesizer agent.InsightSynthesizer) Option {
	return func(orchestrator *Orchestrator) { orchestrator.analytics.Synthesizer = synthesizer }
}

func WithTracingEnabled(enabled bool) Option {
	return func(orchestrator *Orchestrator) { orchestrator.tracingEnabled = enabled }
}

func New(memory *store.Memory, clickhouse *ch.Client, tracer trace.Tracer, database string, options ...Option) *Orchestrator {
	orchestrator := &Orchestrator{
		store:           memory,
		clickhouse:      clickhouse,
		instrumentation: agent.InstrumentationAgent{Database: database},
		analytics:       agent.AnalyticsAgent{Reader: clickhouse, Tracer: tracer},
		tracer:          tracer,
		approvals:       map[string]chan struct{}{},
		refreshing:      map[string]bool{},
	}
	for _, option := range options {
		option(orchestrator)
	}
	return orchestrator
}

func (o *Orchestrator) Start(ctx context.Context, input domain.FeatureInput) (domain.FeatureRun, error) {
	input.Name = strings.TrimSpace(input.Name)
	input.SpecMarkdown = strings.TrimSpace(input.SpecMarkdown)
	input.EventsNDJSON = strings.TrimSpace(input.EventsNDJSON)
	if input.Name == "" || input.SpecMarkdown == "" {
		return domain.FeatureRun{}, fmt.Errorf("name and spec_markdown are required")
	}
	if existing, ok := o.existingRun(input); ok {
		return existing, nil
	}
	if input.UseExistingData {
		if input.EventsNDJSON != "" {
			return domain.FeatureRun{}, fmt.Errorf("use_existing_data cannot be combined with events_ndjson")
		}
		database, table, _ := o.instrumentation.Target(input)
		events, err := o.clickhouse.ReadExistingFeature(ctx, database, table)
		if err != nil {
			return domain.FeatureRun{}, err
		}
		input.EventsNDJSON = events
	}
	if input.EventsNDJSON == "" {
		return domain.FeatureRun{}, fmt.Errorf("name, spec_markdown, and events_ndjson are required")
	}
	if input.Role == "" {
		input.Role = "product_manager"
	}
	base := o.store.LatestContext()
	now := time.Now().UTC()
	run := domain.FeatureRun{
		ID:            newID("run"),
		Input:         input,
		Stage:         domain.StageReceived,
		ExecutionMode: executionMode(o.clickhouse),
		BaseContext:   base.Version,
		CreatedAt:     now,
		UpdatedAt:     now,
	}
	approval := make(chan struct{}, 1)
	o.mu.Lock()
	if o.resetting {
		o.mu.Unlock()
		return domain.FeatureRun{}, fmt.Errorf("control plane reset is in progress")
	}
	if existing, ok := o.existingRun(input); ok {
		o.mu.Unlock()
		return existing, nil
	}
	o.store.CreateRun(run)
	o.approvals[run.ID] = approval
	o.mu.Unlock()
	message := "Release package accepted; orchestrator opened a governed agent run"
	if input.UseExistingData {
		message = "Retained ClickHouse feature dataset rehydrated; orchestrator opened a governed replay"
	}
	o.emit(run.ID, domain.StageReceived, message)
	go o.run(context.WithoutCancel(ctx), run.ID, approval)
	return run, nil
}

func (o *Orchestrator) existingRun(input domain.FeatureInput) (domain.FeatureRun, bool) {
	wantedSlug := agent.Slug(input.Slug)
	if wantedSlug == "" {
		wantedSlug = agent.Slug(input.Name)
	}
	wantedVersion := input.SchemaVersion
	if wantedVersion < 1 {
		wantedVersion = 1
	}
	for _, run := range o.store.ListRuns() {
		if run.Stage == domain.StageFailed {
			continue
		}
		runSlug := agent.Slug(run.Input.Slug)
		if runSlug == "" {
			runSlug = agent.Slug(run.Input.Name)
		}
		runVersion := run.Input.SchemaVersion
		if runVersion < 1 {
			runVersion = 1
		}
		if runSlug == wantedSlug && runVersion == wantedVersion {
			return run, true
		}
	}
	return domain.FeatureRun{}, false
}

func (o *Orchestrator) Approve(runID string) error {
	run, ok := o.store.GetRun(runID)
	if !ok {
		return fmt.Errorf("run %s not found", runID)
	}
	if run.Stage != domain.StageAwaitingApproval {
		if approvalWasAccepted(run.Stage) {
			return nil
		}
		return fmt.Errorf("run %s is at %s, not awaiting approval", runID, run.Stage)
	}
	o.mu.Lock()
	approval := o.approvals[runID]
	o.mu.Unlock()
	if approval == nil {
		return fmt.Errorf("approval gate for %s is unavailable", runID)
	}
	select {
	case approval <- struct{}{}:
	default:
	}
	return nil
}

// Approval is idempotent once the workflow has crossed its human gate. Clients
// can safely retry after a timeout or a delayed UI refresh without turning an
// already accepted decision into a user-facing conflict.
func approvalWasAccepted(stage domain.RunStage) bool {
	switch stage {
	case domain.StageSchemaExecuting,
		domain.StageSchemaVerified,
		domain.StageContextCandidate,
		domain.StageContextPublished,
		domain.StageAnalyticsComplete,
		domain.StageEvaluated,
		domain.StageCompleted:
		return true
	default:
		return false
	}
}

func (o *Orchestrator) Ask(ctx context.Context, request domain.QuestionRequest) (domain.QuestionResponse, error) {
	ctx, span := o.tracer.Start(ctx, "analytics.user_question", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "span"),
		attribute.String("langfuse.trace.name", "analytics.user_question"),
		attribute.StringSlice("langfuse.trace.tags", []string{"featurelens", "single-feature-question"}),
		attribute.String("langfuse.observation.input", langfuseJSON(map[string]any{"question": request.Question, "role": request.Role, "feature": request.Feature})),
		attribute.String("analytics.user_input", request.Question),
		attribute.String("analytics.role", request.Role),
		attribute.String("analytics.requested_feature", request.Feature),
	))
	defer span.End()
	traceID := span.SpanContext().TraceID().String()
	if traceID == "00000000000000000000000000000000" {
		traceID = newID("trace")
	}
	runs := o.store.ListRuns()
	var selected *domain.FeatureRun
	for index := range runs {
		run := &runs[index]
		if run.Profile == nil || run.Schema == nil || run.Context == nil {
			continue
		}
		if request.Feature == "" || strings.EqualFold(run.Input.Name, request.Feature) || agent.Slug(run.Input.Name) == agent.Slug(request.Feature) {
			selected = run
			break
		}
	}
	if selected == nil {
		return domain.QuestionResponse{}, fmt.Errorf("no published feature context matches %q", request.Feature)
	}
	// Always answer from the latest published context so the Analytics Agent
	// never reasons from the snapshot minted by an older feature run.
	graph := o.store.LatestContext()
	latestVersion := graph.Version
	staleContext := false
	if request.ContextVersion != nil && *request.ContextVersion != latestVersion {
		if !request.AllowStale {
			return domain.QuestionResponse{}, fmt.Errorf("context v%d is not latest (v%d); set allow_stale to pin a historical version", *request.ContextVersion, latestVersion)
		}
		versioned, ok := o.store.Context(*request.ContextVersion)
		if !ok {
			return domain.QuestionResponse{}, fmt.Errorf("context v%d not found", *request.ContextVersion)
		}
		graph = versioned
		staleContext = true
	}
	featureKey := "feature:" + agent.Slug(selected.Input.Name)
	known := false
	for _, node := range graph.Nodes {
		if node.Key == featureKey {
			known = true
			break
		}
	}
	if !known {
		return domain.QuestionResponse{}, fmt.Errorf("context v%d does not know feature %q; use a context version where it has been verified and published", graph.Version, selected.Input.Name)
	}
	span.SetAttributes(
		attribute.String("analytics.selected_feature", selected.Input.Name),
		attribute.Int("analytics.context_version", graph.Version),
		attribute.Int("analytics.latest_context_version", latestVersion),
		attribute.Bool("analytics.context_stale", staleContext),
		attribute.String("analytics.schema", selected.Schema.Database+"."+selected.Schema.Table),
		attribute.Int("analytics.dataset_rows", selected.Profile.Rows),
	)
	contract, insight := o.analytics.Analyze(ctx, request.Role, request.Question, selected.Input, *selected.Profile, *selected.Schema, graph, traceID)
	if insight.Trace != nil {
		for index := range insight.Trace.Steps {
			if insight.Trace.Steps[index].ID == "answer.compose" {
				insight.Trace.Steps[index].ObservationID = span.SpanContext().SpanID().String()
			}
		}
	}
	if staleContext {
		staleness := fmt.Sprintf("pinned context v%d; latest is v%d", graph.Version, latestVersion)
		contract.Limitations = append(contract.Limitations, "Answer uses a pinned historical context version: "+staleness)
		if insight.Evidence == nil {
			insight.Evidence = map[string]any{}
		}
		insight.Evidence["context_staleness"] = staleness
	}
	span.SetAttributes(
		attribute.String("analytics.answerability", contract.Answerability), attribute.String("analytics.output", insight.Summary),
		attribute.String("langfuse.observation.output", langfuseJSON(map[string]any{
			"headline": insight.Headline, "summary": insight.Summary, "why": insight.Why,
			"confidence": insight.Confidence, "recommended_action": insight.RecommendedAction,
			"context_version": graph.Version,
		})),
	)
	return domain.QuestionResponse{Contract: contract, Insight: insight}, nil
}

// RefreshAnalytics re-executes a completed feature's declared questions and
// dashboard bundle against the latest published semantic context. It does not
// rebuild schemas, mutate retained feature data, or publish a new context.
func (o *Orchestrator) RefreshAnalytics(ctx context.Context, runID string) (domain.FeatureRun, error) {
	o.mu.Lock()
	if o.resetting {
		o.mu.Unlock()
		return domain.FeatureRun{}, fmt.Errorf("control plane reset is in progress")
	}
	if o.refreshing[runID] {
		o.mu.Unlock()
		return domain.FeatureRun{}, fmt.Errorf("analytics refresh for run %s is already in progress", runID)
	}
	o.refreshing[runID] = true
	o.mu.Unlock()
	defer func() {
		o.mu.Lock()
		delete(o.refreshing, runID)
		o.mu.Unlock()
	}()

	run, ok := o.store.GetRun(runID)
	if !ok {
		return domain.FeatureRun{}, fmt.Errorf("run %s not found", runID)
	}
	if run.Stage != domain.StageCompleted || run.Profile == nil || run.Schema == nil || run.Context == nil {
		return domain.FeatureRun{}, fmt.Errorf("run %s is not a completed published feature", runID)
	}
	graph := o.store.LatestContext()
	featureKey := "feature:" + agent.Slug(run.Input.Name)
	known := false
	for _, node := range graph.Nodes {
		if node.Key == featureKey {
			known = true
			break
		}
	}
	if !known {
		return domain.FeatureRun{}, fmt.Errorf("latest context v%d does not know feature %q", graph.Version, run.Input.Name)
	}

	traceID := run.TraceID
	if strings.TrimSpace(traceID) == "" {
		traceID = newID("trace")
	}
	questions := agent.ExtractQuestions(run.Input.SpecMarkdown)
	if len(questions) == 0 {
		questions = []string{"What did this feature add and how should a Product Manager evaluate it?"}
	}
	answers := make([]domain.QuestionResponse, 0, len(questions))
	for _, question := range questions {
		contract, insight := o.analytics.Analyze(ctx, run.Input.Role, question, run.Input, *run.Profile, *run.Schema, graph, traceID)
		answers = append(answers, domain.QuestionResponse{Contract: contract, Insight: insight})
	}
	contract, insight := answers[0].Contract, answers[0].Insight
	bundle := o.analytics.BuildFeatureBundle(ctx, run.Input.Role, run.Input, *run.Profile, *run.Schema, graph, answers, traceID)

	candidate := run
	candidate.AnalysisContract = &contract
	candidate.Insight = &insight
	candidate.QuestionAnswers = answers
	candidate.AnalyticsBundle = &bundle
	candidate.UpdatedAt = time.Now().UTC()
	if err := o.clickhouse.SaveRun(ctx, candidate); err != nil {
		return domain.FeatureRun{}, fmt.Errorf("persist refreshed analytics for run %s: %w", runID, err)
	}
	updated, err := o.store.UpdateRun(runID, func(stored *domain.FeatureRun) {
		stored.AnalysisContract = &contract
		stored.Insight = &insight
		stored.QuestionAnswers = answers
		stored.AnalyticsBundle = &bundle
	})
	if err != nil {
		return domain.FeatureRun{}, err
	}
	o.emit(runID, domain.StageCompleted, fmt.Sprintf("Analytics refreshed against context v%d: %d declared questions, %d evidence-backed Inbox claims", graph.Version, len(answers), len(bundle.Insights)))
	return updated, nil
}

func (o *Orchestrator) Store() *store.Memory { return o.store }

func (o *Orchestrator) AnalyticsStatus() map[string]any { return o.analytics.SynthesisStatus() }

func (o *Orchestrator) Catalog(ctx context.Context) (domain.DataCatalog, error) {
	return o.clickhouse.Catalog(ctx, agent.BaselineSourceTableNames(), o.store.LatestContext())
}

// Reset restores context v0 after proving that no feature evolution is still
// waiting at the human gate or executing downstream work.
func (o *Orchestrator) Reset(ctx context.Context) (domain.ContextVersion, error) {
	ctx, span := o.tracer.Start(ctx, "orchestrator.reset_baseline", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "agent"),
		attribute.String("agent.name", "FeatureLens Orchestrator"),
		attribute.String("reset.scope", "control_plane_only"),
		attribute.Bool("reset.preserve_source_tables", true),
		attribute.Bool("reset.preserve_feature_tables", true),
	))
	defer span.End()

	o.mu.Lock()
	if o.resetting {
		o.mu.Unlock()
		return domain.ContextVersion{}, fmt.Errorf("control plane reset is already in progress")
	}
	if len(o.approvals) > 0 {
		o.mu.Unlock()
		return domain.ContextVersion{}, fmt.Errorf("cannot reset while %d agent run(s) are active", len(o.approvals))
	}
	if len(o.refreshing) > 0 {
		o.mu.Unlock()
		return domain.ContextVersion{}, fmt.Errorf("cannot reset while %d analytics refresh(es) are active", len(o.refreshing))
	}
	o.resetting = true
	o.mu.Unlock()
	defer func() {
		o.mu.Lock()
		o.resetting = false
		o.mu.Unlock()
	}()

	baseline := agent.BaselineContext()
	if o.clickhouse.Enabled() {
		catalog, err := o.clickhouse.DiscoverSourceCatalog(ctx, agent.BaselineSourceTableNames())
		if err != nil {
			return domain.ContextVersion{}, fmt.Errorf("refresh baseline source catalog: %w", err)
		}
		baseline = agent.ApplySourceCatalog(baseline, catalog)
	}
	toolCtx, toolSpan := o.tracer.Start(ctx, "clickhouse.reset_control_plane", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "tool"),
		attribute.String("tool.name", "clickhouse.reset_control_plane"),
	))
	err := o.clickhouse.ResetControlPlane(toolCtx, baseline)
	toolSpan.End()
	if err != nil {
		return domain.ContextVersion{}, err
	}
	o.store.Reset(baseline)
	span.SetAttributes(attribute.Int("context.version", baseline.Version))
	return baseline, nil
}

func (o *Orchestrator) TracingStatus() map[string]any {
	status := "local_only"
	if o.tracingEnabled {
		status = "streaming"
	}
	return map[string]any{
		"enabled":  o.tracingEnabled,
		"status":   status,
		"provider": "langfuse",
	}
}

func (o *Orchestrator) run(ctx context.Context, runID string, approval <-chan struct{}) {
	run, _ := o.store.GetRun(runID)
	ctx, span := o.tracer.Start(ctx, "orchestrator.feature_evolution",
		trace.WithAttributes(
			attribute.String("langfuse.observation.type", "agent"),
			attribute.String("langfuse.trace.name", "orchestrator.feature_evolution"),
			attribute.StringSlice("langfuse.trace.tags", []string{"featurelens", "feature-evolution"}),
			attribute.String("langfuse.observation.input", langfuseJSON(map[string]any{"feature": run.Input.Name, "role": run.Input.Role, "schema_version": run.Input.SchemaVersion, "use_existing_data": run.Input.UseExistingData})),
			attribute.String("agent.name", "FeatureLens Orchestrator"),
			attribute.String("feature.name", run.Input.Name),
			attribute.String("run.id", runID),
			attribute.String("role", run.Input.Role),
			attribute.String("orchestration.policy", "instrumentation -> approval -> context -> analytics -> evaluation"),
		))
	traceID := span.SpanContext().TraceID().String()
	if traceID == "00000000000000000000000000000000" {
		traceID = newID("trace")
	}
	defer func() {
		span.End()
		o.mu.Lock()
		delete(o.approvals, runID)
		o.mu.Unlock()
	}()
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.TraceID = traceID })

	if err := o.stage(runID, domain.StageProfiling, "Instrumentation Agent is profiling NDJSON shape, types, cardinality, and event order"); err != nil {
		return
	}
	_, profileSpan := o.tracer.Start(ctx, "instrumentation.profile", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "chain"),
		attribute.String("agent.name", "Instrumentation Agent"),
	))
	profile, err := profiler.Profile(run.Input.EventsNDJSON)
	profileSpan.SetAttributes(attribute.Int("profile.rows", profile.Rows), attribute.Int("profile.fields", len(profile.Fields)))
	profileSpan.End()
	if err != nil {
		o.fail(runID, err)
		return
	}
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Profile = &profile })
	profiledMessage := fmt.Sprintf("Profiled %d rows, %d fields, and %d event types", profile.Rows, len(profile.Fields), len(profile.EventCounts))
	if profile.SkippedRows > 0 {
		profiledMessage += fmt.Sprintf(" (%d malformed lines skipped)", profile.SkippedRows)
	}
	_ = o.stage(runID, domain.StageProfiled, profiledMessage)

	_, designSpan := o.tracer.Start(ctx, "instrumentation.schema_design", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "agent"),
		attribute.String("agent.name", "Instrumentation Agent"),
		attribute.String("agent.goal", "Design a verified ClickHouse schema from the release contract and observed events"),
	))
	schema := o.instrumentation.Design(run.Input, profile)
	if run.Input.UseExistingData {
		existing, schemaErr := o.clickhouse.ExistingSchema(ctx, schema.Database, schema.Table, schema.Version)
		if schemaErr != nil {
			designSpan.End()
			o.fail(runID, schemaErr)
			return
		}
		schema = existing
	}
	validation := o.instrumentation.Validate(profile, schema)
	designSpan.SetAttributes(
		attribute.String("schema.table", schema.Database+"."+schema.Table),
		attribute.Int("schema.version", schema.Version),
		attribute.Bool("schema.validation_passed", validation.Passed),
	)
	designSpan.End()
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Schema = &schema })
	proposalMessage := "Instrumentation Agent proposed typed ClickHouse DDL and an analytics-aware sort key"
	if run.Input.UseExistingData {
		proposalMessage = "Instrumentation Agent loaded the authoritative physical schema from the retained ClickHouse table"
	}
	_ = o.stage(runID, domain.StageSchemaProposed, proposalMessage)
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Validation = &validation })
	_ = o.stage(runID, domain.StageSchemaValidated, "Deterministic schema safety checks completed")
	if !validation.Passed {
		o.fail(runID, fmt.Errorf("schema proposal failed deterministic validation"))
		return
	}

	approvalMessage := "Human approval is required before any ClickHouse DDL is executed"
	if run.Input.UseExistingData {
		approvalMessage = "Human approval is required before the retained dataset is attached to a new context version"
	}
	_ = o.stage(runID, domain.StageAwaitingApproval, approvalMessage)
	if !run.Input.AutoApprove {
		select {
		case <-approval:
		case <-ctx.Done():
			o.fail(runID, ctx.Err())
			return
		}
	}
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Schema.Status = "approved" })
	executionMessage := "Approved DDL and event insert are being applied"
	if run.Input.UseExistingData {
		executionMessage = "Approved retained-table row count, event IDs, and catalog schema are being verified"
	}
	_ = o.stage(runID, domain.StageSchemaExecuting, executionMessage)
	_, executeSpan := o.tracer.Start(ctx, "instrumentation.schema_execute", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "tool"),
		attribute.String("tool.name", "clickhouse.apply_and_verify"),
		attribute.String("schema.table", schema.Database+"."+schema.Table),
	))
	var insertReport ch.InsertReport
	if run.Input.UseExistingData {
		err = o.clickhouse.VerifyRetainedFeature(ctx, schema, run.Input.EventsNDJSON, profile.Rows)
	} else {
		insertReport, err = o.clickhouse.Apply(ctx, schema, run.Input.EventsNDJSON)
		if err == nil {
			err = o.clickhouse.Verify(ctx, schema, insertReport.Inserted)
		}
		if len(insertReport.Warnings) > 0 {
			_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) {
				if run.Profile != nil {
					run.Profile.Warnings = append(run.Profile.Warnings, insertReport.Warnings...)
				}
			})
		}
	}
	executeSpan.End()
	if err != nil {
		o.fail(runID, err)
		return
	}
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Schema.Status = "verified" })
	schema.Status = "verified"
	message := "Schema and inserted rows verified in ClickHouse"
	if insertReport.Quarantined > 0 {
		message = fmt.Sprintf("Schema and %d inserted rows verified in ClickHouse (%d rows quarantined for not matching the schema)", insertReport.Inserted, insertReport.Quarantined)
	}
	if run.Input.UseExistingData {
		message = "Retained ClickHouse schema, row count, and full event-ID fingerprint verified without writes"
	}
	if !o.clickhouse.Enabled() {
		message = "Schema lifecycle verified in safe simulation mode; configure ClickHouse runtime credentials for physical execution"
	}
	_ = o.stage(runID, domain.StageSchemaVerified, message)

	_ = o.stage(runID, domain.StageContextCandidate, "Context Agent is compiling the spec, observed events, schema, metrics, questions, roles, and known issues")
	parent := o.store.LatestContext()
	publishState := "published"
	if !o.clickhouse.Enabled() {
		publishState = "simulation-published"
	}
	_, contextSpan := o.tracer.Start(ctx, "context.evolve", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "agent"),
		attribute.String("agent.name", "Context Agent"),
		attribute.String("agent.goal", "Publish an immutable semantic context version grounded in the verified schema"),
		attribute.Int("context.parent_version", parent.Version),
	))
	graph := o.contextAgent.Evolve(parent, run.Input, profile, schema, traceID, "candidate")
	diff := agent.DiffContexts(parent, graph)
	contextSpan.SetAttributes(
		attribute.Int("context.version", graph.Version),
		attribute.Int("context.nodes", len(graph.Nodes)),
		attribute.Int("context.edges", len(graph.Edges)),
		attribute.Int("context.conflicts", len(graph.Conflicts)),
		attribute.Int("context.diff.added_nodes", len(diff.AddedNodes)),
		attribute.Int("context.diff.changed_nodes", len(diff.ChangedNodes)),
		attribute.Int("context.diff.added_edges", len(diff.AddedEdges)),
		attribute.Int("context.diff.removed_nodes", len(diff.RemovedNodeKeys)),
	)
	contextSpan.End()
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) {
		run.BaseContext = parent.Version
		run.ContextDiff = &diff
	})

	// The analytics phase runs against the candidate graph so the full
	// evolution gate suite can judge the version before it is published.
	analyticsCtx, analyticsSpan := o.tracer.Start(ctx, "analytics.answer_declared_questions", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "agent"),
		attribute.String("agent.name", "Analytics Agent"),
		attribute.String("agent.goal", "Answer declared business questions with role-aware context and verified ClickHouse evidence"),
		attribute.Int("context.version", graph.Version),
	))
	questions := agent.ExtractQuestions(run.Input.SpecMarkdown)
	if len(questions) == 0 {
		questions = []string{"What did this feature add and how should a Product Manager evaluate it?"}
	}
	answers := make([]domain.QuestionResponse, 0, len(questions))
	for _, question := range questions {
		contract, insight := o.analytics.Analyze(analyticsCtx, run.Input.Role, question, run.Input, profile, schema, graph, traceID)
		answers = append(answers, domain.QuestionResponse{Contract: contract, Insight: insight})
	}
	contract := answers[0].Contract
	insight := answers[0].Insight
	if insight.Trace != nil {
		for index := range insight.Trace.Steps {
			if insight.Trace.Steps[index].ID == "answer.compose" {
				insight.Trace.Steps[index].ObservationID = span.SpanContext().SpanID().String()
			}
		}
	}
	bundle := o.analytics.BuildFeatureBundle(analyticsCtx, run.Input.Role, run.Input, profile, schema, graph, answers, traceID)
	analyticsSpan.SetAttributes(
		attribute.Int("analytics.questions_answered", len(answers)),
		attribute.Int("analytics.bundle_kpis", len(bundle.KPIs)),
		attribute.Int("analytics.bundle_charts", len(bundle.Charts)),
		attribute.String("analytics.bundle_status", bundle.Status),
		attribute.String("analytics.output", insight.Summary),
	)
	analyticsSpan.End()

	_, evalSpan := o.tracer.Start(ctx, "context.evaluate", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "evaluator"),
		attribute.String("evaluator.name", "Context evolution quality gates"),
	))
	evaluations := eval.ContextEvolution(parent, graph, run.Input, profile, contract, insight, answers)
	failedBlocking := failedBlockingGates(evaluations)
	evalSpan.SetAttributes(
		attribute.Int("context.gates_total", len(evaluations)),
		attribute.Int("context.gates_failed_blocking", len(failedBlocking)),
	)
	evalSpan.End()
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Evaluations = evaluations })

	if len(failedBlocking) > 0 {
		graph.State = "rejected"
		o.store.QuarantineContext(graph)
		_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Context = &graph })
		if persistErr := o.clickhouse.SaveEvaluations(ctx, graph.Version, evaluations, traceID, runID); persistErr != nil {
			o.emit(runID, domain.StageEvaluated, fmt.Sprintf("Warning: rejected-candidate evaluations were not persisted: %v", persistErr))
		}
		o.fail(runID, fmt.Errorf("context v%d rejected before publish: blocking evolution gates failed (%s); latest context remains v%d", graph.Version, strings.Join(failedBlocking, ", "), parent.Version))
		return
	}

	graph.State = publishState
	if err := o.store.PublishContext(graph); err != nil {
		o.fail(runID, err)
		return
	}
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) { run.Context = &graph })
	_ = o.stage(runID, domain.StageContextPublished, fmt.Sprintf("Immutable context v%d published from v%d after passing all blocking gates (+%d nodes, ~%d changed, +%d edges)", graph.Version, graph.ParentVersion, len(diff.AddedNodes), len(diff.ChangedNodes), len(diff.AddedEdges)))
	_, _ = o.store.UpdateRun(runID, func(run *domain.FeatureRun) {
		run.AnalysisContract = &contract
		run.Insight = &insight
		run.QuestionAnswers = answers
		run.AnalyticsBundle = &bundle
	})
	_ = o.stage(runID, domain.StageAnalyticsComplete, fmt.Sprintf("Analytics Agent executed %d declared playbooks and published %d KPIs, %d charts, and %d ranked actions", len(answers), len(bundle.KPIs), len(bundle.Charts), len(bundle.Insights)))
	if err := o.clickhouse.SaveContext(ctx, graph, schema, evaluations, &diff, runID); err != nil {
		o.fail(runID, fmt.Errorf("persist context control plane: %w", err))
		return
	}
	_ = o.stage(runID, domain.StageEvaluated, "Before/after, grounding, role-awareness, and regression checks completed before publish")
	span.SetAttributes(attribute.String("langfuse.observation.output", langfuseJSON(map[string]any{
		"feature": run.Input.Name, "context_version": graph.Version, "headline": insight.Headline,
		"summary": insight.Summary, "confidence": insight.Confidence, "evaluations": evaluations,
	})))
	_ = o.stage(runID, domain.StageCompleted, "Feature evolution run completed")
}

func failedBlockingGates(evaluations []domain.EvaluationResult) []string {
	failed := []string{}
	for _, evaluation := range evaluations {
		if evaluation.Blocking && !evaluation.Passed {
			failed = append(failed, evaluation.Name)
		}
	}
	return failed
}

func (o *Orchestrator) stage(runID string, stage domain.RunStage, message string) error {
	run, err := o.store.UpdateRun(runID, func(run *domain.FeatureRun) {
		run.Stage = stage
		run.Error = ""
	})
	if err == nil {
		o.emit(runID, stage, message)
		_ = o.clickhouse.SaveRun(context.Background(), run)
	}
	return err
}

func (o *Orchestrator) fail(runID string, err error) {
	run, _ := o.store.UpdateRun(runID, func(run *domain.FeatureRun) {
		run.Stage = domain.StageFailed
		run.Error = err.Error()
	})
	o.emit(runID, domain.StageFailed, err.Error())
	_ = o.clickhouse.SaveRun(context.Background(), run)
}

func (o *Orchestrator) emit(runID string, stage domain.RunStage, message string) {
	o.store.AddEvent(domain.RunEvent{RunID: runID, Stage: stage, Message: message, Timestamp: time.Now().UTC()})
}

func executionMode(client *ch.Client) string {
	if client.Enabled() {
		return "clickhouse"
	}
	return "simulation"
}

func newID(prefix string) string {
	buffer := make([]byte, 8)
	_, _ = rand.Read(buffer)
	return prefix + "_" + hex.EncodeToString(buffer)
}
