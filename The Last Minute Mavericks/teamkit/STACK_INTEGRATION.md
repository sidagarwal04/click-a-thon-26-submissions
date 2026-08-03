# Stack Integration — ClickHouse three ways, + deep OSS

The problem statement requires ClickHouse as primary **and** ≥1 of ClickStack / Langfuse /
LibreChat, warning that **superficial inclusion won't count**. We go for **all four** (Spot Award).
This doc is the bar for what "deep" means per stack, so no integration reads as bolted-on.

## The unifying idea: it's ClickHouse all the way down
Both Langfuse (v3+) and ClickStack/HyperDX store their data **in ClickHouse under the hood**. So:
```
   the LLM only        ┌──────────────  C L I C K H O U S E  ──────────────┐
   narrates      ───▶  │ 1. RCA reasoning engine     rca.*                 │
                       │ 2. Langfuse trace store     traces/observations   │
                       │ 3. ClickStack telemetry     HyperDX otel_*         │
                       └───────────────────────────────────────────────────┘
```
**Pitch line:** *"ClickHouse is the reasoning engine, the trace store, and the observability store.
The only thing outside it is the LLM reading the answer out loud."*

## Per-stack: superficial ✗ vs deep ✓ (what we build)

### ClickHouse — the engine (owner A)
- ✗ dump data, run a few SELECTs.
- ✓ the entire RCA algorithm as SQL over an `AggregatingMergeTree` cube — baseline/MAD → LMDI →
  Adtributor → rate/mix → purity → verdict — with results persisted as queryable tables
  (`incidents`, `attribution`, `evidence`; see the data-model doc). ClickHouse *reasons*; the LLM
  never does arithmetic. → scored under *analytical depth in ClickHouse* (25%).

### Langfuse — LLM observability & analytics (owner B; inseparable from the graph)
- ✗ log one trace of the LLM call.
- ✓ four layers:
  1. **Trace = the investigation.** One trace per RCA; a **span per node** (detect→decompose→
     attribute→verify→rule_out→narrate), each carrying its **SQL, ClickHouse `query_id`, rows
     scanned, and prune/pursue reason.** A judge reads it like a transcript.
  2. **Datasets + Scores + Experiments.** The **battle-test synthetic incidents become a Langfuse
     Dataset**; each pipeline run is a Langfuse run, scored with **precision/recall/confidence
     Scores** → Langfuse analytics track the detector improving. (Ties to `tests/battletest.py`.)
  3. **Prompt management** — the narration prompt is versioned in Langfuse.
  4. **Closed loop with ClickHouse** — because Langfuse stores traces/scores *in ClickHouse*, we
     query them with our own ClickHouse SQL: analyzing our investigations with the same engine.
- Pin `langfuse==4.14.2` (v4 SDK); `shutdown()` in `finally`; `set_trace_as_public()`.

### ClickStack / HyperDX — observability of our own service (owner C) — SHIPPED & VERIFIED
- ✗ send one latency number.
- ✓ **Done.** `integrations/otel.py` (tracer `rca.clickhouse`, service `rca-engine`) plus a
  `TracedClient` proxy returned by `run_incident.py connect()` open **one span per ClickHouse
  query** across `run_incident.py`, `tests/e2e/run_incident_v2.py` and `api/server.py` — zero
  call-site edits, because all three receive `cx` from the one `connect()`. Stage spans wrap
  `compute()` (`rca.scan`, `rca.connect`, `rca.detect`, `rca.decompose`, `rca.adjudicate`,
  `rca.narrate`, `rca.publish_trace`), and `wall_clock_s` is now measured — it was hardcoded `0.0`.
  Measured, not claimed: **198 spans per scan** (192 query + 6 stage, 7 span names), average query
  ~154 ms, **30/30 evidence objects carry real `rows_read`/`bytes_read`/`duration_ms`** from the
  `X-ClickHouse-Summary` header (e.g. 3,599,416 rows in 102.6 ms). Detector output is **identical
  ON vs OFF**; overhead is not measurable (25.6s OFF / 25.2s ON). HyperDX UI:
  **`http://localhost:8081`** — host 8080 is held by Tailscale, so the compose file maps
  `8081:8080`. Full plan and results: `PLAN_CLICKSTACK.md`.
- **The thing a judge runs — one SQL statement.** Copy any `query_id` out of the Evidence ledger
  and read that number's exact cost back out of ClickStack's own ClickHouse:
  ```sql
  SELECT SpanAttributes['db.query_id']    AS query_id,
         SpanAttributes['db.rows_read']   AS rows_read,
         SpanAttributes['db.duration_ms'] AS server_ms,
         round(Duration / 1e6, 1)         AS round_trip_ms,
         SpanAttributes['db.statement']   AS sql
  FROM default.otel_traces
  WHERE ServiceName = 'rca-engine' AND SpanName = 'clickhouse.query'
    AND query_id = '<paste from the ledger>'
  ```
  A number in the UI → the SQL that produced it → what that SQL cost. That is the pitch line at
  `:16` made runnable. The `otel_traces` × `otel_logs` variant is in
  `integrations/clickstack/README.md`.
- **Guardrail — held, verified.** ClickStack writes to its **own bundled ClickHouse**, never the
  competition service. After a full instrumented run, **no `otel_*` or `hyperdx_*` table exists in
  the graded service.** Gate `CLICKSTACK_ENABLED=1`. Keep the two observability systems apart with
  a **private** `TracerProvider`: the global `trace.set_tracer_provider()` makes Langfuse v4 (also
  OTel-based) export its reasoning spans through our collector.
  `Langfuse(blocked_instrumentation_scopes=["rca.clickhouse"])` is set, but it is not sufficient
  on its own.
- **Scope limits, stated honestly.** The engine query path only. `ui/data.py`,
  `scripts/load_clickhouse.py` and `scripts/gen_e2e_dataset.py` use their own clients and are not
  instrumented. Traces only — no OTel logs or metrics pipeline. The collector reachability check
  runs once at init, so a collector that dies mid-run drops spans safely but does not re-attach
  without a restart.

### LibreChat — conversational front door (owner C) — REINSTATED
- ✗ point LibreChat at OpenAI (a generic chatbot — the trap C originally flagged).
- ✓ expose the **LangGraph RCA agent as an OpenAI-compatible `/v1/chat/completions` endpoint**,
  registered as a custom endpoint. Follow-ups ("was APAC affected too?") run **real ClickHouse
  SQL** and return evidence-chipped, traceable answers — the same guarantees as the dashboard.
  Not a chatbot; a natural-language skin over the CH engine.
- **Tradeoff to manage (C's concern, still valid):** 6–10 containers / 2–4h Docker; it must **not**
  weaken the primary dashboard. Timebox, gate behind `LIBRECHAT_ENABLED`, drop before freeze if shaky.

## Ownership + scoring
| Stack | Owner | Scored under |
|---|---|---|
| ClickHouse (engine + tables) | A | Analytical depth in ClickHouse (25%) |
| Langfuse (trace + datasets/scores) | B | Traceability + trustworthiness |
| ClickStack (HyperDX latency) | C | "Fast" proven + OSS depth |
| LibreChat (deep endpoint) | C | Innovation / Spot Award |

## Build order (lowest-risk first)
1. **Langfuse trace-per-node** (P0 — "no trace, no credit") + battle-test as a Dataset with Scores.
2. **ClickStack** query + stage spans — ✅ shipped and verified (additive, gated).
3. **LibreChat** endpoint last (highest setup cost; drop if the core isn't solid).
