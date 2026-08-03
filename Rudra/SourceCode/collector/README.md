# Collector: streaming ingestion (Vector)

Devices never write to the database. They POST newline-delimited JSON events to this
collector; **Vector** validates, normalizes, batches, buffers, and pushes them to
ClickHouse `sonyliv.raw_events`: the same table, with the **same normalization as the
batch loader** (`ingest/load.sh`), so both paths land identical rows and the model
downstream (`mv_live_sessions`, `hist_minute_full`) does not care which path fed it.

```
devices / simulator --ndjson HTTP--> Vector :8080/ingest --batched gzip HTTPS--> ClickHouse
```

## Run
```bash
cp .env.example .env        # CH endpoint + creds, scale knobs
docker compose up -d

# POST events directly:
curl -X POST --data-binary @events.ndjson http://localhost:8080/ingest
```

## Demo: replay the day as a live stream
```bash
python3 simulator.py --speed 3600               # a day of events in ~24 s
python3 simulator.py --speed 60 --rebase-now    # slower, timestamped "now" for a live dashboard
```
The simulator sends *raw* CSV fields in event-time order; `--speed` compresses delivery
while keeping timestamps intact so minute-grain concurrency stays correct. `--rebase-now`
constant-shifts timestamps (cadence preserved) so `mv_hist_refresh` (the per-minute
refreshable MV) snapshots the stream live into `hist_minute_full`.

## What Vector does (vector.yaml)
- **Validates**: rejects events with null/absent `event_timestamp` / `session_start_epoch` /
  `country` before coercion (a null epoch would otherwise land as 1970-01-01 and corrupt
  the concurrency series). Rejected events go to a **dead-letter log**, nothing is lost silently.
- **Normalizes** (identical to the batch path): epoch-ms → `DateTime64(3)` strings,
  lowercase country/audio, uppercase subtitle, `video_resolution` cleanup
  (`Auto`/`NA`/empty → `unknown`, strip `Auto-`/`NA-`/`0-` prefixes).
- **Batches + buffers**: gzip inserts of up to `BATCH_MAX_EVENTS`, 512 MiB disk buffer,
  adaptive insert concurrency, 10 retries: env-tunable for 100x/1000x without code changes.
- **Observes itself**: Prometheus metrics on :9598 (scraped into ClickStack), health API on :8686.
- **Scale path**: a Kafka/Redpanda source is stubbed in `vector.yaml` for a durable buffer
  tier; run N replicas behind a load balancer.
