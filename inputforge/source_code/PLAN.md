# PLAN — Automated Root-Cause Analyst (InMobi track)

Agentic architecture: three separable agents sharing one trace, instead of one
monolithic pipeline. Detection is decoupled from investigation, and
investigation is decoupled from remediation, so each stage has its own
failure mode, its own trust level, and its own place in the trace.

## Why separate the stages

- **Detection** needs recall and cheap repeatability — it runs constantly
  over the full metric surface.
- **Investigation** needs precision and deep tool use — it runs once per
  flagged anomaly, agentically deciding which ClickHouse query to run next.
- **Remediation** is speculative — it must never contaminate the
  evidence-backed diagnosis if it hallucinates.

We are evaluated on synthetic **eval data** with planted anomalies whose
answer key is private, plus an **unseen incident** released on day 2. Nothing
in detection or investigation may be tuned to the specific anomalies we've
seen in the current dataset — thresholds must stay statistical (z-score /
seasonal baseline), not hand-fit. Build for the unseen incident.

## Stage 1 — Detection Agent (batch/cron sweep, mostly deterministic)

- Tool: parameterized ClickHouse query `(metric, time bucket)` vs. a
  seasonal baseline (same weekday/hour, trailing weeks — per
  [`metrics_glossary.md`](metrics_glossary.md) "Notes on normal").
- Sweeps revenue, fill rate, eCPM, CTR, requests hourly; flags deviations by
  z-score/%-delta against the like-for-like baseline, not fixed thresholds.
- Output: rows in an `anomalies` ClickHouse table:
  `{metric, time_window, observed, expected, delta, z}`.
  This table is both the trace start and the work queue for Stage 2.
- LLM role: none required. Keep this stage boring and reproducible.

## Stage 2 — Investigation Agent (agentic, per-anomaly)

- Triggered off `anomalies` (or a chat question parsed to the same shape).
- Tool-calling loop over ClickHouse:
  1. Revenue-identity decomposition (`Revenue ≈ Requests × Fill rate × eCPM / 1000`)
     to find which factor moved — volume, fill, or price.
  2. Tier-1: rank every dimension independently
     (`ad_format, category, tier, vertical, campaign_type, region, country,
     device_model, os_version`) by contribution to the delta.
  3. Tier-2: pairwise, conditional — only runs if Tier-1's best single
     dimension doesn't cover most of the delta (e.g. <60–70%). Cross only
     the top 2–3 Tier-1 dimensions with each other (not a full 9-way
     cross-product), with a min-support floor.
  4. Explicit rule-out checks, including the seasonality check the brief
     calls out (at least one planted movement is pure seasonality and must
     be checked and ruled out, not alarmed on).
- The LLM chooses *which* query to run next from the allowed tool set; it
  never computes a number itself, only narrates ClickHouse's output.
- Output: rows in an `investigations` table:
  `{anomaly_id, segment, factor, evidence, ruled_out[]}`
  plus a Langfuse trace of every query issued and why.

## Stage 3 — Remediation Agent (advisory, downstream, lowest-trust)

- Consumes a completed diagnosis; maps factor + segment → candidate
  hypotheses, e.g.:
  - fill-rate drop → check waterfall/demand partner
  - eCPM drop → check pricing floor
  - isolated to one `ad_format` → creative/format issue
- Strictly advisory text, grounded in the diagnosed factor. Not part of the
  scored rubric (detection/localization accuracy, explanation
  trustworthiness, analytical depth, traceability all concern Stages 1–2).
- Kept visually and structurally separate from the evidence-backed
  diagnosis in output and in the trace, so a judge can never mistake a
  hypothesis for a computed number.

## Entry points

Both share the same `investigate(metric, hour)` core from Stage 2:

- **CLI/scan** — sweeps a time range across all core metrics (Stage 1),
  auto-runs Stage 2 on each flagged anomaly, dumps structured output +
  Langfuse trace links. This produces the required unseen-incident
  deliverable, reproducibly.
- **Chat** (LibreChat or a lighter custom UI, tbd via a quick embed-ability
  spike) — a natural-language question ("why did revenue drop yesterday?")
  is parsed to `(metric, time window)` and routed through the same Stage 2
  core, or continues as a follow-up on an already-investigated anomaly.

## Requirements checklist (from PROBLEM_STATEMENT.md)

- [ ] ClickHouse as primary datastore; all drill-down logic lives in
      ClickHouse queries, not in the LLM.
- [ ] Meaningful integration of at least one of ClickStack / Langfuse /
      LibreChat (leaning Langfuse for trace, chat entry point tbd).
- [ ] Every number in a diagnosis reproducible from the data — no
      hallucinated figures.
- [ ] Explicit "checked and ruled out" list per investigation, including
      the seasonality case.
- [ ] Reproducible output + trace for the unseen incident, released day 2.

## Open questions

- LibreChat embed-ability for a custom backend — needs a quick spike before
  committing to it as the chat entry point.
- Exact min-support floor and Tier-1→Tier-2 escalation threshold (60–70%
  coverage) — validate against known planted anomalies, then re-check it
  isn't overfit before the unseen incident.
