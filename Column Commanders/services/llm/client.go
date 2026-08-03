package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"

	"clickhouse-go-service/internal/config"
)

type Client struct {
	apiKey          string
	baseURL         string
	reasoningEffort string
	maxOutputTokens int
	httpClient      *http.Client
}

func NewClient(cfg config.LLMConfig) *Client {
	return &Client{
		apiKey: cfg.APIKey, baseURL: strings.TrimRight(cfg.BaseURL, "/"),
		reasoningEffort: cfg.ReasoningEffort, maxOutputTokens: cfg.MaxOutputTokens,
		httpClient: &http.Client{Timeout: cfg.RequestTimeout},
	}
}

func NewClientWithHTTP(cfg config.LLMConfig, client *http.Client) *Client {
	result := NewClient(cfg)
	result.httpClient = client
	return result
}

type responseRequest struct {
	Model           string         `json:"model"`
	Instructions    string         `json:"instructions"`
	Input           string         `json:"input"`
	Store           bool           `json:"store"`
	Reasoning       map[string]any `json:"reasoning,omitempty"`
	Text            responseText   `json:"text"`
	MaxOutputTokens int            `json:"max_output_tokens"`
}

type responseText struct {
	Format responseFormat `json:"format"`
}

type responseFormat struct {
	Type   string         `json:"type"`
	Name   string         `json:"name"`
	Strict bool           `json:"strict"`
	Schema map[string]any `json:"schema"`
}

type apiResponse struct {
	ID                string `json:"id"`
	Status            string `json:"status"`
	IncompleteDetails struct {
		Reason string `json:"reason"`
	} `json:"incomplete_details"`
	Output []struct {
		Type    string `json:"type"`
		Content []struct {
			Type    string `json:"type"`
			Text    string `json:"text"`
			Refusal string `json:"refusal"`
		} `json:"content"`
	} `json:"output"`
	Error *struct {
		Message string `json:"message"`
		Type    string `json:"type"`
	} `json:"error"`
}

func (c *Client) GenerateJSON(ctx context.Context, model, schemaName, instructions, input string, schema map[string]any, output any) (string, error) {
	if strings.TrimSpace(c.apiKey) == "" {
		return "", errors.New("openai api key is empty")
	}
	requestBody := responseRequest{
		Model: model, Instructions: instructions, Input: input, Store: false,
		Text:            responseText{Format: responseFormat{Type: "json_schema", Name: schemaName, Strict: true, Schema: schema}},
		MaxOutputTokens: c.maxOutputTokens,
	}
	if c.reasoningEffort != "" {
		requestBody.Reasoning = map[string]any{"effort": c.reasoningEffort}
	}
	body, err := json.Marshal(requestBody)
	if err != nil {
		return "", fmt.Errorf("marshal OpenAI request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/responses", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("create OpenAI request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("call OpenAI Responses API: %w", err)
	}
	defer resp.Body.Close()
	responseBody, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return "", fmt.Errorf("read OpenAI response: %w", err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var apiErr struct {
			Error struct {
				Message string `json:"message"`
			} `json:"error"`
		}
		_ = json.Unmarshal(responseBody, &apiErr)
		if apiErr.Error.Message == "" {
			apiErr.Error.Message = strings.TrimSpace(string(responseBody))
		}
		return "", fmt.Errorf("OpenAI Responses API status %d: %s", resp.StatusCode, apiErr.Error.Message)
	}

	var decoded apiResponse
	if err := json.Unmarshal(responseBody, &decoded); err != nil {
		return "", fmt.Errorf("decode OpenAI response: %w", err)
	}
	if decoded.Error != nil {
		return decoded.ID, fmt.Errorf("OpenAI response error: %s", decoded.Error.Message)
	}
	if decoded.Status != "completed" {
		return decoded.ID, fmt.Errorf("OpenAI response status %q: %s", decoded.Status, decoded.IncompleteDetails.Reason)
	}
	var outputText string
	for _, item := range decoded.Output {
		if item.Type != "message" {
			continue
		}
		for _, content := range item.Content {
			switch content.Type {
			case "output_text":
				outputText += content.Text
			case "refusal":
				return decoded.ID, fmt.Errorf("OpenAI refusal: %s", content.Refusal)
			}
		}
	}
	if strings.TrimSpace(outputText) == "" {
		return decoded.ID, errors.New("OpenAI response contained no output text")
	}
	if err := json.Unmarshal([]byte(outputText), output); err != nil {
		return decoded.ID, fmt.Errorf("decode structured OpenAI output: %w", err)
	}
	return decoded.ID, nil
}
