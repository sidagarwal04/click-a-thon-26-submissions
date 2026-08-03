# Submission compliance mapping

Cross-references the shipped system against the three governing documents: the v1 problem
statement, the v2 insights change plan, and the SonyLIV submission guidelines. Built by reading
the cited files directly; anything not directly confirmed is marked UNVERIFIED.

---

## Table 1, v1 console vs `docs/problem/PROBLEM_STATEMENT.md`

| Requirement | Where satisfied (file:line) | Surfaced in the UI? (which component/route) | Gap |
|---|---|---|---|
| Q1: define an active interval when heartbeat missing/paused/backgrounded (`PROBLEM_STATEMENT.md:22`) | `sql/schema/03_event_state.sql` (three-bucket state machine, 90s gap tolerance), per `docs/problem/DESIGN.md:18` | Not directly rendered; consumed by the serving tables behind `frontend/src/app/api/concurrency/route.ts` | None, answered at the data-model layer, which is what the question asks for |
| Q2: how active ranges should be represented (`PROBLEM_STATEMENT.md:23`) | normalized intervals to per-session minute runs to +1/-1 deltas, `docs/problem/DESIGN.md:19`, section 3 | Not a UI concern | None |
| Q3: compute minute-wise peak/average without scanning raw history (`PROBLEM_STATEMENT.md:24-25`) | `sql/queries/serving/peak_average.sql`, `sql/queries/serving/concurrency_curve.sql`, per `docs/problem/DESIGN.md:20`, sections 4-6 | `frontend/src/components/ConcurrencyChart.tsx`, backed by `frontend/src/app/api/concurrency/route.ts` and `frontend/src/app/api/user-concurrency/route.ts` | None |
| Q4: filter-friendly across platform, country, content, video type, time grain (`PROBLEM_STATEMENT.md:26`) | same serving queries, parameterised; `docs/problem/DESIGN.md:21`, section 7 | `FilterRail` component wired into `ConcurrencyChart.tsx` (imported `ConcurrencyChart.tsx:8`, filter state `ConcurrencyChart.tsx:88-95`) | See Table 3 row on filter-to-column documentation: the mapping is implemented but not written up in README |
| Q5: handle sessions still open (`PROBLEM_STATEMENT.md:27`) | `sql/queries/serving/open_sessions.sql` plus retraction path, `docs/problem/DESIGN.md:22`, section 9b | `frontend/src/app/api/open-sessions/route.ts` | None |
| Great: Correct (`PROBLEM_STATEMENT.md:56`) | Parity/oracle evidence, e.g. `evidence/oracle_parity__20260801T193552Z__3be2212.tsv` | N/A (evidence artifact, not a UI surface) | None |
| Great: Fast (`PROBLEM_STATEMENT.md:57`) | Read-budget table, `docs/problem/DESIGN.md:30-34` (`[V:filter_shapes]`) | Read cost reported alongside answers per view (v2 route: see Table 2) | None |
| Great: Update-friendly (`PROBLEM_STATEMENT.md:58`) | Incremental delta absorption noted at `docs/problem/DESIGN.md:24-28`; open-session retraction path | `frontend/src/app/api/open-sessions/route.ts` | UNVERIFIED, no single file confirms watermark-driven incremental refresh end-to-end for this table; would need `docs/LATENESS.md` cross-check, out of scope for this pass |
| Great: Explained (`PROBLEM_STATEMENT.md:59`) | `docs/problem/DESIGN.md` in full, decisions with trade-offs | N/A | None |
| Evaluation: Correctness (`PROBLEM_STATEMENT.md:63`) | `evidence/oracle_parity__*.tsv` | N/A | None |
| Evaluation: Query performance (`PROBLEM_STATEMENT.md:64`) | `docs/problem/DESIGN.md:30-34`, read-budget rows | N/A | None |
| Evaluation: Update handling (`PROBLEM_STATEMENT.md:65`) | `docs/problem/DESIGN.md:24-28`; open-session path | N/A | Same UNVERIFIED note as above |
| Evaluation: Design quality (`PROBLEM_STATEMENT.md:66`) | `docs/problem/DESIGN.md` in full | N/A | None |
| Evaluation: The unseen day (`PROBLEM_STATEMENT.md:67`) | `docs/RUNBOOK_UNSEEN_DAY.md` (present in `docs/`, not read in this pass) | N/A | UNVERIFIED, file exists but its content was not verified as part of this compliance pass |
| Hard requirement: ClickHouse as primary datastore (`PROBLEM_STATEMENT.md:39`) | All schema/query files live under `sql/`, targeting ClickHouse; `docs/problem/DESIGN.md` throughout | N/A | None |
| Hard requirement: meaningfully integrate ClickStack/Langfuse/LibreChat (`PROBLEM_STATEMENT.md:40`) | `docs/clickstack.md` (ClickStack chosen over Langfuse/LibreChat, rationale at `docs/clickstack.md:10-16`); evidence `evidence/clickstack_integration__20260801T160716Z__d2b6c86-dirty.tsv` shows `verdict PASS` (5 dashboard tiles, 11 `otel_*` tables, registered source `phoenix.concurrency_deltas`, event watermark lag 1s, query_log rows for serving tables in 6h window: 4340) | Both consoles now link to it: `frontend/src/components/ConsoleHeader.tsx:8,29` (`/`) and `frontend/src/app/v2/InsightConsole.tsx:77,281` (`/v2`), pointing at `NEXT_PUBLIC_CLICKSTACK_URL` or `http://localhost:8090` where `docker/clickstack/compose.yml` puts it | None: ClickStack is still a separate Docker service, not embedded, but a judge on either console now has a link to it rather than needing to read `docs/clickstack.md` to discover it |

