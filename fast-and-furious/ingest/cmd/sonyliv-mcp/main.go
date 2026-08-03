// Command sonyliv-mcp serves the SonyLIV concurrency serving layer over the Model
// Context Protocol, so an assistant can answer viewing-trend questions against it.
//
//	sonyliv-mcp --transport http --addr :8848 --token-env SONYLIV_MCP_TOKEN
//	sonyliv-mcp --transport stdio
//
// It exposes ONLY the serving layer. That is enforced in two independent places:
//
//   - The ClickHouse user it connects as (ingest/sql/manual/009_mcp_reader.sql) holds SELECT on
//     the serving tables and views and nothing else — no events, no session_intervals, no
//     system tables, no write privilege of any kind.
//   - Every statement is validated before it is sent (guard.go).
//
// The grant is the boundary that actually holds; the validator exists so a refusal
// explains itself, and so a parser bug is not the only thing between a model and
// per-user data.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"reflect"
	"strings"
	"syscall"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/config"
)

var buildVersion = "dev"

type server struct {
	ch       *chx.Client
	database string
	tools    []toolDef
	handlers map[string]handler
}

var currentDatabase string

// defaultDatabase is read by guard.go when deciding whether a qualified relation refers
// to our database or is reaching somewhere else entirely.
func defaultDatabase() string { return currentDatabase }

func main() {
	log.SetFlags(0)
	log.SetPrefix("sonyliv-mcp: ")

	fs := flag.NewFlagSet("sonyliv-mcp", flag.ExitOnError)
	transport := fs.String("transport", "stdio", "stdio or http")
	addr := fs.String("addr", ":8848", "listen address for --transport http")
	tokenEnv := fs.String("token-env", "SONYLIV_MCP_TOKEN", "env var holding the bearer token required by the HTTP transport")
	envPath := fs.String("env", "", "path to .env (default: search upward)")
	allowNoAuth := fs.Bool("allow-no-auth", false, "serve HTTP without a bearer token — loopback only, refuses a non-loopback bind")
	devUnrestricted := fs.Bool("dev-unrestricted", false,
		"development only: start even when the connected user can read outside the serving layer. "+
			"The SQL guard still applies; only the grant preflight is skipped. Never use in deployment")
	if err := fs.Parse(os.Args[1:]); err != nil {
		os.Exit(2)
	}

	cfg, err := config.Load(*envPath)
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	currentDatabase = cfg.Database

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	ch, err := chx.Open(ctx, cfg)
	if err != nil {
		log.Fatalf("clickhouse: %v", err)
	}
	defer ch.Close()

	s := &server{ch: ch, database: cfg.Database}
	s.registerTools()

	// Fail at startup rather than on the first tool call: a server that answers
	// tools/list but cannot read anything looks healthy and is not.
	if err := s.preflight(ctx); err != nil {
		if !*devUnrestricted {
			log.Fatalf("preflight: %v", err)
		}
		// Deliberately loud, and deliberately still runs the guard: this path exists so
		// the validator can be exercised before an admin has created sonyliv_mcp, not so
		// the boundary can be skipped.
		log.Printf("WARNING --dev-unrestricted: %v", err)
		log.Printf("WARNING the grant boundary is NOT in place; only the SQL guard is protecting the serving layer")
	}
	log.Printf("connected as %s to %s (%d tools)", cfg.User, cfg.Redacted(), len(s.tools))

	switch *transport {
	case "stdio":
		s.serveStdio(ctx)
	case "http":
		token := os.Getenv(*tokenEnv)
		if token == "" {
			if !*allowNoAuth {
				log.Fatalf("%s is empty. The HTTP transport hands out SQL access, so it requires a\n"+
					"bearer token. Set %s, or pass --allow-no-auth for a loopback-only bind.",
					*tokenEnv, *tokenEnv)
			}
			if !isLoopback(*addr) {
				log.Fatalf("--allow-no-auth refuses a non-loopback bind (%s): that would expose "+
					"unauthenticated SQL access to the network", *addr)
			}
			log.Printf("WARNING: serving without authentication on %s (loopback only)", *addr)
		}
		s.serveHTTP(ctx, *addr, token)
	default:
		log.Fatalf("unknown transport %q (want stdio or http)", *transport)
	}
}

// preflight proves the grants are right before accepting traffic: the serving layer must
// be readable, and per-user data must not be. The negative check matters more — an
// over-granted user would otherwise be discovered only by someone reading user_id
// through the model.
func (s *server) preflight(ctx context.Context) error {
	var n uint64
	if err := s.ch.Conn.QueryRow(ctx,
		fmt.Sprintf("SELECT count() FROM %s.serving_watermark", s.database)).Scan(&n); err != nil {
		return fmt.Errorf("cannot read the serving layer (is 009_mcp_reader.sql applied?): %w", err)
	}
	for _, forbidden := range []string{"events_clean", "session_intervals"} {
		err := s.ch.Conn.QueryRow(ctx,
			fmt.Sprintf("SELECT count() FROM %s.%s", s.database, forbidden)).Scan(&n)
		if err == nil {
			return fmt.Errorf("REFUSING TO START: this connection can read %s.%s, which carries "+
				"user identity. Connect as sonyliv_mcp, not as an admin or the service user",
				s.database, forbidden)
		}
	}
	return nil
}

