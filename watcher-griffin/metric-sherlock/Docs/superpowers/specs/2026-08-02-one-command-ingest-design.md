# One-command validated load: `ingestion.cli load`

Date: 2026-08-02 · Status: approved (design), pending implementation plan
Branch: `ingestion_pipeline`

## Problem

Getting a data drop (e.g. `Unseen-data/`) into ClickHouse today requires four
manual `--entity` runs of the dry-run CLI plus a hand-written insert script,
with three ordering rules the operator must remember (DDL before facts,
dimensions before facts, dictionary reload between them) and one silent
catastrophe available at every step (re-inserting doubles all 18 rollups;
loading unseen dimensions into the main DB relabels 9M historical facts).

Goal: **one command that takes a path — file or directory — validates every
row through the existing ingestion pipeline, and inserts accepted rows into an
explicitly named ClickHouse database**, with the ordering rules and safety
guards enforced by code.

## Decisions (made with the user)

| Question | Decision |
|---|---|
| Destination | Validate **and** insert into ClickHouse (rejects → dead-letter JSONL, never the DB) |
| Target database | `--db` is **always required**, no default |
| Non-empty target | **Refuse unless `--truncate`** (re-loads are not idempotent) |
| Missing DDL | **Auto-bootstrap**: run `schema.sql` → `dictionaries.sql` → `rollups.sql` in the target DB |
| Input shape | **File or directory**; directory ingests all recognized entities in dependency order |
| Approach | Extend `ingestion/` natively (new sink + subcommand), not a wrapper script |
| Flag-coercion defect | Fix in the same change: `_coerce_flag` must reject non-integral values |

## Command surface

```bash
python -m ingestion.cli load --db unseen_v2 Unseen-data/
python -m ingestion.cli load --db unseen_v2 Unseen-data/ad_events.parquet
```

Flags:

- `--db <name>` (required) — target database. Host/port/user/password/secure
  come from `utils/.env` via `python-dotenv`, same variable names as
  `scripts/apply_*.py` (`CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`,
  `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_SECURE`).
- `--truncate` — empty the target entity's tables before inserting (see
  Safety). Without it, a non-empty target aborts.
- `--force` — required only when `--db` equals the engine's live
  `CLICKHOUSE_DATABASE` from `utils/.env`.
- `--out-dir` (default `ingestion/_out`) — dead-letter destination
  (`<entity>.rejected.jsonl`).
- `--ddl-dir` (default `<repo>/clickhouse`) — where bootstrap finds the three
  SQL files. This is a *file* dependency on `clickhouse/`, not a Python
  import; the module's isolation claim (no imports from `engine/`,
  `clickhouse/`, `api/`) still holds.

Existing `batch` and `stream` subcommands are unchanged. Output is one stats
line per entity: `accepted / rejected / skipped / inserted` plus the
dead-letter path when rejects exist.

## Components

### `ingestion/detect.py` — entity auto-detection

1. Filename stem match: `apps*` → `apps`, `advertisers*` → `advertisers`,
   `geo_device*` → `geo_device`, `ad_events*` → `ad_events`.
2. Fallback: sniff columns (CSV header line / parquet schema), normalize with
   the existing `transformers._normalize_key`, and select the entity whose
   required field set the columns cover.
3. Zero or multiple candidate entities → abort listing the columns seen.
4. Directory input: detect every recognizable file; unrecognized files are
   reported and skipped. Processing order is always dimensions
   (`apps`, `advertisers`, `geo_device`) then `ad_events`.

### `ingestion/sinks/clickhouse_sink.py` — the missing sink

- Implements the existing `Sink.write(entity, rows)` contract with
  `clickhouse-connect`.
- One batched `INSERT` per pipeline flush (pipeline already micro-batches at
  `BATCH_MAX_ROWS = 5000`), columns explicitly ordered.
- Bounded retry-with-backoff on transient errors (repo principle 3: no bare
  unguarded client calls). After retries are exhausted, the error propagates —
  see Error handling.
