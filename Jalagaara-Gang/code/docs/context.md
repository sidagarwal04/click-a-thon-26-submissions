# Session Context — where things actually stand

Written as a working snapshot after a long session of iteration on top of the team's base
build (see `PLAN.md`/`TASKS.md`/`CODING_STANDARDS.md` for the original design). This file
describes what exists RIGHT NOW, including two schema changes and a data model split that
happened after the original docs were written. Treat this as the source of truth for current
state; treat PLAN.md as the source of truth for original intent.

## The big picture

Automated RCA analyst over InMobi ad-metrics data in ClickHouse Cloud. Detects an anomaly,
decomposes which factor moved, drills down to the responsible segment, narrates it, and now
lets a dashboard user switch between detected anomalies and ask a bundle-aware chat about
whichever one is on screen.

```
ClickHouse (events_full, hourly_summary)
  → detection (stats or ML) → decomposition → drill-down  →  Evidence Bundle
  → narration (LLM, Langfuse-traced)  →  stored in `bundles` + `investigations`
  → FastAPI  →  React dashboard (anomaly switcher, metric tree, chat)
```

## Data model — READ THIS BEFORE TOUCHING store.py OR schema.sql

Two tables, split by concern (this is a REBUILD of what was originally one `investigations`
table with an embedded `bundle` JSON column — that older, wider shape still exists on disk as
`investigations_legacy`, unused, safe to drop):

### `bundles` — the evidence, one row per detection run
Every detection run gets a row here — not just the ones that fire. `is_anomaly=0` rows are
"checked, normal" traceability records (the majority, once context-seeding runs); `is_anomaly=1`
rows are real anomalies and carry the full drilled-down evidence.

Columns: `investigation_id, created_at, updated_at, window_start, window_end, metric, direction,
observed, expected, pct_delta, score, is_anomaly, primary_factor, localized_segment,
ruled_out_count, ruled_out_summary, narrative, narrated, trace_url, bundle` (bundle = full
`EvidenceBundle` JSON, the source of truth — everything else is a flattened projection of it for
SQL querying without parsing JSON).

`primary_factor == "pending"` is a **signal, not a bug**: it means the bundle came from the chat
detection-only path (`pipeline.run_detection`, no decompose/drill/narrate), not the full pipeline
(`pipeline.run_investigation` / `rca.bundle.build_bundle`). The dashboard's anomaly switcher
filters these out client-side (`api.ts` `listIncidents`) so an incomplete chat-triggered bundle
never gets showcased with empty panels.