func isLoopback(addr string) bool {
	h := addr
	if i := strings.LastIndex(addr, ":"); i >= 0 {
		h = addr[:i]
	}
	return h == "" || h == "127.0.0.1" || h == "localhost" || h == "[::1]" || h == "::1"
}

// ------------------------------------------------------------------- transports ----

func (s *server) serveStdio(ctx context.Context) {
	dec := json.NewDecoder(os.Stdin)
	enc := json.NewEncoder(os.Stdout)
	for {
		var req rpcRequest
		if err := dec.Decode(&req); err != nil {
			if errors.Is(err, io.EOF) {
				return
			}
			log.Printf("decode: %v", err)
			return
		}
		if resp := s.dispatch(ctx, &req); resp != nil {
			if err := enc.Encode(resp); err != nil {
				log.Printf("encode: %v", err)
				return
			}
		}
	}
}

func (s *server) serveHTTP(ctx context.Context, addr, token string) {
	mux := http.NewServeMux()

	// Unauthenticated so a load balancer can probe it; deliberately reveals nothing but
	// liveness.
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "ok\n")
	})

	mux.HandleFunc("/mcp", func(w http.ResponseWriter, r *http.Request) {
		if token != "" && !authorised(r, token) {
			w.Header().Set("WWW-Authenticate", `Bearer realm="sonyliv-mcp"`)
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		switch r.Method {
		case http.MethodPost:
		case http.MethodGet, http.MethodDelete:
			// No server-initiated messages and no session state to tear down, so the
			// streamable-HTTP SSE channel is intentionally absent.
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		var req rpcRequest
		if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
			writeJSON(w, &rpcResponse{JSONRPC: "2.0",
				Error: &rpcError{Code: codeParse, Message: "malformed JSON: " + err.Error()}})
			return
		}

		rctx, cancel := context.WithTimeout(r.Context(), 60*time.Second)
		defer cancel()

		resp := s.dispatch(rctx, &req)
		if resp == nil {
			w.WriteHeader(http.StatusAccepted) // notification
			return
		}
		writeJSON(w, resp)
	})

	srv := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}
	go func() {
		<-ctx.Done()
		sh, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = srv.Shutdown(sh)
	}()

	log.Printf("listening on %s (POST /mcp, GET /healthz)", addr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("http: %v", err)
	}
}

func authorised(r *http.Request, token string) bool {
	h := r.Header.Get("Authorization")
	if strings.HasPrefix(h, "Bearer ") && subtleEqual(strings.TrimPrefix(h, "Bearer "), token) {
		return true
	}
	// Some MCP clients only offer a custom-header field.
	return subtleEqual(r.Header.Get("X-MCP-Token"), token)
}

// Constant-time compare so a token cannot be recovered byte-by-byte from timing.
func subtleEqual(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	var v byte
	for i := 0; i < len(a); i++ {
		v |= a[i] ^ b[i]
	}
	return v == 0
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("write: %v", err)
	}
}

// --------------------------------------------------------------- query plumbing ----

func named(k string, v any) driver.NamedValue { return chx.Named(k, v) }

// queryText renders a result set as an aligned text table. Models read column headers
// and units far more reliably than raw JSON, and the row count at the end lets them tell
// "no matching rows" from a truncated answer.
func (s *server) queryText(ctx context.Context, q string, params ...driver.NamedValue) (string, error) {
	a := make([]any, len(params))
	for i, p := range params {
		a[i] = p
	}
	rows, err := s.ch.Conn.Query(ctx, q, a...)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	cols := rows.Columns()
	// clickhouse-go cannot scan into *any — it needs a destination of the column's own
	// type. ScanType() supplies that, so arbitrary user SQL with columns we cannot know
	// ahead of time still renders.
	types := rows.ColumnTypes()
	out := [][]string{cols}
	for rows.Next() {
		vals := make([]any, len(cols))
		for i := range vals {
			vals[i] = reflect.New(types[i].ScanType()).Interface()
		}
		if err := rows.Scan(vals...); err != nil {
			return "", err
		}
		rec := make([]string, len(cols))
		for i, v := range vals {
			rec[i] = render(reflect.ValueOf(v).Elem().Interface())
		}
		out = append(out, rec)
	}
	if err := rows.Err(); err != nil {
		return "", err
	}

	width := make([]int, len(cols))
	for _, r := range out {
		for i, c := range r {
			if len(c) > width[i] {
				width[i] = len(c)
			}
		}
	}
	var b strings.Builder
	for ri, r := range out {
		for i, c := range r {
			if i > 0 {
				b.WriteString("  ")
			}
			b.WriteString(c)
			if i < len(r)-1 {
				b.WriteString(strings.Repeat(" ", width[i]-len(c)))
			}
		}
		b.WriteString("\n")
		if ri == 0 {
			for i := range r {
				if i > 0 {
					b.WriteString("  ")
				}
				b.WriteString(strings.Repeat("-", width[i]))
			}
			b.WriteString("\n")
		}
	}
	fmt.Fprintf(&b, "\n(%d rows)\n", len(out)-1)
	return b.String(), nil
}

func render(v any) string {
	switch t := v.(type) {
	case nil:
		return ""
	case time.Time:
		return t.UTC().Format("2006-01-02 15:04:05")
	case float64:
		return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.6f", t), "0"), ".")
	case float32:
		return strings.TrimRight(strings.TrimRight(fmt.Sprintf("%.6f", t), "0"), ".")
	case string:
		return t
	default:
		return fmt.Sprintf("%v", t)
	}
}
