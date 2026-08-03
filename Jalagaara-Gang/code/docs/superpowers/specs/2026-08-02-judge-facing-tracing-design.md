# Judge-facing investigation tracing — design

**Date:** 2026-08-02 · **Status:** approved · **Owner:** Lane C

## Problem

The rubric scores traceability directly: *"a judge should be able to open your traces and follow
the investigation: what was checked, in what order, and why. No trace, no credit."*

Measured against the live Langfuse DB, today's traces fail that test:

- Investigation traces nest their SQL spans correctly, but **every span is named
  `clickhouse-query`** (102 identical spans in the latest trace). No phases, no decisions.
- **481 orphan single-span traces** (dev-console/benchmark queries with no root trace) bury the
  real investigations in the trace list.
- Span outputs carry row counts, not verdicts — the *why* (descend vs stop, cleared vs culprit)
  is nowhere in the trace.

## Goals

1. A judge opens one trace and reads the investigation as a story: detect → decompose →
   drill (with per-depth decisions) → ruled-out → narrate.
2. Spans appear in the Langfuse UI **while the investigation runs** (live demo) and remain a
   clean narrative afterward.
3. The trace *list* already shows conclusions (tags + scores) before clicking anything.
4. Dev tooling stops generating orphan trace noise — without changing dev code.
5. Chat (`/v1/chat/completions`) inherits the same structure for free.

## Non-goals

- No custom OTEL tracers/processors (Approach C — over-engineering).
- No tracing of dev-console/benchmark runs under their own named traces.
- No frontend changes.

## Design

### 1. `phase()` context manager — narrator/tracing.py

```python
with phase("drilldown", input={"factor": "fill_rate"}) as p:
    ...
    p.verdict(winner="country=IN", contribution_pct=0.87, decision="descend")
```

- Opens a Langfuse span as a child of the current OTEL context (root trace or another phase).
  Existing `run_query` spans nest under the innermost phase automatically — no plumbing.
- `p.verdict(**kw)` sets span output: the decision plus the numbers that drove it.
- On exit: `lf.flush()` if `config.tracing.live_flush` (live visibility, per-phase granularity).
- Degrades to a no-op when Langfuse is off **or no trace is active** — library code never
  crashes or emits orphans when called untraced.
- Phase names live in one constants map in `tracing.py` (no scattered magic strings).

### 2. `run_query` orphan guard — data/client.py

Create a span only when `lf.get_current_trace_id()` is not `None`. Dev/benchmark queries run
outside any root trace → no span → the 481-orphan class of noise stops at the source, with zero
changes to `api/dev.py`. Judge-visible traces become exactly the set of real investigations.

### 3. Instrumentation map

| Phase span | Wraps | Output (the "why") |
|---|---|---|
| `detect` | window scan + window-level anomaly (`bundle.py`) | observed, expected, robust z, direction, window chosen |
| `decompose` | LMDI (`decomposition.py` call site in `bundle.py`) | per-factor contribution %, `primary_factor` |
| `drilldown` | whole recursion (`bundle.py`) | localized segment, depth reached |
| `depth-N:{dim}` | each recursion level (`drilldown.py`) | dims tested, winner, contribution %, lift, decision descend/stop + reason |
| `ruled-out` | `_ruled_out` (`bundle.py`) | each hypothesis + clearing number |
| `narrate` | existing generation span | + guardrail verdict (already present) |

SQL span names threaded through `run_query(name=...)`: `sql:baseline`, `sql:factor-sums`,
`sql:contribution:{dim}`, `sql:window-scan`, etc. Chat's `run_detection`/`build_bundle` call
these same functions, so the chat path inherits the structure.

### 4. Trace-list surfacing

- Root trace update on completion: `output` = verdict summary (`primary_factor`,
  `localized_segment`, `score`, `pct_delta`, `detected`); `tags` = `[metric, "detected"|"clean"]`.
- Langfuse **scores** per investigation: `anomaly_score` (numeric) at detect; `guardrail_passed`
  (0/1) at narrate. Both render as trace-list columns.

### 5. Config

`config.json` gains `"tracing": {"live_flush": true}`. Everything else already config-driven.

### 6. Testing

Fake-Langfuse client capturing an in-memory span tree (extends existing test pattern). Assert:

1. Phases nest under root in algorithm order.
2. Verdicts land as span output (decision + numbers).
3. `run_query` emits **no span** outside an active trace.
4. Pipeline runs unchanged with Langfuse disabled (keys unset).

### 7. Documentation deliverable

`docs/langfuse.md` — how to read a trace as a judge (phase story, scores, tags), how the live
flush behaves in a demo, login/where-to-click for the self-hosted UI, and a dev section: adding
a phase to new code, degradation semantics when keys are unset.

## Risks

- **Langfuse v4 SDK API drift** (`get_current_trace_id`, score API): verify against installed
  4.14.x; wrap score calls defensively like `narration_span` already does.
- **Per-phase flush latency**: ~5–8 flushes per investigation, each a small network call to
  langfuse-web; acceptable, and `live_flush: false` turns it off.
