# Plan — ClickStack integration (the 4th leg)

**Status:** ✅ SHIPPED & VERIFIED — T1–T10 all landed · 2026-08-02 · **code freeze 12:00 IST today**
Every claim below the line marked *measured* was measured on this machine. Two facts in the
original draft were wrong and are corrected in place: the HyperDX **host** port is **8081**, not
8080, and a private `TracerProvider` is required (see Failure modes).
**Owner:** C (per `CLAUDE.md:92`, `CONTRACTS.md:13`)
**Budget:** 90 min build + 30 min demo wiring. Additive only. Drop it if P0 work appears.
**Scope:** ClickStack only. ClickHouse itself is already integrated (cube, engine SQL, live
API at `23.101.175.68:8077`) and is **not** touched by this plan.

---

## Why this exists

`teamkit/GAPS.md:16` — *"ClickStack not wired | The 4th 'ClickHouse three ways' leg — latency
telemetry to prove 'seconds'. | MED"*. It is the only one of our four planned integrations with
zero code. `rg CLICKSTACK_ENABLED` matches **three docs and no source file**.

Rubric hook: *Use of ClickHouse & OSS Stack* = **25%**, our largest single weight.
`CLAUDE.md:58` sets the bar: *"Integrate all four — each meaningfully, none as a replacement.
Superficial inclusion scores nothing."*

The claim it makes true — and this is verified, not aspirational — is that **ClickStack stores
its telemetry in ClickHouse tables** (`otel_traces`, `otel_logs`, `otel_metrics_*`). We can JOIN
our own observability data against our own business tables in one SQL statement. That turns
`STACK_INTEGRATION.md:13`'s pitch line from a slogan into something a judge can run:

> *"ClickHouse is the reasoning engine, the trace store, and the observability store."*

Secondary win, free: `ui/diagnosis.py:378-384` **already renders** `query id · rows read · took`
in the Evidence ledger. It shows `0 rows · 0 ms` today because the engine never captures them.
The same wrapper this plan adds fills those columns. **Zero UI code changes.**

---

## What already exists (do not rebuild)

| Thing | Where | Reuse how |
|---|---|---|
| Single ClickHouse client factory | `run_incident.py:52 def connect(cfg)` | **The whole ballgame.** Both engines and the API receive `cx` as a parameter from here. |
| UI query chokepoint w/ rows/bytes/elapsed already parsed | `ui/data.py:78 def query()`, summary parsed at `:133-146` | Wrap once; values already in scope. |
| Evidence ledger UI columns | `ui/diagnosis.py:378-384` | Already renders `duration_ms`/`rows_read`. Just populate them. |
| Sidebar external-link pattern + CSS | `ui/app.py:347-350`, classes at `:191-200` | Copy one `<a class="sb-item">`. No new CSS. |
| Env config reader | `ui/data.py:_cfg()`, used at `ui/app.py:159-160` | `D._cfg("CLICKSTACK_URL", ...)` — established idiom. |
| Compose + health-check pattern | `integrations/librechat/docker-compose.yml`, `scripts/demo_up.sh:41` | Sibling dir + one more port in the check list. |
| Langfuse span structure | `run_incident.py:573-593` | Do **not** duplicate. ClickStack covers latency; Langfuse covers reasoning. |

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │  run_incident.py:52  connect(cfg)       │
                    │    returns TracedClient(raw_client) ────┼──┐
                    └─────────────────────────────────────────┘  │  ONE wrapper,
                              │ cx passed as a parameter          │  11 query sites,
          ┌───────────────────┼───────────────────┐               │  ZERO call-site edits
          ▼                   ▼                   ▼               │
   run_incident.py     run_incident_v2.py    api/server.py:25     │
   (9 cx.query sites)  (3 cx.query sites)    (compute())          │
          └───────────────────┴───────────────────┘               │
                              │                                   │
                    per query: query_id, rows_read,               │
                    bytes_read, elapsed_ns  ────────────┬─────────┘
                                                        │
                          ┌─────────────────────────────┴──────────────┐
                          ▼                                            ▼
              evidence[].duration_ms/rows_read            integrations/otel.py
              (UI already renders these)                  tracer "rca.clickhouse"
                          │                                            │ OTLP :4318
                          ▼                                            ▼
                  ui/diagnosis.py:378                     ┌────────────────────────┐
                  Evidence ledger lights up               │ ClickStack (local mode)│
                                                          │ HyperDX UI host :8081  │
                                                          │ bundled ClickHouse     │
                                                          │  otel_traces           │
                                                          │  otel_logs             │
                                                          │  otel_metrics_*        │
                                                          └────────────────────────┘
                                                             ▲ NEVER the graded DB
