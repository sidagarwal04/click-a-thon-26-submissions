# Epic: Foreground-Only Concurrency at Streaming Scale

**Project:** Click-a-thon 2026 · SonyLIV

**Goal:** Build a ClickHouse-based pipeline that counts only *actively watching* viewers per minute (excluding backgrounded/paused time), answers peak/average concurrency at minute/hour/day grain with dimension filters, stays update-friendly for open sessions, and produces benchmark answers with pipeline evidence for the unseen day.

---

## MVP (Minimum Viable Product)

The MVP is the smallest end-to-end system that passes correctness and latency checks on the benchmark set:

1. **Ingest** raw events + content metadata into ClickHouse (`.csv` → tables).
2. **Enrich** raw events with content attributes (title, video_type, category) via real-time join.
3. **Active-state logic** — derive foreground-only active intervals using:
   - `AppBackgrounded` / `AppForegrounded` to cut inactive windows
   - heartbeat gap timeout (90s) to close stale intervals
   - dedup of late/duplicate events
4. **Aggregation model** — interval→delta (+1/−1) with a pre-aggregated **serving table** keyed by `(minute, platform, country, content_id, video_type)` so dashboards never rescan raw history.
5. **Benchmark queries** — peak & average concurrency at minute/hour/day grain with dimension filters, reading from the serving table at dashboard-grade latency.
6. **Open-session handling** — incremental delta updates as new heartbeats arrive (no full rebuild).
7. **One integration** — ClickStack (pipeline observability: ingestion lag + query latency) or LibreChat (chat over concurrency data).
8. **Evidence** — `system.query_log` / traces proving unseen-day answers ran through the pipeline.

### MVP Out of Scope
- Production deployment, auth, polished frontend (minimal visualization is enough)
- LLM on the core path (optional add-on only)
- 100x tuning beyond documented reasoning

---

## Must-Have Stories (MVP)

| ID | Story | Priority |
|----|-------|----------|
| [US-01](stories/US-01-foreground-concurrency-per-minute.md) | Foreground-only concurrency per minute | P0 |
| [US-02](stories/US-02-peak-concurrency.md) | Peak concurrency over a range | P0 |
| [US-03](stories/US-03-average-concurrency.md) | Average concurrency over a range | P0 |
| [US-04](stories/US-04-dimension-filtered-concurrency.md) | Dimension-filtered concurrency | P0 |
| [US-05](stories/US-05-time-grains.md) | Multiple time grains (minute/hour/day) | P0 |
| [US-06](stories/US-06-exclude-backgrounded.md) | Exclude backgrounded time | P0 |
| [US-07](stories/US-07-missing-heartbeat-rule.md) | Active interval when heartbeat missing | P0 |
| [US-08](stories/US-08-open-sessions-incremental.md) | Open sessions update incrementally | P0 |
| [US-10](stories/US-10-late-duplicate-events.md) | Late / duplicate event handling | P0 |
| [US-11](stories/US-11-content-enrichment.md) | Real-time content metadata enrichment | P0 |
| [US-12](stories/US-12-serving-layer.md) | Serving layer for dashboards | P0 |
| [US-16](stories/US-16-unseen-day.md) | Unseen-day benchmark answers + evidence | P0 |

## Should-Have Stories (Post-MVP)

| ID | Story | Priority |
|----|-------|----------|
| [US-09](stories/US-09-session-aware-vs-independent.md) | Session-aware vs session-independent parity | P1 |
| [US-13](stories/US-13-incremental-compaction.md) | Incremental compaction of finalized sessions | P1 |
| [US-14](stories/US-14-pipeline-observability.md) | Pipeline observability (integration requirement) | P1 |
| [US-15](stories/US-15-scalability-100x.md) | Scalability framing (100x) | P1 |
| [US-17](stories/US-17-demo-replay.md) | Live-event concurrency replay (demo) | P1 |

---

## Data Schema Reference

Raw data: `data/ch-hackathon-raw-data.csv`
`video_session_id, user_id, content_id, event_type, event, event_timestamp, platform, app_version, country, audio_language, subtitle_language, player_version, session_start_epoch`

Content data: `data/ch-hackathon-content-data.csv`
`content_id, title, video_type, category`

> **Labels:** `[NOW]` = query runs on the CSVs as-is; `[BUILD]` = requires the aggregated/serving tables built in this epic. Full dictionary: `SonyLiv/dataset_details.md`.
