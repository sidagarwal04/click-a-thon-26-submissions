# OBSERVABILITY — ClickStack watching OUR pipeline (H7)

> **Summary:** `sonyliv observe` (`cmd/sonyliv/observe.go`) is the emitter — it queries watermark lag
> (`v_cc_watermark`), build-stage timing (`system.query_log`), and the reconcile gate's last verdict
> (`evidence/reconcile.txt`), then POSTs all three to our own ClickStack collector as OTLP/HTTP JSON:
> metrics (gauges), a correlated log line per signal, and one trace covering the run. It is deliberately
> **NOT** an OTel-SDK integration — `internal/otelemit` is a ~250-line stdlib-only JSON client, because
> the OTLP/HTTP JSON mapping is small and stable and the SDK's log bridge is still experimental. Every
> claim below was executed, not reasoned about — see "Verified end to end".

**The hosted twin.** The ClickHouse Cloud service has **no OTLP path** (no `otel_*` tables), so the
metrics below cannot land there. `tools/clickstack-cloud.sh` therefore builds **"SonyLIV pipeline
health (cloud)"** on the hosted HyperDX from the same three signals cloud-natively: `v_cc_watermark`
directly, build stages from `system.query_log` with the exact filters `internal/pipelinehealth`
uses, and reconcile-gate *runs* by their read set (`ev_raw` AND `cc_minute_delta`). What the hosted
twin cannot show is the gate's PASS/FAIL **verdict** — that lives in `evidence/reconcile.txt` and in
`sonyliv.reconcile.gate_pass` here, which is precisely why this OTLP emitter still earns its keep.

## Why this file exists

The rubric test is: *if I delete ClickStack, does the demo stop doing something a judge saw?* Before
H7, the answer was no — ClickStack only charted our concurrency views (read-only), and nothing of ours
ever spoke OTLP. `sonyliv observe` closes that gap: the demo's freshness indicator (watermark lag) is a
real number read back out of ClickStack's own ClickHouse, not a screenshot of something computed
elsewhere. Delete ClickStack and that indicator has nowhere to come from.

## What is emitted, and why

| Signal | Source | Why this one |
|---|---|---|
| `sonyliv.watermark.sealed_lag_seconds` | `v_cc_watermark.sealed_lag_s` | **The headline.** "`W` is the metric to instrument in ClickStack" — [ARCHITECTURE.md](ARCHITECTURE.md). It is the one number that tells you whether the served answer is trustworthy right now. |
| `sonyliv.watermark.healthy` | derived: `sealed_lag_s <= 0` | A boolean a dashboard threshold can alert on without re-deriving the sign convention (see below) every time. |
| `sonyliv.watermark.hour_tier_complete` | `v_cc_watermark.hour_tier_last_hour_complete` | Whether hour-grain answers are final or still accumulating — the second freshness axis `v_cc_watermark` names. |
| `sonyliv.build.stage_duration_seconds{stage}` | `system.query_log`, most recent `Insert` per stage | How long `tools/build-model.sh`'s real, already-executed stages took — from ClickHouse's own record, not a re-timed re-run. |
| `sonyliv.build.stage_rows_written{stage}` | ″ | Throughput per stage; a stalled/empty build is visible as a rows-written cliff. |
| `sonyliv.build.seconds_since_last_run{stage}` | ″ | **Freshness of the served answer** in the most literal sense: how long ago the model was actually rebuilt. |
| `sonyliv.reconcile.gate_pass` | `evidence/reconcile.txt`, parsed | Whether THE GATE (`sql/90_reconcile.sql`) passed last time it ran. A correctness gate flipping to FAIL belongs in an observability tool and exists nowhere else. |
| `sonyliv.reconcile.max_abs_delta` | ″ | The size of the failure, not just pass/fail — `0` normally, `37` was the real historical incremental-absorption bug (TESTS.md). |
| `sonyliv.reconcile.evidence_age_seconds` | ″ (file mtime) | The gate's own freshness — how stale the "PASS" you're looking at actually is. |

### `hour_tier_complete=false` is the expected reading on this dataset

Do not treat it as a fault. The flag is `raw_wm >= last_hour + 1h` — is the newest *stored* hour
already sealed? On the supplied data the last event is `2026-07-26 11:30:04.847`, and the newest
stored hour is `11:00`, which does not end until `12:00`. The hour is genuinely still partial, so
`false` is the truthful answer and would stay `false` no matter how many times the model is
rebuilt. It flips to `true` only once data arrives past the hour boundary — which on a static
file never happens.

