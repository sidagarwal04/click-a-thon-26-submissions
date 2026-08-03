// Package config loads ClickHouse connection settings from a .env file and the
// process environment. Environment variables always win over the .env file, so
// the same binary works from a laptop and from CI without editing anything.
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
)

// Config is everything needed to reach a ClickHouse service.
type Config struct {
	Host     string
	Port     int
	Database string
	User     string
	Password string
	Secure   bool

	DialTimeout  time.Duration
	ReadTimeout  time.Duration
	MaxOpenConns int
}

// Load reads .env (searching upward from the working directory if envPath is
// empty), overlays the process environment, and validates the result.
func Load(envPath string) (*Config, error) {
	if envPath != "" {
		if err := godotenv.Load(envPath); err != nil {
			return nil, fmt.Errorf("load %s: %w", envPath, err)
		}
	} else if found := findEnvFile(); found != "" {
		// A missing .env is fine — the environment may already carry everything.
		_ = godotenv.Load(found)
	}

	secure := envBool("CLICKHOUSE_SECURE", true)

	// ClickHouse Cloud terminates the native protocol on 9440 (TLS); a local
	// server listens on 9000 in the clear. Default to whichever matches the
	// secure flag so a minimal .env still works.
	defaultPort := 9000
	if secure {
		defaultPort = 9440
	}

	cfg := &Config{
		Host:         envStr("CLICKHOUSE_HOST", "localhost"),
		Port:         envInt("CLICKHOUSE_PORT", defaultPort),
		Database:     envStr("CLICKHOUSE_DATABASE", "default"),
		User:         envStr("CLICKHOUSE_USER", "default"),
		Password:     envStr("CLICKHOUSE_PASSWORD", ""),
		Secure:       secure,
		DialTimeout:  envDuration("CLICKHOUSE_DIAL_TIMEOUT", 30*time.Second),
		ReadTimeout:  envDuration("CLICKHOUSE_READ_TIMEOUT", 5*time.Minute),
		MaxOpenConns: envInt("CLICKHOUSE_MAX_OPEN_CONNS", 16),
	}

	if cfg.Host == "" {
		return nil, fmt.Errorf("CLICKHOUSE_HOST is required (copy .env.example to .env)")
	}
	if cfg.Port <= 0 || cfg.Port > 65535 {
		return nil, fmt.Errorf("CLICKHOUSE_PORT %d is out of range", cfg.Port)
	}
	return cfg, nil
}

// Addr is the host:port the native client dials.
func (c *Config) Addr() string { return fmt.Sprintf("%s:%d", c.Host, c.Port) }

// Redacted renders the connection for logs without leaking the password.
func (c *Config) Redacted() string {
	scheme := "clickhouse"
	if c.Secure {
		scheme = "clickhouse+tls"
	}
	return fmt.Sprintf("%s://%s@%s/%s", scheme, c.User, c.Addr(), c.Database)
}

// findEnvFile walks up from the working directory looking for a .env, so the
// binaries can be run from anywhere inside the repo.
func findEnvFile() string {
	dir, err := os.Getwd()
	if err != nil {
		return ""
	}
	for i := 0; i < 6; i++ {
		candidate := filepath.Join(dir, ".env")
		if st, err := os.Stat(candidate); err == nil && !st.IsDir() {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return ""
}

func envStr(key, def string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if n, err := strconv.Atoi(strings.TrimSpace(v)); err == nil {
			return n
		}
	}
	return def
}

func envBool(key string, def bool) bool {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if b, err := strconv.ParseBool(strings.TrimSpace(v)); err == nil {
			return b
		}
	}
	return def
}

func envDuration(key string, def time.Duration) time.Duration {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if d, err := time.ParseDuration(strings.TrimSpace(v)); err == nil {
			return d
		}
	}
	return def
}
