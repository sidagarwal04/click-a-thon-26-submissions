# Backend

Python backend for the automated RCA analyst: **data** (ClickHouse), **RCA**, **narrator**, **API**.

> Run every command from **`backend/`**. Running from the repo root lets the root `config/` folder
> shadow `backend/config.py`, breaking imports.

> **Just want to run things?** After the one-time [Setup](#setup-once), use the
> [`oneclick/`](oneclick/README.md) launchers — no venv activation, no long commands:
> `.\backend\oneclick\detect.ps1`, `.\backend\oneclick\compare.ps1`, `.\backend\oneclick\test.ps1`.

## Coming from .NET? Quick mental model
| Python thing | .NET equivalent |
|---|---|
| `python -m venv .venv` | a per-project package sandbox (like an isolated `packages/` folder) |
| `.venv\Scripts\Activate.ps1` | "use this project's sandbox in my shell" — do it once per terminal |
| `python -m pip install -e ".[dev]"` | `dotnet restore` + reference the local project (editable, so code changes need no reinstall) |
| `pytest` | `dotnet test` |
| `pyproject.toml` | `.csproj` (deps + project metadata) |
| `config.json` / `.env` | `appsettings.json` / user-secrets |

Rule of thumb: **activate the venv once per terminal**, then every `python ...` / `pytest` command uses this project's packages.

## Prerequisites
- Python **3.11+** (`python --version`)
- ClickHouse Cloud credentials (see [Environment](#environment))
- No `uv` required — plain `venv` + `pip` is fine.

## Setup (once)
PowerShell 5.1 has no `&&`, so run these as separate lines:
```bash
python -m venv .venv                 # create the virtualenv (once ever)
.venv\Scripts\Activate.ps1           # activate it — prompt should show (.venv); once PER TERMINAL
python -m pip install -e ".[dev]"    # install the package + dev deps (pytest, ruff)
```
If activation is blocked by execution policy, allow it for this shell only:
```bash
Set-ExecutionPolicy -Scope Process -Bypass
```
Every command below assumes the venv is active (you see `(.venv)` in the prompt).

## Environment
Table names and thresholds live in `config.json` (no magic strings in code). **Secrets** live in a
`.env` file at the **repo root** (one level up from `backend/`):
```bash
cp ../.env.example ../.env           # then fill in the values
```
Required keys: `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`,
`CLICKHOUSE_DATABASE`.

## Run the tests (no database needed)
The suite covers metric formulas, the robust stats, and the baseline engine against fixed inputs:
```bash
pytest -q                            # all tests
pytest tests/test_baseline.py -v     # just the baseline engine, verbose
```

## Load the data / build the tables
Lane A loads the four source files and builds the derived tables. `hourly_summary` is the hourly
rollup the RCA engine reads (`config.clickhouse.hourly_table`) — it stores raw sums, and ratios are
computed at read time (sum/sum) by the shared `metrics` lib:
```bash
python -m data.load                  # ad_events + *_dim -> events_full -> hourly_summary, then sanity-checks
```
> DDL lives in [`data/schema.sql`](data/schema.sql); the loader is [`data/load.py`](data/load.py).

## Detect an anomaly (JAL-27) — the thing to demo
`detect(metric, window)` decides whether a metric moved abnormally at a given hour and returns an
`Anomaly` plus the exact SQL queries behind every number. There are **two interchangeable detectors**,
chosen by one config key — no code change to switch:

| `config.detection.method` | detector | idea |
|---|---|---|
| `"robust_z"` (default) | deterministic | same weekday+hour, median/MAD over the trailing 3 weeks |
| `"seasonal_ml"` | unsupervised ML | seasonal profile over ALL history, flags residual outliers |

**Run the default (robust-z) detector:**
```bash
python -c "from datetime import datetime; from models import Window; from rca.detection import detect; a,q=detect('revenue', Window(start=datetime(2026,7,4,10), end=datetime(2026,7,4,11))); print(a.model_dump()); print('queries:', [x['id'] for x in q])"
```
Example output (annotated):
```
{'detected': True,        # did we flag it?
 'observed': 22.99,       # actual value this hour
 'expected': 21.66,       # what the baseline expected
 'abs_delta': 1.33,       # observed - expected
 'pct_delta': 0.061,      # +6.1%
 'score': 7.07,           # robust z-score (how many robust std-devs out)
 'direction': 'spike'}    # 'spike' (up) or 'drop' (down)
queries: ['q_observed', 'q_baseline']   # SQL behind the numbers (for traceability)
```

**Switch to the ML detector** — edit [`config.json`](config.json) → `"detection": { "method": "seasonal_ml" }`, or override inline for a quick A/B:
```bash
python -c "from datetime import datetime; from config import config; from models import Window; from rca.detection import detect; config()['detection']['method']='seasonal_ml'; a,q=detect('revenue', Window(start=datetime(2026,7,4,10), end=datetime(2026,7,4,11))); print(a.model_dump())"
```
Same hour, the two detectors can disagree — e.g. robust-z scores 7.07 (its 3-point baseline is noise-starved) while the seasonal model scores ~2.2 ("within normal"). That contrast is a good demo beat.

## Run a baseline query (live, against ClickHouse)
`score()` = one metric on one segment; `scan()` = every value of a dimension, ranked by |robust_z|:
```bash
# global revenue baseline for one hour (same weekday + hour over the trailing 3 weeks)
python -c "from datetime import datetime; from rca import baseline; s=baseline.score('revenue', datetime(2026,7,4,10)).stats[0]; print('observed=%.2f expected=%.2f z=%.2f detected=%s' % (s.observed, s.expected, s.robust_z, s.detected))"

# top-5 countries by anomaly strength for revenue at that hour
python -c "from datetime import datetime; from rca import baseline; r=baseline.scan('revenue', datetime(2026,7,4,10), 'country'); [print(s.segment, round(s.robust_z,2), s.detected) for s in r.stats[:5]]"
```

## Run the API
```bash
uvicorn api.main:app --reload --port 8000
# POST http://localhost:8000/investigate  -> Evidence Bundle
```

## Dev console (admin + benchmarker)
Start the API (`.\backend\oneclick\api.ps1`) and open **http://localhost:8000/dev** — a local dev
dashboard to manage tables/data and benchmark detection:
- **Tables & Data** — list/preview tables, drop (typed confirm), run the full data load.
- **Runs** — investigation history + bundle viewer (empty until the pipeline is wired).
- **Benchmarker** — run `detect()` with live config overrides, compare `robust_z` vs `seasonal_ml`,
  and run the ground-truth harness (detection-only for now).

Local-dev only: it's gated by env `ENABLE_DEV_DASHBOARD` (default on) — set it to `0` on any deploy.
For a big data load, prefer the CLI: `.\backend\oneclick\load.ps1` (no `--reload` to interrupt it).

## Inspect the database (ad-hoc)
```bash
python -c "from data.client import run_query; print([r[0] for r in run_query('SHOW TABLES')['rows']])"
```

## Layout
- `config.py` / `config.json` — all thresholds, dimensions, table names. No magic strings in code.
- `metrics.py` — the ONE place metric formulas live (SQL builders + Python compute).
- `models.py` — pydantic mirror of `contracts/evidence_bundle.schema.json`.
- `data/` — Lane A: `schema.sql`, `load.py`, `client.run_query`, `metrics.sql`.
- `rca/` — Lane B: `baseline.py`, `detection.py` (dispatcher) + `detectors/` (`robust_z`, `seasonal_ml`), `decomposition.py`, `drilldown.py`, `bundle.py`.
- `narrator/` — Lane C: `narrate.py`, `guardrail.py`, `tracing.py`.
- `api/` — Lane C: `main.py`.

Stubs raise `NotImplementedError` and point to the owning lane's prompt in `prompts/`.

## Live table names
The live ClickHouse and this repo agree on these names (config-driven):
`ad_events`, `apps_dim`, `advertisers_dim`, `geo_device_dim`, `events_full` (enriched),
`hourly_summary` (rollup).
