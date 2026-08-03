package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

func loadEnvFile() {
	cwd, _ := os.Getwd()
	paths := []string{
		filepath.Join(cwd, ".env"),
		filepath.Join(cwd, "../.env"),
		"/workspaces/Peekachu/.env",
	}
	for _, p := range paths {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				val := strings.TrimSpace(parts[1])
				if os.Getenv(key) == "" {
					os.Setenv(key, val)
				}
			}
		}
	}
}

func ConnectClickHouse() (driver.Conn, error) {
	loadEnvFile()

	chURL := os.Getenv("CLICKHOUSE_URL")
	if chURL == "" {
		return nil, fmt.Errorf("CLICKHOUSE_URL environment variable is missing")
	}
	username := os.Getenv("CLICKHOUSE_USERNAME")
	if username == "" {
		username = "default"
	}
	password := os.Getenv("CLICKHOUSE_PASSWORD")
	if password == "" {
		return nil, fmt.Errorf("CLICKHOUSE_PASSWORD environment variable is missing")
	}

	// Parse host and port from URL
	parsedURL, err := url.Parse(chURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse CLICKHOUSE_URL '%s': %w", chURL, err)
	}

	host := parsedURL.Hostname()
	if host == "" {
		return nil, fmt.Errorf("invalid CLICKHOUSE_URL '%s': host is empty", chURL)
	}

	var port uint16 = 9440
	pStr := parsedURL.Port()
	if pStr != "" {
		if pInt, err := strconv.Atoi(pStr); err == nil && pInt > 0 {
			port = uint16(pInt)
		}
	}

	useTLS := parsedURL.Scheme != "http"
	useHTTP := port == 8443 || port == 80 || parsedURL.Scheme == "http" || parsedURL.Scheme == "https"

	addr := fmt.Sprintf("%s:%d", host, port)

	opt := clickhouse.Options{
		Addr: []string{addr},
		Auth: clickhouse.Auth{
			Database: "default",
			Username: username,
			Password: password,
		},
		DialTimeout:     5 * time.Second,
		MaxOpenConns:    32,
		MaxIdleConns:    16,
		ConnMaxLifetime: 10 * time.Minute,
	}

	if useHTTP {
		opt.Protocol = clickhouse.HTTP
		if useTLS {
			opt.TLS = &tls.Config{InsecureSkipVerify: true}
		}
	} else {
		opt.Protocol = clickhouse.Native
		if useTLS {
			opt.TLS = &tls.Config{InsecureSkipVerify: true}
		}
	}

	conn, err := clickhouse.Open(&opt)
	if err != nil {
		return nil, fmt.Errorf("failed to open clickhouse connection: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := conn.Ping(ctx); err != nil {
		// If native connection fails, try fallback to HTTP on 8443
		if opt.Protocol == clickhouse.Native {
			fmt.Printf("Native connection failed (%v), trying HTTP fallback...\n", err)
			opt.Protocol = clickhouse.HTTP
			opt.Addr = []string{fmt.Sprintf("%s:8443", host)}
			opt.TLS = &tls.Config{InsecureSkipVerify: true}
			conn, err = clickhouse.Open(&opt)
			if err != nil {
				return nil, fmt.Errorf("http fallback open failed: %w", err)
			}
			if err := conn.Ping(ctx); err != nil {
				return nil, fmt.Errorf("http fallback ping failed: %w", err)
			}
		} else {
			return nil, fmt.Errorf("clickhouse ping failed: %w", err)
		}
	}

	fmt.Printf("Successfully connected to ClickHouse at %s\n", strings.Join(opt.Addr, ","))
	return conn, nil
}