This is the same class as the gate's `TAIL_S` note at `2026-07-26 11:31`: an artifact of a
dataset that stops mid-interval, not a pipeline defect. Verified live 2026-08-01 with
`healthy=true` and `pass=true` alongside it. Anyone demoing `sonyliv observe` should expect to be
asked about this line and should have this answer ready, because "one of your health flags says
false" is the obvious question.

Each metric is also mirrored as a `severityText`-appropriate **log line** (lower-case
`info`/`warn`/`error` — see Gotchas) sharing the run's `trace_id`, and the whole run is one **trace**:
root span `sonyliv.observe.run` with child spans `pipeline.watermark.query`,
`pipeline.build_stages.query`, `pipeline.reconcile_evidence.read`. Logs, metrics and spans correlate by
`trace_id`/`span_id` — click a log line in HyperDX and its span is one click away.

## What is deliberately NOT instrumented, and why

**Benchmark query latency and bytes read are not emitted here**, despite being a natural-sounding
"observability" signal. ClickHouse's own `system.query_log` already has this data, more accurately than
a client span ever could:

- it has `granules_read`/`bytes_read` from server-side `ProfileEvents` a client cannot observe at all;
- a client-measured span additionally bakes in network round-trip time, which is noise on top of a
  number the database already recorded authoritatively.

A second, independent HyperDX source over `system.query_log` (`ClickHouse query_log (our own
queries)`, Cloud source id `6a6dd4ac233f0475ad40cecd`) already exists and charts p95 latency and bytes
read directly from that table — built and owned separately from this emitter. Duplicating it here would
be strictly worse data shipped twice. See `docs/TESTS.md`'s H7 section for the same reasoning applied
to the test suite.

**Also not built:** a Langfuse emitter. One OTel emitter can feed ClickStack and Langfuse
simultaneously by sharing the same `trace_id` — the cheap path to the Spot Award — and
`otelemit.NewTraceID()`'s plain 16-byte-random-hex shape was chosen so a future Langfuse emitter could
reuse it without a format change. It was not built because H7's brief is ClickStack specifically; see
whoever picks up the Langfuse task before duplicating trace-id generation.

## The sign convention (read this before touching `sealed_lag_s`)

`v_cc_watermark` (built by another agent, `sql/85_windows.sql` — never altered here) documents that the
sealed tier legitimately **leads** raw ingestion by up to ~2 minutes, because an interval's close delta
carries `TAIL_S=60s` of grace. So a **negative** `sealed_lag_s` is the healthy steady state, and only a
**positive** value means the finalizer is genuinely behind. `pipelinehealth.Watermark.Healthy()` encodes
exactly this (`sealed_lag_s <= 0`) — an alert built on "any negative number is suspicious" would fire on
the normal case every time, which is the trap this file exists partly to prevent someone from re-adding.

## Running it

```bash
tools/clickstack-bootstrap.sh        # once per stack: registers the team, prints CLICKSTACK_INGESTION_KEY
./bin/sonyliv observe -target cloud            # emit real telemetry
./bin/sonyliv observe -target cloud -dry-run   # compute and print, do not POST — no key required
tools/clickstack-observability.sh    # idempotent: dashboard tiles over the metrics above
```

Env vars (see `.env.example`): `CLICKSTACK_OTLP` (default `http://localhost:4318`),
`CLICKSTACK_INGESTION_KEY` (from bootstrap), `CLICKSTACK_SERVICE_NAME` (default
`sonyliv-pipeline` — every span/log/metric carries this as `service.name`, so a judge filtering by
service in HyperDX sees only our self-observation, never the concurrency data it charts separately).

`observe` also takes `-timeout` (default 30s) and `-evidence <path>` (default
`evidence/reconcile.txt`) for pointing at a different reconcile run.

## Verified end to end

Not "returns 200" — read back out of ClickStack's own bundled ClickHouse after a real run against
Cloud (`./bin/sonyliv observe -target cloud`, trace `1d3a39fd5fd5dea577a3b71275a13f6e`):

