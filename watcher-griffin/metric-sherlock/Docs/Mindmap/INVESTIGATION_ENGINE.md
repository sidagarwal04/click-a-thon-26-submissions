# Investigation Engine

Orchestrated as a **LangGraph `StateGraph`** (`engine/graph.py`), not a hand-rolled Python call sequence — see "Orchestration" below for why. Every node is still a thin wrapper around the same deterministic, ClickHouse-backed functions:

1. Validate baseline. — `engine/baseline.py`: incident window vs like-for-like baseline (same weekday, trailing N weeks); queries `hourly_overall`.
2. Decompose metric. — `engine/decompose.py`: Revenue ≈ Requests × Fill rate × eCPM/1000 against `hourly_overall`, isolates which factor moved. Skipped (conditional edge) for non-revenue metrics — the requested metric itself becomes the factor to rank.
3. Rank dimensions by contribution. — `engine/rank.py`: queries the relevant `hourly_by_*` rollups **concurrently** (rollups first, always), ranks dimension values by share-of-deviation. This is drill-down level 0.
4. **Recursive** drill-down. — `engine/drilldown.py`: a graph node that **loops back on itself** — keeps drilling into whichever dimension still concentrates the deviation (falls back to raw `ad_events`, since no rollup covers an N-dimensional slice; every fallback query is logged verbatim) until either nothing concentrates enough (`drilldown_concentration_threshold`, default 0.15) or `max_drilldown_depth` (default 3) is hit. Each level's filter is the **conjunction** of every prior level's pinned (dimension, value) pair — depth 3 stays within depth 1 *and* depth 2's segment, not just the latest one.
5. Rule out alternatives. — `engine/rule_out.py`: records dimensions/factors that did NOT explain the deviation, with actual numbers; the seasonality check always runs and is always logged, since seasonality-as-red-herring is an explicit planted case to catch.
6. Generate evidence. — `engine/evidence.py`: assembles the `EvidenceBundle` — metrics, every SQL query + result, `drilldown_levels` (one list of ranked segments per recursion depth, each segment citing the exact `source_step` query it came from), ruled-out list. The only artifact that reaches the LLM.
7. Narrate findings. — `engine/narrator.py`: LLM restates only numbers already in the evidence bundle, and must cite each key claim's `source_step` (e.g. "per the rank:hourly_by_region:current query") so the final narration itself names a real, traceable query — not just the surrounding JSON. Never computes, never invents; degrades to "narration unavailable" rather than fabricating on failure.

## Orchestration: why LangGraph

The engine was originally a fixed Python function-call sequence in `pipeline.py`. Reapproached with LangGraph specifically to get genuine recursive drill-down — a graph node with a conditional edge back to itself — instead of a hardcoded two-level special case. This is an orchestration change only: no node lets an LLM decide what to query, the query/contribution-math logic in `rank.py`/`drilldown.py` is unchanged, and `pipeline.py`'s `run_investigation()` keeps its exact external signature (`engine/graph.py`'s `run_graph()` is the one thing it calls differently).

Every step's queries run through `engine/ch_client.py` (bounded, retried, and logged) so the resulting trace list is exactly what's traced in Langfuse and returned in `evidence.queries`, regardless of how many drill-down levels ran. See `PRODUCTION_PLAN.md` for the full build plan.
