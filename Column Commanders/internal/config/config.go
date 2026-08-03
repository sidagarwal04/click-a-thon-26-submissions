package config

import (
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ClickHouseHost     string
	ClickHousePort     string
	ClickHouseDB       string
	ClickHouseUser     string
	ClickHousePassword string
	ClickHouseSecure   bool
	ServerPort         string
	BatchMaxSize       int

	// RequestTimeout bounds body read and response write. It must exceed the
	// longest ingestion; the 9M-row events file takes roughly three minutes.
	RequestTimeout time.Duration

	// Langfuse / OpenTelemetry export.
	// Set OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS to
	// route traces to Langfuse. Example (EU region):
	//
	//   AUTH=$(echo -n "pk-lf-...:sk-lf-..." | base64)
	//   OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel
	//   OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $AUTH,x-langfuse-ingestion-version=4"
	//
	// US region:   https://us.cloud.langfuse.com/api/public/otel
	// Self-hosted: http://localhost:3000/api/public/otel
	// Keys:        Langfuse project → Settings → API Keys
	OtelEndpoint string
	Detection    DetectionConfig
	LLM          LLMConfig
}

// DetectionConfig holds all tunable parameters for the anomaly detection pipeline.
// Every field maps 1:1 to an environment variable (see .env.example).
type DetectionConfig struct {
	// Window
	Window        time.Duration // DETECTION_WINDOW e.g. "1h", "6h", "1d"
	LookbackWeeks int           // DETECTION_LOOKBACK_WEEKS
	MinBaselineN  int           // DETECTION_MIN_BASELINE_N

	// Z-score thresholds
	ZScoreThreshold    float64 // DETECTION_ZSCORE_THRESHOLD
	ZScoreCTRThreshold float64 // DETECTION_ZSCORE_CTR_THRESHOLD
	// V2's short windows need a larger commercial floor for additive counters:
	// ordinary intra-hour request/revenue variation is much larger than ratio
	// metric variation, even when a tiny empirical sigma produces a large z-score.
	V2AdditiveMinDeviationPct float64       // DETECTION_V2_ADDITIVE_MIN_DEVIATION_PCT
	V2HistoricalMergeGap      time.Duration // DETECTION_V2_HISTORICAL_MERGE_GAP

	// Magnitude floor — z-score/CUSUM significance alone is unreliable as a noise
	// filter at this row count (tiny sigma + huge N makes even ~2% noise swings
	// register as z > 150). IsAnomaly requires BOTH the significance test AND a
	// minimum |deviation_pct|, so ordinary noise (e.g. ~2-3% eCPM softness) doesn't
	// alarm while real incidents (double-digit-percent swings) still do.
	MinDeviationPct    float64 // DETECTION_MIN_DEVIATION_PCT (fill_rate, ecpm, requests)
	MinDeviationPctCTR float64 // DETECTION_MIN_DEVIATION_PCT_CTR (ctr is noisier — higher floor)

	// CUSUM parameters
	CUSUMSlackK        float64 // DETECTION_CUSUM_SLACK_K     (in sigma units)
	CUSUMThresholdH    float64 // DETECTION_CUSUM_THRESHOLD_H (in sigma units)
	CUSUMRollingWindow int     // DETECTION_CUSUM_ROLLING_WINDOW (number of windows)

	// Drilldown
	ContributionThreshold float64 // DRILLDOWN_CONTRIBUTION_THRESHOLD
	MaxCulpritSegments    int     // DRILLDOWN_MAX_CULPRIT_SEGMENTS
	ParallelWorkers       int     // DRILLDOWN_PARALLEL_WORKERS
	HoldOutRevertPct      float64 // DRILLDOWN_HOLDOUT_REVERT_PCT — |deviation| below this counts as "reverted to baseline"
	PairwiseTriggerPct    float64 // DRILLDOWN_PAIRWISE_TRIGGER_PCT — run the intersection check when the top 2 culprits (different dimensions) both score at least this much |contribution_pct|

	// Broad dimensions scanned every Detect() cycle (not only inside drilldown,
	// after a platform-level detector already fired) — see
	// services/anomalydetector/detector/segment.go and docs/ARCHITECTURE_VALIDATED.md §4.2.
	SegmentDimensions []string // DETECTION_SEGMENT_DIMENSIONS, comma-separated (default: os_version,region)

	// Dual-resolution real-time scanning.
	CheckFrequency    time.Duration // DETECTION_CHECK_FREQUENCY
	LatenessAllowance time.Duration // DETECTION_LATENESS_ALLOWANCE
	FastWindow        time.Duration // DETECTION_FAST_WINDOW
	StandardWindow    time.Duration // DETECTION_STANDARD_WINDOW
	PersistenceChecks int           // DETECTION_PERSISTENCE_CHECKS
	SchedulerEnabled  bool          // DETECTION_SCHEDULER_ENABLED
	AutoBackfill      bool          // DETECTION_AUTO_BACKFILL
	MaxEpisodesPerRun int           // DETECTION_MAX_EPISODES_PER_RUN

	// Hard limits applied to every investigation-agent query.
	AgentQueryTimeout  time.Duration // AGENT_QUERY_TIMEOUT
	AgentMaxRowsRead   uint64        // AGENT_MAX_ROWS_TO_READ
	AgentMaxBytesRead  uint64        // AGENT_MAX_BYTES_TO_READ
	AgentMaxResultRows uint64        // AGENT_MAX_RESULT_ROWS
}