**Metrics** (`SELECT MetricName, Value, Attributes FROM otel_metrics_gauge WHERE ServiceName =
'sonyliv-pipeline'`):

```
sonyliv.watermark.sealed_lag_seconds     -116          {}                              <- negative = healthy
sonyliv.watermark.healthy                   1          {}
sonyliv.watermark.hour_tier_complete        0          {}
sonyliv.build.stage_duration_seconds     1.525          {'stage':'session_intervals'}
sonyliv.build.stage_duration_seconds     1.02           {'stage':'cc_minute_delta'}
sonyliv.build.stage_rows_written       121492          {'stage':'session_intervals'}
sonyliv.build.stage_rows_written        28139          {'stage':'cc_minute_delta'}
sonyliv.build.seconds_since_last_run   127.12          {'stage':'session_intervals'}
sonyliv.build.seconds_since_last_run   125.12          {'stage':'cc_minute_delta'}
sonyliv.reconcile.gate_pass                 1          {}
sonyliv.reconcile.max_abs_delta             0          {}
sonyliv.reconcile.evidence_age_seconds  114.2          {}
```

**Logs** (`SELECT SeverityText, Body FROM otel_logs WHERE TraceId = '1d3a39fd...'`):

```
info   watermark: raw=2026-07-26T11:30:04Z sealed=2026-07-26T11:32:00Z sealed_lag_s=-116 healthy=true hour_tier_complete=false
info   build stage session_intervals: 1525ms, 121492 rows written, last ran 2m7s ago
info   build stage cc_minute_delta: 1020ms, 28139 rows written, last ran 2m5s ago
info   reconcile gate: PASS (5/5 minutes agree, evidence commit 3c081ff, 1m54s old)
```

(That log line predates the hardened gate. Since 2026-08-01 the parser reads the gate's SUMMARY row
rather than counting sample rows, and the line reads
`reconcile gate: PASS (17028 minutes compared, 0 mismatched, peak 2887, evidence commit d6c85e2, …)`.
A file with no parseable SUMMARY — empty, malformed, or pre-81c0161 — logs
`FAIL — no SUMMARY row parsed` and `gate_pass=0`: unreadable evidence fails loudly instead of
passing silently.)

`SeverityText` came back **lower-case** exactly as written — confirms VERIFIED.md's `severity:error`
filtering fact against this emitter specifically, not just the general claim.

**Traces** (`SELECT SpanName, ParentSpanId = '' AS is_root, Duration/1e6 AS ms, StatusCode FROM
otel_traces WHERE TraceId = '1d3a39fd...'`):

```
pipeline.watermark.query           child   202.4ms   Ok
sonyliv.observe.run                root    605.3ms   Ok
pipeline.build_stages.query        child   402.7ms   Ok
pipeline.reconcile_evidence.read   child     0.2ms   Ok
```

**The dashboard tile itself**, queried the way HyperDX's own UI would (`POST /clickhouse-proxy` with
the `x-hyperdx-connection-id` header the Metrics source uses):

```
SELECT toStartOfMinute(TimeUnix) AS t, max(Value) AS v
FROM otel_metrics_gauge WHERE MetricName='sonyliv.watermark.sealed_lag_seconds' GROUP BY t ORDER BY t
-> 2026-08-01 11:24:00   -116        (HTTP 200)
```

`tools/clickstack-observability.sh` was run twice to confirm idempotency: first run `created`, second
`updated` (PATCH), dashboard count stayed at **1** with all **8** tiles present both times — no
duplicate.

Local probe rows used to validate the wire shape before any real run (a throwaway gauge/log/span) were
deleted afterward (`ALTER TABLE ... DELETE`); they are not part of the numbers above.

## Gotchas found building this

- **Local self-hosted dashboards use `PATCH /dashboards/:id`, not `PUT`.** The Cloud control-plane API
  (`tools/clickstack-cloud.sh`) uses PUT; the local all-in-one's own router
  (`routers/api/dashboards.js` inside the `cs` container) only registers PATCH. PUT returns 404, which
  reads exactly like "dashboard not found" and sends you debugging the wrong thing.
- **Local tile config uses `source` (bare id), not `sourceId`**, and every tile needs an explicit `id`
  — both differ from the Cloud dashboard schema `tools/clickstack-cloud.sh` targets. There is also no
  `/dashboards/validate` route locally; POST is itself the validation.
