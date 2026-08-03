package langfuse

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

var ErrDisabled = errors.New("Langfuse is not configured")

type Config struct {
	BaseURL    string
	PublicKey  string
	SecretKey  string
	HTTPClient *http.Client
}

type Client struct {
	baseURL   string
	publicKey string
	secretKey string
	http      *http.Client
}

type Observation struct {
	ID                  string         `json:"id"`
	TraceID             string         `json:"trace_id"`
	ProjectID           string         `json:"project_id,omitempty"`
	ParentObservationID string         `json:"parent_observation_id,omitempty"`
	Name                string         `json:"name,omitempty"`
	Type                string         `json:"type,omitempty"`
	Level               string         `json:"level,omitempty"`
	StatusMessage       string         `json:"status_message,omitempty"`
	Version             string         `json:"version,omitempty"`
	Environment         string         `json:"environment,omitempty"`
	StartTime           string         `json:"start_time,omitempty"`
	EndTime             string         `json:"end_time,omitempty"`
	Input               any            `json:"input,omitempty"`
	Output              any            `json:"output,omitempty"`
	Metadata            map[string]any `json:"metadata,omitempty"`
	Model               string         `json:"model,omitempty"`
	Usage               map[string]any `json:"usage,omitempty"`
	Cost                float64        `json:"cost,omitempty"`
	Latency             float64        `json:"latency,omitempty"`
	TraceName           string         `json:"trace_name,omitempty"`
	Tags                []string       `json:"tags,omitempty"`
	Release             string         `json:"release,omitempty"`
}

type ScoreSubject struct {
	Kind    string `json:"kind"`
	ID      string `json:"id"`
	TraceID string `json:"trace_id,omitempty"`
}

type Score struct {
	ID           string         `json:"id"`
	Name         string         `json:"name"`
	Value        any            `json:"value"`
	DataType     string         `json:"data_type"`
	Source       string         `json:"source"`
	Timestamp    string         `json:"timestamp,omitempty"`
	Environment  string         `json:"environment,omitempty"`
	Comment      string         `json:"comment,omitempty"`
	Metadata     map[string]any `json:"metadata,omitempty"`
	AuthorUserID string         `json:"author_user_id,omitempty"`
	QueueID      string         `json:"queue_id,omitempty"`
	Subject      ScoreSubject   `json:"subject"`
}

type TraceSummary struct {
	ObservationCount int     `json:"observation_count"`
	ScoreCount       int     `json:"score_count"`
	GenerationCount  int     `json:"generation_count"`
	TotalCost        float64 `json:"total_cost"`
	TotalTokens      float64 `json:"total_tokens"`
	Latency          float64 `json:"latency"`
}

type TraceInsights struct {
	Enabled      bool          `json:"enabled"`
	Status       string        `json:"status"`
	TraceID      string        `json:"trace_id"`
	ProjectID    string        `json:"project_id,omitempty"`
	URL          string        `json:"url,omitempty"`
	Observations []Observation `json:"observations"`
	Scores       []Score       `json:"scores"`
	Summary      TraceSummary  `json:"summary"`
	FetchedAt    time.Time     `json:"fetched_at"`
}

type FeedbackRequest struct {
	TraceID       string
	ObservationID string
	Helpful       bool
	Issue         string
	Comment       string
	Actor         string
}

func FromEnv() *Client {
	return New(Config{
		BaseURL:   envDefault("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
		PublicKey: strings.TrimSpace(os.Getenv("LANGFUSE_PUBLIC_KEY")),
		SecretKey: strings.TrimSpace(os.Getenv("LANGFUSE_SECRET_KEY")),
	})
}

func New(config Config) *Client {
	httpClient := config.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Second}
	}
	return &Client{
		baseURL: strings.TrimRight(config.BaseURL, "/"), publicKey: strings.TrimSpace(config.PublicKey),
		secretKey: strings.TrimSpace(config.SecretKey), http: httpClient,
	}
}

func (c *Client) Enabled() bool {
	return c != nil && c.publicKey != "" && c.secretKey != "" && c.baseURL != ""
}

func (c *Client) TraceInsights(ctx context.Context, traceID string) (TraceInsights, error) {
	if !c.Enabled() {
		return TraceInsights{Enabled: false, Status: "disabled", TraceID: traceID, Observations: []Observation{}, Scores: []Score{}, FetchedAt: time.Now().UTC()}, nil
	}
	observations, err := c.observations(ctx, traceID)
	if err != nil {
		return TraceInsights{}, err
	}
	scores, err := c.scores(ctx, traceID)
	if err != nil {
		return TraceInsights{}, err
	}
	projectID := ""
	if len(observations) > 0 {
		projectID = observations[0].ProjectID
	}
	status := "pending"
	if len(observations) > 0 {
		status = "synced"
	}
	result := TraceInsights{
		Enabled: true, Status: status, TraceID: traceID, ProjectID: projectID,
		Observations: observations, Scores: scores, FetchedAt: time.Now().UTC(),
	}
	if projectID != "" {
		result.URL = c.baseURL + "/project/" + url.PathEscape(projectID) + "/traces/" + url.PathEscape(traceID)
	}
	result.Summary = summarize(observations, scores)
	return result, nil
}

