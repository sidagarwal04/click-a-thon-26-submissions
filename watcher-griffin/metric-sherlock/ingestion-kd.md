# Ingestion Pipeline — Knowledge Doc

How the `ingestion/` module works, end to end. It is a **standalone, disposable
data-ingestion layer** for the four star-schema entities (`ad_events`, `apps`,
`advertisers`, `geo_device`). It imports nothing from `engine/`, `api/`, or
`clickhouse/` (Python-wise), has its own `requirements.txt` and `config.py`,
and only ever *reads* from `Data/` — deleting the directory breaks nothing
else in the repo.

## The pipeline in one line

```
Source.records() ──> transformers.normalize() ──> pydantic schema ──> validators.validate()
                                                                          │
                                              valid ──> valid Sink        │
                                              invalid ─> dead-letter Sink ┘
```

Everything between the source and the sink operates on plain Python `dict`s.
The only two contracts in the whole module are `Source.records()` (yield raw
dicts) and `Sink.write(entity, rows)` (persist a batch). That is what makes it
transport-agnostic: swapping files for Kafka/Kinesis/Pub-Sub means writing one
new `Source` class and touching nothing else.

## Stage by stage

### 1. Sources (`ingestion/sources/`)

| Source | Mode | Behaviour |
|---|---|---|
| `FileSource` | batch | Reads one parquet/CSV file in chunks (`FILE_CHUNK_SIZE`, default 10,000 rows via pandas), yields each row as a dict, then terminates. Malformed CSV lines (wrong column count) are surfaced as explicit "malformed line" rejects via pandas' `on_bad_lines`, not crashes. |
| `LiveTailSource` | stream | Watches a directory forever, picking up new files **and appended rows**. Persists per-file byte offsets so a restart never reprocesses — the same broker-less pattern as Kafka Connect's FileStreamSource or Filebeat. Blocks between polls (`POLL_INTERVAL_SECONDS`, default 2s). |

### 2. Transform (`transformers.py`)

Normalizes a raw record before any typing happens:

- **Header noise**: column names are case/whitespace/camelCase-normalized, so
  `AppId`, `App_ID`, and `app id` all resolve to `app_id`.
- **Field whitelisting**: only the entity's known fields are kept. Unknown
  columns (e.g. something an unseen dataset added) are dropped deliberately and
  reported in `stats["extra_fields_seen"]` — never a crash, never silent.
- **Null tokens**: `None`, `""`, `"null"`, `"none"`, `"nan"`, `"n/a"`, `"-"`
  are all treated as missing. A missing funnel flag or `revenue` is **rejected,
  never defaulted to 0** — a guessed number would be exactly the fabrication
  the repo guardrails forbid. One deliberate exception: `region` is *not*
  null-collapsed, so a literal `"NA"` survives to validation and gets the
  explicit "did you mean NAM?" error instead of vanishing.
- **Flag coercion**: `is_filled`/`is_impression`/`is_click` accept `1`, `"1"`,
  `1.0` etc., but a non-integral value (`"0.5"`, `1.9`) is rejected — it never
  silently truncates to 0/1.
- **Noise rows**: fully blank rows and re-appearing CSV header lines (common
  when files are concatenated) are recognized and **skipped** (counted in
  `stats["skipped"]`), not dead-lettered as if they were broken data.

### 3. Schema typing (`schemas.py`)

One pydantic model per entity (`AdEventRecord`, `AppRecord`,
`AdvertiserRecord`, `GeoDeviceRecord`) enforces types: `event_time` must parse
as a datetime, funnel flags must be exactly 0/1, `revenue` a float. All models
use `extra="ignore"` as defense-in-depth behind the transformer's whitelist.
Enum membership is deliberately **not** in the models (no `Literal` types) —
that would hardcode dimension values at class-definition time; it lives in the
next stage against env-overridable config instead.

### 4. Business validation (`validators.py`)

Runs on the typed record and returns the **full list of violations, never
fail-fast** — a rejected row's dead-letter entry shows everything wrong with it
at once. Key rules:

- **Funnel monotonicity**: `is_click <= is_impression <= is_filled` must hold.
- **Revenue consistency**: `revenue == 0` when `is_impression == 0`, and never
  negative.
- **Advertiser attribution**: `advertiser_id` must be empty when
  `is_filled == 0` (no ad served → no advertiser) and non-empty when
  `is_filled == 1`.
- **Enum membership**: `ad_format`, `category`, `publisher_tier`, `vertical`,
  `campaign_type`, `region` checked against `config.py`'s sets — all
  overridable via `INGEST_*` env vars, so a new dimension value in an unseen
  dataset needs an env var, not a code change.
