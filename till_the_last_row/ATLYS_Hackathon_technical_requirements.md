# Atlys Track — Full Scope

## The one-liner
Build **3 LLM-powered agents on top of ClickHouse** that automate the whole loop of *feature spec → instrumented tables → PM-ready insights*, plus a **living context layer** that keeps itself fresh, plus **Langfuse tracing** on everything.

---

## Data you get

**8 existing raw event tables** (loaded from Parquet via `data/load.sh` → `data/ddl.sql`):

| Table                                                                                           | Kind                               |
| ----------------------------------------------------------------------------------------------- | ---------------------------------- |
| `destination_card_clicked` → `application_started` → `document_uploaded` → `purchase_completed` | The 4-step conversion **funnel**   |
| `search_typed`, `landing_page_scrolled`, `auth_completed`, `pay_now_clicked`                    | 4 **supporting** engagement events |
~
- ~2.5M rows total. All wide, mostly `Nullable`. Common envelope columns (user_id, application_id, device, os, geo, app_version) + event-specific columns.
- **Deliberately messy** (matches prod): `os = NULL` while `device_type = 'android'`, empty strings, `duplicate_id` / `is_back_filled` markers.
- **Bad legacy sort key**: `ORDER BY (id, timestamp, user_id)` — queries filter by time/segment, never by `id`. Your agent should call this out.

**5 feature specs** in `specs/`, each is a 1-page product brief + `events.ndjson` (~5-6K raw sample events, no schema given). Features:
1. Express Checkout (one-tap payment)
2. Group / Family Applications
3. Visa Status Sharing (viral share links)
4. Abandoned Checkout Recovery (nudges)
5. Instant Forex Add-on (upsell at checkout)

**`base_context.md`** — business overview, entity defs, metric formulas, known-issues log (K1-K7 like *"iOS WebKit OTP autofill regression"*). ⚠️ **Explicitly warned this is imperfect** — spotting contradictions/gaps is part of the Context Agent's job.

**Unseen 6th spec** dropped in final hours of hackathon. Same input to all teams. Your pipeline must run on it end-to-end and produce a **trace that proves your system did the work**.

---

## The 4 things you must build

### 1. Instrumentation Agent
Input: feature spec (markdown brief + raw NDJSON sample)
Output:
- ClickHouse `CREATE TABLE` DDL (column types, ordering key, partitioning, TTL)
- Materialized views / aggregations if needed
- Actually **executes** the DDL against your ClickHouse Cloud service
- Maps raw NDJSON events into the schema

Judges will look at: sensible ordering keys (NOT the legacy `id`-first mistake), partitioning, column types, whether MVs earn their keep.

### 2. Analytics Agent
Input: newly instrumented tables + existing tables + context layer
Output: **PM-ready insight summary** — not charts, actionable text with the *why*.

Must do:
- Statistical analysis (trends, anomalies, segment comparisons, correlations)
- Multi-cut analysis (device, geo, funnel stage, user segment)
- Apply context — e.g. *"iOS checkout drop coincides with known K1 OTP autofill regression"*
- **Push compute into ClickHouse**, use LLM only to interpret. Streaming raw rows to the LLM = token burn = judges mark you down.

### 3. Context Agent
Maintains a **living context layer**:
- Detects new tables/columns and updates business defs, metric formulas, entity relationships
- **Surfaces contradictions and gaps** in `base_context.md` (there are planted ones)
- Feeds fresh context to Analytics Agent on every run
- Storage choice is yours (file, ClickHouse table, vector store) — must justify the choice

### 4. Tracing + Visualization
- **Langfuse traces** on all 3 agents — what each did, why, on what context. This is the *hard evaluation gate*: **"No trace, no credit"** for the unseen-spec output.
- Optional: ClickStack for system-level observability.
- Viz layer (dashboard / lightweight UI / structured CLI) showing:
  - Schema changes over time
  - Agent-generated insights with confidence scores
  - Context layer diff / changelog

---

## Hard constraints

|                   |                                                                                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Datastore         | ClickHouse (Cloud, your team's service, event credits)                                                                                                              |
| Must integrate    | At least one of: **Langfuse** (LLM tracing), **ClickStack** (obs), **LibreChat** (chat UI). Superficial inclusion won't count. **Langfuse is the natural fit here.** |
| LLM               | Any provider, your own keys                                                                                                                                         |
| Agent framework   | Any language, any framework                                                                                                                                         |
| Human-in-the-loop | Allowed during build (e.g., approving a schema). But the **unseen 6th spec output must come from your pipeline**, evidenced by trace                                |
| Out of scope      | Auth, deploy, streaming ingestion, polished frontend                                                                                                                |

---

## Evaluation weight (from the docs)

1. **Schema quality** — ordering keys, partitioning, MV justification
2. **Insight quality** — would a PM act on this?
3. **Context freshness** — does Analytics Agent actually reason with updated context, or a stale snapshot?
4. **Traceability** — judge should be able to open Langfuse and follow the reasoning chain
5. **The unseen 6th spec** — carries **significant weight**. Every team gets identical input at the same time. Systems tuned only to the 5 known specs will crack.

---

## Suggested attack plan (24h)

| Hour  | Work                                                                                                                                                                          |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0-2   | Load 8 tables into CH Cloud. Get MCP server + Langfuse up. Pick agent framework (LangGraph / CrewAI / plain OpenAI+tools).                                                    |
| 2-6   | **Instrumentation Agent MVP** on spec 01. NDJSON → sampled schema inference → LLM proposes DDL → validated → executed.                                                        |
| 6-10  | **Context Agent**: parse `base_context.md` + live schema; store as structured (CH table works well). Diff-on-change. Plant contradiction detection.                           |
| 10-14 | **Analytics Agent**: query-planning loop. LLM proposes questions from spec → generates CH SQL (via MCP) → CH executes → LLM narrates. Reference K1-K7 known issues explicitly. |
| 14-18 | Run all 5 specs end-to-end. Fix breakage. Langfuse traces clean and readable.                                                                                                 |
| 18-22 | Viz layer + insight confidence scoring + context-diff view.                                                                                                                   |
| 22-24 | Unseen 6th spec drops — run pipeline, package trace + output.                                                                                                                 |

## Key risks to plan for now
- **Token burn**: enforce "compute in CH, narrate in LLM" from hour zero. Never stream rows into LLM context — pass aggregates only.
- **Schema quality**: the DDL your agent generates must NOT copy the bad legacy `ORDER BY (id, ...)` pattern. Prompt it explicitly to reason about ordering keys from query patterns.
- **Context staleness**: the Context Agent must be triggered by schema changes, not just at startup. Otherwise Analytics Agent works from stale defs after Instrumentation runs.
- **Trace hygiene**: every LLM call, every SQL query, every context read → all in Langfuse with sensible span names. This is a hard gate.
- **Unseen spec brittleness**: don't hardcode spec-specific logic. Your Instrumentation Agent must be generic enough to handle a spec it has never seen.
