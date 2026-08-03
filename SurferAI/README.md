# Surfer AI

## Track
**Atlys** — *"From feature spec to insight: agents that instrument, analyze, and explain."*

## Project
**InsightMesh** — Autonomous multi-agent telemetry instrumentation, living semantic context governance, and PM-actionable root-cause diagnostics on ClickHouse.

## Team Members
- **Deepesh** ([@deepesh17feb](https://github.com/deepesh17feb))
- **Manoj Goyal** ([@manojgoyal224](https://github.com/manojgoyal224))

---

## Videos
- **Working Demo** - [Link](https://drive.google.com/file/d/1tIQirJLPT-ENii_bnoLiiXF-9hzAAnSK/view?ts=6a6edde2)
- **Architecture Overview** - [Link](https://github.com/deepesh17feb/click-a-thon-26-submissions/blob/main/SurferAI/Arch1.mov)


## 🌐 Hosted Demo & Unified Web Interface

InsightMesh provides a **single unified conversational interface in LibreChat** (`http://localhost:3080`) powered by two dedicated agent models that handle both feature schema instrumentation and diagnostic analytics:

- **LibreChat Web Interface:** `http://localhost:3080` (Docker Compose stack in `src/atlys_agentic/librechat/`)
- **Configured LibreChat Agent Models:**
  1. **`Atlys Instrumentation Engineer` (`atlys-instrumentation`):** Unified CUJ 1 agent for feature spec ingestion, 6-pillar ClickHouse DDL generation, interactive architectural Q&A, and 2-turn Human-in-the-Loop deployment approval (`APPROVE` / `REJECT`).
  2. **`Atlys Product Analyst` (`atlys-analyst`):** Unified CUJ 2 agent for business question answering, 3-guard semantic retrieval, multi-cut ClickHouse aggregations, K1–K7 anomaly correlation, and PM insight synthesis.
- **FastAPI Backend Gateway:** `http://localhost:8008` (OpenAI-compatible `/v1/chat/completions` endpoint connecting LibreChat to CrewAI Flows)
- **Langfuse Semantic Tracing Project:** [Langfuse Project Dashboard](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9)

---

## What It Does

InsightMesh from Surfer AI is an enterprise-grade agentic data platform that collapses the manual, multi-week "tracking-PRD $\rightarrow$ schema engineering $\rightarrow$ analytical insight" cycle into a fully automated, traceable, and inspectable conversational pipeline within LibreChat:

1. **Instrumentation Agent (CUJ 1 in LibreChat):** Ingests product feature specifications (`spec.md`) and raw event streams (`events.ndjson`), infers 6-pillar ClickHouse schemas (query-predicate ordering `(timestamp, user_id)`, monthly partitioning `toYYYYMM(timestamp)`, `LowCardinality` dictionary encodings, 12-month TTL, and `SummingMergeTree` materialized views), validates storage invariants with bounded retry, and executes deployment behind a 2-turn Human-in-the-Loop (HITL) approval gate directly in the chat window.
2. **Context Agent (Librarian & Governance):** Serves as the sole database and metadata custodian. Maintains a living, versioned context layer in embedded **chDB** (`business_context`, `schema_registry`, `context_changelog`, `table_semantics`, and `insights`). Proactively flags metric denominator conflicts, data quality caveats (e.g. Android `os IS NULL`), and undocumented schema gaps.
3. **Query Architect:** A precision SQL translation compiler shared across CUJ 1 and CUJ 2. Translates design intent into production ClickHouse DDL and analytical intent into typed `PlannedQuery` objects (5 cuts, intersection, daily time-series, alt-denominator headline) with strict origin tracking (`architect_llm` vs `architect_fallback`).
4. **Analytics Agent (CUJ 2 in LibreChat):** Translates natural-language business questions into multi-cut ClickHouse aggregations (device, country, destination, funnel stage, guest status), evaluates known platform issues (K1–K7), derives causal concentration ratios and date coincidences, enforces honest refusal on post-purchase metric boundary traps without hallucinating numbers, and synthesizes executive PM reports with calibrated confidence scores.

---

## The Stack & Integration Architecture

```
                    ┌───────────────────────────────────────────────────────────┐
                    │                    InsightMesh Engine                     │
                    ├─────────────────────────────┬─────────────────────────────┤
                    │ ClickHouse Cloud ('default')│  2.5M Events Analytical DB  │
                    │  chDB (In-Process SQL)      │  Living Context & Vectors   │
                    │  CrewAI Flows               │  Deterministic Workflows    │
                    │  LibreChat (Unified UI)     │  2 Configured Agent Models  │
                    │  Langfuse & ClickStack      │  Two-Tier Observability     │
                    │  LiteLLM + Google Gemini    │  Zero-Temp Reasoning & Emb  │
                    └─────────────────────────────┴─────────────────────────────┘
```

| Technology / Component | Version / Identifier | Architectural Role & Implementation Details |
| :--- | :--- | :--- |
| **Primary Datastore** | **ClickHouse Cloud** (`CLICKHOUSE_DATABASE=default`) | Analytical datastore holding **2,479,858 historical events** across 8 foundation tables plus newly ingested feature tables. Executes `windowFunnel`, `cosineDistance`, `SummingMergeTree` rollups, and multi-cut aggregations. |
| **Context Datastore** | **chDB** (Embedded ClickHouse) | In-process ClickHouse engine (`metadata.sqlite` / local chDB session) storing 5 versioned tables: `schema_registry`, `business_context`, `context_changelog`, `table_semantics`, and `insights`. Zero dialect mismatch with ClickHouse Cloud. |
| **Agent Framework** | **CrewAI Flows** | Deterministic sequential execution flows (`IngestionFlow` and `AnalysisFlow`) with strict `memory=False` to prevent opaque context hallucinations. All context is fetched JIT via explicit SQL. |
| **Unified Interface** | **LibreChat** (Docker Compose) | Unified conversational UI on port 3080 with 2 configured agent models (`atlys-instrumentation` and `atlys-analyst`). State is maintained statelessly across turns via invisible HTML comments (`<!-- atlys:proposal -->`, `<!-- atlys:insight -->`). |
| **Semantic Tracing** | **Langfuse** | End-to-end tracing across every agent step, prompt generation, tool execution, and context provenance. Every span records `input`, `output`, `metadata.agent`, and `metadata.why`. |
| **System Observability**| **ClickStack / OpenTelemetry** | OpenTelemetry spans exporting query latencies, rows read, DDL execution time, and error metrics to ClickStack / HyperDX, correlated to Langfuse via a shared `trace_id`. |
| **LLM Provider** | **Google Gemini** (`gemini/gemini-3-flash-preview`) | High-speed, high-reasoning LLM running at `temperature=0.0` for determinism. Embeddings generated via `text-embedding-004` (768 dimensions). |

---

## 📊 Foundation Dataset & ClickHouse Benchmark Evidence

The system was evaluated against Atlys's 8 foundation event tables loaded into ClickHouse Cloud (`CLICKHOUSE_DATABASE=default`):

```sql
SELECT table, total_rows FROM system.tables WHERE database = 'default' AND engine LIKE '%MergeTree%';
```

| Table Name | Category | Verified Rows in ClickHouse Cloud | Primary Sorting Key |
| :--- | :--- | :---: | :--- |
| `destination_card_clicked` | Top of Funnel | **1,000,000** | `(timestamp, user_id)` |
| `search_typed` | Discovery | **599,630** | `(timestamp, user_id)` |
| `landing_page_scrolled` | Engagement | **499,786** | `(timestamp, user_id)` |
| `auth_completed` | Auth & Signup | **183,790** | `(timestamp, user_id)` |
| `application_started` | Stage 1 Funnel | **154,413** | `(timestamp, user_id)` |
| `document_uploaded` | Stage 2 Funnel | **20,446** | `(timestamp, user_id)` |
| `pay_now_clicked` | Checkout Intent | **14,739** | `(timestamp, user_id)` |
| `purchase_completed` | Stage 4 Conversion | **7,054** | `(timestamp, user_id)` |
| **Total Foundation Events** | — | **2,479,858** | **100% Referential Match** |

### Benchmark Results
- **15-Call Benchmark Suite:** `15/15 Passed (100%)`
- **Overall Query Latency:** **`376.83 ms`** average across 2,479,858 rows (Easy: 519.87ms, Medium: 252.63ms, Hard: 357.98ms).
- **Core Derived Baseline:** Funnel conversion rate: **4.57%** (7,054 purchases / 154,413 started applications); Gross Platform Revenue: **$19,627,982.00**.

---

## 🚀 Quick-Start Setup & Execution (`RUN.md`)

### 1. Prerequisites
- **Python**: `3.11+`
- **ClickHouse Cloud**: Active connection credentials
- **Google Gemini API Key**: `GEMINI_API_KEY`
- **Langfuse Keys**: `LANGFUSE_PUBLIC_KEY` & `LANGFUSE_SECRET_KEY`
- **Docker Compose**: For running LibreChat

### 2. Virtual Environment & Package Installation
```bash
# Clone the repository
git clone https://github.com/deepesh17feb/InsightMesh.git
cd InsightMesh

# Create and activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install --upgrade pip
pip install -e .
```

### 3. Environment Configuration
Create `.env` in the root directory or in `src/atlys_agentic/config/.env`:
```ini
CLICKHOUSE_HOST=your-clickhouse-host.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-password
CLICKHOUSE_DATABASE=default
CLICKHOUSE_SECURE=true

CHDB_PATH=./chdb_data

LLM_MODEL=gemini/gemini-3-flash-preview
GEMINI_API_KEY=your-gemini-api-key

LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_TRACING_ENABLED=true

CREWAI_DISABLE_TELEMETRY=true
```

### 4. Running the Complete System End-to-End in LibreChat

#### A. Run Test Suite & Invariant Safety Suite (88 tests)
```bash
pytest -v
```

#### B. Launch Unified LibreChat Services
```bash
# Terminal 1: Launch FastAPI backend gateway (Port 8008)
python -m atlys_agentic.run_chat

# Terminal 2: Launch LibreChat Web UI (Port 3080)
docker compose -f src/atlys_agentic/librechat/docker-compose.librechat.yml up -d
```

#### C. Interact with the Two Configured Agents in LibreChat
Open **`http://localhost:3080`** in your browser:

1. **Feature Spec Ingestion (CUJ 1):**
   - In the top model dropdown, select **`Atlys Instrumentation Engineer`** (`atlys-instrumentation`).
   - Type `ingest 01_express_checkout` (or `ingest problem statment/specs/06_unseen`).
   - The agent returns the 6-pillar ClickHouse storage proposal and SummingMergeTree MV with full rationale.
   - You can ask follow-up questions (e.g., *"Why is timestamp first in ORDER BY?"*).
   - Type **`APPROVE`** to deploy the DDL to ClickHouse Cloud, stream raw events, update `schema_registry`, and register table semantics.

2. **Diagnostic Product Analytics (CUJ 2):**
   - In the top model dropdown, select **`Atlys Product Analyst`** (`atlys-analyst`).
   - Ask any product diagnostic question (e.g., *"Why did checkout conversion drop on mobile web after the express checkout launch?"*).
   - The agent retrieves candidate tables via `cosineDistance`, runs multi-cut aggregations, correlates with known issues K1–K7, and synthesizes an executive PM report.

---

## 🏆 Scoring Rubric Evidence Summary

| Rubric Criterion | Weight | Key Implementation Evidence | Deep Dive Reference |
| :--- | :---: | :--- | :--- |
| **ClickHouse & OSS Stack** | **25%** | • Live ClickHouse Cloud (`default`) with 2.5M rows.<br>• `windowFunnel`, `cosineDistance` vector search, `SummingMergeTree` rollups, `LowCardinality`, monthly partitions (`toYYYYMM`), non-ID ordering keys `(timestamp, user_id)`, 12-month TTL.<br>• Open-source stack: **CrewAI Flows**, **chDB**, **LibreChat**, **Langfuse**, **LiteLLM**. | [ARCHITECTURE.md §3.2](ARCHITECTURE.md#32-the-five-metadata-tables-in-chdb)<br>[EVALUATION_REPORT.md §2](EVALUATION_REPORT.md#2-clickhouse-cloud-15-call-telemetry-benchmark-table) |
| **Problem Fit** | **20%** | • **CUJ 1**: Automated feature schema evolution with 2-turn HITL gate in LibreChat.<br>• **CUJ 2**: Conversational multi-cut analytics with K1–K7 anomaly correlation.<br>• **Trap Honesty**: Refuses post-purchase metric boundary traps without hallucination. | [ARCHITECTURE.md §6](ARCHITECTURE.md#6-deterministic-cuj-1--cuj-2-workflows-in-librechat)<br>[EVALUATION_REPORT.md §3](EVALUATION_REPORT.md#3-four-level-test-suite-breakdown) |
| **Technical Implementation** | **20%** | • Strict 4-agent roster with Least-Privilege Data Custodianship (Context Agent is sole DB writer; Instrumentation & Query Architect have zero DB access).<br>• Generic LLM error handling with deterministic fallback preceding Instrumentation Engineer.<br>• Invariant safety validator with bounded 1-retry self-healing. | [ARCHITECTURE.md §2 & §4](ARCHITECTURE.md#2-agent-roster-naming-consistency--custodianship-model)<br>[EVALUATION_REPORT.md §4](EVALUATION_REPORT.md#4-known-spec-evaluations-01-to-05) |
| **Innovation** | **20%** | • **No Hidden LLM Memory** (`memory=False`): JIT SQL retrieval prevents hallucination.<br>• **Stateless Chat State**: Invisible HTML comments preserve turn state without server sessions.<br>• **Two-Tier Observability**: Correlated Langfuse semantic traces + ClickStack OTel spans. | [ARCHITECTURE.md §7 & §8](ARCHITECTURE.md#7-stateless-conversation-state-machine-librechat-integration) |
| **Scalability & Impact** | **10%** | • Validated across **2,479,858 ClickHouse Cloud events**.<br>• **376.83 ms average query latency** across 15 real analytical queries.<br>• **100% test pass rate** (88/88 tests passing). | [EVALUATION_REPORT.md §1 & §2](EVALUATION_REPORT.md#1-executive-summary--verification-scorecard) |
| **Presentation** | **5%** | • Native **LibreChat Web UI** with 2 configured agent models.<br>• Comprehensive Mermaid sequence and state diagrams with complete Langfuse trace deep links. | [ARCHITECTURE.md §1.1](ARCHITECTURE.md#11-c4-component-interaction-diagram)<br>[EVALUATION_REPORT.md §5](EVALUATION_REPORT.md#5-graded-surprise-round-spec-06-unseen-evaluation-06_unseen) |

---

## 📁 Submission Deliverables & Trace Index

| Feature Specification | Generated Schema DDL | Execution & Run Report | PM Insight Report | Public Ingestion Trace (CUJ 1) | Public Analytics Trace (CUJ 2) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **01 Express Checkout** | [`schema.sql`](outputs/submission/01_express_checkout/schema.sql) | [`run_report.md`](outputs/submission/01_express_checkout/run_report.md) | [`insight_report.md`](outputs/submission/01_express_checkout/insight_report.md) | [View CUJ 1 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/b3458d1ce2002eeeeb91ea6f00b22652) | [View CUJ 2 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/1f552c04e3c1dcc47c74fa80e847ae5b) |
| **02 Group & Family** | [`schema.sql`](outputs/submission/02_group_family/schema.sql) | [`run_report.md`](outputs/submission/02_group_family/run_report.md) | [`insight_report.md`](outputs/submission/02_group_family/insight_report.md) | [View CUJ 1 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/4691f5638bd841b70e8f1175aec348da) | [View CUJ 2 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/1e28466e35e6dce3f543eae3c5814f18) |
| **03 Status Sharing** | [`schema.sql`](outputs/submission/03_status_sharing/schema.sql) | [`run_report.md`](outputs/submission/03_status_sharing/run_report.md) | [`insight_report.md`](outputs/submission/03_status_sharing/insight_report.md) | [View CUJ 1 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/5ab251e4a0cde1dea807872e252df016) | [View CUJ 2 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/facae71d12671911844267f332e97583) |
| **04 Abandoned Recovery** | [`schema.sql`](outputs/submission/04_abandoned_checkout_recovery/schema.sql) | [`run_report.md`](outputs/submission/04_abandoned_checkout_recovery/run_report.md) | [`insight_report.md`](outputs/submission/04_abandoned_checkout_recovery/insight_report.md) | [View CUJ 1 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/a7e7af3878a96a1b2274894ba66c87b5) | [View CUJ 2 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/583dae0dbcc8d2837bac9106ac94fe19) |
| **05 Instant Forex** | [`schema.sql`](outputs/submission/05_instant_forex/schema.sql) | [`run_report.md`](outputs/submission/05_instant_forex/run_report.md) | [`insight_report.md`](outputs/submission/05_instant_forex/insight_report.md) | [View CUJ 1 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/78887b8990db27c0bc3eae826739f21f) | [View CUJ 2 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/51e71909154adb878463a51c75265e99) |
| **06 Unseen (Surprise Round)** | [`schema.sql`](outputs/submission/06_unseen/schema.sql) | [`run_report.md`](outputs/submission/06_unseen/run_report.md) | [`insight_report.md`](outputs/submission/06_unseen/insight_report.md) | [View CUJ 1 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/a82d9533e2b28b824781eb3bc8a15cc7) | [View CUJ 2 Trace](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/ec89e95c7e782a7fe502a71abbd8bc8b) |

---
*Created for Click-a-thon 2026 Submission by Surfer AI.*
