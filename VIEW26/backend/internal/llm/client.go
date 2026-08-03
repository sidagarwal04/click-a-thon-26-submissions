package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/view26/featurelens/internal/agent"
	"github.com/view26/featurelens/internal/domain"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

type Config struct {
	Provider      string
	BaseURL       string
	APIKey        string
	Model         string
	PromptVersion string
	Timeout       time.Duration
	HTTPClient    *http.Client
}

type Client struct {
	config Config
	http   *http.Client
	tracer trace.Tracer
}

func FromEnv(tracer trace.Tracer) *Client {
	timeout := 30 * time.Second
	if value := strings.TrimSpace(os.Getenv("LLM_TIMEOUT")); value != "" {
		if parsed, err := time.ParseDuration(value); err == nil {
			timeout = parsed
		}
	}
	return New(Config{
		Provider:      envDefault("LLM_PROVIDER", "openai-compatible"),
		BaseURL:       envDefault("LLM_BASE_URL", "https://api.openai.com/v1"),
		APIKey:        strings.TrimSpace(os.Getenv("LLM_API_KEY")),
		Model:         strings.TrimSpace(os.Getenv("LLM_MODEL")),
		PromptVersion: envDefault("LLM_PROMPT_VERSION", agent.AnalyticsPromptVersion),
		Timeout:       timeout,
	}, tracer)
}

func New(config Config, tracer trace.Tracer) *Client {
	if config.PromptVersion == "" {
		config.PromptVersion = agent.AnalyticsPromptVersion
	}
	if config.Timeout <= 0 {
		config.Timeout = 30 * time.Second
	}
	httpClient := config.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: config.Timeout}
	}
	return &Client{config: config, http: httpClient, tracer: tracer}
}

func (c *Client) Enabled() bool {
	return c != nil && strings.TrimSpace(c.config.APIKey) != "" && strings.TrimSpace(c.config.Model) != ""
}

func (c *Client) Metadata() domain.InsightProvenance {
	return domain.InsightProvenance{
		Provider: c.config.Provider, Model: c.config.Model, PromptVersion: c.config.PromptVersion,
	}
}

