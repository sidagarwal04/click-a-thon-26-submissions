# Langfuse — reading an investigation

Traceability is scored directly: *"a judge should be able to open your traces and follow the
investigation: what was checked, in what order, and why."* And: **no trace, no credit.**

Every investigation opens one Langfuse trace. Inside it, each stage of the algorithm is its own
span, and every ClickHouse query nests under the stage that ran it — so the trace *is* the
investigation, not a log of it.

## Logging in

Open **http://localhost:3000** and **sign in** (do not sign up — registering creates a separate
empty org that has none of the traces):

| | |
|---|---|
| email | `admin@clickathon.local` |
| password | `LANGFUSE_INIT_USER_PASSWORD` in `.env` (default `clickathon123`) |

The project is **RCA Analyst**. Self-hosted Langfuse v3 comes up with the compose stack
(`docker compose up`); see [docker.md](docker.md).

## The trace list

Each row is one investigation. You can read the verdict before opening anything:

- **Name** — `investigation:{metric}`, e.g. `investigation:fill_rate`
- **Tags** — the metric investigated
- **Output** — the conclusion: `detected`, `primary_factor`, `localized_segment`, `score`, `pct_delta`
- **Scores** — `anomaly_score` (how many robust-z units from baseline) and, once narrated,
  `guardrail_passed` (1 = every number in the prose exists in the Evidence Bundle)

Filter by **session** to follow one LibreChat conversation across its investigations.

## Reading a trace

Below is a real captured trace — a `fill_rate` investigation that localized to Android 15. The
`output:` lines are copied verbatim from the spans, not illustrations.

```
investigation:fill_rate                       tags=[fill_rate]  anomaly_score = -128.58
│  output: {detected: true, primary_factor: "fill_rate",
│           localized_segment: {os_version: "Android 15"}, pct_delta: -0.0438}
│
├─ detect                                     ← is this a real move?
│  │  output: {detected: true, observed: 0.7508, expected: 0.7852, score: -128.58,
│  │           direction: "drop", window: ["2026-06-23 00:00", "2026-06-26 00:00"]}
│  ├─ sql:data-range
│  ├─ scan:fill_rate
│  └─ sql:window-metric:fill_rate ×4         ← observed + 3 prior same-shape windows
│
├─ decompose                                  ← WHICH FACTOR moved?
│  │  output: {primary_factor: "fill_rate",
│  │           factors: {requests: 0.4852, fill_rate: -0.5113, ecpm: 0.0035}}
│  └─ sql:factor-sums
│
├─ drilldown                                  ← WHICH SEGMENT?
│  │  output: {localized_segment: {os_version: "Android 15"}, depth: 1,
│  │           culprit_contribution_pct: 0.9767}
│  ├─ sql:population:0
│  ├─ depth-0:os_version
│  │  │  output: {decision: "descend", winner: {os_version: "Android 15"},
│  │  │           contribution_pct: 0.9767, lift: 10.2}
│  │  └─ sql:contribution:{country, region, os_version, app_id, advertiser_id,
│  │        vertical, category, device_model, ad_format, campaign_type,
│  │        publisher_tier}                  ← all 11 dimensions tested in SQL
│  ├─ sql:population:1
│  └─ depth-1:stop
│     │  output: {decision: "stop",
│     │           reason: "no segment clears contribution>=0.5 and lift>=1.5"}
│     └─ sql:contribution:{10 dims}          ← searched again inside Android 15, found nothing
│
├─ ruled-out                                  ← what was checked and cleared
│     output: {cleared: {ecpm_price: "ecpm moved +0.0% (2.475 -> 2.476) — within noise"}}
│
└─ narrate:fill_rate                          ← the LLM's only job: prose (added by /narrate)
      metadata: {guardrail_passed, unverified_numbers}
```

Read that top to bottom and you have the whole argument: fill rate really moved (−128 robust z),
the fill-rate factor carried it (−51% of the delta, while requests and eCPM did not), Android 15
explained 97.7% of the gap at 10.2× its volume share, a further split found nothing better, and
eCPM was explicitly cleared.

**How to read it as a judge would:**

1. **Top-down is chronological.** The order of spans is the order the system reasoned.
2. **Every phase span's `output` is the decision plus the numbers behind it.** `depth-0` doesn't
   just say "Android 15" — it says it explained enough of the gap (`contribution_pct`) and was
   disproportionate enough (`lift`) to descend into.
3. **`depth-N:stop` is where the search ended, and why.** The drill-down stops honestly rather
   than inventing a deeper culprit.
4. **`sql:*` spans carry the exact SQL** as span input, with row counts and timing as output.
   Click any one to see the query that produced a number.
5. **The LLM appears once, at the end.** Everything above `narrate` is deterministic
   ClickHouse work — which is the architecture the rubric asks for.

## The chat path

A LibreChat conversation opens the same kind of trace (`investigation:{metric}`, grouped by
`session_id` so one thread = one Langfuse session), but its shape is shallower:

```
investigation:revenue
└─ detect                    output: detected, observed, expected, score, direction, segment
   └─ sql:observed:{metric}, sql:baseline:{metric},
      sql:observed-by:{dim}, sql:baseline-by:{dim}    ← segment-aware hourly scan
```

That is honest, not a bug: the chat path (`pipeline.run_detection`) runs **detection only** — it
does not yet run decomposition or the recursive drill-down, so there are no `decompose`,
`drilldown` or `ruled-out` phases to show. The dashboard's `/investigate` path is the full
engine. Unifying the two is tracked as follow-up work.

## Live demo behavior

Spans are flushed **as each phase completes**, so a judge watching Langfuse during a demo sees
the investigation build up: detect, then decompose, then each drill level. Toggle with
`tracing.live_flush` in [backend/config.json](../backend/config.json) (`false` = one flush at
the end, slightly faster).

Trace links on a bundle (the dashboard's **Open trace** button) point at `localhost:3000`. In
Docker the backend *sends* traces to the internal `langfuse-web:3000`, so the link is rewritten
to the browser-facing host — that's `LANGFUSE_PUBLIC_HOST`.

## Why the trace list is clean

`run_query` emits a span **only inside an active trace**. Dev-console queries, the benchmarker,
and ad-hoc scripts therefore create no spans at all, instead of each minting a one-span orphan
trace. Every trace in the list is a real investigation.

## For developers

**Add a phase** to new pipeline code:

```python
from narrator.tracing import phase

with phase("my-stage", input={"metric": metric}) as p:
    result = do_work()
    p.verdict(decision="descend", winner=..., contribution_pct=...)   # the WHY
```

`p.rename("my-stage:winner")` renames the span when the outcome is only known at the end
(that's how `depth-0` becomes `depth-0:os_version`).

**Name a query** so it reads in the trace:

```python
run_query(sql, params, name=f"sql:contribution:{dim}")
```

**Degradation rules** — tracing never breaks the pipeline:

| Condition | Behavior |
|---|---|
| `LANGFUSE_PUBLIC_KEY` unset | All tracing no-ops; investigations run normally |
| No active trace (dev console, tests) | No span created — this is the orphan guard |
| Langfuse container down | Investigation still completes; trace links are absent |

**Trace-level helpers:** `stamp_trace_verdict(bundle)` writes the conclusion onto the root trace;
`score_trace(name, value, data_type)` attaches a score. Both no-op outside a trace.

Design rationale: [superpowers/specs/2026-08-02-judge-facing-tracing-design.md](superpowers/specs/2026-08-02-judge-facing-tracing-design.md).
