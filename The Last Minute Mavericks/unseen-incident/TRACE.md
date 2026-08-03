# Trace — proof the pipeline generated the diagnosis

**Public Langfuse trace (no login required — trace is marked public):**

https://cloud.langfuse.com/project/cmsa4wcn20ah0ad0iy746nak4/traces/f6df80cbec40eb48ee1316048c53b8a3

- Trace name: `RCA scan · rca_unseen` — one trace for the whole scan, one span per
  investigation (3 investigations + scan summary = 4 observations).
- Each investigation span carries: verdict, culprit segment, window, factor
  decomposition, ruled-out list, and every evidence item with its ClickHouse `query_id`.
- Cross-check: the `query_id` on any evidence item in [`bundle.json`](bundle.json)
  matches the one recorded in the trace span — the diagnosis, the SQL, and the trace
  are the same run.

**JSON export (fallback, per submission guidelines):** [`trace_export.json`](trace_export.json)
— fetched from the Langfuse API immediately after the run; `"public": true` is visible in
the export.