// LLMConfig controls the OpenAI-powered investigation agent. String and
// LogValue deliberately omit the API key to protect routine logs and telemetry.
type LLMConfig struct {
	Enabled              bool
	InvestigationEnabled bool
	NarrationEnabled     bool
	APIKey               string
	BaseURL              string
	Model                string // legacy alias for NarratorModel
	InvestigatorModel    string
	NarratorModel        string
	ReasoningEffort      string
	RequestTimeout       time.Duration
	MaxSteps             int
	MaxQueries           int
	MaxOutputTokens      int
}

// String deliberately omits APIKey so accidental formatted logging cannot
// disclose credentials.
func (c LLMConfig) String() string {
	return fmt.Sprintf("enabled=%t investigation=%t narration=%t base_url=%q investigator_model=%q narrator_model=%q timeout=%s max_steps=%d max_queries=%d",
		c.Enabled, c.InvestigationEnabled, c.NarrationEnabled, c.BaseURL,
		c.InvestigatorModel, c.NarratorModel, c.RequestTimeout, c.MaxSteps, c.MaxQueries)
}

// LogValue redacts APIKey when the config is passed to slog.Any.
func (c LLMConfig) LogValue() slog.Value {
	return slog.GroupValue(
		slog.Bool("enabled", c.Enabled),
		slog.Bool("investigation_enabled", c.InvestigationEnabled),
		slog.Bool("narration_enabled", c.NarrationEnabled),
		slog.String("base_url", c.BaseURL),
		slog.String("investigator_model", c.InvestigatorModel),
		slog.String("narrator_model", c.NarratorModel),
		slog.String("reasoning_effort", c.ReasoningEffort),
		slog.Duration("request_timeout", c.RequestTimeout),
		slog.Int("max_steps", c.MaxSteps),
		slog.Int("max_queries", c.MaxQueries),
	)
}

// Validate checks the credentials and safety bounds required when the
// investigation agent is enabled. Disabled narration has no credential
// requirements, so local detection continues to work without an OpenAI key.
func (c LLMConfig) Validate() error {
	if !c.Enabled {
		return nil
	}
	if strings.TrimSpace(c.APIKey) == "" {
		return errors.New("openai api key is required when narrator is enabled")
	}
	if strings.TrimSpace(c.BaseURL) == "" {
		return errors.New("openai base url is required when narrator is enabled")
	}
	if c.InvestigationEnabled && strings.TrimSpace(c.InvestigatorModel) == "" {
		return errors.New("investigator model is required when investigation is enabled")
	}
	if c.NarrationEnabled && strings.TrimSpace(c.NarratorModel) == "" {
		return errors.New("narrator model is required when narration is enabled")
	}
	if c.RequestTimeout <= 0 {
		return errors.New("narrator request timeout must be positive")
	}
	if c.MaxSteps <= 0 || c.MaxQueries <= 0 || c.MaxQueries > c.MaxSteps {
		return errors.New("investigation query and step limits are invalid")
	}
	if c.MaxOutputTokens <= 0 {
		return errors.New("llm max output tokens must be positive")
	}
	return nil
}

