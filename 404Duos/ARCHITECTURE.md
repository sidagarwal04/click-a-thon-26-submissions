# Architecture — InsightIQ (InMobi track)

**Team:** 404Duos  

1–2 pager for Click-a-thon evaluation. Detail: [docs/architecture.md](./docs/architecture.md), [docs/pipeline.md](./docs/pipeline.md).

## Where analysis runs

**ClickHouse does the analytical work.** The LLM never drills the data.

```
ad_events_raw
      │  MATERIALIZED VIEW mv_hourly
      ▼
agg_hourly  (SummingMergeTree)
      │
      ├─► baseline_hourly     ← same hour-of-day / day-of-week, ~4 prior weeks
      │         │
      │         ▼
      └─► alerts_live         ← noise-floored Z-score, |z| > 3
                │
                ├─► alert_dimension_contributors   ← segment attribution
                └─► alert_observations             ← plain-language CH rows

Node apps/api/src/engine  →  reads the view layer, packages diagnosis + trace
Gemini                    →  narrates evidence JSON only
Langfuse                  →  records chat / investigate / narrate spans
```

Product paths query `alerts_live`, contributors, observations, and `metric_hourly_snapshot` / `agg_hourly` — **not** a raw event scan in the LLM.

## Detect → drill-down → diagnosis

| Step | Mechanism | Trust controls |
|------|-----------|----------------|
| **Detect** | Seasonality-aware expected value + stddev; floor `greatest(stddev, 0.05)` so penny noise cannot explode Z | Threshold `|z| > 3`; daily wall = peak hour per advertiser×metric×day |
| **Drill-down** | Contribution analysis across dimensions (`country`, `os_version`, `ad_format`, `category`, `vertical`, `publisher_tier`, `campaign_type`, …); filters e.g. meaningful `delta` / `contribution` | Segments named with values + contribution %; CH `alert_observations` |
| **Diagnosis** | Deterministic text + citations (actual/expected/z, factor deltas, top segments) | Ruled-out list (requests, eCPM, seasonality); SHA-256 evidence hash; ordered `trace[]` |
| **Narrate** | Gemini Flash Lite | Prompt: only use numbers in evidence JSON; fallback copies engine text if Gemini fails |

## Anomaly & attribution approach

We optimize for **explainability**, not ML sophistication:

1. **Baseline** — same hour × day-of-week over prior ~4 weeks (avoids “weekend looks like an incident”).
2. **Noise floor** — stddev floor collapses ~tens of thousands of noisy candidates into hundreds of significant revenue alerts on the reference load.
3. **Contribution** — localize which slice moved with the metric.
4. **Honesty** — seasonality check can mark “not an incident”; factor walk marks culprit vs ruled_out on the metric tree.

## OSS stack integration — Langfuse

**Required “at least one of ClickStack / Langfuse / LibreChat” → Langfuse.**

| Evidence | Location |
|----------|----------|
| Wiring | `apps/api/src/instrumentation.js` (OTEL → Langfuse), `apps/api/src/index.js` (`propagateAttributes`, `startActiveObservation` on chat/investigate/narrate) |
| Config (redacted) | `apps/api/.env.example` — `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL=https://jp.cloud.langfuse.com` |
| Live role | Every in-app chat completion and investigation narration emits a trace tree judges can open via **public share links** or JSON under `evidence/langfuse/` |
| Hosted proof | Demo video + live chat on https://insight-iq-woad.vercel.app/chat |

LibreChat / ClickStack are **not** used.

## LLM provider

**Google Gemini** (`gemini-flash-lite-latest`) via Generative Language API.

- Low latency/cost for hackathon demos  
- Strict evidence-only system prompt  
- Deterministic engine remains source of truth for numbers  

## Hosted topology

```
Browser → Vercel (apps/web)
            → Railway (apps/api + in-process RCA)
                 → ClickHouse Cloud (insightiq)
                 → Gemini API
                 → Langfuse JP Cloud
```

## Suggested judge walkthrough

1. Open hosted Alerts → pick a critical revenue drop  
2. Investigation: metric tree (culprit / ruled out), segments, diagnosis citations  
3. Confirm seasonality / ruled-out panel  
4. Ask in chat → reply cites engine numbers  
5. Open Langfuse public share (or `evidence/langfuse/*.json`) for that session  
