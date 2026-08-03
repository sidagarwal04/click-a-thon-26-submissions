# InsightMesh Execution Guide (`RUN.md`)
### Click-a-thon 2026 Submission Runbook

This guide contains everything required to configure, test, and run the **InsightMesh** multi-agent pipeline end-to-end.

---

## 1. Environment Variables & Prerequisites

Create a `.env` file in the project root or in `src/atlys_agentic/config/.env`:

```ini
# ==============================================================================
# 1. ClickHouse Cloud Connection ('default' database)
# ==============================================================================
CLICKHOUSE_HOST=your-clickhouse-instance.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-clickhouse-password
CLICKHOUSE_DATABASE=default
CLICKHOUSE_SECURE=true

# ==============================================================================
# 2. Embedded Metadata & Context Datastore (chDB)
# ==============================================================================
CHDB_PATH=./chdb_data

# ==============================================================================
# 3. LLM Provider (Google Gemini via LiteLLM)
# ==============================================================================
LLM_MODEL=gemini/gemini-3-flash-preview
GEMINI_API_KEY=your-gemini-api-key

# ==============================================================================
# 4. Observability & Tracing (Langfuse)
# ==============================================================================
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
LANGFUSE_TRACING_ENABLED=true

# ==============================================================================
# 5. CrewAI Settings
# ==============================================================================
CREWAI_DISABLE_TELEMETRY=true
```

---

## 2. Installation

```bash
# Clone the repository
git clone https://github.com/deepesh17feb/InsightMesh.git
cd InsightMesh

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install --upgrade pip
pip install -e .
```

---

## 3. One-Command End-to-End Pipeline Execution

### A. Run Full Test Suite & Invariant Verification
```bash
pytest -v
```

### B. Ingest a Feature Specification (CUJ 1)
To run the automated schema design, invariant validation, and gated ClickHouse Cloud deployment:

```bash
# Dry run proposal review (generates DDL, MV, and Context Diff without Cloud execution)
python -m atlys_agentic.run_ingestion --spec_dir "problem statment/specs/01_express_checkout" --dry-run

# Interactive live deployment (prompts for 'APPROVE' before ClickHouse Cloud execution & event loading)
python -m atlys_agentic.run_ingestion --spec_dir "problem statment/specs/01_express_checkout"
```

### C. Ingest the Unseen Spec (06_unseen)
```bash
python -m atlys_agentic.run_ingestion --spec_dir "problem statment/specs/06_unseen"
```

---

## 4. Starting the Web UI Surfaces

### Start FastAPI Backend (Port 8008)
```bash
python -m atlys_agentic.run_chat
# Or: uvicorn atlys_agentic.run_chat:app --host 0.0.0.0 --port 8008 --reload
```
Healthcheck: `curl http://localhost:8008/healthz` $\rightarrow$ `{"status":"ok"}`

### Start LibreChat Conversational Interface (Port 3080)
```bash
docker compose -f src/atlys_agentic/librechat/docker-compose.librechat.yml up -d
```
Open **`http://localhost:3080`** in your browser.

- **`Atlys Instrumentation Engineer`** (`atlys-instrumentation`): Ask to review, design, and deploy feature specifications (`spec.md`).
- **`Atlys Product Analyst`** (`atlys-analyst`): Ask natural language product and conversion questions across any instrumented table.

---

## 5. Artifact Outputs

Generated schemas, run reports, and diagnostic insights are persisted in:
```text
outputs/submission/
├── 01_express_checkout/
│   ├── schema.sql              # ClickHouse MergeTree DDL & SummingMergeTree MV
│   ├── run_report.md           # Execution log, context audit & Langfuse trace link
│   └── insight_report.md       # Multi-cut diagnostic insight report
└── 06_unseen/
    ├── schema.sql              # Unseen round ClickHouse DDL & MV
    ├── run_report.md           # Ingestion receipt, 5,363 rows loaded, trace link
    └── insight_report.md       # Coupon funnel & rejection analysis
```
