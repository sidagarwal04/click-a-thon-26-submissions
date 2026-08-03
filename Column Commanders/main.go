package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.uber.org/zap"

	"clickhouse-go-service/internal/config"
	"clickhouse-go-service/internal/db"
	httpserver "clickhouse-go-service/internal/http"
	"clickhouse-go-service/internal/query"
	"clickhouse-go-service/internal/telemetry"
	"clickhouse-go-service/services/alertmanager"
	"clickhouse-go-service/services/anomalydetector"
	"clickhouse-go-service/services/anomalydetector/baseline"
	"clickhouse-go-service/services/anomalydetector/detector"
	"clickhouse-go-service/services/detectionv2"
	"clickhouse-go-service/services/drilldown"
	"clickhouse-go-service/services/investigation"
	"clickhouse-go-service/services/llm"
	"clickhouse-go-service/services/narrator"
)

func main() {
	cfg := config.Load()
	if err := cfg.LLM.Validate(); err != nil {
		fmt.Fprintf(os.Stderr, "invalid llm configuration, disabling llm features: %v\n", err)
		cfg.LLM.Enabled = false
		cfg.LLM.InvestigationEnabled = false
		cfg.LLM.NarrationEnabled = false
	}

	const svcName = "clickhouse-go-service"
	ctx := context.Background()

	zapLogger, otelShutdown, err := telemetry.Setup(ctx, svcName)
	if err != nil {
		// zap.L() is a no-op before Setup succeeds; print directly to stderr.
		fmt.Fprintf(os.Stderr, "failed to init opentelemetry: %v\n", err)
		os.Exit(1)
	}
	defer otelShutdown()

	langfuseShutdown, err := telemetry.InitLangfuse(ctx, svcName)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to init langfuse: %v\n", err)
		os.Exit(1)
	}
	defer langfuseShutdown()

	// slog logger for anomaly detection services and HTTP handlers
	logger := slog.Default()

	// ── ClickHouse connection ─────────────────────────────────────────────────
	chClient, err := db.NewClient(cfg)
	if err != nil {
		zapLogger.Error("failed to connect to clickhouse", zap.Error(err))
		os.Exit(1)
	}
	defer chClient.Close()

	if err := chClient.Migrate(ctx); err != nil {
		zapLogger.Error("migration failed", zap.Error(err))
		os.Exit(1)
	}
	if err := chClient.MigrateGlobalRollups(ctx); err != nil {
		logger.Warn("global rollup migration failed (non-fatal, platform detectors will error until fixed)", slog.Any("error", err))
	} else if err := chClient.BackfillGlobalRollupsIfEmpty(ctx); err != nil {
		logger.Warn("global rollup backfill failed (non-fatal)", slog.Any("error", err))
	}
	if err := chClient.MigrateDetection(ctx); err != nil {
		logger.Warn("detection migration failed (non-fatal)", slog.Any("error", err))
	}
	if err := chClient.MigrateDimensionRollup(ctx); err != nil {
		logger.Warn("dimension rollup migration failed (non-fatal, segment detectors will error until fixed)", slog.Any("error", err))
	} else if err := chClient.BackfillDimensionRollupIfEmpty(ctx); err != nil {
		logger.Warn("dimension rollup backfill failed (non-fatal)", slog.Any("error", err))
	}
	if err := chClient.MigrateDetectionV2(ctx); err != nil {
		logger.Warn("detection v2 migration failed (non-fatal)", slog.Any("error", err))
	}
	if cfg.Detection.AutoBackfill {
		if err := chClient.BackfillDetectionV2(ctx); err != nil {
			logger.Warn("detection v2 backfill failed (non-fatal)", slog.Any("error", err))
		}
	}
	logger.Info("clickhouse migrations complete")

	if cfg.OtelEndpoint != "" {
		zapLogger.Info("clickstack tracing enabled", zap.String("otlp_endpoint", cfg.OtelEndpoint))
	}

	// ── Anomaly detection pipeline ────────────────────────────────────────
	qe := query.NewExecutor(chClient, logger)
	bp := baseline.NewSamePeriodProvider(qe, cfg.Detection, logger)

	detectors := []anomalydetector.Detector{
		detector.NewRobustZScoreDetector(bp, cfg.Detection, logger),
		detector.NewTrendVolumeDetector(bp, cfg.Detection, logger),
		detector.NewDirectionalCUSUMDetector(qe, bp, cfg.Detection, logger),
	}
	// Broad-segment detectors run every cycle alongside the platform-level ones
	// above — not cascaded from a platform-level trigger. See
	// docs/ARCHITECTURE_VALIDATED.md §4.2: both known fill-rate incidents in the
	// validated dataset are invisible at the platform aggregate.
	for _, dim := range cfg.Detection.SegmentDimensions {
		detectors = append(detectors, detector.NewSegmentZScoreDetector(qe, dim, cfg.Detection, logger))
	}

	ddEngine := drilldown.NewEngine(qe, cfg.Detection, logger)
	detEngine := anomalydetector.NewDetectionEngine(detectors, qe, cfg.Detection, logger)
	llmClient := llm.NewClient(cfg.LLM)
	llmNarrator := narrator.New(llmClient, cfg.LLM)

	store := alertmanager.NewStore(qe)
	var v1Narrator alertmanager.VerdictNarrator
	if cfg.LLM.NarrationEnabled {
		v1Narrator = llmNarrator
	}
	alertMgr := alertmanager.NewManager(store, ddEngine, v1Narrator, cfg.Detection, logger)

	// ── Dual-resolution detection + investigation pipeline ───────────────────
	metricRegistry, err := anomalydetector.DefaultMetricRegistry()
	if err != nil {
		logger.Error("metric registry initialization failed", slog.Any("error", err))
		os.Exit(1)
	}
	v2Scanner := detectionv2.NewScanner(qe, metricRegistry, cfg.Detection)
	v2Repo := detectionv2.NewRepository(qe)
	queryValidator := investigation.NewValidator(cfg.Detection)
	agentExecutor := investigation.NewQueryExecutor(qe)
	canonicalVerifier := investigation.NewVerifier(qe, metricRegistry, cfg.Detection)
	investigationStore := investigation.NewStore(qe)
	investigationAgent := investigation.NewAgent(llmClient, queryValidator, agentExecutor, canonicalVerifier, investigationStore, cfg.LLM, logger)
	v2Pipeline := detectionv2.NewPipeline(qe, v2Scanner, v2Repo, investigationAgent, llmNarrator, metricRegistry, cfg.Detection, cfg.LLM, logger)
	if err := v2Pipeline.CompileTemplates(ctx); err != nil {
		logger.Warn("detection v2 template compilation failed (non-fatal)", slog.Any("error", err))
	}
	schedulerCtx, stopScheduler := context.WithCancel(context.Background())
	defer stopScheduler()
	v2Pipeline.StartScheduler(schedulerCtx)

	// ── HTTP server ───────────────────────────────────────────────────────────
	srv := httpserver.New(chClient, cfg, zapLogger, detEngine, alertMgr, v2Pipeline, logger)

	httpSrv := &http.Server{
		Addr:        ":" + cfg.ServerPort,
		Handler:     srv.Handler(),
		ReadTimeout: 15 * time.Second,
		// /upload streams and batch-inserts arbitrarily large CSV/Parquet files
		// (a full 9M-row backfill takes several minutes) — 30s cut the response
		// off mid-insert while the data still landed, leaving the client with a
		// dropped connection instead of a confirmation. All other routes return
		// in milliseconds, so this only matters for that one endpoint.
		WriteTimeout: 10 * time.Minute,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		zapLogger.Info("server listening", zap.String("port", cfg.ServerPort))
		if err := httpSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			zapLogger.Error("server error", zap.Error(err))
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("shutting down")
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := httpSrv.Shutdown(shutdownCtx); err != nil {
		zapLogger.Error("shutdown error", zap.Error(err))
	}
}