- **The `NA` trap**: `region == "NA"` gets a targeted error ("did you mean
  'NAM'?") because `NA` reads as null in many tools.

### 5. Sinks (`ingestion/sinks/`)

- `JsonlSink` — dry-run sink used by `batch`/`stream`: writes accepted rows to
  `<out-dir>/<entity>.valid.jsonl`. Any stray `NaN`/`Infinity` float is
  sanitized to `null` so every line is strictly valid JSON.
- `DeadLetterSink` — writes each rejected row to
  `<out-dir>/<entity>.rejected.jsonl` as `{"record": <raw>, "errors": [...]}`,
  preserving the original raw record alongside all its violations.
- `ClickHouseSink` — used by `load`: one batched `INSERT` per pipeline flush
  with explicitly ordered columns, and bounded retry-with-backoff on transient
  errors (repo principle: no bare unguarded client calls). Rejected rows never
  touch the database.

## Orchestration (`pipeline.py`)

`IngestionPipeline.run()` is agnostic to whether the source is a finite batch
or a never-ending stream:

- `source.records()` runs on a **background producer thread feeding a bounded
  queue** (maxsize 1000). The main loop does a `queue.get(timeout=...)` rather
  than iterating the generator directly — a plain `for` loop would block on
  the *next record*, so a quiet stream would never reach the time-based flush
  and buffered rows would sit invisible until more data arrived.
- **Micro-batched flushing**: buffers flush when they hit `BATCH_MAX_ROWS`
  (default 5,000) *or* `BATCH_MAX_SECONDS` (default 5s) elapses, whichever
  comes first.
- **Clean shutdown**: Ctrl+C against a live stream flushes whatever is
  buffered before returning — already-processed records are never lost.
- **Error isolation**: one bad record never drops the rest of a batch; a
  source-read error propagates only *after* buffered rows are flushed.
- Returns stats: `accepted / rejected / skipped / extra_fields_seen`.

## The three CLI modes (`cli.py`)

```bash
pip install -r ingestion/requirements.txt

# Batch dry-run: one file -> JSONL, then exit
python -m ingestion.cli batch --entity apps --path Data/apps.txt --out-dir ingestion/_out

# Streaming dry-run: tail a watch directory forever (Ctrl+C to stop)
python -m ingestion.cli stream --entity apps --watch-dir ingestion/_incoming --out-dir ingestion/_out

# One-command validated load into ClickHouse (file or directory)
python -m ingestion.cli load --db unseen_v2 Unseen-data/
python -m ingestion.cli load --db unseen_v2 Unseen-data/ad_events.parquet --truncate
```

`batch` and `stream` are pure dry-runs (JSONL sinks only). `load` is the real
thing: it validates every row through the exact same pipeline and inserts
accepted rows into an explicitly named ClickHouse database. Connection details
come from `utils/.env` (`CLICKHOUSE_HOST/PORT/USER/PASSWORD/SECURE`).

### How `load` works (`loader.py`, `detect.py`, `bootstrap.py`)

1. **Live-DB guard** — `--db` equal to the engine's live `CLICKHOUSE_DATABASE`
   aborts without `--force`, because unseen dimension files reuse IDs with
   different attributes and `ReplacingMergeTree` would silently relabel all 9M
   historical facts.
2. **Entity detection** (`detect.py`) — filename stem first (`apps*`,
   `advertisers*`, `geo_device*`, `ad_events*`), falling back to sniffing the
   CSV header / parquet schema against each entity's required field set. Zero
   or multiple matches → abort listing the columns seen. A directory is
   planned **dimensions first, `ad_events` last**.
3. **Bootstrap** (`bootstrap.py`) — `CREATE DATABASE IF NOT EXISTS`, then if
   `ad_events` is absent, run `clickhouse/schema.sql` → `dictionaries.sql` →
   `rollups.sql` statement-by-statement. (A file dependency on `clickhouse/`,
   not a Python import — the isolation claim still holds.)
4. **Non-empty guard** — all planned entities are checked *before the first
   row is written*, so a mid-run abort can't leave a half-guarded state.
   Non-empty tables abort unless `--truncate` (re-loads are not idempotent —
   re-inserting doubles every rollup). `--truncate` on `ad_events` also
   truncates every rollup target table, discovered dynamically from
   `system.tables`, never a hardcoded list.
5. **Ordered ingest** — dimension inserts complete, then
   `SYSTEM RELOAD DICTIONARY` for the three dicts, then facts insert — so
   rollup `dictGet` enrichment sees fresh labels. Loading `ad_events` alone
   into a DB with empty dimension tables emits a loud warning (rows would
   enrich to `''` labels in every `hourly_by_*` rollup).
6. Rejects go to `<out-dir>/<entity>.rejected.jsonl`; a mid-run insert failure
   (after retries) aborts with exact per-entity counts and a note to re-run
   with `--truncate`.

## Config (`config.py`)

Everything shape- or throughput-dependent is env-overridable, nothing
hardcoded:

| Env var | Default |
|---|---|
| `INGEST_AD_FORMATS`, `INGEST_CATEGORIES`, `INGEST_PUBLISHER_TIERS`, `INGEST_VERTICALS`, `INGEST_CAMPAIGN_TYPES`, `INGEST_REGIONS` | the known dimension value sets (comma-separated to override) |
| `INGEST_BATCH_MAX_ROWS` | 5000 |
| `INGEST_BATCH_MAX_SECONDS` | 5.0 |
| `INGEST_POLL_INTERVAL_SECONDS` | 2.0 |
| `INGEST_FILE_CHUNK_SIZE` | 10000 |

## Tests

`pytest ingestion/tests` — fully offline (no live ClickHouse, no network, no
broker). Covers transformers, validators, schemas, batch pipeline flushing,
live-tail offset persistence, entity detection, bootstrap guards, the
JSONL/ClickHouse sinks (the latter against a fake client), and the loader.
