// Command sonyliv is the CLI entry point for the concurrency pipeline.
//
// Subcommands are added as the model is built. `verify` exists first because
// the repo's first non-negotiable is that nothing is trusted until the stack is
// confirmed up and pointing at the database you think it is.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"text/tabwriter"
	"time"

	"github.com/d-cryptic/clickathon/internal/chdb"
	"github.com/d-cryptic/clickathon/internal/config"
)

// version is stamped by the linker: see LDFLAGS in the Makefile.
var version = "dev"

// main does nothing but translate a status code, because os.Exit skips deferred
// calls — including the signal-handler teardown in cli().
func main() {
	os.Exit(cli())
}

func cli() int {
	// A signal-aware context so a long query dies on Ctrl-C instead of orphaning.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, os.Args[1:]); err != nil {
		if errors.Is(err, context.Canceled) {
			fmt.Fprintln(os.Stderr, "cancelled")
			return 130
		}
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	return 0
}

func run(ctx context.Context, args []string) error {
	if len(args) == 0 {
		usage()
		return errors.New("no subcommand given")
	}

	switch args[0] {
	case "verify":
		return cmdVerify(ctx, args[1:])
	case "observe":
		return cmdObserve(ctx, args[1:])
	case "version":
		fmt.Println(version)
		return nil
	case "help", "-h", "--help":
		usage()
		return nil
	default:
		usage()
		return fmt.Errorf("unknown subcommand %q", args[0])
	}
}

func usage() {
	fmt.Fprint(os.Stderr, `sonyliv — foreground-only concurrency at streaming scale

usage:
  sonyliv verify [-target local|cloud]    confirm the stack is up and show table state
  sonyliv observe [-target local|cloud]   emit watermark lag, build-stage timing and the
                                           reconcile gate outcome to ClickStack over OTLP
                                           (-dry-run to print without emitting)
  sonyliv version                         print the build version
  sonyliv help                            this message

Connection settings come from .env (see .env.example). TARGET=cloud selects the
graded Cloud service; the default is local. observe additionally reads
CLICKSTACK_OTLP and CLICKSTACK_INGESTION_KEY (tools/clickstack-bootstrap.sh).
`)
}

func cmdVerify(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("verify", flag.ContinueOnError)
	target := fs.String("target", string(config.TargetFromEnv()), "which clickhouse to check: local or cloud")
	timeout := fs.Duration("timeout", 30*time.Second, "overall timeout")
	if err := fs.Parse(args); err != nil {
		return err
	}

	cfg, err := config.Load(config.Target(*target))
	if err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(ctx, *timeout)
	defer cancel()

	conn, err := chdb.Open(ctx, &cfg)
	if err != nil {
		return err
	}
	defer func() { _ = conn.Close() }()

	serverVersion, err := chdb.ServerVersion(ctx, conn)
	if err != nil {
		return err
	}

	fmt.Printf("target   %s\n", cfg.Target)
	fmt.Printf("server   %s @ %s\n", serverVersion, cfg.Addr())
	fmt.Printf("database %s (user %s)\n\n", cfg.Database, cfg.User)

	tables, err := chdb.Tables(ctx, conn, cfg.Database)
	if err != nil {
		return err
	}
	if len(tables) == 0 {
		return fmt.Errorf("database %q has no tables — apply sql/00_schema.sql and sql/10_intervals.sql", cfg.Database)
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(w, "TABLE\tENGINE\tROWS")
	for _, t := range tables {
		fmt.Fprintf(w, "%s\t%s\t%d\n", t.Name, t.Engine, t.Rows)
	}
	return w.Flush()
}
