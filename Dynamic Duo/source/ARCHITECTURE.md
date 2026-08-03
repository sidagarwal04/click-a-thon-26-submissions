# Architecture — Automated Root-Cause Analyst

**Current scope (team decision 2026-08-01): the interactive flow.** A user sees
incidents in LibreChat, asks about one, and the system drills down live — running our
fixed q1–q6 queries through an MCP server — then presents the evidence. We build and
test this end to end first: it makes the flow, the correctness of every query, and the
look of the product visible. Automatic detection and any pre-filling policy are
**parked** (see last section) and revisited after the flow works.

## System overview

```
                      ClickHouse (rca database)
  ┌──────────────────────────────────────────────────────────────────┐
  │ dims+dictionaries ─▶ ad_events ─MV▶ ad_events_enriched           │
  │                                 ─MV▶ metrics_hourly_by_dim       │
  │                                                                  │
  │ incidents            ← the intake: whatever names a              │
  │                        (metric, window, scope) creates one       │
  │ investigation_steps  ← the trace: hypothesis · SQL · result ·    │
  │                        decision, per step                        │
  │ diagnoses            ← narrative + evidence bundle + verified    │
  └──────────────────────────────────────────────────────────────────┘
                ▲                                   ▲
                │ writes                            │ read-only SELECTs
        ┌───────┴────────┐                  ┌───────┴────────┐
        │    rca-mcp     │                  │ mcp-clickhouse │
        │ (custom, ours) │                  │   (official)   │
        │ list_incidents │                  │ follow-up SQL, │
        │ investigate    │                  │ query visible  │
        │ investigate_   │                  │ in chat        │
        │   window       │                  └───────┬────────┘
        └───────┬────────┘                          │
                └──────────────┬────────────────────┘
                               ▼
                     LIBRECHAT — "RCA Analyst" agent
        "what incidents are there?" → "why did fill drop?" →
        (drill-down runs LIVE, trace written as it goes) →
        "what about APAC?" → fresh read-only SQL
```

Philosophy, unchanged: **ClickHouse computes every number; a fixed deterministic query
sequence decides the drill-down; the LLM narrates and formats only; every step leaves a
trace.**

## The interactive flow (what we are building and testing)

1. **See incidents.** User asks "what incidents are there?" → agent calls
   `list_incidents` → table of incident rows with headline/status/window/severity.
   (Rows come from the dev-run seed — profiler → sweep → `agent/prefill.py`, see
   the un-parked note below; `investigate_window` also creates rows on demand.)
2. **Ask about one.** "Why did fill rate drop June 23–25?" → agent calls
   `investigate(incident_id)` → pre-filled incidents return their stored diagnosis
   instantly (presentation of static data); otherwise — and on `force` re-runs —
   the runner executes the fixed sequence
   **q1 decompose → q2 sweep (per lever dims) → [q5 mix gate if all-flat] → q3
   confound → q4 peer cross-check**, branching only on returned numbers, logging every
   step (hypothesis, exact SQL, result rows, decision) to `investigation_steps` via
   `detector/tracing.py`, then one narrator LLM call guard-railed by
   `detector/guardrail.py` → verified narrative + evidence returned to chat and stored
   in `diagnoses`.
3. **Ask about anything.** "Something feels off with rewarded ads Tuesday" →
   `investigate_window(metric, window, scope?)` — same runner on an ad-hoc window;
   "nothing moved beyond noise, here's what I checked" is a valid verdict.
4. **Follow up.** "Which apps were hit hardest?" → mcp-clickhouse composes a read-only
   SELECT (patterns whitelisted in the agent instructions), the SQL shown beside the
   answer.

Every number the user sees traces to a query; the "why" answers are computed by the
fixed sequence, never by the chat model. Humans may *trigger* any investigation; no
human ever *authors* one — however invoked, the diagnosis is computed by the fixed
sequence and proven by its trace (the rules' line: system-generated-with-trace vs
hand-written, not human-present vs human-absent).

## Metrics an incident can be about

The whitelist family from [`sql/agent/README.md`](sql/agent/README.md) — volumes:
requests, fills, impressions, clicks, revenue; ratios: fill_rate, render_rate, ctr,
ecpm — any of them, on any window/scope, via `investigate_window`. Coverage basis
(relevant when detection is un-parked): monitoring the two volumes (requests, revenue)
+ the three funnel ratios + eCPM is a *complete basis* — the funnel identity
(fills = requests × fill_rate; impressions = fills × render_rate; clicks =
impressions × ctr) guarantees any movement in a raw count surfaces in a monitored
metric; standalone raw-count series would only re-detect the same events.
Generalization (deck/judge answer): a metric here is a (numerator, denominator) pair
over dimensioned events — new domains (sign-ups, error rate) are whitelist rows, not
redesigns; quantile metrics (latency p95) are the honest exception — they need
quantile-sketch states in the rollup (AggregatingMergeTree), not additive counters.

## Components

