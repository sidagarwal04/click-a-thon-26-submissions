# Generated DDL — per spec

Each `{spec}.sql` was authored + validated + applied to ClickHouse Cloud and pushed by the
**Instrumentation Agent** (via the `clickhouse_git_write` MCP, direct to `master`). The
`{spec}.metrics.json` sibling holds the confirmed PM metrics the Context Agent registers.

The 6th (unseen) spec's DDL is in [`../unseen-6th-spec/`](../unseen-6th-spec/).

Every table uses the JSON-`payload` design with a daily AggregatingMergeTree rollup + MV
where the metrics earn it. Schema quality notes (ordering keys, partitioning, TTL, skip
indexes, the D1/D2 deviations) are documented in `../../ARCHITECTURE.md` and the context
bundle's `tables/` concepts.