func Load() *Config {
	batchMaxSize := 10000
	if v := os.Getenv("BATCH_MAX_SIZE"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			batchMaxSize = n
		}
	}

	secure := true
	if v := os.Getenv("CLICKHOUSE_SECURE"); v == "false" || v == "0" {
		secure = false
	}

	requestTimeout := 30 * time.Minute
	if v := os.Getenv("REQUEST_TIMEOUT"); v != "" {
		if d, err := time.ParseDuration(v); err == nil && d > 0 {
			requestTimeout = d
		}
	}

	return &Config{
		ClickHouseHost:     getEnvOrDefault("CLICKHOUSE_HOST", "localhost"),
		ClickHousePort:     getEnvOrDefault("CLICKHOUSE_PORT", "9440"),
		ClickHouseDB:       getEnvOrDefault("CLICKHOUSE_DB", "default"),
		ClickHouseUser:     getEnvOrDefault("CLICKHOUSE_USER", "default"),
		ClickHousePassword: os.Getenv("CLICKHOUSE_PASSWORD"),
		ClickHouseSecure:   secure,
		ServerPort:         getEnvOrDefault("SERVER_PORT", "8080"),
		BatchMaxSize:       batchMaxSize,
		RequestTimeout:     requestTimeout,
		OtelEndpoint: firstNonEmpty(
			os.Getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
			os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
		),
		Detection: loadDetectionConfig(),
		LLM:       loadLLMConfig(),
	}
}

func loadDetectionConfig() DetectionConfig {
	window := time.Hour
	if v := os.Getenv("DETECTION_WINDOW"); v != "" {
		// Support shorthand: "1d" → 24h, "7d" → 168h
		if strings.HasSuffix(v, "d") {
			if n, err := strconv.Atoi(strings.TrimSuffix(v, "d")); err == nil && n > 0 {
				window = time.Duration(n) * 24 * time.Hour
			}
		} else if d, err := time.ParseDuration(v); err == nil {
			window = d
		}
	}

	return DetectionConfig{
		Window:                    window,
		LookbackWeeks:             getEnvInt("DETECTION_LOOKBACK_WEEKS", 3),
		MinBaselineN:              getEnvInt("DETECTION_MIN_BASELINE_N", 3),
		ZScoreThreshold:           getEnvFloat("DETECTION_ZSCORE_THRESHOLD", 5.0),
		ZScoreCTRThreshold:        getEnvFloat("DETECTION_ZSCORE_CTR_THRESHOLD", 8.0),
		V2AdditiveMinDeviationPct: getEnvFloat("DETECTION_V2_ADDITIVE_MIN_DEVIATION_PCT", 0.10),
		V2HistoricalMergeGap:      getEnvDuration("DETECTION_V2_HISTORICAL_MERGE_GAP", 24*time.Hour),
		MinDeviationPct:           getEnvFloat("DETECTION_MIN_DEVIATION_PCT", 0.03),
		MinDeviationPctCTR:        getEnvFloat("DETECTION_MIN_DEVIATION_PCT_CTR", 0.15),
		CUSUMSlackK:               getEnvFloat("DETECTION_CUSUM_SLACK_K", 0.5),
		CUSUMThresholdH:           getEnvFloat("DETECTION_CUSUM_THRESHOLD_H", 4.0),
		CUSUMRollingWindow:        getEnvInt("DETECTION_CUSUM_ROLLING_WINDOW", 7),
		ContributionThreshold:     getEnvFloat("DRILLDOWN_CONTRIBUTION_THRESHOLD", 0.10),
		MaxCulpritSegments:        getEnvInt("DRILLDOWN_MAX_CULPRIT_SEGMENTS", 5),
		ParallelWorkers:           getEnvInt("DRILLDOWN_PARALLEL_WORKERS", 5),
		HoldOutRevertPct:          getEnvFloat("DRILLDOWN_HOLDOUT_REVERT_PCT", 0.05),
		PairwiseTriggerPct:        getEnvFloat("DRILLDOWN_PAIRWISE_TRIGGER_PCT", 0.50),
		SegmentDimensions:         getEnvStringList("DETECTION_SEGMENT_DIMENSIONS", []string{"os_version", "region"}),
		CheckFrequency:            getEnvDuration("DETECTION_CHECK_FREQUENCY", time.Minute),
		LatenessAllowance:         getEnvDuration("DETECTION_LATENESS_ALLOWANCE", time.Minute),
		FastWindow:                getEnvDuration("DETECTION_FAST_WINDOW", 5*time.Minute),
		StandardWindow:            getEnvDuration("DETECTION_STANDARD_WINDOW", 10*time.Minute),
		PersistenceChecks:         getEnvInt("DETECTION_PERSISTENCE_CHECKS", 2),
		SchedulerEnabled:          getEnvBool("DETECTION_SCHEDULER_ENABLED", false),
		AutoBackfill:              getEnvBool("DETECTION_AUTO_BACKFILL", false),
		MaxEpisodesPerRun:         getEnvInt("DETECTION_MAX_EPISODES_PER_RUN", 10),
		AgentQueryTimeout:         getEnvDuration("AGENT_QUERY_TIMEOUT", 3*time.Second),
		AgentMaxRowsRead:          getEnvUint64("AGENT_MAX_ROWS_TO_READ", 10_000_000),
		AgentMaxBytesRead:         getEnvUint64("AGENT_MAX_BYTES_TO_READ", 1_000_000_000),
		AgentMaxResultRows:        getEnvUint64("AGENT_MAX_RESULT_ROWS", 1000),
	}
}

