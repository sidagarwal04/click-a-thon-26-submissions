# Submission — Atlys track

Index of the graded evidence, organized to match the "What to submit at code
freeze" checklist exactly. Everything under this directory is a captured
artifact from a real, unedited run of the pipeline on 2026-08-02 — nothing
here is hand-written.

## 1. Code + how to run it

Not duplicated here — see the repo root:

- **[RUN.md](../RUN.md)** — env vars, this submission's ClickHouse Cloud
  connection, and the one command that runs the pipeline end to end.
- **[SETUP.md](../SETUP.md)** — from a brand-new machine to a running UI.

## 2. Architecture

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** — the three agents and how they
  hand off (§1–§2, with a Mermaid flowchart per agent), where the context
  layer is stored and why, how Langfuse is wired (and the LibreChat/ClickStack
  status), and which LLM provider(s) are used and why (§4).

## 3. Unseen Data / Surprise Round folder (this directory)

| Requirement | Where |
| --- | --- |
| Generated DDL for the 5 known specs | [`ddl/`](ddl/) — one log per spec: full design reasoning, final DDL, executed statements, load results |
| Generated DDL for the 6th spec | Not yet possible — no 6th spec exists yet. Runbook ready: [`unseen_data/SPEC_6_PENDING.md`](unseen_data/SPEC_6_PENDING.md) |
| Analytics Agent's insight report over the 8 existing tables (autonomous run) | [`insights/baseline_8_tables_autonomous.log`](insights/baseline_8_tables_autonomous.log) |
| Context layer + before/after changelog (context-freshness proof) | [`context/CHANGELOG.md`](context/CHANGELOG.md) — v1 (bootstrap) → v6 (after all 5 specs), +25 tables, +398 entries, all automatic |
| 6th-spec bundle (schema + insight summary + trace) | Pending — see [`unseen_data/SPEC_6_PENDING.md`](unseen_data/SPEC_6_PENDING.md) for the exact runbook that produces it |

## 4. Langfuse trace links

**[TRACES.md](TRACES.md)** — every run above, indexed by `run_id`/`trace_id`,
with a live-link pattern and a durable JSON export per trace under
[`traces/`](traces/) (all spans, decisions, SQL, and real per-run cost —
$0.384 total across all 12 runs captured for this submission).

## Standard probe set

All 4 required prompts, run against the 8 existing tables, autonomous
(no manual SQL, no hints beyond the prompt itself):

| # | Prompt | Output | Trace |
| --- | --- | --- | --- |
| 1 | Analyze the existing funnel and surface the most important issues, with the why. | [`probes/01_funnel_issues.log`](probes/01_funnel_issues.log) | [TRACES.md](TRACES.md#standard-probe-set-all-4-against-the-8-existing-tables) |
| 2 | Where are we losing conversions, and for which segments (device / geo / destination)? | [`probes/02_losing_conversions_by_segment.log`](probes/02_losing_conversions_by_segment.log) | ↑ |
| 3 | Are there any regressions or trends over the last quarter? | [`probes/03_regressions_and_trends.log`](probes/03_regressions_and_trends.log) | ↑ |
| 4 | Is anything in the base context wrong, stale, or self-contradictory? | [`probes/04_context_self_consistency.log`](probes/04_context_self_consistency.log) | ↑ |

## Folder layout

```
submission/
├── README.md              this file
├── TRACES.md               every run_id/trace_id, live-link pattern, cost/timing summary
├── ddl/                    the 5 known specs, executed — full design + DDL + load logs
├── insights/               the autonomous baseline insight report over the 8 existing tables
├── probes/                 the 4 standard probe outputs
├── context/                before/after changelog (context-freshness proof)
├── traces/                 durable JSON export of every Langfuse trace referenced above
└── unseen_data/            the 6th-spec runbook, ready to execute the moment it drops
```
