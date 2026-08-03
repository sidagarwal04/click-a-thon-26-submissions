# `scripts/` — one-command database bring-up

Stands up a complete ClickHouse database from nothing: every table, view,
materialized view and dictionary, then the seed data, then verification that
refuses to pass quietly.

```bash
./scripts/bootstrap.sh
```

That is the whole thing. With no arguments it targets `$CLICKHOUSE_DATABASE`
(default `sonyliv`), creates the schema, loads the seed CSVs if it can find
them, builds the interval and serving tiers, and runs seven assertions.

## Prerequisites

| Need | Why | If missing |
|---|---|---|
| `python3` | splits and POSTs the DDL over HTTPS | hard requirement — stdlib only, nothing to `pip install` |
| Go toolchain | builds `sonyliv-ingest` for the CSV load | only needed for `--seed`; use `--no-seed` without it |
| `.env` or env vars | connection details | see below |

`clickhouse-client` is **not** required. The applier talks to the HTTPS
endpoint directly, so the script runs on a machine with nothing installed.

## Configuration

Read from the environment, falling back to `.env` in the repo root. The
password is never printed, not even in an error.

```bash
CLICKHOUSE_HOST=qz1k8n597s.ap-south-1.aws.clickhouse.cloud
CLICKHOUSE_HTTP_PORT=8443      # 8443 on Cloud, 8123 locally
CLICKHOUSE_DATABASE=sonyliv
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=…
CLICKHOUSE_SECURE=true         # false -> plain HTTP for local dev
```

`.env` is gitignored. Note the existing `~/.clickhouse-client/config.xml`
points at the **native** port 9440; this script needs the **HTTP** port 8443.

## Flags

| Flag | Effect |
|---|---|
| `--dry-run` | print every statement in order, execute nothing. Needs no connection. |
| `--database NAME` | target a different database — `sonyliv`, `sonyliv_prod`, a scratch `sonyliv_dev` |
| `--no-seed` | schema only. Use this when the data arrives later. |
| `--seed-only` | data into a schema that already exists |
| `--verify-only` | run the assertions, change nothing |
| `--force` | permit a load into a non-empty target. Read the warning first. |
| `--content FILE` / `--events FILE` | name the seed CSVs instead of searching |

## For data that arrives in a few hours

```bash
./scripts/bootstrap.sh --no-seed                       # now: schema is ready and waiting
./ingest/bin/sonyliv-ingest events --file new-data.csv # later: load, repeatable per file
./scripts/bootstrap.sh --verify-only                   # then: assert it is coherent
```

The loader derives an `insert_deduplication_token` from
`source | file-fingerprint | batch-size | row-count | ordinal`, and chunks are
cut by the reader rather than by whichever worker is free — so ordinal *N* is
the same bytes on every replay and re-running one file is a no-op. Loading a
*different* file is not swallowed, because the fingerprint differs.

## Object manifest, in creation order

| Stage | File | Creates |
|---|---|---|
| 1 | `ingest/sql/001_content.sql` | `content_dim`, `content_current`, `content_dict` |
| 1 | `ingest/sql/002_events_raw.sql` | `events_raw`, `dirty_sessions`, `events_raw_to_dirty_mv` |
| 1 | `ingest/sql/003_events_clean.sql` | `events_clean`, `events_raw_to_clean_mv`, `events_dedup` |
| 1 | `ingest/sql/004_ingest_control.sql` | `ingest_batches`, `ingest_rejects` |
| 2 | `pipeline/sql/010_active_intervals.sql` | `active_intervals`, `active_intervals_current`, `pipeline_watermark` |
| 2 | `pipeline/sql/020_serving_layer.sql` | `concurrency_deltas`, `concurrency_bucket_net`, `concurrency_day_anchor`, `concurrency_deltas_to_bucket_mv`, `session_live_state` |
| 2 | `pipeline/sql/040_concurrency_minute.sql` | `concurrency_minute_versions`, `concurrency_minute_mask13` |
| 3 | seed | `content` then `events` CSV |
| 3b | `pipeline/sql/011`, `022` | populates the interval and serving tiers |
| 4 | — | verification |

Order is load-bearing: a materialized view must be created **after** its target
table, or it drains into nothing.

## What the verification actually checks

The figures this project knows — 31,947 intervals, peak 2,305 — will not be
known for unseen data, so **no assertion may depend on recognising them**. Every
check ties a stage's output back to its own input.

| | Check | Why it exists |
|---|---|---|
| V1 | every expected object exists | catches a half-applied deployment before it is mistaken for a data problem |
| V2 | `content_dict` LOADED **and non-empty on every replica** | a dictionary is the only per-replica object here, and an **empty one still reports `LOADED`** — so `dictGetOrDefault` silently returns the default for every row, on one replica only, depending on routing |
| V3 | enrichment is not 100% fallback | a dimension that is entirely `__unknown__` is a failure, not a data characteristic |
| V4 | **conservation**: `sum(opens)` in `concurrency_deltas` == `count()` in `active_intervals_current` | the only check that works without already knowing the answer, and therefore the only one worth anything on judging day |
| V5 | `sum(delta) = 0` | every interval that opens also closes |
| V6 | no stuck mutations | a failed mutation leaves a table quietly wrong |
| V7 | `ingest_rejects` empty | empty **is** the passing state; a non-zero count is reported, never swallowed |

**V4 is the one that matters.** V5 and the other balance invariants are
necessary but not sufficient: a curve loaded twice has `sum(net) = 0`,
`min(running) = 0` and `opens = closes` — it passes all of them while being
exactly 2× wrong. That shipped on 2026-08-01. V4 catches it because it compares
against a source *outside* the layer being checked, and it prints the ratio, so
a clean `2.0` names its own cause.

## Why it refuses to reload by default

`concurrency_deltas` is a `SummingMergeTree`. A second load **adds** to the
first. `insert_deduplication_token` does **not** make a large `INSERT SELECT`
idempotent — a 524k-row insert is split across blocks and the token is suffixed
per block, so two runs whose block boundaries differ produce different dedup
keys and both land.

So the seed stage guards on the target being empty and fails loudly with the
row count and the options. Overwriting is a deliberate act (`--force`), not a
retry.

## When a stage fails

The applier prints the file, the statement index, the statement, and the server
error, then stops. Nothing after it runs. Fix the cause and re-run: the DDL
stages are idempotent, so re-running costs nothing.

`--dry-run` prints the exact statement set without a connection, which is the
fastest way to check what a stage *would* do.
