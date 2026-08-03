package telemetry

import (
	"context"
	"encoding/base64"
	"os"
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

func Configure(ctx context.Context) (trace.Tracer, func(context.Context) error, error) {
	publicKey := strings.TrimSpace(os.Getenv("LANGFUSE_PUBLIC_KEY"))
	secretKey := strings.TrimSpace(os.Getenv("LANGFUSE_SECRET_KEY"))
	if publicKey == "" || secretKey == "" {
		return otel.Tracer("featurelens"), func(context.Context) error { return nil }, nil
	}
	baseURL := strings.TrimRight(envDefault("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"), "/")
	authorization := "Basic " + base64.StdEncoding.EncodeToString([]byte(publicKey+":"+secretKey))
	exporter, err := otlptracehttp.New(ctx,
		otlptracehttp.WithEndpointURL(baseURL+"/api/public/otel/v1/traces"),
		otlptracehttp.WithHeaders(map[string]string{
			"Authorization":                authorization,
			"x-langfuse-ingestion-version": "4",
		}),
	)
	if err != nil {
		return nil, nil, err
	}
	resourceAttributes := []attribute.KeyValue{semconv.ServiceName("featurelens-go")}
	if environment := strings.TrimSpace(os.Getenv("LANGFUSE_TRACING_ENVIRONMENT")); environment != "" {
		resourceAttributes = append(resourceAttributes, attribute.String("langfuse.environment", environment))
	}
	if release := strings.TrimSpace(os.Getenv("LANGFUSE_RELEASE")); release != "" {
		resourceAttributes = append(resourceAttributes, attribute.String("langfuse.release", release))
	}
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewWithAttributes(semconv.SchemaURL, resourceAttributes...)),
	)
	otel.SetTracerProvider(provider)
	return provider.Tracer("featurelens"), provider.Shutdown, nil
}

// Enabled reports whether the process has enough configuration to export traces.
// It intentionally exposes configuration state without ever exposing credentials.
func Enabled() bool {
	return strings.TrimSpace(os.Getenv("LANGFUSE_PUBLIC_KEY")) != "" &&
		strings.TrimSpace(os.Getenv("LANGFUSE_SECRET_KEY")) != ""
}

func envDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
