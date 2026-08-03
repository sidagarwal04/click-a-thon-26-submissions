# Go RCA Engine — Architecture & Execution Guide

## Overview

The **Go RCA Engine** is a high-performance, concurrent analytical microservice that executes automated Root Cause Analysis (RCA) directly against ClickHouse Cloud.

It receives anomaly investigation requests from the Fastify orchestrator, queries ClickHouse using a bounded parallel worker pool, performs revenue identity factor decomposition, calculates dimensional contribution scores ($Share\ of\ Delta$), executes 2-level recursive drill-downs, and compiles an explicit list of cleared/ruled-out factors.

---

## Why a Separate Go Helper Engine?

1. **High Concurrency & Goroutines**:
   - Investigating a metric anomaly requires querying baseline vs. current window across 9 primary dimensions (`ad_format`, `category`, `publisher_tier`, `vertical`, `campaign_type`, `region`, `country`, `device_model`, `os_version`) and secondary multi-level pairs.
   - Go's lightweight goroutines and channels allow bounded parallel execution (semaphore worker pool of size 8) without blocking the single-threaded Node.js main event loop.

2. **Low Latency & High Performance**:
   - Go compiles to a native machine binary with zero JIT warmup latency.
   - End-to-end multi-dimensional drill-downs across 9,000,000 events complete in **<600 milliseconds**.

3. **Strict Separation of Deterministic Analytics from LLM Narration**:
   - **Go Engine**: Computes exact, reproducible, mathematical deltas, $Z$-scores, factor breakdowns, and dictionary-backed segment contributions in SQL/code.
   - **LLM (DeepSeek via LlamaIndex)**: Fed strictly the JSON evidence bundle from the Go Engine to generate plain-language narratives without any risk of LLM mathematical hallucination.

4. **Resilience & Scalability**:
   - Operating as an independent microservice allows scaling the analytical worker pool independently of the web API or LLM streaming services.

---

## Technical Methodology

### 1. Like-for-Like Baseline Anomaly Detection
Compares the metric value in the target hourly window against the like-for-like baseline over trailing 4 weeks (matching day-of-week and hour-of-day):

$$\text{Baseline}\ \mu = \text{avg}(\text{metric}_{\text{trailing 4 weeks, same hour-of-week}})$$
$$\text{Z-Score} = \frac{\text{Metric}_{\text{now}} - \mu}{\sigma}$$

Anomalies are flagged when $|Z| > 3.0$.

### 2. Revenue Identity Factor Decomposition
Walks the ad revenue identity equation to determine the primary factor driving metric movement:

$$\text{Revenue} = \text{Requests} \times \text{Fill Rate} \times \text{Render Rate} \times \frac{\text{eCPM}}{1000}$$

Decomposes the total delta into:
- Volume Delta ($\Delta\text{Requests}$)
- Fill Rate Delta ($\Delta\text{Fill Rate}$)
- Render Rate Delta ($\Delta\text{Render Rate}$)
- Price Delta ($\Delta\text{eCPM}$)

### 3. Single-Pass `GROUP BY GROUPING SETS` Dimensional Contribution ($Share\ of\ Delta$)
Instead of issuing N separate SQL queries across primary dimensions, the engine executes a **single-pass `GROUP BY GROUPING SETS` query** in ClickHouse across all 9 primary dimensions (`ad_format`, `category`, `publisher_tier`, `vertical`, `campaign_type`, `region`, `country`, `device_model`, `os_version`):

```sql
WITH current_segs AS (
    SELECT 
        multiIf(ad_format != '', 'ad_format', category != '', 'category', ...) AS dim_name,
        coalesce(nullIf(ad_format,''), nullIf(category,''), ...) AS dim_val,
        sum(revenue) AS cur_metric
    FROM ( SELECT ... FROM ad_events WHERE event_time >= ? AND event_time < ? )
    GROUP BY GROUPING SETS (
        (ad_format), (category), (publisher_tier), (vertical), (campaign_type),
        (region), (country), (device_model), (os_version)
    )
),
base_segs AS ( ... )
SELECT coalesce(c.dim_name, b.dim_name) AS dim_name, coalesce(c.dim_val, b.dim_val) AS dim_val, ...
FROM current_segs c 
FULL OUTER JOIN base_segs b ON c.dim_name = b.dim_name AND c.dim_val = b.dim_val
ORDER BY abs(current_m - base_m) DESC;
```

