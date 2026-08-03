# ingestion — standalone, disposable data-ingestion module

Self-contained validation + transformation layer for the four star-schema
entities (`ad_events`, `apps`, `advertisers`, `geo_device`). Delete this
directory and nothing else in the repo breaks: it does not import from
`engine/`, `clickhouse/`, or `api/`, has its own `requirements.txt` and
`config.py`, and only ever *reads* files under `Data/` (never writes there).

Two sinks are available: a JSONL dry-run sink (used by `batch`/`stream`) that
writes validated rows to local files for inspection, and a `ClickHouseSink`
(used by `load`) that performs real INSERT operations into ClickHouse. The
`Sink` interface is generic, so validation and transformation code is
unchanged across both paths.

## Why it's migratable to Kafka (or anything else)

`Source.records()` and `Sink.write()` are the only two contracts. Two
concrete `Source`s exist today:

- `sources/file_source.py` — reads a parquet/CSV file, terminates (batch).
- `sources/live_tail_source.py` — watches a directory for new/appended
  files and streams rows continuously, blocking between polls, persisting
  per-file offsets so a restart never reprocesses (streaming, self-contained,
  no broker required — the same pattern Kafka Connect's FileStreamSource or
  Filebeat use).

Everything from `transformers.py` onward operates on plain `dict` records
and has zero knowledge of files, polling, or any transport. Swapping in
Kafka, Kinesis, Pub/Sub, RabbitMQ, or a webhook receiver later means writing
one new class that implements `records()` — deserialize a message, yield a
dict, block on the consumer's own `poll()` — with no changes to
`transformers.py`, `validators.py`, or `pipeline.py`.

## Pipeline

```
source.records() -> transformers.normalize() -> schemas.<Entity>Model(**row)
                  -> validators.validate() -> valid_sink.write() / dead_letter_sink.write()
```

Every record gets the full list of violations (never fail-fast) — a rejected
row's dead-letter entry shows everything wrong with it, not just the first
problem found. One bad record never drops the rest of a batch.

### Production edge cases handled

- **Header noise**: column names are case/whitespace/camelCase-normalized
  (`AppId`, `App_ID`, `app id` all resolve to `app_id`) before field matching.
- **Field selection**: only each entity's known fields are read from a raw
  record; anything else (a column the unseen dataset added) is dropped
  intentionally and reported back via `stats["extra_fields_seen"]` — never a
  crash, never silently absorbed by accident.
- **Nulls & placeholder tokens**: `None`, `""`, `"null"`, `"none"`, `"nan"`,
  `"n/a"`, `"-"` are all recognized as "missing." A missing/garbled funnel
  flag (`is_filled`/`is_impression`/`is_click`) or `revenue` is **rejected
  with a clear message, never silently defaulted to 0** — a guessed number
  here would be exactly the kind of fabrication the guardrails forbid.
  Exception: the `region` field is deliberately NOT null-collapsed, so a
  literal `"NA"` survives into validation and gets the explicit "did you mean
  NAM?" hint instead of silently becoming an empty value.
- **Unwanted rows**: a fully blank row, or a CSV header line re-appearing in
  the body (common when files get concatenated), is recognized as noise and
  **skipped** (counted in `stats["skipped"]`) rather than dead-lettered as if
  it were a real, broken record.
- **Malformed lines**: a CSV row with the wrong column count (`file_source.py`
  via pandas' `on_bad_lines`, `live_tail_source.py` via a token-count check)
  is rejected with an explicit "malformed line" message instead of crashing
  the read or silently truncating/padding it.
- **Non-finite JSON values**: any stray `NaN`/`Infinity` float reaching a sink
  (e.g. from a source library's own missing-value convention) is sanitized to
  `null` before writing — every line written is guaranteed strictly valid
  JSON.

## Usage

```bash
pip install -r ingestion/requirements.txt

# Batch: ingest one file, then exit
python -m ingestion.cli batch --entity apps --path Data/apps.txt --out-dir ingestion/_out

# Streaming: tail a watch directory forever (Ctrl+C to stop cleanly)
python -m ingestion.cli stream --entity apps --watch-dir ingestion/_incoming --out-dir ingestion/_out
# ...then, from another terminal, drop/append rows into ingestion/_incoming/ and
# watch them land in ingestion/_out/apps.valid.jsonl within one poll interval.

# One command: validate a whole drop (or one file) and insert into ClickHouse.
# --db is always explicit; refuses non-empty tables without --truncate;
# bootstraps schema/dictionaries/rollups in a fresh database automatically.
python -m ingestion.cli load --db unseen_v2 Unseen-data/
python -m ingestion.cli load --db unseen_v2 Unseen-data/ad_events.parquet --truncate
```

Run the tests (no live ClickHouse, no network, no broker required):

```bash
pytest ingestion/tests
```

## Config

All enum sets and thresholds are env-overridable (see `config.py`) — nothing
about dataset shape or size is hardcoded, so an unseen incident dataset with
a new dimension value or different throughput doesn't need a code change.