func loadLLMConfig() LLMConfig {
	masterEnabled := getEnvBool("LLM_ENABLED", false)
	narrationEnabled := getEnvBool("NARRATOR_ENABLED", masterEnabled)
	// Backwards compatibility: the original single narrator toggle enables the
	// complete LLM workflow unless investigation is explicitly overridden.
	investigationEnabled := getEnvBool("INVESTIGATION_ENABLED", narrationEnabled || masterEnabled)
	narratorModel := getEnvOrDefault("NARRATOR_MODEL", "gpt-5.6-sol")
	return LLMConfig{
		Enabled:              investigationEnabled || narrationEnabled,
		InvestigationEnabled: investigationEnabled,
		NarrationEnabled:     narrationEnabled,
		APIKey:               os.Getenv("OPENAI_API_KEY"),
		BaseURL:              getEnvOrDefault("OPENAI_BASE_URL", "https://api.openai.com/v1"),
		Model:                narratorModel,
		InvestigatorModel:    getEnvOrDefault("INVESTIGATION_MODEL", "gpt-5.6-sol"),
		NarratorModel:        narratorModel,
		ReasoningEffort:      getEnvOrDefault("OPENAI_REASONING_EFFORT", "low"),
		RequestTimeout:       getEnvDuration("OPENAI_REQUEST_TIMEOUT", getEnvDuration("NARRATOR_REQUEST_TIMEOUT", 30*time.Second)),
		MaxSteps:             getEnvInt("INVESTIGATION_MAX_STEPS", getEnvInt("NARRATOR_MAX_STEPS", 12)),
		MaxQueries:           getEnvInt("INVESTIGATION_MAX_QUERIES", getEnvInt("NARRATOR_MAX_QUERIES", 8)),
		MaxOutputTokens:      getEnvInt("OPENAI_MAX_OUTPUT_TOKENS", 4000),
	}
}

func getEnvOrDefault(key, defaultValue string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultValue
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func getEnvInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func getEnvStringList(key string, def []string) []string {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	var out []string
	for _, part := range strings.Split(v, ",") {
		if p := strings.TrimSpace(part); p != "" {
			out = append(out, p)
		}
	}
	if len(out) == 0 {
		return def
	}
	return out
}

func getEnvFloat(key string, def float64) float64 {
	if v := os.Getenv(key); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}
	return def
}

func getEnvUint64(key string, def uint64) uint64 {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.ParseUint(v, 10, 64); err == nil && n > 0 {
			return n
		}
	}
	return def
}

func getEnvBool(key string, def bool) bool {
	v := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if v == "" {
		return def
	}
	switch v {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return def
	}
}

func getEnvDuration(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil && d > 0 {
			return d
		}
	}
	return def
}
