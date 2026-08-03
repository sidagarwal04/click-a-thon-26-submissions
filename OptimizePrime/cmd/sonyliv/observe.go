package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/d-cryptic/clickathon/internal/chdb"
	"github.com/d-cryptic/clickathon/internal/config"
	"github.com/d-cryptic/clickathon/internal/otelemit"
)

// observeScopeName names the OTel instrumentation scope for every payload
// this subcommand emits (metrics, logs, traces alike).
const observeScopeName = "sonyliv.observe"

// cmdObserve is H7: ClickStack observing OUR pipeline, not the other way
// round. It queries the same ClickHouse database the rest of the CLI talks
// to for watermark lag, recent build-stage timing (from system.query_log),
// and the reconcile gate's last recorded verdict, then emits all three as
// OTLP metrics, a correlated log line per signal, and one trace covering the
// whole observe run — to our own ClickStack collector.
//
// See docs/OBSERVABILITY.md for what is emitted and why, and for the
// deliberate omission: benchmark query latency/bytes read is NOT
// instrumented here. ClickHouse's own system.query_log already has it —
// exactly (granules_read, a server-side ProfileEvent no client span could
// know), and a client-measured span would only add network round-trip noise
// on top of a number the database already has authoritatively.
func cmdObserve(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("observe", flag.ContinueOnError)
	target := fs.String("target", string(config.TargetFromEnv()), "which clickhouse to observe: local or cloud")
	timeout := fs.Duration("timeout", 30*time.Second, "overall timeout")
	evidencePath := fs.String("evidence", "evidence/reconcile.txt", "path to the reconcile gate's evidence file")
	dryRun := fs.Bool("dry-run", false, "compute and print telemetry but do not POST it to ClickStack")
	if err := fs.Parse(args); err != nil {
		return err
	}

	cfg, err := config.Load(config.Target(*target))
	if err != nil {
		return err
	}
	cs := config.LoadClickStack()
	if !*dryRun && cs.IngestionKey == "" {
		return fmt.Errorf("CLICKSTACK_INGESTION_KEY is not set — run tools/clickstack-bootstrap.sh, or pass -dry-run")
	}

	ctx, cancel := context.WithTimeout(ctx, *timeout)
	defer cancel()

	conn, err := chdb.Open(ctx, &cfg)
	if err != nil {
		return err
	}
	defer func() { _ = conn.Close() }()

	run, err := newObserveRun()
	if err != nil {
		return err
	}

	wm, wmSpan, err := observeWatermark(ctx, conn, run)
	if err != nil {
		return err
	}
	stages, stagesSpan, err := observeBuildStages(ctx, conn, cfg.Database, run)
	if err != nil {
		return err
	}
	evidence, evidenceFound, evidenceSpan, err := observeReconcile(*evidencePath, run)
	if err != nil {
		return err
	}

	run.spans = append(run.spans, wmSpan, stagesSpan, evidenceSpan)
	run.finish()

	metrics := buildMetrics(wm, stages, evidence, evidenceFound)
	logs := buildLogs(wm, stages, evidence, evidenceFound, run)
	resource := otelemit.Resource{Attributes: []otelemit.KeyValue{
		otelemit.StringAttr("service.name", cs.ServiceName),
		otelemit.StringAttr("sonyliv.target", string(cfg.Target)),
		otelemit.StringAttr("sonyliv.database", cfg.Database),
	}}

	printSummary(wm, stages, evidence, evidenceFound, run.traceID)

	if *dryRun {
		fmt.Println("\n-dry-run: not posting to ClickStack")
		return nil
	}

	client := otelemit.New(cs.Endpoint, cs.IngestionKey)
	metricsPayload := otelemit.MetricsPayload{ResourceMetrics: []otelemit.ResourceMetrics{{
		Resource:     resource,
		ScopeMetrics: []otelemit.ScopeMetrics{{Scope: otelemit.Scope{Name: observeScopeName}, Metrics: metrics}},
	}}}
	logsPayload := otelemit.LogsPayload{ResourceLogs: []otelemit.ResourceLogs{{
		Resource:  resource,
		ScopeLogs: []otelemit.ScopeLogs{{Scope: otelemit.Scope{Name: observeScopeName}, LogRecords: logs}},
	}}}
	tracesPayload := otelemit.TracesPayload{ResourceSpans: []otelemit.ResourceSpans{{
		Resource:   resource,
		ScopeSpans: []otelemit.ScopeSpans{{Scope: otelemit.Scope{Name: observeScopeName}, Spans: run.spans}},
	}}}

	if err := client.PostMetrics(ctx, metricsPayload); err != nil {
		return fmt.Errorf("emit metrics: %w", err)
	}
	if err := client.PostLogs(ctx, logsPayload); err != nil {
		return fmt.Errorf("emit logs: %w", err)
	}
	if err := client.PostTraces(ctx, tracesPayload); err != nil {
		return fmt.Errorf("emit traces: %w", err)
	}

	fmt.Fprintf(os.Stdout, "\nemitted %d metrics, %d logs, %d spans to %s (trace %s)\n",
		len(metrics), len(logs), len(run.spans), cs.Endpoint, run.traceID)
	return nil
}