func (c *Client) CreateFeedback(ctx context.Context, request FeedbackRequest) ([]Score, error) {
	if !c.Enabled() {
		return nil, ErrDisabled
	}
	metadata := map[string]any{"channel": "featurelens_trace_explorer"}
	if request.Actor != "" {
		metadata["actor"] = request.Actor
	}
	if request.Issue != "" {
		metadata["issue_category"] = request.Issue
	}
	created := make([]Score, 0, 2)
	helpful, err := c.createScore(ctx, scoreCreateRequest{
		ID: stableScoreID(request.TraceID, request.Actor, "user_helpful"), TraceID: request.TraceID,
		ObservationID: request.ObservationID, Name: "user_helpful", Value: request.Helpful,
		DataType: "BOOLEAN", Comment: request.Comment, Metadata: metadata,
	})
	if err != nil {
		return nil, err
	}
	created = append(created, helpful)
	if request.Issue != "" {
		issue, issueErr := c.createScore(ctx, scoreCreateRequest{
			ID: stableScoreID(request.TraceID, request.Actor, "issue_category"), TraceID: request.TraceID,
			ObservationID: request.ObservationID, Name: "issue_category", Value: request.Issue,
			DataType: "CATEGORICAL", Comment: request.Comment, Metadata: metadata,
		})
		if issueErr != nil {
			return created, fmt.Errorf("helpfulness saved but issue category failed: %w", issueErr)
		}
		created = append(created, issue)
	}
	return created, nil
}

type observationAPI struct {
	ID                  string         `json:"id"`
	TraceID             string         `json:"traceId"`
	ProjectID           string         `json:"projectId"`
	ParentObservationID string         `json:"parentObservationId"`
	Name                string         `json:"name"`
	Type                string         `json:"type"`
	Level               string         `json:"level"`
	StatusMessage       string         `json:"statusMessage"`
	Version             string         `json:"version"`
	Environment         string         `json:"environment"`
	StartTime           string         `json:"startTime"`
	EndTime             string         `json:"endTime"`
	Input               any            `json:"input"`
	Output              any            `json:"output"`
	Metadata            map[string]any `json:"metadata"`
	ProvidedModelName   string         `json:"providedModelName"`
	UsageDetails        map[string]any `json:"usageDetails"`
	TotalCost           any            `json:"totalCost"`
	Latency             any            `json:"latency"`
	TraceName           string         `json:"traceName"`
	Tags                []string       `json:"tags"`
	Release             string         `json:"release"`
}

type scoreAPI struct {
	ID           string         `json:"id"`
	Name         string         `json:"name"`
	Value        any            `json:"value"`
	DataType     string         `json:"dataType"`
	Source       string         `json:"source"`
	Timestamp    string         `json:"timestamp"`
	Environment  string         `json:"environment"`
	Comment      string         `json:"comment"`
	Metadata     map[string]any `json:"metadata"`
	AuthorUserID string         `json:"authorUserId"`
	QueueID      string         `json:"queueId"`
	Subject      struct {
		Kind    string `json:"kind"`
		ID      string `json:"id"`
		TraceID string `json:"traceId"`
	} `json:"subject"`
}

func (c *Client) observations(ctx context.Context, traceID string) ([]Observation, error) {
	values := url.Values{
		"traceId": {traceID}, "fields": {"core,basic,time,io,metadata,model,usage,metrics,trace_context"}, "limit": {"1000"},
	}
	result := make([]Observation, 0)
	for page := 0; page < 10; page++ {
		var response struct {
			Data []observationAPI `json:"data"`
			Meta struct {
				Cursor string `json:"cursor"`
			} `json:"meta"`
		}
		if err := c.get(ctx, "/api/public/v2/observations", values, &response); err != nil {
			return nil, fmt.Errorf("read Langfuse observations: %w", err)
		}
		for _, item := range response.Data {
			result = append(result, Observation{
				ID: item.ID, TraceID: item.TraceID, ProjectID: item.ProjectID, ParentObservationID: item.ParentObservationID,
				Name: item.Name, Type: item.Type, Level: item.Level, StatusMessage: item.StatusMessage,
				Version: item.Version, Environment: item.Environment, StartTime: item.StartTime, EndTime: item.EndTime,
				Input: normalizeIO(item.Input), Output: normalizeIO(item.Output), Metadata: item.Metadata,
				Model: item.ProvidedModelName, Usage: item.UsageDetails, Cost: number(item.TotalCost), Latency: number(item.Latency),
				TraceName: item.TraceName, Tags: item.Tags, Release: item.Release,
			})
		}
		if response.Meta.Cursor == "" {
			break
		}
		values.Set("cursor", response.Meta.Cursor)
	}
	return result, nil
}

