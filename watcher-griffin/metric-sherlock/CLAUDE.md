# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state of this repository

**Read `PROGRESS.md` (repo root) first in any new session** — it is the single source of truth for current state, every gotcha hit so far, and what to do next. Do not assume what exists from this file alone.

This is a 24-hour hackathon build (Click-a-thon 2026, InMobi's "automated root-cause analyst" problem). **All phases are complete and verified.** The ClickHouse foundation is live across **two isolated databases** selected via the dataset registry (`engine/datasets.py`): `ad_events_main` (9M-row `ad_events` + 3 dimension tables + 3 dictionaries + 19 rollups — 12 `hourly_*` + 7 monitoring — plus the monitoring state tables `baselines`/`metric_events`/`incidents`/`sweep_runs`/`sweep_coverage` and the `investigations`/`scan_ticks`/`investigation_chat` app-state tables) and `unseen_data` (the sealed 1.5M-row Jul 6–10 incident drop, same schema — a separate database because its dimension files reuse every id with regenerated attributes). The Investigation Engine (`engine/`) is orchestrated as a **LangGraph `StateGraph`** (`engine/graph.py`) with genuine recursive drill-down; the monitoring layer (`sweep.py`/`bands.py`/`cluster.py`/`impact.py`) covers 10 metrics × 16 scopes × 14 grains with backtested thresholds; Langfuse tracing emits **real-time spans**; there's a scanner service per dataset (`scanner`, `scanner-unseen`), a stateless FastAPI JSON API (per-request `?dataset=` binding), and a **React + Vite UI** behind nginx with a dataset switcher. `./scripts/deploy.sh` brings up all four services with preflight/postflight checks. Operational scripts live in `scripts/`, not the repo root.

**Keys are live.** `GEMINI_API_KEY`, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are all set in `utils/.env` and verified against their providers, so narration and Langfuse tracing both work. Nothing is blocked. Confirm with `scripts/check_keys.py` rather than assuming either way — if narration ever reports "unavailable", run that script first, because an empty or rejected key is by far the most likely cause and the code degrades safely by design. The user pastes their own keys; never ask for secrets in chat.

The `mcp__clickhouse` MCP connection is **read-only**: any DDL/DML needs a direct `clickhouse-connect` client (`scripts/apply_*.py`). (`ingestion/` no longer exists — it was confirmed unused and removed; see PROGRESS.md.)

```
Data/                     (gitignored — the original drop)
  ad_events.parquet   9,000,000 rows · ~5 weeks of events (Jun 1 – Jul 5, 2026)
  advertisers.txt     500 advertisers (CSV format despite .txt extension)
  apps.txt            2,000 apps (CSV format despite .txt extension)
  geo_device.txt      5,000 geo/device profiles (CSV format despite .txt extension)
Unseen-data/              (tracked — the sealed incident drop, loaded into `unseen_data`)
  ad_events.parquet   1,500,000 rows · 5 days (Jul 6 – 10, 2026)
  apps.txt / advertisers.txt / geo_device.txt   same ids, REGENERATED attributes —
                      never co-load these with Data/'s dims (ReplacingMergeTree would
                      silently relabel all 9M historical facts); hence the separate database
Docs/
  README_START_HERE.md   package overview, load steps
  PROBLEM_STATEMENT.md    the actual problem, judging criteria, constraints
  DESIGN_RATIONALE.md     why each contested design choice exists, answered with a
                          measurement rather than an argument -- read before removing
                          the UI, the rollups or LangGraph as "overengineering", and
                          before defending them: it concedes the rollup latency point
  metrics_glossary.md     required metric formulas — must match exactly
  Mindmap/                condensed architecture notes + PRODUCTION_PLAN.md (canonical phase-wise build order)
clickhouse/               schema.sql / dictionaries.sql / rollups.sql / monitoring_rollups.sql /
                          monitoring_state.sql / app_state.sql / load.sql — see "ClickHouse schema" below
PROGRESS.md               live, session-to-session build status — update at the end of every work session
```

All data is synthetic (no real user/advertiser/publisher data).

## The problem being solved

Build a system that: **detects when a key metric moves abnormally, automatically drills down to isolate the responsible segment (device, region, app, advertiser, format), and produces a plain-language, evidence-backed diagnosis in seconds** — ideally also stating what was checked and ruled out. Full detail in `Docs/PROBLEM_STATEMENT.md`.

Hard requirements from the problem statement (do not violate these when implementing):

- **ClickHouse is the primary datastore and must do the real analytical work.** Drill-down/attribution logic runs as ClickHouse queries, not in application code or the LLM. Judges specifically look for analytical depth in ClickHouse.
- **Must meaningfully integrate at least one of:** ClickStack (observability), Langfuse (LLM observability/analytics), or LibreChat (conversational interface). Superficial inclusion doesn't count.
- **The LLM only narrates; it must not compute or invent numbers.** Every number in an explanation must be reproducible directly from ClickHouse. A single fabricated figure is worse than a missed anomaly.
- **Traceability is scored.** A judge must be able to open a trace and see what was checked, in what order, and why something was ruled out.
- Out of scope / not judged: auth, production deployment, alerting integrations (PagerDuty etc.), polished frontends.
- Build for robustness against an **unseen incident dataset** released later in the hackathon, not just the anomalies visible in this sample data — avoid overfitting detection logic to the specific planted anomalies you find while exploring.

## Data model (star schema)

One fact table, three dimensions, joined by key:

```
apps (2,000)                              advertisers (500)
app_id, category, publisher_tier           advertiser_id, vertical, campaign_type
            \                                     /
             \                                   /
              ad_events (9,000,000 rows, fact table)
   event_time, app_id, geo_device_id, advertiser_id, ad_format,
   is_filled, is_impression, is_click, revenue
                        |
                 geo_device (5,000)
      geo_device_id, region, country, device_model, os_version
```

- Join `ad_events` to dimension tables on the shared `*_id` key to slice metrics by app/advertiser/geo/device.
- `advertiser_id` (and thus `vertical`/`campaign_type`) is **empty** on unfilled requests — no ad was served, so there's no advertiser to attribute.
- Funnel per row: `is_filled` → `is_impression` → `is_click`, with `revenue` earned on impressions.

### Dimension values

- `ad_format` (on `ad_events`): `banner, interstitial, native, rewarded, video`
- `category` (on `apps`): `gaming, social, entertainment, news, ecommerce, utility, finance`
- `publisher_tier` (on `apps`): `tier_1, tier_2, tier_3`
- `vertical` (on `advertisers`): `gaming, ecommerce, finance, travel, entertainment, auto, cpg`
- `campaign_type` (on `advertisers`): `CPM, CPC, CPI`
- `region` (on `geo_device`): `NAM, EU, APAC, LATAM, MEA` — **note: `NAM` not `NA`**, since `NA` reads as null in many tools
- `country`, `device_model`, `os_version` also on `geo_device`

## Metric formulas (must match `Docs/metrics_glossary.md` exactly)

Judging compares formulas literally, so use these — all ratio metrics are **sum/sum over the group, never an average of per-row ratios**:

| Metric | Formula |
|---|---|
| Requests | `count(*)` |
| Fills | `sum(is_filled)` |
| Fill rate | `sum(is_filled) / count(*)` |
| Impressions | `sum(is_impression)` |
| Render rate | `sum(is_impression) / sum(is_filled)` |
| Clicks | `sum(is_click)` |
| CTR | `sum(is_click) / sum(is_impression)` |
| Revenue | `sum(revenue)` |
| eCPM | `sum(revenue) / sum(is_impression) * 1000` |
| Revenue per request (RPR) | `sum(revenue) / count(*)` |

**Revenue decomposition identity** (use to localize *why* revenue moved before slicing by dimension):

```
Revenue ≈ Requests × Fill rate × eCPM / 1000
```

Walk this identity first (volume vs. fill vs. price) to find which factor moved, then slice that factor by dimension to find which segment moved it.

### Seasonality caveat

The data has real daily (hour-of-day) and weekly (weekend-lower) seasonality plus a slow growth trend and noise. Compare against a like-for-like baseline (same weekday, trailing weeks) — a flat global average will flag every weekend as anomalous. At least one planted anomaly in the sample data is pure seasonality and is meant to be checked and ruled out, not alarmed on.

## ClickHouse schema (`clickhouse/`)

The 4-table star schema plus a supporting rollup layer live in `clickhouse/`. **Run order matters**: `schema.sql` → `dictionaries.sql` → `rollups.sql` → `load.sql` — dimension tables must be populated before `ad_events`, and the rollup materialized views must exist before the `ad_events` bulk load so they backfill automatically as part of that insert (MVs only fire on rows inserted after creation).

- `schema.sql` — `ad_events` fact table (`MergeTree`, monthly partitions, `ORDER BY (event_time, app_id, geo_device_id, advertiser_id)`, bloom-filter skip indexes on all 4 event-level dimensions, projections on `advertiser_id`/`geo_device_id` for post-localization deep-dives) + the 3 dimension tables (`ReplacingMergeTree`, so re-loading updated dimension rows replaces by id — which is also exactly why the unseen drop, whose dimension files reuse every id with different attributes, must live in its own database and never be co-loaded).
- `dictionaries.sql` — in-memory dictionaries (`apps_dict`, `advertisers_dict`, `geo_device_dict`) over the dimension tables, used by the rollups to enrich `ad_events` via `dictGet(...)`/`dictGetOrDefault(...)` instead of joining. Use `dictGetOrDefault` for advertiser-derived fields — `advertiser_id` is `''` on unfilled requests, which has no dictionary entry.
- `rollups.sql` — one hourly `SummingMergeTree` table + materialized view per candidate slicing dimension (`hourly_overall`, `hourly_by_app`, `hourly_by_advertiser`, `hourly_by_format`, `hourly_by_region`, `hourly_by_country`, `hourly_by_device_model`, `hourly_by_os_version`, `hourly_by_category`, `hourly_by_publisher_tier`, `hourly_by_vertical`, `hourly_by_campaign_type`). This is the table set the anomaly-detection and drill-down engine should query first — each is a small fraction of the 9M-row fact table's size, and every dimension exposes the same query shape (`GROUP BY value` over a hour range, compare window vs. baseline). Fall back to raw `ad_events` (aided by the skip indexes/projections above) only for a deep-dive on one already-localized segment.
- `load.sql` — the 4 `INSERT ... FROM INFILE` statements that load `Data/`.
- `monitoring_rollups.sql` — the 7 monitoring rollups (`minute5_overall`/`minute5_by_region`/`minute5_by_format` for sub-hourly coverage, `hourly_geo_cell`/`hourly_os_family_region`/`hourly_format_region` composite scopes, `reach_hourly`) — see `Docs/ROLLUP_LAYER.md`.
- `monitoring_state.sql` — the detection loop's state: `baselines` (robust bands), `metric_events`, `incidents`, `sweep_runs`, `sweep_coverage`.
- `app_state.sql` — `investigations` / `scan_ticks` / `investigation_chat`.

The same schema exists in both databases (`ad_events_main` and `unseen_data`); no SQL in the repo is database-qualified, so the dataset registry (`engine/datasets.py`) repoints everything by choosing the connection's default database.

## Suggested architecture (from the problem statement)

- Anomaly detection: compare `hourly_overall` against a like-for-like baseline (same weekday, trailing weeks); any approach is allowed (statistical baselines, contribution/decomposition analysis, ML) — simplicity and explainability are valued over sophistication.
- Root-cause drill-down: query the per-dimension rollup tables above (not raw `ad_events`) to rank each dimension's contribution to the deviation, then drop to raw `ad_events` only to deep-dive the localized segment.
- Narration layer: an LLM turns the computed ClickHouse numbers into a plain-language explanation — it must not do arithmetic or introduce numbers not already computed.
- The ClickHouse MCP server (https://github.com/ClickHouse/mcp-clickhouse) is a suggested starting point for wiring an agent/LLM to ClickHouse.

The concrete phase-wise build order (with module names) is `Docs/Mindmap/PRODUCTION_PLAN.md`; treat it as the source of truth for what to build next, and `PROGRESS.md` for what's already done.

## Guardrails

These are hard rules, not suggestions — violating them directly costs points on "explanation trustworthiness" and "traceability":

- The narrator LLM (`engine/narrator.py`) **never computes** — it only restates numbers already present in the evidence bundle it's given. If it needs a number that isn't there, that's a bug in the evidence step, not something the LLM should estimate.
- Every number in a narration must trace back to a specific logged ClickHouse query in the evidence bundle. If it can't be traced, it doesn't ship.
- Query the `hourly_*` rollups first, always. Falling back to raw `ad_events` is allowed only when no rollup covers the needed slice (e.g. a 2D drill-down), and that fallback query must be logged verbatim in the trace — never summarized or paraphrased.
- The seasonality baseline check (same weekday, trailing weeks) always runs before anything is flagged as anomalous — a flat global average will falsely flag every weekend.
- If narration fails (LLM/Langfuse unreachable), return the deterministic evidence with an explicit "narration unavailable" flag. Never degrade to a guessed or templated number.
- Every narrated claim names the `source_step` it came from (e.g. "per the `rank:hourly_by_region:current` query"). Each `SegmentEvidence` carries that field precisely so the prose itself points at a real, runnable query — not just the surrounding JSON.

### Detection invariants (`engine/sweep.py`, `engine/cluster.py`, `engine/impact.py`)

Each of these was a real defect found by replaying all 35 days (`scripts/backtest.py`), not a precaution. Re-breaking any of them is silent and looks like a working system.

- **An evaluation window must lie entirely inside the available data.** A window reaching back before `min(event_time)` is only partly populated, so its sum is short by the missing history and reads as a collapse. Measured at `as_of = 2026-06-02`: **67,360 confirmed breaches, 67,159 of them coarser than 1d, every one `below`** — while 1d and finer produced 201. Guarded and counted as `skipped_incomplete_window`. Test the window's **position, not its length**: disabling coarse grains instead would remove the erosion detection they exist for.
- **A dollar figure must never imply revenue that did not move.** Revenue accrues on *impressions* in this dataset — revenue/impression is 0.00247 for CPC, CPI and CPM alike — so clicks carry none of it and a click shortfall books **$0** revenue exposure (`settings.engagement_carries_revenue` flips this for a click-monetised dataset; verify before flipping). Pricing missing clicks at revenue/click once put a phantom **$39.73** finding at the top of the queue, above a real $24.42/day outage, on a day when revenue/impression was 0.002467 against a 0.002462 median.
- **Incident dollars are additive by construction: same root scope, same metric, same grain, over consecutive windows.** Never sum members (that counts one shortfall once per scope × grain — $1,680 for a $24/day outage) and never use one window for a multi-day event. The current window comes from the incident in hand, *not* read back from `metric_events` — the scanner persists after clustering, so reading it back made the span silently always 1.
- **If you rank on money at all, rank on `impact_usd_per_day`, signed — but the queue no longer does.** The UI orders incidents chronologically and leads each row with how far the metric moved (band-widths, and percent or percentage points by unit); `impact_usd_per_day` is still computed, still decides `gated_by_impact`, and is still shown per row as supporting detail. The original reasoning stands wherever a *magnitude* ranking is used: raw window dollars are not comparable across grains, and ranking on `abs()` lets a gain outrank a loss. Neither failure mode is reintroduced by ordering on time. Movement figures reach the list via a `metric_events` aggregate in `monitor_store.list_incidents` — `argMax(..., abs(deviation_score))` over the root slice, because 618 of 825 incidents have more than one root window and a plain join duplicates the row.
- **`band_k_amber = 3.0` is backtested.** Changing it means re-running `scripts/backtest.py`, not reasoning about it — the scorecard reports detection *and* false positives, and k = 2.0 was measured and rejected (a third of all cells breach).
- **A band may not be narrower than `min_relative_spread` × its own centre.** A nearly-flat trailing history yields a MAD near zero, and dividing by it turns a fraction of a percentage point into a six-sigma verdict — this, not mis-detected movement, was what kept the system raising on 21 of 29 quiet days at k = 3.0. The floor is applied in exactly one place, `bands.py:evaluate()`, because bands are built in SQL (`baselines_job.py`) and read back by `sweep.py`, so a floor at construction would exist twice in two languages and drift. A verdict that clears sigma but fails a floor is `suppressed` — never `skipped`, which would take it out of `entities_evaluated` and quietly shrink reported coverage.
- **`min_relative_spread = 0.02` is adopted over the quieter 0.05 deliberately.** `k × floor` is the smallest relative move that can *ever* breach: 6% at 2%, 15% at 5%. Both planted incidents are ~20% moves, so the replay prices that blindness at exactly zero and will always recommend the higher floor. Raising it means finding evidence about weak incidents, not re-reading this table. `min_relative_move` was measured, found to contribute nothing once the spread floor exists, and ships at 0.0.
- The seasonality baseline check (same weekday, trailing weeks) always runs before anything is flagged — see the bullet above this section.

### Per-number provenance invariants (`engine/provenance.py`)

- **Every number the incident page renders has a `Fact`, and its `kind` is honest.** `measured`
  must carry runnable SQL (or a stated reason it cannot); `derived` must carry a published
  formula plus `inputs` keys that all resolve to other Facts; `config` must carry its settings
  path. A constant rendered like a measurement borrows authority it has not earned — that is why
  `signature_confidence` (a hand-set literal per rule, worth up to 15 of the 100 evidence points)
  is `config` and not `measured`.
- **`build_provenance()` is pure.** No query, no arithmetic on data, every `value` copied from the
  incident — the same contract as `engine/causal_chain.py`. It runs inline on every
  `GET /api/incidents/{id}`, so it must stay free.
- **The SQL is reconstructed from the incident's own scope/grain/window, and pinned.**
  `sweep.window_sql()` / `sweep.band_lookup_sql()` are the single definitions; passing no
  narrowing arguments must stay **byte-identical** to what the sweep sends, and a test diffs it
  against a live `Trace`. Never add a second SQL expression of something the engine already
  computes unless the verification path checks it — the one exception, `metric_value_sql()`, is
  read from `METRIC_DEFS` and proves itself on every run.
- **A band query must filter the seasonal cell the verdict actually used.** `baselines` holds one
  row per ladder rung, so an unfiltered read returns an arbitrary cell: `sample_count` verified as
  662 (pooled `all`) against a displayed 8 (strict `dow|hod`). Reproducing the wrong row is worse
  than reproducing nothing.
- **Divide in `Float64`, not `Decimal`.** `revenue` is `Decimal64(6)`, so a metric expressed as
  `sum(revenue)/sum(impressions)*1000` truncates to 6 places and contradicts the figure it is
  supposed to prove (5.600000 vs 5.6003203670300366).
- **Direction-filter a breach count, never its denominator.** `uniformity.spread_profile` filters
  verdicts by direction, so "1 of 5 siblings moved" is only true within one direction — pooling an
  above-band and a below-band breach destroys the seasonality disproof. `entities_evaluated` is
  deliberately NOT direction-filtered: how many entities were looked at does not depend on which
  way any went.
- **The verify route accepts a fact KEY and never SQL.** `ch_client.query()` runs arbitrary
  statements and `command()` writes, as user `default`. Verification goes through
  `query_readonly()` only: comment-aware statement allowlist, `readonly = 2`, row caps, short
  timeout. Do not add a general query endpoint.
- **`evidence_score_sql()` is a licensed exception, and its licence is one test.** It expresses
  `engine/confidence.py`'s six-component arithmetic a second time, in SQL, because a single
  runnable query for the confidence figure was asked for. That duplication is only safe while
  `test_the_single_confidence_query_returns_the_displayed_score` asserts the query equals the
  persisted score on real incidents in both databases. **Delete that test and delete the function
  with it** — an unchecked second copy of a scoring formula is how two different confidences end up
  on screen, each looking authoritative. Every weight and threshold is interpolated from
  `config.py`/`confidence.py`, never typed, so a threshold change cannot leave the published query
  describing the previous configuration.
- **`source_steps` must come from coverage, not only from breaches.** A ruled-out dimension has
  `breached = 0`, so recording the step inside the verdict loop left the system's strongest claim
  uncited — and `SpreadBars` guards on a non-empty list, so it failed silently.

### Observability invariants (`engine/tracing.py`)

- **Every `@contextmanager` in `tracing.py` yields exactly once on every path.** Swallowing a tracing error must never swallow the *caller's* exception. A double-yield here previously turned every real investigation error into `RuntimeError: generator didn't stop after throw()` the moment Langfuse keys were configured.
- **Spans are created in real time, never replayed after the fact.** `ch_client.query()` opens the span around the actual execution and `narrator.py` around the actual LLM call, so durations and parallel overlap in the Langfuse timeline are true. Do not reintroduce post-hoc span replay in `pipeline.py` — it double-logs every query.
- **Tracing is gated on `_tracing_active()`** (a Langfuse client exists *and* an OTel span is recording), so the scanner's routine 30s ticks never spam Langfuse with orphan root spans.
- **OTel context must be propagated into thread pools** via `tracing.in_parent_context()`. `ThreadPoolExecutor` workers start with an empty context, so parallel query spans would otherwise orphan themselves out of the investigation trace.
- **Langfuse buffers spans; `flush()` must run before any process exits.** It is `atexit`-registered on client creation, plus explicit on API shutdown and each scanner tick. Without it, short-lived runs export nothing — fatal under "no trace, no credit."
- **A follow-up chat turn needs its OWN root span (`tracing.traced_chat`), not just a generation span.** `_tracing_active()` requires a live recording span, and a chat question arrives on a later HTTP request long after the investigation's span closed — so a `traced_generation` alone silently no-ops there. This is the reverse of the scanner gate: routine ticks must not create orphan roots, a user-initiated question must. Chat was the one interactive LLM surface in the system and produced no trace at all until this existed.

## Production & scalability principles

Prioritize these over feature breadth — the system must hold up against an unseen dataset of unknown size and shape released later in the hackathon, not just today's 9M-row sample:

1. **Data-volume agnostic.** No code assumes today's date range, dimension cardinalities, or row count. Baseline windows, dimension lists, and anomaly thresholds are config (`engine/config.py`), not literals.
2. **The rollup layer is what scales, not raw-table cleverness.** Any new slicing dimension gets its own narrow `hourly_by_*` rollup — never a wider composite-key rollup whose cardinality could approach the fact table's.
3. **Bounded, resilient ClickHouse access.** All queries go through one client wrapper (`engine/ch_client.py`) with a query timeout, a result-size cap, and retry-with-backoff — never a bare unguarded client call scattered across modules.
4. **Concurrency where independent.** Steps that query multiple independent rollups (e.g. ranking region + device + format + advertiser) run concurrently, not as serial round-trips — this is what keeps diagnosis in seconds as the dimension list grows.
5. **Stateless, horizontally replicable service.** The API holds no in-process state between requests; evidence/trace state lives in ClickHouse + Langfuse.
6. **Config and secrets externalized.** One settings module reads env vars; nothing hardcoded, nothing new checked into git.
7. **Fails safe, never fails silent-wrong.** See Guardrails above.
8. **Tested, not just demoed.** Unit tests for the decomposition/contribution math; one integration test against a known window with exact-number assertions.
9. **Containerized and one-command runnable.** `Dockerfile` + `docker-compose.yml` so the tested artifact is exactly what runs for the unseen incident.