func (c *Client) Synthesize(ctx context.Context, input agent.InsightSynthesisRequest) (agent.InsightSynthesis, error) {
	if !c.Enabled() {
		return agent.InsightSynthesis{}, errors.New("LLM synthesis is not configured")
	}
	payload, err := json.Marshal(input)
	if err != nil {
		return agent.InsightSynthesis{}, fmt.Errorf("marshal governed synthesis input: %w", err)
	}
	requestBody := map[string]any{
		"model": c.config.Model,
		"messages": []map[string]string{
			{"role": "system", "content": agent.AnalyticsSystemPrompt},
			{"role": "user", "content": string(payload)},
		},
		"temperature": 0.1,
		"response_format": map[string]any{
			"type": "json_schema",
			"json_schema": map[string]any{
				"name":   "featurelens_analytics_insight",
				"strict": true,
				"schema": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"headline":           map[string]any{"type": "string", "description": "Concise product-facing finding grounded in the supplied aggregates."},
						"summary":            map[string]any{"type": "string", "description": "What changed and the key aggregate values."},
						"why":                map[string]any{"type": "string", "description": "Business interpretation that respects known issues and limitations."},
						"confidence":         map[string]any{"type": "number", "minimum": 0, "maximum": 1},
						"recommended_action": map[string]any{"type": "string", "description": "Concrete next step for the requested role, naming the specific target from the evidence."},
						"key_findings": map[string]any{
							"type":        "array",
							"description": "2-4 ranked, evidence-grounded findings ordered by impact, most important first.",
							"minItems":    1,
							"maxItems":    4,
							"items": map[string]any{
								"type": "object",
								"properties": map[string]any{
									"point":    map[string]any{"type": "string", "description": "The specific observation, quantified from the evidence (exact stage, segment, or metric and its value)."},
									"why":      map[string]any{"type": "string", "description": "Why THIS finding matters to the PM and what decision it informs; never generic."},
									"evidence": map[string]any{"type": "string", "description": "The metric, funnel stage, or segment name this finding is grounded in."},
									"severity": map[string]any{"type": "string", "description": "Impact tier for ordering and emphasis: one of high, medium, or low."},
								},
								"required":             []string{"point", "why", "evidence", "severity"},
								"additionalProperties": false,
							},
						},
					},
					"required":             []string{"headline", "summary", "why", "confidence", "recommended_action", "key_findings"},
					"additionalProperties": false,
				},
			},
		},
	}
	if strings.EqualFold(c.config.Provider, "openrouter") {
		requestBody["provider"] = map[string]any{"require_parameters": true}
	}
	body, err := json.Marshal(requestBody)
	if err != nil {
		return agent.InsightSynthesis{}, fmt.Errorf("marshal LLM request: %w", err)
	}

	ctx, span := c.tracer.Start(ctx, "analytics.llm_synthesize", trace.WithAttributes(
		attribute.String("langfuse.observation.type", "generation"),
		attribute.String("langfuse.observation.input", string(payload)),
		attribute.String("gen_ai.system", c.config.Provider),
		attribute.String("gen_ai.request.model", c.config.Model),
		attribute.String("analytics.prompt_version", c.config.PromptVersion),
		attribute.String("analytics.role", input.Contract.Role),
		attribute.String("analytics.playbook", input.Contract.Playbook),
		attribute.Int("analytics.context_version", input.Contract.ContextVersion),
		attribute.String("analytics.governed_input", truncate(string(payload), 16000)),
	))
	defer span.End()

	request, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(c.config.BaseURL, "/")+"/chat/completions", bytes.NewReader(body))
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "create request")
		return agent.InsightSynthesis{}, err
	}
	request.Header.Set("Authorization", "Bearer "+c.config.APIKey)
	request.Header.Set("Content-Type", "application/json")
	response, err := c.http.Do(request)
	if err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "LLM request failed")
		return agent.InsightSynthesis{}, fmt.Errorf("LLM request: %w", err)
	}
	defer response.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if err != nil {
		return agent.InsightSynthesis{}, fmt.Errorf("read LLM response: %w", err)
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		err = fmt.Errorf("LLM returned HTTP %d: %s", response.StatusCode, truncate(string(responseBody), 512))
		span.RecordError(err)
		span.SetStatus(codes.Error, "LLM HTTP error")
		return agent.InsightSynthesis{}, err
	}
	var envelope struct {
		Model   string `json:"model"`
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Usage map[string]any `json:"usage"`
	}
	if err := json.Unmarshal(responseBody, &envelope); err != nil || len(envelope.Choices) == 0 {
		return agent.InsightSynthesis{}, errors.New("LLM response did not contain a completion")
	}
	content := stripCodeFence(envelope.Choices[0].Message.Content)
	var synthesis agent.InsightSynthesis
	if err := json.Unmarshal([]byte(content), &synthesis); err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "invalid structured insight")
		return agent.InsightSynthesis{}, fmt.Errorf("decode structured insight: %w", err)
	}
	if err := validate(synthesis); err != nil {
		span.RecordError(err)
		span.SetStatus(codes.Error, "unsafe structured insight")
		return agent.InsightSynthesis{}, err
	}
	synthesis.ObservationID = span.SpanContext().SpanID().String()
	attributes := []attribute.KeyValue{
		attribute.String("analytics.generated_insight", truncate(content, 8000)),
		attribute.String("langfuse.observation.output", content),
	}
	if envelope.Model != "" {
		attributes = append(attributes, attribute.String("gen_ai.response.model", envelope.Model))
	}
	if inputTokens := usageInt(envelope.Usage, "prompt_tokens", "input_tokens"); inputTokens > 0 {
		attributes = append(attributes, attribute.Int64("gen_ai.usage.input_tokens", inputTokens))
	}
	if outputTokens := usageInt(envelope.Usage, "completion_tokens", "output_tokens"); outputTokens > 0 {
		attributes = append(attributes, attribute.Int64("gen_ai.usage.output_tokens", outputTokens))
	}
	span.SetAttributes(attributes...)
	span.SetStatus(codes.Ok, "governed insight generated")
	return synthesis, nil
}

func usageInt(usage map[string]any, keys ...string) int64 {
	for _, key := range keys {
		switch value := usage[key].(type) {
		case float64:
			return int64(value)
		case int64:
			return value
		case json.Number:
			parsed, _ := value.Int64()
			return parsed
		}
	}
	return 0
}

func validate(value agent.InsightSynthesis) error {
	fields := map[string]struct {
		value string
		max   int
	}{
		"headline": {value.Headline, 240}, "summary": {value.Summary, 1200}, "why": {value.Why, 1200},
		"recommended_action": {value.RecommendedAction, 600},
	}
	for name, field := range fields {
		if strings.TrimSpace(field.value) == "" {
			return fmt.Errorf("LLM insight field %s is empty", name)
		}
		if len(field.value) > field.max {
			return fmt.Errorf("LLM insight field %s exceeds %d characters", name, field.max)
		}
	}
	if value.Confidence < 0 || value.Confidence > 1 {
		return errors.New("LLM insight confidence must be between 0 and 1")
	}
	if len(value.KeyFindings) > 4 {
		return fmt.Errorf("LLM insight returned %d key findings; at most 4 are allowed", len(value.KeyFindings))
	}
	for index, finding := range value.KeyFindings {
		if strings.TrimSpace(finding.Point) == "" || strings.TrimSpace(finding.Why) == "" {
			return fmt.Errorf("LLM insight key finding %d is missing its point or why", index+1)
		}
		if len(finding.Point) > 400 || len(finding.Why) > 600 {
			return fmt.Errorf("LLM insight key finding %d exceeds the length budget", index+1)
		}
	}
	return nil
}

func stripCodeFence(value string) string {
	value = strings.TrimSpace(value)
	if strings.HasPrefix(value, "```") {
		value = strings.TrimPrefix(value, "```json")
		value = strings.TrimPrefix(value, "```")
		value = strings.TrimSuffix(value, "```")
	}
	return strings.TrimSpace(value)
}

func truncate(value string, limit int) string {
	if len(value) <= limit {
		return value
	}
	return value[:limit] + "…"
}

func envDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