```

**Hard guardrail (stated 3× — `CLAUDE.md:75-76`, `STACK_INTEGRATION.md:48`, `PRD-C:34`):**
ClickStack writes to its **own bundled ClickHouse**. Never `CLICKHOUSE_HOST` from `.env`, or it
creates `otel_*` tables inside the graded competition database.

---

## Bring-up (verified on this machine, not copied from docs)

```bash
docker run -d --name clickstack \
  -p 8081:8080 -p 4317:4317 -p 4318:4318 \
  clickhouse/clickstack-local:latest
```

- **Local mode, not all-in-one.** The auth image does **not open 4317/4318 until the first user
  is created** — it looks like a broken image and costs ~30 min. Local mode needs no signup and
  no API key. Measured: UI + OTLP answering **10 s** after `docker run`. ~660 MB RAM. Native arm64.
- **Host 8080 is NOT free — corrected.** The draft claimed it was. Tailscale holds 8080 on this
  machine (a Funnel listener), and the failure is silent: docker reports the port published, lima
  logs `failed to set up forwarding tcp port 8080 (negligible if already forwarded)`, and the UI
  is simply unreachable. **Publish the HyperDX UI on host 8081** — the container side stays 8080,
  so the compose file maps `8081:8080` and `CLICKSTACK_URL` defaults to `http://localhost:8081`.
  OTLP 4317/4318 are unaffected and collide with nothing we run (3080 LibreChat · 8077 API ·
  8533 UI · 8601 shim · 11434 Ollama). Run `lsof -nP -i:8081` before you start.
- Default OTel retention is **3 days** — fine for a demo, irrelevant after freeze.

---

## Tasks

