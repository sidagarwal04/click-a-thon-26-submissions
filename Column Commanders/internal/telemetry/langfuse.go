package telemetry

// Langfuse tracing — dedicated TracerProvider that exports only to Langfuse.
//
// This is intentionally separate from the ClickStack OTLP setup in otel.go.
// ClickStack receives ALL OTel signals (traces, metrics, logs) from the service.
// Langfuse receives ONLY the upload-pipeline spans created via Tracer()/StartSpan().
//
// Spans sent to Langfuse are independent root traces — they do NOT inherit the
// ClickStack HTTP span as a parent, keeping the two backends cleanly separated.
//
// Required env vars:
//   LANGFUSE_OTLP_ENDPOINT  – full traces endpoint, e.g.
//                              https://jp.cloud.langfuse.com/api/public/otel/v1/traces
//   LANGFUSE_OTLP_HEADERS   – comma-separated key=value pairs, e.g.
//                              Authorization=Basic <base64>,x-langfuse-ingestion-version=4

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	otlptracehttp "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	sdkresource "go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/trace"
)

const instrumentationScope = "clickhouse-go-service"

// langfuseTP is the dedicated TracerProvider that sends spans to Langfuse.
// Nil until InitLangfuse is called; Tracer() falls back to the global (no-op) tracer.
var langfuseTP *sdktrace.TracerProvider

// InitLangfuse creates a dedicated OTLP HTTP trace exporter for Langfuse and
// stores it in the package-level langfuseTP. Returns a shutdown function.
// If LANGFUSE_OTLP_ENDPOINT is unset, this is a no-op and Tracer() returns
// the global no-op tracer so spans are silently discarded.
func InitLangfuse(ctx context.Context, serviceName string) (func(), error) {
	endpoint := os.Getenv("LANGFUSE_OTLP_ENDPOINT")
	if endpoint == "" {
		return func() {}, nil
	}

	headers := parseLangfuseHeaders(os.Getenv("LANGFUSE_OTLP_HEADERS"))

	// WithEndpointURL requires otlptracehttp >= v1.22; we target v1.18 which
	// uses WithEndpoint(host) + WithURLPath(path) + optional WithInsecure().
	u, err := url.Parse(endpoint)
	if err != nil {
		return nil, fmt.Errorf("parse LANGFUSE_OTLP_ENDPOINT: %w", err)
	}
	opts := []otlptracehttp.Option{
		otlptracehttp.WithEndpoint(u.Host),
		otlptracehttp.WithURLPath(u.Path),
		otlptracehttp.WithHeaders(headers),
	}
	if u.Scheme == "http" {
		opts = append(opts, otlptracehttp.WithInsecure())
	}

	exporter, err := otlptracehttp.New(ctx, opts...)
	if err != nil {
		return nil, fmt.Errorf("create langfuse exporter: %w", err)
	}

	res, _ := sdkresource.New(ctx, sdkresource.WithAttributes(
		attribute.String("service.name", serviceName),
	))

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)
	langfuseTP = tp

	return func() { _ = tp.Shutdown(ctx) }, nil
}

// Tracer returns the Langfuse-dedicated tracer. If InitLangfuse was not called
// or LANGFUSE_OTLP_ENDPOINT was not set, returns the global no-op tracer.
func Tracer() trace.Tracer {
	if langfuseTP != nil {
		return langfuseTP.Tracer(instrumentationScope)
	}
	return otel.Tracer(instrumentationScope)
}

// NewLangfuseTrace starts a new root span for the upload pipeline in Langfuse.
// It uses context.Background() so the trace is fully independent of the
// ClickStack HTTP span — ClickStack and Langfuse see separate trace trees.
// The caller MUST call span.End() when the operation completes.
func NewLangfuseTrace(name string) (context.Context, trace.Span) {
	return Tracer().Start(context.Background(), name)
}

// StartSpan creates a named child span under ctx using the Langfuse tracer.
// The caller MUST call span.End() when the operation completes.
func StartSpan(ctx context.Context, name string) (context.Context, trace.Span) {
	return Tracer().Start(ctx, name)
}

// SetTraceName sets the human-readable trace name visible in the Langfuse UI,
// overriding the default span name.
func SetTraceName(span trace.Span, name string) {
	span.SetAttributes(attribute.String("langfuse.trace.name", name))
}

// SetSpanInput records the meaningful input for this observation in Langfuse.
// Pass only non-sensitive data — never include API keys, passwords, or PII.
func SetSpanInput(span trace.Span, input any) {
	b, err := json.Marshal(input)
	if err != nil {
		return
	}
	span.SetAttributes(attribute.String("langfuse.observation.input", string(b)))
}

// SetSpanOutput records the result of this observation in Langfuse.
func SetSpanOutput(span trace.Span, output any) {
	b, err := json.Marshal(output)
	if err != nil {
		return
	}
	span.SetAttributes(attribute.String("langfuse.observation.output", string(b)))
}

// RecordSpanError marks the span as an error in both OTel status and Langfuse level.
func RecordSpanError(span trace.Span, err error) {
	span.RecordError(err)
	span.SetStatus(codes.Error, err.Error())
	span.SetAttributes(
		attribute.String("langfuse.observation.level", "ERROR"),
		attribute.String("langfuse.observation.status_message", err.Error()),
	)
}

// parseLangfuseHeaders parses a "key=value,key2=value2" header string into a map.
// Only the first '=' in each pair is treated as the delimiter, so values that
// contain '=' (e.g. base64-encoded auth tokens) are handled correctly.
func parseLangfuseHeaders(raw string) map[string]string {
	headers := make(map[string]string)
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if i := strings.IndexByte(part, '='); i > 0 {
			headers[strings.TrimSpace(part[:i])] = strings.TrimSpace(part[i+1:])
		}
	}
	return headers
}
