# `sonyliv-api` — HTTP event ingest into `events_raw`

Design for the long-lived service. Accepts events over HTTP and writes them to
the landing zone, reusing the existing write path rather than adding a second one.

---

## 1. What it reuses

Almost everything. The API is a handler that turns a request body into
`chx.Chunk`s and feeds `chx.Loader`.

| Existing | Role in the API |
|---|---|
| `config.Load(envPath)` | ClickHouse settings from `/etc/sonyliv/sonyliv.env` |
| `chx.NewClient` | connection; already forces `async_insert: 0` at connection level |
| `chx.Loader` / `Loader.Run(ctx, chunks)` | the write path, retries, dedup token, audit |
| `chx.Chunk{Ordinal, Rows}` | unit of insert |
| `model.RawEvent` / `InsertColumns` / `Values()` | wire shape — unchanged |
| `csvsrc.ParseEpochMillis`, `ParseContentID` | validators, including the mis-scaled-timestamp bounds |
| `csvsrc.Reason*` constants + `ingest_rejects` | quarantine, same reasons as the CSV path |
| `chx.AuditWriter` → `ingest_batches` | per-batch audit row |
| `chx.ValidateWritePath(workers, retries)` | flag validation |

No new insert path, no second normalization rule. `model.RawEvent`'s contract holds:
**the API validates and rejects but never corrects.** No case folding, no event
classification, no empty-to-unknown — all of that stays in
`events_raw_to_clean_mv` so this producer, the CSV loader and the generator agree
by construction rather than by three clients implementing the same thing.

---

## 2. Measured: async insert and the dedup token do NOT conflict

An earlier draft of this design claimed they did — that because ClickHouse's async
insert queue groups pending inserts by a hash of (query, settings, format), and
`insert_deduplication_token` is a setting, a unique token per request would force
every request into its own block and defeat coalescing entirely. That reasoning
led to a two-mode design, split by request size.

**It is wrong.** Measured on ClickHouse 26.7.1, 60 concurrent HTTP inserts of 10
rows each, `async_insert=1, wait_for_async_insert=1`, into a `MergeTree` with
`non_replicated_deduplication_window = 1000`:

| run | arm | client inserts | server flushes | inserts/flush |
|---|---|---:|---:|---:|
| A first | distinct token per request | 60 | 5 | 12 |
| A first | no token | 60 | 4 | 15 |
| **B first** | distinct token per request | 60 | **3** | **20** |
| **B first** | no token | 60 | 5 | 12 |

Swapping the order flips which arm looks better, so the entire difference is
warmup — whichever arm runs second wins. The token has **no effect on grouping**.
Both arms landed all 600 rows, so dedup produced no false positives either.

Separately confirmed: **dedup works under `async_insert`.** Two inserts carrying
the same `insert_deduplication_token` yield 2 rows, not 4.

Inserts must be sent **concurrently** to observe any of this. With
`wait_for_async_insert=1` a sequential client blocks on its own flush, so nothing
can ever coalesce regardless of settings — which is why the first attempt at this
test measured nothing useful.

### Consequence: always set the token

Coalescing and exactly-once are both available at once, so the two-mode split is
deleted. Every insert carries `insert_deduplication_token`.

A size threshold survives, but for a different and better reason — one already
argued in `client.go`: bulk data should not be routed through a buffer designed
for small writes.

| request rows | mode | why |
|---|---|---|
| ≥ `--sync-threshold` (default 10,000) | synchronous insert | The client already batched well; server-side buffering adds latency and nothing else. This is why `client.go` forces `async_insert: 0` at the connection level. |
| < threshold | async insert, `wait_for_async_insert=1` | Chatty producers sending hundreds of rows. The server coalesces across producers into sensible parts — measured at 12–20 client inserts per flush. |

Both modes set the token, so retries are idempotent in both. The response reports
which ran (`"mode": "sync" | "async"`) so behaviour is never a mystery client-side.

