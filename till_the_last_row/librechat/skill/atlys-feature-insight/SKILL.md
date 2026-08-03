---
name: atlys-feature-insight
description: Use when a newly instrumented feature table has been created and you must analyze it end-to-end and produce a PM-ready insight summary AND a machine-readable insights manifest (Atlys/schemas/{spec_name}.insights.json — numeric confidence scores, related known issues K1-K7, and the Langfuse trace URL) for the visualization layer. Generic, spec-agnostic workflow — also the path for the unseen 6th spec.
---

# Skill: Feature Insight (new instrumented table)

Goal: when the Instrumentation Agent has just created a new feature table, analyze it
end-to-end and produce a PM-ready insight summary. This is the pipeline-mode deliverable
and the path the unseen 6th spec runs through — keep it generic, driven by what the
table actually contains, not hardcoded per feature.

## Step 1 — Discover, don't assume (and detect the shape)
- `DESCRIBE TABLE atlys.<new_table>` to learn columns and types. **A newly instrumented
  table is the JSON `payload` shape** — a single `payload JSON(...)` column holding all
  event types, discriminator at `payload.event` (see `atlys-json-payload-access`). Confirm
  it, then access fields as `payload.<field>` (backtick-escape nested paths, CAST for math).
- List the event types: `SELECT payload.event AS e, count() FROM atlys.<new_table> GROUP BY e`.
- `SELECT count(), min(payload.timestamp), max(payload.timestamp) FROM atlys.<new_table>`
  for size/window (flat legacy tables use bare `timestamp`).
- Check for a pre-aggregated MV sibling:
  `SELECT name FROM system.tables WHERE database='atlys' AND name LIKE '%_agg'` — prefer it
  (read with `*Merge`) over scanning the raw `payload` table.
- Identify: envelope paths (device/geo/etc.) vs feature-specific metric/dimension paths.
  Numeric `payload.*` paths are candidate KPIs; string/flag paths are candidate dimensions.
  Note which paths are event-type-specific (filter by `payload.event` before aggregating).
- Identify join keys present (`payload.user_id`, `payload.application_id`) to tie the
  feature to the existing (flat) funnel tables.

## Step 2 — Read the spec + context
- Read the feature's `spec.md` (the questions the PM will ask are usually listed there).
- Load latest context (metric defs, K1–K7). Note any new entities the feature implies.

## Step 3 — Baseline the feature
- Volume and adoption over time (`toDate(timestamp)` trend).
- Distribution of the key feature dimensions (top-N values, share).
- If the feature has a success/outcome event or flag, compute its rate.

## Step 4 — Tie to the funnel / conversion
- Do users who used the feature convert better/worse? Compare
  `purchase_completed` rate for feature-users vs non-feature-users, joining the flat funnel
  tables on `user_id` / `application_id`. Note the join crosses shapes: the feature table's
  key is `payload.user_id`, the funnel table's is the flat `user_id` — e.g.
  `... WHERE user_id IN (SELECT payload.user_id FROM atlys.<new_table> WHERE ...)`.
- Where in the funnel does the feature sit? Does it shift a specific step-through rate?

## Step 5 — Segment it
- Run the device / geo / destination cuts (see the `atlys-segment-comparison` skill).
- Look for a segment where the feature helps or hurts disproportionately.

## Step 6 — Explain with context
- Map any anomaly to K1–K7 or seasonality/campaigns (see the `atlys-known-issue-correlation` skill).
- Example shape: "Feature X lifts conversion +Y% overall, but iOS in the Gulf shows no
  lift / a drop, consistent with K1 (OTP autofill) at the pay step."

## Step 7 — Write the summary (PM audience)
Produce 2–4 insights, each with: Headline / Evidence (numbers + window + metric def) /
Why (context-linked, hedged) / Confidence (H-M-L + reason) / Suggested next step.
Add a one-line "data caveats" note (cleaning applied, small segments, contradictions
found). Never dump raw SQL output.

## Step 8 — Write the insights manifest (machine-readable, for the viz layer)

The PM prose is for humans; the **insights manifest** is the machine-readable twin that
the Tracing & Visualization Layer reads to show *"agent-generated insights with
confidence scores"* (PROBLEM_STATEMENT.md §4). Write **one manifest per spec**, a sibling
of the schema + metrics manifest:

```
Atlys/schemas/{spec_name}.insights.json
```

Commit it with the **`clickhouse_git_write` MCP** — the same writer the Instrumentation Agent uses;
you do not have a shell. Call it with the **EXACT** signature — do not guess, probe, or rename params:

```
write_and_push(
  relative_path = "Atlys/schemas/{spec_name}.insights.json",
  content       = "<the full JSON, inline as a string>",
  message       = "insights(analytics): {spec_name} insight summary"
)
```

