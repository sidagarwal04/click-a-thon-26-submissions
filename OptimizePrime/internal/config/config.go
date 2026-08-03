// Package config loads ClickHouse connection settings from the environment.
//
// It deliberately reads the SAME variables the bash tools in tools/ read, so a
// Go binary and `tools/ch` always talk to the same server with the same
// credentials. Adding a Go-only variable would create two sources of truth and
// a class of bug where the two disagree about which database was loaded.
//
// Target resolution (ADR 0018): each target resolves to exactly one host and
// one database, from variables that belong to that target alone —
//
//	cloud: CH_HOST + CH_DATABASE
//	local: CH_LOCAL_URL + CH_DATABASE_LOCAL
//
// CH_DATABASE names the GRADED Cloud database and never applies to local.
// Local work used to fall back to it, so `sonyliv verify -target local` looked
// for a database that only exists on Cloud and 404ed. Missing configuration is
// an error at Load time, never a silent fallback to a server default.
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// Target selects which ClickHouse to talk to. The graded target is Cloud; local
// Docker exists purely for fast iteration.
type Target string

// The two deployment targets. Values match the TARGET= convention in tools/load.sh.
const (
	TargetLocal Target = "local"
	TargetCloud Target = "cloud"
)

// ClickHouse is everything needed to open a connection.
type ClickHouse struct {
	Host     string
	Port     int
	User     string
	Password string
	Database string
	Secure   bool
	Target   Target
}

// Addr renders the host:port form the ClickHouse driver expects.
//
// Pointer receiver: ClickHouse is 96 bytes and copying it per call buys nothing.
func (c *ClickHouse) Addr() string {
	return net(c.Host, c.Port)
}

func net(host string, port int) string {
	return host + ":" + strconv.Itoa(port)
}

// ParseHost splits a CH_HOST value into a bare host and, if the value carried
// one, a port.
//
// The Cloud console presents the endpoint as https://xxx.clickhouse.cloud, and
// that is what people paste into .env. Everything downstream wants a bare host,
// so a pasted scheme silently produced https://https://... and a "could not
// resolve host: https" failure. Accept what the console gives you instead of
// requiring the human to reformat it.
//
// A returned port of 0 means the value carried none and the caller should use
// its own default.
func ParseHost(raw string) (host string, port int) {
	h := strings.TrimSpace(raw)
	h = strings.TrimPrefix(h, "https://")
	h = strings.TrimPrefix(h, "http://")
	h = strings.TrimSuffix(h, "/")

	// Drop any path component: .../?database=x is a valid thing to paste.
	if i := strings.IndexAny(h, "/?"); i >= 0 {
		h = h[:i]
	}

	// A trailing :NNNN is a port. Anything else after a colon is not, so leave
	// it alone rather than mangling it.
	if i := strings.LastIndex(h, ":"); i >= 0 {
		if p, err := strconv.Atoi(h[i+1:]); err == nil && p > 0 && p <= 65535 {
			return h[:i], p
		}
	}
	return h, 0
}

// Load reads the ClickHouse settings for the given target from the environment.
//
// It returns an error naming the missing variable rather than connecting with a
// blank password and failing later with an opaque auth error.
func Load(target Target) (ClickHouse, error) {
	switch target {
	case TargetCloud:
		return loadCloud()
	case TargetLocal:
		return loadLocal()
	default:
		return ClickHouse{}, fmt.Errorf("unknown target %q (want %q or %q)", target, TargetLocal, TargetCloud)
	}
}

func loadCloud() (ClickHouse, error) {
	rawHost, err := required("CH_HOST")
	if err != nil {
		return ClickHouse{}, err
	}
	password, err := required("CH_PASSWORD")
	if err != nil {
		return ClickHouse{}, err
	}
	database, err := required("CH_DATABASE")
	if err != nil {
		return ClickHouse{}, err
	}

	host, port := ParseHost(rawHost)
	if p := envInt("CH_PORT", 0); p != 0 {
		port = p
	}
	if port == 0 {
		port = 8443 // Cloud HTTPS
	}

	return ClickHouse{
		Host:     host,
		Port:     port,
		User:     envStr("CH_USER", "default"),
		Password: password,
		Database: database,
		Secure:   envBool("CH_SECURE", true),
		Target:   TargetCloud,
	}, nil
}

func loadLocal() (ClickHouse, error) {
	// NOT CH_DATABASE — that names the graded Cloud database, and reading it
	// here is exactly the bug ADR 0018 removes: local verification 404ed
	// looking for `sonyliv` on localhost.
	database, err := required("CH_DATABASE_LOCAL")
	if err != nil {
		return ClickHouse{}, fmt.Errorf("%w (the local container's data lives in `default`; CH_DATABASE is the Cloud database and does not apply to local — ADR 0018)", err)
	}
	password, err := required("CH_PASSWORD_LOCAL")
	if err != nil {
		return ClickHouse{}, err
	}

	// CH_LOCAL_URL is a full URL (http://localhost:8123) in .env, so it goes
	// through the same parser as the Cloud host.
	host, port := ParseHost(envStr("CH_LOCAL_URL", "http://localhost:8123"))
	if port == 0 {
		port = 8123
	}
	return ClickHouse{
		Host:     host,
		Port:     port,
		User:     envStr("CH_LOCAL_USER", "app"),
		Password: password,
		Database: database,
		Secure:   false,
		Target:   TargetLocal,
	}, nil
}

// TargetFromEnv reads TARGET, matching the convention in tools/load.sh.
func TargetFromEnv() Target {
	if strings.EqualFold(os.Getenv("TARGET"), string(TargetCloud)) {
		return TargetCloud
	}
	return TargetLocal
}

func required(key string) (string, error) {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return "", fmt.Errorf("%s is not set — copy .env.example to .env and fill it in", key)
	}
	return v, nil
}

func envStr(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	if v, err := strconv.Atoi(strings.TrimSpace(os.Getenv(key))); err == nil {
		return v
	}
	return fallback
}

func envBool(key string, fallback bool) bool {
	if v, err := strconv.ParseBool(strings.TrimSpace(os.Getenv(key))); err == nil {
		return v
	}
	return fallback
}
