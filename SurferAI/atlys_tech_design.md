# Atlys Agentic Analytics System — Technical Design Document

## Goal Description
The objective is to build a fully automated, agentic data pipeline for Atlys as defined in the Click-a-thon 2026 problem statement. The system eliminates manual data engineering by processing product feature specifications (Markdown) and raw event logs (NDJSON) to automatically generate ClickHouse schemas, maintain a living context layer, and output actionable product insights.

The chosen technology stack relies on **CrewAI** for multi-agent orchestration, **ClickHouse Cloud** for live data execution, **chDB** for embedded context storage, and **Langfuse** for mandatory LLM observability.

## User Review Required
> [!IMPORTANT]
> This architecture strictly prohibits the use of generic CrewAI LLM memory (Short-term/Long-term/Entity) to prevent context hallucination. All context will be handled strictly via explicit SQL routing to `chDB`. Please confirm this aggressive engineering constraint is acceptable for this hackathon implementation.

## Bundle Structure (Monorepo)
The entire architecture is housed in a single Python package. While the execution paths (CUJ 1 and CUJ 2) are strictly decoupled for safety, they share the same overarching configuration, tools, and `chDB` context layer.## Proposed Architecture: Decoupled Pipelines (HLD & CUJs)

Based on product scaling needs, the system is explicitly divided into two independent pipelines. This separation prevents a chatbot from accidentally triggering disruptive database schemas while allowing PMs to safely query data in real-time.

### Critical User Journey (CUJ) 1: The Ingestion Pipeline (DevOps / CLI)
- **Actor:** Product Manager (PM) or Developer.
- **Trigger:** A new feature spec folder is merged or submitted.
- **Flow:** The user runs the ingestion CLI (`python run_ingestion.py --spec_dir`). 
- **Agents Involved:** *Instrumentation Engineer* and *Context Librarian*.
- **Human-in-the-Loop (HITL):** Before the agent executes `CREATE TABLE` and `CREATE MATERIALIZED VIEW` on the ClickHouse Cloud, it pauses execution and prints the proposed DDL to the terminal. The human types "APPROVE" to proceed.
- **Outcome:** The database is prepared, and local `chDB` context is updated securely.

### Critical User Journey (CUJ) 2: The Analyst Interface (LibreChat)
- **Actor:** Product Manager (PM).
- **Trigger:** The PM asks an analytical question in the LibreChat conversational UI ("What's the drop-off for Express Checkout?").
- **Flow:** LibreChat acts as the frontend, communicating with the *Product Analyst* agent running in a backend service.
- **Agents Involved:** *Product Analyst* (and implicitly the *Context Librarian* for rules).
- **Security:** This process is strictly read-only. It hits ClickHouse Cloud purely for analytical `SELECT` queries utilizing tools.
- **Outcome:** PM receives real-time, contextually accurate insights natively rendered in chat.

```mermaid
flowchart TD
    subgraph CUJ 1: Ingestion Pipeline (Asynchronous / HITL)
        Dev([Dev/PM]) --> CLI(["run_ingestion.py / LibreChat"])
        CLI --> CL_Ingest[Context Librarian (Sole DB Custodian)]
        CL_Ingest <-->|1. Context Lookup| chDB[(chDB Metadata)]
        CL_Ingest -->|2. Context Briefing| IE[Instrumentation Engineer (No DB Access)]
        IE -->|3. Proposed 6-Pillar DDL & MV| CL_Ingest
        CL_Ingest -->|4. Context Diff & Proposal| Gate{HITL Gate}
        Gate -->|Approve: Context Librarian Deploys| CloudDB[(ClickHouse Cloud)]
        Gate -->|Approve: Context Librarian Updates| chDB
    end

    subgraph CUJ 2: Analyst Interface (Synchronous / Chat)
        PM([PM]) --> LibreChat[LibreChat UI]
        LibreChat --> PA[Product Analyst]
        PA <-->|5. Fetch Rules & Known Issues (K1-K7)| CL_Analyst[Context Librarian]
        CL_Analyst <-->|Read business_context| chDB
        PA <-->|6. Execute Multi-Cut SELECT| CloudDB
        PA -->|7. Return PM Diagnosis| LibreChat
    end
```

---

### Low-Level Design (LLD): Component Breakdown

#### [NEW] Component 1: Entry Point (`main.py`)
Provides the execution wrapper and initialization of credentials.
- **Responsibilities:** Load `.env` details (ClickHouse connection via `clickhouse-connect`, Langfuse API keys). Set up LiteLLM callbacks for CrewAI. Execute the Crew `kickoff()` mapping to the provided CLI argument (spec folder).

