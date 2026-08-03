# RCA API Design — scan, investigate, converse

**Date:** 2026-08-01 · **Status:** approved · **Supersedes:** the `/investigate`-only surface in `backend/api/main.py`

## Purpose

Expose the automated root-cause analyst over HTTP so that:

1. The system **finds incidents itself** — no human picks the window. This is what the unseen-incident deliverable requires.
2. Judges can call a **deterministic endpoint** twice and diff the result to verify reproducibility.
3. A **conversational layer** sits on top for follow-ups, modelled on the proven slot-filling pattern in `kangavault.haystack`.

## Constraints

- ClickHouse is the primary datastore. All analysis is SQL; the LLM narrates.
- Every number in any answer must trace to an entry in `EvidenceBundle.queries[]`.
- The Evidence Bundle contract (`contracts/evidence_bundle.schema.json`) is frozen. This design adds transport and storage around it, not new analytics.
- 24-hour build window. Endpoints are ordered so the last one can be cut without losing a scoring criterion.

## Endpoint surface

```
GET    /health                                 liveness
GET    /incidents?date=&metric=                scan -> ranked detected incidents
POST   /investigate {incident_id|metric,window}  -> bundle in ~2s, no narrative
POST   /narrate/{id}                           -> adds narrative + verification
GET    /bundle/{id}                            -> retrieve stored bundle
GET    /bundles?limit=                         -> investigation history
POST   /v1/chat/completions                    conversational entry + follow-up
                                               (OpenAI-shaped; LibreChat points here)
GET    /chat/sessions                          list past sessions with history
DELETE /chat/sessions/{contextId}              reset before a demo run
```

### Why investigate and narrate are split

An investigation is ~20–60 ClickHouse queries (~2s) plus LLM narration (~3–5s). Splitting them means:

- The UI shows real numbers immediately, then the prose arrives.
- If the LLM fails or times out, a complete and fully scoreable bundle still exists.
- It mirrors the architecture: ClickHouse computes, LLM narrates.

### Why the deterministic endpoints stay exposed

`/chat` is the demo surface, but a judge verifying "same input produces the same bundle" needs an endpoint with no LLM in the path. `POST /investigate` is that endpoint.

## Data flow

```
GET /incidents
   -> baseline.scan() per factor per hour
   -> merge contiguous anomalous hours into incidents
   -> rank by robust_z x affected volume

POST /investigate
   -> detect -> decompose (which factor moved)
   -> drill down (which segment) -> assemble EvidenceBundle
   -> persist to ClickHouse `investigations`
   -> return bundle (narrative = null)

POST /narrate/{id}
   -> load bundle -> LLM writes 3-5 sentences
   -> guardrail verifies every number exists in the bundle
   -> persist + return

POST /chat
   -> resolve session -> fill slots -> route intent
   -> scan | investigate | followup
   -> return prose + structured bundle together
```

## Chat: slot filling

Adopted from `HaystackChatService`. The chat collects required parameters across turns and only then acts. This removes the need for the LLM to parse a complete request in one shot.

**Slots:** `metric`, `window`, `segment` (optional).

```
User: "why did revenue drop?"
  template = {metric: "revenue", window: null}
  isReadyForInvestigation = false, missingFields = ["window"]
  -> "Which period? I see incidents on Jun 21, Jun 23-25, Jun 28-30."

User: "the 23rd"
  template = {metric: "revenue", window: "2026-06-23/2026-06-25"}
  isReadyForInvestigation = true
  -> runs the pipeline, returns bundle + prose
```

### Intents

| Intent | Trigger | Action |
|---|---|---|
| `scan` | "what's wrong today?" | `GET /incidents`, summarise |
| `investigate` | slots complete | run pipeline, return bundle + prose |
| `followup` | session has an `investigation_id` | answer from bundle, else scoped query |

Intent classification is one cheap LLM call returning a label plus extracted slots. Classification is narration-adjacent, never computation.

### Response contract — OpenAI-shaped

LibreChat is one of the three blessed integrations, and it talks to *model providers*, not custom
APIs: a custom endpoint calls `{baseURL}/chat/completions` with `{model, messages[], stream}` and
reads `choices[0].message.content`.