`content` is the inline file text (not a path, not `sql`/`schema`/`files`). It commits + pushes
directly to `master`. This tool lives ONLY on the `clickhouse_git_write` MCP — **never** route it
(or any write) through the read-only `clickhouse-cloud` MCP; if `write_and_push` shows as "not
found", the wrong MCP is attached — stop and surface that, do not retry-loop against the read MCP.

If you were handed `spec_name` in the pipeline invocation (Instrumentation delegates to you as a
subagent), use it; otherwise derive it from the spec path / base table (it is the numbered spec
dir, e.g. `08_destination_card_clicked`).

### Structure (mirror the metrics manifest style)

```json
{
  "spec_name": "08_destination_card_clicked",
  "database": "atlys",
  "base_table": "atlys.destination_card_clicked",
  "generated_by": "analytics-agent",
  "generated_at": "2026-08-02T12:00:00Z",
  "trace_url": "https://<langfuse-host>/project/<id>/traces/<trace-id>",
  "time_window": { "from": "2026-05-01", "to": "2026-08-01" },
  "data_caveats": "os NULL on ~12% android rows (coalesced to 'unknown'); is_back_filled rows excluded.",
  "insights": [
    {
      "id": "guest-browse-lower-conversion",
      "headline": "Guest-browse card clicks convert to application_started ~38% worse than logged-in clicks.",
      "metric": "guest_browse_conversion",
      "evidence": "guest: 6.1% vs logged-in: 9.8% (application_started / destination_card_clicked), 2026-05-01→08-01, n=41,203 clicks.",
      "why": "Guests hit the auth wall before application; consistent with the funnel's known auth drop, not a feature defect.",
      "confidence": 0.82,
      "confidence_label": "High",
      "confidence_reason": "large sample, stable across weeks, metric defined in context.",
      "direction": "negative",
      "dimensions": ["is_guest_browse"],
      "segments": [
        { "segment": "is_guest_browse=1", "value": 6.1, "unit": "%", "n": 12840 },
        { "segment": "is_guest_browse=0", "value": 9.8, "unit": "%", "n": 28363 }
      ],
      "related_known_issues": [],
      "related_metrics": ["guest_browse_conversion", "guest_browse_click_share"],
      "suggested_next_step": "A/B a lightweight guest checkout to defer auth past application_started.",
      "evidence_sql": "SELECT is_guest_browse, ... GROUP BY is_guest_browse"
    },
    {
      "id": "ios-gulf-no-lift",
      "headline": "page_version v4 lifts click→application +5pp overall, but iOS in the Gulf shows no lift.",
      "metric": "page_version_ctr_to_application",
      "evidence": "v4: 11.2% vs v3: 6.3% overall; iOS+AE/SA: v4 6.4% vs v3 6.5% (flat).",
      "why": "Coincides with K1 (iOS WebKit OTP autofill) at the downstream pay step — not a page_version problem.",
      "confidence": 0.55,
      "confidence_label": "Medium",
      "confidence_reason": "Gulf-iOS segment small (n=1,910); correlation with K1 not proven.",
      "direction": "mixed",
      "dimensions": ["page_version", "os", "geoip_country_code"],
      "segments": [
        { "segment": "v4 / all", "value": 11.2, "unit": "%" },
        { "segment": "v4 / iOS+Gulf", "value": 6.4, "unit": "%", "n": 1910 }
      ],
      "related_known_issues": ["K1"],
      "related_metrics": ["page_version_ctr_to_application"],
      "suggested_next_step": "Segment the v4 rollout dashboard by os×region; hold v4 for iOS-Gulf until K1 ships.",
      "evidence_sql": "SELECT page_version, os, geoip_country_code, ... "
    }
  ]
}
```

### Rules

- **One entry per insight** you reported in the prose — the manifest must match the summary,
  not add or drop findings.
- **`confidence` is a number in [0,1]**; **`confidence_label`** is your H/M/L bucket and
  **`confidence_reason`** the one-liner. Map H≈0.75–1.0, M≈0.45–0.74, L≈0.0–0.44. Never
  emit a high score for a small/dirty segment — the reason must justify the number.
- **`related_known_issues`** uses the canonical `issue_id` keys `K1`…`K7` (from
  `context_docs/known-issues/`); empty array when none applies. Cite only correlation.
- **`related_metrics`** references metric `name`s from the spec's `{spec_name}.metrics.json`
  when the insight is about one — this links insights ↔ metrics ↔ schema in the viz.
- **`trace_url`** is the Langfuse trace of THIS analysis run ("no trace, no credit"). If you
  cannot obtain the URL, set it to `null` and note why in `data_caveats` — never fabricate one.
- **`evidence_sql`** may be a trimmed representative query, not every statement.
- Keep it **derived from data**, never hardcoded per feature (same guardrail as below).

## Genericity guardrail
Do not branch on the feature name. Everything above derives from `DESCRIBE`, the spec,
and the data. A spec you have never seen must flow through unchanged — including its shape:
introspect the `payload JSON(...)` column and its `payload.event` values rather than assuming
any field exists.
