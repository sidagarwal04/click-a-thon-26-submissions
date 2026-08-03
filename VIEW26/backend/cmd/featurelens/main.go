package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/api"
	"github.com/view26/featurelens/internal/clickhouse"
	"github.com/view26/featurelens/internal/langfuse"
	"github.com/view26/featurelens/internal/llm"
	"github.com/view26/featurelens/internal/orchestrator"
	"github.com/view26/featurelens/internal/store"
	"github.com/view26/featurelens/internal/telemetry"
)

func main() {
	ctx := context.Background()
	tracer, shutdownTracing, err := telemetry.Configure(ctx)
	if err != nil {
		log.Fatalf("configure Langfuse tracing: %v", err)
	}
	defer func() { _ = shutdownTracing(context.Background()) }()

	clickhouseClient := clickhouse.FromEnv()
	if clickhouseClient.Enabled() {
		pingCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
		err = clickhouseClient.Ping(pingCtx)
		cancel()
		if err != nil {
			log.Fatalf("ClickHouse configured but unreachable: %v", err)
		}
		migrationCtx, migrationCancel := context.WithTimeout(ctx, 30*time.Second)
		err = clickhouseClient.Initialize(migrationCtx)
		migrationCancel()
		if err != nil {
			log.Fatalf("initialize ClickHouse control plane: %v", err)
		}
	}
	baseline := agent.BaselineContext()
	if clickhouseClient.Enabled() {
		catalogCtx, catalogCancel := context.WithTimeout(ctx, 30*time.Second)
		catalog, catalogErr := clickhouseClient.DiscoverSourceCatalog(catalogCtx, agent.BaselineSourceTableNames())
		catalogCancel()
		if catalogErr != nil {
			log.Fatalf("bootstrap baseline source catalog: %v", catalogErr)
		}
		baseline = agent.ApplySourceCatalog(baseline, catalog)
	}
	if err := clickhouseClient.SaveBaseline(ctx, baseline); err != nil {
		log.Fatalf("persist baseline context: %v", err)
	}
	memory := store.NewMemory(baseline)
	if clickhouseClient.Enabled() {
		restoreCtx, restoreCancel := context.WithTimeout(ctx, 30*time.Second)
		contexts, runs, restoreErr := clickhouseClient.LoadControlPlane(restoreCtx)
		restoreCancel()
		if restoreErr != nil {
			log.Fatalf("restore durable control plane: %v", restoreErr)
		}
		if err := memory.Restore(contexts, runs); err != nil {
			log.Fatalf("hydrate in-memory control plane: %v", err)
		}
		log.Printf("Restored %d published contexts and %d current feature releases from %d durable run records in ClickHouse", len(contexts), len(memory.ListRuns()), len(runs))
	}
	database := envDefault("CLICKHOUSE_CONTROL_DATABASE", "featurelens_poc")
	synthesizer := llm.FromEnv(tracer)
	langfuseClient := langfuse.FromEnv()
	engine := orchestrator.New(
		memory,
		clickhouseClient,
		tracer,
		database,
		orchestrator.WithInsightSynthesizer(synthesizer),
		orchestrator.WithTracingEnabled(telemetry.Enabled()),
	)

	address := envDefault("FEATURELENS_ADDR", ":8080")
	server := &http.Server{Addr: address, Handler: api.New(engine, api.WithLangfuse(langfuseClient)), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		log.Printf("FeatureLens listening on %s (ClickHouse mode: %t)", address, clickhouseClient.Enabled())
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("serve: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Printf("shutdown: %v", err)
	}
}

func envDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
