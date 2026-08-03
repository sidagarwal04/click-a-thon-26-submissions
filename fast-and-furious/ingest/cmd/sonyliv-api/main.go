// Command sonyliv-api serves HTTP event ingest into events_raw.
//
// It is the long-lived service of the ingest module: sonyliv-ingest is a CLI you
// invoke, sonyliv-gen runs to a bound, this one stays up. Deployed by
// deploy/deploy.sh and supervised by deploy/sonyliv-api.service.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/sonyliv-clickathon/ingest/internal/api"
	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/config"
)

// version is stamped at build time by deploy/deploy.sh via -ldflags.
var version = "dev"

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "sonyliv-api: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	fs := flag.NewFlagSet("sonyliv-api", flag.ContinueOnError)
	listen := fs.String("listen", "127.0.0.1:8080", "address to serve on")
	envPath := fs.String("env", "", "path to .env (default: search upward, then process env)")
	batchSize := fs.Int("batch-size", api.DefaultBatchSize, "rows per INSERT chunk")
	maxRows := fs.Int("max-rows", api.DefaultMaxRows, "reject a request carrying more events than this")
	maxBody := fs.Int64("max-body", api.DefaultMaxBodyBytes, "reject a request body larger than this, in bytes")
	maxInflight := fs.Int("max-inflight", api.DefaultMaxInFlight, "concurrent inserts before shedding with 503")
	syncThresh := fs.Int("sync-threshold", api.DefaultSyncThreshold, "row count at or above which a request bypasses the async buffer")
	workers := fs.Int("workers", 4, "concurrent INSERT streams per request")
	retries := fs.Int("retries", 3, "retry attempts per chunk (same dedup token)")
	drain := fs.Duration("drain-timeout", api.DefaultDrainTimeout, "how long to let in-flight requests finish on SIGTERM")
	// Serve TLS when both are given. Needed where the only inbound port a
	// security group allows is 443, which is the common case on a box in a
	// private subnet. A self-signed pair is fine there: the bearer token is the
	// authentication, TLS is only transport encryption, and callers reach the
	// host over a private path already. Clients then need --insecure/-k.
	tlsCert := fs.String("tls-cert", "", "PEM certificate; enables TLS when set with -tls-key")
	tlsKey := fs.String("tls-key", "", "PEM private key; enables TLS when set with -tls-cert")
	allowOpen := fs.Bool("allow-unauthenticated", false,
		"serve without a bearer token; only safe where the network is the boundary")
	showVersion := fs.Bool("version", false, "print version and exit")

	if err := fs.Parse(os.Args[1:]); err != nil {
		return err
	}
	if *showVersion {
		fmt.Println(version)
		return nil
	}
	if err := chx.ValidateWritePath(*workers, *retries); err != nil {
		return err
	}

	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))

	// Read the credential before dialling: refusing to start is the right failure
	// for a write endpoint, and it should happen before anything observable.
	token := os.Getenv("SONYLIV_API_TOKEN")
	if token == "" && !*allowOpen {
		return api.ErrNoToken
	}

	cfg, err := config.Load(*envPath)
	if err != nil {
		return err
	}

	// Bounded startup: a wedged network should fail the unit rather than hang it.
	dialCtx, cancelDial := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancelDial()
	client, err := chx.Open(dialCtx, cfg)
	if err != nil {
		return err
	}
	defer client.Close()

	serverVersion, err := client.ServerVersion(dialCtx)
	if err != nil {
		return fmt.Errorf("read server version: %w", err)
	}

	// The audit writer flushes on its own timer for the whole process lifetime,
	// so it is tied to a context that outlives any single request.
	auditCtx, cancelAudit := context.WithCancel(context.Background())
	defer cancelAudit()
	audit := chx.NewAuditWriter(auditCtx, client)

	writer := api.NewLoaderWriter(client, audit, *workers, *retries, *batchSize)

	srv, err := api.NewServer(writer, audit, client.Conn.Ping, api.Options{
		Token:                token,
		AllowUnauthenticated: *allowOpen,
		BatchSize:            *batchSize,
		MaxRows:              *maxRows,
		MaxBodyBytes:         *maxBody,
		MaxInFlight:          *maxInflight,
		SyncThreshold:        *syncThresh,
		Log:                  log,
	})
	if err != nil {
		return err
	}

	httpSrv := &http.Server{
		Addr:    *listen,
		Handler: srv.Handler(),
		// A generous write/read window: a 64 MiB body over a slow link is a
		// legitimate request, not an attack. The body size cap is the real guard.
		ReadHeaderTimeout: 10 * time.Second,
		WriteTimeout:      2 * time.Minute,
		IdleTimeout:       120 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	// Both or neither: a cert without a key would otherwise start plaintext on
	// 443 and look like it worked.
	useTLS := *tlsCert != "" || *tlsKey != ""
	if useTLS && (*tlsCert == "" || *tlsKey == "") {
		return errors.New("-tls-cert and -tls-key must be given together")
	}

	errCh := make(chan error, 1)
	go func() {
		log.Info("listening",
			"addr", *listen, "tls", useTLS, "version", version, "clickhouse", serverVersion,
			"database", cfg.Database, "run_id", writer.RunID().String(),
			"batch_size", *batchSize, "sync_threshold", *syncThresh, "max_inflight", *maxInflight)
		var err error
		if useTLS {
			err = httpSrv.ListenAndServeTLS(*tlsCert, *tlsKey)
		} else {
			err = httpSrv.ListenAndServe()
		}
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case err := <-errCh:
		return err
	case <-ctx.Done():
	}

	// Drain: stop accepting, let in-flight inserts finish, then flush the audit
	// buffer. Audit last, because in-flight requests are still adding to it.
	log.Info("shutting down", "drain_timeout", drain.String())
	shutCtx, cancelShut := context.WithTimeout(context.Background(), *drain)
	defer cancelShut()
	if err := httpSrv.Shutdown(shutCtx); err != nil {
		log.Warn("drain incomplete", "error", err)
	}
	if err := audit.Close(shutCtx); err != nil {
		log.Warn("audit flush incomplete", "error", err)
	}
	log.Info("stopped")
	return nil
}