### `investigations` — lean session record, references `bundles` by id
Columns: `investigation_id, bundle_id, trace_id, session_id, created_at, updated_at`. No
evidence duplicated here. `bundle_id == investigation_id` today (1:1), kept as its own column so
the two tables stay conceptually independent (a future investigation could reference a bundle it
didn't create).

`GET /bundles` (the dashboard's "Past investigations" history panel) reads a **JOIN** of the two
— `store.list_investigations()` — because the frontend's `InvestigationRow` type expects the
rich shape (metric, window, primary_factor, localized_segment, detected, narrated). Don't
"simplify" this back to a lean-only query without also changing the frontend.

### Both tables are `ReplacingMergeTree(updated_at)` keyed on `investigation_id`
Every read is `FINAL`. Every write (`store.save_bundle`) re-supplies ALL columns including
`trace_id`/`session_id` even when unchanged — omitting them on a later write (e.g. after
`/narrate`) silently blanks them, because ReplacingMergeTree replaces the whole row.

### Other tables (Lane A, chat)
`ad_events`, `apps_dim`, `advertisers_dim`, `geo_device_dim` (raw), `events_full` (denormalized,
one row per event, joined dims), `hourly_summary` (SummingMergeTree rollup, the table detection
actually queries). `chat_sessions`/`chat_turns` for the conversational layer (JAL-84).
`metrics_hourly_advanced` exists but its origin/owner is unclear — check with the team before
relying on or dropping it.

## Backend surface (`backend/api/main.py`)

- `POST /investigate` — full pipeline (detect → decompose → drill), NO narrative yet. Returns
  the bundle. Numbers only, so a judge can diff two calls for reproducibility.
- `POST /narrate/{id}` — adds prose to a stored bundle. Split from investigate so the UI shows
  real numbers in ~2s before the LLM sentence arrives, and so an LLM failure can't destroy an
  otherwise-complete bundle.
- `GET /bundle/{id}` — one full `EvidenceBundle`, resolved via `investigations.bundle_id → bundles`.
- `GET /bundles?limit=` — rich flattened history (see data model above). Dashboard's history panel.
- `GET /dashboard?limit=&since=` — reads `bundles` directly, `is_anomaly` etc. flattened, no JSON
  parse needed. This is what the anomaly switcher polls. `since` is a `created_at` cursor for
  incremental polling (not currently used by the frontend — it re-fetches on demand instead).
- `POST /v1/chat/completions` (and `/chat/completions`) — OpenAI-shaped. See "Chat" below.
- `GET/DELETE /chat/sessions...` — conversation history, unrelated to bundles.
- `/dev/*` — local-only dev dashboard (gated by `ENABLE_DEV_DASHBOARD`, default on). See below.

## Chat (`backend/api/chat.py` + `main.py::_handle_chat`)

Deterministic slot-filling + regex intent classification (no LLM in the classify step — cheap,
testable, can't hallucinate a date). `ChatCompletionRequest.bundle_id` is our own extension (not
OpenAI-standard): the dashboard sends the currently-showcased anomaly's id with every message, so
"this anomaly" resolves to what's on screen instead of the chat guessing.

Intents, in classify() priority order:
1. `greeting` — exact match on a short list ("hi", "thanks", ...).
2. `baseline` — "what were normal values that day" / "compare to baseline" / etc. Answered by
   `main._baseline_text()`, which calls `store.load_nearby_bundles()` — reads OTHER stored rows
   for the same metric within ±14 days, NOT the current bundle's own JSON. Fully deterministic,
   no LLM. **This is brand new and only works if `bundles` actually has nearby context rows
   seeded — see "Known issue" below, this is currently broken.**
3. `replay` — "replay this anomaly end to end" / "walk me through" / etc. Answered by
   `main._replay_text()`, a deterministic walkthrough built from the bundle's own fields
   (detection → decomposition → drill-down → verdict → ruled-out → trace link). No LLM.
4. `scan` — "what's wrong" / "any incidents" — points the user at how to ask a real question.
5. `investigate` (default, when metric+window slots are filled) — runs the REAL detection-only
   pipeline (`pipeline.run_detection`) then narrates. This is the path that produces
   `primary_factor: "pending"` bundles (see data model note above).
6. `followup` — slots incomplete, asks for what's missing.

Reroute rule: if `bundle_id` is set and intent lands on `followup`/`scan`, it's promoted to
`replay` — an under-specified question in dashboard context is almost always about the anomaly
on screen, not a request to start a fresh investigation.

## `/dev` endpoints relevant to seeding data

- `POST /dev/discover {start, end, method}` — sweeps a date range (global + per-segment) for
  anomalies, folds echoes/duplicates, returns candidates with `role: primary|secondary`. Doesn't
  persist anything.
- `POST /dev/seed_bundles {start, end, method}` — runs `discover()`, then the FULL pipeline
  (investigate + narrate) for each `primary` incident, persisting one real Evidence Bundle each.
  This is what produced the current 8 anomalies. Background job, poll `/dev/jobs/{id}`.
- `POST /dev/seed_context {days_before, days_after}` — **new this session, currently the thing
  that needs fixing (see below).** Intent: for each existing `is_anomaly=1` bundle, run detection
  for the surrounding ±N days so `bundles` has real "normal day" numbers to answer baseline
  questions from. Idempotent (skips a `metric, day` pair already present).

## KNOWN ISSUE — context-day detection fires far too often

First implementation of `seed_context` called `pipeline.run_detection()` per day, which
internally scans **every hour in that day (24 hypothesis tests)** and reports the worst one
(`rca.detection.detect_in_window`, designed for finding a real incident inside a coarse window).
Run across every context day, that's 24 chances per day to false-positive — result: nearly every
`fill_rate`/`ecpm`/`revenue` context day came back `is_anomaly: true` (measured — see chat log
around job `2bfd2a31`, 46 rows seeded, the overwhelming majority flagged true). That defeats the
entire purpose: there was no "normal" left to compare against.

**Fix applied but not yet re-verified end-to-end**: switched `seed_context` to call
`pipeline.run_investigation()` instead, which scores the WHOLE DAY as a single point against its
same-weekday-trailing-weeks baseline (`rca.bundle._window_anomaly`, one test, not 24). The bad
batch (48 rows) was deleted from ClickHouse; only the original 8 clean anomalies remain. The
fixed code is saved on disk (`dev.py` line ~506 calls `run_investigation`) but **`seed_context`
has not been re-run since the fix** — that's the next concrete step.

Open question worth deciding before re-running: even whole-day scoring uses only `weeks: 2`
trailing baseline samples (visible in earlier bundle output — `"weeks": 2`) for MAD, which is a
small sample and may still over-fire on real noise. Watch the re-seeded results; if the false
positive rate is still high, the fix may need to go deeper (e.g. widen the baseline window, or
use the pooled-relative-MAD fallback documented in the detection methodology memory).

## Frontend (`frontend/src/`)

- `App.tsx` — top-level state: `bundle` (current), `incidents` (switcher options from
  `listIncidents()`, sorted biggest-move-first), `history` (past-runs panel from `listBundles()`),
  theme, manual investigate controls (metric select + `DateField` start/end + Investigate button).
  On mount: loads health, history, and incidents; auto-selects the biggest mover.
- `api.ts` — all backend calls. `listIncidents()` filters out `primary_factor === "pending"`
  bundles (see data model note). `sendChat()` posts to `/v1/chat/completions` with `bundle_id`.
- `components/SidebarDock.tsx` — the bottom-right two-button dock: "Past investigations" (history
  list) and "Ask a follow-up" (built-in chat, NOT a LibreChat iframe — needs `bundle_id` per
  message, which only an in-house chat can carry). Both panels are `position: absolute` inside
  `.sidebar-dock`, which MUST have `position: relative` in CSS or clicks silently fall through to
  whatever's underneath (this was a real bug, fixed — see index.css `.sidebar-dock`).
- `components/MarkdownLite.tsx` — small hand-rolled renderer (headings `## `, bold `**x**`,
  inline code `` `x` ``, links `[x](y)`, `- ` bullets) for the chat's assistant messages. Not a
  general markdown engine — built specifically for what `_replay_text`/`_baseline_text`/narrator
  prose produce. If the backend starts emitting other markdown constructs (tables, nested lists),
  this won't handle them.
- `components/AnomalyCard.tsx`, `DiagnosisCard.tsx`, `FactorSplit.tsx`, `MetricTree.tsx`,
  `RuledOutPanel.tsx` — pure display components over `EvidenceBundle` fields, largely untouched
  this session.

Dev servers: backend `uvicorn api.main:app --port 8000 --reload` from `backend/`, frontend
`npm run dev` (Vite, port 5173) from `frontend/`. Both are started via the Bash/PowerShell tool
in this environment, not a persistent process — expect to restart them after edits that don't
hot-reload cleanly, and after any interrupted tool call (backgrounded servers get killed).

## Current ClickHouse data state (as of this writing)

`bundles` has exactly **8 rows** — the 4 audited real anomalies plus 4 rows freshly re-seeded via
the now-idempotent `/dev/seed_bundles`, correctly landing as `is_anomaly=0` (see "seed_bundles
made idempotent" below):

| metric | pct_delta | is_anomaly | localized_segment |
|---|---|---|---|
| requests | −43.5% | 1 | (empty — genuinely non-localizable, independently confirmed, see audit below) |
| fill_rate | −4.4% | 1 | os_version=Android 15 |
| fill_rate | −1.1% | 1 | region=APAC, os_version=iOS 18.1 |
| ecpm | −2.4% | 1 | category=finance |
| ecpm | −0.9% (window Jun 16) | 0 | (empty — correctly NOT promoted; segment-level peak was +7.2% for `ad_format=native` but the whole-window re-score and drill-down found nothing concentrated) |
| ecpm | +0.8% (window Jun 28) | 0 | (empty — correctly NOT promoted) |
| render_rate | +0.06% (window Jun 9) | 0 | (empty — correctly NOT promoted) |
| render_rate | +0.05% (window Jun 14) | 0 | (empty — correctly NOT promoted) |

This 4-real + 4-correctly-rejected split is the fixed `seed_bundles` override working as
intended — see "seed_bundles override fix, now validated end-to-end" below. **This count (8)
now exactly matches what `/dev/discover` reports as `primary_count` over the full range** — that
was the explicit ask this round ("same amount of bundles when we hit find anomaly").

No context/normal-day rows exist for the *dates around* each anomaly — `seed_context` still
needs a clean re-run before the "baseline" chat intent has anything real to answer with.
Deliberately not run this session — separate concern from anomaly-count parity.

`investigations_legacy` table exists on disk from an earlier schema migration, unused — safe to
`DROP TABLE investigations_legacy` when convenient, not urgent.

## seed_bundles made idempotent + validated end-to-end (this session)

User asked for two things: (1) the dev tool's "find anomaly" action should populate `bundles`
with matching data, and (2) re-running it shouldn't create duplicates of what's already there.

**Idempotency added** (`api/dev.py::_bundle_exists` + `seed_bundles`): before investigating a
discover-found primary, check for an existing `bundles` row with the exact same
`(metric, window_start, window_end)`; skip if found rather than re-running the full pipeline
with a fresh id. Verified live: re-running `seed_bundles` over the full range correctly reported
`already_present: 4` for the 4 curated anomalies (untouched, no new ids) and `seeded: 4` for the
4 previously-removed weak candidates (freshly re-investigated).

**Validates the seed_bundles override fix from the earlier audit.** All 4 freshly-seeded rows
came back `is_anomaly=false, localized_segment={}` — exactly the outcome the fix was designed to
produce (previously these same 4 candidates would have been force-promoted to `is_anomaly=true`
with nothing for drill() to find). This is independent confirmation, from a real second run, not
just code review, that the override fix works.

**Dev dashboard UI**: added a "Seed bundles from these findings" button next to "Find anomalies"
in `dev_dashboard.html`, calling the same `/dev/seed_bundles` endpoint with the same
start/end/model inputs. Result panel shows new/already-present/error counts and a table, with an
explicit note that new + already-present should equal Find anomalies' "distinct finding(s)"
count.

**Contamination found and cleaned during validation**: after the real seed_bundles run, `bundles`
briefly had 12 rows instead of the expected 8 — 4 extra (`revenue` ×2 duplicate, plus one stray
`ecpm` and one stray `render_rate`) that were **not** in the job's own returned result and whose
percentages matched none of the 8 known discover primaries. Something else concurrently called
`/investigate` during that ~45s window — likely a stray leftover browser tab/process from earlier
in the session, not identified further. Deleted; final state is the clean 8 above. **Worth
watching for if this recurs** — the app shares one single ClickHouse client instance
(`data/client.py::get_client`, `lru_cache(maxsize=1)`), which already caused one confirmed
concurrency error earlier this session ("Attempt to execute concurrent queries within the same
session") when a `/dev/tables` call landed while a seed job was running. That's a known
architectural constraint: avoid firing dev-tool requests while any background job is in flight.

## Localization audit (earlier this session, still holds) — why "only 1 bundle had a full tree"

## Localization audit (this session, now closed) — why "only 1 bundle had a full tree"

User noticed only one of the original 8 showcased anomalies had a multi-level metric tree and
asked whether localization was broken. **It wasn't.** Two rounds of investigation, in order:

**Round 1 — found 3 outright false positives.** `render_rate +0.058%` (score≈0), `render_rate
+0.050%` (score≈0), and `ecpm +0.78%` (score 2.73, below the ~3.5 calibrated threshold) were
never real anomalies. Root cause, in `dev.py::seed_bundles`:
```python
if row.get("scope") == "segment" and not b.anomaly.detected:
    b.anomaly.detected = True
```
This force-promoted ANY segment-sweep hit to `is_anomaly=True` regardless of how weak the
whole-window re-score came back, overriding the detector's own honest "not detected" verdict.
Deleted the 3 rows.

**Round 2 — found a diluted duplicate.** `ecpm −0.9%` (Jun 16–21, score −174 but under the
materiality gate) turned out to be the same finance-vertical event as the already-present
`ecpm −2.4% → finance` bundle (Jun 18–19), just captured at a wider, noisier window — manually
running the drill-down math showed `category=finance` would explain 98% of the gap at lift 13.9
if it had been allowed to drill, identical signature to the confirmed real one. Not a
localization failure, a redundant echo. Deleted.

**`seed_bundles` override — now fixed.** Changed to only promote a segment finding when drill()
independently found real corroborating evidence (`b.localized_segment` non-empty), not
unconditionally:
```python
if row.get("scope") == "segment" and not b.anomaly.detected and b.localized_segment:
```
Every real case (Android 15, APAC/iOS 18.1, finance) clears this — none of the 3 false positives
could have, since a genuinely flat move has no segment with disproportionate lift. Backend test
suite re-run clean after the change (209 passed / 1 skipped).

**`requests −43.5%` independently re-verified without relying on `TEST_CASES.md`.** Per explicit
user instruction, re-checked from raw ClickHouse numbers alone rather than citing the pre-written
expected answer. Pulled contribution+lift for every value of all 11 drilldown dimensions
directly: every single one clustered at lift 0.94–1.09 (i.e., every segment moved by exactly its
proportional share, no concentration anywhere). This is the actual mathematical signature of a
uniform population-wide event — confirmed independently, not assumed.

Net result at the time: went from 8 anomalies (3 fake) → 5 (1 redundant) → 4 clean, all
independently verified. **Since then** (see idempotency section above), `seed_bundles` was
re-run for real with the fix in place and correctly re-produced all 8 original discover
candidates as 4 real (`is_anomaly=1`, matching the 4 above) + 4 correctly-rejected
(`is_anomaly=0`) — current state is 8 rows total, not 4. The 4 audited-real ones haven't changed.

## Immediate next steps (in order)

1. Re-run `POST /dev/seed_context {"days_before": 3, "days_after": 3}` for the days around each
   of the 4 real anomalies (fix for the hour-scan false-positive storm is on disk, partially
   verified once already this session but that data was deliberately rolled back — see "Note on
   the seed_context hour-scan bug" below). Poll `/dev/jobs/{id}`, check the `is_anomaly`
   distribution actually comes back mostly `false` before declaring it fixed. **Do not run this
   without being asked** — user has twice this session asked NOT to seed context data yet.
2. If still over-firing, consider widening the baseline sample or reviewing
   `rca/bundle.py::_window_anomaly`'s `_SCORE_PRIORS` (currently 3 prior windows).
3. Once clean, verify the `baseline` chat intent live: switch to an anomaly in the dashboard, ask
   "what were the normal values that day", confirm the reply cites real nearby numbers with
   correct is_anomaly framing (not fabricated, not a false "no data" response).
4. Re-run the full backend test suite (`pytest tests/ -q`, expect ~222 passed / 1 skipped — count
   crept up from 209 earlier this session, source not investigated, nothing failing) and a
   TypeScript build (`npx tsc -b`) after any further backend/frontend changes.
5. Watch for the shared-ClickHouse-client concurrency issue (see idempotency section above) if
   running dev-tool actions while a background job is in flight — it has caused both a hard
   error (`/dev/tables` 500) and silent contamination (stray extra bundles) this session.

## Note on the seed_context hour-scan bug (fix on disk, not yet re-verified)

Earlier in this session, `seed_context`'s first implementation called `pipeline.run_detection()`
per day, which scans all 24 hours and reports the worst one — 24 hypothesis tests per day, which
flooded nearly every context day with `is_anomaly=true`. Switched to
`pipeline.run_investigation()` (scores the whole day as ONE point against its same-weekday
baseline), which is saved on disk but has not been re-run since the fix — folded into step 1
above.