| # | Task | File | Est. |
|---|---|---|---|
| T1 | `integrations/otel.py` — contractually-named module. Tracer name **literally `"rca.clickhouse"`**. No-op when `CLICKSTACK_ENABLED != 1`. | new, ~60 lines | 25 min |
| T2 | `TracedClient` proxy returned by `connect()` — records `query_id` + `summary` per query, opens a span. | `run_incident.py:52-54` | 20 min |
| T3 | Populate `duration_ms`/`rows_read`/`bytes_read` on evidence objects. One `query_id` per number (today `:512-525` stamps one id onto 5 numbers). | `run_incident.py:483,525` | 10 min |
| T4 | Stage spans around the 5 sequential blocks in `compute()`. | `api/server.py:25,28,42,48,54` | 10 min |
| T5 | `Langfuse(blocked_instrumentation_scopes=["rca.clickhouse"])` so query spans don't flood Langfuse. | `run_incident.py:580` | 1 line |
| T6 | Sidebar shortcut + `_CLICKSTACK` config. | `ui/app.py:161`, `:351` | 5 min |
| T7 | `integrations/clickstack/docker-compose.yml` + `.env.example` key. | new | 10 min |
| T8 | Deps: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`. **Both** in `requirements.txt` **and** `scripts/deploy_mercury.sh:31` — that line pip-installs a hardcoded list, not the requirements file. | 2 files | 5 min |
| T9 | Health check + startup in the demo bring-up. | `scripts/demo_up.sh:20-25,41` | 5 min |
| T10 | `DECISIONS.md` entry (required by `CLAUDE.md:105-109`); flip `GAPS.md:16`, `PROGRESS.md:44`, `TASKS.md:47`. | docs | 5 min |

**T2 is the whole plan.** Because both engine variants and the API receive `cx` as a parameter
from one `connect()`, a single proxy instruments ~11 query sites across 3 files with no call-site
edits. If T2 is done right, T3/T4 are trivial and T1 is the only real new code.

---

## Test plan

The engine has no test for query instrumentation because there is no instrumentation. Every task
below gets a check; none needs a framework.

| Path | Test | Type |
|---|---|---|
| `otel.py` disabled (`CLICKSTACK_ENABLED` unset) | returns a no-op tracer; `connect()` returns a working client; a full `/scan` succeeds with **no** OTel deps importable | unit + smoke |
| `otel.py` enabled, collector **down** | scan still completes; export failure is swallowed, never raised | **critical** — see failure modes |
| `TracedClient` passthrough | `cx.query()` / `cx.command()` return the same objects as the raw client; `.query_id` and `.result_rows` still readable by existing call sites | unit |
| Detector output equality | run `/scan` on `rca_e2e` with instrumentation ON and OFF; assert the bundles are **identical** except timing fields | **gate** |
| Evidence population | every evidence object has non-zero `rows_read` and `duration_ms`; Evidence ledger renders non-zero | integration |
| Span export | after a scan, `docker exec clickstack clickhouse-client --query "SELECT count() FROM default.otel_traces WHERE ServiceName='rca-engine'"` > 0 | e2e |
| The demo claim | the SQL JOIN of `otel_traces` × `otel_logs` returns rows | e2e |
| Guardrail | assert the OTLP endpoint is never derived from `CLICKHOUSE_HOST`; assert no `otel_*` table exists in the graded DB after a run | **security/gate** |

Add `tests/test_otel.py` with the disabled-path, collector-down, and passthrough cases.
The equality gate goes in the run log, not a test file — it is a one-shot before/after diff.

---

## Failure modes

| Failure | Covered? | User sees |
|---|---|---|
| **Collector down / container not started** | Must be. `BatchSpanProcessor` retries then drops; the export thread must never propagate. Wrap `otel.py` init in try/except and return a no-op on any exception. | Nothing. Scan completes normally. |
| **`tp.shutdown()` never called** → spans lost on a short-lived CLI run | `run_incident.py` `__main__` must call shutdown in a `finally`, same as the existing Langfuse `shutdown()` pattern. | Empty HyperDX. Silent. **Flag: this is the classic OTel footgun.** |
| **Span overhead slows the scan** | The scan already makes 56 round-trips; one span each is ~µs, but measure it. If the ON/OFF wall-clock differs by >5%, gate harder. | Slower demo. |
| **Port 8080 taken** | **HAPPENED.** Tailscale holds host 8080 here. Compose now maps `8081:8080`; `demo_up.sh` health-checks 8081. | UI unreachable, container looks healthy. Silent: docker reports the port published and lima logs `failed to set up forwarding tcp port 8080`. |
| **Langfuse spans leak into ClickStack** | **HAPPENED — not predicted by this plan.** `trace.set_tracer_provider()` sets the *global* provider, and Langfuse v4 is OTel-based too, so it exported ITS reasoning spans through our collector — observed in `otel_traces`. Fix: keep a **private** provider (`provider.get_tracer(...)`, never the global setter). That isolates both directions. `blocked_instrumentation_scopes=["rca.clickhouse"]` alone was **not** sufficient. | Two observability systems silently cross-contaminate; the Langfuse trace a judge reads stops being the clean reasoning transcript. |
| **ClickStack writes into the graded DB** | Guardrail test above. | Catastrophic — pollutes the judged database. **Critical gap if untested.** |
| **`deploy_mercury.sh:31` misses the new deps** | Deps listed in both places (T8). | API 500s on import after redeploy. |

**Critical gap flagged:** the graded-DB pollution path has no test today and would be silent.
T7's compose file must hardcode ClickStack's own storage and never read `CLICKHOUSE_HOST`.

---

## NOT in scope (considered, deferred)

| Item | Why deferred |
|---|---|
| Auto-instrumentation (`opentelemetry-instrument`, FastAPI instrumentor) | Adds a wrapper process and breaks with `uvicorn --reload`/`--workers`. Manual spans are ~20 lines and we control them. |
| Metrics + logs pipelines | Traces alone carry the latency story. Logs/metrics are additive polish with no rubric delta. |
| "RCA on ClickStack's own telemetry" (the self-diagnosing stretch in `STACK_INTEGRATION.md:46`) | Genuinely cool, genuinely a rabbit hole at 02:30 with a 12:00 freeze. |
| Replacing Langfuse spans with OTel | Langfuse is the P0 reasoning spine. Two systems, two jobs. Explicitly separated by `blocked_instrumentation_scopes`. |
| Session replay / RUM | No browser telemetry story here. |
| Persisting ClickStack volumes | Demo-scoped. Data survives the session; that is enough. |

---

## Sequencing

```
02:30 ─ T1 otel.py ──┐
02:55 ─ T2 TracedClient (the load-bearing one)
03:15 ─ T3 evidence fields ── T4 stage spans
03:35 ─ equality gate: bundle ON == bundle OFF   ◄── STOP here if it fails
03:50 ─ T5 T6 T7 T8 T9 (parallel-safe, different files)
04:15 ─ e2e: spans land + SQL join demo runs
04:30 ─ T10 docs + DECISIONS entry + PR
```

**Parallelization:** T1+T2+T3+T4 are one lane (all engine/`integrations/`, sequential).
T6 (`ui/`), T7 (`integrations/clickstack/`), T8+T9 (`scripts/`) are three independent lanes that
can run in parallel worktrees after T1 lands. T10 waits on everything.

## Definition of done

1. `CLICKSTACK_ENABLED=1` → spans visible in HyperDX at :8081, with SQL and `query_id` attributes.
2. `CLICKSTACK_ENABLED` unset → byte-identical behaviour to today, no OTel import required.
3. Detector output identical ON vs OFF (33/33 preserved) — verified by diff, not assumed.
4. Evidence ledger shows real non-zero rows/ms.
5. A judge can run one SQL statement joining `otel_traces` against our data. Rehearsed.
6. Nothing written to the graded ClickHouse service.