func (c *Client) scores(ctx context.Context, traceID string) ([]Score, error) {
	values := url.Values{"traceId": {traceID}, "fields": {"details,subject,annotation"}, "limit": {"100"}}
	result := make([]Score, 0)
	for page := 0; page < 20; page++ {
		var response struct {
			Data []scoreAPI `json:"data"`
			Meta struct {
				Cursor string `json:"cursor"`
			} `json:"meta"`
		}
		if err := c.get(ctx, "/api/public/v3/scores", values, &response); err != nil {
			return nil, fmt.Errorf("read Langfuse scores: %w", err)
		}
		for _, item := range response.Data {
			result = append(result, Score{
				ID: item.ID, Name: item.Name, Value: item.Value, DataType: item.DataType, Source: item.Source,
				Timestamp: item.Timestamp, Environment: item.Environment, Comment: item.Comment, Metadata: item.Metadata,
				AuthorUserID: item.AuthorUserID, QueueID: item.QueueID,
				Subject: ScoreSubject{Kind: item.Subject.Kind, ID: item.Subject.ID, TraceID: item.Subject.TraceID},
			})
		}
		if response.Meta.Cursor == "" {
			break
		}
		values.Set("cursor", response.Meta.Cursor)
	}
	return result, nil
}

type scoreCreateRequest struct {
	ID            string         `json:"id"`
	TraceID       string         `json:"traceId"`
	ObservationID string         `json:"observationId,omitempty"`
	Name          string         `json:"name"`
	Value         any            `json:"value"`
	DataType      string         `json:"dataType"`
	Comment       string         `json:"comment,omitempty"`
	Metadata      map[string]any `json:"metadata,omitempty"`
}

func (c *Client) createScore(ctx context.Context, body scoreCreateRequest) (Score, error) {
	encoded, err := json.Marshal(body)
	if err != nil {
		return Score{}, err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/api/public/scores", bytes.NewReader(encoded))
	if err != nil {
		return Score{}, err
	}
	request.SetBasicAuth(c.publicKey, c.secretKey)
	request.Header.Set("Content-Type", "application/json")
	response, err := c.http.Do(request)
	if err != nil {
		return Score{}, err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return Score{}, fmt.Errorf("Langfuse returned HTTP %d: %s", response.StatusCode, strings.TrimSpace(string(message)))
	}
	var item scoreAPI
	if err := json.NewDecoder(io.LimitReader(response.Body, 1<<20)).Decode(&item); err != nil {
		return Score{}, fmt.Errorf("decode Langfuse score: %w", err)
	}
	return Score{
		ID: item.ID, Name: item.Name, Value: item.Value, DataType: item.DataType, Source: item.Source,
		Timestamp: item.Timestamp, Environment: item.Environment, Comment: item.Comment, Metadata: item.Metadata,
		Subject: ScoreSubject{Kind: item.Subject.Kind, ID: item.Subject.ID, TraceID: item.Subject.TraceID},
	}, nil
}

func (c *Client) get(ctx context.Context, path string, values url.Values, target any) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+path+"?"+values.Encode(), nil)
	if err != nil {
		return err
	}
	request.SetBasicAuth(c.publicKey, c.secretKey)
	response, err := c.http.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(response.Body, 4096))
		return fmt.Errorf("HTTP %d: %s", response.StatusCode, strings.TrimSpace(string(message)))
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, 8<<20)).Decode(target); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}
	return nil
}

func normalizeIO(value any) any {
	text, ok := value.(string)
	if !ok || strings.TrimSpace(text) == "" {
		return value
	}
	var decoded any
	if json.Unmarshal([]byte(text), &decoded) == nil {
		return decoded
	}
	return text
}

func summarize(observations []Observation, scores []Score) TraceSummary {
	summary := TraceSummary{ObservationCount: len(observations), ScoreCount: len(scores)}
	for _, observation := range observations {
		if strings.EqualFold(observation.Type, "GENERATION") {
			summary.GenerationCount++
			summary.TotalCost += observation.Cost
			summary.TotalTokens += usageTotal(observation.Usage)
		}
		if observation.ParentObservationID == "" && observation.Latency > summary.Latency {
			summary.Latency = observation.Latency
		}
	}
	if summary.Latency == 0 {
		for _, observation := range observations {
			if observation.Latency > summary.Latency {
				summary.Latency = observation.Latency
			}
		}
	}
	return summary
}

func usageTotal(usage map[string]any) float64 {
	for _, key := range []string{"total", "total_tokens", "totalTokens", "total_usage"} {
		if value := number(usage[key]); value > 0 {
			return value
		}
	}
	return number(usage["input"]) + number(usage["output"])
}

func number(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case float32:
		return float64(typed)
	case int:
		return float64(typed)
	case json.Number:
		result, _ := typed.Float64()
		return result
	case string:
		result, _ := strconv.ParseFloat(typed, 64)
		return result
	default:
		return 0
	}
}

func stableScoreID(traceID, actor, name string) string {
	digest := sha256.Sum256([]byte(traceID + "|" + actor + "|" + name))
	return "featurelens-" + hex.EncodeToString(digest[:16])
}

func envDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