| piece | what it is | owner | state |
|---|---|---|---|
| Schema + loader + MV cascade + load-time validation | `sql/00–06,99` + `load.sh` (`CH_SECURE=0` server mode added) | Srikanth | ✅ |
| Drill-down queries q1–q6 | `sql/agent/*.sql`, validated | Nitya | ✅ |
| Runner (executes q1–q6, branches on numbers, assembles bundle) | `agent/` package (`runner.py` + `whitelist.py` + `narrator.py`), importable: `investigate` / `investigate_window` / `list_incidents` | Nitya | ✅ tested vs VALIDATED.md |
| Tracing (`Investigation.step/generation/close`) + guardrail | `detector/tracing.py`, `detector/guardrail.py` | Srikanth | ✅ |
| **rca-mcp** — MCP server exposing `list_incidents` / `investigate` / `investigate_window`, calling the runner | `rca_mcp/server.py` (~90 lines), compose sidecar (streamable HTTP :8100) | Srikanth | ✅ protocol-tested |
| **mcp-clickhouse** — official server, read-only user `librechat_ro` (SELECT-only grants) | compose sidecar + `sql/07` (writes verified blocked) | Srikanth | ✅ |
| **LibreChat** — compose stack + "RCA Analyst" agent (instructions: answer-routing policy, schema card, sum/sum formulas, query patterns, gotchas) + conversation starters + golden-question checklist | `librechat/` package (runbook: `librechat/README.md`) | Srikanth | ✅ stack up, both MCP servers connect; agent = 2-min UI step |
| ClickHouse server for the stack (local docker now, Cloud at the end) | env swap only | Srikanth | ✅ docker (25.5), Cloud swap documented |

## The runner ⇄ platform contract (unchanged)

- Input: `(metric, window_start, window_end, scope)` — from an incident row or from
  `investigate_window`. Deterministic `incident_id` = `{window}_{metric}_{scope}`;
  re-investigation converges (ReplacingMergeTree), `force` re-runs.
- Every step → `Investigation.step(...)`: row in `investigation_steps` (+ optional
  OTLP export to ClickStack, env-gated, dormant by default).
- Narrator → `Investigation.generation(...)`; publication blocked unless
  `guardrail.verify(narrative, evidence).ok`; result → `diagnoses`
  (`numbers_verified` stored).
- q6 excluded-dates reads past **confirmed-cause** verdicts (join to `diagnoses.verdict_code`) — source-agnostic. Hedged short-history verdicts (PEER_OUTLIER) close as `diagnosed` but never exclude dates: letting them do so starves later baselines chronologically (EDGE_CASES.md finding, resolved).
- Baseline shortage (min_clean_days < 2) → q4-only path; agent never invents baselines.

## Storage (DDL in `sql/`, unchanged)

`dim_*`+dictionaries · `ad_events` (raw, `dataset` tag) · `ad_events_enriched`
(dims glued at insert, `event_date` in sort key) · `metrics_hourly_by_dim`
(long-format hourly counters — q2a hot path reads this) · `incidents` ·
`investigation_steps` · `diagnoses` · (`series_profile` — used by parked detection;
harmless at rest).

Ratios are always computed sum/sum at read; `NAM` not `NA`; advertiser `''` = unfilled
vs `'(none)'` bucket on the rollup; rollup reads always aggregate (SummingMergeTree).

## Requirements & judging map (current scope)

| criterion | where |
|---|---|
| ClickHouse primary + analytical depth | all analysis in the q1–q6 SQL + rollup/enriched reads |
| LibreChat (the ≥1-tool integration, meaningful) | it is the product surface: incidents, live drill-downs, follow-ups all happen there |
| Trustworthiness (no fabricated numbers) | fixed query sequence + guardrail + `numbers_verified`; chat "why" answers come only from tool results |
| Traceability | `investigation_steps` written live during each drill-down; readable in chat ("how do you know?") and as a table |
| Fast ("diagnosed in seconds") | measured: q1–q6 < 1s SQL total, ~3 round trips + one LLM call ≈ 4–5s, demonstrated live in chat |

## Build order (current)

1. ✅ `librechat/` package: compose stack (LibreChat + Mongo + mcp-clickhouse + rca-mcp),
   `.env` template, `sql/07_librechat_user.sql` (read-only grants), agent instructions,
   conversation starters, golden-question checklist. Local `clickhouse-server` docker +
   loader tweak (`CH_SECURE=0`, port 9000) so the stack has a server to talk to.
2. ✅ rca-mcp tools wired to the runner (integration point: the runner as an importable
   function — same signature as the contract above).
3. **Checkpoint: the interactive flow works** — programmatic half ✅: drill-downs
   reproduce every VALIDATED.md number (Jun 23–25 → Android 15, −3.455 pp, 97.5% of
   move, guardrail-verified, ~0.5 s SQL), traces written live, MCP protocol tested
   tool-by-tool, read-only user verified write-blocked. Chat half: walk
   `librechat/GOLDEN_QUESTIONS.md` after the 2-minute agent setup
   (`librechat/README.md` §5 — needs an `OPENAI_API_KEY` in `librechat/.env`).
4. Then: revisit the parked items below; Cloud migration at the very end (env swap).

## Parked — revisit after the flow is tested

Automatic detection (profiler + sweep in `detector/` — built, validated on dev data,
pushed) and any pre-filling/batch policy for Day 2, including production scheduling.
Deliberately out of the current document scope; nothing in the interactive flow depends
on them — `incidents` is an open intake and `investigate_window` works without any
detector. Decision on how detection re-enters (and whether/when anything is pre-run)
happens after we've seen the flow work end to end.

**Un-parked 2026-08-01 (flow tested end to end): pre-filling.** Seeding now runs
profiler → sweep → **`agent/prefill.py`**: every seeded incident is batch-investigated
*chronologically* (q6 hygiene applies earlier verdicts to later baselines exactly as
live operation would), so `incidents` + `investigation_steps` + `diagnoses` are fully
populated and LibreChat's job on listed incidents is presentation of stored,
system-generated-with-trace diagnoses. `investigate_window` (and `force=true`
re-runs) remain the live path. Production scheduling of detection stays parked.