#### [NEW] Component 2: Custom Tools Layer (`tools.py`)
This is the "Skills" enforcement layer ensuring the LLMs do not hallucinate math or schemas.
- `Tool_Init_chDB_Context()`: Reads `base_context.md`, uses Python regex to chunk sections, creates a `business_context` table in `chDB`, and inserts the chunks.
- `Tool_Execute_DDL(ddl_string)`: 
  - Connects to ClickHouse Cloud and runs the provided `CREATE TABLE` / `MATERIALIZED VIEW`.
  - Runs identical DDL against the local `chDB` engine to maintain 1:1 metadata parity natively.
- `Tool_Analytics_Compute(query_string)`: Receives a ClickHouse `SELECT` statement (e.g., funnel aggregations), runs them on Cloud, and returns the aggregated JSON response so the LLM doesn't crash pulling raw rows.

#### [NEW] Component 3: Agent Definitions (`agents.py`)
The explicit LLM personas stripped of magic memory modules.
- **Context Librarian**: 
  - *Role:* Business Logic Gatekeeper
  - *Goal:* Query `chDB` using JIT (Just-In-Time) SQL to fetch specific rules/anomalies (e.g. known iOS issues) relevant to the current analytical question.
- **Instrumentation Engineer**: 
  - *Role:* Senior ClickHouse DBA
  - *Goal:* Parse `events.ndjson` and `spec.md` to design highly optimized columnar schemas (using proper `ORDER BY` and Partition keys) and execute them via `Tool_Execute_DDL`.
- **Product Analyst**: 
  - *Role:* Principal Data Scientist
  - *Goal:* Take the Librarian's context and write advanced analytical SQL (`sequenceMatch`, `windowFunnel`) to measure drop-offs, executing them via `Tool_Analytics_Compute`. Synthesize the outputs into a final PM report.

#### [NEW] Component 4: The Task Definitions (`tasks.py`)
The strict `Sequential` loop enforced by CrewAI.
1. `setup_context_task`: Librarian populates `chDB`.
2. `instrumentation_task`: Engineer structures the DB. Output is the final DDL applied.
3. `context_retrieval_task`: Librarian pulls known quirks related to the new DDL. Output is a Markdown string of localized context.
4. `generate_insights_task`: Analyst combines context + SQL math, outputting the final Deliverable Insight formatted text.

---

## Verification Plan

### Automated Tests
1. **Tool Verification:** Create a mock spec `specs/mock_test/`. Run `python test_tools.py` which executes dummy queries via `clickhouse_connect` to verify valid network pathways to ClickHouse Cloud.
2. **Parse & Sync:** Boot `chDB` locally using a `pytest` fixture to verify it accurately ingests `base_context.md` into SQL memory.

### Manual Verification
Upon pressing **'Proceed'** to approve this plan, the user should:
1. Verify the `.env` file credentials match the Atlys Cloud instance.
2. Check the Langfuse dashboard post-run to verify that traces correctly populated under a "Clickathon Run" project.
3. View the ClickHouse Cloud Query Console to verify that the tables from `01_express_checkout` were successfully created natively.

---

## Extended Goals & Future Roadmap

### Feature Extension: External Web & Bug Tracker Search Tool (`Tool_Search_External_Issues`)

#### Motivation & Value
Product conversion anomalies frequently originate outside the application codebase (e.g. zero-day mobile OS regressions, WebKit autofill malfunctions, third-party payment gateway outages, or regional telecom SMS OTP delivery failures). Integrating a targeted external web search capability empowers the **Product Analyst** agent to cross-verify live ClickHouse anomaly cuts against public vendor issue trackers and status portals.

#### Architectural Design & Guardrails
1. **Strict Separation of Ground Truth (Zero Hallucination Policy)**:
   - **Internal Ground Truth (Immutable)**: All internal metric formulas, denominator rules (`purchases/sessions` vs `purchases/application_started`), table schemas, and business thresholds remain strictly anchored to `chDB.business_context` and ClickHouse Cloud `schema_registry`.
   - **External Search (Correlation Only)**: The search tool is strictly barred from redefining internal KPIs, schemas, or metric boundaries. It is used solely to verify external root causes (e.g., *"WebKit Bugzilla issue #25412 regarding iOS 17.4 OTP paste failure"*).
2. **Dedicated Tool Definition**:
   - Tool Name: `Tool_Search_External_Issues(query: str, domain: str)`
   - Backends: Scoped API integration with Tavily, SerperDev, or DuckDuckGo Search API.
   - Target Surfaces: Apple Developer Forums, WebKit Bugzilla, Chromium Issue Tracker, Android WebView release notes, and payment gateway status dashboards (Stripe, Razorpay, UPI).
3. **Langfuse Observability & Lineage**:
   - Every external search execution records input queries, cited URLs, and retrieved snippets as distinct spans (`mcp::web_search` or `tool::external_search`) nested within the parent Langfuse trace tree.
4. **Confidence Score Calibration**:
   - External corroboration from official vendor issue trackers increases the analyst's diagnostic confidence score and embeds external citation links into the executive finding report.

