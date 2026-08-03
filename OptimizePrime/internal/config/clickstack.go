package config

// ClickStack holds the settings needed to emit OTLP telemetry to our own
// ClickStack collector. A separate file from config.go on purpose: it is
// additive (new env vars, same .env) and keeps the Cloud/local ClickHouse
// loading path — which is load-bearing for the whole rest of the repo —
// untouched by H7 instrumentation work.
type ClickStack struct {
	// Endpoint is the OTLP/HTTP collector base, no trailing slash and no
	// /v1/... suffix. OTLP 4317/4318 do not bind until a team exists
	// (tools/clickstack-bootstrap.sh), and the collector binds LATE even
	// after that — callers should expect the first request or two to fail on
	// a freshly started stack.
	Endpoint string
	// IngestionKey is sent as the `authorization` header. A request with no
	// key gets 401 — VERIFIED.md.
	IngestionKey string
	// ServiceName tags every span/log/metric this binary emits, so a judge
	// filtering by service in HyperDX sees only our self-observation and
	// never the concurrency data it charts separately.
	ServiceName string
}

// LoadClickStack reads CLICKSTACK_OTLP / CLICKSTACK_INGESTION_KEY from the
// environment. It does not require the key: a caller may want to construct
// telemetry and only fail at emit time with a clear "who is missing" error,
// rather than refusing to even compute the numbers.
func LoadClickStack() ClickStack {
	return ClickStack{
		Endpoint:     envStr("CLICKSTACK_OTLP", "http://localhost:4318"),
		IngestionKey: envStr("CLICKSTACK_INGESTION_KEY", ""),
		ServiceName:  envStr("CLICKSTACK_SERVICE_NAME", "sonyliv-pipeline"),
	}
}
