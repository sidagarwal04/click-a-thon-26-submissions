package otelemit

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client POSTs OTLP/HTTP JSON payloads to a collector. It is not the
// go.opentelemetry.io SDK — see the package doc for why.
type Client struct {
	endpoint   string // e.g. http://localhost:4318, NO trailing slash, NO /v1/... suffix
	key        string
	httpClient *http.Client
}

// New builds a Client. endpoint is the collector base (http://localhost:4318);
// key is the ingestion key from `tools/clickstack-bootstrap.sh`, sent as the
// `authorization` header — VERIFIED.md: a request with no key gets 401.
func New(endpoint, key string) *Client {
	return &Client{
		endpoint: endpoint,
		key:      key,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// UnixNano renders a time.Time as the string OTLP/HTTP JSON wants for
// *TimeUnixNano fields — a decimal string, not a JSON number (int64 ns since
// epoch overflows float64's exact-integer range well within this decade).
func UnixNano(t time.Time) string {
	return formatInt(t.UnixNano())
}

func (c *Client) PostMetrics(ctx context.Context, payload MetricsPayload) error {
	return c.post(ctx, "/v1/metrics", payload)
}

func (c *Client) PostLogs(ctx context.Context, payload LogsPayload) error {
	return c.post(ctx, "/v1/logs", payload)
}

func (c *Client) PostTraces(ctx context.Context, payload TracesPayload) error {
	return c.post(ctx, "/v1/traces", payload)
}

func (c *Client) post(ctx context.Context, path string, v any) error {
	body, err := json.Marshal(v)
	if err != nil {
		return fmt.Errorf("marshal otlp payload for %s: %w", path, err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.endpoint+path, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build otlp request for %s: %w", path, err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("authorization", c.key)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("post %s to %s: %w", path, c.endpoint, err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("post %s to %s: HTTP %d: %s", path, c.endpoint, resp.StatusCode, respBody)
	}
	return nil
}