---

## Table 2, v2 console vs `sonyliv_concurrent_user_insights_db_change_plan_v2.md`

Plan's "Recommended First Release" (`sonyliv_concurrent_user_insights_db_change_plan_v2.md:1259-1270`) names six tables. Ten views are registered in
`frontend/src/app/api/v2/insight/[view]/route.ts:31-97`, reading SQL from `sql/insights/benchmark/`.

| View id | Reads table | Plan phase | Gate A parity evidence in evidence/? | Gate B query_log evidence in evidence/? |
|---|---|---|---|---|
| `versions` (route.ts:56-61, `session_facts_app_version_health.sql`) | `session_insight_facts` | Phase 1 (plan:411, gate at plan:1454) | `evidence/insight_parity_session_facts__20260801T175457Z__bd04d14-dirty.tsv` and `evidence/insight_parity_session_facts__20260801T201017Z__83b9ff6-dirty.tsv` | `evidence/insight_bench_session_facts_app_version_health__20260801T195215Z__f1b6d38-dirty.tsv` |
| `states` (route.ts:38-43, `state_flow.sql`) | `session_state_transitions` | Phase 2 (plan:520, gate at plan:1505) | `evidence/insight_parity_state_flow__20260802T003437Z__8cae0d7-dirty.tsv` (server-side diff, `sql/insights/validation/state_flow_diff.sql`, 36 rows each side, 0 disagreements, verdict PASS) | `evidence/insight_bench_state_flow__20260802T003033Z__8cae0d7-dirty.tsv` |
| `flow` (route.ts:32-37, `audience_snapshot_minute_trend.sql`) | `audience_minute_snapshot` | Phase 3 (plan:577, gate at plan:1543) | `evidence/insight_parity_audience_snapshot__20260801T201012Z__83b9ff6-dirty.tsv` | `evidence/insight_bench_audience_snapshot_minute_trend__20260801T194914Z__f1b6d38-dirty.tsv` |
| `spikes` (route.ts:62-70, `spike_explanation.sql`) | `concurrency_spike_events` | Phase 4 (plan:634, gate at plan:1588) | **MISSING** | `evidence/insight_bench_spike_explanation__20260802T003104Z__8cae0d7-dirty.tsv`, `evidence/insight_bench_spike_explanation__20260802T003208Z__8cae0d7-dirty.tsv` |
| `retention` (route.ts:44-49, `cohorts_retention_curve.sql`) | `content_entry_cohorts` | Phase 5 (plan:714, gate at plan:1617) | `evidence/insight_parity_cohorts__20260801T201013Z__83b9ff6-dirty.tsv` | `evidence/insight_bench_cohorts_retention_curve__20260801T195022Z__f1b6d38-dirty.tsv` |
| `health` (route.ts:50-55, `health_incident_window.sql`) | `playback_health_minute` | Phase 8 / Playback Health (gate at plan:1707) | `evidence/insight_parity_health__20260801T201015Z__83b9ff6-dirty.tsv` | `evidence/insight_bench_health_incident_window__20260801T195119Z__f1b6d38-dirty.tsv` |
| `switching` (route.ts:71-76, `journey_content.sql`) | `user_content_transitions` | Phase 6, out of first release (plan:769) | **MISSING** | **MISSING** |
| `handoff` (route.ts:77-82, `journey_platform.sql`) | `user_platform_transitions` | Phase 7, out of first release (plan:838) | **MISSING** | **MISSING** |
| `forecast` (route.ts:83-88, `concurrency_forecast.sql`) | `audience_minute_snapshot` | Phase 3 data, later prediction phase (plan Phase 9-12, out of first release) | Covered indirectly by the `flow` view's parity file | **MISSING** dedicated bench file |
| `lateness` (route.ts:89-96, `lateness_audit.sql`) | `late_event_audit` | Phase 0 mandatory fix (plan:314, lateness policy at plan:370) | **MISSING** | **MISSING** |

