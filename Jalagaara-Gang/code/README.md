# Automated Root-Cause Analyst

**Team:** Jalagaara Gang · **Track:** InMobi — *From alert to answer*

> A metric moved. It tells you **which segment** did it, in seconds.

**ClickHouse is the detective. The LLM is the journalist.** Every figure in a diagnosis is
computed by SQL before the model ever sees it, and a guardrail rejects any number in the prose
that is not in the evidence.

| | |
|---|---|
| **Live demo** | **https://clickathon.kangasys.com** |
| **Langfuse traces** | https://traces.kangasys.com |
| **LibreChat** | https://chat.kangasys.com |
| **Demo video** | https://drive.google.com/file/d/10gCzD86sdgB3gRTdEimLrbeHNSbB3MPM/view |
| **Pitch deck** | [`pitch-deck.pdf`](pitch-deck.pdf) |

## Team

| Name | GitHub |
|---|---|
| Rohan M Rao | [@Rohanmrao](https://github.com/Rohanmrao) |
| Ankith Dinakar | [@Ankith2502](https://github.com/Ankith2502) |
| Shashank | [@ShashankEC37](https://github.com/ShashankEC37) |
| Shreyas Bharadhwaj S P | [@bharadhwaj18](https://github.com/bharadhwaj18) |

## What it does

Ask *"why did fill rate drop on June 23?"* — or ask nothing at all and let it sweep the data
itself — and it answers in three steps:

1. **Detect** — is this window genuinely unusual, or ordinary noise?
2. **Decompose** — `Revenue = Requests × FillRate × eCPM`. Which factor actually moved?
3. **Drill down** — which segment inside that factor is responsible, and what was ruled out?

Two cases matter more than raw accuracy, and the system is built for both.

**A move can be population-wide.** When a metric drops uniformly across every region and every
hour, the correct answer is that **no segment is responsible** — naming one is a false positive.
The drill-down stops rather than inventing a culprit.

**A cause can exist only at an intersection.** Some segments look unremarkable alone and only
reveal themselves in combination. A single-dimension scan cannot see these at all, so the search
descends through combinations rather than ranking one dimension at a time.

## Architecture

```
                 ┌──────────── API ────────────┐
   browser ────▶ │ /investigate   /narrate     │
   LibreChat ──▶ │ /v1/chat/completions        │
                 └──────────────┬──────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │           RCA ENGINE              │
              │  detection → decomposition        │
              │            → drill-down           │
              └─────────────────┬─────────────────┘
                                │  every step is SQL
                 ┌──────────────▼──────────────┐
                 │         CLICKHOUSE          │
                 │  events_full     9M rows    │
                 │  hourly_summary  rollup     │
                 │  investigations  evidence   │
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │   NARRATOR — prose only     │
                 │   guardrail verifies every  │
                 │   number against the bundle │
                 └──────────────┬──────────────┘
                                │
                         Langfuse trace
```

Component-by-component detail: **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**.
The contract everything flows through: [`contracts/evidence_bundle.schema.json`](contracts/evidence_bundle.schema.json).

### Where the analysis runs

**All of it is in ClickHouse.** The drill-down issues a `GROUP BY` per dimension per depth and
ranks segments by a counterfactual: restore this segment's component sums to baseline, and how
much of the total metric gap closes? That fraction is then divided by the segment's share of the
metric's *volume* — its **lift**.

That ratio is the whole idea. A segment that is merely large closes roughly its own share of the
gap and scores lift ≈ 1. A real culprit closes far more than its share and scores much higher.

Ranking on raw contribution instead just picks whichever segment carries the most traffic, because
for a uniform effect contribution share simply equals traffic share. That is how a naive
drill-down turns a single-condition answer into a four-condition one, each extra clause explaining
nothing and each one wrong against an answer key.

The LLM receives a finished Evidence Bundle and writes 3–5 sentences. It never queries, never
computes, and cannot inflate a figure: `narrator/guardrail.py` extracts every number from the
prose and rejects any absent from the bundle — including a genuine number wearing invented units,
since a real figure restated at the wrong magnitude reads as fabricated to anyone checking it.

### Detection

Three interchangeable detectors behind one contract, selected via `config.detection.method`:

- **`robust_z`** — same weekday and hour over trailing weeks; median centre, MAD spread
- **`seasonal_ml`** — a per-(weekday × hour) profile from all history, scored on residuals
- **`isolation_forest`** — scikit-learn over a per-hour feature vector

Thresholds are **calibrated from the data**, not hardcoded (`data/calibration.py`): each metric's
floor derives from its own natural volatility, measured over like-for-like hours. "How big is big"
differs enormously per metric — a ratio built on millions of requests is stable, while one built
on a few thousand clicks swings wildly — so a single shared threshold either drowns in false
positives or misses everything.

Detection runs on **every factor, not just revenue.** A regression inside one factor can be masked
by growth in another, leaving the headline metric flat while something is genuinely broken
underneath. A revenue-only detector never sees it.

### OSS Stack integration — Langfuse

Every investigation is one Langfuse trace, wired at the layer that matters:
`data.client.run_query` emits a span per SQL statement, nesting under the root automatically via
OpenTelemetry context. A judge reads the **actual query sequence**, not a summary of it.

`trace_id` is persisted alongside the bundle because `/investigate` and `/narrate` are separate
HTTP calls — without it the LLM generation opens an orphaned second trace and the SQL steps look
unrelated to the diagnosis. Chat turns group into a Langfuse **session**, so a whole conversation
reads as one thread.

`Query.langfuse_span_id` cross-references both ways: pick any number in a diagnosis, jump to the
span that produced it, and back again.

**LibreChat** is wired through an OpenAI-compatible endpoint. `POST /v1/chat/completions` returns
a valid chat completion with the Evidence Bundle riding alongside in the same payload, so one
endpoint serves both LibreChat and the dashboard with no adapter and no duplicated logic. Config
committed at [`librechat.yaml`](librechat.yaml) (no real keys).

## Tech stack

| Layer | |
|---|---|
| Analytics | **ClickHouse Cloud** — 9M ad events; single datastore for data *and* results |
| Backend | Python 3.11, FastAPI, `clickhouse-connect`, Pydantic, pandas, scikit-learn |
| Narration | AWS Bedrock, authenticated by IAM instance profile — no keys on the host |
| Observability | **Langfuse** v3, self-hosted |
| Chat | **LibreChat**, via the OpenAI-compatible endpoint |
| Dashboard | React 19 + TypeScript + Vite, served by nginx |
| Deployment | Docker Compose on EC2, nginx + Let's Encrypt, secrets in SSM Parameter Store |

**241 tests**, including a regression suite that pins each known anomaly in the provided dataset
to its expected segment — and asserts that a population-wide move localizes to *nothing*, so a
false positive fails the build like any other regression.

## Run it locally

```bash
git clone https://github.com/Rohanmrao/Clickathon2026.git
cd Clickathon2026
cp .env.example .env          # fill CLICKHOUSE_* ; Langfuse dev keys are pre-filled
docker compose up --build
```

Then open **http://localhost:5173**. Full notes, including loading the dataset, in
[`docs/docker.md`](docs/docker.md).

Backend only:

```bash
cd backend
pip install -e ".[dev]"
python -m data.load                    # 9M-row parquet + 3 CSVs into ClickHouse
uvicorn api.main:app --port 8000       # dev console at /dev, API docs at /docs
pytest -q
```

`GET /health` reports whether the engine is live and Langfuse is wired — the fastest way to tell
a half-started stack from a working one.

### API

```
GET  /health                    engine + Langfuse status
POST /investigate               run one — bundle in seconds, no narrative, no LLM in the path
POST /narrate/{id}              add the prose, reattached to the same trace
GET  /bundle/{id}               retrieve stored evidence
GET  /bundles                   investigation history
GET  /series/{id}               hourly actual-vs-expected behind the chart
GET  /trace/{id}                the investigation's steps, in-app
POST /scan                      sweep a blind window — background job
GET  /scan/{job_id}             poll it
GET  /dashboard?since=          incident feed, polled for live updates
POST /v1/chat/completions       OpenAI-compatible; LibreChat points here
GET  /chat/sessions             past conversations with history
```

**`POST /scan` is the unseen-incident path.** Point it at a date range with no prior knowledge of
what happened: it sweeps every metric globally *and* every value of every dimension, folds echoes
of the same underlying event, and localizes the top findings. A full sweep is roughly 50 queries,
so it runs as a background job you poll.

`/investigate` is deliberately LLM-free so it can be called twice and diffed: same input, same
bundle.

```bash
curl -X POST https://clickathon.kangasys.com/api/investigate \
  -H 'Content-Type: application/json' \
  -d '{"metric":"fill_rate","window":{"start":"2026-06-23T00:00:00","end":"2026-06-26T00:00:00"}}'
```

## Deployment

A single EC2 host running Docker Compose behind nginx with Let's Encrypt.

Secrets live in **SSM Parameter Store** as `SecureString` and are read at boot through the
instance's IAM role — never in the repo, never in the image, never an AWS key on the box.
Rotating a credential is: update the parameter, reboot. The IAM policy is scoped to
`/clickathon/*` only, with `kms:Decrypt` gated by `kms:ViaService`.

Fully reproducible from [`deploy/`](deploy/) — bootstrap script, IAM policy, nginx config, README.

## Known limitations

Stated plainly, because trustworthiness is the point.

- **The unseen-incident bundle is not yet included.** Added when the fresh slice is released.
- **A blind sweep returns more findings than distinct events.** One underlying cause surfaces
  through several metrics and several segments at once. Echo-folding groups the obvious
  duplicates, but the ranked list is still longer than the number of real incidents behind it.
- **Langfuse trace links currently require a login.** Programmatic publishing did not take effect
  on this Langfuse version; individual traces can be shared from the UI.

## Repository

```
backend/   rca/        detection, decomposition, drilldown, incidents
           narrator/   narrate, guardrail, tracing
           api/        endpoints, chat, pipeline
           data/       load, store, client, calibration
frontend/  React dashboard
deploy/    EC2 bootstrap, IAM policy, nginx config
docs/      ARCHITECTURE.md, docker.md
InMobi/    problem statement and synthetic dataset (read-only)
```

MIT licensed. All code written during the hackathon period.
