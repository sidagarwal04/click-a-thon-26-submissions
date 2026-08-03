# RCA report template

Canonical shape for reports served by `rca-api` and rendered by `rca-ui`.
Numbers must come from the investigation ledger — the UI never computes them.

---

## Architecture

```
ClickStack alert
    → POST /webhooks/alerts          (RCA/app/main.py — FastAPI, port 8000)
    → run_investigation(metric_id)   (RCA/app/investigate.py)
         reproduce → decompose → scan_dims → holdout_check
    → ledger                         (verdict + findings + candidates)
    → narrate(ledger)                (RCA/app/narrate.py — one LLM call, grounded)
    → [integration point] persist + expose via rca-api
    → rca-ui                         (React, port 8090 via Docker)
```

| Layer | Role | Computes? |
|-------|------|-----------|
| **RCA engine** (`RCA/app/`) | Detect reproduction, rank segments, holdout, narrate | Yes — all numbers in ClickHouse |
| **rca-api** | Serve stored reports + chart series as JSON | Yes — chart queries only (today: mock series) |
| **rca-ui** | Present sections, tables, filterable charts | No — display only |

**Design rule:** ClickHouse computes, the LLM narrates, the UI displays. A fabricated
number in the narrative costs more than a missed anomaly.

---

## How the template works

### 1. Report list (`GET /api/rca/reports`)

The sidebar shows recent investigations. Each summary row carries enough to pick
a report without loading the full ledger:

- `id`, `title`, `created_at`, `status` (top-level verdict)
- `metric_id`, `window`, `peak_abs_z`

### 2. Report detail (`GET /api/rca/reports/:id`)

Selecting a report loads the full template object. Six UI sections map to ledger fields:

| UI section | Template field | Origin in RCA engine |
|------------|----------------|----------------------|
| **What triggered this RCA** | `trigger` | Alert payload (`title`, `body`) + `reproduce_global` aggregates |
| **What went wrong** | `sections.what_went_wrong` | Narrator §1 or `fallback_summary` from `findings[].global` |
| **Why it happened** | `sections.why_it_happened` + `holdout` | Narrator §3; holdout from `investigate.holdout_check` |
| **Supporting data** | `candidates[]`, charts | `investigate.scan_dims` ranked by contribution |
| **Checked and ruled out** | `ruled_out[]` | Narrator §4; segments that failed holdout |
| **Visualizations** | chart endpoints | `reproduce_global` + segment drill queries |

The `ledger` field on every report is the raw investigation output — same shape
`run_investigation()` returns. The UI sections are a presentation layer over it;
when wired live, `sections.*` can be generated from `narrate(ledger).narrative`
or kept as structured prose derived from the ledger without an LLM.

### 3. Filterable charts

All chart panels share one `RcaFilters` object posted on Apply:

```json
{
  "from": "2026-06-23T00:00:00",
  "to": "2026-06-25T23:00:00",
  "os_versions": ["Android 15"],
  "granularity": "hour"
}
```

| Chart | Endpoint | What it shows |
|-------|----------|---------------|
| Global metric | `POST .../global-series` | `actual` vs `expected` over time (from `reproduce_global`) |
| Segment drill-down | `POST .../segment-series` | Metric sliced by OS (or other dim) over the filter window |
| Contribution bars | `GET .../contributions` | Static ranking from `candidates[]` (not filter-dependent) |

Today `rca-api/mock-series.js` synthesizes chart data shaped like live queries.
When integrated, replace with ClickHouse calls mirroring `reproduce_global` and
segment-scoped deviation SQL from `RCA/app/metric_sql.py`.

### 4. Verdict badges

Top-level `status` mirrors the ledger verdict:

| Verdict | Meaning |
|---------|---------|
| `localized` | Holdout confirmed a single segment as the cause |
| `inconclusive` | Top candidate is a lead, holdout did not confirm |
| `broad_based` | Movement uniform across every tested dimension |
| `not_reproducible` | Alert did not reproduce against current data |

---

## Integrating with the RCA engine

### Current state (as-built)

```
RCA/app/main.py
  POST /webhooks/alerts  →  background: run_investigation → narrate → logger.info
```

The ledger and narrative reach **stdout only**. Sample reports in
`rca-api/sample-reports.js` stand in until persistence is wired.

### Target integration

```
RCA/app/main.py
  POST /webhooks/alerts
    → run_investigation(metric_id, dimension_id)
    → narrate(ledger)
    → persist_report(ledger, narrative, alert_payload)   # new
    → tracing.flush()

rca-api/server.js
  GET  /api/rca/reports              ← read from store
  GET  /api/rca/reports/:id          ← read from store
  POST /api/rca/reports/:id/global-series   ← ClickHouse reproduce_global
  POST /api/rca/reports/:id/segment-series  ← ClickHouse segment query
```

#### Step 1 — Map ledger → report template

After `run_investigation()` returns, build the UI object:

```python
def ledger_to_report(
    ledger: dict, alert: ClickStackAlertPayload, narrative: dict
) -> dict:
    finding = ledger["findings"][0] if ledger.get("findings") else None
    sections = split_narrative(narrative["narrative"])  # 4 paragraphs → 3 section keys
    return {
        "id": f"rca-{ledger['metric_id']}-{uuid4().hex[:8]}",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "title": f"{ledger['metric_id']} — {ledger['verdict']}",
        "status": ledger["verdict"],
        "trigger": {
            "metric_id": ledger["metric_id"],
            "alert_title": alert.title,
            "alert_body": alert.body,
            "window": ledger["window"],
            "dimension_hint": ledger.get("dimension_id"),
            "actual": finding["global"]["actual"],
            "expected": finding["global"]["expected"],
            "peak_abs_z": finding["global"]["peak_abs_z"],
            "hours": finding["global"]["hours"],
        },
        "sections": sections,
        "ruled_out": [
            {"segment": s, "reason": holdout_reason(finding, s)}
            for s in finding.get("ruled_out", [])
        ],
        "candidates": finding["candidates"],
        "holdout": finding["holdout"],
        "ledger": ledger,
    }
```

