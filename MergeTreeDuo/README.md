# MergeTreeDuo

## Track

**SonyLIV**

## Project

**StreamPulse** — Real-time session-aware concurrency analytics for SonyLIV, proving that heartbeat-driven measurement eliminates overcount bias in streaming viewer metrics.

## Team Members

- **Saikiranudayana**
- **BalajiBG**

## What it does

SONY Liv Streaming Analytics Platform is a full-stack streaming analytics platform that addresses a concurrency problem: **Session aware and Session independent**

Traditional concurrency measurement (session-independent) simply counts open connections — inflating numbers by including backgrounded apps, paused players, and idle sessions. Our session-aware approach uses heartbeat signals (~30s intervals) and lifecycle events to count only genuinely active viewers.

The platform provides:
- **Session-Aware vs Session-Independent comparison** — side-by-side visualization proving the overcount gap
- **AI-powered natural language querying** — ask questions in plain English, Claude generates ClickHouse SQL, executes it, and summarizes results
- **Real-time observability** — live ClickHouse query statistics, table health, partition schemes, and pipeline evidence
- **Platform & content breakdown** — concurrency by device type and content, all from real ClickHouse queries
- **Benchmark mode** — one-click fresh execution against both models for live evaluation with unseen datasets

## GitHub link
[Git hub repo link](https://github.com/BalajiBG/MergeTreeDuoclick-a-thon-2026)

## Hosted Demo

**Live:** [http://ec2-54-84-196-101.compute-1.amazonaws.com](http://ec2-54-84-196-101.compute-1.amazonaws.com)

## Demo Video

[https://drive.google.com/file/d/1AtscJK1YlNB7J0fhJ6nUkCtEuG5ks7dx/view?usp=sharing](https://drive.google.com/file/d/1AtscJK1YlNB7J0fhJ6nUkCtEuG5ks7dx/view?usp=sharing)

## Architecture

![Architecture Diagram](evidence_files/architecture.png)

### Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────────────┐
│  DATA SOURCES   │     │   ClickHouse     │     │        FRONTEND (React)         │
│                 │     │   Cloud          │     │                                 │
│ Raw Events CSV ─┼──1──▶ raw_events       │     │  Concurrency Tab                │
│                 │     │ (MergeTree)      │     │  ├─ Session-Aware KPIs          │
│ Content Meta   ─┼──2──▶ active_intervals │     │  ├─ Session-Independent KPIs    │
│ (PostgreSQL CDC)│     │ (Replacing)      │◀─3──┤  ├─ Comparison Chart            │
│                 │     │                  │     │  ├─ Platform Breakdown           │
└─────────────────┘     │ concurrency_     │     │  └─ Playback States             │
                        │ deltas           │     │                                 │
                        │ (SummingMerge)   │     │  AI Chat Tab                    │
                        │                  │     │  └─ Claude → SQL → ClickHouse   │
                        │ session_indep_   │     │                                 │
                        │ concurrency      │     │  Observability Tab              │
                        │ (Aggregating)    │     │  ├─ Query Performance           │
                        │                  │     │  ├─ Table Stats (system.parts)  │
                        │ public_content_  │     │  └─ Partition Schemes           │
                        │ dim (CDC-synced) │     │                                 │
                        └──────────────────┘     └─────────────────────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
              LibreChat    Langfuse    Custom UI
              (Chat+MCP)   (Tracing)   (React+Express)
```

### ClickHouse Tables & Engines

| Table | Engine | Partition | Purpose |
|-------|--------|-----------|---------|
| `raw_events` | MergeTree | `toYYYYMMDD(event_time)` | All streaming events (905K+ rows) |
| `active_intervals` | ReplacingMergeTree | `toYYYYMMDD(active_start_time)` | Computed active playback intervals |
| `concurrency_deltas` | SummingMergeTree | `toYYYYMM(minute)` | +1/-1 deltas for session-aware counting |
| `session_independent_concurrency` | AggregatingMergeTree | `toYYYYMM(minute)` | Unique open sessions per minute |
| `public_content_dim` | ReplacingMergeTree | — | Content metadata (CDC from PostgreSQL) |

### Key Insight

Session-independent concurrency overcounts by **~40-60%** compared to session-aware measurement. This is proven live in the Concurrency Comparison chart with real data from both ClickHouse materialized views running side-by-side.

## How we built it

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Database** | ClickHouse Cloud (Query API, MergeTree family engines) |
| **Backend** | Node.js + Express |
| **Frontend** | React + Recharts |
| **AI** | Claude Sonnet 4.6 (Anthropic API) for natural language → SQL |
| **Infrastructure** | AWS EC2 (t3.micro), nginx, PM2 |
| **Data Pipeline** | ClickPipes (CDC from PostgreSQL), Bulk CSV insert |
| **Observability** | Langfuse (LLM tracing), ClickStack (monitoring) |
| **Chat** | LibreChat + MCP integration |

### What makes it interesting

1. **No hardcoded data** — every number on the dashboard comes from a real ClickHouse query with verifiable `rows_read` and `elapsed_ms` statistics
2. **Sub-10ms query performance** — ClickHouse scans 900K+ rows in under 10ms thanks to MergeTree columnar storage and partition pruning
3. **AI Chat with real SQL execution** — Claude generates ClickHouse SQL from natural language, backend executes it, Claude summarizes results with actual numbers
4. **Grain switching** — minute/hour/day aggregation using `toStartOfHour()` and `toStartOfDay()` ClickHouse functions
5. **Pipeline Evidence** — real-time audit log proving every query was executed against ClickHouse (Copy as JSON for evaluation)
6. **Benchmark button** — one-click fresh execution for live evaluation with unseen datasets

## How to run it

### Prerequisites

- Node.js 18+
- ClickHouse Cloud service with the required tables
- Anthropic API key (for AI Chat)

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/MergeTreeDuoclick-a-thon-2026.git
cd MergeTreeDuoclick-a-thon-2026

# Create environment file
cp .env.example .env
# Edit .env with your credentials:
# CH_KEY_ID=your_clickhouse_key_id
# CH_KEY_SECRET=your_clickhouse_key_secret
# CH_SERVICE_ID=your_clickhouse_service_id
# ANTHROPIC_API_KEY=sk-ant-...
# PORT=4000

# Install all dependencies
npm run install-all

# Run both backend + frontend
npm start
```

- **Backend** runs on `http://localhost:4000`
- **Frontend** runs on `http://localhost:3000`

### Production Deployment (EC2)

```bash
# On EC2 instance
cd frontend && npm run build && cd ..
pm2 start backend/server.js --name concurrency-api
# Configure nginx to serve frontend/build and proxy /api/ to :4000
```

## Evidence Files

| File | Description |
|------|-------------|
| `evidence_files/LangfuseTracing_MergeTreeDuo` | Langfuse LLM tracing configuration and logs |
| `evidence_files/ClickStack_MergeTreeDuo` | ClickStack monitoring and alerting setup |
| `evidence_files/LibreChat_MergeTreeDuo` | LibreChat + MCP integration configuration |

---

*Built in 24 hours at ClickHouse Click-a-thon 2026. All data is synthetic.*
