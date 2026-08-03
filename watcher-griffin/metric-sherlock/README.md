# Watcher Griffin

> **⚠️ TODO before submitting** — two items remain, both mandatory:
>
> 1. **Hosted demo URL** (§ Hosted Demo)
> 2. **Demo video URL** (§ Demo Video)
>
> Delete this block once done.

## Track

**InMobi** — *"From alert to answer": an automated root-cause analyst for ad-tech metrics.*

## Project

**Metric Sherlock** — detects an abnormal metric move, isolates the segment responsible, and
explains it in plain language with a runnable query behind every number.

## Team Members

- Ashish Vaghasiya ([@asysvaghasiya](https://github.com/asysvaghasiya))
- Mohit Jadav ([@Mohitjadav20](https://github.com/Mohitjadav20))
- Karan Kumar Singh ([@KaranKumar0402](https://github.com/KaranKumar0402))
- Sonu Kumar Pandit ([@sonu1680](https://github.com/sonu1680))

## Why this one is different

Five claims, each checkable in the repo rather than taken on trust:

- **ClickHouse does the analysis; the LLM only narrates — and it physically cannot do otherwise.**
  It receives a finished JSON bundle, issues zero queries, and an empty response from it is
  reported as *unavailable* rather than as an answer. The mechanism sentence a reader sees first
  comes from a deterministic rule table, so the diagnosis survives the model being down.
- **Every number carries a runnable query, and a button that re-runs it.** Not one trace at the
  foot of the page — per figure. 584 measured facts across 21 real incidents reproduce their
  displayed value exactly, and confidence ships as a single self-contained query you can paste
  into ClickHouse.
- **The thresholds are measured, not chosen.** All 35 days replayed at k ∈ {2, 2.5, 3};
  `band_k_amber = 3.0` comes from that table. The scorecard is committed and baked into the image,
  so the calibration shown on the operations home is the calibration of the code being run.
- **The replay found five defects that a single-moment sweep never could** — every one failing in
  the *reassuring* direction, including a **$39.73 figure the data does not contain** sitting at
  the top of the queue and a home screen reporting "0 suppressed" while 791 were.
- **It states what it cannot do.** Grains without enough history report `insufficient` with the
  sample count rather than rendering green; there is an Honest Limitations section below, and
  `Docs/DESIGN_RATIONALE.md` concedes the rollup-latency point instead of overselling it.

## What it does

An ad-tech metric moves. Normally someone opens a dashboard and starts slicing — by region, by
device, by app — until something looks wrong. This does that automatically and then argues its
case.

1. **Detects** a move against a *like-for-like* seasonal baseline (same weekday, same hour,
   trailing 4 weeks) — never a flat average, which would flag every weekend. Coverage is
   **10 metrics × 16 scopes × 14 time grains**, on a 30-second tick; each grain is re-evaluated
   when its own window advances, so a 3-week band is not recomputed every half minute.
2. **Localises** it by walking the exact revenue identity
   `Revenue = Requests × Fill rate × Show rate × eCPM/1000` to find which factor moved, then
   ranking **12 dimensions** by share-of-deviation — all queried concurrently, and recursively:
   it keeps descending into whichever segment still concentrates the deviation, carrying every
   prior filter forward, to a depth of 3.
3. **Rules out** what did *not* explain it, with the numbers that clear it — "category 7/7
   spread, ad_format 5/5 spread, app 33/170 concentrated". The seasonality check always runs,
   because one planted anomaly in the sample data *is* pure seasonality and is meant to be
   caught and dismissed, not alarmed on.
4. **Explains** it. The LLM receives a finished evidence bundle; it cannot query and cannot
   compute. Every claim cites the query step it came from, and if the model is unavailable the
   diagnosis is still complete — the mechanism sentence is produced by a deterministic rule
   table, not by the model.

**Every number on screen carries the query that produces it, and a button that re-runs it.**
Each figure is classed `measured` (one query returns it), `derived` (published formula over
inputs that are each themselves verifiable) or `config` (a constant, with its settings path — a
threshold is never dressed up as a measurement). The confidence score also ships as a single
self-contained query you can paste into ClickHouse and run. 584 measured facts across 21 real
incidents reproduce their displayed value exactly.

It also runs against **two independent datasets** — the training set and the unseen incident
drop — switchable from the header, with the whole console following.

## Hosted Demo

**TODO** — mandatory. Must show the operations screen, an incident diagnosis, the ruled-out
evidence, and a number being verified against its query.

## Demo Video

**TODO** — mandatory, 2–3 minutes.

## Architecture

```
                          ┌─────────────────────────────────────────────┐
ClickHouse Cloud          │ ad_events  9M rows  +  3 dimension tables   │
(primary datastore,       │ 3 dictionaries (dictGet, no joins)          │
 does ALL the analysis)   │ 19 rollups: 15 hourly_* · 3 minute5_* ·     │
                          │             reach_hourly                    │
                          │ state: baselines (1.17M bands) ·            │
                          │        metric_events · incidents ·          │
                          │        sweep_runs · sweep_coverage          │
                          └──────────────────┬──────────────────────────┘
                                             │  every query is logged verbatim
   ┌─────────────────────────────────────────┴──────────────────────────────┐
   │ engine/  (32 modules)                                                   │
   │                                                                         │
   │  DETECT    grains · scopes · bands (median ± k·MAD) · baselines_job      │
   │            sweep  ── 364 queries, 133k band evaluations, 7.6s           │
   │                                                                         │
   │  CLUSTER   cluster (atom-based union-find) · signature (S1–S11 rule      │
   │            table) · uniformity · impact · history · confidence          │
   │                                                                         │
   │  DIAGNOSE  LangGraph StateGraph:                                        │
   │            baseline → decompose → rank → drilldown ⟲ → rule_out         │
   │                                        (recursive, depth ≤ 3)           │
   │                     → evidence → narrate                                │
   │                                                                         │
   │  PROVE     provenance — per-number SQL, reconstructed from the           │
   │            incident's own scope/grain/window, then re-runnable           │
   └───────┬──────────────────────────────────┬──────────────────────────────┘
           │                                  │
   ┌───────┴────────┐              ┌──────────┴──────────┐
   │ api/  :8088    │              │ scanner  ×2         │  one process per dataset
   │ FastAPI        │              │ sweep → cluster →   │  (a scanner is bound to
   │ 21 routes      │              │ gate → investigate  │   one dataset's clock)
   │ stateless      │              │ → persist, every    │
   └───────┬────────┘              │ 30s                 │
           │                       └─────────────────────┘
   ┌───────┴────────┐
   │ ui/   :80      │  React 19 + Vite behind nginx
   │ React + TS     │  ops home · incident detail · dataset switcher
   └────────────────┘
                                  │
                          Langfuse (LLM observability)
                          real-time spans — true durations and
                          true parallel overlap, never replayed
```

**The load-bearing design choice:** ClickHouse does the analysis, not the application and not
the model. Detection, decomposition, ranking and drill-down are all SQL. The LLM issues zero
queries — it receives finished numbers and turns them into prose.

**Every rollup query runs first, raw `ad_events` only as a logged fallback.** Benchmarked
honestly: the rollups buy **6× to 10,714× fewer rows scanned**, and a median 1.5× on wall clock
— see `Docs/DESIGN_RATIONALE.md`, which concedes the latency point rather than overselling it.

## How we built it

**Stack** — Python 3.12 · ClickHouse Cloud · LangGraph · Langfuse · FastAPI · React 19 + Vite 8
+ TypeScript · Docker Compose (4 services) · Gemini (`google-genai`), with Anthropic, OpenAI and
Grok adapters behind one interface selected by `LLM_PROVIDER`.

Things worth calling out:

- **The thresholds are backtested, not chosen.** All 35 days were replayed at k ∈ {2, 2.5, 3};
  `band_k_amber = 3.0` comes from that table, and k = 2.0 was measured and rejected (a third of
  every evaluated cell breached). The scorecard is committed and baked into the image, so the
  calibration a judge reads on the operations home is the calibration of the code they are
  running.
- **The replay found five defects a single-moment sweep never could**, every one failing in the
  reassuring direction: windows reaching before the data start (67,360 phantom breaches, all
  "below"), clustering that could not finish on the busiest day, a dollar span that silently
  measured one window, a **$39.73 revenue figure the data does not contain** sitting at the top
  of the queue, and a home screen reporting "0 suppressed" while 791 incidents were.
- **A robust band answers "is this improbable?", which is not the question.** A slice with a
  nearly-flat history has a MAD near zero, so a fraction of a percentage point became a
  six-sigma verdict. A noise floor at 2% of the band centre took quiet days with a false raise
  from 21-of-29 to 16-of-29 — and 2% was adopted over the *quieter* 5%, because `k × floor` is
  the smallest move that can ever breach (6% vs 15%) and this replay cannot price that
  blindness.
- **Latency was measured before anything was changed**, and ClickHouse was innocent: queries run
  15–90 ms. The narrator was spending 21.9 s per call on internal reasoning it is *forbidden* to
  use, one chat prompt had grown to 975,728 characters, and TLS handshakes cost more than the
  analysis (~33 connections/investigation at 125–266 ms each). Now 2.5 s per diagnosis.
- **Per-number provenance is verified, not asserted.** Re-running each query and comparing
  caught two defects that both produced entirely plausible SQL — a `Decimal64(6)` truncation
  (eCPM 5.600000 vs 5.6003203670300366) and a band read returning one row per seasonal cell, so
  `sample_count` "verified" as 662 against a displayed 8. Neither raised.
- **The verify endpoint takes a fact key, never SQL.** The engine's own client runs arbitrary
  statements and can write, so an endpoint accepting a query string would be a SQL-execution
  surface. The server re-derives the statement itself and runs it under a statement allowlist,
  `readonly = 2`, row caps and a short timeout.

**143 tests** — unit maths plus live-ClickHouse integration. The suite reports whether the
integration tests actually ran (`clickhouse: reachable — integration tests ran`), because a green
suite that silently skipped every database test is the kind of green that costs trust.

## How to run it

### Prerequisites

Docker + the compose v2 plugin. Nothing else — ClickHouse is external (ClickHouse Cloud) and all
four services build from the two Dockerfiles in this repo. `scripts/deploy.sh` installs Docker
itself on a bare Amazon Linux / Ubuntu box.

### 1. Credentials

```bash
cp utils/.env.example utils/.env
```

Fill in:

```
CLICKHOUSE_HOST=<your-instance>.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=...
CLICKHOUSE_DATABASE=ad_events_main         # primary dataset
CLICKHOUSE_UNSEEN_DATABASE=unseen_data     # second dataset, for the header switcher
CLICKHOUSE_SECURE=true

GEMINI_API_KEY=...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com   # region matters — see below
```

⚠️ **Langfuse Cloud is region-specific** (`cloud` = EU, `us.cloud`, `jp.cloud`). The wrong host
returns `401 Invalid credentials` with perfectly valid keys — a failure that looks like a bad key
and isn't. `scripts/check_keys.py` detects it and says so.

Missing LLM/tracing keys are **not** fatal: narration reports `unavailable` and tracing no-ops,
by design. The deterministic diagnosis is always returned.

```bash
.venv/Scripts/python.exe scripts/check_keys.py    # reports set/empty per key, never prints secrets
```

### 2. Load the data (first run only)

Run in this order — dimension tables must exist before the fact table, and the rollup
materialized views must exist before the bulk load so they backfill as part of it.

```bash
python scripts/apply_and_backfill.py    # schema → dictionaries → rollups → load
python scripts/apply_app_state.py       # investigations / scan_ticks / investigation_chat
python scripts/apply_monitoring.py all  # monitoring rollups + state, then reconcile
```

`apply_monitoring.py all` runs `ddl → columns → backfill → reconcile` and **exits non-zero on any
mismatch**. The `columns` step matters on an existing database: `CREATE TABLE IF NOT EXISTS`
cannot add a column, so it reconciles columns with `ALTER TABLE ADD COLUMN IF NOT EXISTS` and
reports drift instead of skipping silently.

Then build the bands and take a first sweep:

```bash
python -m engine.baselines_job --rebuild                 # ~1.17M bands
python -m engine.scanner --once --ignore-cadence         # sweep → cluster → diagnose → persist
```

For the second dataset, add `--dataset unseen` to both. (⚠️ `--rebuild` issues an unqualified
`TRUNCATE TABLE baselines`; passing `--dataset` lets the job assert it is on the database you
asked for and refuse otherwise.)

### 3. Start everything

```bash
./scripts/deploy.sh          # Linux/macOS
scripts\deploy.ps1           # Windows
```

Both run **preflight** checks (Docker up, credentials present, ports free) and refuse to start on
a real problem, then **postflight** checks (API healthy, UI serving, nginx→API proxy working, all
four containers actually *running* — not merely "started", since a crash-looping container still
counts as started to compose).

| | |
|---|---|
| **UI** | http://127.0.0.1:8089 |
| **API** | http://127.0.0.1:8088 |
| Tests | `.venv/Scripts/python.exe -m pytest tests/` — 143 |
| Logs · stop | `docker compose logs -f` · `docker compose down` |

### 4. What to look at

- **`/`** — the operations home. Zero form inputs by design: "now" is the data's own clock
  (`max(event_time)`), which is what removes the date picker rather than hiding it.
- **`/incidents/:id`** — one incident as an argument. Verdict → deterministic mechanism (*above*
  the LLM narration) → evidence score with its full breakdown → proof charts → what was ruled
  out, with numbers → recurrence history → member breaches → SQL. Expand any figure's `SQL` or
  `ƒ` badge to read the query and press **run it and check**.
- **The dataset switcher**, top right — moves the whole console between the two databases.
- **The Langfuse trace link** on any investigated incident: one parent span, children in
  execution order, real SQL, non-zero overlapping durations on the parallel `rank:*` spans.
  Every trace is published, so the link opens without a Langfuse login — no account needed to
  audit what was checked.

## Data ingestion (`ingestion/`)

A standalone module that seeds a raw data drop into ClickHouse, in four steps:

```
1 · select the seed file     point it at a file or a folder — each file's entity
                             (apps / advertisers / geo_device / ad_events) is
                             auto-detected from its name or columns
        │
2 · apply transformations    headers normalized (AppId → app_id), values typed
                             (dates, 0/1 flags, numbers), unknown columns dropped
        │
3 · find & remove bad data   missing values, broken funnel rows, invalid
                             region/format values → rejected to
                             <entity>.rejected.jsonl with the reason; nothing
                             is ever silently defaulted to 0
        │
4 · seed into the database   clean rows batch-inserted into ClickHouse,
                             dimensions first, then ad_events
```

```bash
python -m ingestion.cli load --db unseen_v2 Unseen-data/
```

One command bootstraps the schema in a fresh database and loads everything in the right order.
It refuses a non-empty table without `--truncate` and the engine's live database without
`--force`. Full detail: [`ingestion/README.md`](ingestion/README.md).

## Against the judging criteria

| Criterion | How |
|---|---|
| **Analytical depth in ClickHouse** | All detection, decomposition, ranking and drill-down are SQL. 19 purpose-built rollups + dictionaries, bloom-filter skip indexes and projections for the raw fallback. 1.17M robust bands over 16 scopes × 14 grains × 10 metrics. The LLM runs zero queries. |
| **Explanation trustworthiness** | The narrator physically cannot compute — it receives finished JSON. Every figure carries the query that produces it, re-runnable from the page. Metric formulas match `Docs/metrics_glossary.md` literally (sum/sum, never an average of ratios). An empty LLM response is reported as *unavailable*, never as an answer. |
| **Traceability** | One Langfuse trace per investigation, spans opened **in real time** so durations and parallel overlap are true rather than replayed, and every trace is **public** — a judge opens the link without an account. Plus per-number provenance on every incident, not only the few that were fully investigated. |
| **Detection accuracy** | Backtested over a 35-day replay: both planted incidents caught on the earliest sweep that could see them. Windows reaching before the data start are skipped and counted. Click-based metrics book $0 revenue exposure, because revenue accrues on impressions here — measured, not assumed. |
| **Built for the unseen incident** | Nothing hardcodes dates, cardinalities or row counts. All windows, thresholds, grains, scopes and dimensions are config. Every apply script is idempotent and re-runnable, and the whole console switches datasets from a dropdown. |

## Repo layout

```
engine/      32 modules — graph.py (LangGraph) · sweep · bands · cluster · signature
             impact · confidence · history · provenance · narrator · chat · ch_client
             tracing · datasets · monitor_store · llm/<provider>_provider.py
api/         main.py — 21-route stateless JSON API
ui/          React 19 + Vite + TypeScript, own Dockerfile + nginx.conf
clickhouse/  schema · dictionaries · rollups · monitoring_rollups · monitoring_state
             app_state · load   (SQL only)
ingestion/   standalone seed-the-database module: detect entity → transform →
             validate/reject → batch-insert (see "Data ingestion" above)
scripts/     deploy.sh · deploy.ps1 · check_keys.py · apply_*.py · backtest.py
             bench_rollups.py · bench_latency.py
tests/       143 tests (pure-maths unit + live-ClickHouse integration)
Docs/        PROBLEM_STATEMENT · metrics_glossary · DESIGN_RATIONALE · BACKTEST_SCORECARD
PROGRESS.md  authoritative build state, every gotcha hit, next steps
CLAUDE.md    the invariants — read before changing detection, tracing or provenance
```

## Honest limitations

Stated here rather than discovered by a reviewer:

- The **unseen dataset holds 5 days**, which is less history than the 4-week baseline wants. `1d`
  and coarser grains correctly report `insufficient` (n=5 against a required 8) and the coarse
  windows are skipped as incomplete; detection there runs at `1h`–`15h` and `5m`/`15m`. The
  system says so on screen rather than rendering green.
- **The evidence score is an index, never a probability**, and 15 of its 100 points come from a
  hand-set rule-table confidence rather than from a query. It is labelled as config for that
  reason.
- **Coarse-grain bands are optimistic**: 2w/3w observations are overlapping rolling windows, so
  the sample count is real but the independence is not.
- **`ops_summary().queries` covers only about half the home page** — every `monitor_store` read
  goes through a discard sink, so the queue, counts and owner chips contribute no queries to
  "How this page was computed". Real, known, and out of scope for this pass.
- Two concurrent unrelated incidents sharing a geography can still merge, since clustering is
  transitive over shared (dimension, value) atoms. Mitigated for the OS-family case that
  actually occurred.

## License

MIT — see [LICENSE](LICENSE). All data is synthetic; no real advertiser, publisher or user data.