Reference implementation of ledger shape: `RCA/tests/test_grounding.py` (`LEDGER`).

#### Step 2 — Persist reports

Option A (minimal): append JSON files to a volume mounted into `rca-api`.

Option B (production): ClickHouse table `inmobi.rca_reports`:

```sql
CREATE TABLE inmobi.rca_reports (
    id String,
    created_at DateTime,
    metric_id LowCardinality(String),
    verdict LowCardinality(String),
    window_start DateTime,
    window_end DateTime,
    report_json String   -- full template object including ledger
) ENGINE = MergeTree ORDER BY (created_at, id);
```

Either way, `rca-api` reads from the store instead of `sample-reports.js`.

#### Step 3 — Live chart series

Replace mock series with calls that reuse the RCA engine's SQL builders:

| Chart endpoint | RCA function | SQL source |
|----------------|--------------|------------|
| `global-series` | `reproduce_global(metric_id, start, end)` | `investigate.reproduce_global` |
| `segment-series` | segment deviation over window | `metric_sql.deviation_sql` with dim filter |
| `contributions` | static from stored `candidates[]` | no re-query needed |

Pass the report's `metric_id` and filter `from`/`to` from the UI. Never expose
ClickHouse credentials to the browser — all queries stay in `rca-api` or the
FastAPI process.

#### Step 4 — Docker topology

```yaml
# docker-compose.yml (target)
services:
  rca-agent:          # RCA/app — webhook + investigation
    build: ./RCA
    ports: ["8000:8000"]
    env_file: .env

  rca-api:            # report store + chart queries
    build: ./rca-api
    ports: ["3002:3002"]
    volumes: ["rca-data:/data"]

  rca-ui:             # nginx + static React build
    build: ./rca-ui
    ports: ["8090:80"]
    depends_on: [rca-api]
```

Alert flow: ClickStack → `rca-agent:8000/webhooks/alerts` → persist → UI polls
or refreshes `GET /api/rca/reports`.

---

## Report object (schema)

```json
{
  "id": "rca-android15-fill",
  "created_at": "2026-06-26T08:15:00Z",
  "title": "Global fill rate drop — Android 15 localized",
  "status": "localized",
  "trigger": {
    "metric_id": "fill_rate",
    "alert_title": "fill_rate anomaly (z ≥ 3)",
    "alert_body": "...",
    "window": { "start": "2026-06-23T00:00:00", "end": "2026-06-25T23:00:00" },
    "dimension_hint": "os_version",
    "actual": 0.7499,
    "expected": 0.7813,
    "peak_abs_z": 11.4,
    "hours": 72
  },
  "sections": {
    "what_went_wrong": "...",
    "why_it_happened": "...",
    "supporting_data_summary": "..."
  },
  "ruled_out": [
    { "segment": "publisher_tier=tier_2", "reason": "Holdout did not confirm..." }
  ],
  "candidates": [
    {
      "dim_name": "os_version",
      "dim_value": "Android 15",
      "avg_actual": 0.4287,
      "avg_expected": 0.7449,
      "peak_abs_z": 28.1,
      "contribution": 4208.36
    }
  ],
  "holdout": {
    "candidate": [{ "dim_name": "os_version", "dim_value": "Android 15" }],
    "residual_actual": 0.7841,
    "residual_delta": 0.0029,
    "candidate_delta": -0.3162,
    "verdict": "localized"
  },
  "ledger": { }
}
```

### Ledger finding shape (engine output)

What `run_investigation()` produces — the `ledger` field above:

```python
{
    "metric_id": str,
    "window": {"start": iso, "end": iso},
    "dimension_id": str | None,
    "decomposition": dict | None,  # revenue alerts only
    "findings": [
        {
            "factor": str,
            "global": {"actual", "expected", "hours", "peak_abs_z"},
            "candidates": [
                {
                    "dim_name",
                    "dim_value",
                    "avg_actual",
                    "avg_expected",
                    "peak_abs_z",
                    "contribution",
                },
                ...,
            ],
            "holdout": {
                "candidate",
                "residual_actual",
                "residual_delta",
                "candidate_delta",
                "verdict",
            },
            "interaction": dict | None,
            "verdict": str,
            "ruled_out": [str, ...],
        }
    ],
    "verdict": str,
}
```

---

## API endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/rca/reports` | List of report summaries |
| GET | `/api/rca/reports/:id` | Full report |
| POST | `/api/rca/reports/:id/global-series` | Actual vs expected time series |
| POST | `/api/rca/reports/:id/segment-series` | Metric by segment over time |
| GET | `/api/rca/reports/:id/contributions` | Contribution bar chart data |

### Running today

```bash
docker compose up -d
```

| Service | URL |
|---------|-----|
| RCA UI | http://localhost:8090 |
| RCA API | http://localhost:3002/health |

Sample reports: `rca-api/sample-reports.js` (Android 15 + iOS 18.1 incidents from
the sealed dataset). Replace with live persistence when the RCA engine write path
is connected per § Integrating with the RCA engine above.
