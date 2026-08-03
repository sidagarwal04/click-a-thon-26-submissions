package main

import (
	"context"
	"errors"
	"flag"
	"fmt"

	"github.com/sonyliv-clickathon/ingest/internal/chx"
	"github.com/sonyliv-clickathon/ingest/internal/config"
)

// cmdDoctor is the preflight for a service this pipeline has not run against
// before.
//
// It exists because the two environments differ in ways that a successful
// connection does not reveal. ClickHouse Cloud turns `ENGINE = MergeTree` into
// SharedMergeTree, which reads a different deduplication window than the local
// engine and expires it on a timer; it also enables async_insert by default,
// which this pipeline deliberately turns off. Each of those is silent — the
// load succeeds and the guarantee is quietly weaker. Better to print the
// difference before the first load than to infer it from a row count later.
func cmdDoctor(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("doctor", flag.ExitOnError)
	envPath := fs.String("env", "", "path to .env (default: nearest .env walking up)")
	_ = fs.Parse(args)

	cfg, err := config.Load(*envPath)
	if err != nil {
		return err
	}
	fmt.Printf("target      : %s\n", cfg.Redacted())
	fmt.Printf("tls         : %t\n", cfg.Secure)
	if !cfg.Secure && !isLocal(cfg.Host) {
		fmt.Printf("  WARNING   : CLICKHOUSE_SECURE=false against a remote host sends credentials in the clear\n")
	}

	client, err := chx.Open(ctx, cfg)
	if err != nil {
		return err
	}
	defer client.Close()

	report, err := client.Preflight(ctx)
	if err != nil {
		return err
	}

	fmt.Printf("server      : ClickHouse %s\n", report.Version)
	fmt.Printf("deployment  : %s\n", report.Deployment)
	fmt.Printf("database    : %s (%s)\n", cfg.Database, existsWord(report.DatabaseExists))
	fmt.Println()

	fmt.Println("session defaults this pipeline overrides:")
	fmt.Printf("  async_insert            server=%s  pipeline=0 for bulk, 1 for control rows\n", report.AsyncInsertDefault)
	fmt.Println()

	if len(report.Tables) > 0 {
		fmt.Println("deduplication settings in place (blank = table not created yet):")
		// 24 wide: SharedReplacingMergeTree is the longest engine name this
		// pipeline creates, and it is what Cloud makes of content_dim.
		fmt.Printf("  %-18s %-24s %-10s %-10s %s\n", "table", "engine", "non_repl", "repl", "repl_seconds")
		for _, tb := range report.Tables {
			fmt.Printf("  %-18s %-24s %-10s %-10s %s\n",
				tb.Name, dash(tb.Engine), dash(tb.NonReplicatedWindow), dash(tb.ReplicatedWindow), dash(tb.ReplicatedWindowSeconds))
		}
		fmt.Println()
	}

	problems := report.Problems(cfg.User)
	if len(problems) == 0 {
		fmt.Println("no problems found — safe to run `sonyliv-ingest schema`")
		return nil
	}
	fmt.Println("problems:")
	for _, p := range problems {
		fmt.Printf("  - %s\n", p)
	}
	fmt.Println("\nMost of these are fixed by re-running `sonyliv-ingest schema`, which\n" +
		"converges an existing database rather than only creating a missing one.")
	return errors.New("preflight found problems; fix them before loading")
}

func isLocal(host string) bool {
	return host == "localhost" || host == "127.0.0.1" || host == "::1"
}

func existsWord(ok bool) string {
	if ok {
		return "exists"
	}
	return "does not exist yet — `sonyliv-ingest schema` will not create it, see README"
}

func dash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}
