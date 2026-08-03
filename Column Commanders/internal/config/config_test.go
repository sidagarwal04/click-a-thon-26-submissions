package config

import (
	"fmt"
	"log/slog"
	"os"
	"strings"
	"testing"
	"time"
)

func TestConfiguredLLMEnvironment(t *testing.T) {
	if os.Getenv("OPENAI_CONFIG_TEST") != "1" {
		t.Skip("set OPENAI_CONFIG_TEST=1 to validate the configured LLM environment")
	}
	cfg := Load()
	if err := cfg.LLM.Validate(); err != nil {
		t.Fatalf("configured LLM environment: %v", err)
	}
}

func TestLoadDualResolutionAndLLMConfig(t *testing.T) {
	t.Setenv("DETECTION_CHECK_FREQUENCY", "30s")
	t.Setenv("DETECTION_LATENESS_ALLOWANCE", "2m")
	t.Setenv("DETECTION_FAST_WINDOW", "5m")
	t.Setenv("DETECTION_STANDARD_WINDOW", "10m")
	t.Setenv("DETECTION_PERSISTENCE_CHECKS", "3")
	t.Setenv("DETECTION_V2_ADDITIVE_MIN_DEVIATION_PCT", "0.12")
	t.Setenv("DETECTION_V2_HISTORICAL_MERGE_GAP", "18h")
	t.Setenv("NARRATOR_ENABLED", "true")
	t.Setenv("OPENAI_API_KEY", "test-key")
	t.Setenv("OPENAI_BASE_URL", "https://gateway.example/v1")
	t.Setenv("NARRATOR_MODEL", "test-model")
	t.Setenv("INVESTIGATION_MODEL", "test-investigator")
	t.Setenv("NARRATOR_REQUEST_TIMEOUT", "45s")
	t.Setenv("NARRATOR_MAX_STEPS", "10")
	t.Setenv("NARRATOR_MAX_QUERIES", "6")

	cfg := Load()
	if cfg.Detection.CheckFrequency != 30*time.Second {
		t.Fatalf("check frequency = %s", cfg.Detection.CheckFrequency)
	}
	if cfg.Detection.LatenessAllowance != 2*time.Minute {
		t.Fatalf("lateness allowance = %s", cfg.Detection.LatenessAllowance)
	}
	if cfg.Detection.FastWindow != 5*time.Minute || cfg.Detection.StandardWindow != 10*time.Minute {
		t.Fatalf("unexpected windows: fast=%s standard=%s", cfg.Detection.FastWindow, cfg.Detection.StandardWindow)
	}
	if cfg.Detection.PersistenceChecks != 3 {
		t.Fatalf("persistence checks = %d", cfg.Detection.PersistenceChecks)
	}
	if cfg.Detection.V2AdditiveMinDeviationPct != 0.12 || cfg.Detection.V2HistoricalMergeGap != 18*time.Hour {
		t.Fatalf("unexpected v2 false-positive controls: additive_floor=%v merge_gap=%s",
			cfg.Detection.V2AdditiveMinDeviationPct, cfg.Detection.V2HistoricalMergeGap)
	}
	if err := cfg.LLM.Validate(); err != nil {
		t.Fatalf("validate llm config: %v", err)
	}
	if cfg.LLM.BaseURL != "https://gateway.example/v1" || cfg.LLM.Model != "test-model" {
		t.Fatalf("unexpected llm routing config: base=%q model=%q", cfg.LLM.BaseURL, cfg.LLM.Model)
	}
	if !cfg.LLM.InvestigationEnabled || !cfg.LLM.NarrationEnabled || cfg.LLM.InvestigatorModel != "test-investigator" {
		t.Fatalf("unexpected LLM stages: investigation=%t narration=%t investigator_model=%q",
			cfg.LLM.InvestigationEnabled, cfg.LLM.NarrationEnabled, cfg.LLM.InvestigatorModel)
	}
	if cfg.LLM.RequestTimeout != 45*time.Second || cfg.LLM.MaxSteps != 10 || cfg.LLM.MaxQueries != 6 {
		t.Fatalf("unexpected llm bounds: timeout=%s steps=%d queries=%d",
			cfg.LLM.RequestTimeout, cfg.LLM.MaxSteps, cfg.LLM.MaxQueries)
	}
}

func TestLLMConfigDisabledDoesNotRequireCredentials(t *testing.T) {
	if err := (LLMConfig{Enabled: false}).Validate(); err != nil {
		t.Fatalf("disabled config should be valid: %v", err)
	}
}

func TestLLMConfigEnabledRequiresCredentials(t *testing.T) {
	cfg := LLMConfig{
		Enabled:        true,
		BaseURL:        "https://api.openai.com/v1",
		Model:          "gpt-5.6",
		RequestTimeout: 30 * time.Second,
		MaxSteps:       12,
		MaxQueries:     8,
	}
	err := cfg.Validate()
	if err == nil || !strings.Contains(err.Error(), "api key") {
		t.Fatalf("expected api key error, got %v", err)
	}
}

func TestLLMConfigRejectsUnsafeBounds(t *testing.T) {
	cfg := LLMConfig{
		Enabled:        true,
		APIKey:         "test-key",
		BaseURL:        "https://api.openai.com/v1",
		Model:          "gpt-5.6",
		RequestTimeout: 30 * time.Second,
		MaxSteps:       4,
		MaxQueries:     5,
	}
	if err := cfg.Validate(); err == nil {
		t.Fatal("expected invalid bounds error")
	}
}

func TestLLMConfigRedactsAPIKey(t *testing.T) {
	cfg := LLMConfig{Enabled: true, APIKey: "super-secret", BaseURL: "https://api.openai.com/v1", Model: "gpt-5.6"}
	if got := fmt.Sprintf("%+v", cfg); strings.Contains(got, cfg.APIKey) {
		t.Fatalf("formatted config leaked api key: %s", got)
	}
	if got := cfg.LogValue(); got.Kind() != slog.KindGroup {
		t.Fatalf("log value kind = %s, want group", got.Kind())
	}
}