**First-release table coverage**: all six plan tables have at least one registered view
(`session_insight_facts` -> `versions`, `session_state_transitions` -> `states`,
`audience_minute_snapshot` -> `flow` and `forecast`, `concurrency_spike_events` -> `spikes`,
`content_entry_cohorts` -> `retention`, `playback_health_minute` -> `health`). No first-release
table is missing a view. `session_state_transitions` now has both Gate A parity (`state_flow`,
36 rows each side, 0 disagreements) and Gate B evidence checked in. `concurrency_spike_events`
now has Gate B evidence but still has no Gate A parity file.

**Additional discrepancy found (beyond the two flagged deviations below)**: `evidence/LEDGER.tsv`
contains entries for a separately derived `phoenix_insights` database (e.g. `derive_phoenix_insights`,
`replicate_phoenix_next_to_phoenix_insights`, `refresh_insights_phoenix_insights`,
`spike_sustainability_phoenix_insights`), but the shipped API reads `phoenix_next`
(`frontend/src/lib/insights.ts:15` - `INSIGHT_DATABASE = process.env.CH_INSIGHT_DATABASE || 'phoenix_next'`).
A `phoenix_insights` database was built and evidenced but the live route does not query it. This
is separate from, and in addition to, the deliberate database-name deviation noted below.

**Notes (deliberate deviations, not gaps):**
- The plan names database `phoenix_insights` throughout (e.g. `sonyliv_concurrent_user_insights_db_change_plan_v2.md:299,420`); the shipped tables live in `phoenix_next` (`frontend/src/lib/insights.ts:15`). Documented team decision, not a defect.
- The plan specifies no materialized or regular views (`grep -ni "view\b"` against the plan returns zero matches); the ten `route.ts` "views" are an API-layer naming convention over plain SQL queries against physical tables, not ClickHouse view objects.

---

## Table 3, `docs/problem/SONYLIV_SUBMISSION_GUIDELINES.md` checklist