**One caveat on transferring this to Cloud.** The test ran against a
non-replicated `MergeTree` using `non_replicated_deduplication_window`. Cloud's
`SharedMergeTree` deduplicates through a different path
(`replicated_deduplication_window`, which `002_events_raw.sql` sets to 1000).
Coalescing is queue behaviour and should be identical, but re-run the same two
arms against the real service before relying on the exactly-once half.

Reproduce: `ingest/testdata/async_coalescing_test.sh`.

---

## 3. Idempotency

In sync mode the token is what makes a retry safe. It must not reuse the CSV
loader's fingerprint scheme unchanged:

```
dedupToken = source | fingerprint | bs=N | n=rows | ordinal
```

For a CSV, `fingerprint` is the file SHA-256 and `ordinal` is the chunk index —
deterministic and replayable. For an API with a long-lived loader and a constant
fingerprint, two *different* requests with equal row counts and the same ordinal
produce the **same token**, and ClickHouse silently drops the second as a
duplicate. That is silent data loss, and it is the single easiest way to get this
wrong.

So: **`Fingerprint` = the `Idempotency-Key` request header, or the SHA-256 of the
request body if absent.** Then a retry of the same payload dedups (exactly-once,
which is the point) and distinct payloads never collide.

Because `Fingerprint` lives in `LoaderOptions` rather than in `Chunk`, this means
**one `Loader` per request** — `NewLoader`, feed chunks, close the channel, read
`Stats`. Workers are `min(--workers, chunkCount)`, so a small request spawns one
goroutine. The alternative, moving `Fingerprint` into `Chunk`, is arguably the
cleaner model but changes tested shared code for no benefit at this scale.

`RunID` is allocated **once at process start**, matching its documented meaning
("groups every batch of one pipeline invocation"), so `ingest_batches` groups all
of a process's API batches. `Source` is the constant `"api"` — deliberately *not*
client-supplied, because source participates in the token and a client changing
it mid-retry would break dedup.

### Measured, and one subtlety the smoke test surfaced

Replaying a POST byte-for-byte against a live ClickHouse: `events_raw` held **10
rows, not 13** — the replayed chunk was deduplicated by its token, and all 10 rows
were distinct semantic keys. Exactly-once on the landing zone holds.

But `events_clean` transiently held **13**. That is not a bug, and it is worth
knowing before someone "fixes" it:
`deduplicate_blocks_in_dependent_materialized_views` defaults to `0`, so when the
raw insert is dropped as a duplicate, the materialized view's own insert into
`events_clean` is **not** covered by the same token and still lands. The three
extra rows then collapse on the next merge, because `events_clean` is a
`ReplacingMergeTree(row_version)` keyed on the semantic event key — and
`events_dedup` returned 10 the whole time, since it resolves by `argMax` without
waiting for a merge.

So the layering does exactly what it was built to do, and the counts mean what
they say: `events_raw` is exactly-once and its duplicate-rate metric stays honest;
`events_clean` may carry transient duplicates; every read through `events_dedup`
is already resolved. Turning
`deduplicate_blocks_in_dependent_materialized_views = 1` would make the MV honor
the token too, at the cost of making `events_clean` depend on insert-level dedup
rather than on its own engine — not worth it, since the current arrangement is
correct at every read.

---

## 4. Chunking, and the 20-bit trap

`Loader.Run` sets `BatchRowSeq = uint32(i)` per chunk, and `row_version` in
`003_events_clean.sql` packs it as `(ingest_millis << 20) | seq`. That leaves
**1,048,575** as the maximum sequence. The CSV loader is safe because it cuts at
`--batch-size` (default 50,000), but an API accepts whatever it is handed — so
this is where the handoff's "unenforced bound" becomes reachable.

Two hard limits, both enforced before any row is parsed into a chunk:

- `--max-rows` per request (default 500,000)
- `--max-body` bytes (default 64 MiB)

