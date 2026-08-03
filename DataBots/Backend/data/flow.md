# System Architecture & Technical Flow

## Reference Documentation
- **Problem Statement**: [PROBLEM_STATEMENT.md](https://raw.githubusercontent.com/sidagarwal04/click-a-thon-2026/refs/heads/main/InMobi/PROBLEM_STATEMENT.md)
- **Readme / Getting Started**: [README_START_HERE.md](https://raw.githubusercontent.com/sidagarwal04/click-a-thon-2026/refs/heads/main/InMobi/README_START_HERE.md)
- **Metrics Glossary**: [metrics_glossary.md](https://raw.githubusercontent.com/sidagarwal04/click-a-thon-2026/refs/heads/main/InMobi/metrics_glossary.md)

---

## Overview

This document outlines the architecture and execution flow for the InMobi Root Cause Analysis (RCA) Engine. The stack consists of:
- **Fastify API**: Front door service for orchestration and serving endpoints.
- **Go RCA Engine**: Worker pool for concurrent dimension breakdown, contribution scoring, and multi-level recursive drill-downs.
- **ClickHouse Cloud / Local**: Analytical database executing fast z-score anomaly detection and dimensional aggregates using MergeTree tables and external dictionaries.
- **LlamaIndex + DeepSeek**: Strictly constrained LLM narration engine and ReAct-style follow-up chat agent with ClickHouse MCP tools.
- **Langfuse**: Observability and traceability backbone capturing end-to-end spans (SQL execution, RCA timing, LLM calls, tool execution).

---

## System Architecture

```
                          ┌─────────────────────────┐
                          │   ClickHouse Cloud       │
                          │  ad_events (MergeTree)   │
                          │  + Dictionaries for      │
                          │    apps/advertisers/geo  │
                          └────────────┬─────────────┘
                                       │
                    ┌──────────────────┴───────────────────┐
                    │                                       │
          ┌─────────▼─────────┐                  ┌──────────▼──────────┐
          │   Go RCA Engine    │                  │  ClickHouse MCP      │
          │ (fan-out worker    │                  │  (ad-hoc queries for │
          │  pool, decompose,  │                  │   the LlamaIndex     │
          │  rank, recurse)    │                  │   follow-up agent)   │
          └─────────┬──────────┘                  └──────────┬───────────┘
                    │  evidence JSON                          │ tool calls
          ┌─────────▼──────────────────────────────────────────▼──────────┐
          │                     Fastify API                                │
          │  POST /analyze  → detect+drilldown (Go) → narrate (LlamaIndex) │
          │  POST /chat      → LlamaIndex agent w/ MCP tool, follow-ups    │
          └─────────┬────────────────────────────────────────────────────┘
                    │
          ┌─────────▼─────────┐        ┌────────────────────┐
          │  LlamaIndex +      │───────▶│      Langfuse        │
          │  DeepSeek narrator │  spans │ (traces every stage: │
          │                    │        │  SQL, timings, tool  │
          └────────────────────┘        │  calls, LLM turns)   │
                                         └────────────────────┘
```

---

## Key Modules & Pipelines

### 1. ClickHouse Schema & Data Load

Use **Dictionaries** for small dimensions (`apps`, `advertisers`, `geo_device`) to avoid costly runtime JOINs during repeated drill-down queries.

```sql
CREATE TABLE ad_events
(
    event_time    DateTime,
    app_id        UInt32,
    geo_device_id UInt32,
    advertiser_id Nullable(UInt32),
    ad_format     LowCardinality(String),
    is_filled     UInt8,
    is_impression UInt8,
    is_click      UInt8,
    revenue       Float64
)
ENGINE = MergeTree
PARTITION BY toStartOfWeek(event_time)
ORDER BY (event_time, ad_format);

-- Dimension tables as plain MergeTree
CREATE DICTIONARY apps_dict (app_id UInt32, category String, publisher_tier String)
PRIMARY KEY app_id
SOURCE(CLICKHOUSE(TABLE 'apps'))
LAYOUT(HASHED())
LIFETIME(0);
```

#### Loading Data
```bash
# Load Parquet event data
clickhouse-client --query "INSERT INTO ad_events FORMAT Parquet" < ad_events.parquet

# Load Dimension CSVs
clickhouse-client --query "INSERT INTO apps FORMAT CSVWithNames" < apps.csv
```

---

### 2. Anomaly Detection (SQL - Hourly Granularity)

Compares each hour against a like-for-like baseline (same hour-of-week over trailing weeks) instead of a naive flat average.

```sql
WITH hourly AS (
  SELECT toStartOfHour(event_time) AS h,
         count() AS requests,
         sum(is_filled) AS fills,
         sum(is_impression) AS impressions,
         sum(revenue) AS revenue,
         fills / requests AS fill_rate,
         revenue / impressions * 1000 AS ecpm
  FROM ad_events GROUP BY h
),
baseline AS (
  SELECT h,
         avg(fill_rate) OVER (PARTITION BY toDayOfWeek(h), toHour(h)
                               ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS fr_baseline,
         stddevPop(fill_rate) OVER (PARTITION BY toDayOfWeek(h), toHour(h)
                               ORDER BY h ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS fr_std
  FROM hourly
)
SELECT h, (fill_rate - fr_baseline) / nullIf(fr_std, 0) AS z
FROM hourly JOIN baseline USING h
WHERE abs(z) > 3;
```

---

### 3. Go RCA Engine (Concurrent Drill-Down)

Handles bounded concurrent fan-out across dimensions (`ad_format`, `category`, `publisher_tier`, `vertical`, `campaign_type`, `region`, `country`, `device_model`, `os_version`).

```go
type SegmentResult struct {
    Dimension, Value        string
    AnomalyMetric, Baseline float64
    ShareOfDelta            float64 // contribution to total delta
}

func drillDown(ctx context.Context, ch *clickhouse.Conn, window Window, factor string) []SegmentResult {
    dims := []string{"ad_format", "category", "publisher_tier", "vertical",
                      "campaign_type", "region", "country", "device_model", "os_version"}
    results := make(chan SegmentResult, len(dims)*20)
    sem := make(chan struct{}, 8) // bounded worker pool
    var wg sync.WaitGroup

    for _, dim := range dims {
        wg.Add(1)
        go func(dim string) {
            defer wg.Done()
            sem <- struct{}{}; defer func() { <-sem }()
            rows := queryContribution(ctx, ch, dim, window, factor)
            for _, r := range rows { results <- r }
        }(dim)
    }
    go func() { wg.Wait(); close(results) }()

    var all []SegmentResult
    for r := range results { all = append(all, r) }
    sort.Slice(all, func(i, j int) bool { return all[i].ShareOfDelta > all[j].ShareOfDelta })
    return all
}
```

#### Contribution Scoring & Multi-Level Recursion
- **Delta Calculation**: `segment_delta = (segment_metric_now - segment_metric_baseline) * segment_weight`
- **Share of Delta**: `share_of_delta = segment_delta / total_delta`
- **Recursion**: Drill 2 levels deep into top single-dimension segments combined with secondary dimensions (e.g. `device_model = 'Pixel 7'` × `region`).
- **Ruled-Out List**: Dimensions/segments with `share_of_delta ≈ 0` or z-score within normal bounds are retained in evidence JSON as ruled-out causes.

---

### 4. LLM Narration & Chat Agent (LlamaIndex + DeepSeek)

#### Narration (Constrained Prompt)
The narrator is fed strictly the Go RCA evidence JSON:
```
You are given a JSON evidence bundle with: anomaly window, metric, magnitude,
revenue-identity factor breakdown, ranked segments with their computed deltas
and shares, and a ruled_out list. Write a 3-4 sentence plain-language diagnosis.
Every number you state must appear verbatim in the JSON. Do not compute,
estimate, or round differently. If evidence is insufficient, say so explicitly
rather than guessing.
```

#### Interactive Chat Agent
- ReAct agent equipped with **ClickHouse MCP** tool for answering ad-hoc user queries live.
- All query executions and turns are piped directly to **Langfuse**.

---

### 5. API Endpoints (Fastify)

- `POST /analyze`: Accepts `{ metric, window? }` → runs detection & Go RCA → generates narration → returns `{ diagnosis, evidence, trace_id }`.
- `POST /chat`: Handles interactive follow-up questions via LlamaIndex MCP Agent.

---

### 6. Observability (Langfuse Integration)

Captures full trace hierarchy for each investigation:
1. `detect`: Baseline SQL query execution & z-score evaluation.
2. `drilldown:wave1`: Parallel primary dimension query set.
3. `drilldown:wave2`: Two-way interaction sub-queries.
4. `rank`: Contribution scoring & sorting.
5. `narrate`: LLM prompt & DeepSeek response.

---

## 24-Hour Implementation Roadmap

1. **Phase 1**: Load dataset into ClickHouse, configure HASHED dictionaries, verify metrics formulas (`~2h`).
2. **Phase 2**: Implement Detection SQL & Go worker-pool query engine (`~4h`).
3. **Phase 3**: Contribution scoring & multi-level recursive drill-down (`~4h`).
4. **Phase 4**: Wire up Langfuse telemetry spans across all stages (`~2h`).
5. **Phase 5**: Implement LlamaIndex narrator with strict evidence prompt (`~2h`).
6. **Phase 6**: Fastify API routes + ClickHouse MCP follow-up agent (`~3h`).
7. **Phase 7**: Validation against test anomaly scenarios & performance tuning (`~3h`).
