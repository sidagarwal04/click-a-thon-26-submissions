# Atlys OTEL Pipeline - Parquet to ClickHouse

Reads the 8 Atlys event Parquet files and ingests them into ClickHouse Cloud
via an OpenTelemetry Collector (otelcol-contrib).

## Architecture

    emit.py  (Python)
      | OTLP/gRPC -> localhost:4317
      v
    otelcol-contrib
      batch processor  (10K rows/flush - insert-batch-size rule)
      routing connector  (resource attr: atlys.table)
      |
      +-> logs/destination_card_clicked  ->  ClickHouse: destination_card_clicked
      +-> logs/application_started       ->  ClickHouse: application_started
      +-> logs/document_uploaded         ->  ClickHouse: document_uploaded
      +-> logs/purchase_completed        ->  ClickHouse: purchase_completed
      +-> logs/search_typed              ->  ClickHouse: search_typed
      +-> logs/landing_page_scrolled     ->  ClickHouse: landing_page_scrolled
      +-> logs/auth_completed            ->  ClickHouse: auth_completed
      +-> logs/pay_now_clicked           ->  ClickHouse: pay_now_clicked

## Quick start

1. Configure credentials:
   cp .env.example .env
   # Edit .env: CH_ENDPOINT, CH_USER, CH_PASSWORD, CH_DATABASE

2. Create ClickHouse tables (skip if done):
   clickhouse-client --host HOST --user default --password PW --secure \
     --database default --multiquery < ../data/ddl.sql

3. Start the collector:
   docker compose up

4. Run the emitter:
   pip install -r requirements.txt
   python emit.py                          # all 8 tables
   python emit.py --table purchase_completed   # single table
   python emit.py --batch 50000               # custom batch size

## File reference

  collector-config.yaml  - OTEL Collector config
  docker-compose.yaml    - Runs otelcol-contrib:0.103.0
  .env.example           - ClickHouse credential template
  emit.py                - Python emitter (Parquet -> OTLP LogRecords)
  requirements.txt       - Python dependencies

## Design notes

Batching (insert-batch-size CRITICAL):
  batch processor: send_batch_size=10000, timeout=5s
  emitter default: --batch 10000
  Each ClickHouse INSERT is 10K-100K rows - prevents part explosion.

Routing:
  Each Parquet file sets resource attr atlys.table=<name>.
  Routing connector fans out to the correct per-table pipeline + CH exporter.

Retry / backpressure:
  retry_on_failure: 5s -> 60s backoff, max 5min.
  sending_queue: 1000 items, 4 consumers.

Column mapping:
  emit.py sets LogRecord.attributes = row dict (full Parquet row).
  ClickHouse exporter writes attributes as columns - matches flat DDL schema.