- **A fresh ClickStack team already has default `Logs`/`Traces`/`Metrics`/`Sessions` sources** pointed
  at `otel_logs`/`otel_traces`/`otel_metrics_*`/`hyperdx_sessions` the moment the team is created —
  confirmed via `GET /sources` right after `tools/clickstack-bootstrap.sh`. `sonyliv observe`'s traffic
  needs no new source; `tools/clickstack-observability.sh` only adds a dashboard over the existing
  `Metrics` source.
- OTLP/HTTP JSON's `intValue` field is a **decimal string**, not a JSON number — pinned by
  `TestIntAttrEncodesAsJSONString`. A bare `int64` field would silently lose precision above 2^53
  (irrelevant at today's row counts, but the wire format doesn't get to assume that forever).
- The usual ClickStack facts from `docs/VERIFIED.md`/`docs/CLICKSTACK.md` all applied unchanged: the
  `cs` container needs `tty: true` or it exits 129; OTLP does not bind until a team exists and binds
  *late* even after — poll, don't sleep a fixed amount; no `authorization` header is a 401; registration
  is at the root (`/register/password`), not under `/api`.

## Alerting — what we page on, and what we deliberately do not

Everything above observes the *pipeline*. The one thing we alert on is a **business** signal:
concurrency declining. It has its own document, [DECLINE_ALERTING.md](DECLINE_ALERTING.md), because
the hard part is not the detection — it is telling apart the three causes the problem statement names
(the asset ended · a system issue · the content is not engaging), which have completely different
responses. Summary of what is live in hosted HyperDX:

| Alert | Fires when | Response |
|---|---|---|
| **Concurrency decline — SYSTEM ISSUE** | concurrency below 80% of its 15-min trailing median, departures *not* explained by session closes, heartbeat rate below the fully-paused rate. 5 min, 2 consecutive windows | **page** |
| **Concurrency decline — CONTENT NOT ENGAGING** | same decline, viewers still connected and emitting, but pausing/backgrounding above their own recent rate. 15 min | content call, no page |
| **Concurrency decline — UNCLASSIFIED** | a decline that matches none of the three cleanly. 15 min | look at it |

There is **no alert on an asset ending**, which is the entire point: concurrency falls legitimately
all evening, and a detector that fires on that is one people learn to ignore.

Two things from that work belong here rather than only there:

- **Alert windows anchor to `v_cc_watermark.sealed_watermark`, never `now()`.** Same watermark this
  emitter reports as `sonyliv.watermark.sealed_lag_seconds`. It is what makes an alert meaningful on
  a frozen dataset, and it degrades usefully on a live one — if ingestion stalls the window stops
  advancing instead of sliding onto empty minutes and reporting all-clear.
- **A 200 from the alerts API does not mean the alert works.** Two alerts sat in `state=ALERT` while
  their tiles read `0` — either because `above` is inclusive or because the engine fires on a row
  existing; we closed both doors rather than guess. Only reading state back and comparing it against
  the tile's own value caught it, and `tools/clickstack-alerts.sh --verify` exists to make that check
  routine. Same lesson as the OTLP work above: verify by reading the data back out, not by trusting
  the write.

## Files

| File | Role |
|---|---|
| `internal/otelemit/` | the OTLP/HTTP JSON client — types, `Client.Post{Metrics,Logs,Traces}`, `NewTraceID`/`NewSpanID` |
| `internal/pipelinehealth/` | the three queries — `QueryWatermark`, `QueryBuildStages`, `ReadReconcileEvidence` |
| `cmd/sonyliv/observe.go`, `observe_helpers.go` | wiring: gather signals inside a trace, build the OTLP payloads, print a summary, POST |
| `internal/config/clickstack.go` | `CLICKSTACK_OTLP`/`CLICKSTACK_INGESTION_KEY`/`CLICKSTACK_SERVICE_NAME` — additive, does not touch `config.go`'s Cloud/local ClickHouse loading |
| `tools/clickstack-observability.sh` | idempotent dashboard over the emitted metrics, local self-hosted stack |
| `tools/clickstack-alerts.sh` | idempotent decline dashboard + 3 alerts on hosted HyperDX; `--validate` regenerates the thresholds' evidence, `--verify` reads the alerts back signed-in ([DECLINE_ALERTING.md](DECLINE_ALERTING.md)) |