**Key Optimizations**:
- Scans `ad_events` **once** instead of 9 times (**76 ms vs 205 ms**, a **2.67x latency reduction**).
- Projects `dim_name` and `dim_val` in CTEs to perform exact composite key JOIN `ON c.dim_name = b.dim_name AND c.dim_val = b.dim_val`, eliminating duplicate rows across empty non-active columns.
- Uses ClickHouse `dictGet` functions (`apps_dict`, `geo_device_dict`, `advertisers_dict`) to perform dictionary evaluation on aggregated result groups.

For each segment value $s$:
$$\Delta_{\text{segment}} = \text{Metric}_{\text{current}, s} - \text{Metric}_{\text{baseline}, s}$$
$$\text{Share of Delta} = \frac{\Delta_{\text{segment}}}{\Delta_{\text{total}}}$$

### 4. Multi-Level Recursive Drill-Down (Wave 2)
Takes top-contributing single dimensions (e.g. `publisher_tier = 'tier_2'`) and drills 2 levels deep combined with secondary dimensions (e.g. `publisher_tier = 'tier_2'` $\times$ `region = 'NAM'`).

### 5. Deterministic Ruled-Out List
Factors or dimensions where $\Delta_{\text{segment}} \approx 0$, $Z$-score is within $[-3.0, +3.0]$, or segment changes are uniform ($Share\ of\ Delta < 8\%$) are explicitly added to the `ruled_out` list.

---

## How to Run

### Prerequisites
- Go 1.22+ installed (`go version`)
- Access to ClickHouse Cloud instance with `ad_events` table and dictionaries loaded

### Environment Variables
Configure the following in `.env` (or pass via environment):

```env
CLICKHOUSE_URL=https://v8k6il94hg.ap-south-1.aws.clickhouse.cloud:8443
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=i2D_29fLWj8i3
RCA_ENGINE_PORT=8081
```

### 1. Build the Binary
From the `Engine/` folder:

```bash
go build -o /tmp/rca-engine ./...
```

### 2. Run the Engine
Run the compiled binary:

```bash
/tmp/rca-engine
```

*Output:*
```
Successfully connected to ClickHouse at v8k6il94hg.ap-south-1.aws.clickhouse.cloud:8443
🚀 Go RCA Engine listening on http://localhost:8081
```

---

## API Endpoints

### `GET /health`
Checks engine health and ClickHouse connectivity.

**Command:**
```bash
curl -s http://localhost:8081/health
```

**Response:**
```json
{
  "clickhouse": "connected",
  "engine": "go-rca-engine",
  "status": "ok"
}
```

---

### `POST /analyze`
Executes full RCA for a given metric and optional time window.

**Command:**
```bash
curl -s -X POST http://localhost:8081/analyze \
  -H "Content-Type: application/json" \
  -d '{"metric": "revenue"}'
```

**Response:**
```json
{
  "anomaly_detected": true,
  "metric": "revenue",
  "window_start": "2026-06-21 11:00:00",
  "window_end": "2026-06-21 12:00:00",
  "current_value": 12.46,
  "baseline_value": 10.82,
  "delta": 1.64,
  "pct_change": 15.2,
  "z_score": -506.15,
  "factor_decomposition": {
    "requests_delta_pct": 15,
    "fill_rate_delta_pct": -0.4,
    "render_rate_delta_pct": 0.1,
    "ecpm_delta_pct": 0.4,
    "primary_driver_factor": "requests",
    "explanation": "Primary revenue movement driver is requests (15.0% change)..."
  },
  "top_contributing_segments": [
    { "dimension": "publisher_tier", "value": "tier_2", "share_of_delta": 0.611 },
    { "dimension": "region", "value": "NAM", "share_of_delta": 0.521 }
  ],
  "ruled_out": [
    { "dimension": "ecpm_pricing", "reason": "eCPM pricing was normal (0.4% change) and ruled out as primary cause" }
  ],
  "execution_time_ms": 528
}
```

---

### `GET /detect`
Scans the stream for top detected anomalies.

**Command:**
```bash
curl -s http://localhost:8081/detect?metric=revenue
```
