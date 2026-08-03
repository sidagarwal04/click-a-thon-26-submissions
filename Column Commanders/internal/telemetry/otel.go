package telemetry

import (
	"context"
	"fmt"
	"os"

	"github.com/hyperdxio/opentelemetry-go/otelzap"
	"github.com/hyperdxio/opentelemetry-logs-go/exporters/otlp/otlplogs"
	sdk "github.com/hyperdxio/opentelemetry-logs-go/sdk/logs"
	"github.com/hyperdxio/otel-config-go/otelconfig"
	"go.opentelemetry.io/otel/trace"
	"go.uber.org/zap"
)

// Setup initialises the OpenTelemetry SDK and returns a zap.Logger wired to the
// OTel log provider plus a shutdown function that must be deferred by the caller.
//
// When OTEL_EXPORTER_OTLP_ENDPOINT is not set the function returns a plain JSON
// production logger so the service works in local dev without any collector.
// When the ClickStack endpoint IS set but the collector is unreachable, Setup
// logs a warning and falls back to the plain logger instead of crashing.
func Setup(ctx context.Context, serviceName string) (logger *zap.Logger, shutdown func(), err error) {
	// Fall back to plain JSON logger when no OTLP endpoint is configured.
	otlpEndpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if otlpEndpoint == "" {
		l, _ := zap.NewProduction()
		return l, func() { _ = l.Sync() }, nil
	}

	if serviceName != "" {
		_ = os.Setenv("OTEL_SERVICE_NAME", serviceName)
	}

	otelShutdown, configErr := otelconfig.ConfigureOpenTelemetry()
	if configErr != nil {
		// ClickStack collector is configured but unavailable — degrade gracefully.
		fmt.Fprintf(os.Stderr, "warning: clickstack setup failed (%q): %v — running without ClickStack\n",
			otlpEndpoint, configErr)
		l, _ := zap.NewProduction()
		return l, func() { _ = l.Sync() }, nil
	}

	logExporter, err := otlplogs.NewExporter(ctx)
	if err != nil {
		otelShutdown()
		return nil, nil, fmt.Errorf("create log exporter: %w", err)
	}

	loggerProvider := sdk.NewLoggerProvider(sdk.WithBatcher(logExporter))

	logger = zap.New(otelzap.NewOtelCore(loggerProvider))
	zap.ReplaceGlobals(logger)

	shutdown = func() {
		_ = loggerProvider.Shutdown(ctx)
		otelShutdown()
	}
	return logger, shutdown, nil
}

// WithTraceMetadata attaches the active span's trace_id and span_id fields to
// the logger so every log line is correlated with its trace in ClickStack.
func WithTraceMetadata(ctx context.Context, logger *zap.Logger) *zap.Logger {
	span := trace.SpanContextFromContext(ctx)
	if !span.IsValid() {
		return logger
	}
	return logger.With(
		zap.String("trace_id", span.TraceID().String()),
		zap.String("span_id", span.SpanID().String()),
	)
}