- Supporting pipeline change: `_process` returns Python-mode dicts
  (`model_dump()`, real `datetime`/`float`) instead of `mode="json"` strings.
  `JsonlSink` already handles non-JSON types via `default=str`, so the dry-run
  path is unaffected. `revenue` (float) inserts cleanly into `Decimal64(6)`.
- Rejected rows never touch the database; they remain JSONL dead letters.

### `ingestion/bootstrap.py` — DDL, ordering, and guards

- `CREATE DATABASE IF NOT EXISTS <db>` (client connected without a database),
  then, if `ad_events` is absent in the target, execute
  `schema.sql` → `dictionaries.sql` → `rollups.sql` statement-by-statement
  (split on `;`, comments stripped) with the client's database set to the
  target. All three files use unqualified table names, so no rewriting is
  needed. App-state tables (`investigations`, `metric_events`, …) are out of
  scope — they belong to `scripts/apply_*.py`.
- **Non-empty guard**: per entity, `SELECT count()` before inserting;
  non-empty aborts with the `--truncate` recipe. `--truncate` on `ad_events`
  also truncates every rollup target table in the DB, discovered from
  `system.tables` (MergeTree-family tables that are targets of the DB's
  materialized views) — never a hardcoded list.
- **Ordering**: dimension inserts complete → `SYSTEM RELOAD DICTIONARY` for
  `apps_dict`, `advertisers_dict`, `geo_device_dict` → facts insert. This
  guarantees rollup `dictGet` enrichment sees the fresh labels.
- Loading `ad_events` alone while the target's dimension tables are empty
  emits a loud warning (rows would enrich to `''` labels in every
  `hourly_by_*` rollup).
- **Live-DB guard**: `--db` equal to `utils/.env`'s `CLICKHOUSE_DATABASE`
  aborts without `--force` (the unseen dimension files reuse IDs with
  different attributes; `ReplacingMergeTree` would silently relabel all
  historical facts — PROGRESS.md "Unseen dataset" section).

### `transformers._coerce_flag` fix

Non-integral numerics (`"0.5"`, `1.9`) currently truncate to 0/1 and are
accepted, violating the module's "never silently defaulted" policy. Change:
a float (or float-parsed string) whose value is not exactly integral returns
`None` → the row is rejected with the standard "could not parse … as 0/1"
message. Integral floats (`1.0`, `"0"`) keep coercing as today.

## Error handling

- Connection/authentication failure: abort before any write, non-zero exit.
- Insert failure mid-run (after retries): abort with exact per-entity counts
  inserted so far and an explicit note that the partial load must be re-run
  with `--truncate` (inserts are not idempotent).
- Validation rejects do not stop the run: they are counted, dead-lettered,
  and reported — same semantics as `batch` mode today.
- Producer (source-read) errors propagate after buffered rows are flushed,
  as the pipeline already does.

## Testing

Offline (module tests must keep passing with no live ClickHouse / network):

- `detect.py`: filename match, header sniff (CSV + parquet), ambiguous and
  unrecognizable inputs, directory ordering.
- `ClickHouseSink`: batched write, column ordering, retry exhaustion — against
  a fake client object.
- Bootstrap guards: non-empty abort, `--truncate` table discovery, live-DB
  `--force` gate — against a mocked client.
- `_coerce_flag`: non-integral rejection (`"0.5"`, `1.9`), integral floats
  still accepted.

Post-build verification (manual, live): `load --db <scratch>` on
`Unseen-data/`, then reconcile row counts (2,000 / 500 / 5,000 / 1,500,000)
and total revenue (`$2,530.4381`) against the values already verified in
PROGRESS.md, and confirm `hourly_overall` has 120 rows.

## Dependencies

`ingestion/requirements.txt` gains `clickhouse-connect` and `python-dotenv`.

## Out of scope

- Pointing the engine at the newly loaded DB (that is `utils/.env` +
  restart, and the 5-days-vs-28-day-baseline question — PROGRESS.md).
- Streaming (`stream` subcommand) inserting into ClickHouse.
- App-state DDL (`monitoring_state.sql`, `apply_*.py` territory).
- The LiveTailSource torn-write/truncation defects (documented separately).