Rather than build a translation layer, `/chat` returns an OpenAI-shaped response with our fields
alongside. OpenAI clients ignore unknown keys, so **one endpoint serves both LibreChat and the
dashboard**, and neither needs to know about the other.

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1785200000,
  "model": "rca-analyst",
  "choices": [{
    "index": 0,
    "message": { "role": "assistant",
                 "content": "Revenue fell 4.4% on Jun 23. Fill rate collapsed on Android 15 devices — 78.5% to 43.3%. Region, app category and ad format were checked and ruled out." },
    "finish_reason": "stop"
  }],

  "investigation": { "...EvidenceBundle..." },
  "template": { "metric": "fill_rate", "window": "2026-06-23/2026-06-25",
                "segment": null, "contextId": "abc123" },
  "isReadyForInvestigation": true,
  "missingFields": [],
  "isPlottable": true,
  "plotKind": "metric_tree",
  "plotData": [],
  "verification": { "passed": true, "unverifiedNumbers": [] }
}
```

LibreChat reads `choices[0].message.content`. The dashboard reads `investigation` and `template`.

The request accepts the OpenAI shape too — the last user message becomes the query, and the
conversation id becomes our `contextId` so a LibreChat thread maps to one chat session and one
Langfuse session. `model` is accepted and ignored; the narrator model is chosen server-side.

Slot filling still works, and gets simpler: LibreChat resends the full message history every turn,
so a `missingFields` prompt is just an assistant turn and the reply arrives as the next user
message. No state machine is needed on the client side.

Field mapping from kangavault: `IsReadyForRetrieval` → `isReadyForInvestigation`, `Retrieval` →
`investigation`, `Template` → slots. Session continuity via an `X-Session-Id` header or the
conversation id, exactly as `Kv-Chat-Session-Id` works today.

Streaming (`stream: true`) uses SSE: run the pipeline first, then stream the finished narrative.
The deterministic analysis is never streamed.

**Deliberately dropped:** multi-tenancy, context-file upload, vector search, graph/Cypher. Single tenant, no documents.

## LLM-generated SQL

Allowed in `/chat` only. Never in `/investigate`, which produces the scored artifact.

The rationale is specific to this dataset. Two traps would silently return wrong numbers:

1. `advertiser_id` is empty on 1,972,090 unfilled requests. An inner `JOIN advertisers` returns `fill_rate = 1.0` with no error.
2. Precomputed ratio columns invite `avg(fill_rate)`, which is wrong by up to +2.8% and skewed differently per region.

Both become unreachable under these guardrails:

1. Dedicated read-only ClickHouse user; session `readonly=1`, `max_execution_time=10`, bounded `max_result_rows`.
2. **Only `events_enriched` is queryable** — pre-joined and flat, so trap 1 cannot occur.
3. Ratio columns removed from the Gold layer, so trap 2 cannot occur.
4. Single `SELECT` only. Reject semicolons, DDL and DML by parse before execution.
5. Forced `LIMIT` injection.
6. Metric formulas from `metrics.py` injected into the system prompt so ratios are computed sum/sum.
7. Every generated query appended to `queries[]` with `source: "llm_generated"`.
8. The existing guardrail verifies every number in the final answer.

Tagging generated queries makes the split visible to judges: they can see exactly which numbers came from deterministic SQL and which from LLM-authored SQL.

## Storage

```sql
CREATE TABLE investigations (
    investigation_id  String,
    trace_id          String,      -- Langfuse trace, survives across HTTP calls
    session_id        String,      -- chat session (contextId), empty for direct calls
    created_at        DateTime,
    metric            LowCardinality(String),
    window_start      DateTime,
    window_end        DateTime,
    primary_factor    LowCardinality(String),
    localized_segment String,      -- JSON
    detected          UInt8,
    bundle            String       -- full EvidenceBundle JSON
) ENGINE = MergeTree ORDER BY (created_at, investigation_id);
```

Single datastore, survives restarts, and investigation history is queryable in SQL — which reinforces the "ClickHouse is the primary datastore" requirement.

Chat sessions and turns use two small companion tables keyed by `context_id`.

## Prerequisite fixes

These block clean work and land first.

1. **Merge the lane branches into `main`.** Work is currently split across `lane-a-data` (loader), `JAL-26-robust-...` (baseline) and `main` (AWS setup). Nothing has all three. Lanes B/C/D would build on divergent copies of `config.json`.
2. **Detection false-positive gate.** `_detected` currently uses `min_pct_delta` only as a fallback when MAD is zero. Measured across 9 normal hours (72 checks): **18 false positives**. With the two conditions ANDed and `min_pct_delta = 0.05`: **0 false positives**, both known anomalies still detected. At `0.10` anomaly D is missed.
3. **Slim the Gold layer.** `metrics_hourly_advanced` is 178 MiB against a 91 MiB source with 1.03× compression. Drop the precomputed ratio columns and reduce grain.
4. **Drop duplicate tables.** `events_enriched` and `events_full` hold the same 9M rows at 118 MiB each; `apps`/`apps_dim`, `advertisers`/`advertisers_dim`, `geo_device`/`geo_device_dim` are likewise duplicated.
5. **Per-factor dimension allowlist and drill-down spec.** `drilldown_dimensions` is one flat list; `vertical` and `campaign_type` are structurally invalid for `fill_rate` and `requests`. `stop_contribution_threshold: 0.15` still encodes the ranking rule that mislocalises.

## Tracing contract

Tracing is designed in from the start rather than bolted on, because the trace is a scored
deliverable and because the investigate/narrate split spans two HTTP calls.

**One trace per investigation, anchored on `investigation_id`.** `POST /investigate` opens the
trace and persists `trace_id` alongside the bundle. `POST /narrate/{id}` loads that `trace_id`
and attaches its generation span to the *existing* trace. Without persistence, narration would
open an orphaned second trace and the SQL steps would appear unrelated to the LLM call.

**Chat turns group into a Langfuse session** via `contextId`, so a multi-turn conversation reads
as one session containing several investigation traces.

**Every endpoint is traceable.** `GET /incidents` emits its own scan trace; `POST /chat` emits a
routing span then nests the investigation trace beneath the session.

**Span naming carries the verdict, not just the query id.** `reject publisher_tier=tier_2
(uniform, lift 0.99x)` is legible from the tree view; `q_14` is not. Rejected drill-down
candidates are emitted as spans — that is where the "what did you rule out" evidence lives.
Emit one span per dimension scan carrying the ranked table as output, plus individual spans for
the accepted node and the top few rejects. Legibility beats completeness.

**Bundle and trace cross-reference both ways.** `Query.langfuse_span_id` already exists in
`models.py` and must be populated, with span names reusing the `q_NN` ids from `queries[]`. A
judge can then pick any number in the diagnosis, jump to the span that produced it, and back.

**Failure is loud, not silent.** `tracing._client()` currently returns `None` when keys are
absent and the pipeline continues with no traces and no warning — a judge would score
traceability as unimplemented. Log loudly at startup and surface component status in
`GET /health` (ClickHouse, Langfuse, LLM each reporting ok/error).

## Local reproducibility

Judges run the whole stack locally, so bring-up is part of the deliverable.

- `docker-compose up` starts ClickHouse, Langfuse, backend and frontend.
- Langfuse is **seeded headlessly** (`LANGFUSE_INIT_*` environment variables) so a fresh instance
  already has an org, project and the API keys the backend expects. Without this, a fresh Langfuse
  has no keys and tracing silently no-ops.
- `load.py` must work against a local ClickHouse container: host, port and `secure` fully
  config-driven, no assumption of a Cloud TLS endpoint.
- Narration must degrade gracefully. Bedrock needs AWS credentials a judge will not have, so
  provide a local LLM fallback and ship the four regression bundles with narratives
  pre-generated. The investigate/narrate split already guarantees the bundle stays valid.

## Error handling

- Missing session header → 400 with a clear message.
- Unknown `investigation_id` → 404.
- Detection finds nothing → 200 with `detected: false` and a plain-language "no anomaly" response. Not an error.
- LLM failure during narration → 200 with the bundle and `narrative: null`; the bundle stays valid and scoreable.
- Guardrail failure → return the answer with `verification.passed: false` and the offending numbers listed. Never silently drop it.
- Rejected LLM SQL → answer from the bundle instead and say the query was refused.

## Testing

- **Unit:** slot extraction, intent routing, SQL validator (accepts a SELECT, rejects DDL/DML/multi-statement), window merging.
- **Integration:** each endpoint against live ClickHouse; `/investigate` called twice must produce identical `localized_segment` and `queries[]`.
- **Regression:** the four known anomalies, asserting the exact localized segment:

| Window | Metric | Expected segment |
|---|---|---|
| Jun 23–25 | fill_rate | `os_version=Android 15` |
| Jun 19–22 | ecpm | `category=finance` |
| Jun 21 | requests | *no segment — global/uniform* |
| Jun 28–30 | fill_rate | `region=APAC AND os_version=iOS 18.1` |

The Jun 21 case is the false-positive guard: the correct output names no segment.

Note that Jun 21 sits inside anomaly B's window and carries its own request collapse. The two are independent — finance eCPM is depressed on all four of Jun 19–22 — but the test for B should use Jun 19, 20 and 22 as the target window so the traffic anomaly does not confound the eCPM measurement. Baselines are the matching weekdays from the prior week.

## Build order

1. Prerequisite fixes 1–5.
2. `investigations` table → `GET /bundle/{id}`.
3. `GET /incidents` (wraps `baseline.scan`, merges contiguous hours).
4. `POST /investigate` on the real pipeline.
5. `POST /narrate/{id}`.
6. `POST /chat` — slots, sessions, intent routing.
7. `/chat` guarded SQL path.

Steps 6 and 7 are last deliberately: they depend on everything above, and cutting them loses no scoring criterion.