| Requirement | Status | Evidence or what is missing |
|---|---|---|
| Concurrency curve rendered in product UI (`SONYLIV_SUBMISSION_GUIDELINES.md:16-26`) | Done | `frontend/src/components/ConcurrencyChart.tsx`, served by `frontend/src/app/api/concurrency/route.ts` and `frontend/src/app/api/user-concurrency/route.ts` |
| ...with the ClickHouse query included (`SONYLIV_SUBMISSION_GUIDELINES.md:23-24`) | Done | Both consoles now render the actual query text (not just its filename) via the shared `QueryPanel` component (`frontend/src/components/QueryPanel.tsx`), fed by `sql`/`sqlFiles`/`reads`/`rowsRead`/`bytesRead`/`serverMs` on the API response. `QueryPanel` reads the file at request time and hands back exactly what executed (comments stripped for display only), so there is no separate copy to drift; the read cost (rows, bytes, server ms, wall ms) is shown underneath |
| Dataset filters applied to curve and every other view (`SONYLIV_SUBMISSION_GUIDELINES.md:28-34`) | Done | `FilterRail` wired into `ConcurrencyChart.tsx` (`ConcurrencyChart.tsx:8,214-217`) and into the v2 console's per-view filter set (`ALL_FILTERS` in `frontend/src/app/api/v2/insight/[view]/route.ts:29`), with per-view `honours` lists for the spike/switching/handoff/lateness views (`route.ts:62-96`). The v2 console now **disables** the controls a view cannot honour and names the table that lacks the column, rather than accepting a filter and silently dropping it |
| ...documented in the README which dataset columns back each filter (`SONYLIV_SUBMISSION_GUIDELINES.md:35`) | Done | `README.md`, "Filters, and the dataset column behind each": one row per filter giving the dataset column, the serving table it prunes on, and what it applies to. Also names the two documented dataset dimensions deliberately not exposed (`subtitle_language`, `category`) |
| Source code (`SONYLIV_SUBMISSION_GUIDELINES.md:39-40`) | Done | This repository |
| README with hosted demo link (`SONYLIV_SUBMISSION_GUIDELINES.md:40`) | Outstanding | `README.md` (140 lines) contains no hosted/deployed URL |
| Architecture (`SONYLIV_SUBMISSION_GUIDELINES.md:40`) | Done | `README.md:31-56` (prose plus a diagram), linking to `docs/problem/DESIGN.md` and `docs/DATA_MODEL.md` |
| Recorded demo video, 2-3 min (`SONYLIV_SUBMISSION_GUIDELINES.md:40-42`) | Outstanding | No `.mp4`/`.mov`/`.webm` file or reference to a hosted video found anywhere in the repository |
| Pitch deck PDF (`SONYLIV_SUBMISSION_GUIDELINES.md:40-42`) | Outstanding | `pitch/` contains only `NOTES.md`, which is an explicit placeholder ("Placeholder until there is something to show") with an unchecked todo list (story, model diagram, benchmark results, 100x scaling). No PDF or slides exist |
| Screenshots (`SONYLIV_SUBMISSION_GUIDELINES.md:40-42`) | Outstanding | The browser extension needed to capture them is unavailable in this environment; none checked into the repo |

---

### Summary of gaps and outstanding items

**Gaps (Table 1):** none outstanding. ClickStack integration is evidenced (`evidence/clickstack_integration__20260801T160716Z__d2b6c86-dirty.tsv`, verdict PASS) and both consoles now link to it (`ConsoleHeader.tsx`, `InsightConsole.tsx`).

**Gaps (Table 2):**
- `concurrency_spike_events` (1 of 6 first-release tables) still has no Gate A parity evidence checked into `evidence/`, only Gate B. `session_state_transitions` is now fully covered (Gate A and Gate B).
- A `phoenix_insights` database was derived and evidenced in `evidence/LEDGER.tsv` but the shipped `route.ts` reads `phoenix_next` instead, evidence exists for infrastructure the live API does not use.

**Outstanding (Table 3):**
- README has no hosted demo link.
- No recorded demo video (2-3 min) exists in the repo.
- No pitch deck PDF exists; `pitch/` is an unchecked placeholder.
- No screenshots checked in; the browser extension needed to capture them is unavailable here.