and the request is always split into chunks of at most `--batch-size`, so `seq`
never exceeds 50,000. Exceeding either limit is `413`, not a truncation.

---

## 5. Wire format

`POST /v1/events`

Two content types, both streamed with `json.Decoder` so memory is bounded by one
event, not by the request:

- `application/x-ndjson` — one event per line. Preferred for producers.
- `application/json` — a JSON array. Convenient for `curl` and tests.

Field names are the `events_raw` column names, which are also the source CSV
header. Timestamps are **epoch milliseconds as integers**, matching the source —
no RFC3339, so there is no timezone ambiguity to get wrong.

```json
{
  "video_session_id": "94D660E9...8DAC",
  "user_id": "7C7D3C62...858D",
  "content_id": 21311522,
  "event_type": "VideoHeartbeat",
  "event": "network-activity",
  "event_timestamp": 1785062011289,
  "session_start_epoch": 1785062007336,
  "platform": "JIO_ANDROID_TV",
  "app_version": "3.9.4",
  "country": "india",
  "audio_language": "hin",
  "subtitle_language": "UNK",
  "player_version": "1.8.2"
}
```

### Response

```json
{
  "accepted": 4821,
  "rejected": 3,
  "batches": 1,
  "mode": "async",
  "ingest_batch_ids": ["..."],
  "rejects": [{"index": 117, "reason": "bad_timestamp", "detail": "..."}]
}
```

`200` with a non-zero `rejected` count is a **success** — partial acceptance
matches the CSV path, which quarantines bad rows into `ingest_rejects` and keeps
going. It also stays idempotent: the same body yields the same accepted set, hence
the same token.

`ingest_rejects.source_line` is documented as "1-based line number in the source
file, 0 for generated rows" — the API writes the request-relative index, with
`source` = `api` making the interpretation unambiguous.

---

## 6. Endpoints

| | |
|---|---|
| `POST /v1/events` | ingest. Bearer auth. |
| `GET /healthz` | liveness. **No ClickHouse call** — a CH blip must not make systemd restart a healthy process. |
| `GET /readyz` | readiness. Pings CH. This is what a load balancer polls. |
| `GET /v1/stats` | aggregate `Loader.Stats()` + uptime + in-flight count. |

## 7. Auth and limits

Bearer token from `SONYLIV_API_TOKEN`, compared with `subtle.ConstantTimeCompare`.
**The service refuses to start if it is unset** — an unauthenticated endpoint that
writes into the production ClickHouse is not a defensible default, and a
fail-closed startup is better than a flag someone forgets.

A semaphore bounds concurrent in-flight inserts (`--max-inflight`, default 32).
Over the limit returns `503` with `Retry-After` rather than queueing behind the
driver pool (`MaxOpenConns` default 16) and timing out with a worse error.

`SIGTERM` → stop accepting, drain in-flight up to `--drain-timeout` (default 15s),
close the connection. Pairs with `TimeoutStopSec` in the unit file.

---

## 8. Files

```
ingest/cmd/sonyliv-api/main.go      flags, config, wiring, graceful shutdown
ingest/internal/api/server.go       routes, middleware (auth, limits, logging)
ingest/internal/api/ingest.go       decode → validate → chunk → Loader
ingest/internal/api/ingest_test.go  table tests: both formats, every reject
                                    reason, oversized request, idempotent retry
```

`internal/api` rather than putting it in `cmd` so it is testable with
`httptest.NewServer` without a live ClickHouse — the loader is behind a small
interface so tests substitute a fake.

## 9. Deferred, deliberately

- **ClickStack spans** (`api.receive → api.validate → raw.insert`). The service is
  the natural place to emit them and the problem statement wants the integration;
  the hook goes in now, the exporter later.
- **A `/metrics` endpoint.** `Loader.Stats()` already has the numbers.
- **Backfill from the API.** `sonyliv-ingest events --file` stays the path for bulk
  CSV; it is faster and already audited.
