# Design — `/dev` admin & benchmarker dashboard

**Date:** 2026-08-01 · **Lane:** B/dev-tooling · **Author:** Rohan M Rao

## Problem

The team needs an internal dev dashboard to run every data/table action (load, drop, preview,
check runs) and to benchmark detection (switch configs, compare detectors) — an analytics/ops panel
for devs, not the judge-facing React dashboard. It should be available whenever the backend is on.

## Decisions (locked)

1. **Served by the existing FastAPI** as one self-contained HTML page at `GET /dev`, plus `/dev/*`
   JSON endpoints. No build step, no extra process.
2. **Destructive ops execute, behind a typed confirm** (server-enforced).
3. **Benchmarker = live playground now + stubbed ground-truth harness.**
4. **Config overrides are in-memory per-run only** — `config.json` is never written.
5. **Gating:** `/dev` mounts only when env `ENABLE_DEV_DASHBOARD` is truthy (**default on**). A deploy
   can disable it. UI shows a "LOCAL DEV ONLY" banner.

## Non-goals

- No change to the React judge dashboard (`frontend/`).
- Not implementing `build_bundle` — the Runs tab reads whatever `data.store` has (empty until the
  pipeline lands).
- Harness **localization** scoring is deferred to JAL-77 (drill-down). Harness ships detection-only.

## Architecture

`backend/api/dev.py` — a FastAPI `APIRouter`, mounted in `api/main.py` only when enabled:

```python
if env_flag("ENABLE_DEV_DASHBOARD", default=True):
    app.include_router(dev.router)
```

`GET /dev` serves `backend/api/dev_dashboard.html` (inline CSS + vanilla JS, no framework). All data
flows through `/dev/*` endpoints below. Reuses `data.client.run_query`, `data.store`, `data.load`,
`rca.detection.detect`, `config`.

## Endpoints

**Tables & data**
| Method | Path | Notes |
|---|---|---|
| GET | `/dev/tables` | `[{name, rows}]` |
| GET | `/dev/table/{name}?limit=20` | preview rows; `name` validated against the live table list (no injection) |
| POST | `/dev/table/{name}/drop` | body `{confirm}` must equal `name`; server re-checks, then `DROP TABLE` |
| POST | `/dev/load` | body `{confirm:"LOAD"}`; starts a **background job**, returns `{job_id}` |
| GET | `/dev/jobs/{job_id}` | `{status: running|done|error, log, started, finished}` |

**Runs**
| GET | `/dev/runs?limit=50` | `data.store.list_investigations` |
| GET | `/dev/runs/{id}` | full bundle via `data.store.load_bundle` (404 if missing) |

**Benchmarker**
| POST | `/dev/detect` | body `{metric, at, method?, overrides?}` → `{anomaly, queries}`. Overrides applied to a **snapshot** of `config.detection`, restored in `finally`. |
| POST | `/dev/compare` | body `{metric, at}` → both detectors' anomalies |
| GET | `/dev/benchmark/cases` | the ground-truth cases from `benchmark_cases.json` |
| POST | `/dev/benchmark/run` | runs `detect()` per case; scores **detected vs expected**; `localization: "pending (JAL-77)"` |

**Safety details**
- `{name}` for preview/drop must be in the current `SHOW TABLES` set — reject otherwise (prevents
  arbitrary SQL via the path).
- Drop confirm is checked server-side, not just in the browser.
- Job registry is a process-local dict; `data.load.main()` runs in a `threading.Thread`, its stdout
  captured into the job log via `contextlib.redirect_stdout`.

## In-memory override contract

```python
det = config()["detection"]
snapshot = copy.deepcopy(det)
try:
    if method: det["method"] = method
    det.update(overrides or {})           # e.g. {"mad_z_threshold": 3.0}
    anomaly, queries = detect(metric, window)
finally:
    det.clear(); det.update(snapshot)      # config.json untouched, next request clean
```

## `benchmark_cases.json` (JAL-77 ground truth, seed)

```json
[
  {"id": "A", "metric": "fill_rate", "window": "2026-06-23..25", "expect_segment": {"os_version": "Android 15"}},
  {"id": "B", "metric": "ecpm",      "window": "2026-06-19..22", "expect_segment": {"category": "finance"}},
  {"id": "C", "metric": "requests",  "window": "2026-06-21",     "expect_segment": null},
  {"id": "D", "metric": "fill_rate", "window": "2026-06-28..30", "expect_segment": {"region": "APAC", "os_version": "iOS 18.1"}}
]
```
Each case needs a concrete target hour to score detection; the harness uses the window start hour for
now and marks multi-day/range handling as a TODO for JAL-77.

## UI (single page, 3 tabs)

- **Tables & Data** — table list w/ counts; click → row preview; per-table Drop (typed-confirm
  modal); "Load all data" (typed `LOAD`, shows live job log via polling).
- **Runs** — investigations table; row → bundle JSON viewer. (Empty until pipeline lands.)
- **Benchmarker** — Playground: metric/hour/method + threshold inputs → Run → anomaly card + SQL;
  "Compare both". Harness: cases list + "Run benchmark" → per-case detected vs expected, localization
  "pending". Red LOCAL-DEV-ONLY banner up top.

## Testing (FastAPI TestClient)

- `/dev/tables` returns names+counts; `/dev/table/{name}` preview; unknown table rejected (400/404).
- drop with wrong `confirm` → 400 and no drop; correct confirm calls drop (patch `run_query`/client
  so no real table is dropped in tests).
- `/dev/detect` with overrides returns an anomaly **and restores** `config.detection` afterward
  (assert the snapshot is back).
- `/dev/compare` returns two methods.
- `/dev/benchmark/cases` returns 4 cases; `/dev/benchmark/run` returns per-case detection results.
- gating: with `ENABLE_DEV_DASHBOARD` false, `/dev` routes are absent (404).

## Rollout order

1. Router skeleton + gated mount + `/dev/tables` + `/dev/table/{name}` (+ tests).
2. Drop (typed confirm) + load background job + `/dev/jobs` (+ tests).
3. Runs endpoints (+ tests).
4. Benchmarker `/dev/detect` (+ override-restore test) + `/dev/compare`.
5. Harness `benchmark_cases.json` + `/dev/benchmark/*` (+ test).
6. `dev_dashboard.html` (the UI).
7. `oneclick/load.ps1` + README/oneclick docs.

## Risks

- **Destructive via browser** — mitigated by typed server-side confirm + table-name allow-listing +
  env gate.
- **Load job vs `--reload`** — editing files mid-load restarts uvicorn and kills the job; the
  dedicated `oneclick/load.ps1` (CLI, no server) is the reliable heavy-load path.
- **`/dev` exposure** — never enable `ENABLE_DEV_DASHBOARD` on a public deploy.
